"""
GA tests (Phase 3): deterministic, genome on the simplex, elitism keeps the best
non-decreasing across generations, train/val split returns both, and the GA does
no worse than the live-default baseline.

Pure Python (no DB, no pytest): ``python3 backend/tests/test_backtest_ga.py``.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.services.backtest.fitness import compute_metrics, fitness  # noqa: E402
from app.services.backtest.ga import GeneticOptimizer, default_weights  # noqa: E402
from app.services.backtest.replay_engine import ReplayEngine  # noqa: E402


def _stock(seed: int, n: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-02", periods=n, freq="B", tz="UTC")
    drift = rng.uniform(0.0004, 0.0011)            # gentle uptrend -> technical BUYs
    ret = rng.normal(drift, 0.016, n)
    close = 100 * np.exp(np.cumsum(ret))
    op = close * (1 + rng.normal(0, 0.005, n))
    hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    vol = rng.integers(5_000_00, 5_000_000, n)
    return pd.DataFrame({"timestamp": idx, "open": op, "high": hi, "low": lo, "close": close, "volume": vol})


def _universe(n_stocks=3, n=80):
    prices = {sid: _stock(100 + sid, n) for sid in range(n_stocks)}
    dates = sorted(set(prices[0]["timestamp"].tolist()))
    return prices, dates


# Shared universe (3 stocks x 80 days) — cache build is the costly step (~70ms per
# (stock,T) bundle with the pandas indicator fallback), so the scope is kept tiny.
_PRICES, _DATES = _universe()


def _baseline_fitness(engine, prices, train_dates, cache):
    """Fitness of the live default weights on the train window."""
    acct = ReplayEngine(engine=engine, weights=default_weights(engine), input_cache=cache).run(prices, train_dates)
    m = compute_metrics(acct.equity_curve, acct.closed, 100_000.0, None)
    return fitness(m)


FAILURES = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if (detail and not cond) else ""))
    if not cond:
        FAILURES.append(name)


def test_determinism_and_bounds():
    r1 = GeneticOptimizer("engine_2", _PRICES, _DATES, pop_size=5, generations=2, seed=42).optimize()
    r2 = GeneticOptimizer("engine_2", _PRICES, _DATES, pop_size=5, generations=2, seed=42).optimize()
    check("deterministic best_weights", r1["best_weights"] == r2["best_weights"])
    check("deterministic train_fitness", abs(r1["train_fitness"] - r2["train_fitness"]) < 1e-12)
    w = r1["best_weights"]
    check("weights sum to 1", abs(sum(w.values()) - 1.0) < 1e-9, f"sum={sum(w.values())}")
    check("weights within [0, w_max]", all(0.0 <= v <= 0.60 + 1e-9 for v in w.values()))
    check("weights have all keys", set(w.keys()) == set(default_weights("engine_2").keys()))


def test_elitism_monotone_and_val():
    opt = GeneticOptimizer("engine_2", _PRICES, _DATES, pop_size=6, generations=3, seed=1)
    r = opt.optimize()
    bests = [g["best"] for g in r["generations"]]
    mono = all(bests[i] <= bests[i + 1] + 1e-12 for i in range(len(bests) - 1))
    check("best fitness non-decreasing across generations (elitism)", mono, str([round(b, 3) for b in bests]))
    check("val window present", r["n_val_dates"] > 0, f"n_val={r['n_val_dates']}")
    check("val_fitness reported", r["val_fitness"] is not None)
    check("train_val_gap reported", r["train_val_gap"] is not None, f"gap={r['train_val_gap']}")
    # baseline reuses THIS optimizer's cache (no second cache build).
    base = _baseline_fitness("engine_2", _PRICES, opt.train_dates, opt.cache_train)
    check("GA train fitness >= live-default baseline", r["train_fitness"] >= base - 1e-9,
          f"ga={r['train_fitness']:.4f} baseline={base:.4f}")


if __name__ == "__main__":
    print("=" * 60)
    print("test_backtest_ga")
    print("=" * 60)
    for t in (test_determinism_and_bounds, test_elitism_monotone_and_val):
        print(f"[{t.__name__}]")
        t()
    print("=" * 60)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s): {FAILURES}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
    sys.exit(0)
