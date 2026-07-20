"""
Processor tasks for pattern detection and analysis

These tasks run after price data is updated to:
- Detect chart patterns
- Run technical indicator calculations
- Generate trading signals
"""
from app.celery_app import celery_app
from app.config.pattern_thresholds import swing_detector_kwargs, swing_detect_kwargs
import logging

logger = logging.getLogger(__name__)

# ============================================
# PATTERN DETECTION TASKS
# ============================================

@celery_app.task(bind=True, max_retries=3)
def detect_patterns_high_priority(self):
    """
    Detect patterns for high-priority stocks (15 min after price update)
    
    Runs multi-timeframe pattern detection and saves to database.
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock, ChartPattern
    from app.services.multi_timeframe_patterns import MultiTimeframePatternDetector
    from sqlalchemy import and_
    import time
    
    logger.info("🔍 Starting pattern detection for high-priority stocks")
    
    db = SessionLocal()
    try:
        # Get all high-priority stocks
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'high'
        ).all()
        
        total_patterns = 0
        success_count = 0
        error_count = 0
        
        for idx, stock in enumerate(stocks):
            try:
                # Detect patterns using multi-timeframe detector
                detector = MultiTimeframePatternDetector(
                    db=db,
                    stock_id=stock.id,
                    **swing_detector_kwargs()
                )
                
                result = detector.detect_all_patterns(
                    **swing_detect_kwargs()
                )
                
                detected_patterns = result['patterns']
                
                # Save new patterns to database
                saved_count = 0
                for pattern in detected_patterns:
                    # Check if pattern already exists
                    existing = db.query(ChartPattern).filter(
                        and_(
                            ChartPattern.stock_id == stock.id,
                            ChartPattern.pattern_name == pattern['pattern_name'],
                            ChartPattern.end_date == pattern['end_date']
                        )
                    ).first()
                    
                    if not existing:
                        db_pattern = ChartPattern(
                            stock_id=stock.id,
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
                            # Multi-timeframe fields
                            primary_timeframe=pattern.get('primary_timeframe', '1d'),
                            detected_on_timeframes=pattern.get('detected_on_timeframes', ['1d']),
                            confirmation_level=pattern.get('confirmation_level', 1),
                            base_confidence=pattern.get('base_confidence'),
                            alignment_score=pattern.get('alignment_score')
                        )
                        db.add(db_pattern)
                        saved_count += 1
                
                db.commit()
                
                total_patterns += saved_count
                success_count += 1
                
                logger.info(f"✅ {stock.symbol}: Detected {len(detected_patterns)} patterns, saved {saved_count} new")
                
            except Exception as e:
                logger.error(f"❌ Error detecting patterns for {stock.symbol}: {e}")
                error_count += 1
                db.rollback()
            
            # Small delay between stocks to avoid overwhelming the system
            if idx < len(stocks) - 1:
                time.sleep(0.5)
        
        logger.info(f"✅ Pattern detection complete: {success_count} stocks processed, {total_patterns} new patterns, {error_count} errors")
        
        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_patterns_saved': total_patterns
        }
        
    except Exception as e:
        logger.error(f"❌ Error in detect_patterns_high_priority: {e}")
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def detect_patterns_medium_priority(self):
    """
    Detect patterns for medium-priority stocks (30 min after price update)
    
    Runs multi-timeframe pattern detection and saves to database.
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock, ChartPattern
    from app.services.multi_timeframe_patterns import MultiTimeframePatternDetector
    from sqlalchemy import and_
    import time
    
    logger.info("🔍 Starting pattern detection for medium-priority stocks")
    
    db = SessionLocal()
    try:
        # Get all medium-priority stocks
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'medium'
        ).all()
        
        total_patterns = 0
        success_count = 0
        error_count = 0
        
        for idx, stock in enumerate(stocks):
            try:
                # Detect patterns using multi-timeframe detector
                detector = MultiTimeframePatternDetector(
                    db=db,
                    stock_id=stock.id,
                    **swing_detector_kwargs()
                )
                
                result = detector.detect_all_patterns(
                    **swing_detect_kwargs()
                )
                
                detected_patterns = result['patterns']
                
                # Save new patterns to database
                saved_count = 0
                for pattern in detected_patterns:
                    # Check if pattern already exists
                    existing = db.query(ChartPattern).filter(
                        and_(
                            ChartPattern.stock_id == stock.id,
                            ChartPattern.pattern_name == pattern['pattern_name'],
                            ChartPattern.end_date == pattern['end_date']
                        )
                    ).first()
                    
                    if not existing:
                        db_pattern = ChartPattern(
                            stock_id=stock.id,
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
                            # Multi-timeframe fields
                            primary_timeframe=pattern.get('primary_timeframe', '1d'),
                            detected_on_timeframes=pattern.get('detected_on_timeframes', ['1d']),
                            confirmation_level=pattern.get('confirmation_level', 1),
                            base_confidence=pattern.get('base_confidence'),
                            alignment_score=pattern.get('alignment_score')
                        )
                        db.add(db_pattern)
                        saved_count += 1
                
                db.commit()
                
                total_patterns += saved_count
                success_count += 1
                
                logger.info(f"✅ {stock.symbol}: Detected {len(detected_patterns)} patterns, saved {saved_count} new")
                
            except Exception as e:
                logger.error(f"❌ Error detecting patterns for {stock.symbol}: {e}")
                error_count += 1
                db.rollback()
            
            # Small delay between stocks
            if idx < len(stocks) - 1:
                time.sleep(0.5)
        
        logger.info(f"✅ Pattern detection complete: {success_count} stocks processed, {total_patterns} new patterns, {error_count} errors")
        
        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_patterns_saved': total_patterns
        }
        
    except Exception as e:
        logger.error(f"❌ Error in detect_patterns_medium_priority: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def detect_patterns_low_priority(self):
    """
    Detect patterns for low-priority stocks (daily at 6 PM)
    
    Runs multi-timeframe pattern detection and saves to database.
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock, ChartPattern
    from app.services.multi_timeframe_patterns import MultiTimeframePatternDetector
    from sqlalchemy import and_
    import time
    
    logger.info("🔍 Starting pattern detection for low-priority stocks")
    
    db = SessionLocal()
    try:
        # Get all low-priority stocks
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'low'
        ).all()
        
        total_patterns = 0
        success_count = 0
        error_count = 0
        
        for idx, stock in enumerate(stocks):
            try:
                # Detect patterns using multi-timeframe detector
                detector = MultiTimeframePatternDetector(
                    db=db,
                    stock_id=stock.id,
                    **swing_detector_kwargs()
                )
                
                result = detector.detect_all_patterns(
                    **swing_detect_kwargs()
                )
                
                detected_patterns = result['patterns']
                
                # Save new patterns to database
                saved_count = 0
                for pattern in detected_patterns:
                    # Check if pattern already exists
                    existing = db.query(ChartPattern).filter(
                        and_(
                            ChartPattern.stock_id == stock.id,
                            ChartPattern.pattern_name == pattern['pattern_name'],
                            ChartPattern.end_date == pattern['end_date']
                        )
                    ).first()
                    
                    if not existing:
                        db_pattern = ChartPattern(
                            stock_id=stock.id,
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
                            # Multi-timeframe fields
                            primary_timeframe=pattern.get('primary_timeframe', '1d'),
                            detected_on_timeframes=pattern.get('detected_on_timeframes', ['1d']),
                            confirmation_level=pattern.get('confirmation_level', 1),
                            base_confidence=pattern.get('base_confidence'),
                            alignment_score=pattern.get('alignment_score')
                        )
                        db.add(db_pattern)
                        saved_count += 1
                
                db.commit()
                
                total_patterns += saved_count
                success_count += 1
                
                logger.info(f"✅ {stock.symbol}: Detected {len(detected_patterns)} patterns, saved {saved_count} new")
                
            except Exception as e:
                logger.error(f"❌ Error detecting patterns for {stock.symbol}: {e}")
                error_count += 1
                db.rollback()
            
            # Small delay between stocks
            if idx < len(stocks) - 1:
                time.sleep(0.5)
        
        logger.info(f"✅ Pattern detection complete: {success_count} stocks processed, {total_patterns} new patterns, {error_count} errors")
        
        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_patterns_saved': total_patterns
        }
        
    except Exception as e:
        logger.error(f"❌ Error in detect_patterns_low_priority: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()
