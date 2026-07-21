"""
Signal-core characterization tests (Phase 0.4a).

Locks the behavior of the 4 pure helpers moved out of ``realtime_recommendation``
into ``app.services.signal.core`` (plus the new ``SignalResult`` /
``config_version`` contracts). These run with NO database, NO TA-Lib, NO app.* DB
models — the signal layer is pure pandas, so the move is unit-testable directly.

Runnable without pytest:
    python3 backend/tests/test_signal_core.py

Why these tests exist: 0.4a relocated the helpers verbatim. The next steps
(0.4b Engine #1 extraction, 0.4c Engine #2 extraction) build pure signal
functions ON TOP of these helpers, so their current behavior must be frozen first
— otherwise a future "cleanup" can silently flip a weekly-trend verdict or a
confidence multiplier and contaminate the ledger/backtest.
"""
import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _daily(n: int, close: np.ndarray, start: str = "2022-01-03") -> pd.DataFrame:
    """Build an OHLCV daily frame at `close` with symmetric high/low and flat vol."""
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=idx,
    )


def _ramp_up_daily() -> pd.DataFrame:
    """Flat 250 bars then ramp up -> last weekly close clearly > 50-week SMA."""
    close = np.concatenate([np.full(250, 100.0), np.linspace(100, 140, 110)])
    return _daily(len(close), close)


def _ramp_down_daily() -> pd.DataFrame:
    """Flat 250 bars then ramp down -> last weekly close clearly < 50-week SMA."""
    close = np.concatenate([np.full(250, 100.0), np.linspace(100, 60, 110)])
    return _daily(len(close), close)


# --------------------------------------------------------------------------- #
# config_version + SignalResult contracts
# --------------------------------------------------------------------------- #
def test_config_version_deterministic_and_sensitive():
    from app.services.signal import config_version

    a = config_version({"chart": 0.28, "tech": 0.23}, {"buy": 0.3}, "systematic-v1")
    b = config_version({"chart": 0.28, "tech": 0.23}, {"buy": 0.3}, "systematic-v1")
    c = config_version({"chart": 0.29, "tech": 0.23}, {"buy": 0.3}, "systematic-v1")  # weight changed
    d = config_version({"chart": 0.28, "tech": 0.23}, {"buy": 0.3}, "systematic-v2")  # schema changed
    assert a == b, "identical config must hash identically"
    assert a != c, "changing a weight must change the version"
    assert a != d, "changing the schema tag must change the version"


def test_config_version_is_order_independent_and_short():
    from app.services.signal import config_version

    a = config_version({"x": 1, "y": 2})
    b = config_version({"y": 2, "x": 1})  # dict key order swapped
    assert a == b, "config_version must be order-independent (sort_keys=True)"
    assert len(a) == 12, f"expected 12-char hash, got {len(a)}"


def test_signal_result_defaults():
    from app.services.signal import SignalResult

    sr = SignalResult(
        signal="BUY",
        confidence=0.7,
        weighted_score=0.4,
        component_scores={"technical": 0.4},
        config_version="abc123def456",
    )
    assert sr.reasoning == [], "reasoning must default to a fresh list"
    assert sr.regime is None
    assert sr.extras is None
    # default list must not be shared across instances (field(default_factory=list))
    sr2 = SignalResult("HOLD", 0.5, 0.0, {}, "zzz")
    sr.reasoning.append("x")
    assert sr2.reasoning == [], "each instance must own its default reasoning list"


# --------------------------------------------------------------------------- #
# check_weekly_trend
# --------------------------------------------------------------------------- #
def test_weekly_trend_bullish_on_ramp_up():
    from app.services.signal.core import check_weekly_trend

    wt = check_weekly_trend(_ramp_up_daily())
    assert wt["trend"] == "bullish", f"ramp-up should be bullish, got {wt['trend']}"
    assert wt["weekly_close"] > wt["weekly_sma_50"]
    assert wt["weekly_sma_50"] is not None and wt["weekly_close"] is not None


def test_weekly_trend_bearish_on_ramp_down():
    from app.services.signal.core import check_weekly_trend

    wt = check_weekly_trend(_ramp_down_daily())
    assert wt["trend"] == "bearish", f"ramp-down should be bearish, got {wt['trend']}"
    assert wt["weekly_close"] < wt["weekly_sma_50"]


def test_weekly_trend_neutral_on_insufficient_data():
    from app.services.signal.core import check_weekly_trend

    wt = check_weekly_trend(_daily(40, np.linspace(100, 110, 40)))  # < 60 daily bars
    assert wt["trend"] == "neutral"
    assert wt["weekly_sma_50"] is None and wt["weekly_close"] is None


