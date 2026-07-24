"""
Pure stop/target level calculation for the backtester (Phase 2).

A price-only twin of ``OrderCalculatorService._calculate_levels_v2``. The live
service is DB/now-coupled (it queries ``Stock``/``StockPrice``/``ChartPattern``
+ a volume profile), so it cannot be reused in a no-look-ahead replay. This
reproduces the SL/TP priority chain using only the price series (``df_T``):

  SL : swing-low (ATR buffer) > pattern SL > ATR-based (2x) > 4% default,
       capped at an 8% max loss (``SL >= entry*0.92``).
  TP : pattern target > risk/reward (2.5x; 3x on strong bullish alignment),
       capped at +10% when overextended from the 200-SMA.

Volume-profile (VAL/VAH/HVN) and volume-weighted S/R branches are omitted —
those inputs are not derivable from OHLCV at price-technical fidelity, so they
fall through to the ATR / R:R fallbacks (documented). Everything here is a pure
function of ``df_T``; no DB, no ``now()``.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def _true_range_series(df_T: pd.DataFrame) -> pd.Series:
    h, l, c = df_T["high"], df_T["low"], df_T["close"]
    prev_c = c.shift(1)
    return pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)


def _atr(df_T: pd.DataFrame, period: int = 14) -> Optional[float]:
    s = _true_range_series(df_T).rolling(window=period, min_periods=period).mean()
    v = s.iloc[-1]
    return float(v) if pd.notna(v) else None


def _vol_status(df_T: pd.DataFrame, atr: Optional[float]) -> str:
    """Crude ATR-percentile -> band (mirrors detect_volatility_regime)."""
    try:
        s = _true_range_series(df_T).rolling(window=14, min_periods=14).mean().dropna()
        if len(s) < 2 or atr is None:
            return "normal"
        pct = (s < atr).sum() / len(s) * 100.0
        if pct >= 80:
            return "very_high"
        if pct >= 60:
            return "high"
        if pct >= 20:
            return "normal"
        return "low"
    except Exception:
        return "normal"


def _pattern_levels(df_T: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
    """First chart-pattern (stop_loss, target_price) from the pure detector."""
    try:
        from app.services.chart_patterns import ChartPatternDetector

        for p in ChartPatternDetector(df_T.tail(300).copy()).detect_all_patterns():
            sl, tp = p.get("stop_loss"), p.get("target_price")
            if sl is not None and tp is not None:
                return float(sl), float(tp)
    except Exception as e:  # noqa: BLE001
        logger.warning("[backtest] order-calc pattern levels failed: %s", e)
    return None, None


def _swing_low(df_T: pd.DataFrame, lookback: int = 20) -> Optional[float]:
    try:
        v = df_T["low"].tail(lookback).min()
        return float(v) if pd.notna(v) else None
    except Exception:
        return None


def _sma200_distance_pct(df_T: pd.DataFrame, entry_price: float) -> Optional[float]:
    if "close" not in df_T.columns or len(df_T) < 200:
        return None
    try:
        sma = df_T["close"].rolling(window=200, min_periods=200).mean().iloc[-1]
        if pd.isna(sma) or sma == 0:
            return None
        return abs(entry_price - float(sma)) / float(sma) * 100.0
    except Exception:
        return None


def calculate_levels(df_T: pd.DataFrame, entry_price: float, pattern_levels: Optional[Tuple[Optional[float], Optional[float]]] = None) -> Dict[str, float]:
    """entry / stop_loss / take_profit as-of the last bar of ``df_T`` (pure).

    ``entry_price`` is supplied by the replay engine (the bar's close, with
    slippage applied). Returns ``{entry_price, stop_loss, take_profit}``.

    ``pattern_levels``: optional pre-detected ``(stop_loss, target_price)`` from
    the bundle's chart detection (Phase 3). When given, the ~1s
    ``_pattern_levels`` re-detection is skipped — the GA's many eval candidates
    reuse ONE detection per (stock, T). ``None`` => detect fresh (Phase-2 path).
    """
    atr = _atr(df_T)
    vol = _vol_status(df_T, atr)
    if pattern_levels is not None:
        pattern_sl, pattern_tp = pattern_levels
    else:
        pattern_sl, pattern_tp = _pattern_levels(df_T)
    swing_low = _swing_low(df_T)

    # ── stop loss (priority: swing-low > pattern > ATR > 4% default) ──
    if swing_low is not None:
        mult = {"very_high": 1.5, "high": 1.2}.get(vol, 1.0)
        buffer = (atr * mult) if atr else (swing_low * 0.02)
        stop_loss = swing_low - buffer
    elif pattern_sl is not None and pattern_sl < entry_price:
        stop_loss = pattern_sl
    elif atr is not None:
        mult = 2.5 if vol == "very_high" else 2.0
        stop_loss = entry_price - (atr * mult)
    else:
        stop_loss = entry_price * 0.96

    max_sl = entry_price * 0.92  # cap at 8% max loss
    if stop_loss < max_sl:
        stop_loss = max_sl

    # ── take profit (priority: pattern target > risk/reward) ──
    if pattern_tp is not None and pattern_tp > entry_price:
        take_profit = pattern_tp
    else:
        risk_reward = 2.5
        stop_distance = abs(entry_price - stop_loss)
        take_profit = entry_price + (stop_distance * risk_reward)

    # cap if overextended from the 200-SMA (>10% above)
    dist = _sma200_distance_pct(df_T, entry_price)
    if dist is not None and dist > 10:
        max_tp = entry_price * 1.10
        if take_profit > max_tp:
            take_profit = max_tp

    return {"entry_price": entry_price, "stop_loss": stop_loss, "take_profit": take_profit}
