"""
Regime de-risk overlay — proportional bear-market suppression (Phase 2.5).

Pure, no-DB, no-``now`` math. The overlay scales LONG exposure down in bearish
regimes — *proportional*, never a hard buy-ban. It is OFF by default
(``strength == 0`` -> every factor is ``1.0`` -> byte-identical signals/sizes),
and is validated by A/B backtest before any live promotion.

Each engine applies the lever that fits its signal structure, keyed on the bear
detector it already computes:

- **engine_1 (systematic)** has a continuous weighted score in [-1, 1]; the
  overlay scales the **buy-leaning (positive) score** by
  :func:`buy_score_factor`, keyed on the per-stock directional regime
  (``bearish`` / ``bearish_weak`` from ``MarketRegimeService.detect_tcr_regime``).
  A weakly-bullish bearish-direction buy shrinks and may fall below the BUY
  threshold -> HOLD. Sells/holds are untouched.

- **engine_2 (swing)** decides by a vote, not a score, and its sizing is
  risk-based (stop distance), not confidence-based. So the overlay scales the
  resulting **position SIZE** by :func:`weekly_size_factor`, keyed on the
  engine's existing weekly trend (``weekly close < 50-week SMA``). A weekly-bear
  BUY still enters, but at reduced size -> real de-risk, no hard ban.

``strength ∈ [0, 1]`` is a fixed policy knob (NOT GA-tunable — the GA path keeps
``0``). Default test value ``0.4`` -> bear factor ``0.6`` / weak ``0.8``.
"""
from __future__ import annotations

from typing import Optional


def buy_score_factor(direction: Optional[str], strength: float) -> float:
    """engine_1: multiplier in ``[1-strength, 1.0]`` for a POSITIVE buy score.

    ``bearish`` -> ``1 - strength`` (full suppression); ``bearish_weak`` ->
    ``1 - strength/2`` (half); anything else (bullish / neutral / None / unknown)
    -> ``1.0``. ``strength <= 0`` -> ``1.0`` everywhere (overlay OFF, no-op).
    """
    if strength <= 0 or direction is None:
        return 1.0
    if direction == "bearish":
        return max(0.0, 1.0 - strength)
    if direction == "bearish_weak":
        return max(0.0, 1.0 - strength / 2.0)
    return 1.0


def weekly_size_factor(strength: float, is_weekly_bear: bool) -> float:
    """engine_2: multiplier in ``[1-strength, 1.0]`` for a position SIZE.

    Weekly-bear -> ``1 - strength``; otherwise ``1.0``. ``strength <= 0`` ->
    ``1.0`` everywhere (overlay OFF). The weekly trend has no "weak" gradation
    (it is bullish / bearish / neutral), so suppression is binary by regime.
    """
    if strength <= 0 or not is_weekly_bear:
        return 1.0
    return max(0.0, 1.0 - strength)
