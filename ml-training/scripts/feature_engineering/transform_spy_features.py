#!/usr/bin/env python3
"""
TRANSFORM SPY TO RELATIVE FEATURES

Purpose: Transform raw SPY features to relative features to force
         the model to learn stock-specific alpha instead of beta.

Approach:
- Remove raw SPY price/trend features
- Replace with stock-relative features (stock vs SPY)
- Keep minimal SPY context for alpha calculation

Created: 2026-02-05
Author: ML Team
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Setup paths
sys.path.insert(0, '/app')

import pandas as pd
import numpy as np

def transform_spy_features(
    features_path: str,
    output_path: str = None
):
    """
    Transform SPY features to relative features

    Args:
        features_path: Path to features.parquet
        output_path: Optional output path (default: features_relative_spy.parquet)
    """

    print("=" * 70)
    print("SPY FEATURE TRANSFORMATION")
    print("=" * 70)

    # Load features
    print(f"\n📂 Loading features from: {features_path}")
    df = pd.read_parquet(features_path)

    print(f"✅ Loaded {len(df):,} samples with {len(df.columns)} features")

    # ============================================================
    # IDENTIFY SPY FEATURES TO REMOVE
    # ============================================================

    spy_features_to_remove = [
        'spy_close',           # Raw SPY price
        'spy_ma_200',          # SPY 200-day MA
        'spy_ma_50',           # SPY 50-day MA
        'spy_ma_20',           # SPY 20-day MA
        'spy_uptrend',         # SPY uptrend flag
        'spy_uptrend_long',    # SPY long-term uptrend
        'spy_downtrend',       # SPY downtrend flag
        'spy_high_20d',        # SPY 20-day high
        'spy_low_20d',         # SPY 20-day low
    ]

    # Check which features exist
    spy_features_present = [f for f in spy_features_to_remove if f in df.columns]

    print(f"\n🗑️  Removing {len(spy_features_present)} raw SPY features:")
    for f in spy_features_present:
        print(f"   - {f}")

    # ============================================================
    # CREATE RELATIVE FEATURES
    # ============================================================

    print(f"\n🔄 Creating relative features...")

    # 1. Stock vs SPY price ratio
    if 'spy_close' in df.columns and 'close' in df.columns:
        df['stock_vs_spy_ratio'] = df['close'] / df['spy_close']
        print(f"   ✓ stock_vs_spy_ratio (stock price / SPY price)")

    # 2. Stock vs SPY momentum (relative strength)
    if 'spy_return_20d' in df.columns and 'momentum_20d' in df.columns:
        df['stock_vs_spy_momentum'] = df['momentum_20d'] - df['spy_return_20d']
        print(f"   ✓ stock_vs_spy_momentum (stock momentum - SPY return)")

    # 3. Stock vs SPY volatility ratio
    if 'spy_return_20d' in df.columns:
        # Calculate rolling volatility for stock and SPY
        df_temp = df.sort_values(['stock_id', 'timestamp'])

        # Stock 20-day volatility (use existing volatility_20d if available)
        if 'volatility_20d' in df.columns:
            df_temp['stock_vol_20d'] = df_temp['volatility_20d']
        else:
            # Fallback: calculate from daily_return
            df_temp['stock_vol_20d'] = df_temp.groupby('stock_id')['daily_return'].transform(
                lambda x: x.rolling(20, min_periods=10).std()
            )

        # SPY 20-day volatility (approximate from returns)
        df_temp['spy_vol_20d'] = df_temp['spy_return_20d'].rolling(20, min_periods=10).std()

        # Volatility ratio
        df_temp['stock_vs_spy_volatility'] = df_temp['stock_vol_20d'] / (df_temp['spy_vol_20d'] + 1e-6)

        # Map back to original df
        df = df.set_index(['stock_id', 'timestamp'])
        df_temp = df_temp.set_index(['stock_id', 'timestamp'])
        df['stock_vs_spy_volatility'] = df_temp['stock_vs_spy_volatility']
        df = df.reset_index()

        print(f"   ✓ stock_vs_spy_volatility (stock vol / SPY vol)")

    # 4. Relative strength indicator (RSI relative to SPY's RSI)
    if 'rsi' in df.columns:
        # Create SPY RSI approximation (if it doesn't exist)
        if 'spy_rsi' not in df.columns:
            # Simple RSI approximation based on spy returns
            spy_returns = df['spy_return_20d']
            gains = spy_returns.where(spy_returns > 0, 0)
            losses = -spy_returns.where(spy_returns < 0, 0)

            avg_gain = gains.rolling(14).mean()
            avg_loss = losses.rolling(14).mean()

            df['spy_rsi'] = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-6)))

        # Relative RSI
        df['rsi_vs_spy'] = df['rsi'] - df['spy_rsi']
        print(f"   ✓ rsi_vs_spy (stock RSI - SPY RSI)")

    # 5. Market regime (keep this - useful context)
    # Already exists as 'market_regime_bull' - keep it

    # ============================================================
    # REMOVE RAW SPY FEATURES
    # ============================================================

    print(f"\n🗑️  Removing raw SPY features...")
    features_before = len(df.columns)

    df = df.drop(columns=spy_features_present, errors='ignore')

    features_after = len(df.columns)
    print(f"   Removed {features_before - features_after} features")
    print(f"   Total features: {features_before} → {features_after}")

    # ============================================================
    # KEEP MINIMAL SPY CONTEXT
    # ============================================================

    # Keep these for alpha calculation context:
    spy_features_to_keep = [
        'spy_return_5d',
        'spy_return_20d',
        'spy_return_60d',
    ]

    kept_spy = [f for f in spy_features_to_keep if f in df.columns]
    print(f"\n✅ Keeping {len(kept_spy)} SPY features for context:")
    for f in kept_spy:
        print(f"   - {f}")

    # ============================================================
    # VERIFY TRANSFORMATION
    # ============================================================

    print(f"\n" + "=" * 70)
    print("TRANSFORMATION SUMMARY")
    print("=" * 70)

    # Count feature types
    relative_features = [c for c in df.columns if 'vs_spy' in c or 'vs_' in c]
    spy_remaining = [c for c in df.columns if c.startswith('spy_')]
    stock_features = [c for c in df.columns if not c.startswith('spy_') and c not in ['stock_id', 'timestamp']]

    print(f"\n📊 Feature breakdown:")
    print(f"   Relative features (stock vs SPY): {len(relative_features)}")
    print(f"   Remaining SPY features: {len(spy_remaining)}")
    print(f"   Stock-specific features: {len(stock_features)}")
    print(f"   Total features: {len(df.columns) - 2}")  # Exclude stock_id, timestamp

    print(f"\n✅ Relative features created:")
    for f in relative_features:
        print(f"   - {f}")

    # ============================================================
    # SAVE TRANSFORMED FEATURES
    # ============================================================

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/app/outputs/features/dataset_20260204_204134/features_relative_spy_{timestamp}.parquet"

    print(f"\n💾 Saving transformed features to:")
    print(f"   {output_path}")

    df.to_parquet(output_path, index=False)

    print(f"\n✅ Transformation complete!")

    return df


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Transform SPY features to relative features',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/transform_spy_features.py
  python scripts/transform_spy_features.py --features-path /path/to/features.parquet
  python scripts/transform_spy_features.py --output-path /path/to/output.parquet

This script:
  1. Removes raw SPY price/trend features
  2. Creates relative features (stock vs SPY)
  3. Keeps minimal SPY context for alpha calculation
        """
    )

    parser.add_argument(
        '--features-path',
        type=str,
        default='/app/outputs/features/dataset_20260204_204134/features.parquet',
        help='Path to input features file'
    )

    parser.add_argument(
        '--output-path',
        type=str,
        default=None,
        help='Path to output features file (default: auto-generated)'
    )

    args = parser.parse_args()

    transform_spy_features(
        features_path=args.features_path,
        output_path=args.output_path
    )


if __name__ == "__main__":
    main()
