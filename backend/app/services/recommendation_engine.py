"""
Recommendation Engine Service — Engine #1 (systematic) DB→DataFrame adapter.

Thin adapter over the pure signal function
:func:`app.services.signal.systematic.signal_systematic`. This module owns all
database access and maps the resulting :class:`SignalResult` back to the legacy
dict shape that callers (``analysis_tasks.analyze_stock_comprehensive``) expect.

The scoring logic itself — the 6-factor weighted score — lives in the pure
``signal.systematic`` module so the paper-trading ledger (Phase 1) and backtester
(Phase 2) call exactly what the live engine produces, with no DB coupling.

Kept deliberately separate from ``realtime_recommendation`` (Engine #2, swing):
the two are an **A/B pair** (decision D35) and will be unified only after the
paper-trading ledger can score each on real data — not by guessing.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def generate_final_recommendation(db: Session, stock_id: int) -> dict:
    """
    Generate final trading recommendation based on all analysis factors (Engine #1).

    DB→DataFrame adapter: fetches the 6 component inputs, delegates the scoring to
    the pure ``signal_systematic``, and maps the result to the legacy dict shape.

    Args:
        db: Database session
        stock_id: Stock ID

    Returns:
        dict with final_recommendation, overall_confidence, weighted_score,
        component_scores, technical_recommendation, ml_recommendation,
        sentiment_index, status, dividend_split_signal.
    """
    from app.models.stock import Stock, ChartPattern, CandlestickPattern, StockPrice
    from app.models.news import News
    from app.services.market_regime import MarketRegimeService
    from app.services.dividend_split_detector import DividendSplitDetector
    from app.services.signal.systematic import signal_systematic
    import pandas as pd

    try:
        # Get stock info
        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            return {
                'final_recommendation': 'HOLD',
                'overall_confidence': 0.0,
                'status': 'error',
                'message': 'Stock not found'
            }

        # ============================================
        # FETCH all 6 component inputs (DB → plain data)
        # Each fetch is independent + fault-tolerant: a failure leaves that
        # component at its default (empty/None/0.0), matching the original
        # per-component try/except behavior (score stays 0 on failure).
        # ============================================

        # 1. CHART PATTERNS (last 30 days) -> list of dicts
        chart_patterns = []
        try:
            recent_patterns = db.query(ChartPattern).filter(
                ChartPattern.stock_id == stock_id,
                ChartPattern.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
            ).all()
            chart_patterns = [
                {
                    'signal': p.signal,
                    'confidence_score': p.confidence_score,
                    'confirmation_level': p.confirmation_level,
                }
                for p in recent_patterns
            ]
        except Exception as e:
            logger.warning(f"Chart pattern fetch failed: {e}")

        # 2. CANDLESTICK PATTERNS (last 7 days) -> list of dicts
        candlestick_patterns = []
        try:
            recent_cs = db.query(CandlestickPattern).filter(
                CandlestickPattern.stock_id == stock_id,
                CandlestickPattern.timestamp >= datetime.now(timezone.utc) - timedelta(days=7)
            ).all()
            candlestick_patterns = [
                {
                    'pattern_type': p.pattern_type,
                    'confidence_score': p.confidence_score,
                }
                for p in recent_cs
            ]
        except Exception as e:
            logger.warning(f"Candlestick pattern fetch failed: {e}")

        # 3. PRICE DATA (last 60 daily bars) -> DataFrame (timestamp column, chronological)
        df_prices = pd.DataFrame()
        try:
            prices = db.query(StockPrice).filter(
                StockPrice.stock_id == stock_id
            ).order_by(StockPrice.timestamp.desc()).limit(60).all()

            if prices:
                df_prices = pd.DataFrame([{
                    'timestamp': p.timestamp,
                    'open': float(p.open),
                    'high': float(p.high),
                    'low': float(p.low),
                    'close': float(p.close),
                    'volume': int(p.volume)
                } for p in reversed(prices)])  # Reverse to chronological order
        except Exception as e:
            logger.warning(f"Price fetch failed: {e}")

        # 4. SENTIMENT (avg of last 20 news articles with a sentiment score) -> float|None
        sentiment_score = None
        try:
            recent_news = db.query(News).filter(
                News.stock_id == stock_id,
                News.sentiment_score.isnot(None)
            ).order_by(News.published_utc.desc()).limit(20).all()

            if recent_news:
                sentiment_score = sum(
                    float(article.sentiment_score) for article in recent_news
                ) / len(recent_news)
        except Exception as e:
            logger.warning(f"Sentiment fetch failed: {e}")

        # 5. MARKET REGIME (MarketRegimeService is DB-bound) -> regime label str
        #    + directional regime (Phase 2.5: feeds the regime de-risk overlay;
        #    inert in live — overlay_strength stays 0 — but promote-ready).
        regime = 'unknown'
        regime_direction = None
        try:
            regime_service = MarketRegimeService(db)
            regime_result = regime_service.detect_market_regime(stock_id)
            regime = regime_result.get('regime', 'unknown')
            regime_direction = regime_result.get('direction')
        except Exception as e:
            logger.warning(f"Market regime detection failed: {e}")

        # 6. DIVIDEND & SPLIT SIGNAL (DividendSplitDetector is DB-bound) -> dict|None
        dividend_split_signal = None
        try:
            detector = DividendSplitDetector()
            signal = detector.get_signals_for_recommendation(stock_id, db, days_ahead=30)

            if signal['has_signal']:
                dividend_split_signal = signal
        except Exception as e:
            logger.warning(f"Dividend/split signal detection failed: {e}")

        # ============================================
        # PURE SIGNAL (no DB access below this point)
        # ============================================
        result_signal = signal_systematic(
            df_prices=df_prices,
            chart_patterns=chart_patterns,
            candlestick_patterns=candlestick_patterns,
            sentiment_score=sentiment_score,
            regime=regime,
            dividend_split_signal=dividend_split_signal,
            regime_direction=regime_direction,
        )

        # ============================================
        # MAP SignalResult -> legacy dict shape (rounding matches the original)
        # ============================================
        result = {
            'final_recommendation': result_signal.signal,
            'overall_confidence': round(float(result_signal.confidence), 4),
            'weighted_score': round(float(result_signal.weighted_score), 4),
            'component_scores': {k: round(float(v), 4) for k, v in result_signal.component_scores.items()},
            'technical_recommendation': result_signal.signal,  # For compatibility
            'ml_recommendation': None,  # Placeholder for future ML model
            'sentiment_index': result_signal.component_scores.get('sentiment', 0.0),
            'status': 'success'
        }

        # Add dividend/split signal details if present
        if dividend_split_signal:
            result['dividend_split_signal'] = {
                'signal_type': dividend_split_signal['signal_type'],
                'signal_strength': dividend_split_signal['signal_strength'],
                'reasoning': dividend_split_signal['reasoning'],
                'event_date': dividend_split_signal['event_date'],
                'days_until': dividend_split_signal['days_until'],
                'details': dividend_split_signal['details']
            }
        else:
            result['dividend_split_signal'] = None

        return result

    except Exception as e:
        logger.error(f"Error generating recommendation for stock {stock_id}: {e}")
        return {
            'final_recommendation': 'HOLD',
            'overall_confidence': 0.0,
            'technical_recommendation': 'HOLD',
            'ml_recommendation': None,
            'sentiment_index': 0.0,
            'status': 'error',
            'message': str(e)
        }
