"""
Analysis orchestration tasks

These tasks run comprehensive analysis after price data updates:
- Chart pattern detection
- Candlestick pattern detection
- Technical indicators calculation
- Sentiment analysis
- Market regime detection
- Final recommendation generation
"""
from app.celery_app import celery_app
from datetime import datetime, timezone
import logging
from app.services.analysis_completeness import AnalysisCompletenessService
from app.config.pattern_thresholds import swing_detector_kwargs, swing_detect_kwargs

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300, time_limit=360)
def analyze_stock_comprehensive(self, stock_id: int, symbol: str):
    """
    Run comprehensive analysis for a single stock after data update

    This is the main orchestration task that coordinates all analysis steps:
    1. Chart patterns (multi-timeframe)
    2. Candlestick patterns
    3. Technical indicators
    4. Sentiment from news
    5. Market regime detection
    6. Final recommendation

    Args:
        stock_id: Stock database ID
        symbol: Stock ticker symbol

    Returns:
        dict with analysis results and status
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock
    from app.services.multi_timeframe_patterns import MultiTimeframePatternDetector
    from app.services.candlestick_patterns import CandlestickPatternDetector
    from app.services.technical_indicators import TechnicalIndicators
    # from app.services.sentiment_service import SentimentService  # REMOVED: Now using Polygon API sentiment
    from app.services.market_regime import MarketRegimeService
    from app.services.recommendation_engine import generate_final_recommendation
    from sqlalchemy import and_

    logger.info(f"🔬 Starting comprehensive analysis for {symbol} (ID: {stock_id})")

    db = SessionLocal()
    analysis_results = {
        'stock_id': stock_id,
        'symbol': symbol,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'steps': {}
    }

    try:
        # Verify stock exists
        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            logger.error(f"Stock {symbol} (ID: {stock_id}) not found")
            return {'status': 'error', 'message': 'Stock not found'}

        # ============================================
        # STEP 1: CHART PATTERNS (Multi-Timeframe)
        # ============================================
        try:
            logger.info(f"📊 {symbol}: Detecting chart patterns...")
            from app.models.stock import ChartPattern

            detector = MultiTimeframePatternDetector(
                db=db,
                stock_id=stock_id,
                **swing_detector_kwargs()
            )

            result = detector.detect_all_patterns(
                **swing_detect_kwargs()
            )

            detected_patterns = result['patterns']

            # Save new patterns
            saved_count = 0
            for pattern in detected_patterns:
                existing = db.query(ChartPattern).filter(
                    and_(
                        ChartPattern.stock_id == stock_id,
                        ChartPattern.pattern_name == pattern['pattern_name'],
                        ChartPattern.end_date == pattern['end_date']
                    )
                ).first()

                if not existing:
                    db_pattern = ChartPattern(
                        stock_id=stock_id,
                        pattern_name=pattern['pattern_name'],
                        pattern_type=pattern['pattern_type'],
                        signal=pattern['signal'],
                        start_date=pattern['start_date'],
                        end_date=pattern['end_date'],
                        breakout_price=pattern.get('breakout_price'),
                        target_price=pattern.get('target_price'),
                        stop_loss=pattern.get('stop_loss'),
                        confidence_score=pattern['confidence_score'],
                        key_points=pattern['key_points'],
                        trendlines=pattern['trendlines'],
                        primary_timeframe=pattern.get('primary_timeframe', '1d'),
                        detected_on_timeframes=pattern.get('detected_on_timeframes', ['1d']),
                        confirmation_level=pattern.get('confirmation_level', 1),
                        base_confidence=pattern.get('base_confidence'),
                        alignment_score=pattern.get('alignment_score')
                    )
                    db.add(db_pattern)
                    saved_count += 1

            db.commit()

            # Update timestamp for chart pattern detection
            stock.last_chart_pattern_detection = datetime.now(timezone.utc)
            db.commit()

            analysis_results['steps']['chart_patterns'] = {
                'status': 'success',
                'total_detected': len(detected_patterns),
                'new_saved': saved_count,
                'multi_timeframe_confirmed': sum(1 for p in detected_patterns if p.get('is_multi_timeframe_confirmed', False))
            }
            logger.info(f"✅ {symbol}: Chart patterns - {len(detected_patterns)} detected, {saved_count} new")

        except Exception as e:
            logger.error(f"❌ {symbol}: Chart pattern detection failed: {e}")
            analysis_results['steps']['chart_patterns'] = {'status': 'error', 'message': str(e)}
            db.rollback()

        # ============================================
        # STEP 2: CANDLESTICK PATTERNS
        # ============================================
        try:
            logger.info(f"🕯️ {symbol}: Detecting candlestick patterns...")
            from app.models.stock import CandlestickPattern, StockPrice
            import pandas as pd

            # Fetch price data for last 30 days
            prices = db.query(StockPrice).filter(
                StockPrice.stock_id == stock_id
            ).order_by(StockPrice.timestamp.desc()).limit(30).all()

            if not prices:
                raise ValueError(f"No price data available for {symbol}")

            # Create DataFrame for CandlestickPatternDetector
            df = pd.DataFrame([{
                'timestamp': p.timestamp,
                'open': float(p.open),
                'high': float(p.high),
                'low': float(p.low),
                'close': float(p.close),
                'volume': int(p.volume)
            } for p in reversed(prices)])  # Reverse to chronological order

            cs_detector = CandlestickPatternDetector(df)
            cs_patterns = cs_detector.detect_all_patterns()  # No days parameter

            # Save candlestick patterns
            saved_cs_count = 0
            for pattern in cs_patterns:
                existing = db.query(CandlestickPattern).filter(
                    and_(
                        CandlestickPattern.stock_id == stock_id,
                        CandlestickPattern.pattern_name == pattern['pattern_name'],
                        CandlestickPattern.timestamp == pattern['timestamp']
                    )
                ).first()

                if not existing:
                    db_cs_pattern = CandlestickPattern(
                        stock_id=stock_id,
                        pattern_name=pattern['pattern_name'],
                        pattern_type=pattern['pattern_type'],
                        timestamp=pattern['timestamp'],
                        confidence_score=pattern['confidence_score'],
                        candle_data=pattern.get('candle_data')
                    )
                    db.add(db_cs_pattern)
                    saved_cs_count += 1

            db.commit()

            # Update timestamp for candlestick pattern detection
            stock.last_candlestick_detection = datetime.now(timezone.utc)
            db.commit()

            analysis_results['steps']['candlestick_patterns'] = {
                'status': 'success',
                'total_detected': len(cs_patterns),
                'new_saved': saved_cs_count
            }
            logger.info(f"✅ {symbol}: Candlestick patterns - {len(cs_patterns)} detected, {saved_cs_count} new")

        except Exception as e:
            logger.error(f"❌ {symbol}: Candlestick pattern detection failed: {e}")
            analysis_results['steps']['candlestick_patterns'] = {'status': 'error', 'message': str(e)}
            db.rollback()

        # ============================================
        # STEP 3: TECHNICAL INDICATORS
        # ============================================
        try:
            logger.info(f"📈 {symbol}: Calculating technical indicators...")
            from app.models.stock import StockPrice
            import pandas as pd

            # Fetch price data for last 90 days for technical indicators (daily bars
            # only — without the timeframe filter this mixed 1h/4h/1d/1w rows, since
            # stock_prices holds every timeframe).
            prices = db.query(StockPrice).filter(
                StockPrice.stock_id == stock_id,
                StockPrice.timeframe == '1d'
            ).order_by(StockPrice.timestamp.desc()).limit(90).all()

            if not prices:
                raise ValueError(f"No price data available for {symbol}")

            # Create DataFrame for TechnicalIndicators
            df = pd.DataFrame([{
                'timestamp': p.timestamp,
                'open': float(p.open),
                'high': float(p.high),
                'low': float(p.low),
                'close': float(p.close),
                'volume': int(p.volume)
            } for p in reversed(prices)])  # Reverse to chronological order

            # Calculate all indicators (static method)
            indicators = TechnicalIndicators.calculate_all_indicators(df)

            # Update timestamp for technical analysis
            stock.last_technical_analysis = datetime.now(timezone.utc)
            db.commit()

            analysis_results['steps']['technical_indicators'] = {
                'status': 'success',
                'indicators_calculated': len(indicators) if not indicators.empty else 0
            }
            logger.info(f"✅ {symbol}: Technical indicators calculated")

        except Exception as e:
            logger.error(f"❌ {symbol}: Technical indicator calculation failed: {e}")
            analysis_results['steps']['technical_indicators'] = {'status': 'error', 'message': str(e)}

        # ============================================
        # STEP 4: SENTIMENT ANALYSIS
        # ============================================
        # REMOVED: Sentiment is now automatically extracted from Polygon API during news fetching
        # See fetcher_tasks.py for sentiment extraction from article insights
        # The news table now stores sentiment, sentiment_score, and sentiment_reasoning
        logger.info(f"💭 {symbol}: Sentiment analysis skipped - handled during news fetch")
        analysis_results['steps']['sentiment'] = {
            'status': 'success',
            'sentiment_index': 0,  # Not calculated here anymore
            'news_analyzed': 0,
            'note': 'Sentiment extracted from Polygon API during news fetch'
        }

        # try:
        #     logger.info(f"💭 {symbol}: Analyzing sentiment from news...")
        #     import os
        #
        #     # Get Polygon API key from environment
        #     polygon_api_key = os.getenv('POLYGON_API_KEY', 'demo')
        #
        #     sentiment_service = SentimentService(polygon_api_key)
        #     sentiment_result = sentiment_service.analyze_sentiment(symbol, limit_per_ticker=20)
        #
        #     # Update timestamp for sentiment analysis
        #     stock.last_sentiment_analysis = datetime.now(timezone.utc)
        #     db.commit()
        #
        #     analysis_results['steps']['sentiment'] = {
        #         'status': 'success',
        #         'sentiment_index': sentiment_result.get('sentiment_index', 0),
        #         'news_analyzed': sentiment_result.get('total_articles', 0)
        #     }
        #     logger.info(f"✅ {symbol}: Sentiment analyzed - index: {sentiment_result.get('sentiment_index', 0):.2f}")
        #
        # except Exception as e:
        #     logger.error(f"❌ {symbol}: Sentiment analysis failed: {e}")
        #     analysis_results['steps']['sentiment'] = {'status': 'error', 'message': str(e)}

        # ============================================
        # STEP 5: MARKET REGIME DETECTION
        # ============================================
        try:
            logger.info(f"🌊 {symbol}: Detecting market regime...")

            regime_service = MarketRegimeService(db)
            regime_result = regime_service.detect_market_regime(stock_id)

            analysis_results['steps']['market_regime'] = {
                'status': 'success',
                'regime': regime_result.get('regime', 'unknown'),
                'trend_strength': regime_result.get('trend_strength', 0)
            }
            logger.info(f"✅ {symbol}: Market regime - {regime_result.get('regime', 'unknown')}")

        except Exception as e:
            logger.error(f"❌ {symbol}: Market regime detection failed: {e}")
            analysis_results['steps']['market_regime'] = {'status': 'error', 'message': str(e)}

        # ============================================
        # STEP 6: FINAL RECOMMENDATION
        # ============================================
        try:
            logger.info(f"🎯 {symbol}: Generating final recommendation...")

            recommendation = generate_final_recommendation(db, stock_id)

            analysis_results['steps']['recommendation'] = {
                'status': 'success',
                'final_recommendation': recommendation.get('final_recommendation'),
                'confidence': recommendation.get('overall_confidence')
            }
            logger.info(f"✅ {symbol}: Recommendation - {recommendation.get('final_recommendation')} ({recommendation.get('overall_confidence', 0)*100:.0f}% confidence)")

        except Exception as e:
            logger.error(f"❌ {symbol}: Recommendation generation failed: {e}")
            analysis_results['steps']['recommendation'] = {'status': 'error', 'message': str(e)}

        # ============================================
        # FINAL STATUS & UPDATE ANALYSIS TRACKING
        # ============================================
        successful_steps = sum(1 for step in analysis_results['steps'].values() if step.get('status') == 'success')
        total_steps = len(analysis_results['steps'])

        # Update comprehensive analysis timestamp
        stock.last_comprehensive_analysis = datetime.now(timezone.utc)

        # Recalculate analysis score and completeness flag
        stock.analysis_score = AnalysisCompletenessService.calculate_completeness_score(stock, db)
        stock.analysis_complete = (stock.analysis_score >= 0.80)
        db.commit()

        analysis_results['overall_status'] = 'success' if successful_steps == total_steps else 'partial'
        analysis_results['successful_steps'] = successful_steps
        analysis_results['total_steps'] = total_steps
        analysis_results['analysis_score'] = float(stock.analysis_score)
        analysis_results['analysis_complete'] = stock.analysis_complete

        logger.info(
            f"✅ {symbol}: Analysis complete - {successful_steps}/{total_steps} steps successful, "
            f"score={stock.analysis_score:.2f}, complete={stock.analysis_complete}"
        )

        return analysis_results

    except Exception as e:
        logger.error(f"❌ {symbol}: Comprehensive analysis failed: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True)
def analyze_high_priority_stocks(self):
    """
    Run comprehensive analysis for all high-priority stocks

    Triggered after high-priority price fetch completes
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock

    logger.info("🔬 Starting analysis for high-priority stocks")

    db = SessionLocal()
    try:
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'high'
        ).all()

        results = []
        for stock in stocks:
            # Queue individual analysis tasks
            result = analyze_stock_comprehensive.apply_async(
                args=[stock.id, stock.symbol],
                countdown=5  # Small delay to avoid overwhelming system
            )
            results.append({
                'stock_id': stock.id,
                'symbol': stock.symbol,
                'task_id': result.id
            })

        logger.info(f"✅ Queued analysis for {len(stocks)} high-priority stocks")

        return {
            'status': 'queued',
            'stocks_queued': len(stocks),
            'tasks': results
        }

    finally:
        db.close()


