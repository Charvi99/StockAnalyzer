"""
Fresh-signal adapter for the paper-trading ledger (Phase 1, step 2).

This is the **load-bearing C2 fix**. The live recommendation adapters
(``recommendation_engine.generate_final_recommendation`` for Engine #1 and
``realtime_recommendation._get_recommendation_for_stock`` for Engine #2) are the
*trader-facing* surfaces. Engine #2's adapter fuses **cached** technical
indicators (``IndicatorCacheService``) with fresh strategy consensus — the exact
Phase-0.5 JBHT divergence (SELL on the list, HOLD on the radar). A cached signal
is not reproducible: ``config_version`` hashes the **weights**, not the **inputs**.

The ledger must measure signal *quality*, so it calls the PURE signal functions
(``signal_systematic`` / ``signal_swing``) on **freshly-fetched** data and reads
``config_version`` off the returned :class:`SignalResult`. This module owns that
fresh assembly and is deliberately separate from the live adapters:

  - **Engine #1** — the live adapter is *already* fresh (it fetches 60 daily bars
    and ``signal_systematic`` computes indicators itself), so the assembly here is
    faithful to it; the value is returning the ``SignalResult`` (config-bearing)
    instead of the legacy dict.
  - **Engine #2** — the assembly here drops the cache branch and computes the
    indicator frame fresh via ``TechnicalIndicators.calculate_all_indicators``
    (the divergence from the live adapter is intentional and is the whole point).

The PERMANENT invariant (locked by ``test_phase1_ledger``): this module NEVER
references ``IndicatorCacheService`` — for either engine. The ledger trades the
fresh signal, not a cached one.

Phase 1 step 2 ships Engine #1 only; Engine #2 is enabled in step 8 (it raises
``NotImplementedError`` until then so the dispatch structure is ready).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.services.signal.types import SignalResult

logger = logging.getLogger(__name__)


def signal_for_ledger(db: Session, stock, engine: str) -> SignalResult:
    """
    Compute the FRESH signal the ledger trades, for one stock under one engine.

    Mirrors each engine's live adapter data-assembly minus any cache, delegates to
    the pure signal function, and returns the :class:`SignalResult` (which carries
    ``config_version`` for attribution). Per-component fetches are fault-tolerant
    (a failure leaves that component at its default, matching the live engines —
    the score stays neutral, it does not abort the cycle).

    Args:
        db: database session.
        stock: a ``Stock`` (or any object with ``.id``). Engine #1 uses ``.id`` only.
        engine: ``'engine_1'`` (systematic) or ``'engine_2'`` (swing).

    Returns:
        The :class:`SignalResult` produced by the pure signal function.

    Raises:
        ValueError: unknown ``engine``.
        NotImplementedError: ``'engine_2'`` before Phase 1 step 8.
    """
    if engine == "engine_1":
        return _engine1_signal(db, stock)
    if engine == "engine_2":
        return _engine2_signal(db, stock)
    raise ValueError(
        f"Unknown paper-trading engine {engine!r}; expected 'engine_1' or 'engine_2'."
    )


# ── Engine #1 (systematic) ────────────────────────────────────────────────────
def _engine1_signal(db: Session, stock) -> SignalResult:
    """
    Engine #1 fresh signal — mirrors ``generate_final_recommendation`` but returns
    the :class:`SignalResult` (config-bearing) instead of the legacy dict.

    Faithful to the live adapter: same 6 inputs, same time windows (chart 30d,
    candlestick 7d, prices 60 bars, news 20), same per-component fault tolerance,
    and it delegates to the same pure ``signal_systematic``. The live Engine #1
    adapter uses no cache, so this is byte-identical to it for the same DB state.
    """
    from app.services.signal.systematic import signal_systematic

    return signal_systematic(
        df_prices=_fetch_engine1_prices(db, stock.id),
        chart_patterns=_fetch_engine1_chart_patterns(db, stock.id),
        candlestick_patterns=_fetch_engine1_candlestick_patterns(db, stock.id),
        sentiment_score=_fetch_engine1_sentiment(db, stock.id),
        regime=_fetch_engine1_regime(db, stock.id),
        dividend_split_signal=_fetch_engine1_dividend_split(db, stock.id),
    )


def _fetch_engine1_chart_patterns(db: Session, stock_id: int):
    """Last-30d chart patterns -> [{signal, confidence_score, confirmation_level}]."""
    try:
        from app.models.stock import ChartPattern

        recent = db.query(ChartPattern).filter(
            ChartPattern.stock_id == stock_id,
            ChartPattern.created_at >= datetime.now(timezone.utc) - timedelta(days=30),
        ).all()
        return [
            {
                "signal": p.signal,
                "confidence_score": p.confidence_score,
                "confirmation_level": p.confirmation_level,
            }
            for p in recent
        ]
    except Exception as e:
        logger.warning(f"[ledger engine_1] chart pattern fetch failed (stock {stock_id}): {e}")
        return []


def _fetch_engine1_candlestick_patterns(db: Session, stock_id: int):
    """Last-7d candlestick patterns -> [{pattern_type, confidence_score}]."""
    try:
        from app.models.stock import CandlestickPattern

        recent = db.query(CandlestickPattern).filter(
            CandlestickPattern.stock_id == stock_id,
            CandlestickPattern.timestamp >= datetime.now(timezone.utc) - timedelta(days=7),
        ).all()
        return [
            {"pattern_type": p.pattern_type, "confidence_score": p.confidence_score}
            for p in recent
        ]
    except Exception as e:
        logger.warning(f"[ledger engine_1] candlestick fetch failed (stock {stock_id}): {e}")
        return []


def _fetch_engine1_prices(db: Session, stock_id: int) -> pd.DataFrame:
    """Last 60 daily bars -> DataFrame WITH a `timestamp` column, chronological.

    Matches ``generate_final_recommendation`` exactly: newest-first `.limit(60)`,
    then reversed to chronological, with a plain ``timestamp`` COLUMN (not index).
    ``signal_systematic`` calls ``calculate_all_indicators`` on this frame.
    """
    try:
        from app.models.stock import StockPrice

        prices = db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
        ).order_by(StockPrice.timestamp.desc()).limit(60).all()

        if not prices:
            return pd.DataFrame()

        return pd.DataFrame([
            {
                "timestamp": p.timestamp,
                "open": float(p.open),
                "high": float(p.high),
                "low": float(p.low),
                "close": float(p.close),
                "volume": int(p.volume),
            }
            for p in reversed(prices)  # chronological
        ])
    except Exception as e:
        logger.warning(f"[ledger engine_1] price fetch failed (stock {stock_id}): {e}")
        return pd.DataFrame()


def _fetch_engine1_sentiment(db: Session, stock_id: int):
    """Mean sentiment of the 20 most-recent scored news articles -> float|None."""
    try:
        from app.models.news import News

        recent_news = db.query(News).filter(
            News.stock_id == stock_id,
            News.sentiment_score.isnot(None),
        ).order_by(News.published_utc.desc()).limit(20).all()

        if recent_news:
            return sum(float(a.sentiment_score) for a in recent_news) / len(recent_news)
        return None
    except Exception as e:
        logger.warning(f"[ledger engine_1] sentiment fetch failed (stock {stock_id}): {e}")
        return None


def _fetch_engine1_regime(db: Session, stock_id: int) -> str:
    """MarketRegimeService regime label, or 'unknown' on failure."""
    try:
        from app.services.market_regime import MarketRegimeService

        return MarketRegimeService(db).detect_market_regime(stock_id).get("regime", "unknown")
    except Exception as e:
        logger.warning(f"[ledger engine_1] regime detection failed (stock {stock_id}): {e}")
        return "unknown"


def _fetch_engine1_dividend_split(db: Session, stock_id: int):
    """DividendSplitDetector signal dict (has_signal block), or None."""
    try:
        from app.services.dividend_split_detector import DividendSplitDetector

        signal = DividendSplitDetector().get_signals_for_recommendation(
            stock_id, db, days_ahead=30
        )
        return signal if signal.get("has_signal") else None
    except Exception as e:
        logger.warning(f"[ledger engine_1] dividend/split detection failed (stock {stock_id}): {e}")
        return None


# ── Engine #2 (swing) — enabled in Phase 1 step 8 ─────────────────────────────
def _engine2_signal(db: Session, stock) -> SignalResult:
    """
    Engine #2 fresh signal (C2 fix: computes the indicator frame FRESH via
    ``TechnicalIndicators.calculate_all_indicators`` instead of the live adapter's
    ``IndicatorCacheService`` branch). Implemented in Phase 1 step 8 when engine_2
    is seeded and its beat enabled.
    """
    raise NotImplementedError(
        "engine_2 ledger signal is enabled in Phase 1 step 8 "
        "(fresh-indicator path, no cache). It is intentionally not live yet."
    )
