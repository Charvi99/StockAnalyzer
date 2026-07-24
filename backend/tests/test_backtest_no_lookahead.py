"""
No-look-ahead guard for the backtest signal adapter (Phase 2).

Pure-Python (no DB, no pytest): ``python3 backend/tests/test_backtest_no_lookahead.py``.

Two layers of proof that the as-of-T signal cannot see the future:

1. SOURCE GUARD (AST): the adapter module imports neither SQLAlchemy / app.models
   / IndicatorCacheService, nor reads wall-clock time (``.now`` / ``.today`` /
   ``.utcnow`` / ``time.time``). If it can't read "now" or the DB/cache, it can
   only use its ``df_T`` argument -> the as-of-T signal is a pure function of
   data <= T. (AST, not substring, so the docstring's mention of these tokens is
   not a false positive.)

2. BEHAVIOUR: (a) determinism (same df_T -> identical SignalResult), and
   (b) causal indicators — the indicator values on bar T computed from the full
   series equal those computed from the series truncated at T (rolling indicators
   look backward only, so no future leak). Pattern detectors legitimately depend
   on their input window, so full-signal equality at i vs i+k is NOT asserted
   (boundary-candle dependence is correct causal behaviour, not a leak).
"""
import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

ADAPTER = BACKEND / "app" / "services" / "backtest" / "backtest_signal_adapter.py"

# Every module that assembles an as-of-T input must be AST-guarded: a now()/DB/cache
# read in ANY of them would break no-look-ahead, not just the signal adapter.
GUARDED_MODULES = [
    BACKEND / "app" / "services" / "backtest" / n
    for n in ("backtest_signal_adapter.py", "backtest_regime.py", "backtest_order_calc.py", "precompute.py")
]

FAILURES = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if (detail and not cond) else ""))
    if not cond:
        FAILURES.append(name)


# ── 1. AST source guard ──────────────────────────────────────────────────────
def _ast_violations(path: Path) -> list:
    tree = ast.parse(path.read_text())
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("app.models") or mod.startswith("sqlalchemy"):
                violations.append(f"forbidden import: from {mod}")
            for alias in node.names:
                if alias.name == "IndicatorCacheService":
                    violations.append("imports IndicatorCacheService")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("sqlalchemy") or alias.name == "IndicatorCacheService":
                    violations.append(f"forbidden import: import {alias.name}")
        if isinstance(node, ast.Attribute) and node.attr in ("now", "today", "utcnow"):
            violations.append(f"wall-clock read: .{node.attr}")
        if isinstance(node, ast.Attribute) and node.attr == "time" and isinstance(node.value, ast.Name) and node.value.id == "time":
            violations.append("wall-clock read: time.time")
    return violations


def source_guard():
    print("[1] AST source guard on as-of-T input modules (adapter + regime + order_calc + precompute)")
    for path in GUARDED_MODULES:
        v = _ast_violations(path)
        check(f"{path.name}: no forbidden imports / wall-clock reads", not v, "; ".join(v))


# ── synthetic OHLCV (seeded, deterministic) ──────────────────────────────────
def synthetic_prices(n=300, seed=42):
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0005, 0.015, n)
    close = 100 * np.exp(np.cumsum(ret))
    ts = pd.date_range(end=pd.Timestamp("2026-01-01"), periods=n, freq="B", tz="UTC")
    op = close * (1 + rng.normal(0, 0.005, n))
    hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    vol = rng.integers(500_000, 5_000_000, n)
    return pd.DataFrame({"timestamp": ts, "open": op, "high": hi, "low": lo, "close": close, "volume": vol})