# --------------------------------------------------------------------------- #
# detect_swing_points
# --------------------------------------------------------------------------- #
def test_detect_swing_points_finds_planted_peak():
    from app.services.signal.core import detect_swing_points

    high = np.full(25, 50.0)
    high[10] = 100.0  # strict local max, 5 bars clear each side
    low = np.full(25, 48.0)
    df = pd.DataFrame({"high": high, "low": low},
                      index=pd.date_range("2024-01-01", periods=25, freq="D"))
    sp = detect_swing_points(df, lookback=5)
    assert df.index[10] in sp["swing_highs"], "planted peak must be a swing high"
    assert len(sp["swing_lows"]) == 0, "no valleys planted -> no swing lows"


def test_detect_swing_points_empty_on_short_frame():
    from app.services.signal.core import detect_swing_points

    df = pd.DataFrame({"high": [1, 2, 3], "low": [0, 1, 2]},
                      index=pd.date_range("2024-01-01", periods=3, freq="D"))
    sp = detect_swing_points(df, lookback=5)  # len < 2*5+1
    assert sp["swing_highs"] == set() and sp["swing_lows"] == set()


# --------------------------------------------------------------------------- #
# categorize_candlestick_pattern
# --------------------------------------------------------------------------- #
def test_categorize_reversal_and_continuation():
    from app.services.signal.core import categorize_candlestick_pattern

    assert categorize_candlestick_pattern("Hammer") == "reversal"
    assert categorize_candlestick_pattern("Morning Star") == "reversal"
    assert categorize_candlestick_pattern("Bearish Engulfing") == "reversal"
    assert categorize_candlestick_pattern("Rising Three Methods") == "continuation"
    assert categorize_candlestick_pattern("Bullish Marubozu") == "continuation"


def test_categorize_unknown_defaults_reversal():
    from app.services.signal.core import categorize_candlestick_pattern

    # Conservative default: unknown patterns are treated as reversal (valid only at swing points).
    assert categorize_candlestick_pattern("Totally Made Up Pattern") == "reversal"


# --------------------------------------------------------------------------- #
# evaluate_swing_trading_context
# --------------------------------------------------------------------------- #
def test_evaluate_context_contract_and_clamp():
    from app.services.signal.core import evaluate_swing_trading_context

    row = pd.DataFrame(
        {"close": [120.0], "ma_short": [110.0], "ma_long": [105.0], "sma_200": [100.0],
         "rsi": [55.0], "macd": [1.0], "macd_signal": [0.5]},
        index=[pd.Timestamp("2024-01-01")],
    )
    ctx = evaluate_swing_trading_context(row, {"trend": "bullish"}, {}, "BUY")
    # Required keys (contract documented in the function docstring).
    assert set(ctx.keys()) == {
        "confidence_adjustment", "reasoning", "ma_alignment", "rsi_context", "macd_alignment"
    }
    # Multiplier is always clamped to [0.65, 1.25].
    assert 0.65 <= ctx["confidence_adjustment"] <= 1.25


def test_evaluate_context_bullish_strong_alignment_boosts():
    """price > ma50 > sma200 + MACD aligned in a bullish weekly trend must boost > 1.0."""
    from app.services.signal.core import evaluate_swing_trading_context

    row = pd.DataFrame(
        {"close": [120.0], "ma_short": [110.0], "ma_long": [105.0], "sma_200": [100.0],
         "rsi": [55.0], "macd": [1.0], "macd_signal": [0.5]},
        index=[pd.Timestamp("2024-01-01")],
    )
    ctx = evaluate_swing_trading_context(row, {"trend": "bullish"}, {}, "BUY")
    assert ctx["confidence_adjustment"] > 1.0, (
        f"strong bullish alignment should boost confidence, got {ctx['confidence_adjustment']}"
    )
    assert ctx["ma_alignment"] == "strong"
    assert ctx["macd_alignment"] == "aligned"


def test_evaluate_context_counter_trend_penalizes():
    """A BUY into a bearish weekly trend with price > ma50 is counter-trend -> mult < 1.0."""
    from app.services.signal.core import evaluate_swing_trading_context

    row = pd.DataFrame(
        {"close": [120.0], "ma_short": [110.0], "ma_long": [105.0], "sma_200": [100.0],
         "rsi": [55.0], "macd": [1.0], "macd_signal": [0.5]},
        index=[pd.Timestamp("2024-01-01")],
    )
    ctx = evaluate_swing_trading_context(row, {"trend": "bearish"}, {}, "BUY")
    assert ctx["ma_alignment"] == "counter"
    assert ctx["confidence_adjustment"] < 1.0


# --------------------------------------------------------------------------- #
# Package import smoke
# --------------------------------------------------------------------------- #
def test_signal_package_imports():
    """The pure signal package must import with no DB / no app.models dependency."""
    from app.services.signal import (  # noqa: F401
        SignalResult,
        config_version,
        check_weekly_trend,
        detect_swing_points,
        categorize_candlestick_pattern,
        evaluate_swing_trading_context,
    )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL  {name}: {e}")
            except Exception as e:  # env-dependent (e.g. pandas missing)
                failures += 1
                print(f"ERROR {name}: {e!r}")
    print(f"\n{'All passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
