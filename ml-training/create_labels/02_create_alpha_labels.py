#!/usr/bin/env python3
"""
ALPHA LABEL GENERATION: Predict Stock Outperformance, Not Absolute Returns

Purpose:
    Generate labels based on alpha (outperformance vs SPY) instead of absolute returns.
    This forces the model to learn stock-picking ability instead of market timing.

Key Concepts:
    - Alpha = stock_return - spy_return
    - Label = 1 if alpha >= target (outperforms market)
    - Label = 0 if alpha < target (underperforms market)

Usage:
    # Binary alpha labels (recommended for starting)
    python 02_create_alpha_labels.py --type binary --alpha-target 0.02

    # 5-class alpha labels (for more granular signals)
    python 02_create_alpha_labels.py --type 5class --alpha-target 0.02

    # Using specific dataset
    python 02_create_alpha_labels.py --type binary --dataset-folder dataset_20260204_204134

Parameters:
    --alpha-target: Minimum outperformance to consider "positive" (default: 0.02 = 2%)
    --lookahead: Days to look ahead for returns (default: 20)
    --beta-adjusted: Use CAPM beta adjustment (default: False)

Expected Label Distribution (Binary, 2% target):
    - BUY (outperforms by 2%+):     ~35-40%
    - DON'T BUY (underperforms):     ~60-65%

Expected Label Distribution (5-Class, 1-3% thresholds):
    - STRONG OUTPERFORM (>3%):       ~10%
    - OUTPERFORM (1-3%):            ~25%
    - MARKET PERFORM (-1% to 1%):   ~30%
    - UNDERPERFORM (-3% to -1%):    ~25%
    - STRONG UNDERPERFORM (<-3%):   ~10%

Created: 2026-02-05
Author: ML Team
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from tqdm import tqdm

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass@db:5432/stockanalyzer')
engine = create_engine(DATABASE_URL)


def get_stock_prices(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Fetch stock price data"""
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


