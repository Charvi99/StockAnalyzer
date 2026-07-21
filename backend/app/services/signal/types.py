"""
Signal-layer type contracts (Phase 0.4 refactor).

Defines:
- :class:`SignalResult` — the single return type every pure signal function
  produces. This is the internal contract the live engines, the paper-trading
  ledger (Phase 1), and the backtester (Phase 2) all consume. Legacy dict /
  ``RecommendationResponse`` shapes are produced by mapping a ``SignalResult`` at
  the adapter edges, so existing callers keep working unchanged.
- :func:`config_version` — a deterministic short hash of the weights/thresholds
  that define a signal, so every recommendation can carry a ``signal_version``
  (roadmap §1.5). Tweaking a weight changes the hash -> the ledger knows the
  signal definition changed.

This module imports ONLY the stdlib (no ORM, no DB, no app.* imports) so the pure
signal layer is replayable and unit-testable without a database.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SignalResult:
    """
    The pure signal a recommendation surface produces for one stock at one time.

    Fields mirror what the paper-trading ledger (Phase 1) records per signal
    fired. Entry/stop/target are NOT here — those are trade-construction outputs
    of the order calculator, not part of the signal itself.

    Attributes:
        signal: BUY / SELL / HOLD.
        confidence: 0..1, surface-defined.
        weighted_score: raw combined score; range is surface-defined (e.g. the
            systematic engine's [-1, 1] weighted average).
        component_scores: per-component scores; keys are surface-defined
            (e.g. ``technical_indicators``, ``chart_patterns``).
        config_version: hash of the config that produced this signal. Two
            recommendations with the same ``config_version`` were computed under
            identical weights/thresholds.
        reasoning: human-readable explanation lines (UI + audit).
        regime: market regime at signal time (e.g. Trend/Cycle/trending_up), if
            known; ``None`` when the surface does not compute one.
        extras: surface-specific payload that does not fit the common fields
            (e.g. the dividend/split signal block, ML prediction). Optional.
    """

    signal: str
    confidence: float
    weighted_score: float
    component_scores: Dict[str, float]
    config_version: str
    reasoning: List[str] = field(default_factory=list)
    regime: Optional[str] = None
    extras: Optional[Dict[str, Any]] = None


def config_version(*parts: Any) -> str:
    """
    Deterministic 12-char hash of the config parts that define a signal.

    Pass the weights dict, thresholds dict, and a schema tag, e.g.::

        config_version({"chart": 0.28, "tech": 0.23, ...}, {"buy": 0.3}, "systematic-v1")

    Two calls with identical parts return the same hash; changing any weight or
    threshold changes it, so the ledger can detect that the signal definition
    changed. ``sort_keys=True`` makes the hash order-independent. Values are
    coerced via ``str`` so dataclasses/floats hash deterministically.
    """
    blob = json.dumps(parts, default=str, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]
