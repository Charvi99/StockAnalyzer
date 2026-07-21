"""
Engine #1 pure-signal characterization tests (Phase 0.4b).

Locks :func:`app.services.signal.systematic.signal_systematic` — the DB-free
6-factor weighted score extracted from ``generate_final_recommendation``. Runs
with NO database: inputs are synthetic dicts + an empty price frame (so the
technical component is 0 and the combine logic is exercised directly by the
other 5 components).

Runnable without pytest:
    python3 backend/tests/test_signal_systematic.py

Why: 0.4b made Engine #1 replayable. These freeze its decision logic so a future
weight/threshold edit can't silently flip a BUY/SELL verdict and contaminate the
paper-trading ledger. (Behavior parity vs the pre-refactor engine was already
proven head-to-head on live data: identical to floating-point exactness.)
"""
import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.signal.systematic import (
    signal_systematic,
    WEIGHTS,
    BUY_SELL_THRESHOLD,
    REGIME_SCORES,
)


def _bullish_chart():
    return [{"signal": "bullish", "confidence_score": 1.0, "confirmation_level": 0}]


def _bullish_candle():
    return [{"pattern_type": "bullish", "confidence_score": 1.0}]


def _bearish_chart():
    return [{"signal": "bearish", "confidence_score": 1.0, "confirmation_level": 0}]


def _bearish_candle():
    return [{"pattern_type": "bearish", "confidence_score": 1.0}]


def _div(score_adjustment):
    return {"has_signal": True, "score_adjustment": score_adjustment}


def test_all_empty_inputs_are_hold():
    """No data at all -> every component 0 -> weighted_score 0 -> HOLD @ 0.5."""
    sr = signal_systematic(pd.DataFrame(), [], [], None, "unknown", None)
    assert sr.signal == "HOLD"
    assert sr.confidence == 0.5
    assert abs(sr.weighted_score) < 1e-12
    assert all(v == 0.0 for v in sr.component_scores.values())


def test_strong_bullish_inputs_are_buy():
    """All non-technical components maximally bullish -> weighted 0.746 -> BUY."""
    sr = signal_systematic(
        pd.DataFrame(), _bullish_chart(), _bullish_candle(),
        1.0, "trending_up", _div(20),
    )
    expected = (1.0 * WEIGHTS["chart_patterns"] + 1.0 * WEIGHTS["candlestick_patterns"]
                + 0.0 * WEIGHTS["technical_indicators"] + 1.0 * WEIGHTS["sentiment"]
                + REGIME_SCORES["trending_up"] * WEIGHTS["market_regime"]
                + 1.0 * WEIGHTS["dividend_split_signals"])
    assert sr.signal == "BUY", f"expected BUY, weighted={sr.weighted_score}"
    assert abs(sr.weighted_score - expected) < 1e-9
    assert abs(sr.confidence - min(abs(expected), 1.0)) < 1e-9


def test_strong_bearish_inputs_are_sell():
    """All non-technical components maximally bearish -> weighted -0.746 -> SELL."""
    sr = signal_systematic(
        pd.DataFrame(), _bearish_chart(), _bearish_candle(),
        -1.0, "trending_down", _div(-20),
    )
    assert sr.signal == "SELL", f"expected SELL, weighted={sr.weighted_score}"
    assert sr.weighted_score < -BUY_SELL_THRESHOLD


def test_sub_threshold_is_hold():
    """Sentiment alone (max 0.13 weighted) is below the 0.3 BUY threshold -> HOLD."""
    sr = signal_systematic(pd.DataFrame(), [], [], 1.0, "unknown", None)
    assert sr.signal == "HOLD"
    assert sr.weighted_score < BUY_SELL_THRESHOLD


def test_regime_mapping():
    """Regime label -> score via REGIME_SCORES; unknown labels -> 0."""
    assert signal_systematic(pd.DataFrame(), [], [], None, "trending_up", None).component_scores["market_regime"] == 0.8
    assert signal_systematic(pd.DataFrame(), [], [], None, "trending_down", None).component_scores["market_regime"] == -0.8
    assert signal_systematic(pd.DataFrame(), [], [], None, "ranging", None).component_scores["market_regime"] == 0.0
    assert signal_systematic(pd.DataFrame(), [], [], None, "totally_unknown", None).component_scores["market_regime"] == 0.0


def test_dividend_score_normalized_and_clamped():
    """score_adjustment in [-20,20] maps to [-1,1]; outside is clamped."""
    assert signal_systematic(pd.DataFrame(), [], [], None, "unknown", _div(20)).component_scores["dividend_split_signals"] == 1.0
    assert signal_systematic(pd.DataFrame(), [], [], None, "unknown", _div(-20)).component_scores["dividend_split_signals"] == -1.0
    assert signal_systematic(pd.DataFrame(), [], [], None, "unknown", _div(10)).component_scores["dividend_split_signals"] == 0.5
    # 30 -> 1.5 -> clamped to 1.0
    assert signal_systematic(pd.DataFrame(), [], [], None, "unknown", _div(30)).component_scores["dividend_split_signals"] == 1.0


def test_chart_confirmation_level_boosts_raw_score():
    """A bullish pattern with confirmation_level=5 counts as confidence*(1+5*0.2)=2x in
    the numerator (before the [-1,1] clamp). Verifies the confirmation weighting carried over."""
    # 1 bullish, confidence 0.5, confirmation 5 -> bullish_score = 0.5*(1+1.0)=1.0, count 1 -> 1.0 (clamped)
    sr = signal_systematic(
        pd.DataFrame(),
        [{"signal": "bullish", "confidence_score": 0.5, "confirmation_level": 5}],
        [], None, "unknown", None,
    )
    assert sr.component_scores["chart_patterns"] == 1.0  # 1.0 raw, clamped to 1.0


def test_config_version_is_stable_and_present():
    """Same inputs -> same non-empty config_version (the ledger stamps this)."""
    a = signal_systematic(pd.DataFrame(), _bullish_chart(), [], None, "unknown", None)
    b = signal_systematic(pd.DataFrame(), _bullish_chart(), [], None, "unknown", None)
    assert a.config_version == b.config_version
    assert len(a.config_version) == 12


def test_component_scores_keys_are_the_six_factors():
    """SignalResult.component_scores must carry exactly the 6 Engine #1 factors."""
    sr = signal_systematic(pd.DataFrame(), [], [], None, "unknown", None)
    assert set(sr.component_scores.keys()) == set(WEIGHTS.keys())


def test_regime_is_stamped_on_result():
    """The regime label is carried on the SignalResult for the ledger."""
    sr = signal_systematic(pd.DataFrame(), [], [], None, "trending_up", None)
    assert sr.regime == "trending_up"


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
