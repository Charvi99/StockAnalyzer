#!/usr/bin/env python3
"""
Regime de-risk overlay tests (Phase 2.5).

Pure-Python (repo convention: no DB, no pytest):
``python3 backend/tests/test_regime_overlay.py``.

Proves the overlay's four invariants:

1. MATH — :func:`buy_score_factor` / :func:`weekly_size_factor` schedules, incl.
   ``strength == 0`` => ``1.0`` everywhere (OFF = no-op).
2. BYTE-IDENTICAL AT OFF — for BOTH engines,
   ``config_version_for(None, 0.0)`` reproduces the engine's pinned
   ``_SYSTEMATIC_CONFIG_VERSION`` / ``_SWING_CONFIG_VERSION`` exactly, and
   ``_decide_systematic(comp, None, 0.0)`` is identical to the no-overlay call
   (signal / confidence / weighted_score / config_version). Nonzero strength
   changes the hash (overlay-on is attributable).
3. SUPPRESSION (engine_1) — a bearish directional regime scales the BUY-leaning
   score (``bearish`` x0.6, ``bearish_weak`` x0.8 at strength 0.4), can flip
   BUY->HOLD across the threshold, and NEVER touches a SELL (negative) score.
4. PARITY — :func:`detect_direction_from_df` returns the SAME direction label
   the live ``MarketRegimeService.detect_tcr_regime`` produces on the identical
   frame (no live/backtest divergence) and degrades to ``'neutral'`` on
   insufficient data.

The engine_2 SOFT weekly-bear branch (BUY retained, ``extras['bear_size_factor']``
emitted) and the replay size-scaling are integration-tested by the A/B backtest
(STATUS.md) — ``test_backtest_no_lookahead.py`` already covers the
byte-identical-at-OFF invariant for ``signal_as_of`` on both engines
(determinism + bundle==fresh). The module-level AST purity of
``backtest_regime.py`` (incl. ``detect_direction_from_df``) is also already
enforced there.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.signal.regime_overlay import buy_score_factor, weekly_size_factor  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if (detail and not cond) else ""))
    if not cond:
        FAILURES.append(name)


def approx(a, b, tol=1e-9):
    return abs(a - b) < tol


# ── 1. math ──────────────────────────────────────────────────────────────────
def math_factors():
    print("[1] overlay factor math")
    # OFF everywhere
    for d in ("bearish", "bearish_weak", "bullish", "neutral", None):
        check(f"buy_score_factor({d!r}, 0.0)==1.0", buy_score_factor(d, 0.0) == 1.0)
    check("buy_score_factor('bearish', neg)==1.0", buy_score_factor("bearish", -0.5) == 1.0)
    # schedules @ strength 0.4
    check("bearish  x0.6", approx(buy_score_factor("bearish", 0.4), 0.6))
    check("bearish_weak x0.8", approx(buy_score_factor("bearish_weak", 0.4), 0.8))
    for d in ("bullish", "neutral", "bullish_weak", None):
        check(f"non-bear {d!r} x1.0", approx(buy_score_factor(d, 0.4), 1.0))
    # extremes
    check("bearish strength 1.0 -> 0.0", approx(buy_score_factor("bearish", 1.0), 0.0))
    check("bearish_weak strength 1.0 -> 0.5", approx(buy_score_factor("bearish_weak", 1.0), 0.5))
    # weekly size factor (engine_2)
    check("weekly_size_factor(0.4, bear)==0.6", approx(weekly_size_factor(0.4, True), 0.6))
    check("weekly_size_factor(0.4, not-bear)==1.0", approx(weekly_size_factor(0.4, False), 1.0))
    check("weekly_size_factor(0.0, bear)==1.0", approx(weekly_size_factor(0.0, True), 1.0))
    check("weekly_size_factor(1.0, bear)==0.0", approx(weekly_size_factor(1.0, True), 0.0))


# ── 2 + 3. systematic (engine_1) byte-identical + suppression ────────────────
def systematic_overlay():
    from app.services.signal.systematic import (
        WEIGHTS, _SYSTEMATIC_CONFIG_VERSION, _decide_systematic, config_version_for,
    )
    print("[2] engine_1 config_version byte-identical at OFF")
    check("cv(None,0.0)==_SYSTEMATIC_CONFIG_VERSION",
          config_version_for(None, 0.0) == _SYSTEMATIC_CONFIG_VERSION)
    check("cv(None,0.4)!=_SYSTEMATIC_CONFIG_VERSION (overlay attributable)",
          config_version_for(None, 0.4) != _SYSTEMATIC_CONFIG_VERSION)

    def comp(direction, **score_overrides):
        s = {k: 0.0 for k in WEIGHTS}
        s.update(score_overrides)
        return {"scores": s, "regime": "trend", "sentiment_score": None, "direction": direction}

    # weighted_score = 0.28 + 0.14 = 0.42 (a BUY; > 0.3 threshold)
    buy = comp("bearish", chart_patterns=1.0, candlestick_patterns=1.0)
    base = _decide_systematic(buy, None)            # today's call shape
    off = _decide_systematic(buy, None, 0.0)        # explicit OFF

    print("[3] engine_1 suppression")
    check("explicit OFF == today's call (signal)", base.signal == off.signal)
    check("explicit OFF == today's call (weighted_score)", approx(base.weighted_score, off.weighted_score))
    check("explicit OFF == today's call (config_version)", base.config_version == off.config_version)
    check("base is BUY @ 0.42", base.signal == "BUY" and approx(base.weighted_score, 0.42))

    on = _decide_systematic(buy, None, 0.4)         # bearish -> x0.6 -> 0.252 -> HOLD
    check("bearish x0.6 -> 0.252", approx(on.weighted_score, 0.42 * 0.6))
    check("bearish x0.6 flips BUY->HOLD", on.signal == "HOLD")
    check("overlay changes config_version", on.config_version != off.config_version)

    weak = _decide_systematic(comp("bearish_weak", chart_patterns=1.0, candlestick_patterns=1.0), None, 0.4)
    check("bearish_weak x0.8 -> 0.336 (stays BUY)", weak.signal == "BUY" and approx(weak.weighted_score, 0.42 * 0.8))

    neutral = _decide_systematic(comp("neutral", chart_patterns=1.0, candlestick_patterns=1.0), None, 0.4)
    check("neutral x1.0 (unchanged)", neutral.signal == "BUY" and approx(neutral.weighted_score, 0.42))

    # SELL (negative) is NEVER scaled by the overlay.
    sell = _decide_systematic(comp("bearish", chart_patterns=-1.0, candlestick_patterns=-1.0), None, 0.0)
    sell_on = _decide_systematic(comp("bearish", chart_patterns=-1.0, candlestick_patterns=-1.0), None, 0.4)
    check("SELL signal stays SELL", sell.signal == "SELL" and sell_on.signal == "SELL")
    check("SELL score untouched by overlay", approx(sell.weighted_score, sell_on.weighted_score))


# ── 2b. swing (engine_2) config_version byte-identical at OFF ────────────────
def swing_config_version():
    from app.services.signal.swing import _SWING_CONFIG_VERSION, config_version_for
    print("[2b] engine_2 config_version byte-identical at OFF")
    check("swing cv(None,0.0)==_SWING_CONFIG_VERSION",
          config_version_for(None, 0.0) == _SWING_CONFIG_VERSION)
    check("swing cv(None,0.4)!=_SWING_CONFIG_VERSION (overlay attributable)",
          config_version_for(None, 0.4) != _SWING_CONFIG_VERSION)


# ── 4. detect_direction_from_df parity with the live service ─────────────────
def synthetic_prices(n=160, seed=7):
    rng = np.random.default_rng(seed)
    ret = rng.normal(-0.0005, 0.012, n)  # mild downtrend bias -> often bearish
    close = 100 * np.exp(np.cumsum(ret))
    ts = pd.date_range(end=pd.Timestamp("2026-01-01"), periods=n, freq="B", tz="UTC")
    op = close * (1 + rng.normal(0, 0.004, n))
    hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, 0.005, n)))
    lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, 0.005, n)))
    vol = rng.integers(500_000, 5_000_000, n)
    return pd.DataFrame({"timestamp": ts, "open": op, "high": hi, "low": lo, "close": close, "volume": vol})


def direction_parity():
    from app.services.backtest.backtest_regime import detect_direction_from_df
    from app.services.market_regime import MarketRegimeService
    print("[4] detect_direction_from_df parity with live MarketRegimeService")
    valid = {"bullish", "bearish", "bullish_weak", "bearish_weak", "neutral"}

    # insufficient data -> neutral
    check("<50 bars -> 'neutral'", detect_direction_from_df(synthetic_prices(40)) == "neutral")
    check("None -> 'neutral'", detect_direction_from_df(None) == "neutral")

    # parity: same frame, same direction as the live service's detect_tcr_regime.
    for seed in (1, 2, 3, 7, 42):
        px = synthetic_prices(160, seed=seed)
        svc = MarketRegimeService(None)
        df = px.tail(100).copy()
        df = svc.calculate_moving_averages(df)
        df = svc.calculate_adx(df, period=14)
        tcr = svc.detect_tcr_regime(
            float(df["adx"].iloc[-1]), float(df["plus_di"].iloc[-1]),
            float(df["minus_di"].iloc[-1]),
            svc.calculate_ma_slope(df["ma20"], period=5),
            svc.calculate_ma_slope(df["ma50"], period=5),
        )
        live_dir = tcr["direction"]
        bt_dir = detect_direction_from_df(px, lookback=100)
        check(f"seed {seed}: bt direction==live direction", bt_dir == live_dir,
              f"bt={bt_dir!r} live={live_dir!r}")
        check(f"seed {seed}: direction is a valid label", bt_dir in valid)


if __name__ == "__main__":
    print("=" * 60)
    print("test_regime_overlay")
    print("=" * 60)
    math_factors()
    systematic_overlay()
    swing_config_version()
    direction_parity()
    print("=" * 60)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s): {FAILURES}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
    sys.exit(0)
