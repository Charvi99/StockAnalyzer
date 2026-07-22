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

# module-level cache (single-process backend; per-worker is fine — worst case a
# few extra Polygon calls across workers)
_cache: Dict[str, object] = {"fetched_at": 0.0, "series": []}


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


def _fetch_cached() -> List[Dict]:
    """Return the raw SPY daily ``[{date, close}]`` series (oldest-first), cached."""
    now = time.time()
    if _cache["series"] and (now - _cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        return _cache["series"]
    fetched = _fetch_spy()
    if fetched:
        _cache["fetched_at"] = now
        _cache["series"] = fetched
    return fetched


def _fetch_spy() -> List[Dict]:
    """Fetch SPY daily closes from Polygon → ``[{date, close}]``, oldest-first."""
    from app.services.polygon_fetcher import PolygonFetcher

    fetcher = PolygonFetcher(api_key=os.getenv("POLYGON_API_KEY"))
    bars = fetcher.fetch_historical_data(BENCHMARK_SYMBOL, period="1y", interval="1d")
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
