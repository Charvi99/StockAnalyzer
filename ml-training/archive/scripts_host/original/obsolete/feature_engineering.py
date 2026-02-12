#!/usr/bin/env python3
"""
Feature Engineering: 40 Features (28 Technical + 12 Insider)
Simplified version - no complex merge operations
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/backend')
sys.path.insert(0, '/app/ml_training')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Import technical indicators
from app.services.technical_indicators import TechnicalIndicators

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def create_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create labels for swing trading strategy

    For each day, determine if price hits +3% before -2% within next 20 days

    Args:
        df: DataFrame with price data (must have 'close' and 'timestamp')

    Returns:
        DataFrame with labels indexed by timestamp
    """
    labels = []

    for i in range(len(df) - 20):  # Need 20 days lookahead
        current_price = df['close'].iloc[i]
        max_upside = 0
        max_drawdown = 0
        label = 0  # Default: didn't hit target

        # Look ahead up to 20 days
        for j in range(i + 1, min(i + 21, len(df))):
            future_price = df['close'].iloc[j]
            upside = (future_price - current_price) / current_price
            drawdown = (future_price - current_price) / current_price

            max_upside = max(max_upside, upside)
            max_drawdown = min(max_drawdown, drawdown)

            # Check if we hit target (+3%)
            if upside >= 0.03:
                label = 1
                break
            # Check if we hit stop loss (-2%)
            if drawdown <= -0.02:
                break

        labels.append({
            'timestamp': df['timestamp'].iloc[i],
            'label': label,
            'max_upside': max_upside,
            'max_drawdown': max_drawdown
        })

    return pd.DataFrame(labels)

def add_insider_features_inline(features_df: pd.DataFrame, stock_id: int, end_date: datetime) -> pd.DataFrame:
    """Add insider features directly to DataFrame without merge"""
    # Initialize all insider feature columns with 0
    feature_cols = [
        'insider_buy_count_30d', 'insider_sell_count_30d',
        'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
        'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
        'cluster_buying_30d', 'insider_buy_at_52w_low',
        'insider_sentiment_30d', 'insider_buy_value_30d', 'insider_sell_value_30d'
    ]
    
    for col in feature_cols:
        features_df[col] = 0
    
    # Fetch insider trades
    query_start = end_date - timedelta(days=90)
    query = text("""
        SELECT trade_date, transaction_type, shares, total_value, insider_title
        FROM insider_trades
        WHERE stock_id = :stock_id
          AND trade_date >= :start_date
          AND trade_date <= :end_date
          AND is_congressional = false
        ORDER BY trade_date ASC
    """)
    
    with engine.connect() as conn:
        trades_df = pd.read_sql(query, conn, params={'stock_id': stock_id, 'start_date': query_start, 'end_date': end_date})
    
    if trades_df.empty:
        return features_df
    
    trades_df['trade_date'] = pd.to_datetime(trades_df['trade_date'])
    
    # Calculate features for each row
    for idx in range(len(features_df)):
        row_date = features_df.iloc[idx]['timestamp']
        lookback_start = row_date - timedelta(days=30)
        
        window_trades = trades_df[
            (trades_df['trade_date'] >= lookback_start) &
            (trades_df['trade_date'] <= row_date)
        ]
        
        if window_trades.empty:
            continue
        
        buys = window_trades[window_trades['transaction_type'] == 'BUY']
        sells = window_trades[window_trades['transaction_type'] == 'SELL']
        
        buy_count = len(buys)
        sell_count = len(sells)
        buy_volume = int(buys['shares'].sum()) if not buys.empty else 0
        buy_value = float(buys['total_value'].sum()) if not buys.empty else 0.0
        sell_value = float(sells['total_value'].sum()) if not sells.empty else 0.0
        
        total = buy_count + sell_count
        net_ratio = (buy_count - sell_count) / total if total > 0 else 0
        
        # Executive checks
        titles = buys['insider_title'].fillna('').tolist()
        ceo = 1 if any('CEO' in t for t in titles) else 0
        cto = 1 if any('CTO' in t or 'Chief Technology' in t for t in titles) else 0
        cfo = 1 if any('CFO' in t or 'Chief Financial' in t for t in titles) else 0
        
        features_df.iloc[idx, features_df.columns.get_loc('insider_buy_count_30d')] = buy_count
        features_df.iloc[idx, features_df.columns.get_loc('insider_sell_count_30d')] = sell_count
        features_df.iloc[idx, features_df.columns.get_loc('insider_buy_volume_30d')] = buy_volume
        features_df.iloc[idx, features_df.columns.get_loc('insider_net_buy_ratio_30d')] = net_ratio
        features_df.iloc[idx, features_df.columns.get_loc('ceo_bought_30d')] = ceo
        features_df.iloc[idx, features_df.columns.get_loc('cto_bought_30d')] = cto
        features_df.iloc[idx, features_df.columns.get_loc('cfo_bought_30d')] = cfo
        features_df.iloc[idx, features_df.columns.get_loc('cluster_buying_30d')] = 1 if buy_count >= 3 else 0
        features_df.iloc[idx, features_df.columns.get_loc('insider_buy_at_52w_low')] = 1 if buy_count > 0 else 0
        features_df.iloc[idx, features_df.columns.get_loc('insider_sentiment_30d')] = 1 if buy_count > sell_count else (0 if sell_count > buy_count else 0.5)
        features_df.iloc[idx, features_df.columns.get_loc('insider_buy_value_30d')] = buy_value
        features_df.iloc[idx, features_df.columns.get_loc('insider_sell_value_30d')] = sell_value
    
    return features_df


