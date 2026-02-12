"""
Create Multi-Class Multi-Timeframe Labels - PROFESSIONAL VERSION

Uses FINAL RETURN (price at end of period) not MAX upside.
This gives more realistic distribution because stocks that hit +10% then fall to +2%
will be classified as HOLD, not STRONG BUY.

Classification uses SCORE-BASED approach:
  Score = Final Return + Risk Penalty
  Risk Penalty = 0.3 * |Max Drawdown| (if drawdown > 3%)

Classes determined by score percentiles for balance.

Usage:
    python create_multiclass_labels.py
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from tqdm import tqdm

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass@db:5432/stockanalyzer')
engine = create_engine(DATABASE_URL)

CLASS_NAMES = {
    0: 'STRONG SELL',
    1: 'SELL',
    2: 'HOLD',
    3: 'BUY',
    4: 'STRONG BUY'
}


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


def create_multiclass_labels(
    stock_id: int,
    start_date: datetime,
    end_date: datetime,
    max_lookahead: int = 40,
    score_percentiles: dict = None
) -> pd.DataFrame:
    """
    Create labels using FINAL RETURN (not max upside)

    Score = Final Return (%) - Risk Penalty
    Risk Penalty = 0.3 * |Max Drawdown| (if drawdown < -3%)

    This penalizes volatile stocks even if they end up positive.
    """
    extended_end = end_date + timedelta(days=max_lookahead + 10)
    prices = get_stock_prices(stock_id, start_date - timedelta(days=10), extended_end)

    if prices is None or len(prices) < max_lookahead + 10:
        return None

    labels = []

    for i in tqdm(range(len(prices) - max_lookahead - 1), desc=f"Stock {stock_id}", leave=False):
        current_date = prices.iloc[i]['timestamp']
        current_price = prices.iloc[i]['close']

        if current_date < start_date or current_date > end_date:
            continue

        row = {'timestamp': current_date, 'stock_id': stock_id}

        for lookahead in [20, 30, 40]:
            future_prices = prices.iloc[i+1:i+lookahead+1]['close'].values

            if len(future_prices) < lookahead:
                row[f'label_{lookahead}d'] = 2
                row[f'final_return_{lookahead}d'] = 0.0
                row[f'max_upside_{lookahead}d'] = 0.0
                row[f'max_drawdown_{lookahead}d'] = 0.0
                continue

            # Final return (where stock ends up)
            final_return = ((future_prices[-1] - current_price) / current_price) * 100

            # Also track max upside/drawdown for analysis
            max_upside = np.max((future_prices - current_price) / current_price) * 100
            max_drawdown = np.min((future_prices - current_price) / current_price) * 100

            row[f'final_return_{lookahead}d'] = final_return
            row[f'max_upside_{lookahead}d'] = max_upside
            row[f'max_drawdown_{lookahead}d'] = max_drawdown

            # Calculate score: final return minus risk penalty
            # Risk penalty only applies if drawdown < -3%
            risk_penalty = 0
            if max_drawdown < -3.0:
                risk_penalty = 0.3 * abs(max_drawdown)

            score = final_return - risk_penalty
            row[f'score_{lookahead}d'] = score

            # Classify by INDEPENDENT thresholds (not derived from data)
            # Using wide thresholds for realistic distribution:
            # STRONG SELL: score < -10%
            # SELL: -10% to -5%
            # HOLD: -5% to +5%
            # BUY: +5% to +10%
            # STRONG BUY: > +10%

            if score <= -10.0:
                label_class = 0  # STRONG SELL
            elif score <= -5.0:
                label_class = 1  # SELL
            elif score <= 5.0:
                label_class = 2  # HOLD
            elif score <= 10.0:
                label_class = 3  # BUY
            else:
                label_class = 4  # STRONG BUY

            row[f'label_{lookahead}d'] = label_class

        labels.append(row)

    return pd.DataFrame(labels)


def calculate_score_percentiles(stock_ids, start_date, end_date):
    """Calculate score percentiles across all stocks for balanced classification"""
    print("📊 Calculating score percentiles for balanced classification...")

    all_scores = {20: [], 30: [], 40: []}

    for stock_id in stock_ids[:100]:  # Sample first 100 for speed
        extended_end = end_date + timedelta(days=50)
        prices = get_stock_prices(stock_id, start_date - timedelta(days=10), extended_end)

        if prices is None or len(prices) < 50:
            continue

        for i in range(len(prices) - 41):
            current_date = prices.iloc[i]['timestamp']
            if current_date < start_date or current_date > end_date:
                continue

            current_price = prices.iloc[i]['close']

            for lookahead in [20, 30, 40]:
                future_prices = prices.iloc[i+1:i+lookahead+1]['close'].values
                if len(future_prices) < lookahead:
                    continue

                final_return = ((future_prices[-1] - current_price) / current_price) * 100
                max_drawdown = np.min((future_prices - current_price) / current_price) * 100

                risk_penalty = 0
                if max_drawdown < -3.0:
                    risk_penalty = 0.3 * abs(max_drawdown)

                score = final_return - risk_penalty
                all_scores[lookahead].append(score)

    # Calculate percentiles
    percentiles = {}
    for lookahead in [20, 30, 40]:
        scores = np.array(all_scores[lookahead])
        percentiles[f'{lookahead}d'] = {
            'p20': np.percentile(scores, 20),
            'p40': np.percentile(scores, 40),
            'p60': np.percentile(scores, 60),
            'p80': np.percentile(scores, 80),
        }
        print(f"  {lookahead}d: p20={percentiles[f'{lookahead}d']['p20']:.1f}%, "
              f"p40={percentiles[f'{lookahead}d']['p40']:.1f}%, "
              f"p60={percentiles[f'{lookahead}d']['p60']:.1f}%, "
              f"p80={percentiles[f'{lookahead}d']['p80']:.1f}%")

    return percentiles


def main():
    print("=" * 70)
    print("StockAnalyzer ML - Multi-Class Labels (Professional Version)")
    print("=" * 70)

    print("\nStrategy:")
    print("  1. Use FINAL RETURN (not max upside)")
    print("  2. Apply risk penalty for high drawdown")
    print("  3. Classify by score percentiles for balance")
    print("\n  Score = Final Return (%) - 0.3 * |Max Drawdown| (if < -3%)")

    outputs_dir = Path('/app/outputs/features')
    outputs_dir.mkdir(parents=True, exist_ok=True)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=1825)  # 5 YEARS (was 730 days = 2 years)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM stocks WHERE is_tracked = true"))
        stock_ids = [row[0] for row in result]

    print(f"\n📊 Found {len(stock_ids)} tracked stocks")

    # Calculate score percentiles for balanced classification
    score_percentiles = calculate_score_percentiles(stock_ids, start_date, end_date)

    # Create labels WITHOUT percentile forcing
    # Use absolute thresholds based on actual data
    print(f"\n🔄 Creating labels with absolute thresholds (no artificial balance)...")
    all_labels = []

    for stock_id in stock_ids:
        try:
            labels = create_multiclass_labels(stock_id, start_date, end_date,
                                            score_percentiles=None)  # Don't force balance
            if labels is not None and not labels.empty:
                all_labels.append(labels)
        except Exception as e:
            pass

    if not all_labels:
        print("\n❌ No labels created!")
        return

    df = pd.concat(all_labels, ignore_index=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = outputs_dir / f'labels_multiclass_5class_{timestamp_str}.parquet'
    df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved {len(df):,} label rows")

    # Print statistics
    for lookahead in [20, 30, 40]:
        print(f"\n{lookahead}-DAY Distribution:")
        label_col = f'label_{lookahead}d'
        distribution = df[label_col].value_counts().sort_index()

        for class_id, count in distribution.items():
            pct = count / len(df) * 100
            print(f"  {CLASS_NAMES[class_id]:12} {count:7,} ({pct:5.1f}%)")

    print(f"\n📁 Saved to: {output_file}")


if __name__ == "__main__":
    main()
