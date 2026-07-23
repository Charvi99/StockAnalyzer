"""
Replay-engine sanity test (Phase 2). Pure-Python, no DB:
``python3 backend/tests/test_backtest_engine.py``.

Validates the in-memory replay on synthetic data:
  - accounting conservation: at every snapshot
        equity == cash + open_positions_value,
    and at the final state
        last_equity == starting_cash + Σ(realized) + Σ(unrealized).
  - no exit on the birth bar (every closed trade has exit_date > entry_date).
  - determinism (two runs -> identical equity curve + same closed count).
  - cash never goes negative.
  - both engines complete without raising.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.backtest.replay_engine import ReplayEngine  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if (detail and not cond) else ""))
    if not cond:
        FAILURES.append(name)


def synthetic_prices(n, seed, end="2026-01-01"):
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0006, 0.018, n)
    close = 100 * np.exp(np.cumsum(ret))
    ts = pd.date_range(end=pd.Timestamp(end), periods=n, freq="B", tz="UTC")
    op = close * (1 + rng.normal(0, 0.006, n))
    hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, 0.007, n)))
    lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, 0.007, n)))
    vol = rng.integers(500_000, 5_000_000, n)
    return pd.DataFrame({"timestamp": ts, "open": op, "high": hi, "low": lo, "close": close, "volume": vol})


def build_inputs(n=70):
    prices = {1: synthetic_prices(n, 1), 2: synthetic_prices(n, 2)}
    dates = sorted(set(pd.Timestamp(t) for df in prices.values() for t in df["timestamp"]))
    return prices, dates


def run_engine(engine):
    prices, dates = build_inputs()
    account = ReplayEngine(engine=engine, starting_cash=100_000.0).run(prices, dates)

    bad_identity = [
        r for r in account.equity_curve
        if abs(r["equity"] - (r["cash"] + r["open_positions_value"])) > 1e-6
    ]
    check(f"{engine}: equity == cash + open_value at every snapshot", not bad_identity, f"{len(bad_identity)} bad rows")

    realized = sum((t.realized_pnl or 0.0) for t in account.closed)
    unrealized = sum((t.unrealized_pnl or 0.0) for t in account.open.values())
    last = account.equity_curve[-1] if account.equity_curve else {}
    final_eq = last.get("equity", 0.0)
    check(f"{engine}: final equity == start + realized + unrealized",
          abs(final_eq - (100_000.0 + realized + unrealized)) < 1e-6,
          f"{final_eq} vs {100_000.0 + realized + unrealized}")

    if last:
        check(f"{engine}: realized_pnl_cumulative == Σ closed",
              abs(last["realized_pnl_cumulative"] - realized) < 1e-6,
              f"{last['realized_pnl_cumulative']} vs {realized}")

    bad_exit = [t for t in account.closed if pd.Timestamp(t.exit_date) <= pd.Timestamp(t.entry_date)]
    check(f"{engine}: no exit on birth bar", not bad_exit, f"{len(bad_exit)} bad")

    neg_cash = [r for r in account.equity_curve if r["cash"] < -1e-6]
    check(f"{engine}: cash never negative", not neg_cash)

    check(f"{engine}: equity curve non-empty", len(account.equity_curve) > 0)
    return account


def determinism():
    print("[determinism] two runs -> identical equity curve + closed count")
    p1, d1 = build_inputs()
    p2, d2 = build_inputs()
    r1 = ReplayEngine("engine_1").run(p1, d1)
    r2 = ReplayEngine("engine_1").run(p2, d2)
    eq_same = [a == b for a, b in zip(r1.equity_curve, r2.equity_curve)]
    check("engine_1 equity curve identical across runs",
          all(eq_same) and len(r1.equity_curve) == len(r2.equity_curve))
    check("engine_1 closed count stable", len(r1.closed) == len(r2.closed))


if __name__ == "__main__":
    print("=" * 60)
    print("test_backtest_engine")
    print("=" * 60)
    for eng in ("engine_1", "engine_2"):
        print(f"[{eng}]")
        run_engine(eng)
    determinism()
    print("=" * 60)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s): {FAILURES}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
    sys.exit(0)
