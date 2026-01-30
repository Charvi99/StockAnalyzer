"""
Priority Calculator Service

Calculates stock priority based on:
- Trading volume
- Price volatility
- Pattern detection frequency
- Recent activity

Priority Tiers:
- High (score >= 60): Updated hourly
- Medium (30 <= score < 60): Updated every 4 hours
- Low (score < 30): Updated daily
"""

from datetime import datetime, timedelta, timezone
from typing import Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)


class PriorityCalculator:
    """Calculate and assign priorities to stocks"""

    # Scoring weights (total = 100 points)
    VOLUME_WEIGHT = 30      # Trading volume importance
    VOLATILITY_WEIGHT = 25  # Price movement importance
    PATTERN_WEIGHT = 25     # Pattern detection frequency
    RECENCY_WEIGHT = 20     # Recent activity importance

    # Priority thresholds
    HIGH_THRESHOLD = 60     # >= 60 points = high priority
    MEDIUM_THRESHOLD = 30   # 30-59 points = medium priority
                            # < 30 points = low priority

    def __init__(self, db: Session):
        self.db = db

    def calculate_statistics(self, stock_id: int) -> dict:
        """
        Calculate statistics for a stock over the last 30 days

        Args:
            stock_id: Stock ID

        Returns:
            dict with avg_volume, avg_price, volatility, pattern_count
        """
        from app.models.stock import StockPrice, ChartPattern

        # Calculate date range (30 days ago)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)

        # Get price data for last 30 days (1d timeframe)
        prices = self.db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timeframe == '1d',
            StockPrice.timestamp >= start_date,
            StockPrice.timestamp <= end_date
        ).all()

        if not prices or len(prices) < 5:
            # Not enough data
            return {
                'avg_volume_30d': None,
                'avg_price_30d': None,
                'volatility_30d': None,
                'pattern_count_30d': 0,
                'last_pattern_date': None
            }

        # Calculate average volume
        avg_volume = sum(p.volume for p in prices if p.volume) / len(prices)

        # Calculate average price
        avg_price = sum(float(p.close) for p in prices) / len(prices)

        # Calculate volatility (standard deviation of daily returns)
        if len(prices) > 1:
            returns = []
            for i in range(1, len(prices)):
                prev_close = float(prices[i-1].close)
                curr_close = float(prices[i].close)
                daily_return = (curr_close - prev_close) / prev_close
                returns.append(daily_return)

            # Standard deviation
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
        else:
            volatility = 0.0

        # Count patterns detected in last 30 days
        pattern_count = self.db.query(ChartPattern).filter(
            ChartPattern.stock_id == stock_id,
            ChartPattern.created_at >= start_date,
            ChartPattern.created_at <= end_date
        ).count()

        # Get last pattern date
        last_pattern = self.db.query(ChartPattern).filter(
            ChartPattern.stock_id == stock_id
        ).order_by(ChartPattern.created_at.desc()).first()

        return {
            'avg_volume_30d': int(avg_volume),
            'avg_price_30d': round(avg_price, 4),
            'volatility_30d': round(volatility * 100, 4),  # Convert to percentage
            'pattern_count_30d': pattern_count,
            'last_pattern_date': last_pattern.created_at if last_pattern else None
        }

    def calculate_priority_score(self, stock_id: int, symbol: str, stats: dict = None) -> float:
        """
        Calculate priority score for a stock

        Args:
            stock_id: Stock ID
            symbol: Stock symbol
            stats: Pre-calculated statistics (optional)

        Returns:
            Priority score (0-100)
        """
        # Get statistics if not provided
        if stats is None:
            stats = self.calculate_statistics(stock_id)

        # If no price data available, assign default medium priority (50 points)
        if stats['avg_volume_30d'] is None:
            logger.warning(f"{symbol}: No price data available, assigning default medium priority")
            return 50.0

        score = 0.0

        # 1. Volume Score (0-30 points)
        # High volume = more liquid = more tradeable
        if stats['avg_volume_30d']:
            volume_millions = stats['avg_volume_30d'] / 1_000_000
            # Scale: 1M vol = 5pts, 5M = 15pts, 10M+ = 30pts
            volume_score = min(volume_millions * 3, self.VOLUME_WEIGHT)
            score += volume_score
            logger.debug(f"{symbol}: Volume score = {volume_score:.1f} (avg {volume_millions:.1f}M)")

        # 2. Volatility Score (0-25 points)
        # Higher volatility = more swing trading opportunities
        if stats['volatility_30d']:
            volatility_pct = float(stats['volatility_30d'])
            # Scale: 1% = 8pts, 2% = 16pts, 3%+ = 25pts
            volatility_score = min(volatility_pct * 8, self.VOLATILITY_WEIGHT)
            score += volatility_score
            logger.debug(f"{symbol}: Volatility score = {volatility_score:.1f} ({volatility_pct:.2f}%)")

        # 3. Pattern Score (0-25 points)
        # More patterns = more trading opportunities
        pattern_count = stats['pattern_count_30d']
        # Scale: 1 pattern = 5pts, 2 = 10pts, 5+ = 25pts
        pattern_score = min(pattern_count * 5, self.PATTERN_WEIGHT)
        score += pattern_score
        logger.debug(f"{symbol}: Pattern score = {pattern_score:.1f} ({pattern_count} patterns)")

        # 4. Recency Score (0-20 points)
        # Recent patterns = current activity
        if stats['last_pattern_date']:
            days_since_pattern = (datetime.now(timezone.utc) - stats['last_pattern_date'].replace(tzinfo=timezone.utc)).days
            if days_since_pattern <= 7:
                recency_score = self.RECENCY_WEIGHT  # Full points if pattern in last week
            elif days_since_pattern <= 14:
                recency_score = self.RECENCY_WEIGHT * 0.75  # 75% if 1-2 weeks
            elif days_since_pattern <= 30:
                recency_score = self.RECENCY_WEIGHT * 0.5   # 50% if 2-4 weeks
            else:
                recency_score = self.RECENCY_WEIGHT * 0.25  # 25% if older
            score += recency_score
            logger.debug(f"{symbol}: Recency score = {recency_score:.1f} ({days_since_pattern} days)")

        logger.info(f"{symbol}: Total priority score = {score:.1f}/100")
        return round(score, 2)

    def determine_priority_tier(self, score: float) -> str:
        """
        Determine priority tier based on score

        Args:
            score: Priority score (0-100)

        Returns:
            Priority tier: 'high', 'medium', or 'low'
        """
        if score >= self.HIGH_THRESHOLD:
            return 'high'
        elif score >= self.MEDIUM_THRESHOLD:
            return 'medium'
        else:
            return 'low'

    def calculate_stock_priority(self, stock_id: int, symbol: str) -> Tuple[str, float, dict]:
        """
        Calculate full priority for a stock

        Args:
            stock_id: Stock ID
            symbol: Stock symbol

        Returns:
            Tuple of (priority_tier, priority_score, statistics)
        """
        logger.info(f"Calculating priority for {symbol}")

        # Calculate statistics
        stats = self.calculate_statistics(stock_id)

        # Calculate score
        score = self.calculate_priority_score(stock_id, symbol, stats)

        # Determine tier
        tier = self.determine_priority_tier(score)

        logger.info(f"{symbol}: Priority = {tier} (score: {score:.1f})")

        return tier, score, stats

    def update_stock_priority(self, stock_id: int, symbol: str) -> dict:
        """
        Calculate and update priority for a stock in database

        Args:
            stock_id: Stock ID
            symbol: Stock symbol

        Returns:
            dict with updated values
        """
        from app.models.stock import Stock

        # Calculate priority
        tier, score, stats = self.calculate_stock_priority(stock_id, symbol)

        # Update stock in database
        stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
        if stock:
            stock.priority = tier
            stock.priority_score = score
            stock.priority_updated_at = datetime.now(timezone.utc)
            stock.avg_volume_30d = stats['avg_volume_30d']
            stock.avg_price_30d = stats['avg_price_30d']
            stock.volatility_30d = stats['volatility_30d']
            stock.pattern_count_30d = stats['pattern_count_30d']
            stock.last_pattern_date = stats['last_pattern_date']
            self.db.commit()

        return {
            'symbol': symbol,
            'priority': tier,
            'score': score,
            'statistics': stats
        }

    def recalculate_all_priorities(self) -> dict:
        """
        Recalculate priorities for all tracked stocks

        Returns:
            dict with summary statistics
        """
        from app.models.stock import Stock

        logger.info("Starting priority recalculation for all stocks")

        stocks = self.db.query(Stock).filter(Stock.is_tracked == True).all()

        high_count = 0
        medium_count = 0
        low_count = 0
        error_count = 0

        for stock in stocks:
            try:
                result = self.update_stock_priority(stock.id, stock.symbol)
                if result['priority'] == 'high':
                    high_count += 1
                elif result['priority'] == 'medium':
                    medium_count += 1
                else:
                    low_count += 1

            except Exception as e:
                logger.error(f"Error calculating priority for {stock.symbol}: {e}")
                error_count += 1

        logger.info(f"Priority recalculation complete: {high_count} high, {medium_count} medium, {low_count} low, {error_count} errors")

        return {
            'status': 'completed',
            'total_stocks': len(stocks),
            'high_priority': high_count,
            'medium_priority': medium_count,
            'low_priority': low_count,
            'errors': error_count
        }
