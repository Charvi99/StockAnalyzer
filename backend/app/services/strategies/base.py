"""
Base class + registry hook for trading strategies (Phase 0.5).

This is the rewritten home of ``BaseStrategy`` (moved from
``app/services/base_strategy.py``). Differences from the old version:

- **Immutable per-call use.** The registry holds *classes* (factories), not
  long-lived instances. Callers instantiate a fresh strategy per request with
  merged params, so there is no shared mutable state to leak across requests
  or users (audit finding **S1**).
- **Canonical params (S3).** Each strategy declares its parameters via
  ``get_default_parameters()``; the route validates request overrides against
  those canonical names (unknown keys → 422). Param names that flow into
  indicator calculation use the canonical indicator names
  (``rsi_period``/``macd_fast``/``macd_slow``/``macd_signal``/``bb_window``/
  ``bb_std``) so they cannot silently mismatch the calculator again.
- **No toy backtest (S2).** The lookahead-biased ``backtest()`` that lived in
  the base class is removed. A real backtester is Phase 2.
- **Consensus-ready.** Each strategy carries a ``weight`` used when the
  strategies are collapsed into the single Engine #2 "strategy" component.

``register_strategy`` is the auto-discovery hook: decorating a subclass adds it
to ``REGISTERED``, which ``StrategyManager`` collects by importing every module
in this package (see ``registry.py``). Adding a strategy = drop a decorated
class into the package; no manual list to edit.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type

import pandas as pd

# Populated by the @register_strategy decorator. StrategyManager imports every
# module in this package (pkgutil) so decoration runs, then reads this list.
REGISTERED: List[Type["BaseStrategy"]] = []


def register_strategy(cls: Type["BaseStrategy"]) -> Type["BaseStrategy"]:
    """Class decorator: register a BaseStrategy subclass for auto-discovery."""
    if not issubclass(cls, BaseStrategy):
        raise TypeError(f"@register_strategy: {cls.__name__} must subclass BaseStrategy")
    if cls not in REGISTERED:
        REGISTERED.append(cls)
    return cls


class BaseStrategy(ABC):
    """
    Base class for all trading strategies.

    Subclasses implement :meth:`analyze` and may override
    :meth:`get_default_parameters` / :meth:`get_min_data_points`.

    Attributes:
        name: Strategy name (registry key) — set as a CLASS attribute.
        description: Human-readable description — set as a CLASS attribute.
        parameters: Resolved parameters (defaults merged with any overrides
            passed at construction). Treat as read-only after construction.
        weight: Vote weight when this strategy contributes to the strategy
            consensus (default 1.0 = equal weight).

    Subclasses set ``name``/``description`` as class attributes and implement
    ``analyze`` (+ optionally ``get_default_parameters``/``get_min_data_points``).
    No ``__init__`` boilerplate is required — adding a strategy is just those
    pieces plus ``@register_strategy``.
    """

    name: str = ""
    description: str = ""
    # Equal-weight by default; override per strategy to emphasize/de-emphasize.
    weight: float = 1.0

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        merged = dict(self.get_default_parameters())
        if parameters:
            # Only accept canonical names; ignore anything else defensively.
            known = set(self.get_default_parameters())
            for k, v in parameters.items():
                if k in known:
                    merged[k] = v
        self.parameters = merged

    @abstractmethod
    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        Analyze the stock data and generate a trading signal.

        Args:
            prices: DataFrame with columns timestamp, open, high, low, close,
                volume (chronological).
            indicators: Pre-calculated indicator dict, as produced by
                ``TechnicalIndicators.generate_recommendation(df)['indicators']``
                (keys like 'RSI', 'MACD', 'Moving_Averages', 'Bollinger_Bands',
                'ADX', each a nested dict).

        Returns:
            (signal, confidence, details) where signal is 'BUY'/'SELL'/'HOLD',
            confidence is a float in [0.0, 1.0], and details is a dict (may
            include entry_price/stop_loss/take_profit/reason).
        """
        raise NotImplementedError

    # ── data validation ────────────────────────────────────────────────────
    def validate_data(self, prices: pd.DataFrame) -> bool:
        """True if prices has the required OHLCV columns and enough bars."""
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if prices is None or prices.empty:
            return False
        if not all(col in prices.columns for col in required_columns):
            return False
        if len(prices) < self.get_min_data_points():
            return False
        return True

    def get_min_data_points(self) -> int:
        """Minimum bars required. Override if a strategy needs more history."""
        return 20

    # ── parameters ─────────────────────────────────────────────────────────
    def get_default_parameters(self) -> Dict[str, Any]:
        """Canonical default parameters. Override per strategy.

        These names are the contract: request overrides are validated against
        them (unknown keys → 422 at the API edge). Names that should flow into
        ``TechnicalIndicators.calculate_all_indicators`` must match its kwargs
        (rsi_period/macd_fast/macd_slow/macd_signal/bb_window/bb_std).
        """
        return {}

    def get_parameters(self) -> Dict[str, Any]:
        return self.parameters

    def get_param_names(self) -> List[str]:
        return list(self.get_default_parameters().keys())

    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Instance-local parameter update (back-compat). Only canonical names
        are accepted. Because the registry holds classes and callers build a
        fresh instance per request, this never mutates shared state."""
        known = set(self.get_default_parameters())
        for k, v in parameters.items():
            if k in known:
                self.parameters[k] = v

    def get_params(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Defaults merged with overrides (canonical names only)."""
        merged = dict(self.get_default_parameters())
        if overrides:
            known = set(merged)
            for k, v in overrides.items():
                if k in known:
                    merged[k] = v
        return merged

    # ── risk helper (kept; used by docs + position sizing) ─────────────────
    def calculate_position_size(
        self,
        account_balance: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss: float,
    ) -> int:
        """Shares to buy given a fixed-fractional risk per trade."""
        if stop_loss == 0 or entry_price == stop_loss:
            return 0
        risk_amount = account_balance * risk_per_trade
        risk_per_share = abs(entry_price - stop_loss)
        return max(0, int(risk_amount / risk_per_share))

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"

    def __repr__(self) -> str:
        return f"<Strategy: {self.name}>"
