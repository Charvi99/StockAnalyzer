"""
S&P 500 (SPY) benchmark series for the paper-trading equity curve.

The ledger measures recommendation quality; the honest yardstick is "did the
engine beat the market?" — so the equity view overlays SPY (scaled to the same
starting capital) alongside each engine's equity. SPY is a normal Polygon ticker,
fetched on demand and cached briefly so rapid dashboard refreshes don't re-hit the
API. On any failure the benchmark is simply absent (empty list) — it never breaks
the equity view.
"""
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)

BENCHMARK_SYMBOL = "SPY"
_CACHE_TTL_SECONDS = 15 * 60  # refresh at most every 15 min

# module-level cache keyed by fetch period (single-process backend; per-worker is
# fine — worst case a few extra Polygon calls across workers)
_cache: Dict[str, Dict] = {}


def _with_returns(window: List[Dict]) -> List[Dict]:
    """Add cumulative ``return_pct`` to a ``[{date, close}]`` window (oldest-first).

    ``return_pct`` is measured from the first in-window close, so the frontend can
    scale SPY to any engine's starting_cash and plot it alongside that engine's
    equity. Pure (no I/O) → unit-tested directly."""
    if not window:
        return []
    first = window[0]["close"]
    out = []
    for bar in window:
        close = bar["close"]
        ret = (close - first) / first if first else 0.0
        out.append({"date": bar["date"], "close": close, "return_pct": ret})
    return out


def get_spy_series(days: int = 90) -> List[Dict]:
    """SPY daily closes over the last ``days`` trading days as
    ``[{date(YYYY-MM-DD), close, return_pct}]``, oldest-first.

    Returns ``[]`` on any failure (the benchmark line is simply omitted; the equity
    view must never depend on Polygon being reachable)."""
    try:
        series = _fetch_cached()
        if not series:
            return []
        window = series[-days:] if days and days < len(series) else series
        return _with_returns(window)
    except Exception as e:
        logger.warning("[benchmark] SPY series failed: %s", e)
        return []


def get_spy_series_for_window(start, end) -> List[Dict]:
    """Date-aligned SPY daily series for a historical ``[start, end]`` window as
    ``[{date(YYYY-MM-DD), close, return_pct}]``, oldest-first, filtered to the window.

    Unlike :func:`get_spy_series` (which only ever returns the *recent* last-1y
    slice), this fetches enough history to cover ``start`` (which may be years in
    the past), so it is correct for historical backtest windows. ``start``/``end``
    may be ``pandas``/``datetime`` timestamps or ISO ``YYYY-MM-DD`` strings.

    Returns ``[]`` on any failure (the benchmark line/alpha is simply omitted)."""
    try:
        import pandas as pd

        start_s = pd.Timestamp(start).strftime("%Y-%m-%d")
        end_s = pd.Timestamp(end).strftime("%Y-%m-%d")
        # Always fetch the full 5y history: the fetcher only honours a couple of
        # period values ("1y", "5y") — anything in between collapses to ~1y, which
        # would miss a years-old window. 5y covers every realistic backtest window;
        # cached per-period for 15 min.
        series = _fetch_cached("5y")
        if not series:
            return []
        window = [b for b in series if start_s <= b["date"] <= end_s]
        return _with_returns(window)
    except Exception as e:
        logger.warning("[benchmark] SPY window series failed: %s", e)
        return []


def _fetch_cached(period: str = "1y") -> List[Dict]:
    """Return the raw SPY daily ``[{date, close}]`` series (oldest-first), cached
    per ``period`` (the live view uses ``"1y"``; historical backtest windows use
    ``"5y"`` so years-old windows are covered)."""
    now = time.time()
    entry = _cache.get(period)
    if entry and entry["series"] and (now - entry["fetched_at"]) < _CACHE_TTL_SECONDS:
        return entry["series"]
    fetched = _fetch_spy(period=period)
    if fetched:
        _cache[period] = {"fetched_at": now, "series": fetched}
    return fetched


def _fetch_spy(period: str = "1y") -> List[Dict]:
    """Fetch SPY daily closes from Polygon → ``[{date, close}]``, oldest-first.

    ``period`` widens the fetch so a historical backtest window (e.g. 2024) is
    covered even though "now" is years later — ``"1y"`` (default) preserves the
    existing recent-window behaviour used by the live equity view."""
    from app.services.polygon_fetcher import PolygonFetcher

    fetcher = PolygonFetcher(api_key=os.getenv("POLYGON_API_KEY"))
    bars = fetcher.fetch_historical_data(BENCHMARK_SYMBOL, period=period, interval="1d")
    if not bars:
        return []
    out = []
    for b in bars:
        ts = b.get("timestamp")
        close = b.get("close")
        if ts is None or close is None:
            continue
        # fetch_historical_data returns tz-aware UTC datetimes; normalize to a
        # calendar date string so it lines up with the equity snapshot `date`.
        d = ts.astimezone(timezone.utc).strftime("%Y-%m-%d") if isinstance(ts, datetime) else str(ts)[:10]
        out.append({"date": d, "close": float(close)})
    return out
