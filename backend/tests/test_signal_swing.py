"""
Engine #2 pure-signal characterization tests (Phase 0.4c).

Locks :func:`app.services.signal.swing.signal_swing` — the DB-free swing-aware
weighted vote extracted from ``_get_recommendation_for_stock``. Runs with NO
database: a short synthetic OHLCV frame (so weekly trend is neutral and the
Phase-2C indicator columns are NaN -> multiplier 1.0) isolates the vote / override
/ dividend logic.

Runnable without pytest:
    python3 backend/tests/test_signal_swing.py

Why: 0.4c made Engine #2 replayable. These freeze its decision logic so a future
weight/override edit can't silently flip a BUY/SELL verdict. (Behavior parity vs
the pre-refactor engine was already proven byte-identical on 5 live stocks.)
"""
import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.signal.swing import signal_swing, COMPONENT_WEIGHTS, ML_CONFIDENCE_GATE


def _short_df(n=60):
    """OHLCV daily frame + NaN indicator columns. n=60 -> ~12 weeks < 50 -> weekly
    neutral; NaN indicators -> Phase-2C multiplier stays 1.0 (isolates the vote)."""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = np.linspace(100.0, 110.0, n)
    df = pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0,
         "close": close, "volume": np.full(n, 1000.0)},
        index=idx,
    )
    for col in ["ma_short", "ma_long", "sma_200", "rsi", "macd", "macd_signal"]:
        df[col] = np.nan
    return df


def _tech(rec="BUY", conf=0.8):
    return {"recommendation": rec, "confidence": conf, "reason": "test",
            "signals": {}, "indicators": {}}


def _div(signal_type="dividend_entry"):
    return {"has_signal": True, "signal_type": signal_type, "reasoning": "test event"}


def test_technical_only_drives_buy():
    """A lone bullish technical vote -> BUY at that confidence (weekly neutral, no boosts)."""
    sr = signal_swing(_short_df(), _tech("BUY", 0.8), [], [], None, (None, None, None), None)
    assert sr.signal == "BUY"
    assert abs(sr.confidence - 0.8) < 1e-9


def test_hold_with_dividend_entry_flips_to_buy():
    """dividend_entry flips a HOLD to BUY at 0.6 confidence (carried over verbatim)."""
    sr = signal_swing(_short_df(), _tech("HOLD", 0.5), [], [], None, (None, None, None), _div("dividend_entry"))
    assert sr.signal == "BUY"
    assert abs(sr.confidence - 0.6) < 1e-9


def test_buy_with_dividend_exit_flips_to_hold():
    """dividend_exit flips a BUY to HOLD at 0.7x confidence."""
    sr = signal_swing(_short_df(), _tech("BUY", 0.8), [], [], None, (None, None, None), _div("dividend_exit"))
    assert sr.signal == "HOLD"
    assert abs(sr.confidence - 0.8 * 0.7) < 1e-9


def test_ml_below_confidence_gate_excluded_from_vote():
    """ML with confidence <= the gate does NOT vote: a lone HOLD technical stays HOLD
    even when ML says BUY at 0.5 (gate = 0.6)."""
    assert ML_CONFIDENCE_GATE == 0.6
    sr = signal_swing(_short_df(), _tech("HOLD", 0.5), [], [], None, ("BUY", 0.5, 123.0), None)
    assert sr.signal == "HOLD", "sub-gate ML must not join the vote"


def test_regime_is_weekly_trend_neutral_on_short_frame():
    """Short df -> weekly neutral; the regime stamp on the result is the weekly trend."""
    sr = signal_swing(_short_df(), _tech(), [], [], None, (None, None, None), None)
    assert sr.regime == "neutral"


def test_component_scores_signed_for_ledger():
    """component_scores maps each component vote to a signed [-1,1] value (BUY->+conf)."""
    sr = signal_swing(_short_df(), _tech("BUY", 0.8), [], [], None, (None, None, None), None)
    assert sr.component_scores["technical"] == 0.8
    # absent components score 0
    assert sr.component_scores["chart_pattern"] == 0.0
    assert sr.component_scores["ml"] == 0.0
    assert set(sr.component_scores.keys()) == set(COMPONENT_WEIGHTS.keys())


def test_extras_carry_response_fields():
    """extras must carry every field the adapter maps onto RecommendationResponse."""
    sr = signal_swing(_short_df(), _tech("BUY", 0.8), [], [], None, (None, None, None), None)
    ex = sr.extras
    for key in ["technical_recommendation", "technical_confidence", "technical_signals",
                "chart_pattern_signal", "chart_pattern_confidence", "chart_pattern_count",
                "candlestick_signal", "candlestick_confidence", "candlestick_pattern_count",
                "sentiment_index", "sentiment_positive", "sentiment_negative",
                "ml_recommendation", "ml_confidence", "predicted_price", "risk_level"]:
        assert key in ex, f"extras missing {key}"
    assert ex["technical_recommendation"] == "BUY"
    assert ex["risk_level"] in ("LOW", "MEDIUM", "HIGH")


def test_config_version_stable_and_present():
    a = signal_swing(_short_df(), _tech(), [], [], None, (None, None, None), None)
    b = signal_swing(_short_df(), _tech(), [], [], None, (None, None, None), None)
    assert a.config_version == b.config_version
    assert len(a.config_version) == 12


def test_sentiment_vote_from_scores():
    """Strongly positive news scores -> a sentiment BUY vote joins the components."""
    sr = signal_swing(_short_df(), _tech("HOLD", 0.5), [], [], [0.9, 0.8, 0.7], (None, None, None), None)
    # sentiment_index = avg(0.9,0.8,0.7)*100 ~= 80 -> BUY; extras carry it
    # (use approx: 0.9+0.8+0.7 is not exactly 2.4 in float)
    assert abs(sr.extras["sentiment_index"] - 80.0) < 1e-6
    assert sr.extras["sentiment_positive"] == 3
    assert sr.component_scores["sentiment"] > 0


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
            except Exception as e:
                failures += 1
                print(f"ERROR {name}: {e!r}")
    print(f"\n{'All passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