# ── 2a. determinism ──────────────────────────────────────────────────────────
def determinism():
    from app.services.backtest.backtest_signal_adapter import signal_as_of
    print("[2a] determinism (same df_T -> identical SignalResult)")
    df = synthetic_prices()
    for eng in ("engine_1", "engine_2"):
        s1 = signal_as_of(eng, df.iloc[:250].copy())
        s2 = signal_as_of(eng, df.iloc[:250].copy())
        same = (s1.signal == s2.signal
                and abs((s1.confidence or 0) - (s2.confidence or 0)) < 1e-12
                and abs((s1.weighted_score or 0) - (s2.weighted_score or 0)) < 1e-12)
        check(f"{eng} deterministic", same, f"{s1.signal}/{s2.signal}")
        check(f"{eng} returns a valid signal", s1.signal in ("BUY", "SELL", "HOLD"))
        check(f"{eng} carries config_version", bool(s1.config_version))


# ── 2b. causal indicators (no future leak) ───────────────────────────────────
def causal_indicators():
    from app.services.technical_indicators import TechnicalIndicators
    print("[2b] causal indicators (full-series row T == truncated-at-T last row)")
    df = synthetic_prices(300)
    full = TechnicalIndicators.calculate_all_indicators(df.copy())
    T = 250
    trunc = TechnicalIndicators.calculate_all_indicators(df.iloc[: T + 1].copy())
    for col in ("rsi", "ma_long", "macd_signal"):
        a = full[col].iloc[T]
        b = trunc[col].iloc[-1]
        ok = pd.isna(a) and pd.isna(b) or (abs(float(a) - float(b)) < 1e-9)
        check(f"indicator '{col}' causal at T={T}", ok, f"full={a} trunc={b}")


# ── 3. input-cache (Phase 3): bundle path == fresh path; no leak through cache ─
def precompute_causality():
    from app.services.backtest.backtest_signal_adapter import (
        assemble_inputs, signal_as_of, signal_from_bundle,
    )
    from app.services.backtest.precompute import precompute_inputs
    print("[3] input-cache: bundle==fresh; cache over future-bearing frame doesn't leak")
    df = synthetic_prices(300)
    sid = 0
    T = 200
    df_T = df.iloc[: T + 1].copy()

    # (a) the cached bundle path must reproduce the fresh per-bar assembly exactly
    #     (the cache must not alter signal values).
    for eng in ("engine_1", "engine_2"):
        fresh = signal_as_of(eng, df_T)
        cached = signal_as_of(eng, df_T, bundle=assemble_inputs(eng, df_T))
        same = (fresh.signal == cached.signal
                and abs((fresh.weighted_score or 0) - (cached.weighted_score or 0)) < 1e-9)
        check(f"{eng} bundle-path == fresh-path", same,
              f"{fresh.signal}/{fresh.weighted_score:.4f} vs {cached.signal}/{cached.weighted_score:.4f}")

    # (b) NO future leak through the cache: build the cache over the FULL series
    #     (which contains bars > T), look up the bundle at several T, and confirm
    #     each equals the fresh as-of-T signal. Each cache bundle is assembled from
    #     its OWN truncated df_T (<= T), so future bars never enter it — this is the
    #     property that makes per-(stock,T) caching safe where full-series slicing
    #     (which carried the series-last-bar's broadcast *_signal) was not.
    dates = [df["timestamp"].iloc[i] for i in (100, 200, 250)]
    cache = precompute_inputs("engine_2", {sid: df}, dates)
    for ti in (100, 200, 250):
        T_i = pd.Timestamp(df["timestamp"].iloc[ti])
        cached_sig = signal_from_bundle("engine_2", cache.get((sid, T_i)))
        fresh_sig = signal_as_of("engine_2", df.iloc[: ti + 1].copy())
        same = (cached_sig.signal == fresh_sig.signal
                and abs((cached_sig.weighted_score or 0) - (fresh_sig.weighted_score or 0)) < 1e-9)
        check(f"engine_2 cache(T={ti}) over full series == fresh as-of-T (no leak)", same,
              f"{cached_sig.signal}/{cached_sig.weighted_score:.4f} vs {fresh_sig.signal}/{fresh_sig.weighted_score:.4f}")


if __name__ == "__main__":
    print("=" * 60)
    print("test_backtest_no_lookahead")
    print("=" * 60)
    source_guard()
    determinism()
    causal_indicators()
    precompute_causality()
    print("=" * 60)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s): {FAILURES}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
    sys.exit(0)
