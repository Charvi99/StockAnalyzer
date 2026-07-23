"""
Celery tasks for the Phase-2 backtester.

Phase 2.0 — ``backfill_daily_5y``: fetch ~5 years of daily bars for every
tracked stock so a historical backtest has enough history to warm up indicator
windows (engine_2 needs ~250 bars) and still leave years of tradeable data.

Daily aggregates are cheap: Polygon's aggregates endpoint returns up to 50,000
bars per call, so 5y of *daily* data is **one API call per ticker** (the
"slow fetch" reputation applies to intraday data, not daily). ~200 tickers → a
few minutes. Idempotent: upserts on the ``(stock_id, timeframe, timestamp)``
primary key, so re-running only refreshes bars.

The backtest run task (``run_backtest``) is added in a later step once the
replay engine + persistence exist.
"""
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.celery_app import celery_app
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)


def _bulk_upsert_daily_bars(db, stock_id: int, bars: list) -> int:
    """Bulk upsert 1d bars into ``stock_prices`` on the composite PK.

    Mirrors the column set ``fetch_stock_data_incremental`` writes
    (adjusted_close = close, matching the existing convention). One statement
    per stock — far faster than the live per-bar query/insert loop.
    """
    from app.models.stock import StockPrice

    if not bars:
        return 0
    rows = [
        {
            "stock_id": stock_id,
            "timeframe": "1d",
            "timestamp": b["timestamp"],
            "open": float(b["open"]),
            "high": float(b["high"]),
            "low": float(b["low"]),
            "close": float(b["close"]),
            "volume": int(b["volume"]),
            "adjusted_close": float(b.get("adjusted_close", b["close"])),
        }
        for b in bars
    ]
    stmt = pg_insert(StockPrice.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "timeframe", "timestamp"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "adjusted_close": stmt.excluded.adjusted_close,
        },
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


@celery_app.task(name="app.tasks.backtest_tasks.backfill_daily_5y")
def backfill_daily_5y(period: str = "5y") -> dict:
    """Backfill ~`period` of daily bars for every Stock. Idempotent + fault-tolerant.

    Run once before the first multi-year backtest. Per-stock failures are logged
    and skipped (a single bad ticker never aborts the backfill).
    """
    from app.models.stock import Stock
    from app.services.polygon_fetcher import PolygonFetcher

    db = SessionLocal()
    ok = failed = 0
    total_bars = 0
    try:
        stocks = db.query(Stock).order_by(Stock.id).all()
        fetcher = PolygonFetcher()
        n_stocks = len(stocks)
        logger.info("[backfill-5y] starting %s daily backfill for %d stocks", period, n_stocks)

        for i, stock in enumerate(stocks, 1):
            try:
                bars = fetcher.fetch_historical_data(stock.symbol, period=period, interval="1d")
                if not bars:
                    logger.warning("[backfill-5y] %s: no data returned", stock.symbol)
                    failed += 1
                    continue
                inserted = _bulk_upsert_daily_bars(db, stock.id, bars)
                total_bars += inserted
                ok += 1
                if i % 20 == 0:
                    logger.info("[backfill-5y] %d/%d stocks done (%d bars so far)", i, n_stocks, total_bars)
            except Exception as e:  # noqa: BLE001 — per-stock fault tolerance
                logger.warning("[backfill-5y] %s failed: %s", stock.symbol, e)
                db.rollback()
                failed += 1

        logger.info("[backfill-5y] DONE: %d ok / %d failed, %d daily bars", ok, failed, total_bars)
        return {"period": period, "stocks_ok": ok, "stocks_failed": failed, "bars": total_bars}
    finally:
        db.close()


@celery_app.task(name="app.tasks.backtest_tasks.run_backtest_task")
def run_backtest_task(run_id: int) -> dict:
    """Execute a queued BacktestRun: load -> replay -> metrics -> persist.

    Flips the run row status running -> completed/failed. Consumed on the
    maintenance queue (a backtest can take minutes)."""
    from datetime import datetime, timezone

    from app.models.backtest import BacktestRun
    from app.services.backtest.runner import execute_backtest

    db = SessionLocal()
    try:
        run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
        if run is None:
            return {"status": "not_found", "run_id": run_id}
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        try:
            result = execute_backtest(db, run)
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return result
        except Exception as e:  # noqa: BLE001 — never leave a run stuck in 'running'
            db.rollback()
            run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
            if run is not None:
                run.status = "failed"
                run.error = str(e)
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
            logger.exception("[backtest] run %s failed: %s", run_id, e)
            return {"status": "failed", "run_id": run_id, "error": str(e)}
    finally:
        db.close()
