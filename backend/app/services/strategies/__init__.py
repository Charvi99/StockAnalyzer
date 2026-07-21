"""
Trading-strategies package (Phase 0.5).

Public surface:
    - ``BaseStrategy``     — base class for strategies.
    - ``register_strategy`` — decorator to auto-register a strategy class.
    - ``StrategyManager``   — registry + execution + consensus.
    - ``strategy_manager``  — process-wide singleton instance.

Importing this package instantiates ``strategy_manager``, which auto-discovers
every ``@register_strategy`` class in the package.
"""
from .base import REGISTERED, BaseStrategy, register_strategy
from .registry import StrategyManager

# Singleton. Construction triggers auto-discovery of all registered strategies.
strategy_manager = StrategyManager()

__all__ = [
    "BaseStrategy",
    "register_strategy",
    "REGISTERED",
    "StrategyManager",
    "strategy_manager",
]
