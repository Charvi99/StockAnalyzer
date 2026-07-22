"""
Strategy registry + execution (Phase 0.5).

:class:`StrategyManager` replaces the old singleton-instance registry
(``app/services/strategy_manager.py``). Key fixes vs. the old manager:

- **Holds classes, not instances (S1).** A fresh strategy is built per call, so
  parameter overrides can never leak across requests/users.
- **Auto-discovery (scaling).** At init it imports every module in this package
  via ``pkgutil``; any class decorated with :func:`register_strategy` is picked
  up. Adding a strategy = drop a decorated class into the package.
- **A pure consensus helper.** :meth:`compute_strategy_consensus` takes a
  prices DataFrame + a pre-calculated indicators dict and returns the
  aggregated ``(signal, confidence, breakdown)``. It is DB-free and
  current-time-free, so Engine #2's adapter can call it inline (the consensus
  becomes the "strategy" vote component) and the snapshot endpoint can call it
  standalone — same logic, no duplication.

The public method names (``list_strategies`` / ``get_strategy`` /
``execute_strategy``) are unchanged so ``routes/strategies.py`` needs no edits
for the rewrite.
"""
import importlib
import logging
import os
import pkgutil
from typing import Any, Dict, List, Optional, Tuple, Type

import pandas as pd
from sqlalchemy.orm import Session

from .base import REGISTERED, BaseStrategy

logger = logging.getLogger(__name__)

# Consensus algorithm tag — baked into the source version so the Phase 1 ledger
# can attribute strategy-consensus signals across algorithm changes.
_SOURCE_SCHEMA = "strategies-v1"