@celery_app.task(bind=True)
def analyze_medium_priority_stocks(self):
    """
    Run comprehensive analysis for all medium-priority stocks

    Triggered after medium-priority price fetch completes
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock

    logger.info("🔬 Starting analysis for medium-priority stocks")

    db = SessionLocal()
    try:
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'medium'
        ).all()

        results = []
        for stock in stocks:
            result = analyze_stock_comprehensive.apply_async(
                args=[stock.id, stock.symbol],
                countdown=10  # Slightly longer delay for medium priority
            )
            results.append({
                'stock_id': stock.id,
                'symbol': stock.symbol,
                'task_id': result.id
            })

        logger.info(f"✅ Queued analysis for {len(stocks)} medium-priority stocks")

        return {
            'status': 'queued',
            'stocks_queued': len(stocks),
            'tasks': results
        }

    finally:
        db.close()


@celery_app.task(bind=True)
def analyze_low_priority_stocks(self):
    """
    Run comprehensive analysis for all low-priority stocks

    Triggered after low-priority price fetch completes
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock

    logger.info("🔬 Starting analysis for low-priority stocks")

    db = SessionLocal()
    try:
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'low'
        ).all()

        results = []
        for stock in stocks:
            result = analyze_stock_comprehensive.apply_async(
                args=[stock.id, stock.symbol],
                countdown=15  # Longer delay for low priority
            )
            results.append({
                'stock_id': stock.id,
                'symbol': stock.symbol,
                'task_id': result.id
            })

        logger.info(f"✅ Queued analysis for {len(stocks)} low-priority stocks")

        return {
            'status': 'queued',
            'stocks_queued': len(stocks),
            'tasks': results
        }

    finally:
        db.close()
