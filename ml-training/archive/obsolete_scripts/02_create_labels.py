"""
Create Swing Trading Labels

This script creates labels for supervised learning.
Target: Will stock hit +3% within 20 days before hitting -2%?

Usage:
    python 02_create_labels.py
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from tqdm import tqdm

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass@db:5432/stockanalyzer')
engine = create_engine(DATABASE_URL)

# Swing trading parameters
PROFIT_TARGET = 0.03  # +3%
STOP_LOSS = -0.02  # -2%
LOOKAHEAD_DAYS = 20


def get_stock_prices(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Fetch price data for a stock"""
    query = text("""
        SELECT timestamp, close
        FROM stock_prices
        WHERE stock_id = :stock_id
          AND timeframe = '1d'
          AND timestamp >= :start_date
          AND timestamp <= :end_date
        ORDER BY timestamp ASC
    """)

    df = pd.read_sql(
        query,
        engine,
        params={'stock_id': stock_id, 'start_date': start_date, 'end_date': end_date}
    )

    if df.empty:
        return None

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def create_swing_labels(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Create swing trading labels for a stock

    For each day, checks if stock hits:
    - +3% within next 20 days → BUY (1)
    - -2% before hitting +3% → DON'T BUY (0)
    - Neither within 20 days → DON'T BUY (0)

    Args:
        stock_id: Stock ID
        start_date: Start date for analysis
        end_date: End date for analysis

    Returns:
        DataFrame with columns: timestamp, stock_id, label
    """
    # Fetch price data with extra days for lookahead
    extended_end = end_date + timedelta(days=LOOKAHEAD_DAYS + 5)
    prices = get_stock_prices(stock_id, start_date - timedelta(days=50), extended_end)

    if prices is None or len(prices) < LOOKAHEAD_DAYS:
        return None

    labels = []

    # Create labels for each trading day
    for i in tqdm(range(len(prices) - LOOKAHEAD_DAYS - 1), desc=f"Stock {stock_id}"):
        current_date = prices.iloc[i]['timestamp']
        current_price = prices.iloc[i]['close']

        # Only create labels for dates in range
        if current_date < start_date or current_date > end_date:
            continue

        # Look ahead
        future_prices = prices.iloc[i+1:i+LOOKAHEAD_DAYS+1]['close'].values

        # Calculate max upside and max drawdown
        max_upside = np.max((future_prices - current_price) / current_price)
        max_drawdown = np.min((future_prices - current_price) / current_price)

        # Determine label
        if max_upside >= PROFIT_TARGET and max_drawdown > STOP_LOSS:
            # Hit profit target before stop loss
            label = 1  # BUY
        else:
            # Hit stop loss first or neither
            label = 0  # DON'T BUY

        labels.append({
            'timestamp': current_date,
            'stock_id': stock_id,
            'label': label,
            'max_upside': max_upside,
            'max_drawdown': max_drawdown
        })

    return pd.DataFrame(labels)


def main():
    """Main label creation pipeline"""
    print("=" * 60)
    print("StockAnalyzer ML - Label Creation Pipeline")
    print("=" * 60)
    print(f"\nParameters:")
    print(f"  Profit Target: +{PROFIT_TARGET*100:.1f}%")
    print(f"  Stop Loss: {STOP_LOSS*100:.1f}%")
    print(f"  Lookahead: {LOOKAHEAD_DAYS} days")

    # Create outputs directory
    outputs_dir = Path('/app/outputs/features')
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Get date range (last 2 years for training)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)  # 2 years

    # Get all tracked stocks
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM stocks WHERE is_tracked = true"))
        stock_ids = [row[0] for row in result]

    print(f"\n📊 Found {len(stock_ids)} tracked stocks")
    print(f"📅 Date range: {start_date.date()} to {end_date.date()}")

    # Create labels for each stock
    all_labels = []

    for stock_id in stock_ids:
        try:
            labels = create_swing_labels(stock_id, start_date, end_date)
            if labels is not None and not labels.empty:
                all_labels.append(labels)
        except Exception as e:
            print(f"\n❌ Error creating labels for stock {stock_id}: {e}")

    # Combine all labels
    if not all_labels:
        print("\n❌ No labels created!")
        return

    df = pd.concat(all_labels, ignore_index=True)

    # Save to parquet
    output_file = outputs_dir / f'labels_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
    df.to_parquet(output_file, index=False)

    # Print statistics
    buy_signals = df['label'].sum()
    total = len(df)
    buy_ratio = buy_signals / total

    print(f"\n✅ Saved {len(df)} label rows to {output_file}")
    print(f"\n📊 Label Statistics:")
    print(f"  Total samples: {total}")
    print(f"  BUY signals (1): {buy_signals} ({buy_ratio*100:.1f}%)")
    print(f"  DON'T BUY (0): {total - buy_signals} ({(1-buy_ratio)*100:.1f}%)")
    print(f"\n💡 Use this file with features to train models")


if __name__ == "__main__":
    main()
