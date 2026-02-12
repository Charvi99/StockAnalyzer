#!/usr/bin/env python3
"""
Unified Label Creator for StockAnalyzer ML Pipeline

This is THE SINGLE label creation script supporting all classification types:
- binary: BUY/DON'T BUY
- 3class: SELL/HOLD/BUY
- 5class: STRONG SELL/SELL/HOLD/BUY/STRONG BUY

Each type uses different strategies:
- Binary: Swing trading with profit target/stop loss
- 3-Class: Simplified multi-class with wider thresholds
- 5-Class: Professional multi-timeframe with final return + risk penalty

Usage:
    # Binary classification
    python scripts/create_labels.py --type binary

    # 3-Class classification
    python scripts/create_labels.py --type 3class

    # 5-Class classification
    python scripts/create_labels.py --type 5class
"""

import sys
import os
import argparse
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

# Class names for output
CLASS_NAMES = {
    'binary': {0: "DON'T BUY", 1: 'BUY'},
    '3class': {0: 'SELL', 1: 'HOLD', 2: 'BUY'},
    '5class': {0: 'STRONG SELL', 1: 'SELL', 2: 'HOLD', 3: 'BUY', 4: 'STRONG BUY'}
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


def create_binary_labels(
    stock_id: int,
    start_date: datetime,
    end_date: datetime,
    profit_target: float = 0.03,
    stop_loss: float = -0.02,
    lookahead: int = 20
) -> pd.DataFrame:
    """
    Create binary swing trading labels

    For each day, checks if stock hits:
    - +profit_target within next lookahead days → BUY (1)
    - -stop_loss before hitting +profit_target → DON'T BUY (0)
    - Neither within lookahead days → DON'T BUY (0)
    """
    extended_end = end_date + timedelta(days=lookahead + 5)
    prices = get_stock_prices(stock_id, start_date - timedelta(days=50), extended_end)

    if prices is None or len(prices) < lookahead:
        return None

    labels = []

    for i in tqdm(range(len(prices) - lookahead - 1), desc=f"Stock {stock_id}", leave=False):
        current_date = prices.iloc[i]['timestamp']
        current_price = prices.iloc[i]['close']

        # Only create labels for dates in range
        if current_date < start_date or current_date > end_date:
            continue

        # Look ahead
        future_prices = prices.iloc[i+1:i+lookahead+1]['close'].values

        # Calculate max upside and max drawdown
        max_upside = np.max((future_prices - current_price) / current_price)
        max_drawdown = np.min((future_prices - current_price) / current_price)

        # Determine label
        if max_upside >= profit_target and max_drawdown > stop_loss:
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


def create_3class_labels(
    stock_id: int,
    start_date: datetime,
    end_date: datetime,
    sell_threshold: float = -0.05,
    buy_threshold: float = 0.05,
    lookaheads: list = [20, 30, 40]
) -> pd.DataFrame:
    """
    Create 3-class labels: SELL/HOLD/BUY

    Uses final return approach with simplified thresholds:
    - SELL: return < sell_threshold (-5%)
    - HOLD: between sell_threshold and buy_threshold (-5% to +5%)
    - BUY: return > buy_threshold (+5%)
    """
    max_lookahead = max(lookaheads)
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

        for lookahead in lookaheads:
            future_prices = prices.iloc[i+1:i+lookahead+1]['close'].values

            if len(future_prices) < lookahead:
                row[f'label_{lookahead}d'] = 1  # HOLD
                row[f'final_return_{lookahead}d'] = 0.0
                continue

            # Final return (where stock ends up)
            final_return = (future_prices[-1] - current_price) / current_price
            row[f'final_return_{lookahead}d'] = final_return

            # Classify by thresholds
            if final_return <= sell_threshold:
                label_class = 0  # SELL
            elif final_return >= buy_threshold:
                label_class = 2  # BUY
            else:
                label_class = 1  # HOLD

            row[f'label_{lookahead}d'] = label_class

        labels.append(row)

    return pd.DataFrame(labels)


def create_5class_labels(
    stock_id: int,
    start_date: datetime,
    end_date: datetime,
    strong_sell_threshold: float = -0.10,
    sell_threshold: float = -0.05,
    buy_threshold: float = 0.05,
    strong_buy_threshold: float = 0.10,
    lookaheads: list = [20, 30, 40]
) -> pd.DataFrame:
    """
    Create 5-class labels: STRONG SELL/SELL/HOLD/BUY/STRONG BUY

    Uses FINAL RETURN with risk penalty:
    Score = Final Return (%) - 0.3 * |Max Drawdown| (if drawdown < -3%)

    Class thresholds:
    - STRONG SELL: score <= strong_sell_threshold (-10%)
    - SELL: strong_sell_threshold < score <= sell_threshold (-10% to -5%)
    - HOLD: sell_threshold < score <= buy_threshold (-5% to +5%)
    - BUY: buy_threshold < score <= strong_buy_threshold (+5% to +10%)
    - STRONG BUY: score > strong_buy_threshold (>+10%)
    """
    max_lookahead = max(lookaheads)
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

        for lookahead in lookaheads:
            future_prices = prices.iloc[i+1:i+lookahead+1]['close'].values

            if len(future_prices) < lookahead:
                row[f'label_{lookahead}d'] = 2  # HOLD
                row[f'final_return_{lookahead}d'] = 0.0
                row[f'max_upside_{lookahead}d'] = 0.0
                row[f'max_drawdown_{lookahead}d'] = 0.0
                continue

            # Final return (where stock ends up)
            final_return = (future_prices[-1] - current_price) / current_price

            # Track max upside/drawdown for analysis
            max_upside = np.max((future_prices - current_price) / current_price)
            max_drawdown = np.min((future_prices - current_price) / current_price)

            row[f'final_return_{lookahead}d'] = final_return
            row[f'max_upside_{lookahead}d'] = max_upside
            row[f'max_drawdown_{lookahead}d'] = max_drawdown

            # Calculate score: final return minus risk penalty
            # Risk penalty only applies if drawdown < -3%
            risk_penalty = 0
            if max_drawdown < -0.03:
                risk_penalty = 0.3 * abs(max_drawdown)

            score = final_return - risk_penalty
            row[f'score_{lookahead}d'] = score

            # Classify by thresholds
            if score <= strong_sell_threshold:
                label_class = 0  # STRONG SELL
            elif score <= sell_threshold:
                label_class = 1  # SELL
            elif score <= buy_threshold:
                label_class = 2  # HOLD
            elif score <= strong_buy_threshold:
                label_class = 3  # BUY
            else:
                label_class = 4  # STRONG BUY

            row[f'label_{lookahead}d'] = label_class

        labels.append(row)

    return pd.DataFrame(labels)


def main():
    parser = argparse.ArgumentParser(
        description='Unified Label Creator for StockAnalyzer ML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Binary classification (default: 3% target, -2% stop, 20d lookahead)
  python scripts/create_labels.py --type binary

  # Binary with custom parameters
  python scripts/create_labels.py --type binary --profit-target 0.05 --stop-loss -0.03 --lookahead 30

  # 3-Class classification (default: -5% to +5% HOLD zone)
  python scripts/create_labels.py --type 3class

  # 3-Class with custom thresholds
  python scripts/create_labels.py --type 3class --sell-threshold -0.03 --buy-threshold 0.03

  # 5-Class classification (default: 10% thresholds, multi-timeframe)
  python scripts/create_labels.py --type 5class

  # 5-Class with single timeframe
  python scripts/create_labels.py --type 5class --lookaheads 20
        """
    )

    parser.add_argument(
        '--type',
        type=str,
        required=True,
        choices=['binary', '3class', '5class'],
        help='Label type to create'
    )

    # Binary-specific parameters
    parser.add_argument('--profit-target', type=float, default=0.03,
                        help='Profit target for binary (default: 0.03 = 3%%)')
    parser.add_argument('--stop-loss', type=float, default=-0.02,
                        help='Stop loss for binary (default: -0.02 = -2%%)')
    parser.add_argument('--lookahead', type=int, default=20,
                        help='Lookahead days for binary (default: 20)')

    # 3-class parameters
    parser.add_argument('--sell-threshold', type=float, default=-0.05,
                        help='Sell threshold for 3class (default: -0.05 = -5%%)')
    parser.add_argument('--buy-threshold', type=float, default=0.05,
                        help='Buy threshold for 3class (default: 0.05 = 5%%)')

    # 5-class parameters
    parser.add_argument('--strong-sell-threshold', type=float, default=-0.10,
                        help='Strong sell threshold for 5class (default: -0.10 = -10%%)')
    parser.add_argument('--strong-buy-threshold', type=float, default=0.10,
                        help='Strong buy threshold for 5class (default: 0.10 = 10%%)')

    # Multi-timeframe parameters
    parser.add_argument('--lookaheads', type=int, nargs='+', default=[20, 30, 40],
                        help='Lookahead days for multi-class (default: 20 30 40)')

    # Dataset folder
    parser.add_argument('--dataset-folder', type=str, default=None,
                        help='Dataset folder name (e.g., dataset_20260204_185139). Auto-detects latest if not specified.')

    # Data range
    parser.add_argument('--days', type=int, default=2920,
                        help='Number of days of history to use (default: 2920 = 8 years, 2018-2025)')

    args = parser.parse_args()

    print("=" * 70)
    print(f"StockAnalyzer ML - Label Creator: {args.type.upper()}")
    print("=" * 70)

    # Print configuration
    if args.type == 'binary':
        print(f"\nBinary Classification:")
        print(f"  Profit Target: +{args.profit_target*100:.1f}%")
        print(f"  Stop Loss: {args.stop_loss*100:.1f}%")
        print(f"  Lookahead: {args.lookahead} days")
    elif args.type == '3class':
        print(f"\n3-Class Classification:")
        print(f"  SELL: < {args.sell_threshold*100:.1f}%")
        print(f"  HOLD: {args.sell_threshold*100:.1f}% to {args.buy_threshold*100:.1f}%")
        print(f"  BUY: > {args.buy_threshold*100:.1f}%")
        print(f"  Lookaheads: {args.lookaheads}")
    else:  # 5class
        print(f"\n5-Class Classification:")
        print(f"  STRONG SELL: <= {args.strong_sell_threshold*100:.1f}%")
        print(f"  SELL: {args.strong_sell_threshold*100:.1f}% to {args.sell_threshold*100:.1f}%")
        print(f"  HOLD: {args.sell_threshold*100:.1f}% to {args.buy_threshold*100:.1f}%")
        print(f"  BUY: {args.buy_threshold*100:.1f}% to {args.strong_buy_threshold*100:.1f}%")
        print(f"  STRONG BUY: > {args.strong_buy_threshold*100:.1f}%")
        print(f"  Lookaheads: {args.lookaheads}")

    # ============================================================
    # FIND DATASET FOLDER
    # ============================================================

    outputs_dir = Path('/app/outputs/features')
    outputs_dir.mkdir(parents=True, exist_ok=True)

    if args.dataset_folder:
        dataset_folder = outputs_dir / args.dataset_folder
        if not dataset_folder.exists():
            print(f"\n❌ Dataset folder not found: {dataset_folder}")
            print(f"   Available folders:")
            for folder in sorted(outputs_dir.glob('dataset_*')):
                print(f"   - {folder.name}")
            return
    else:
        # Auto-detect latest dataset folder
        dataset_folders = sorted(outputs_dir.glob('dataset_*'), reverse=True)
        if not dataset_folders:
            print("\n❌ No dataset folders found!")
            print("   Run feature engineering first:")
            print("   python scripts/feature_engineering.py")
            return
        dataset_folder = dataset_folders[0]
        print(f"\n📂 Auto-detected dataset folder: {dataset_folder.name}")

    # Verify features.parquet exists
    features_file = dataset_folder / 'features.parquet'
    if not features_file.exists():
        print(f"\n❌ features.parquet not found in {dataset_folder.name}")
        return

    print(f"   Features: {features_file.name}")

    # Get date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)

    # Get all tracked stocks
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM stocks WHERE is_tracked = true"))
        stock_ids = [row[0] for row in result]

    print(f"\n📊 Found {len(stock_ids)} tracked stocks")
    print(f"📅 Date range: {start_date.date()} to {end_date.date()}")

    # Create labels for each stock
    all_labels = []

    print(f"\n🔄 Creating labels...")
    for stock_id in stock_ids:
        try:
            if args.type == 'binary':
                labels = create_binary_labels(
                    stock_id, start_date, end_date,
                    profit_target=args.profit_target,
                    stop_loss=args.stop_loss,
                    lookahead=args.lookahead
                )
            elif args.type == '3class':
                labels = create_3class_labels(
                    stock_id, start_date, end_date,
                    sell_threshold=args.sell_threshold,
                    buy_threshold=args.buy_threshold,
                    lookaheads=args.lookaheads
                )
            else:  # 5class
                labels = create_5class_labels(
                    stock_id, start_date, end_date,
                    strong_sell_threshold=args.strong_sell_threshold,
                    sell_threshold=args.sell_threshold,
                    buy_threshold=args.buy_threshold,
                    strong_buy_threshold=args.strong_buy_threshold,
                    lookaheads=args.lookaheads
                )

            if labels is not None and not labels.empty:
                all_labels.append(labels)
        except Exception as e:
            print(f"\n❌ Error creating labels for stock {stock_id}: {e}")

    # Combine all labels
    if not all_labels:
        print("\n❌ No labels created!")
        return

    df = pd.concat(all_labels, ignore_index=True)

    # Save to dataset folder
    output_file = dataset_folder / f'labels_{args.type}.parquet'
    df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved {len(df):,} label rows to {dataset_folder.name}/")
    print(f"   File: {output_file.name}")

    # Print statistics
    print(f"\n📊 Label Statistics:")

    if args.type == 'binary':
        label_col = 'label'
        distribution = df[label_col].value_counts().sort_index()
        for class_id, count in distribution.items():
            pct = count / len(df) * 100
            print(f"  {CLASS_NAMES[args.type][class_id]:15} {count:7,} ({pct:5.1f}%)")
    else:
        for lookahead in (args.lookaheads if args.type != 'binary' else [args.lookahead]):
            label_col = f'label_{lookahead}d'
            if label_col not in df.columns:
                continue

            print(f"\n{lookahead}-DAY Distribution:")
            distribution = df[label_col].value_counts().sort_index()
            for class_id, count in distribution.items():
                pct = count / len(df) * 100
                print(f"  {CLASS_NAMES[args.type][class_id]:15} {count:7,} ({pct:5.1f}%)")

    # Show available labels in dataset folder
    print(f"\n📂 Dataset folder contents:")
    label_files = sorted(dataset_folder.glob('labels_*.parquet'))
    if label_files:
        for label_file in label_files:
            print(f"   ✓ {label_file.name}")
    else:
        print(f"   (only labels_{args.type}.parquet exists)")

    print(f"\n💡 Train with this dataset:")
    print(f"   python train.py --dataset-folder {dataset_folder.name} --label-type {args.type}")


if __name__ == "__main__":
    main()
