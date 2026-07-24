"""
Weights-seam tests (Phase 3): the additive ``weights=`` param on
``signal_systematic`` / ``signal_swing`` must be behaviour-preserving for the
default path (weights=None == explicit module defaults, byte-for-byte), must
re-version the signal when a candidate is supplied, and must actually re-weight
the score. Also checks the helper + adapter threading.

Pure Python (no DB, no pytest). Run with:
    python3 backend/tests/test_backtest_weights_seam.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.services.signal.systematic import (  # noqa: E402
    WEIGHTS as SYS_WEIGHTS,
    _SYSTEMATIC_CONFIG_VERSION,
    config_version_for as sys_cv_for,
    signal_systematic,
)
from app.services.signal.swing import (  # noqa: E402
    COMPONENT_WEIGHTS as SWING_WEIGHTS,
    _SWING_CONFIG_VERSION,
    config_version_for as swing_cv_for,
    signal_swing,
)


def _synthetic_prices(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Deterministic OHLCV (uptrend + noise) with a ``timestamp`` column."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-02", periods=n, freq="B")
    drift = np.linspace(0, 60, n)
    noise = rng.normal(0, 2.0, n)
    close = 100 + drift + noise
    op = close + rng.normal(0, 0.5, n)
    hi = np.maximum(op, close) + rng.uniform(0, 1.5, n)
    lo = np.minimum(op, close) - rng.uniform(0, 1.5, n)
    vol = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame({
        "timestamp": idx, "open": op, "high": hi, "low": lo, "close": close, "volume": vol,
    })


def _e1_inputs(df: pd.DataFrame) -> dict:
    return dict(
        df_prices=df.tail(60).copy(),
        chart_patterns=[],
        candlestick_patterns=[],
        sentiment_score=0.8,
        regime="trend",
        dividend_split_signal=None,
    )


def _e2_inputs(df: pd.DataFrame) -> dict:
    from app.services.technical_indicators import TechnicalIndicators
    d = df.tail(250).set_index("timestamp").copy()
    d = TechnicalIndicators.calculate_all_indicators(d)
    tech = TechnicalIndicators.generate_recommendation(d)
    return dict(
        df=d, tech_recommendation=tech, chart_patterns_raw=[], candlestick_patterns_raw=[],
        sentiment_scores=[0.5, 0.6, 0.7], ml=(None, None, None), dividend_split_signal=None,
        strategy_consensus=None,
    )


def _eq(a, b, msg):
    assert a == b, f"{msg}: {a!r} != {b!r}"


def test_engine1_default_parity():
    df = _synthetic_prices()
    base = signal_systematic(**_e1_inputs(df))                       # weights=None
    expl = signal_systematic(**_e1_inputs(df), weights=SYS_WEIGHTS)  # explicit defaults
    _eq(base.signal, expl.signal, "e1 signal")
    assert abs(base.weighted_score - expl.weighted_score) < 1e-12, "e1 weighted_score differs"
    assert abs(base.confidence - expl.confidence) < 1e-12, "e1 confidence differs"
    _eq(base.config_version, expl.config_version, "e1 config_version")
    _eq(base.config_version, _SYSTEMATIC_CONFIG_VERSION, "e1 cv must equal module constant")


def test_engine2_default_parity():
    df = _synthetic_prices()
    base = signal_swing(**_e2_inputs(df))
    expl = signal_swing(**_e2_inputs(df), weights=SWING_WEIGHTS)
    _eq(base.signal, expl.signal, "e2 signal")
    assert abs(base.weighted_score - expl.weighted_score) < 1e-12, "e2 weighted_score differs"
    _eq(base.config_version, expl.config_version, "e2 config_version")
    _eq(base.config_version, _SWING_CONFIG_VERSION, "e2 cv must equal module constant")


def test_config_version_for_helper():
    _eq(sys_cv_for(None), _SYSTEMATIC_CONFIG_VERSION, "sys cv_for(None)")
    _eq(sys_cv_for(SYS_WEIGHTS), _SYSTEMATIC_CONFIG_VERSION, "sys cv_for(defaults)")
    skewed = {**SYS_WEIGHTS, "technical_indicators": 0.50, "chart_patterns": 0.05}
    assert sys_cv_for(skewed) != _SYSTEMATIC_CONFIG_VERSION, "sys cv_for(skewed) must differ"
    _eq(swing_cv_for(None), _SWING_CONFIG_VERSION, "swing cv_for(None)")
    _eq(swing_cv_for(SWING_WEIGHTS), _SWING_CONFIG_VERSION, "swing cv_for(defaults)")


def test_different_weights_change_result():
    df = _synthetic_prices()
    base = signal_systematic(**_e1_inputs(df))  # defaults
    # Push almost all weight onto technical_indicators (keep keys, renormalize implicitly).
    skewed = {k: 0.01 for k in SYS_WEIGHTS}
    skewed["technical_indicators"] = 1.0 - 0.01 * (len(SYS_WEIGHTS) - 1)
    alt = signal_systematic(**_e1_inputs(df), weights=skewed)
    assert alt.config_version != base.config_version, "skewed cv must differ from default"
    assert abs(alt.weighted_score - base.weighted_score) > 1e-6, "skewed weighted_score must differ"
    # The reported weighted_score must equal a hand-recomputation with the skewed weights
    # (i.e. the function used the EFFECTIVE weights, not the module defaults).
    hand = sum(alt.component_scores[k] * skewed[k] for k in skewed)
    assert abs(alt.weighted_score - hand) < 1e-9, f"weighted_score {alt.weighted_score} != hand {hand}"


def test_signal_as_of_threads_weights():
    from app.services.backtest.backtest_signal_adapter import signal_as_of
    df = _synthetic_prices()
    a = signal_as_of("engine_1", df)                 # weights omitted
    b = signal_as_of("engine_1", df, weights=None)   # explicit None
    _eq(a.config_version, b.config_version, "as_of None parity")
    _eq(a.weighted_score, b.weighted_score, "as_of None score parity")
    skewed = {**SYS_WEIGHTS, "sentiment": 0.50, "technical_indicators": 0.05}
    c = signal_as_of("engine_1", df, weights=skewed)
    assert c.config_version != a.config_version, "as_of must thread weights into config_version"
    _eq(c.config_version, sys_cv_for(skewed), "as_of cv must equal helper")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} weights-seam tests passed")
