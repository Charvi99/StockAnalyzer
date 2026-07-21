"""
Realtime Recommendation Engine (Engine #2) — swing-trading-aware recommendation.

DB→DataFrame adapter over the pure signal function
:func:`app.services.signal.swing.signal_swing`. This module owns all database /
cache access, the ``now``-based time-window filtering (30-day candlesticks,
90-day chart patterns, 30-day news), and the mapping of the resulting
:class:`SignalResult` back to ``RecommendationResponse``.

The swing-aware scoring logic — weighted vote, weekly-trend override, Phase-2C
context, dividend/split adjustments — lives in the pure ``signal.swing`` module
so the paper-trading ledger (Phase 1) and backtester (Phase 2) call exactly what
the live engine produces, with no DB coupling and no hidden ``now``.

Kept deliberately separate from ``recommendation_engine.generate_final_recommendation``
(Engine #1, the background systematic 6-factor score): the two are an **A/B pair**
(see ``docs/audit/BU1_analysis_brain.md``, decision D35) and will be unified only after
the paper-trading ledger can score each on real data — not by guessing.

NOTE: ``_get_recommendation_for_stock`` still raises ``HTTPException`` (an HTTP-layer
concern) for the insufficient-data case; that is preserved verbatim on purpose.
"""
from datetime import datetime, timedelta, timezone
import logging

import pandas as pd
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.stock import Stock
from app.schemas.analysis import RecommendationResponse
from app.services.technical_indicators import TechnicalIndicators
from app.services.signal.swing import signal_swing

logger = logging.getLogger(__name__)


