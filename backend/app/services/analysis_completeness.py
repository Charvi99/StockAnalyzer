"""
Analysis Completeness Service

This service provides utilities for tracking and calculating the completeness
of analysis data for stocks. It helps determine which stocks need analysis
and avoids redundant computation.

Key responsibilities:
- Calculate analysis completeness score (0.0 to 1.0)
- Detect missing or stale analysis components
- Determine if a stock needs analysis refresh
- Update analysis timestamps after successful analysis
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.stock import Stock, ChartPattern, CandlestickPattern, SentimentScore, Prediction, TechnicalIndicator
import logging

logger = logging.getLogger(__name__)


class AnalysisCompletenessService:
    """
    Service for managing analysis completeness tracking.

    Analysis Score Calculation (counts ONLY the steps that
    ``analyze_stock_comprehensive`` actually runs):
    - Chart patterns (recent):      1/3
    - Candlestick patterns (recent): 1/3
    - Technical indicators (recent): 1/3

    ML predictions are NOT part of the active pipeline (model not running) and
    sentiment is derived from news at fetch time (not an analysis step), so neither
    is counted. Previously all five were counted at 20% each, which capped the score
    at 0.60 and made ``analysis_complete`` (>=0.80) unreachable — the root cause of
    the "⚠ 60% forever" display and the perpetual re-analysis loop.

    "Recent" is defined by max_age parameter (default: 24 hours).
    """

    # Staleness thresholds (hours)
    DEFAULT_MAX_AGE_HOURS = 24  # Most components should be < 24 hours old
    ML_MAX_AGE_HOURS = 168  # ML predictions can be up to 7 days old (168 hours)

    @staticmethod
    def calculate_completeness_score(
        stock: Stock,
        db: Session,
        max_age_hours: int = DEFAULT_MAX_AGE_HOURS
    ) -> float:
        """
        Calculate analysis completeness score (0.0 to 1.0) for a stock.

        Args:
            stock: Stock object to check
            db: Database session
            max_age_hours: Maximum age (in hours) for data to be considered "fresh"

        Returns:
            Float between 0.0 and 1.0 representing completeness percentage
        """
        score = 0.0
        now = datetime.now(timezone.utc)
        max_age = timedelta(hours=max_age_hours)
        per_component = 1.0 / 3.0  # chart / candlestick / technical — the steps that actually run

        # Component 1: Chart Patterns (1/3)
        if stock.last_chart_pattern_detection and (now - stock.last_chart_pattern_detection) < max_age:
            # Verify we actually have patterns in database
            pattern_count = db.query(func.count(ChartPattern.id)).filter(
                ChartPattern.stock_id == stock.id
            ).scalar()
            if pattern_count > 0 or (now - stock.last_chart_pattern_detection) < timedelta(hours=1):
                # Either has patterns, or was checked very recently (no patterns found is valid)
                score += per_component

        # Component 2: Candlestick Patterns (1/3)
        if stock.last_candlestick_detection and (now - stock.last_candlestick_detection) < max_age:
            candlestick_count = db.query(func.count(CandlestickPattern.id)).filter(
                CandlestickPattern.stock_id == stock.id
            ).scalar()
            if candlestick_count > 0 or (now - stock.last_candlestick_detection) < timedelta(hours=1):
                score += per_component

        # Component 3: Technical Indicators (1/3)
        if stock.last_technical_analysis and (now - stock.last_technical_analysis) < max_age:
            indicator_count = db.query(func.count(TechnicalIndicator.id)).filter(
                TechnicalIndicator.stock_id == stock.id
            ).scalar()
            if indicator_count > 0:
                score += per_component

        # NOTE: sentiment (derived from news at fetch time, not an analysis step) and
        # ML predictions (model not running) are intentionally NOT counted — counting
        # them capped the score at 0.60 and made analysis_complete unreachable.

        return round(score, 2)

    @staticmethod
    def get_missing_components(
        stock: Stock,
        db: Session,
        max_age_hours: int = DEFAULT_MAX_AGE_HOURS
    ) -> List[str]:
        """
        Get list of missing or stale analysis components for a stock.

        Args:
            stock: Stock object to check
            db: Database session
            max_age_hours: Maximum age (in hours) for data to be considered "fresh"

        Returns:
            List of component names that are missing or stale
        """
        missing = []
        now = datetime.now(timezone.utc)
        max_age = timedelta(hours=max_age_hours)

        # Only the components the analysis pipeline actually runs (see calculate_completeness_score)
        if not stock.last_chart_pattern_detection or (now - stock.last_chart_pattern_detection) >= max_age:
            missing.append("chart_patterns")
        if not stock.last_candlestick_detection or (now - stock.last_candlestick_detection) >= max_age:
            missing.append("candlestick_patterns")
        if not stock.last_technical_analysis or (now - stock.last_technical_analysis) >= max_age:
            missing.append("technical_indicators")

        return missing

    @staticmethod
    def should_trigger_analysis(
        stock: Stock,
        db: Session,
        min_score_threshold: float = 0.80,
        max_age_hours: int = DEFAULT_MAX_AGE_HOURS
    ) -> bool:
        """
        Determine if a stock needs comprehensive analysis.

        Args:
            stock: Stock object to check
            db: Database session
            min_score_threshold: Minimum acceptable score (default 0.80 = 80%)
            max_age_hours: Maximum age for data freshness

        Returns:
            True if analysis should be triggered, False otherwise
        """
        # Always analyze if never analyzed before
        if not stock.last_comprehensive_analysis:
            return True

        # Calculate current completeness score
        current_score = AnalysisCompletenessService.calculate_completeness_score(
            stock, db, max_age_hours
        )

        # Trigger if score is below threshold
        if current_score < min_score_threshold:
            logger.info(
                f"Stock {stock.symbol} (ID: {stock.id}) needs analysis: "
                f"score={current_score:.2f} < threshold={min_score_threshold:.2f}"
            )
            return True

        return False

    @staticmethod
    def update_analysis_timestamps(
        stock: Stock,
        db: Session,
        components_completed: List[str]
    ) -> None:
        """
        Update analysis timestamps for completed components.

        Args:
            stock: Stock object to update
            db: Database session
            components_completed: List of component names that were completed
                Valid values: 'chart_patterns', 'candlestick_patterns',
                             'sentiment', 'technical_indicators', 'ml_prediction', 'comprehensive'
        """
        now = datetime.now(timezone.utc)

        for component in components_completed:
            if component == 'chart_patterns':
                stock.last_chart_pattern_detection = now
            elif component == 'candlestick_patterns':
                stock.last_candlestick_detection = now
            elif component == 'sentiment':
                stock.last_sentiment_analysis = now
            elif component == 'technical_indicators':
                stock.last_technical_analysis = now
            elif component == 'ml_prediction':
                stock.last_ml_prediction = now
            elif component == 'comprehensive':
                stock.last_comprehensive_analysis = now

        # Recalculate analysis score and completeness flag
        stock.analysis_score = AnalysisCompletenessService.calculate_completeness_score(stock, db)
        stock.analysis_complete = (stock.analysis_score >= 0.80)

        db.commit()
        logger.info(
            f"Updated analysis timestamps for {stock.symbol}: "
            f"score={stock.analysis_score:.2f}, complete={stock.analysis_complete}"
        )

    @staticmethod
    def get_stocks_needing_analysis(
        db: Session,
        min_score_threshold: float = 0.80,
        max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
        tracked_only: bool = True,
        limit: Optional[int] = None
    ) -> List[Stock]:
        """
        Get list of stocks that need analysis (incomplete or stale).

        Args:
            db: Database session
            min_score_threshold: Minimum acceptable score
            max_age_hours: Maximum age for data freshness
            tracked_only: Only return tracked stocks (default True)
            limit: Maximum number of stocks to return (optional)

        Returns:
            List of Stock objects needing analysis, ordered by priority
        """
        query = db.query(Stock)

        if tracked_only:
            query = query.filter(Stock.is_tracked == True)

        # Filter by score (quick database-level filter)
        query = query.filter(Stock.analysis_score < min_score_threshold)

        # Order by priority (high first) then by score (lowest first)
        query = query.order_by(
            Stock.priority.desc(),  # high > medium > low
            Stock.analysis_score.asc()  # least complete first
        )

        if limit:
            query = query.limit(limit)

        stocks = query.all()

        logger.info(
            f"Found {len(stocks)} stocks needing analysis "
            f"(score < {min_score_threshold:.2f}, max_age={max_age_hours}h)"
        )

        return stocks

    @staticmethod
    def get_completeness_summary(stock: Stock, db: Session) -> Dict:
        """
        Get detailed summary of analysis completeness for a stock.

        Args:
            stock: Stock object to analyze
            db: Database session

        Returns:
            Dictionary with detailed completeness information
        """
        now = datetime.now(timezone.utc)
        missing = AnalysisCompletenessService.get_missing_components(stock, db)

        return {
            "stock_id": stock.id,
            "symbol": stock.symbol,
            "analysis_score": float(stock.analysis_score),
            "analysis_complete": stock.analysis_complete,
            "last_comprehensive_analysis": stock.last_comprehensive_analysis.isoformat() if stock.last_comprehensive_analysis else None,
            "missing_components": missing,
            "components": {
                "chart_patterns": {
                    "last_analyzed": stock.last_chart_pattern_detection.isoformat() if stock.last_chart_pattern_detection else None,
                    "age_hours": (now - stock.last_chart_pattern_detection).total_seconds() / 3600 if stock.last_chart_pattern_detection else None,
                    "is_stale": stock.last_chart_pattern_detection is None or (now - stock.last_chart_pattern_detection).total_seconds() / 3600 > AnalysisCompletenessService.DEFAULT_MAX_AGE_HOURS
                },
                "candlestick_patterns": {
                    "last_analyzed": stock.last_candlestick_detection.isoformat() if stock.last_candlestick_detection else None,
                    "age_hours": (now - stock.last_candlestick_detection).total_seconds() / 3600 if stock.last_candlestick_detection else None,
                    "is_stale": stock.last_candlestick_detection is None or (now - stock.last_candlestick_detection).total_seconds() / 3600 > AnalysisCompletenessService.DEFAULT_MAX_AGE_HOURS
                },
                "sentiment": {
                    "last_analyzed": stock.last_sentiment_analysis.isoformat() if stock.last_sentiment_analysis else None,
                    "age_hours": (now - stock.last_sentiment_analysis).total_seconds() / 3600 if stock.last_sentiment_analysis else None,
                    "is_stale": stock.last_sentiment_analysis is None or (now - stock.last_sentiment_analysis).total_seconds() / 3600 > AnalysisCompletenessService.DEFAULT_MAX_AGE_HOURS
                },
                "technical_indicators": {
                    "last_analyzed": stock.last_technical_analysis.isoformat() if stock.last_technical_analysis else None,
                    "age_hours": (now - stock.last_technical_analysis).total_seconds() / 3600 if stock.last_technical_analysis else None,
                    "is_stale": stock.last_technical_analysis is None or (now - stock.last_technical_analysis).total_seconds() / 3600 > AnalysisCompletenessService.DEFAULT_MAX_AGE_HOURS
                },
                "ml_prediction": {
                    "last_analyzed": stock.last_ml_prediction.isoformat() if stock.last_ml_prediction else None,
                    "age_hours": (now - stock.last_ml_prediction).total_seconds() / 3600 if stock.last_ml_prediction else None,
                    "is_stale": stock.last_ml_prediction is None or (now - stock.last_ml_prediction).total_seconds() / 3600 > AnalysisCompletenessService.ML_MAX_AGE_HOURS
                }
            }
        }
