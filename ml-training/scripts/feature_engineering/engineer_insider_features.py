#!/usr/bin/env python3
"""
ENHANCED INSIDER FEATURES ENGINEERING

Purpose: Transform raw insider trading data into predictive features by adding
         context that makes the signals meaningful.

Current Problem:
- Raw insider features have low importance (0.5-2%)
- Model ignores them because they lack context

Solution:
- Add percentile-based features ("is this unusual?")
- Add price context ("are insiders buying at lows?")
- Add cluster detection ("are multiple executives buying?")

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

def engineer_enhanced_insider_features(
    features_path: str,
    output_path: str = None
):
    """
    Engineer enhanced insider features with context

    Args:
        features_path: Path to features.parquet
        output_path: Optional output path
    """

    print("=" * 70)
    print("ENHANCED INSIDER FEATURES ENGINEERING")
    print("=" * 70)

    # Load features
    print(f"\n📂 Loading features from: {features_path}")
    df = pd.read_parquet(features_path)

    print(f"✅ Loaded {len(df):,} samples with {len(df.columns)} features")

    # ============================================================
    # IDENTIFY BASE INSIDER FEATURES
    # ============================================================

    base_insider_features = {
        'counts': [
            'insider_buy_count_30d',
            'insider_sell_count_30d',
        ],
        'values': [
            'insider_buy_value_30d',
            'insider_sell_value_30d',
        ],
        'sentiment': [
            'insider_sentiment_30d',
            'insider_net_buy_ratio_30d',
        ]
    }

    # Check which features exist
    available_insider = []
    for category, features in base_insider_features.items():
        for f in features:
            if f in df.columns:
                available_insider.append(f)

    print(f"\n✅ Found {len(available_insider)} base insider features")
    for f in available_insider:
        print(f"   - {f}")

    if len(available_insider) == 0:
        print("\n❌ No insider features found! Nothing to enhance.")
        return df

    # ============================================================
    # CATEGORY 1: UNUSUAL ACTIVITY FEATURES
    # ============================================================

    print(f"\n🔄 Creating unusual activity features...")

    # For each stock, calculate percentiles over time
    df_sorted = df.sort_values(['stock_id', 'timestamp']).reset_index(drop=True)

    # 1. Unusual buying (top 20% historically for this stock)
    if 'insider_buy_count_30d' in df.columns:
        df_sorted['insider_buy_unusual_80'] = df_sorted.groupby('stock_id')['insider_buy_count_30d'].transform(
            lambda x: (x > x.rolling(252, min_periods=60).quantile(0.80)).astype(int)
        )
        df_sorted['insider_buy_unusual_90'] = df_sorted.groupby('stock_id')['insider_buy_count_30d'].transform(
            lambda x: (x > x.rolling(252, min_periods=60).quantile(0.90)).astype(int)
        )
        print(f"   ✓ insider_buy_unusual_80 (top 20% historically)")
        print(f"   ✓ insider_buy_unusual_90 (top 10% historically)")

    # 2. Unusual selling
    if 'insider_sell_count_30d' in df.columns:
        df_sorted['insider_sell_unusual_80'] = df_sorted.groupby('stock_id')['insider_sell_count_30d'].transform(
            lambda x: (x > x.rolling(252, min_periods=60).quantile(0.80)).astype(int)
        )
        print(f"   ✓ insider_sell_unusual_80 (top 20% selling)")

    # 3. Unusual value (insiders spending big money)
    if 'insider_buy_value_30d' in df.columns:
        df_sorted['insider_value_unusual_80'] = df_sorted.groupby('stock_id')['insider_buy_value_30d'].transform(
            lambda x: (x > x.rolling(252, min_periods=60).quantile(0.80)).astype(int)
        )
        print(f"   ✓ insider_value_unusual_80 (top 20% by value)")

    # ============================================================
    # CATEGORY 2: VALUE + PRICE CONTEXT FEATURES
    # ============================================================

    print(f"\n🔄 Creating value + price context features...")

    # 4. Insiders buying at dip (RSI < 30)
    if 'insider_buy_count_30d' in df.columns and 'rsi' in df.columns:
        df_sorted['insider_buying_dip'] = (
            (df_sorted['insider_buy_count_30d'] > 0) &
            (df_sorted['rsi'] < 30)
        ).astype(int)
        print(f"   ✓ insider_buying_dip (buying + RSI<30)")

    # 5. Insiders buying at oversold (RSI < 20, extremely oversold)
    if 'insider_buy_count_30d' in df.columns and 'rsi' in df.columns:
        df_sorted['insider_buying_oversold'] = (
            (df_sorted['insider_buy_count_30d'] > 0) &
            (df_sorted['rsi'] < 20)
        ).astype(int)
        print(f"   ✓ insider_buying_oversold (buying + RSI<20)")

    # 6. Insiders buying at 52-week low
    if 'insider_buy_count_30d' in df.columns and 'close' in df.columns:
        # Calculate 52-week low (252 trading days)
        df_sorted['price_52w_low'] = df_sorted.groupby('stock_id')['close'].transform(
            lambda x: x.rolling(252, min_periods=60).min()
        )

        # Within 5% of 52-week low
        df_sorted['near_52w_low'] = (
            df_sorted['close'] <= df_sorted['price_52w_low'] * 1.05
        ).astype(int)

        df_sorted['insider_at_52w_low'] = (
            (df_sorted['insider_buy_count_30d'] > 0) &
            (df_sorted['near_52w_low'] > 0)
        ).astype(int)

        print(f"   ✓ insider_at_52w_low (buying near 52-week low)")

    # 7. Insiders buying below 200-day MA
    if 'insider_buy_count_30d' in df.columns and 'ma_200' in df.columns:
        df_sorted['insider_below_ma200'] = (
            (df_sorted['insider_buy_count_30d'] > 0) &
            (df_sorted['close'] < df_sorted['ma_200'])
        ).astype(int)
        print(f"   ✓ insider_below_ma200 (buying below 200MA)")

    # 7b. Insiders selling when price is up (using momentum)
    if 'insider_sell_count_30d' in df.columns and 'momentum_20d' in df.columns:
        df_sorted['insider_sell_when_up'] = (
            (df_sorted['insider_sell_count_30d'] > 0) &
            (df_sorted['momentum_20d'] > 0.10)  # Stock up 10%
        ).astype(int)
        print(f"   ✓ insider_sell_when_up (selling after 10% rise)")

    # ============================================================
    # CATEGORY 3: EXECUTIVE CLUSTER FEATURES
    # ============================================================

    print(f"\n🔄 Creating executive cluster features...")

    # Note: Current data doesn't have executive-level detail (CEO, CFO, etc.)
    # But we can create cluster features from what we have

    # 8. Strong conviction (high count + high value)
    if 'insider_buy_count_30d' in df.columns and 'insider_buy_value_30d' in df.columns:
        df_sorted['insider_conviction_strong'] = (
            (df_sorted['insider_buy_count_30d'] > 0) &
            (df_sorted['insider_buy_value_30d'] > 0) &
            (df_sorted['insider_sentiment_30d'] > 0.7)
        ).astype(int)
        print(f"   ✓ insider_conviction_strong (high count + value + sentiment)")

    # 9. Insider momentum (buying increasing)
    if 'insider_buy_count_30d' in df.columns:
        # 5-day change in buying
        df_sorted['insider_buy_momentum'] = df_sorted.groupby('stock_id')['insider_buy_count_30d'].transform(
            lambda x: x.diff(5) > 0
        ).fillna(0).astype(int)
        print(f"   ✓ insider_buy_momentum (buying increasing)")

    # 10. Contrarian selling (insiders selling when price is up)
    if 'insider_sell_count_30d' in df.columns and 'momentum_20d' in df.columns:
        df_sorted['insider_sell_at_high'] = (
            (df_sorted['insider_sell_count_30d'] > 0) &
            (df_sorted['momentum_20d'] > 0.10)  # Stock up 10%
        ).astype(int)
        print(f"   ✓ insider_sell_at_high (selling after 10% rise)")

    # ============================================================
    # CATEGORY 4: MARKET CONTEXT FEATURES
    # ============================================================

    print(f"\n🔄 Creating market context features...")

    # 11. Insider buying in bear market (contrarian signal)
    if 'insider_buy_count_30d' in df.columns and 'spy_return_20d' in df.columns:
        df_sorted['insider_buy_bear_market'] = (
            (df_sorted['insider_buy_count_30d'] > 0) &
            (df_sorted['spy_return_20d'] < -0.05)  # SPY down 5%
        ).astype(int)
        print(f"   ✓ insider_buy_bear_market (buying when SPY down 5%)")

    # 12. Insider relative to market (insider bullish when market bearish)
    if 'insider_sentiment_30d' in df.columns and 'spy_return_20d' in df.columns:
        df_sorted['insider_contrarian'] = (
            (df_sorted['insider_sentiment_30d'] > 0.6) &
            (df_sorted['spy_return_20d'] < -0.03)
        ).astype(int)
        print(f"   ✓ insider_contrarian (bullish insiders + bearish market)")

    # ============================================================
    # SUMMARY OF NEW FEATURES
    # ============================================================

    # Get all new features
    original_cols = set(df.columns)
    new_cols = [c for c in df_sorted.columns if c not in original_cols]

    print(f"\n" + "=" * 70)
    print("FEATURE ENGINEERING SUMMARY")
    print("=" * 70)

    print(f"\n✅ Created {len(new_cols)} enhanced insider features:")

    # Group by category
    unusual = [c for c in new_cols if 'unusual' in c]
    context = [c for c in new_cols if any(x in c for x in ['dip', 'oversold', '52w', 'below_ma', 'at_high'])]
    cluster = [c for c in new_cols if any(x in c for x in ['conviction', 'momentum', 'cluster'])]
    market = [c for c in new_cols if any(x in c for x in ['bear_market', 'contrarian'])]

    if unusual:
        print(f"\n   📊 Unusual Activity ({len(unusual)}):")
        for f in unusual:
            print(f"      - {f}")

    if context:
        print(f"\n   💰 Value + Price Context ({len(context)}):")
        for f in context:
            print(f"      - {f}")

    if cluster:
        print(f"\n   👥 Executive Clusters ({len(cluster)}):")
        for f in cluster:
            print(f"      - {f}")

    if market:
        print(f"\n   📈 Market Context ({len(market)}):")
        for f in market:
            print(f"      - {f}")

    # ============================================================
    # SAVE ENHANCED FEATURES
    # ============================================================

    # Clean up temporary columns
    temp_cols = ['price_52w_low', 'near_52w_low']
    df_sorted = df_sorted.drop(columns=[c for c in temp_cols if c in df_sorted.columns], errors='ignore')

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/app/outputs/features/dataset_20260204_204134/features_enhanced_insider_{timestamp}.parquet"

    print(f"\n💾 Saving enhanced features to:")
    print(f"   {output_path}")

    df_sorted.to_parquet(output_path, index=False)

    print(f"\n✅ Feature engineering complete!")
    print(f"   Original features: {len(df.columns)}")
    print(f"   New features: {len(df_sorted.columns)}")
    print(f"   Added: {len(df_sorted.columns) - len(df.columns)}")

    return df_sorted


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Engineer enhanced insider features',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/engineer_insider_features.py
  python scripts/engineer_insider_features.py --features-path /path/to/features.parquet
  python scripts/engineer_insider_features.py --output-path /path/to/output.parquet

This script creates:
  1. Unusual activity features (percentile-based)
  2. Value + price context features (buying at dips, lows, etc.)
  3. Executive cluster features (conviction, momentum)
  4. Market context features (contrarian signals)
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

    engineer_enhanced_insider_features(
        features_path=args.features_path,
        output_path=args.output_path
    )


if __name__ == "__main__":
    main()
