"""
Backward-compatibility facade for the strategies package (Phase 0.5).

The real implementation now lives in :mod:`app.services.strategies`. This
module re-exports the singleton so existing imports
(``from app.services.strategy_manager import strategy_manager``) keep working
unchanged. The old singleton-instance registry that lived here was removed —
see :mod:`app.services.strategies.registry` for the rewritten, class-based,
auto-discovering registry (audit fixes S1/S3 + scaling).
"""
from app.services.strategies import (  # noqa: F401 (re-export)
    BaseStrategy,
    StrategyManager,
    register_strategy,
    strategy_manager,
)

__all__ = ["BaseStrategy", "StrategyManager", "register_strategy", "strategy_manager"]