class StrategyManager:
    """Class-based strategy registry with auto-discovery + per-call execution."""

    def __init__(self) -> None:
        self._classes: Dict[str, Type[BaseStrategy]] = {}
        self._discover()
        self.source_version = self._compute_source_version()
        logger.info(
            "StrategyManager: discovered %d strategies (source_version=%s): %s",
            len(self._classes), self.source_version, sorted(self._classes),
        )

    # ── auto-discovery ─────────────────────────────────────────────────────
    def _discover(self) -> None:
        """Import every module in this package so @register_strategy runs,
        then collect the registered classes. Base/registry modules are skipped."""
        pkg_dir = os.path.dirname(__file__)
        for mod_info in pkgutil.iter_modules([pkg_dir]):
            if mod_info.name in ("base", "registry", "__init__"):
                continue
            try:
                importlib.import_module(f"{__package__}.{mod_info.name}")
            except Exception as e:  # a broken strategy module must not kill the registry
                logger.exception("StrategyManager: failed to import strategies.%s: %s", mod_info.name, e)
        for cls in REGISTERED:
            instance = cls()  # safe: fresh instance just to read the name key
            self._classes[instance.name] = cls

    def _compute_source_version(self) -> str:
        """Deterministic version of the strategy-consensus source (ledger key)."""
        from app.services.signal.types import config_version
        snapshot = []
        for cls in sorted(self._classes.values(), key=lambda c: c.__name__):
            probe = cls()
            snapshot.append((cls.__name__, probe.get_default_parameters(), probe.weight))
        return config_version(snapshot, _SOURCE_SCHEMA)

    # ── registry accessors (signatures unchanged) ──────────────────────────
    def list_strategies(self) -> List[Dict[str, Any]]:
        out = []
        for name, cls in self._classes.items():
            s = cls()
            out.append({
                'name': s.name,
                'description': s.description,
                'parameters': s.get_default_parameters(),
                'min_data_points': s.get_min_data_points(),
            })
        return out

    def get_strategy(self, strategy_name: str) -> Optional[BaseStrategy]:
        """Return a FRESH default instance (no shared state). None if unknown."""
        cls = self._classes.get(strategy_name)
        return cls() if cls else None

    def get_strategy_class(self, strategy_name: str) -> Optional[Type[BaseStrategy]]:
        return self._classes.get(strategy_name)

    def validate_parameters(self, strategy_name: str, parameters: Optional[Dict[str, Any]]) -> None:
        """Raise ValueError if any override key is not a canonical param name (S3)."""
        if not parameters:
            return
        cls = self._classes.get(strategy_name)
        if cls is None:
            raise ValueError(f"Strategy '{strategy_name}' not found")
        known = set(cls().get_default_parameters())
        unknown = set(parameters) - known
        if unknown:
            raise ValueError(
                f"Unknown parameter(s) for strategy '{strategy_name}': {sorted(unknown)}. "
                f"Canonical names: {sorted(known)}"
            )

    # ── pure consensus helper (DB-free, now-free) ──────────────────────────
    def compute_strategy_consensus(
        self,
        prices_df: pd.DataFrame,
        indicators: Dict[str, Any],
        overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[Optional[str], Optional[float], List[Dict[str, Any]]]:
        """
        Run every strategy on the given data and collapse to one vote.

        Args:
            prices_df: OHLCV DataFrame WITH a ``timestamp`` column
                (chronological). Indicator values are read from ``indicators``,
                not from the frame.
            indicators: pre-calculated indicator dict (same shape
                ``TechnicalIndicators.generate_recommendation(...)['indicators']``
                returns).
            overrides: optional ``{strategy_name: {param: value}}`` to override a
                strategy's defaults (canonical names). None → all defaults.

        Returns:
            ``(consensus_signal, consensus_confidence, breakdown)``.
            ``consensus_signal`` is None only when no strategy cast a usable
            vote. ``breakdown`` is one dict per strategy:
            ``{name, signal, confidence, reason, weight, error?}``.
        """
        overrides = overrides or {}
        breakdown: List[Dict[str, Any]] = []
        components: List[Tuple[str, float, float]] = []  # (rec, conf, weight)

        for name, cls in self._classes.items():
            try:
                strategy = cls(parameters=overrides.get(name))
                rec, conf, details = strategy.analyze(prices_df, indicators)
                rec = rec or 'HOLD'
                conf = float(conf) if conf is not None else 0.0
                breakdown.append({
                    'name': name,
                    'signal': rec,
                    'confidence': round(conf, 4),
                    'reason': (details or {}).get('reason', ''),
                    'weight': strategy.weight,
                })
                if rec in ('BUY', 'SELL', 'HOLD') and conf > 0:
                    components.append((rec, conf, strategy.weight))
            except Exception as e:
                logger.warning("StrategyManager: strategy '%s' failed: %s", name, e)
                breakdown.append({
                    'name': name, 'signal': 'ERROR', 'confidence': 0.0,
                    'reason': str(e), 'weight': getattr(cls, 'weight', 1.0), 'error': True,
                })

        if not components:
            return None, None, breakdown

        total_weight = sum(w for _, _, w in components) or 1.0
        scores: Dict[str, float] = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
        for rec, conf, w in components:
            scores[rec] += conf * (w / total_weight)

        consensus_rec = max(scores, key=scores.get)
        return consensus_rec, round(scores[consensus_rec], 4), breakdown

    # ── DB-bound execution (route-facing) ──────────────────────────────────
    def _load_prices_df(self, db: Session, stock_id: int, limit: int) -> pd.DataFrame:
        from app.models.stock import StockPrice
        rows = (
            db.query(StockPrice)
            .filter(StockPrice.stock_id == stock_id)
            .order_by(StockPrice.timestamp.desc())
            .limit(limit)
            .all()
        )
        data = [{
            'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high),
            'low': float(p.low), 'close': float(p.close), 'volume': float(p.volume),
        } for p in rows]
        data.reverse()
        return pd.DataFrame(data)

    @staticmethod
    def _indicator_kwargs(strategy: BaseStrategy) -> Dict[str, Any]:
        """Forward canonical indicator-param names from the strategy's params."""
        out: Dict[str, Any] = {}
        for k in ('rsi_period', 'macd_fast', 'macd_slow', 'macd_signal', 'bb_window', 'bb_std'):
            if k in strategy.parameters:
                out[k] = strategy.parameters[k]
        return out

    def execute_strategy(
        self,
        strategy_name: str,
        stock_id: int,
        db: Session,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute one strategy on a stock (fresh instance; canonical params only)."""
        cls = self._classes.get(strategy_name)
        if cls is None:
            raise ValueError(f"Strategy '{strategy_name}' not found")

        from app.models.stock import Stock
        from app.services.technical_indicators import TechnicalIndicators

        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            raise ValueError(f"Stock with id {stock_id} not found")

        strategy = cls(parameters=parameters)  # fresh, canonical-names-only merge
        min_days = strategy.get_min_data_points() + 50
        prices_df = self._load_prices_df(db, stock_id, min_days)
        if prices_df.empty:
            raise ValueError(f"No price data available for stock {stock.symbol}")

        prices_df = TechnicalIndicators.calculate_all_indicators(
            prices_df, **self._indicator_kwargs(strategy)
        )
        indicators = TechnicalIndicators.generate_recommendation(prices_df)['indicators']

        signal, confidence, details = strategy.analyze(prices_df, indicators)
        return {
            'signal': signal,
            'confidence': round(float(confidence), 3),
            'details': details,
            'strategy_name': strategy_name,
            'stock_symbol': stock.symbol,
            'stock_id': stock_id,
            'current_price': float(prices_df.iloc[-1]['close']),
            'timestamp': prices_df.iloc[-1]['timestamp'].isoformat()
            if hasattr(prices_df.iloc[-1]['timestamp'], 'isoformat')
            else str(prices_df.iloc[-1]['timestamp']),
            'source_version': self.source_version,
        }

    def compute_consensus_for_stock(
        self,
        stock_id: int,
        db: Session,
        overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[Optional[str], Optional[float], List[Dict[str, Any]]]:
        """THE single source of truth for a live stock's strategy consensus.

        Loads a clean OHLCV window, computes indicators FRESH, and runs the
        weighted vote. Used by BOTH :meth:`snapshot` and the recommendation
        engine adapter so the radar axis, the per-strategy list, and the
        Strategies tab always agree.

        The adapter previously fed the cached ``tech_recommendation['indicators']``
        into :meth:`compute_strategy_consensus`; those cached values diverge from
        a fresh ``calculate_all_indicators`` calc and flip mixed-stock directions
        (e.g. JBHT SELL on the list vs HOLD on the radar). Routing everyone
        through this one method removes the second indicator context entirely.

        Raises ValueError if the stock or its price data is missing.
        Returns ``(consensus_rec, consensus_conf, breakdown)``.
        """
        from app.models.stock import Stock
        from app.services.technical_indicators import TechnicalIndicators

        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            raise ValueError(f"Stock with id {stock_id} not found")

        # Enough history for the longest min_data_points among strategies.
        max_min = max((cls().get_min_data_points() for cls in self._classes.values()), default=20) + 50
        prices_df = self._load_prices_df(db, stock_id, max_min)
        if prices_df.empty:
            raise ValueError(f"No price data available for stock {stock.symbol}")

        prices_df = TechnicalIndicators.calculate_all_indicators(prices_df)
        indicators = TechnicalIndicators.generate_recommendation(prices_df)['indicators']
        return self.compute_strategy_consensus(prices_df, indicators, overrides)

    def snapshot(self, stock_id: int, db: Session) -> Dict[str, Any]:
        """All strategies + consensus for a stock (delegates to the shared path)."""
        from app.models.stock import Stock

        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            raise ValueError(f"Stock with id {stock_id} not found")

        consensus_rec, consensus_conf, breakdown = self.compute_consensus_for_stock(stock_id, db)
        return {
            'stock_id': stock_id,
            'stock_symbol': stock.symbol,
            'source_version': self.source_version,
            'consensus': {'signal': consensus_rec, 'confidence': consensus_conf},
            'strategies': breakdown,
        }
