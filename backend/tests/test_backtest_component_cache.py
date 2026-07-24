"""
Component-cache equivalence tests (Phase 3 #3).

The GA speedup caches each engine's WEIGHT-INDEPENDENT component votes once per
(stock, T) on the bundle (``bundle["_components"]``); ``signal_as_of`` then takes
a fast branch (``assemble``) instead of re-deriving them. This must be
BEHAVIOUR-IDENTICAL to the plain per-call path (``signal_from_bundle``) — i.e.
``signal_X == compose(compute_components, assemble)`` — or the GA would optimize
a different objective than the engine actually trades. These tests pin that:

  1. fast-path (enriched bundle) == slow-path (plain bundle), bit-exact on every
     SignalResult field incl. reasoning + extras, across many weight sets;
  2. the enriched bundle is safe to REUSE across candidates (the reasoning list is
     not mutated) — the cache is shared across the GA's weight population;
  3. ``precompute_inputs`` actually attaches ``_components`` to every bundle;
  4. ``assemble(None components)`` is a neutral HOLD.

Pure Python (no DB, no pytest). Run with:
    python3 backend/tests/test_backtest_component_cache.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.services.backtest.backtest_signal_adapter import (  # noqa: E402
    assemble_inputs, assemble, compute_components, signal_as_of,
)
from app.services.backtest.precompute import precompute_inputs  # noqa: E402
from app.services.signal.systematic import WEIGHTS as SYS_WEIGHTS  # noqa: E402
from app.services.signal.swing import COMPONENT_WEIGHTS as SWING_WEIGHTS  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    if not cond:
        FAILURES.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}: {detail}")
    else:
        print(f"  [PASS] {name}")


def _synthetic_prices(n: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-02", periods=n, freq="B")
    drift = np.linspace(0, 60 if seed % 2 else -40, n)  # up- or down-trend by seed
    close = 100 + drift + rng.normal(0, 2.0, n)
    op = close + rng.normal(0, 0.5, n)
    hi = np.maximum(op, close) + rng.uniform(0, 1.5, n)
    lo = np.minimum(op, close) - rng.uniform(0, 1.5, n)
    vol = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame({"timestamp": idx, "open": op, "high": hi, "low": lo,
                         "close": close, "volume": vol})


def _floats_equal(a, b, tol=1e-12):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol
    return a == b


def _signals_equal(a, b, tag):
    """Bit-exact comparison of two SignalResults on every field."""
    ok = True
    if a.signal != b.signal:
        check(f"{tag} signal", False, f"{a.signal} != {b.signal}"); ok = False
    if not _floats_equal(a.confidence, b.confidence):
        check(f"{tag} confidence", False, f"{a.confidence} != {b.confidence}"); ok = False
    if not _floats_equal(a.weighted_score, b.weighted_score):
        check(f"{tag} weighted_score", False, f"{a.weighted_score} != {b.weighted_score}"); ok = False
    if a.config_version != b.config_version:
        check(f"{tag} config_version", False, f"{a.config_version} != {b.config_version}"); ok = False
    if a.regime != b.regime:
        check(f"{tag} regime", False, f"{a.regime} != {b.regime}"); ok = False
    if a.reasoning != b.reasoning:
        check(f"{tag} reasoning", False, f"\n   old={a.reasoning}\n   new={b.reasoning}"); ok = False
    if set(a.component_scores) != set(b.component_scores):
        check(f"{tag} component_scores keys", False); ok = False
    else:
        for k in a.component_scores:
            if not _floats_equal(a.component_scores[k], b.component_scores[k]):
                check(f"{tag} component_scores[{k}]", False,
                      f"{a.component_scores[k]} != {b.component_scores[k]}"); ok = False
    if a.extras is None or b.extras is None:
        if a.extras != b.extras:
            check(f"{tag} extras", False, f"{a.extras!r} != {b.extras!r}"); ok = False
    elif set(a.extras) != set(b.extras):
        check(f"{tag} extras keys", False, f"{set(a.extras)} != {set(b.extras)}"); ok = False
    else:
        for k in a.extras:
            if not _floats_equal(a.extras[k], b.extras[k]):
                check(f"{tag} extras[{k}]", False, f"{a.extras[k]!r} != {b.extras[k]!r}"); ok = False
    return ok


def _weight_sets(defaults):
    sets = [None, dict(defaults)]
    rng = np.random.default_rng(7)
    keys = list(defaults)
    for _ in range(6):
        raw = rng.uniform(0, 0.6, len(keys))
        s = raw.sum() or 1.0
        sets.append({k: float(raw[i] / s) for i, k in enumerate(keys)})
    return sets


def _test_engine(engine, defaults, seeds):
    print(f"[{engine}] fast-path == slow-path (bit-exact), reused across weights")
    for seed in seeds:
        df = _synthetic_prices(seed=seed)
        plain = assemble_inputs(engine, df)
        if plain is None:
            continue
        # ONE enriched bundle, REUSED across all weight sets (exercises the
        # reasoning-not-mutated invariant — the cache is shared across candidates).
        enriched = dict(plain)
        enriched["_components"] = compute_components(engine, plain)
        for W in _weight_sets(defaults):
            slow = signal_as_of(engine, df, weights=W, bundle=plain)        # per-call path
            fast = signal_as_of(engine, df, weights=W, bundle=enriched)     # cached path
            _signals_equal(slow, fast, f"{engine} seed={seed} W_none={W is None}")


def test_engine1_fast_equals_slow():
    _test_engine("engine_1", SYS_WEIGHTS, seeds=(42, 7, 99))


def test_engine2_fast_equals_slow():
    _test_engine("engine_2", SWING_WEIGHTS, seeds=(42, 7, 99))


def test_precompute_enriches_bundles():
    print("[precompute] every assembled bundle carries _components")
    for engine in ("engine_1", "engine_2"):
        prices = {1: _synthetic_prices(seed=42)}
        # A handful of dates is enough to prove enrichment (each date runs the
        # ~1s chart detector — don't iterate the whole 300-bar series here).
        dates = sorted(prices[1]["timestamp"].tolist())[-8:]
        cache = precompute_inputs(engine, prices, dates)
        tagged = 0
        for (sid, T), bundle in cache.items():
            if bundle is None:
                continue
            assert "_components" in bundle, f"{engine} bundle {sid}@{T} missing _components"
            if bundle["_components"] is not None:
                tagged += 1
        check(f"{engine} precompute tagged components", tagged > 0, f"tagged={tagged}")


def test_assemble_none_is_hold():
    print("[assemble] None components -> neutral HOLD")
    for engine in ("engine_1", "engine_2"):
        r = assemble(engine, None, None)
        check(f"{engine} none->HOLD", r.signal == "HOLD", r.signal)
        check(f"{engine} none->confidence 0.5", abs(r.confidence - 0.5) < 1e-12, r.confidence)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        print(f"\n=== {t.__name__} ===")
        t()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s):")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
