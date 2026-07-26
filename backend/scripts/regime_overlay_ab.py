#!/usr/bin/env python3
"""
A/B the regime de-risk overlay (Phase 2.5): same engine + window, overlay 0.0
vs 0.4 (or a sweep), replayed in-memory with NO Celery worker and NO DB writes.

Loads the price universe ONCE, then replays each overlay setting through the
SAME ReplayEngine (so the only thing that varies is overlay_strength) and prints
return / max drawdown / alpha vs SPY / trade count side by side. This is the
decisive validation that the overlay cuts bear drawdown without giving back too
much bull — run before any live promotion.

Env:
  AB_ENGINE     = engine_1 | engine_2   (default engine_1)
  AB_START      = YYYY-MM-DD            (default 2022-01-01 — the bear)
  AB_END        = YYYY-MM-DD            (default 2022-12-31)
  AB_MAX_STOCKS = N                     (default 40; keep <=~80 per the OOM ceiling)
  AB_OVERLAYS   = comma list            (default 0.0,0.4)
  AB_STARTING_CASH = float              (default 100000)

Run (in-container, real TA-Lib+scipy):
  docker exec stock_analyzer_backend python /app/scripts/regime_overlay_ab.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, "/app")

from app.db.database import SessionLocal  # noqa: E402
from app.services.backtest.runner import prepare_backtest  # noqa: E402
from app.services.backtest.replay_engine import ReplayEngine, STARTING_CASH  # noqa: E402
from app.services.backtest.fitness import compute_metrics  # noqa: E402
from app.services.backtest.precompute import precompute_inputs  # noqa: E402
from app.services.benchmark_service import get_spy_series_for_window  # noqa: E402


def _spy_return(start, end):
    try:
        s = get_spy_series_for_window(start, end)
        return float(s[-1]["return_pct"]) if s else None
    except Exception as e:
        print(f"[warn] SPY benchmark unavailable: {e}")
        return None


def main():
    engine = os.getenv("AB_ENGINE", "engine_1")
    start = pd.Timestamp(os.getenv("AB_START", "2022-01-01"))
    end = pd.Timestamp(os.getenv("AB_END", "2022-12-31"))
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    max_stocks = int(os.getenv("AB_MAX_STOCKS", "40"))
    overlays = [float(x) for x in os.getenv("AB_OVERLAYS", "0.0,0.4").split(",")]
    starting_cash = float(os.getenv("AB_STARTING_CASH", str(STARTING_CASH)))

    db = SessionLocal()
    try:
        prices_by_stock, trading_dates, symbols = prepare_backtest(db, start, end, max_stocks)
    finally:
        db.close()

    spy = _spy_return(start, end)
    print("=" * 78)
    print(f"REGIME OVERLAY A/B   engine={engine}  window={start.date()}..{end.date()}")
    print(f"universe={len(prices_by_stock)} stocks  trading_days={len(trading_dates)}  "
          f"starting_cash={starting_cash:,.0f}  SPY_window_return={spy}")
    print("-" * 78)

    # Build the per-(stock,T) input cache ONCE: it is weight- AND overlay-
    # independent (the overlay is applied in the cheap scoring step, AFTER the
    # expensive chart/indicator assembly that lives in the bundle). So both
    # overlays reuse the SAME cache -> the second replay is nearly free. This is
    # the GA's path; parallel across CPU cores.
    print("precomputing inputs (parallel, overlay-independent)...")
    cache = precompute_inputs(engine, prices_by_stock, trading_dates)
    print(f"cache built: {len(cache)} (stock,T) bundles")
    print("-" * 78)
    print(f"{'overlay':>8} | {'return%':>9} | {'maxDD%':>8} | {'alpha%':>8} | "
          f"{'trades':>6} | {'config_version':>14}")
    print("-" * 78)

    for ov in overlays:
        account = ReplayEngine(
            engine=engine, starting_cash=starting_cash, overlay_strength=ov,
            input_cache=cache,
        ).run(prices_by_stock, trading_dates)
        m = compute_metrics(account.equity_curve, account.closed, starting_cash, spy)
        ret = m.get("total_return")
        dd = m.get("max_drawdown")
        alpha = m.get("alpha_vs_spy")
        print(f"{ov:>8.2f} | {(ret or 0):>9.2f} | {(dd or 0):>8.2f} | "
              f"{(alpha if alpha is not None else 0):>8.2f} | {len(account.closed):>6} | "
              f"{account.config_version:>14}")
    print("=" * 78)
    print("Read: overlay cuts maxDD (less negative) without tanking return => good.")
    print("      If return collapses more than DD improves, dial strength down / keep OFF.")


if __name__ == "__main__":
    main()
