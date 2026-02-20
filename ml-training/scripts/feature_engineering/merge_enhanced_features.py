#!/usr/bin/env python3
"""
MERGE ENHANCED FEATURES

Purpose: Merge relative SPY features + enhanced insider features
         into a single enhanced feature file for training.

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

def merge_enhanced_features(
    relative_spy_path: str,
    enhanced_insider_path: str,
    output_path: str = None
):
    """
    Merge relative SPY features with enhanced insider features

    Args:
        relative_spy_path: Path to relative SPY features
        enhanced_insider_path: Path to enhanced insider features
        output_path: Optional output path
    """

    print("=" * 70)
    print("MERGING ENHANCED FEATURES")
    print("=" * 70)

    # Load relative SPY features
    print(f"\n📂 Loading relative SPY features from: {relative_spy_path}")
    df_spy = pd.read_parquet(relative_spy_path)
    print(f"   ✅ {len(df_spy):,} samples, {len(df_spy.columns)} features")

    # Load enhanced insider features
    print(f"\n📂 Loading enhanced insider features from: {enhanced_insider_path}")
    df_insider = pd.read_parquet(enhanced_insider_path)
    print(f"   ✅ {len(df_insider):,} samples, {len(df_insider.columns)} features")

    # Identify new feature columns (excluding stock_id, timestamp)
    base_cols = ['stock_id', 'timestamp']

    # New relative SPY features
    relative_spy_features = [
        'stock_vs_spy_ratio',
        'stock_vs_spy_momentum',
        'stock_vs_spy_volatility',
        'rsi_vs_spy',
    ]

    # New enhanced insider features
    enhanced_insider_features = [
        'insider_buy_unusual_80',
        'insider_buy_unusual_90',
        'insider_sell_unusual_80',
        'insider_value_unusual_80',
        'insider_buying_dip',
        'insider_buying_oversold',
        'insider_at_52w_low',
        'insider_below_ma200',
        'insider_sell_when_up',
        'insider_sell_at_high',
        'insider_conviction_strong',
        'insider_buy_momentum',
        'insider_buy_bear_market',
        'insider_contrarian',
    ]

    # Check which features exist in each dataset
    relative_features_present = [f for f in relative_spy_features if f in df_spy.columns]
    insider_features_present = [f for f in enhanced_insider_features if f in df_insider.columns]

    print(f"\n✅ Relative SPY features to merge: {len(relative_features_present)}")
    for f in relative_features_present:
        print(f"   - {f}")

    print(f"\n✅ Enhanced insider features to merge: {len(insider_features_present)}")
    for f in insider_features_present:
        print(f"   - {f}")

    # Start with base features
    print(f"\n🔄 Creating merged dataset...")

    # Load original features (base)
    df_base = pd.read_parquet('/app/outputs/features/dataset_20260204_204134/features.parquet')
    df_merged = df_base.copy()

    # Remove raw SPY features that were replaced
    spy_features_to_remove = [
        'spy_close', 'spy_ma_200', 'spy_ma_50', 'spy_ma_20',
        'spy_uptrend', 'spy_uptrend_long', 'spy_downtrend',
        'spy_high_20d', 'spy_low_20d'
    ]
    df_merged = df_merged.drop(columns=[f for f in spy_features_to_remove if f in df_merged.columns], errors='ignore')

    # Add relative SPY features
    for f in relative_features_present:
        df_merged[f] = df_spy[f].values

    # Add enhanced insider features
    for f in insider_features_present:
        df_merged[f] = df_insider[f].values

    # Summary
    original_count = len(df_base.columns)
    merged_count = len(df_merged.columns)
    added_count = merged_count - original_count

    print(f"\n" + "=" * 70)
    print("MERGE SUMMARY")
    print("=" * 70)

    print(f"\n📊 Feature counts:")
    print(f"   Original features:  {original_count}")
    print(f"   Merged features:    {merged_count}")
    print(f"   Net change:         {added_count:+d}")

    print(f"\n✅ Removed {len([f for f in spy_features_to_remove if f in df_base.columns])} raw SPY features")
    print(f"✅ Added {len(relative_features_present)} relative SPY features")
    print(f"✅ Added {len(insider_features_present)} enhanced insider features")

    # Feature breakdown
    spy_remaining = [c for c in df_merged.columns if c.startswith('spy_') and c not in base_cols]
    relative = [c for c in df_merged.columns if 'vs_spy' in c or 'vs_' in c]
    insider = [c for c in df_merged.columns if 'insider' in c]
    stock = [c for c in df_merged.columns if c not in base_cols + spy_remaining + relative + insider]

    print(f"\n📊 Feature breakdown:")
    print(f"   Stock-specific:     {len(stock)}")
    print(f"   Insider (raw):      {len([c for c in insider if c in df_base.columns])}")
    print(f"   Insider (enhanced): {len([c for c in insider if c not in df_base.columns])}")
    print(f"   SPY (remaining):    {len(spy_remaining)}")
    print(f"   Relative features:  {len(relative)}")

    # Save merged features
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/app/outputs/features/dataset_20260204_204134/features_enhanced_{timestamp}.parquet"

    print(f"\n💾 Saving merged features to:")
    print(f"   {output_path}")

    df_merged.to_parquet(output_path, index=False)

    print(f"\n✅ Merge complete!")

    return df_merged


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Merge enhanced features',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/merge_enhanced_features.py
  python scripts/merge_enhanced_features.py --output-path /path/to/output.parquet

This script merges:
  1. Relative SPY features (from transform_spy_features.py)
  2. Enhanced insider features (from engineer_insider_features.py)
  3. Original features (with raw SPY removed)
        """
    )

    parser.add_argument(
        '--relative-spy-path',
        type=str,
        default='/app/outputs/features/dataset_20260204_204134/features_relative_spy_20260205_131102.parquet',
        help='Path to relative SPY features file'
    )

    parser.add_argument(
        '--enhanced-insider-path',
        type=str,
        default='/app/outputs/features/dataset_20260204_204134/features_enhanced_insider_20260205_131822.parquet',
        help='Path to enhanced insider features file'
    )

    parser.add_argument(
        '--output-path',
        type=str,
        default=None,
        help='Path to output features file (default: auto-generated)'
    )

    args = parser.parse_args()

    # Check if files exist
    if not os.path.exists(args.relative_spy_path):
        print(f"❌ Relative SPY features not found: {args.relative_spy_path}")
        print("   Run transform_spy_features.py first")
        return

    if not os.path.exists(args.enhanced_insider_path):
        print(f"❌ Enhanced insider features not found: {args.enhanced_insider_path}")
        print("   Run engineer_insider_features.py first")
        return

    merge_enhanced_features(
        relative_spy_path=args.relative_spy_path,
        enhanced_insider_path=args.enhanced_insider_path,
        output_path=args.output_path
    )


if __name__ == "__main__":
    main()
