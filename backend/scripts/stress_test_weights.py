"""
Stress-test a GA run's optimized weights on a DIFFERENT market regime — e.g. take
GA #10's engine_2 weights (fit on the 2024-2026 bull market) and replay them on
the 2022 bear market, head-to-head vs the live DEFAULT weights, on the SAME
universe + cache.

This is the out-of-sample-by-regime check a single train/val split can't give:
does the optimizer's solution survive a market regime it never saw?

Reuses the production pieces exactly (no live-code changes):
  - ``runner.prepare_backtest`` for the price universe (warmup + cycle dates)
  - ``precompute.precompute_inputs`` (parallel) for the weight-independent cache
  - ``replay_engine.ReplayEngine`` with ``weights=`` + ``input_cache=``
  - ``fitness.compute_metrics`` + ``benchmark_service.get_spy_series_for_window``
The cache is weight-independent, so it is built ONCE and replayed for both the
optimized and the default weights (the second replay is near-free).

Run in the container (~25 min for 100 stocks x 1 year on 6 cores; GA done, CPU free):
  docker exec stock_analyzer_backend python /app/scripts/stress_test_weights.py \
      --ga-run-id 10 --start 2022-01-01 --end 2022-12-31 --max-stocks 100
"""
from __future__ import annotations

import argparse
import json
import sys
import time

sys.path.insert(0, "/app")

import pandas as pd  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.models.backtest import GARun  # noqa: E402
from app.services.backtest.runner import prepare_backtest  # noqa: E402
from app.services.backtest.precompute import precompute_inputs  # noqa: E402
from app.services.backtest.replay_engine import ReplayEngine  # noqa: E402
from app.services.backtest.fitness import compute_metrics  # noqa: E402
from app.services.benchmark_service import get_spy_series_for_window  # noqa: E402


def _replay(engine, weights, cache, prices, dates, starting_cash):
    return ReplayEngine(engine=engine, starting_cash=starting_cash,
                        weights=weights, input_cache=cache).run(prices, dates)


def main():
    ap = argparse.ArgumentParser(description="Stress-test a GA run's weights on another regime")
    ap.add_argument("--ga-run-id", type=int, default=10)
    ap.add_argument("--engine", default=None, help="defaults to the GA run's engine")
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--end", default="2022-12-31")
    ap.add_argument("--max-stocks", type=int, default=100)
    ap.add_argument("--starting-cash", type=float, default=100_000.0)
    args = ap.parse_args()

    db = SessionLocal()
    ga = db.query(GARun).filter(GARun.id == args.ga_run_id).first()
    if ga is None:
        print(f"GA run #{args.ga_run_id} not found"); return
    weights = ga.best_weights
    engine = args.engine or ga.engine
    print(f"[stress] GA #{ga.id} engine={engine}  weights={json.dumps(weights)}")
    print(f"[stress] stress window={args.start}..{args.end}  max_stocks={args.max_stocks}")
    if not weights:
        print("GA run has no best_weights — nothing to stress-test"); return

    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    t0 = time.perf_counter()
    prices, dates, symbols = prepare_backtest(db, start, end, args.max_stocks)
    print(f"[stress] universe={len(prices)} stocks  trading_dates={len(dates)}  "
          f"(load: {time.perf_counter()-t0:.0f}s)")

    t0 = time.perf_counter()
    cache = precompute_inputs(engine, prices, dates)
    print(f"[stress] cache built: {len(cache)} bundles  ({time.perf_counter()-t0:.0f}s, parallel)")

    spy = get_spy_series_for_window(start, end)
    spy_ret = float(spy[-1]["return_pct"]) if spy else None
    print(f"[stress] SPY total return over window: {spy_ret}")

    print("[stress] replaying OPTIMIZED weights ...")
    acc_opt = _replay(engine, weights, cache, prices, dates, args.starting_cash)
    m_opt = compute_metrics(acc_opt.equity_curve, acc_opt.closed, args.starting_cash, spy_ret)

    print("[stress] replaying DEFAULT (live) weights ...")
    acc_def = _replay(engine, None, cache, prices, dates, args.starting_cash)
    m_def = compute_metrics(acc_def.equity_curve, acc_def.closed, args.starting_cash, spy_ret)

    db.close()

    cols = ["total_return", "cagr", "sharpe", "calmar", "max_drawdown", "win_rate",
            "profit_factor", "trade_count", "alpha_vs_spy", "final_equity"]
    print(f"\n{'='*72}\nSTRESS TEST - {engine} on {args.start}..{args.end}  "
          f"({len(prices)} stocks)\n{'='*72}")
    print(f"{'metric':<16}{'OPTIMIZED':>16}{'DEFAULT':>16}{'SPY':>16}")
    print("-" * 64)

    def fmt(c, v):
        if v is None:
            return "  -"
        if c in ("total_return", "cagr", "max_drawdown", "alpha_vs_spy"):
            return f"{v*100:+.1f}%"
        if c == "win_rate":
            return f"{v*100:.1f}%"
        if c == "final_equity":
            return f"{v:,.0f}"
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    for c in cols:
        sp = f"{spy_ret:+.1f}%" if (c == "total_return" and spy_ret is not None) else ""
        print(f"{c:<16}{fmt(c, m_opt.get(c)):>16}{fmt(c, m_def.get(c)):>16}{sp:>16}")
    print("\nalpha_vs_spy > 0 => beat the market in this regime. If OPTIMIZED holds")
    print("up (positive alpha / smaller DD than DEFAULT) the weights have regime")
    print("robustness; if it collapses with the market, the 'edge' was bull-market beta.")


if __name__ == "__main__":
    main()
