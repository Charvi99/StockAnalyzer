"""
Set default priorities for all stocks

Use this when:
- First time setup
- After dropping price data
- To reset all priorities to medium

This allows the system to start fetching data before priorities can be calculated.
"""

from app.db.database import SessionLocal
from app.models.stock import Stock
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def set_default_priorities(distribution='even'):
    """
    Set default priorities for all tracked stocks

    Args:
        distribution: 'even' (split evenly), 'medium' (all medium), or 'by_symbol' (alphabetical)
    """
    db = SessionLocal()
    try:
        stocks = db.query(Stock).filter(Stock.is_tracked == True).order_by(Stock.symbol).all()

        if not stocks:
            logger.warning("No tracked stocks found")
            return

        total_stocks = len(stocks)
        logger.info(f"Setting default priorities for {total_stocks} stocks")

        if distribution == 'medium':
            # All stocks get medium priority
            for stock in stocks:
                stock.priority = 'medium'
                stock.priority_score = 50.0
                stock.priority_updated_at = datetime.now(timezone.utc)

            logger.info(f"✅ Set all {total_stocks} stocks to medium priority")

        elif distribution == 'even':
            # Split evenly: 20% high, 40% medium, 40% low
            high_count = int(total_stocks * 0.20)
            medium_count = int(total_stocks * 0.40)

            for idx, stock in enumerate(stocks):
                if idx < high_count:
                    stock.priority = 'high'
                    stock.priority_score = 70.0
                elif idx < high_count + medium_count:
                    stock.priority = 'medium'
                    stock.priority_score = 50.0
                else:
                    stock.priority = 'low'
                    stock.priority_score = 30.0

                stock.priority_updated_at = datetime.now(timezone.utc)

            logger.info(f"✅ Set priorities: {high_count} high, {medium_count} medium, {total_stocks - high_count - medium_count} low")

        elif distribution == 'by_symbol':
            # Assign by alphabetical order (earlier symbols = higher priority)
            # Useful for testing or if you have a specific symbol preference
            for idx, stock in enumerate(stocks):
                if idx < total_stocks // 3:
                    stock.priority = 'high'
                    stock.priority_score = 70.0
                elif idx < 2 * total_stocks // 3:
                    stock.priority = 'medium'
                    stock.priority_score = 50.0
                else:
                    stock.priority = 'low'
                    stock.priority_score = 30.0

                stock.priority_updated_at = datetime.now(timezone.utc)

            logger.info(f"✅ Set priorities by symbol (alphabetical)")

        db.commit()

        # Print summary
        high = db.query(Stock).filter(Stock.priority == 'high').count()
        medium = db.query(Stock).filter(Stock.priority == 'medium').count()
        low = db.query(Stock).filter(Stock.priority == 'low').count()

        logger.info(f"📊 Final distribution:")
        logger.info(f"   🔥 High: {high} stocks")
        logger.info(f"   ⚡ Medium: {medium} stocks")
        logger.info(f"   📊 Low: {low} stocks")

        return {'high': high, 'medium': medium, 'low': low}

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    import sys

    distribution = sys.argv[1] if len(sys.argv) > 1 else 'even'

    if distribution not in ['even', 'medium', 'by_symbol']:
        print("Usage: python set_default_priorities.py [even|medium|by_symbol]")
        print("  even: 20% high, 40% medium, 40% low (default)")
        print("  medium: All stocks get medium priority")
        print("  by_symbol: Priority by alphabetical order")
        sys.exit(1)

    set_default_priorities(distribution)