def get_spy_prices(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Fetch SPY (market) price data"""
    query = text("""
        SELECT sp.timestamp, sp.close as spy_close
        FROM stock_prices sp
        JOIN stocks s ON sp.stock_id = s.id
        WHERE s.symbol = 'SPY'
          AND sp.timeframe = '1d'
          AND sp.timestamp >= :start_date
          AND sp.timestamp <= :end_date
        ORDER BY sp.timestamp ASC
    """)

    df = pd.read_sql(
        query,
        engine,
        params={'start_date': start_date, 'end_date': end_date}
    )

    if df.empty:
        print("⚠️  No SPY data found")
        return None

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def calculate_beta(stock_prices: pd.DataFrame, spy_prices: pd.DataFrame, window: int = 252) -> float:
    """
    Calculate rolling beta using historical returns

    Beta = Cov(stock_return, spy_return) / Var(spy_return)

    Args:
        stock_prices: Stock price data
        spy_prices: SPY price data (already merged)
        window: Rolling window for beta calculation (default: 252 trading days)

    Returns:
        Beta value (typically 0.5 to 2.0 for most stocks)
    """
    if len(stock_prices) < window:
        return 1.0  # Default to market beta if insufficient data

    # Calculate returns
    stock_returns = stock_prices['close'].pct_change().dropna()
    spy_returns = spy_prices['spy_close'].pct_change().dropna()

    # Align
    aligned_stock, aligned_spy = stock_returns.align(spy_returns, join='inner')

    if len(aligned_stock) < 50:
        return 1.0

    # Calculate beta
    covariance = np.cov(aligned_stock, aligned_spy)[0, 1]
    spy_variance = np.var(aligned_spy)

    if spy_variance == 0:
        return 1.0

    beta = covariance / spy_variance

    # Clip extreme values
    beta = max(0.1, min(3.0, beta))

    return beta


def create_alpha_binary_labels(
    stock_id: int,
    start_date: datetime,
    end_date: datetime,
    spy_prices: pd.DataFrame,
    alpha_target: float = 0.02,
    lookahead: int = 20,
    beta_adjusted: bool = False
) -> pd.DataFrame:
    """
    Create binary labels based on alpha (outperformance vs market)

    Logic:
        1. Calculate stock return over lookahead period
        2. Calculate SPY return over same period
        3. Alpha = stock_return - spy_return
        4. If beta_adjusted: Alpha = stock_return - (beta * spy_return)
        5. Label = 1 if alpha >= alpha_target, else 0

    Args:
        stock_id: Database ID of stock
        start_date: Start date for label generation
        end_date: End date for label generation
        spy_prices: SPY price data
        alpha_target: Required outperformance (default: 0.02 = 2%)
        lookahead: Days to look ahead
        beta_adjusted: Use CAPM beta adjustment

    Returns:
        DataFrame with alpha-based labels
    """
    # Fetch extended stock data
    extended_end = end_date + timedelta(days=lookahead + 10)
    extended_start = start_date - timedelta(days=300 if beta_adjusted else 10)

    stock_prices = get_stock_prices(stock_id, extended_start, extended_end)

    if stock_prices is None or len(stock_prices) < lookahead:
        return None

    # Merge with SPY data
    merged = pd.merge(
        stock_prices,
        spy_prices,
        on='timestamp',
        how='inner',
        suffixes=('', '_spy')
    )

    if len(merged) < lookahead:
        return None

    labels = []

    for i in tqdm(range(len(merged) - lookahead), desc=f"Stock {stock_id}", leave=False):
        current_date = merged.iloc[i]['timestamp']

        # Only create labels for dates in range
        if current_date < start_date or current_date > end_date:
            continue

        # Current prices
        current_stock_price = merged.iloc[i]['close']
        current_spy_price = merged.iloc[i]['spy_close']

        # Future prices
        future_stock_price = merged.iloc[i + lookahead]['close']
        future_spy_price = merged.iloc[i + lookahead]['spy_close']

        # Calculate returns
        stock_return = (future_stock_price - current_stock_price) / current_stock_price
        spy_return = (future_spy_price - current_spy_price) / current_spy_price

        # Calculate ALPHA
        if beta_adjusted and i >= 252:
            # Calculate historical beta
            historical_stock = merged.iloc[i-252:i]['close'].pct_change().dropna()
            historical_spy = merged.iloc[i-252:i]['spy_close'].pct_change().dropna()

            if len(historical_stock) > 50 and len(historical_spy) > 50:
                beta = np.cov(historical_stock, historical_spy)[0, 1] / np.var(historical_spy)
                beta = max(0.1, min(3.0, beta))  # Clip
            else:
                beta = 1.0

            # CAPM: Expected return = beta * market_return
            expected_return = beta * spy_return
            alpha = stock_return - expected_return
        else:
            # Simple alpha: stock return - market return
            alpha = stock_return - spy_return
            beta = 1.0

        # Create label based on alpha
        label = 1 if alpha >= alpha_target else 0

        labels.append({
            'timestamp': current_date,
            'stock_id': stock_id,
            'label': label,
            'stock_return': stock_return,
            'spy_return': spy_return,
            'alpha': alpha,
            'beta': beta if beta_adjusted else None
        })

    return pd.DataFrame(labels)


def create_alpha_3class_labels(
    stock_id: int,
    start_date: datetime,
    end_date: datetime,
    spy_prices: pd.DataFrame,
    outperform: float = 0.02,
    underperform: float = -0.02,
    lookahead: int = 20,
    beta_adjusted: bool = False
) -> pd.DataFrame:
    """
    Create 3-class labels based on alpha magnitude

    Classes:
        2: OUTPERFORM / BUY (alpha >= outperform)
        1: MARKET PERFORM / HOLD (underperform <= alpha < outperform)
        0: UNDERPERFORM / SELL (alpha < underperform)

    Args:
        stock_id: Database ID of stock
        start_date: Start date for label generation
        end_date: End date for label generation
        spy_prices: SPY price data
        outperform: Outperform threshold (default: 2%)
        underperform: Underperform threshold (default: -2%)
        lookahead: Days to look ahead
        beta_adjusted: Use CAPM beta adjustment

    Returns:
        DataFrame with 3-class alpha labels
    """
    # Use same logic as binary, but 3 classes instead of 2
    extended_end = end_date + timedelta(days=lookahead + 10)
    extended_start = start_date - timedelta(days=300 if beta_adjusted else 10)

    stock_prices = get_stock_prices(stock_id, extended_start, extended_end)

    if stock_prices is None or len(stock_prices) < lookahead:
        return None

    merged = pd.merge(
        stock_prices,
        spy_prices,
        on='timestamp',
        how='inner',
        suffixes=('', '_spy')
    )

    if len(merged) < lookahead:
        return None

    labels = []

    for i in tqdm(range(len(merged) - lookahead), desc=f"Stock {stock_id}", leave=False):
        current_date = merged.iloc[i]['timestamp']

        if current_date < start_date or current_date > end_date:
            continue

        # Calculate returns
        stock_return = (merged.iloc[i + lookahead]['close'] - merged.iloc[i]['close']) / merged.iloc[i]['close']
        spy_return = (merged.iloc[i + lookahead]['spy_close'] - merged.iloc[i]['spy_close']) / merged.iloc[i]['spy_close']

        # Calculate alpha
        if beta_adjusted and i >= 252:
            historical_stock = merged.iloc[i-252:i]['close'].pct_change().dropna()
            historical_spy = merged.iloc[i-252:i]['spy_close'].pct_change().dropna()

            if len(historical_stock) > 50:
                beta = np.cov(historical_stock, historical_spy)[0, 1] / np.var(historical_spy)
                beta = max(0.1, min(3.0, beta))
            else:
                beta = 1.0

            alpha = stock_return - (beta * spy_return)
        else:
            alpha = stock_return - spy_return

        # Classify by alpha magnitude (3 classes)
        if alpha >= outperform:
            label = 2  # OUTPERFORM / BUY
        elif alpha >= underperform:
            label = 1  # MARKET PERFORM / HOLD
        else:
            label = 0  # UNDERPERFORM / SELL

        labels.append({
            'timestamp': current_date,
            'stock_id': stock_id,
            'label': label,
            'stock_return': stock_return,
            'spy_return': spy_return,
            'alpha': alpha
        })

    return pd.DataFrame(labels)


def create_alpha_5class_labels(
    stock_id: int,
    start_date: datetime,
    end_date: datetime,
    spy_prices: pd.DataFrame,
    strong_outperform: float = 0.03,
    outperform: float = 0.01,
    market_perform: float = -0.01,
    underperform: float = -0.03,
    lookahead: int = 20,
    beta_adjusted: bool = False
) -> pd.DataFrame:
    """
    Create 5-class labels based on alpha magnitude

    Classes:
        4: STRONG OUTPERFORM (alpha >= strong_outperform)
        3: OUTPERFORM (outperform <= alpha < strong_outperform)
        2: MARKET PERFORM (market_perform <= alpha < outperform)
        1: UNDERPERFORM (underperform <= alpha < market_perform)
        0: STRONG UNDERPERFORM (alpha < underperform)

    Args:
        stock_id: Database ID of stock
        start_date: Start date for label generation
        end_date: End date for label generation
        spy_prices: SPY price data
        strong_outperform: Strong outperform threshold (default: 3%)
        outperform: Outperform threshold (default: 1%)
        market_perform: Market perform lower bound (default: -1%)
        underperform: Underperform threshold (default: -3%)
        lookahead: Days to look ahead
        beta_adjusted: Use CAPM beta adjustment

    Returns:
        DataFrame with 5-class alpha labels
    """
    # Use same logic as binary, but 5 classes instead of 2
    extended_end = end_date + timedelta(days=lookahead + 10)
    extended_start = start_date - timedelta(days=300 if beta_adjusted else 10)

    stock_prices = get_stock_prices(stock_id, extended_start, extended_end)

    if stock_prices is None or len(stock_prices) < lookahead:
        return None

    merged = pd.merge(
        stock_prices,
        spy_prices,
        on='timestamp',
        how='inner',
        suffixes=('', '_spy')
    )

    if len(merged) < lookahead:
        return None

    labels = []

    for i in tqdm(range(len(merged) - lookahead), desc=f"Stock {stock_id}", leave=False):
        current_date = merged.iloc[i]['timestamp']

        if current_date < start_date or current_date > end_date:
            continue

        # Calculate returns
        stock_return = (merged.iloc[i + lookahead]['close'] - merged.iloc[i]['close']) / merged.iloc[i]['close']
        spy_return = (merged.iloc[i + lookahead]['spy_close'] - merged.iloc[i]['spy_close']) / merged.iloc[i]['spy_close']

        # Calculate alpha
        if beta_adjusted and i >= 252:
            historical_stock = merged.iloc[i-252:i]['close'].pct_change().dropna()
            historical_spy = merged.iloc[i-252:i]['spy_close'].pct_change().dropna()

            if len(historical_stock) > 50:
                beta = np.cov(historical_stock, historical_spy)[0, 1] / np.var(historical_spy)
                beta = max(0.1, min(3.0, beta))
            else:
                beta = 1.0

            alpha = stock_return - (beta * spy_return)
        else:
            alpha = stock_return - spy_return

        # Classify by alpha magnitude
        if alpha >= strong_outperform:
            label = 4  # STRONG OUTPERFORM
        elif alpha >= outperform:
            label = 3  # OUTPERFORM
        elif alpha >= market_perform:
            label = 2  # MARKET PERFORM
        elif alpha >= underperform:
            label = 1  # UNDERPERFORM
        else:
            label = 0  # STRONG UNDERPERFORM

        labels.append({
            'timestamp': current_date,
            'stock_id': stock_id,
            'label': label,
            'stock_return': stock_return,
            'spy_return': spy_return,
            'alpha': alpha
        })

    return pd.DataFrame(labels)


def main():
    parser = argparse.ArgumentParser(
        description='Generate alpha-based labels (outperformance vs market)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Binary alpha labels (2% outperformance target)
    python 02_create_alpha_labels.py --type binary --alpha-target 0.02

    # Binary with more aggressive target (3%)
    python 02_create_alpha_labels.py --type binary --alpha-target 0.03

    # 5-class alpha labels
    python 02_create_alpha_labels.py --type 5class

    # Beta-adjusted alpha labels (accounts for stock beta)
    python 02_create_alpha_labels.py --type binary --beta-adjusted

    # Specific dataset folder
    python 02_create_alpha_labels.py --type binary --dataset-folder dataset_20260204_204134

Label Types:
    binary: BUY (1) if stock beats SPY by target%, DON'T BUY (0) otherwise
    5class: STRONG UNDERPERFORM / UNDERPERFORM / MARKET PERFORM / OUTPERFORM / STRONG OUTPERFORM

Parameters:
    alpha-target: Minimum outperformance for positive label (default: 0.02 = 2%%)
    lookahead: Days to look ahead for returns (default: 20)
    beta-adjusted: Use CAPM to adjust for stock beta (default: False)
        """
    )

    parser.add_argument(
        '--type',
        type=str,
        required=True,
        choices=['binary', '3class', '5class'],
        help='Label type to create'
    )

    parser.add_argument(
        '--dataset-folder',
        type=str,
        default=None,
        help='Dataset folder name (auto-detects latest if not specified)'
    )

    parser.add_argument(
        '--alpha-target',
        type=float,
        default=0.02,
        help='Alpha target for binary labels (default: 0.02 = 2%%)'
    )

    parser.add_argument(
        '--lookahead',
        type=int,
        default=20,
        help='Lookahead days (default: 20)'
    )

    parser.add_argument(
        '--beta-adjusted',
        action='store_true',
        help='Use CAPM beta adjustment for alpha calculation'
    )

    parser.add_argument(
        '--strong-outperform',
        type=float,
        default=0.03,
        help='Strong outperform threshold for 5-class (default: 0.03)'
    )

    parser.add_argument(
        '--outperform',
        type=float,
        default=0.01,
        help='Outperform threshold for 5-class (default: 0.01)'
    )

    parser.add_argument(
        '--market-perform',
        type=float,
        default=-0.01,
        help='Market perform threshold for 5-class (default: -0.01)'
    )

    parser.add_argument(
        '--underperform',
        type=float,
        default=-0.03,
        help='Underperform threshold for 5-class (default: -0.03)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print(" " * 20)
    print(f"ALPHA LABEL GENERATOR: {args.type.upper()}")
    print(" " * 20)
    print("=" * 70)

    # Print configuration
    if args.type == 'binary':
        print(f"\nBinary Alpha Classification:")
        print(f"  Alpha Target: +{args.alpha_target*100:.1f}% (stock beats SPY)")
        print(f"  Lookahead: {args.lookahead} days")
        print(f"  Beta Adjusted: {args.beta_adjusted}")
    elif args.type == '3class':
        print(f"\n3-Class Alpha Classification:")
        print(f"  BUY / OUTPERFORM: ≥ +{args.alpha_target*100:.1f}%")
        print(f"  HOLD / MARKET PERFORM: {args.alpha_target*100:.1f}% to -{args.alpha_target*100:.1f}%")
        print(f"  SELL / UNDERPERFORM: < -{args.alpha_target*100:.1f}%")
        print(f"  Lookahead: {args.lookahead} days")
        print(f"  Beta Adjusted: {args.beta_adjusted}")
    else:  # 5class
        print(f"\n5-Class Alpha Classification:")
        print(f"  STRONG OUTPERFORM: ≥ +{args.strong_outperform*100:.1f}%")
        print(f"  OUTPERFORM: +{args.outperform*100:.1f}% to +{args.strong_outperform*100:.1f}%")
        print(f"  MARKET PERFORM: {args.market_perform*100:.1f}% to +{args.outperform*100:.1f}%")
        print(f"  UNDERPERFORM: {args.underperform*100:.1f}% to {args.market_perform*100:.1f}%")
        print(f"  STRONG UNDERPERFORM: < {args.underperform*100:.1f}%")
        print(f"  Lookahead: {args.lookahead} days")
        print(f"  Beta Adjusted: {args.beta_adjusted}")

    # Find dataset folder
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
            return
        dataset_folder = dataset_folders[0]
        print(f"\n📂 Auto-detected dataset folder: {dataset_folder.name}")

    # Get date range from dataset
    metadata_file = dataset_folder / 'metadata.json'

    # Try to infer date range from features file
    features_file = dataset_folder / 'features.parquet'
    if features_file.exists():
        features_df_temp = pd.read_parquet(features_file)
        end_date = features_df_temp['timestamp'].max()
        start_date = features_df_temp['timestamp'].min()
        # Ensure they are datetime
        if hasattr(end_date, 'to_pydatetime'):
            end_date = end_date.to_pydatetime()
        if hasattr(start_date, 'to_pydatetime'):
            start_date = start_date.to_pydatetime()
    else:
        end_date = datetime.now()
        start_date = datetime(2018, 1, 1)  # Extended to 2018 for 8 years of data

    print(f"📅 Date range: {start_date.date()} to {end_date.date()} ({(end_date - start_date).days // 365} years)")
    print(f"  Including: 2018-2020 (trade war, corrections, COVID)")
    print(f"             2021-2025 (bull market)")

    # Load SPY data (needed for alpha calculation)
    print(f"\n📊 Loading SPY data...")
    spy_start = start_date - timedelta(days=300 if args.beta_adjusted else 10)
    spy_end = end_date + timedelta(days=args.lookahead + 10)

    spy_prices = get_spy_prices(spy_start, spy_end)

    if spy_prices is None:
        print("\n❌ Could not load SPY data. Alpha labels require SPY comparison.")
        return

    print(f"✅ Loaded SPY data: {len(spy_prices):,} rows")

    # Get all tracked stocks
    print(f"\n📊 Finding tracked stocks...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM stocks WHERE is_tracked = true"))
        stock_ids = [row[0] for row in result]

    print(f"✅ Found {len(stock_ids)} tracked stocks")

    # Create labels
    print(f"\n🔄 Creating alpha labels...")
    all_labels = []

    for stock_id in stock_ids:
        try:
            if args.type == 'binary':
                labels = create_alpha_binary_labels(
                    stock_id, start_date, end_date,
                    spy_prices=spy_prices,
                    alpha_target=args.alpha_target,
                    lookahead=args.lookahead,
                    beta_adjusted=args.beta_adjusted
                )
            elif args.type == '3class':
                labels = create_alpha_3class_labels(
                    stock_id, start_date, end_date,
                    spy_prices=spy_prices,
                    outperform=args.alpha_target,
                    underperform=-args.alpha_target,
                    lookahead=args.lookahead,
                    beta_adjusted=args.beta_adjusted
                )
            else:  # 5class
                labels = create_alpha_5class_labels(
                    stock_id, start_date, end_date,
                    spy_prices=spy_prices,
                    strong_outperform=args.strong_outperform,
                    outperform=args.outperform,
                    market_perform=args.market_perform,
                    underperform=args.underperform,
                    lookahead=args.lookahead,
                    beta_adjusted=args.beta_adjusted
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
    if args.type == 'binary':
        label_type = 'alpha_binary'
    elif args.type == '3class':
        label_type = 'alpha_3class'
    else:
        label_type = 'alpha_5class'

    output_file = dataset_folder / f'labels_{label_type}.parquet'
    df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved {len(df):,} label rows to {dataset_folder.name}/")
    print(f"   File: {output_file.name}")

    # Print statistics
    print(f"\n📊 Label Statistics:")

    if args.type == 'binary':
        distribution = df['label'].value_counts().sort_index()
        for class_id, count in distribution.items():
            pct = count / len(df) * 100
            label_name = "BUY" if class_id == 1 else "DON'T BUY"
            print(f"  {label_name:<15} {count:7,} ({pct:5.1f}%)")
    elif args.type == '3class':
        class_names = {
            0: 'SELL / UNDERPERFORM',
            1: 'HOLD / MARKET PERFORM',
            2: 'BUY / OUTPERFORM'
        }
        distribution = df['label'].value_counts().sort_index()
        for class_id in range(3):
            count = distribution.get(class_id, 0)
            pct = count / len(df) * 100 if count > 0 else 0
            print(f"  {class_names[class_id]:<20} {count:7,} ({pct:5.1f}%)")
    else:  # 5class
        class_names = {
            0: 'STRONG UNDERPERFORM',
            1: 'UNDERPERFORM',
            2: 'MARKET PERFORM',
            3: 'OUTPERFORM',
            4: 'STRONG OUTPERFORM'
        }

        distribution = df['label'].value_counts().sort_index()
        for class_id in range(5):
            count = distribution.get(class_id, 0)
            pct = count / len(df) * 100 if count > 0 else 0
            print(f"  {class_names[class_id]:<20} {count:7,} ({pct:5.1f}%)")

    # Print alpha statistics
    print(f"\n📊 Alpha Statistics:")
    print(f"  Mean alpha:    {df['alpha'].mean():>7.2f}%")
    print(f"  Median alpha:  {df['alpha'].median():>7.2f}%")
    print(f"  Std alpha:     {df['alpha'].std():>7.2f}%")

    # Print win rate (positive alpha)
    win_rate = (df['alpha'] > 0).sum() / len(df) * 100
    print(f"  Win rate (>0% alpha): {win_rate:>5.1f}%")

    if args.type == 'binary' or args.type == '3class':
        target_win_rate = (df['alpha'] >= args.alpha_target).sum() / len(df) * 100
        print(f"  Target win rate (≥{args.alpha_target*100:.1f}%): {target_win_rate:>5.1f}%")

    # Show available labels in dataset folder
    print(f"\n📂 Dataset folder contents:")
    label_files = sorted(dataset_folder.glob('labels_*.parquet'))
    if label_files:
        for label_file in label_files:
            print(f"   ✓ {label_file.name}")
    else:
        print(f"   (only labels_{label_type}.parquet exists)")

    print(f"\n💡 Next Steps:")
    print(f"   1. Run diagnostic to confirm labels work:")
    print(f"      python create_labels/01_diagnose_current_labels.py --dataset-folder {dataset_folder.name}")
    print(f"   2. Train model with new labels:")
    print(f"      python train.py --dataset-folder {dataset_folder.name} --label-type {label_type}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
