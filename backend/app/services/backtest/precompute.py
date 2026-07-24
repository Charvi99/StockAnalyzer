"""
Per-(stock, T) input precompute for the backtester GA (Phase 3).

The signal INPUTS (indicators / patterns / regime / tech-recommendation) are
weight-independent. So for a GA that replays the same universe many times under
different weights, the EXPENSIVE input assembly can be computed ONCE per
(stock, T) and reused across every candidate — each candidate then only
re-applies weights (cheap).

CAUSALITY (no look-ahead): each bundle is assembled from ``df_T =
prices[timestamp <= T]`` with T as the LAST bar of that frame. The ``*_signal``
indicator columns are last-bar-broadcast (computed from the frame's last bar and
copied across the column), so they MUST be computed on a frame whose last bar IS
T — full-series indicator slicing would instead carry the series-last-bar's
signal and LEAK THE FUTURE. This per-(stock, T) cache avoids that by assembling
on the truncated frame, exactly like the Phase-2 per-bar path.

MEMORY: the cache holds one bundle per (stock, trading day). Keep the GA universe
+ window scoped (the API's ``max_stocks`` + a shorter date range) so it fits in
RAM. Single backtests do NOT use this cache — they assemble per bar.

Pure module: no wall-clock reads, no DB, no cache service (AST-guarded alongside
the other backtest modules).
"""
from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


def precompute_inputs(
    engine: str,
    prices_by_stock: Dict[int, pd.DataFrame],
    trading_dates: List,
    on_progress=None,
) -> Dict:
    """Assemble + memoize signal inputs for every (stock, T) over the causal window.

    Returns ``dict[(stock_id, T)] -> bundle`` where ``bundle`` is the kwargs for
    the engine's signal function (minus ``weights``), or ``None`` for stocks with
    insufficient history at T (the caller maps ``None`` -> a neutral HOLD).

    Build ONCE per GA run; reuse across every weight candidate.
    """
    from app.services.backtest.backtest_signal_adapter import assemble_inputs, compute_components

    cache: Dict = {}
    stocks = list(prices_by_stock.items())
    total = len(stocks)
    for i, (sid, df) in enumerate(stocks, 1):
        for T in trading_dates:
            T = pd.Timestamp(T)
            df_T = df[df["timestamp"] <= T]
            if len(df_T) < 2:
                continue
            try:
                bundle = assemble_inputs(engine, df_T)
            except Exception:  # noqa: BLE001 — assembly failure -> None (neutral HOLD)
                bundle = None
            # Phase 3 #3: precompute the weight-independent component votes ONCE per
            # (stock, T) so every GA candidate only re-applies weights via
            # ``signal_as_of`` -> ``assemble`` (skipping the ~99%-of-cost signal
            # derivation). Best-effort: on failure leave ``_components`` absent ->
            # signal_as_of falls back to the per-call path (still correct, just slow).
            if bundle is not None:
                try:
                    bundle["_components"] = compute_components(engine, bundle)
                except Exception as e:  # noqa: BLE001
                    logger.warning("[backtest] component precompute failed for %s@%s: %s", sid, T, e)
            cache[(sid, T)] = bundle
        # Live progress (Phase 3 UI): report per-stock completion so the dashboard
        # can show "Precomputing inputs (i/N stocks)" during the one-time cache build.
        if on_progress:
            try:
                on_progress(i, total)
            except Exception:  # noqa: BLE001 — progress is best-effort; never abort the build
                pass
    return cache