def main():
    print("=" * 70)
    print("Feature Engineering: 40 Features (28 Technical + 12 Insider)")
    print("=" * 70)

    # Get stocks
    db = SessionLocal()
    stocks = db.execute(text("SELECT id, symbol FROM stocks WHERE is_tracked = true ORDER BY symbol")).fetchall()
    db.close()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*5)

    print(f"Processing {len(stocks)} stocks...")

    all_data = []

    for stock_id, symbol in tqdm(stocks, desc="Creating features"):
        try:
            # Fetch prices
            query_start = start_date - timedelta(days=300)
            query = text("""
                SELECT timestamp, open, high, low, close, volume
                FROM stock_prices
                WHERE stock_id = :stock_id
                  AND timeframe = '1d'
                  AND timestamp >= :start_date
                  AND timestamp <= :end_date
                ORDER BY timestamp ASC
            """)

            with engine.connect() as conn:
                prices_df = pd.read_sql(query, conn, params={'stock_id': stock_id, 'start_date': query_start, 'end_date': end_date})

            if prices_df.empty:
                continue

            prices_df['timestamp'] = pd.to_datetime(prices_df['timestamp'])

            # Calculate technical features using the working method
            prices_df = TechnicalIndicators.calculate_all_indicators(prices_df)

            # Filter to main date range
            prices_df = prices_df[prices_df['timestamp'] >= start_date].copy()

            if prices_df.empty:
                continue

            # Add insider features
            prices_df = add_insider_features_inline(prices_df, stock_id, end_date)

            # Add identifiers
            prices_df['stock_id'] = stock_id
            prices_df['symbol'] = symbol

            all_data.append(prices_df)

        except Exception as e:
            print(f"  {symbol}: ERROR - {str(e)[:80]}")
            continue

    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)

        # Create labels for each stock
        all_labels = []
        for stock_id in tqdm(final_df['stock_id'].unique(), desc="Creating labels"):
            stock_data = final_df[final_df['stock_id'] == stock_id].copy()
            stock_labels = create_labels(stock_data)
            stock_labels['stock_id'] = stock_id
            all_labels.append(stock_labels)

        labels_df = pd.concat(all_labels, ignore_index=True)

        # Define label columns to exclude from features
        label_cols = ['stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown']
        feature_cols = [col for col in final_df.columns if col not in label_cols + ['symbol']]

        # Save features (without label columns or symbol)
        features_output = final_df[['stock_id', 'timestamp'] + feature_cols].copy()

        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        features_path = f"/app/outputs/features/features_{timestamp}.parquet"
        labels_path = f"/app/outputs/features/labels_{timestamp}.parquet"

        features_output.to_parquet(features_path, index=False)
        labels_df.to_parquet(labels_path, index=False)

        print(f"\\nSaved {len(features_output)} features to {features_path}")
        print(f"Saved {len(labels_df)} labels to {labels_path}")
        print(f"\\nFeature columns: {len(feature_cols)}")
        print(f"Positive class: {labels_df['label'].mean()*100:.1f}%")

    print("\\nDone!")


if __name__ == "__main__":
    main()
