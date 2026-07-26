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

PARALLELISM: the build is embarrassingly parallel across stocks (no cross-stock
state), so it is fanned out across CPU cores via a ``multiprocessing`` pool. The
GA worker is otherwise single-threaded — on a multi-core host this turns a ~4h
100x2y precompute into ~40 min. ``imap_unordered`` STREAMS each completed stock's
slice back one at a time, so the parent accumulates the cache exactly as the
serial path would (peak RAM ~= final cache size + a few in-flight per-stock
slices), never holding all slices in workers at once. Output is identical to the
serial build (the cache is keyed by ``(sid, T)``; completion order is irrelevant).

Pure module: no wall-clock reads, no DB, no cache service (AST-guarded alongside
the other backtest modules).
"""
from __future__ import annotations

import logging
import multiprocessing
import os
from typing import Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

# Cap parallel workers so the parent process (which accumulates the whole cache)
# and the other containers keep CPU headroom on a multi-core host.
_MAX_PRECOMPUTE_WORKERS = 6


def _precompute_one_stock(task) -> Dict:
    """Build the ``{(stock_id, T): bundle}`` slice for ONE stock.

    Pure + picklable (runs in a worker process). This is exactly the original
    per-stock loop body — only the outer distribution across stocks changed, not
    the per-bar logic, so output is identical to the serial build. Best-effort: a
    per-(stock,T) assembly/component failure maps that entry to ``None`` (neutral
    HOLD) and a catastrophic failure for the whole stock returns ``{}`` (logged)
    so one bad stock never aborts the entire build.
    """
    engine, sid, df, trading_dates = task
    from app.services.backtest.backtest_signal_adapter import assemble_inputs, compute_components

    out: Dict = {}
    try:
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
            out[(sid, T)] = bundle
    except Exception as e:  # noqa: BLE001 — one bad stock must not abort the whole build
        logger.exception("[backtest] precompute failed for stock %s: %s", sid, e)
        return {}
    return out


def _in_daemonic_context() -> bool:
    """True when this process can't spawn multiprocessing children.

    Celery's default ``prefork`` pool runs tasks inside daemonic ``ForkPoolWorker``
    processes, and Python forbids daemonic processes from creating child processes
    (``AssertionError: daemonic processes are not allowed to have children``). So a
    GA task running under Celery must fall back to serial precompute (correct, just
    not parallel). Plain processes — the standalone scripts run via ``docker exec``
    (attribution, stress test) and unit tests — are non-daemonic and use the pool.
    """
    try:
        return bool(multiprocessing.current_process().daemon)
    except Exception:  # noqa: BLE001
        return False


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

    Build ONCE per GA run; reuse across every weight candidate. Parallelized
    across stocks (see module docstring); tiny builds fall back to serial to avoid
    pool spin-up overhead.
    """
    cache: Dict = {}
    stocks = list(prices_by_stock.items())
    total = len(stocks)
    if total == 0:
        return cache

    tasks = [(engine, sid, df, trading_dates) for sid, df in stocks]

    def _report(i: int) -> None:
        # Live progress (Phase 3 UI): per-stock completion so the dashboard can show
        # "Precomputing inputs (i/N stocks)" during the one-time cache build.
        if on_progress:
            try:
                on_progress(i, total)
            except Exception:  # noqa: BLE001 — progress is best-effort; never abort the build
                pass

    n_cpu = os.cpu_count() or 1
    n_workers = max(1, min(n_cpu - 1, _MAX_PRECOMPUTE_WORKERS))

    # Serial path: tiny builds, single-core hosts, OR a daemonic process (Celery
    # prefork task workers can't spawn multiprocessing children -> AssertionError).
    # Falling back to serial here is correct, just not parallel. To get parallel
    # precompute inside Celery, run the worker with --pool=threads (non-daemonic).
    if total < 2 or n_workers < 2 or _in_daemonic_context():
        for i, task in enumerate(tasks, 1):
            cache.update(_precompute_one_stock(task))
            _report(i)
        return cache

    # Parallel: each worker builds one stock's slice; imap_unordered streams
    # completed slices back one at a time so peak RAM ~= final cache size.
    ctx = multiprocessing.get_context("fork")  # explicit: COW-shares parent state; needs no __main__ guard
    with ctx.Pool(processes=n_workers) as pool:
        for i, sub in enumerate(pool.imap_unordered(_precompute_one_stock, tasks), 1):
            cache.update(sub)
            _report(i)
    return cache
