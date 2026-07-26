"""
Pure market-regime label from a price DataFrame (Phase 2).

The live ``MarketRegimeService.detect_market_regime(stock_id)`` is DB-bound (it
queries the last 100 bars). The backtester already holds the price series as-of
date T, so this helper runs the SAME compute (moving averages, ADX, MA slopes,
TCR regime) on a DataFrame and returns the regime label — with no DB and no
``now()``.

CRITICAL: the label is returned **verbatim** (``trend`` / ``channel`` / ``range``)
and the caller passes it straight to ``signal_systematic``. Do NOT remap it to
``REGIME_SCORES`` keys — the live engine has a partial-key overlap there (only
``trend`` scores; ``channel``/``range`` map to 0.0), and the backtest must
reproduce that quirk exactly rather than "fix" it (see the Phase-2 plan).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def detect_regime_from_df(df_prices: Optional[pd.DataFrame], lookback: int = 100) -> str:
    """Regime label as-of the last bar of ``df_prices`` (no DB, no ``now``).

    Mirrors ``MarketRegimeService.detect_market_regime``'s label logic on a
    caller-truncated DataFrame. Returns ``'trend'`` / ``'channel'`` / ``'range'``,
    or ``'unknown'`` on insufficient data (< 50 bars) or any failure.
    """
    if df_prices is None or len(df_prices) < 50:
        return "unknown"
    try:
        from app.services.market_regime import MarketRegimeService

        # The compute methods are pure (never touch the session); passing None is safe.
        svc = MarketRegimeService(None)
        df = df_prices.tail(lookback).copy()
        df = svc.calculate_moving_averages(df)
        df = svc.calculate_adx(df, period=14)

        adx = float(df["adx"].iloc[-1])
        plus_di = float(df["plus_di"].iloc[-1])
        minus_di = float(df["minus_di"].iloc[-1])
        ma20_slope = svc.calculate_ma_slope(df["ma20"], period=5)
        ma50_slope = svc.calculate_ma_slope(df["ma50"], period=5)

        tcr = svc.detect_tcr_regime(adx, plus_di, minus_di, ma20_slope, ma50_slope)
        return tcr["regime"]
    except Exception:
        return "unknown"


def detect_direction_from_df(df_prices: Optional[pd.DataFrame], lookback: int = 100) -> str:
    """Per-stock DIRECTIONAL regime as-of the last bar of ``df_prices`` (no DB, no ``now``).

    Sibling of :func:`detect_regime_from_df`: same compute (moving averages, ADX,
    MA slopes, TCR regime) but returns the ``direction`` label
    (``'bearish'`` / ``'bearish_weak'`` / ``'bullish'`` / ``'bullish_weak'`` /
    ``'neutral'``) instead of the regime, or ``'neutral'`` on insufficient data
    (< 50 bars) or any failure. The regime de-risk overlay (Phase 2.5) keys
    engine_1's buy-score suppression off this — it must be point-in-time, so it
    mirrors the live ``MarketRegimeService.detect_tcr_regime`` on a caller-truncated
    frame exactly (same as :func:`detect_regime_from_df`).

    ``detect_regime_from_df`` is intentionally left untouched (its callers + the
    no-look-ahead test stay byte-identical).
    """
    if df_prices is None or len(df_prices) < 50:
        return "neutral"
    try:
        from app.services.market_regime import MarketRegimeService

        svc = MarketRegimeService(None)
        df = df_prices.tail(lookback).copy()
        df = svc.calculate_moving_averages(df)
        df = svc.calculate_adx(df, period=14)

        adx = float(df["adx"].iloc[-1])
        plus_di = float(df["plus_di"].iloc[-1])
        minus_di = float(df["minus_di"].iloc[-1])
        ma20_slope = svc.calculate_ma_slope(df["ma20"], period=5)
        ma50_slope = svc.calculate_ma_slope(df["ma50"], period=5)

        tcr = svc.detect_tcr_regime(adx, plus_di, minus_di, ma20_slope, ma50_slope)
        return tcr["direction"]
    except Exception:
        return "neutral"
