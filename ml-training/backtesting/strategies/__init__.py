"""
Trading strategies for backtesting.
"""
from .base import BaseStrategy, Signal
from .buy_and_hold import BuyAndHoldStrategy

__all__ = [
    'BaseStrategy',
    'Signal',
    'BuyAndHoldStrategy',
]
