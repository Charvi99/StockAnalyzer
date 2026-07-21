"""
Recommendation Engine Service

Generates final BUY/SELL/HOLD recommendations based on all analysis factors
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)


def generate_final_recommendation(db: Session, stock_id: int) -> dict:
    """
    Generate final trading recommendation based on all analysis factors

    Combines:
    - Chart patterns (weight: 28%)
    - Candlestick patterns (weight: 14%)
    - Technical indicators (weight: 23%)
    - Sentiment (weight: 13%)
    - Market regime (weight: 12%)
    - Dividend/Split signals (weight: 10%)

    Args:
        db: Database session
        stock_id: Stock ID

    Returns:
        dict with final_recommendation, overall_confidence, and component scores
    """
    from app.models.stock import Stock, ChartPattern, CandlestickPattern
    from app.services.technical_indicators import TechnicalIndicators
    # from app.services.sentiment_service import SentimentService  # REMOVED: Now using Polygon API sentiment
    from app.services.market_regime import MarketRegimeService
    from app.services.dividend_split_detector import DividendSplitDetector
    from app.models.news import News
    import os

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

        scores = {
            'chart_patterns': 0.0,
            'candlestick_patterns': 0.0,
            'technical_indicators': 0.0,
            'sentiment': 0.0,
            'market_regime': 0.0,
            'dividend_split_signals': 0.0
        }

        # Store dividend/split signal details for response
        dividend_split_signal = None

        # ============================================
        # 1. CHART PATTERNS (30% weight)
        # ============================================
        try:
            recent_patterns = db.query(ChartPattern).filter(
                ChartPattern.stock_id == stock_id,
                ChartPattern.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
            ).all()

            if recent_patterns:
                bullish_count = sum(1 for p in recent_patterns if p.signal == 'bullish')
                bearish_count = sum(1 for p in recent_patterns if p.signal == 'bearish')

                # Weight by confidence and multi-timeframe confirmation
                bullish_score = sum(
                    float(p.confidence_score) * (1 + float(p.confirmation_level or 0) * 0.2)
                    for p in recent_patterns if p.signal == 'bullish'
                )
                bearish_score = sum(
                    float(p.confidence_score) * (1 + float(p.confirmation_level or 0) * 0.2)
                    for p in recent_patterns if p.signal == 'bearish'
                )

                if bullish_count + bearish_count > 0:
                    scores['chart_patterns'] = (bullish_score - bearish_score) / (bullish_count + bearish_count)
                    scores['chart_patterns'] = max(-1.0, min(1.0, scores['chart_patterns']))

        except Exception as e:
            logger.warning(f"Chart pattern scoring failed: {e}")

        # ============================================
        # 2. CANDLESTICK PATTERNS (15% weight)
        # ============================================
        try:
            recent_cs = db.query(CandlestickPattern).filter(
                CandlestickPattern.stock_id == stock_id,
                CandlestickPattern.timestamp >= datetime.now(timezone.utc) - timedelta(days=7)
            ).all()

            if recent_cs:
                bullish_cs = sum(float(p.confidence_score) for p in recent_cs if p.pattern_type == 'bullish')
                bearish_cs = sum(float(p.confidence_score) for p in recent_cs if p.pattern_type == 'bearish')

                total_cs = bullish_cs + bearish_cs
                if total_cs > 0:
                    scores['candlestick_patterns'] = (bullish_cs - bearish_cs) / total_cs
                    scores['candlestick_patterns'] = max(-1.0, min(1.0, scores['candlestick_patterns']))

        except Exception as e:
            logger.warning(f"Candlestick pattern scoring failed: {e}")

        # ============================================
        # 3. TECHNICAL INDICATORS (25% weight)
        # ============================================
        try:
            from app.models.stock import StockPrice
            import pandas as pd

            # Fetch price data for technical indicators
            prices = db.query(StockPrice).filter(
                StockPrice.stock_id == stock_id
            ).order_by(StockPrice.timestamp.desc()).limit(60).all()

            if not prices:
                logger.warning(f"No price data for stock {stock_id}, skipping technical indicators")
                indicators = None
            else:
                # Create DataFrame
                df = pd.DataFrame([{
                    'timestamp': p.timestamp,
                    'open': float(p.open),
                    'high': float(p.high),
                    'low': float(p.low),
                    'close': float(p.close),
                    'volume': int(p.volume)
                } for p in reversed(prices)])

                # Calculate all indicators (static method)
                indicators = TechnicalIndicators.calculate_all_indicators(df)

            if indicators is not None and not indicators.empty:
                # Advanced scoring with Phase 1 + Phase 2 indicators
                tech_score = 0.0
                indicator_count = 0

                # PHASE 1 INDICATORS
                # NOTE: `indicators` is a DataFrame (calculate_all_indicators returns
                # pd.DataFrame). Values must be read via .iloc[-1], NOT dict-style
                # ['value'] — the old access raised KeyError and was silently swallowed
                # by the except below, so RSI/MACD/SMA never contributed. (BU1 audit)

                # RSI
                if 'rsi' in indicators.columns:
                    rsi = indicators['rsi'].iloc[-1]
                    if pd.notna(rsi):
                        if rsi < 30:
                            tech_score += 1.0  # Oversold - bullish
                        elif rsi > 70:
                            tech_score -= 1.0  # Overbought - bearish
                        indicator_count += 1

                # MACD — 'macd_trend' is the bullish/bearish signal column
                # (do NOT confuse with 'macd_signal', which is the signal LINE)
                if 'macd_trend' in indicators.columns:
                    macd_signal = indicators['macd_trend'].iloc[-1]
                    if pd.notna(macd_signal):
                        if macd_signal == 'bullish':
                            tech_score += 1.0
                        elif macd_signal == 'bearish':
                            tech_score -= 1.0
                        indicator_count += 1

                # Moving Average Trend (golden / death cross)
                if 'sma_50' in indicators.columns and 'sma_200' in indicators.columns:
                    sma_50 = indicators['sma_50'].iloc[-1]
                    sma_200 = indicators['sma_200'].iloc[-1]
                    if pd.notna(sma_50) and pd.notna(sma_200):
                        if sma_50 > sma_200:
                            tech_score += 0.5  # Golden cross zone
                        else:
                            tech_score -= 0.5  # Death cross zone
                        indicator_count += 1

                # PHASE 2 & PHASE 3 NEW INDICATORS - Weighted by category

                # Check market regime first (PHASE 3B: HT_TRENDMODE)
                market_regime = 'TREND'  # Default
                if 'ht_trendmode' in indicators.columns:
                    regime_mode = indicators['ht_trendmode'].iloc[-1]
                    market_regime = 'TREND' if regime_mode == 1 else 'CYCLE'

                # Advanced Trend Indicators (Higher weight for trend confirmation)
                # PHASE 2: KAMA, TEMA, T3, HT_Trendline
                # PHASE 3A: AROON, TRIX
                # PHASE 3B: MAMA, APO, PPO
                trend_signals = []
                if 'kama_signal' in indicators.columns:
                    trend_signals.append(indicators['kama_signal'].iloc[-1])
                if 'tema_signal' in indicators.columns:
                    trend_signals.append(indicators['tema_signal'].iloc[-1])
                if 't3_signal' in indicators.columns:
                    trend_signals.append(indicators['t3_signal'].iloc[-1])
                if 'ht_signal' in indicators.columns:
                    trend_signals.append(indicators['ht_signal'].iloc[-1])
                # PHASE 3A
                if 'aroon_signal' in indicators.columns:
                    trend_signals.append(indicators['aroon_signal'].iloc[-1])
                if 'trix_signal' in indicators.columns:
                    trend_signals.append(indicators['trix_signal'].iloc[-1])
                # PHASE 3B
                if 'mama_signal' in indicators.columns:
                    trend_signals.append(indicators['mama_signal'].iloc[-1])
                if 'apo_signal' in indicators.columns:
                    trend_signals.append(indicators['apo_signal'].iloc[-1])
                if 'ppo_signal' in indicators.columns:
                    trend_signals.append(indicators['ppo_signal'].iloc[-1])

                if trend_signals:
                    buy_count = sum(1 for s in trend_signals if s == 'BUY')
                    sell_count = sum(1 for s in trend_signals if s == 'SELL')
                    if buy_count + sell_count > 0:
                        # Trend confirmation bonus: if 4+ agree, add extra weight
                        trend_score = (buy_count - sell_count) / len(trend_signals)
                        if buy_count >= 4 or sell_count >= 4:
                            trend_score *= 1.8  # Very strong trend consensus (Phase 3 upgrade: 1.5 -> 1.8)

                        # Market regime adjustment: reduce trend weight in cycling markets
                        if market_regime == 'CYCLE':
                            trend_score *= 0.5  # Half weight for trend indicators in cycling markets

                        tech_score += trend_score
                        indicator_count += 1

                # Advanced Momentum Indicators
                # PHASE 2: MFI, Williams %R, ROC, CMO
                # PHASE 3A: StochRSI, ULTOSC, BOP
                # PHASE 3B: ADOSC
                momentum_signals = []
                if 'mfi_signal' in indicators.columns:
                    momentum_signals.append(indicators['mfi_signal'].iloc[-1])
                if 'willr_signal' in indicators.columns:
                    momentum_signals.append(indicators['willr_signal'].iloc[-1])
                if 'roc_signal' in indicators.columns:
                    momentum_signals.append(indicators['roc_signal'].iloc[-1])
                if 'cmo_signal' in indicators.columns:
                    momentum_signals.append(indicators['cmo_signal'].iloc[-1])
                # PHASE 3A
                if 'stochrsi_signal' in indicators.columns:
                    momentum_signals.append(indicators['stochrsi_signal'].iloc[-1])
                if 'ultosc_signal' in indicators.columns:
                    momentum_signals.append(indicators['ultosc_signal'].iloc[-1])
                if 'bop_signal' in indicators.columns:
                    momentum_signals.append(indicators['bop_signal'].iloc[-1])
                # PHASE 3B
                if 'adosc_signal' in indicators.columns:
                    momentum_signals.append(indicators['adosc_signal'].iloc[-1])

                if momentum_signals:
                    buy_count = sum(1 for s in momentum_signals if s == 'BUY')
                    sell_count = sum(1 for s in momentum_signals if s == 'SELL')
                    if buy_count + sell_count > 0:
                        # Momentum confirmation bonus
                        momentum_score = (buy_count - sell_count) / len(momentum_signals)
                        if buy_count >= 4 or sell_count >= 4:
                            momentum_score *= 1.5  # Strong momentum consensus (Phase 3 upgrade: 1.3 -> 1.5)

                        # Market regime adjustment: increase momentum weight in cycling markets
                        if market_regime == 'CYCLE':
                            momentum_score *= 1.5  # Higher weight for momentum in cycling markets

                        tech_score += momentum_score * 0.8  # Slightly lower weight than trend
                        indicator_count += 1

                # Linear Regression Slope (Trend strength)
                if 'linearreg_signal' in indicators.columns:
                    lr_signal = indicators['linearreg_signal'].iloc[-1]
                    if lr_signal == 'BUY':
                        tech_score += 0.7
                    elif lr_signal == 'SELL':
                        tech_score -= 0.7
                    indicator_count += 1

                if indicator_count > 0:
                    scores['technical_indicators'] = tech_score / indicator_count
                    scores['technical_indicators'] = max(-1.0, min(1.0, scores['technical_indicators']))

        except Exception as e:
            logger.warning(f"Technical indicator scoring failed: {e}")

        # ============================================
        # 4. SENTIMENT (15% weight)
        # ============================================
        # Now using Polygon API sentiment stored in news table
        try:
            # Get recent news sentiment (last 20 articles)
            recent_news = db.query(News).filter(
                News.stock_id == stock_id,
                News.sentiment_score.isnot(None)
            ).order_by(News.published_utc.desc()).limit(20).all()

            if recent_news:
                # Calculate average sentiment score from news articles
                avg_sentiment = sum(float(article.sentiment_score) for article in recent_news) / len(recent_news)
                scores['sentiment'] = avg_sentiment  # Already in -1.0 to 1.0 range

        except Exception as e:
            logger.warning(f"Sentiment scoring failed: {e}")

        # ============================================
        # 5. MARKET REGIME (15% weight)
        # ============================================
        try:
            regime_service = MarketRegimeService(db)
            regime_result = regime_service.detect_market_regime(stock_id)
            regime = regime_result.get('regime', 'unknown')

            # Map regime to score (-1 to 1)
            regime_scores = {
                'trending_up': 0.8,
                'trend': 0.6,  # Generic trend (positive)
                'accumulation': 0.5,
                'ranging': 0.0,
                'distribution': -0.5,
                'trending_down': -0.8,
                'volatile': -0.3
            }
            scores['market_regime'] = regime_scores.get(regime, 0.0)

        except Exception as e:
            logger.warning(f"Market regime scoring failed: {e}")

        # ============================================
        # 6. DIVIDEND & SPLIT SIGNALS (10% weight)
        # ============================================
        try:
            detector = DividendSplitDetector()
            signal = detector.get_signals_for_recommendation(stock_id, db, days_ahead=30)

            if signal['has_signal']:
                dividend_split_signal = signal

                # Convert score_adjustment (-20 to +20) to normalized score (-1.0 to +1.0)
                scores['dividend_split_signals'] = signal['score_adjustment'] / 20.0
                scores['dividend_split_signals'] = max(-1.0, min(1.0, scores['dividend_split_signals']))

                logger.info(f"Dividend/split signal for stock {stock_id}: {signal['signal_type']} "
                           f"(adjustment: {signal['score_adjustment']})")

        except Exception as e:
            logger.warning(f"Dividend/split signal detection failed: {e}")

        # ============================================
        # CALCULATE FINAL RECOMMENDATION
        # ============================================
        weights = {
            'chart_patterns': 0.28,
            'candlestick_patterns': 0.14,
            'technical_indicators': 0.23,
            'sentiment': 0.13,
            'market_regime': 0.12,
            'dividend_split_signals': 0.10
        }

        weighted_score = sum(scores[key] * weights[key] for key in scores.keys())

        # Determine recommendation
        if weighted_score > 0.3:
            final_recommendation = 'BUY'
            overall_confidence = min(abs(weighted_score), 1.0)
        elif weighted_score < -0.3:
            final_recommendation = 'SELL'
            overall_confidence = min(abs(weighted_score), 1.0)
        else:
            final_recommendation = 'HOLD'
            overall_confidence = 0.5  # Moderate confidence in HOLD

        result = {
            'final_recommendation': final_recommendation,
            'overall_confidence': round(float(overall_confidence), 4),
            'weighted_score': round(float(weighted_score), 4),
            'component_scores': {k: round(float(v), 4) for k, v in scores.items()},
            'technical_recommendation': final_recommendation,  # For compatibility
            'ml_recommendation': None,  # Placeholder for future ML model
            'sentiment_index': scores.get('sentiment', 0.0),
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
