"""
Pure signal layer for StockAnalyzer (Phase 0.4 refactor).

This package holds the **pure** signal logic — functions that take DataFrames and
plain dicts and return a :class:`SignalResult`, with NO database or ORM access.
The two recommendation engines become thin DB→DataFrame adapters over the pure
signal functions:

- ``recommendation_engine.generate_final_recommendation`` (Engine #1, systematic)
  → ``app.services.signal.systematic``  (0.4b)
- ``realtime_recommendation._get_recommendation_for_stock`` (Engine #2, swing)
  → ``app.services.signal.swing``  (0.4c)

Why: a pure signal is replayable. The paper-trading ledger (Phase 1) can call it
at time T from data-at-T and stamp a ``config_version``; the backtester (Phase 2)
can replay it bar-by-bar. Until the signal is pure, neither can measure the same
thing the live engine produces.

Per decision D35 the two engines stay separate (an A/B pair, unified only after
the ledger scores them). So there are TWO pure signal functions — one per surface
— sharing the common helpers in :mod:`app.services.signal.core`.
"""
from app.services.signal.types import SignalResult, config_version
from app.services.signal.core import (
    check_weekly_trend,
    detect_swing_points,
    categorize_candlestick_pattern,
    evaluate_swing_trading_context,
)

__all__ = [
    "SignalResult",
    "config_version",
    "check_weekly_trend",
    "detect_swing_points",
    "categorize_candlestick_pattern",
    "evaluate_swing_trading_context",
]
