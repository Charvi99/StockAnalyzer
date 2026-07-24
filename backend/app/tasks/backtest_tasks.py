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


@celery_app.task(
    name="app.tasks.backtest_tasks.run_backtest_task",
    # Single backtests over a large universe + multi-year window are long-running
    # (per-bar signal assembly, no input cache). Exempt from the global 31-min
    # task_time_limit — see run_ga_task for the orphaned-row rationale.
    soft_time_limit=21600,
    time_limit=21720,
)
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


@celery_app.task(
    name="app.tasks.backtest_tasks.run_ga_task",
    # GA optimization is long-running by design: a one-time per-(stock,T) input
    # cache build + hundreds of eval replays. Exempt it from the global 31-min
    # task_time_limit (celery_app.py), which hard-kills (SIGKILL via
    # TimeLimitExceeded) a legitimate run mid-optimization and orphans the GARun
    # row at "running". A generous 6h cap still catches true runaways.
    soft_time_limit=21600,
    time_limit=21720,
)
def run_ga_task(ga_run_id: int) -> dict:
    """Run a queued GA weight-optimization (Phase 3): prepare prices -> optimize ->
    persist.

    Builds the per-(stock, T) input cache ONCE, runs the GA over the TRAIN window,
    evaluates the best individual on the unseen VALIDATION window, and persists the
    ``GARun`` + the best individual's TRAIN-window ``BacktestRun`` (equity curve).
    Consumed on the maintenance queue — a GA can take many minutes.
    """
    from datetime import datetime, timezone

    import pandas as pd

    from app.models.backtest import BacktestEquityPoint, BacktestRun, GARun
    from app.services.backtest.ga import GeneticOptimizer
    from app.services.backtest.runner import prepare_backtest

    db = SessionLocal()
    try:
        ga = db.query(GARun).filter(GARun.id == ga_run_id).first()
        if ga is None:
            return {"status": "not_found", "ga_run_id": ga_run_id}
        # Idempotency / restart-safety: ``task_acks_late`` + ``task_reject_on_worker_lost``
        # mean a worker restart mid-run REDELIVERS this task. A redelivered duplicate must
        # NOT clobber an already-terminal run or race a sibling that's already processing
        # it — skip (and ack) instead. Only a genuinely ``pending`` run is started; a
        # stuck-``running`` orphan is left to reconciliation, never double-run.
        if ga.status in ("completed", "failed"):
            logger.info("[ga] run %s already %s — skipping redelivered task", ga_run_id, ga.status)
            return {"status": f"already_{ga.status}", "ga_run_id": ga_run_id}
        if ga.status == "running":
            logger.info("[ga] run %s already running — skipping duplicate task", ga_run_id)
            return {"status": "already_running", "ga_run_id": ga_run_id}
        ga.status = "running"
        ga.started_at = datetime.now(timezone.utc)
        db.commit()

        cfg = ga.config or {}
        engine = ga.engine
        start, end = pd.Timestamp(cfg["start_date"]), pd.Timestamp(cfg["end_date"])
        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        if end.tzinfo is None:
            end = end.tz_localize("UTC")

        prices_by_stock, trading_dates, _symbols = prepare_backtest(
            db, start, end, cfg.get("max_stocks")
        )
        if not trading_dates or not prices_by_stock:
            raise ValueError("no price data in the requested window")

        def _progress(phase, **info):
            """Live GA progress -> write partial ``generations`` + ``best_train_fitness``
            + a phase marker on the GARun row, so the dashboard's 3s poll shows real
            progress (precompute X/N stocks, then generation X/Y with live fitness)
            instead of a bare 'running' status. Best-effort: a write failure is logged
            and swallowed — it must never abort the optimization."""
            try:
                ga.status = "running"
                cfg_now = dict(ga.config or {})
                cfg_now["_progress"] = {"phase": phase, **info}
                ga.config = cfg_now
                if phase == "optimize":
                    ga.generations = info.get("history") or []
                    if info.get("best") is not None:
                        ga.best_train_fitness = float(info["best"])
                db.commit()
            except Exception as e:  # noqa: BLE001
                logger.warning("[ga] progress write failed: %s", e)
                db.rollback()

        opt = GeneticOptimizer(
            engine, prices_by_stock, trading_dates,
            pop_size=int(cfg.get("pop_size") or 20),
            generations=int(cfg.get("generations") or 15),
            seed=int(cfg.get("seed") or 0),
            train_split=float(cfg.get("train_split") or 0.7),
            dd_penalty=float(cfg.get("dd_penalty") or 0.5),
            trade_count_floor=int(cfg.get("trade_count_floor") or 5),
            starting_cash=float(cfg.get("starting_cash") or 100_000.0),
            progress_cb=_progress,
        )
        result = opt.optimize()
        account = result["best_train_account"]

        starting_cash = float(cfg.get("starting_cash") or 100_000.0)
        dd_penalty = float(cfg.get("dd_penalty") or 0.5)
        trade_count_floor = int(cfg.get("trade_count_floor") or 5)

        # Date-aligned SPY over the train (+val) window → a REAL alpha_vs_spy in the
        # metrics (the optimizer passes spy=None, so its metrics otherwise have none).
        from app.services.benchmark_service import get_spy_series_for_window
        from app.services.backtest.fitness import compute_metrics, fitness as compute_fitness

        train_end = opt.train_dates[-1] if opt.train_dates else end
        spy_train = get_spy_series_for_window(start, train_end)
        spy_train_return = float(spy_train[-1]["return_pct"]) if spy_train else None
        train_metrics = compute_metrics(account.equity_curve, account.closed, starting_cash, spy_train_return)

        val_metrics = result["val_metrics"]
        if val_metrics is not None and opt.val_dates:
            spy_val = get_spy_series_for_window(opt.val_dates[0], end)
            spy_val_return = float(spy_val[-1]["return_pct"]) if spy_val else None
            val_metrics = dict(val_metrics)
            val_metrics["alpha_vs_spy"] = (
                val_metrics.get("total_return") - spy_val_return if spy_val_return is not None else None
            )

        # Default-weights baseline ("original engine") over the SAME train window,
        # reusing the optimizer's weight-independent input cache → one cheap replay.
        from app.services.backtest.replay_engine import ReplayEngine
        baseline_account = ReplayEngine(
            engine=engine, weights=None, starting_cash=starting_cash, input_cache=opt.cache_train,
        ).run(prices_by_stock, opt.train_dates)
        baseline_metrics = compute_metrics(
            baseline_account.equity_curve, baseline_account.closed, starting_cash, spy_train_return,
        )
        baseline_fit = compute_fitness(baseline_metrics, dd_penalty=dd_penalty, trade_count_floor=trade_count_floor)

        # Persist the best individual's TRAIN-window replay (equity curve for the UI).
        now = datetime.now(timezone.utc)
        bt = BacktestRun(
            engine=engine, status="completed",
            config={**cfg, "ga_run_id": ga_run_id, "is_validation": False, "weights": result["best_weights"]},
            config_version=account.config_version,
            metrics=train_metrics, fitness=result["train_fitness"],
            started_at=now, completed_at=now,
        )
        db.add(bt)
        db.flush()
        for row in account.equity_curve:
            db.add(BacktestEquityPoint(
                run_id=bt.id, date=row["date"], cash=row["cash"],
                open_positions_value=row["open_positions_value"], equity=row["equity"],
                realized_pnl_cumulative=row["realized_pnl_cumulative"],
                open_trades_count=row["open_trades_count"],
            ))

        # Persist the default-weights baseline run — config-tagged so the GA route
        # locates it and overlays it as the "original engine" comparison line.
        baseline_bt = BacktestRun(
            engine=engine, status="completed",
            config={**cfg, "ga_run_id": ga_run_id, "is_baseline": True, "weights": None},
            config_version=baseline_account.config_version,
            metrics=baseline_metrics, fitness=baseline_fit,
            started_at=now, completed_at=now,
        )
        db.add(baseline_bt)
        db.flush()
        for row in baseline_account.equity_curve:
            db.add(BacktestEquityPoint(
                run_id=baseline_bt.id, date=row["date"], cash=row["cash"],
                open_positions_value=row["open_positions_value"], equity=row["equity"],
                realized_pnl_cumulative=row["realized_pnl_cumulative"],
                open_trades_count=row["open_trades_count"],
            ))

        # Drop the transient _progress marker now that the run is complete (leave the
        # clean param set the launcher wrote — the GET route reads start_date etc.).
        _final_cfg = dict(ga.config or {})
        _final_cfg.pop("_progress", None)
        ga.config = _final_cfg
        ga.best_weights = result["best_weights"]
        ga.best_train_fitness = result["train_fitness"]
        ga.best_val_fitness = result["val_fitness"]
        ga.train_val_gap = result["train_val_gap"]
        ga.best_train_metrics = train_metrics
        ga.best_val_metrics = val_metrics
        ga.generations = result["generations"]
        ga.config_version = account.config_version
        ga.best_train_run_id = bt.id
        ga.status = "completed"
        ga.completed_at = now
        db.commit()

        logger.info(
            "[ga] run %s DONE: train_fit=%s val_fit=%s gap=%s",
            ga_run_id, result["train_fitness"], result["val_fitness"], result["train_val_gap"],
        )
        return {
            "ga_run_id": ga_run_id, "status": "completed",
            "best_train_fitness": result["train_fitness"],
            "best_val_fitness": result["val_fitness"],
            "train_val_gap": result["train_val_gap"],
            "best_train_run_id": bt.id,
        }
    except Exception as e:  # noqa: BLE001 — never leave a GA run stuck in 'running'
        db.rollback()
        ga = db.query(GARun).filter(GARun.id == ga_run_id).first()
        if ga is not None:
            ga.status = "failed"
            ga.error = str(e)
            ga.completed_at = datetime.now(timezone.utc)
            db.commit()
        logger.exception("[ga] run %s failed: %s", ga_run_id, e)
        return {"status": "failed", "ga_run_id": ga_run_id, "error": str(e)}
    finally:
        db.close()
