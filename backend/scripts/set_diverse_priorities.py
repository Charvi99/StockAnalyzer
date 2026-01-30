"""
Set Diverse Priority Values for All Stocks

This script assigns realistic priority values to stocks based on:
- Sector importance
- Major company recognition
- Volume data (if available)

Distribution target:
- HIGH (70-100): 15% of stocks (75 stocks)
- MEDIUM (40-69): 50% of stocks (251 stocks)
- LOW (0-39): 35% of stocks (176 stocks)
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.stock import Stock
from datetime import datetime

# Major companies that should be HIGH priority
MAJOR_SYMBOLS = [
    # Tech Giants
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'AMD', 'INTC',
    'CRM', 'ORCL', 'ADBE', 'CSCO', 'AVGO', 'QCOM', 'TXN', 'AMAT', 'MU', 'LRCX',

    # Financial Giants
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'SCHW', 'AXP', 'USB',
    'PNC', 'TFC', 'COF', 'BK', 'STT',

    # Healthcare Leaders
    'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'LLY', 'DHR', 'BMY',
    'AMGN', 'GILD', 'CVS', 'CI', 'HUM',

    # Consumer/Retail
    'WMT', 'HD', 'DIS', 'NKE', 'SBUX', 'MCD', 'TGT', 'COST', 'LOW', 'TJX',

    # Energy
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'HAL'
]

# High-priority sectors
HIGH_PRIORITY_SECTORS = [
    'Technology',
    'Communication Services',
    'Healthcare',
    'Financial Services',
    'Consumer Cyclical'
]

# Medium-priority sectors
MEDIUM_PRIORITY_SECTORS = [
    'Energy',
    'Industrials',
    'Consumer Defensive',
    'Real Estate'
]

# Low-priority sectors (everything else)


def calculate_priority_score(stock: Stock) -> float:
    """
    Calculate priority score (0-100) for a stock

    Args:
        stock: Stock object

    Returns:
        float: Priority score between 0-100
    """
    score = 50.0  # Base score

    # Factor 1: Major company recognition (+30)
    if stock.symbol in MAJOR_SYMBOLS:
        score += 30

    # Factor 2: Sector importance
    if stock.sector in HIGH_PRIORITY_SECTORS:
        score += 15
    elif stock.sector in MEDIUM_PRIORITY_SECTORS:
        score += 5
    else:
        score -= 10  # Low priority sector

    # Factor 3: Volume boost (if available)
    if stock.avg_volume_30d:
        if stock.avg_volume_30d > 10_000_000:  # Very high volume
            score += 10
        elif stock.avg_volume_30d > 5_000_000:  # High volume
            score += 5
        elif stock.avg_volume_30d < 500_000:  # Low volume
            score -= 10

    # Factor 4: Recent pattern activity (if available)
    if stock.pattern_count_30d and stock.pattern_count_30d > 5:
        score += 5

    # Cap score at 0-100
    return min(100.0, max(0.0, score))


def assign_priority_category(score: float) -> str:
    """
    Convert priority score to category

    Args:
        score: Priority score (0-100)

    Returns:
        str: 'high', 'medium', or 'low'
    """
    if score >= 70:
        return 'high'
    elif score >= 40:
        return 'medium'
    else:
        return 'low'


def set_diverse_priorities():
    """Main function to update priorities for all stocks"""
    db: Session = SessionLocal()

    try:
        # Fetch all stocks
        stocks = db.query(Stock).all()
        print(f"📊 Found {len(stocks)} stocks to update")

        # Calculate priorities
        updates = []
        for stock in stocks:
            old_score = stock.priority_score
            old_priority = stock.priority

            new_score = calculate_priority_score(stock)
            new_priority = assign_priority_category(new_score)

            stock.priority_score = new_score
            stock.priority = new_priority
            stock.priority_updated_at = datetime.utcnow()

            updates.append({
                'symbol': stock.symbol,
                'old_score': old_score,
                'new_score': new_score,
                'old_priority': old_priority,
                'new_priority': new_priority
            })

        # Commit changes
        db.commit()
        print(f"✅ Updated {len(updates)} stocks")

        # Show statistics
        high_count = sum(1 for u in updates if u['new_priority'] == 'high')
        medium_count = sum(1 for u in updates if u['new_priority'] == 'medium')
        low_count = sum(1 for u in updates if u['new_priority'] == 'low')

        print(f"\n📈 Priority Distribution:")
        print(f"  HIGH:   {high_count:3d} stocks ({high_count/len(updates)*100:.1f}%)")
        print(f"  MEDIUM: {medium_count:3d} stocks ({medium_count/len(updates)*100:.1f}%)")
        print(f"  LOW:    {low_count:3d} stocks ({low_count/len(updates)*100:.1f}%)")

        # Show sample updates
        print(f"\n🔍 Sample Updates (first 10):")
        for update in updates[:10]:
            print(f"  {update['symbol']:6s}: {update['old_score']:5.1f} → {update['new_score']:5.1f} "
                  f"({update['old_priority']:6s} → {update['new_priority']:6s})")

        # Show high-priority stocks
        high_priority_stocks = [u['symbol'] for u in updates if u['new_priority'] == 'high']
        print(f"\n⭐ High Priority Stocks ({len(high_priority_stocks)}):")
        print(f"  {', '.join(sorted(high_priority_stocks)[:30])}...")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    print("🚀 Setting Diverse Priority Values for Stocks\n")
    set_diverse_priorities()
    print("\n✨ Done!")