def _get_recommendation_for_stock(stock: Stock, db: Session) -> RecommendationResponse:
    """
    Reusable function to get a comprehensive recommendation for a single stock.

    DB→DataFrame adapter: assembles the indicator frame + pre-time-filtered
    component data, delegates the swing scoring to the pure ``signal_swing``, and
    maps the result onto ``RecommendationResponse``.

    NOTE: When called from the dashboard endpoint, stock.prices/predictions/etc
    are already loaded (avoids re-querying).
    """
    # ── price data (use already-loaded relationship if available) ────────
    # CRITICAL FOR SWING TRADING: absolute latest INTRADAY price (not aggregated weekly/monthly).
    intraday_prices = [p for p in stock.prices if p.timeframe in ['1m', '5m', '15m', '1h', '1d']] if stock.prices else []
    latest_price_any_timeframe = max(intraday_prices, key=lambda p: p.timestamp) if intraday_prices else None

    # For technical analysis, filter to daily (1d) prices OR fall back to all if insufficient daily data
    daily_prices = [p for p in stock.prices if p.timeframe == '1d'] if stock.prices else []
    if len(daily_prices) >= 50:
        prices = sorted(daily_prices, key=lambda p: p.timestamp)
    else:
        prices = sorted(stock.prices, key=lambda p: p.timestamp) if stock.prices else []

    if not prices or len(prices) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient price data for analysis. Have {len(prices)}, need at least 50 daily bars for technical indicators."
        )

    # ── indicators: cached (fast) or compute on-the-fly (slow) ───────────
    from app.services.indicator_cache_service import IndicatorCacheService
    cached_data = IndicatorCacheService.get_cached_indicators(db, stock.id, timeframe='1d')

    if cached_data:
        logger.debug(f"Cache HIT for stock_id={stock.id} ({stock.symbol}) - using cached indicators")
        tech_recommendation = {
            'indicators': cached_data['indicators'],
            'recommendation': cached_data['recommendation'],
            'confidence': cached_data['confidence'] if cached_data['confidence'] else 0.5,
            'reason': cached_data['reasoning'] if cached_data['reasoning'] else 'Technical analysis',
            'signals': cached_data['signals'] if cached_data['signals'] else {'buy': 0, 'sell': 0, 'hold': 0}
        }

        df = pd.DataFrame([{
            'timestamp': p.timestamp,
            'open': float(p.open),
            'high': float(p.high),
            'low': float(p.low),
            'close': float(p.close),
            'volume': int(p.volume)
        } for p in prices])
        df.set_index('timestamp', inplace=True)

        # Add cached indicator values to the last row (for swing context + filtering)
        indicator_cols = {indicator_name: [None] * (len(df) - 1) + [indicator_value]
                          for indicator_name, indicator_value in cached_data['indicators'].items()}
        indicator_df = pd.DataFrame(indicator_cols, index=df.index)
        df = pd.concat([df, indicator_df], axis=1)
    else:
        logger.warning(f"Cache MISS for stock_id={stock.id} ({stock.symbol}) - calculating indicators on-the-fly")
        df = pd.DataFrame([{'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'close': float(p.close), 'volume': int(p.volume)} for p in prices])
        df.set_index('timestamp', inplace=True)
        df = TechnicalIndicators.calculate_all_indicators(df)
        tech_recommendation = TechnicalIndicators.generate_recommendation(df)

    current_price = float(df.iloc[-1]['close'])

    # ── ML prediction (use already-loaded relationship if available) ─────
    latest_prediction = max(stock.predictions, key=lambda p: p.created_at, default=None) if stock.predictions else None
    if latest_prediction and latest_prediction.confidence_score:
        ml = (latest_prediction.recommendation,
              float(latest_prediction.confidence_score),
              float(latest_prediction.predicted_price))
    else:
        ml = (None, None, None)

    # ── sentiment: pre-filter news (30d, has score) -> list of scores ────
    # (Polygon per-ticker insights written to the `news` table by fetcher_tasks.
    #  Replaces the dead `sentiment_scores` read — user-reported issue #4.)
    sentiment_scores = []
    if stock.news:
        news_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent_news = [
            n for n in stock.news
            if n.sentiment_score is not None
            and n.published_utc is not None
            and n.published_utc >= news_cutoff
        ]
        if recent_news:
            # Newest-first, cap at 20 (match Engine #1's window)
            recent_news = sorted(recent_news, key=lambda n: n.published_utc, reverse=True)[:20]
            sentiment_scores = [float(n.sentiment_score) for n in recent_news]

    # ── candlestick patterns: time-filter to last 30d -> dicts ───────────
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    candlestick_patterns_raw = [
        {
            'pattern_name': p.pattern_name,
            'pattern_type': p.pattern_type,
            'timestamp': p.timestamp,
            'confidence_score': p.confidence_score,
        }
        for p in stock.candlestick_patterns
        if p.timestamp >= thirty_days_ago
    ] if stock.candlestick_patterns else []

    # ── chart patterns: time-filter to last 90d -> dicts ─────────────────
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
    chart_patterns_raw = [
        {
            'signal': p.signal,
            'confidence_score': p.confidence_score,
            'start_date': p.start_date,
            'end_date': p.end_date,
        }
        for p in stock.chart_patterns
        if p.end_date >= ninety_days_ago
    ] if stock.chart_patterns else []

    # ── dividend & split signal (DividendSplitDetector is DB-bound) ──────
    dividend_split_signal = None
    try:
        from app.services.dividend_split_detector import DividendSplitDetector
        detector = DividendSplitDetector()
        signal = detector.get_signals_for_recommendation(stock.id, db, days_ahead=30)
        if signal['has_signal']:
            dividend_split_signal = signal
    except Exception as e:
        logger.warning(f"Dividend/split signal detection failed for stock {stock.id}: {e}")

    # ============================================
    # PURE SIGNAL (no DB access below this point)
    # ============================================
    result_signal = signal_swing(
        df=df,
        tech_recommendation=tech_recommendation,
        chart_patterns_raw=chart_patterns_raw,
        candlestick_patterns_raw=candlestick_patterns_raw,
        sentiment_scores=sentiment_scores,
        ml=ml,
        dividend_split_signal=dividend_split_signal,
    )

    # ── latest price across all timeframes (trader-facing current price) ─
    if latest_price_any_timeframe:
        actual_current_price = float(latest_price_any_timeframe.close)
        actual_timestamp = latest_price_any_timeframe.timestamp
        logger.info(f"{stock.symbol}: Using latest {latest_price_any_timeframe.timeframe} price ${actual_current_price:.2f} from {actual_timestamp}")
    else:
        actual_current_price = current_price
        actual_timestamp = df.index[-1]
        logger.warning(f"{stock.symbol}: No latest price found, using DataFrame last price ${actual_current_price:.2f}")

    ex = result_signal.extras or {}
    return RecommendationResponse(
        stock_id=stock.id,
        symbol=stock.symbol,
        name=stock.name,
        sector=stock.sector,
        industry=stock.industry,
        priority=stock.priority,
        priority_score=float(stock.priority_score) if stock.priority_score else None,
        last_fetch_at=stock.last_fetch_at,
        next_fetch_at=stock.next_fetch_at,
        current_price=actual_current_price,
        timestamp=actual_timestamp,
        technical_recommendation=ex.get('technical_recommendation'),
        technical_confidence=ex.get('technical_confidence'),
        technical_signals=ex.get('technical_signals'),
        ml_recommendation=ex.get('ml_recommendation'),
        ml_confidence=ex.get('ml_confidence'),
        predicted_price=ex.get('predicted_price'),
        sentiment_index=ex.get('sentiment_index'),
        sentiment_positive=ex.get('sentiment_positive'),
        sentiment_negative=ex.get('sentiment_negative'),
        candlestick_signal=ex.get('candlestick_signal'),
        candlestick_confidence=ex.get('candlestick_confidence'),
        candlestick_pattern_count=ex.get('candlestick_pattern_count'),
        chart_pattern_signal=ex.get('chart_pattern_signal'),
        chart_pattern_confidence=ex.get('chart_pattern_confidence'),
        chart_pattern_count=ex.get('chart_pattern_count'),
        dividend_split_signal=dividend_split_signal,
        final_recommendation=result_signal.signal,
        overall_confidence=result_signal.confidence,
        reasoning=result_signal.reasoning,
        risk_level=ex.get('risk_level'),
        analysis_score=float(stock.analysis_score) if stock.analysis_score else 0.0,
        analysis_complete=stock.analysis_complete
    )
