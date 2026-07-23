"""
Backtest runner (Phase 2): load prices -> replay engine -> metrics/fitness -> persist.

Ties the pieces together for a real run against the DB:
  1. load daily bars per stock with a warmup lookback before ``start_date``
     (engine_2 needs ~250 bars, regime ~100, chart patterns history) — only the
     bars inside [start, end] are used as cycle dates, the earlier bars feed the
     as-of-T truncations;
  2. run the in-memory ``ReplayEngine``;
  3. compute SPY alpha (approximate — see note) + metrics + composite fitness;
  4. persist a ``BacktestRun`` + its ``BacktestEquityPoint`` curve.

SPY alpha note: ``benchmark_service.get_spy_series`` fetches the most-recent SPY
window, so for a historical [start,end] window the alpha is approximate (it is
exact only when the window is recent). Acceptable for a POC; a date-aligned SPY
fetch is a later refinement.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

from app.services.backtest.replay_engine import ReplayEngine, STARTING_CASH
from app.services.backtest.fitness import compute_metrics, fitness
from app.services.benchmark_service import get_spy_series

logger = logging.getLogger(__name__)

# Calendar-day warmup fetched before start_date (engine_2 needs ~250 trading bars).
LOOKBACK_DAYS = 400

# Inputs excluded at price-technical fidelity (documented on each run).
EXCLUDED_INPUTS = ["news_sentiment", "ml_predictions", "dividends", "stock_splits"]


def execute_backtest(db, run) -> Dict:
    """Run a pending/running BacktestRun to completion and persist results onto it.

    ``run`` is a ``BacktestRun`` row whose ``config`` carries the run parameters.
    Mutates + commits ``run`` and writes its equity-curve points.
    """
    cfg = run.config or {}
    engine = run.engine
    start = pd.Timestamp(cfg["start_date"])
    end = pd.Timestamp(cfg["end_date"])
    # DB bar timestamps are tz-aware (timestamptz); localize naive date strings.
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    max_stocks = cfg.get("max_stocks")
    starting_cash = float(cfg.get("starting_cash") or STARTING_CASH)
    dd_penalty = float(cfg.get("dd_penalty") or 0.5)
    trade_count_floor = int(cfg.get("trade_count_floor") or 5)

    prices_by_stock, trading_dates, symbols = _load_prices(db, start, end, max_stocks)

    account = ReplayEngine(engine=engine, starting_cash=starting_cash).run(prices_by_stock, trading_dates)

    # SPY total return over ~the window (approximate for historical windows).
    spy_return = None
    try:
        n_days = max(1, int((end - start).days))
        s = get_spy_series(n_days)
        if s:
            spy_return = float(s[-1]["return_pct"])
    except Exception as e:  # benchmark is best-effort
        logger.warning("[backtest %s] SPY benchmark unavailable: %s", engine, e)

    metrics = compute_metrics(account.equity_curve, account.closed, starting_cash, spy_return)
    fit = fitness(metrics, dd_penalty=dd_penalty, trade_count_floor=trade_count_floor)

    from app.models.backtest import BacktestEquityPoint

    run.metrics = metrics
    run.fitness = fit
    run.config_version = account.config_version
    cfg.update({
        "universe_size": len(prices_by_stock),
        "trading_days": len(trading_dates),
        "excluded_inputs": EXCLUDED_INPUTS,
        "lookback_days": LOOKBACK_DAYS,
    })
    run.config = cfg

    # replace equity points (idempotent under re-run: clear then insert)
    db.query(BacktestEquityPoint).filter(BacktestEquityPoint.run_id == run.id).delete()
    for row in account.equity_curve:
        db.add(BacktestEquityPoint(
            run_id=run.id,
            date=row["date"],
            cash=row["cash"],
            open_positions_value=row["open_positions_value"],
            equity=row["equity"],
            realized_pnl_cumulative=row["realized_pnl_cumulative"],
            open_trades_count=row["open_trades_count"],
        ))
    db.commit()
    return {"run_id": run.id, "engine": engine, "metrics": metrics, "fitness": fit,
            "trading_days": len(trading_dates), "universe_size": len(prices_by_stock)}


def _load_prices(db, start, end, max_stocks: Optional[int]):
    """Load per-stock daily OHLCV DataFrames (with warmup) + the cycle-date set."""
    from app.models.stock import Stock, StockPrice

    warmup = start - pd.Timedelta(days=LOOKBACK_DAYS)
    q = db.query(Stock).order_by(Stock.id)
    if max_stocks:
        q = q.limit(int(max_stocks))
    stocks = q.all()

    prices_by_stock = {}
    cycle_dates = set()
    symbols = {}
    for s in stocks:
        rows = (
            db.query(StockPrice)
            .filter(
                StockPrice.stock_id == s.id,
                StockPrice.timeframe == "1d",
                StockPrice.timestamp >= warmup,
                StockPrice.timestamp <= end,
            )
            .order_by(StockPrice.timestamp.asc())
            .all()
        )
        if len(rows) < 60:
            continue
        df = pd.DataFrame([
            {"timestamp": r.timestamp, "open": float(r.open), "high": float(r.high),
             "low": float(r.low), "close": float(r.close), "volume": int(r.volume or 0)}
            for r in rows
        ])
        # Normalize to one row per calendar day (bars land at varying UTC times
        # across stocks); the backtest cycles once per trading day, and this also
        # keeps the equity-curve (run_id, date) unique.
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.normalize()
        df = df.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp").reset_index(drop=True)
        if len(df) < 60:
            continue
        prices_by_stock[s.id] = df
        symbols[s.id] = s.symbol
        for ts in df["timestamp"]:
            if start <= ts <= end:
                cycle_dates.add(ts)
    return prices_by_stock, sorted(cycle_dates), symbols
