#!/usr/bin/env python3
"""
Fast News Features Update - FinBERT Sentiment (Direct Version)

This script loads the Feb 10 feature engineering dataset and ONLY updates
the 20 news sentiment features using the new FinBERT sentiment scores.

Usage:
    python scripts/update_news_feb10.py

Expected runtime: ~40 minutes
"""

import sys
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, '/backend')
sys.path.insert(0, '/app/ml_training')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Import news features module
from ml_framework.news_features import NewsFeatures, NEWS_FEATURES

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Direct paths
SOURCE_DATASET = Path('/app/outputs/features/dataset_20260210_224956')


def update_news_features_for_stock(stock_id, start_date, end_date):
    """Update news features for a single stock"""
    # Convert numpy types to Python types
    stock_id = int(stock_id)
    start_date = pd.Timestamp(start_date).to_pydatetime()
    end_date = pd.Timestamp(end_date).to_pydatetime()

    # Get unique dates for this stock
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT DISTINCT date_trunc('day', timestamp::timestamp) as date
                FROM stock_prices
                WHERE stock_id = :stock_id
                  AND timestamp >= :start_date
                  AND timestamp <= :end_date
                ORDER BY date
            """),
            {'stock_id': stock_id, 'start_date': start_date, 'end_date': end_date}
        )
        feature_dates = pd.to_datetime([row[0] for row in result])
    finally:
        db.close()

    if len(feature_dates) == 0:
        return None

    # Calculate news features
    news_df = NewsFeatures.fetch_news_from_db(stock_id, start_date, end_date)

    if news_df.empty:
        # No news data - return zeros
        features = pd.DataFrame(index=feature_dates)
        for feat in NEWS_FEATURES:
            features[feat] = 0
        features['news_data_available'] = 0
        return features

    # Calculate features
    features = NewsFeatures.calculate_rolling_features(news_df, feature_dates)
    return features


def main():
    """Main function to update news features only"""
    print("=" * 80)
    print(" " * 15)
    print("News Features Update - Feb 10 Dataset + FinBERT")
    print(" " * 15)
    print("=" * 80)

    # ============================================================
    # LOAD FEB 10 DATASET
    # ============================================================
    features_path = SOURCE_DATASET / 'features.parquet'
    print(f"\n📂 Loading Feb 10 dataset: {SOURCE_DATASET.name}")

    df = pd.read_parquet(features_path)

    print(f"   Shape: {df.shape}")
    print(f"   Columns: {len(df.columns)}")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # CRITICAL: Normalize timestamps to midnight for proper merge
    # News features use normalized timestamps, so we need to match
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()

    # Remove old news features
    print(f"\n🗑️  Removing old news features...")
    for feat in NEWS_FEATURES:
        if feat in df.columns:
            df = df.drop(columns=[feat])

    # ============================================================
    # UPDATE NEWS FEATURES FOR EACH STOCK
    # ============================================================
    print(f"\n📰 Updating news features for {df['stock_id'].nunique()} stocks...")
    print("=" * 80)

    # Get date range
    start_date = df['timestamp'].min()
    end_date = df['timestamp'].max()

    print(f"\n📅 Date range: {start_date} to {end_date}")

    # Process each stock
    all_news_features = []

    unique_stocks = df['stock_id'].unique()
    for stock_id in tqdm(unique_stocks, desc="Updating news"):
        news_features = update_news_features_for_stock(stock_id, start_date, end_date)

        if news_features is not None:
            news_features['stock_id'] = stock_id
            all_news_features.append(news_features.reset_index())

    # Combine all news features
    if all_news_features:
        news_df = pd.concat(all_news_features, ignore_index=True)
        # The index column from reset_index() is called 'index'
        news_df.rename(columns={'index': 'timestamp'}, inplace=True)
        # Convert timestamp to datetime for proper merge (truncated to day)
        news_df['timestamp'] = pd.to_datetime(news_df['timestamp']).dt.normalize()
        # Create explicit merge_date column for date-based merge (not exact timestamp)
        news_df['merge_date'] = news_df['timestamp'].dt.date

        # ============================================================
        # MERGE NEWS FEATURES WITH EXISTING FEATURES
        # ============================================================
        print(f"\n🔗 Merging news features with existing features...")

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        # Create explicit merge_date column for date-based merge
        df['merge_date'] = df['timestamp'].dt.date

        # Remove timestamp from index if it's there
        if df.index.name == 'timestamp':
            df = df.reset_index()

        # Verify columns exist before merge
        print(f"   df columns: stock_id={df['stock_id'].name}, merge_date exists={'merge_date' in df.columns}")
        print(f"   news_df columns: stock_id={news_df['stock_id'].name}, merge_date exists={'merge_date' in news_df.columns}")

        # Merge on stock_id and merge_date (date-based, not exact timestamp)
        result = df.merge(
            news_df,
            on=['stock_id', 'merge_date'],
            how='left',
            suffixes=('', '_news')
        )

        # Fill NaN with 0 (for dates before first news)
        for feat in NEWS_FEATURES:
            if feat in result.columns:
                result[feat] = result[feat].fillna(0)

        print(f"   ✅ Merged successfully")
        print(f"   Final shape: {result.shape}")

        # ============================================================
        # SAVE TO NEW DATASET FOLDER
        # ============================================================
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_folder_name = f'dataset_{timestamp_str}'
        new_folder = Path('/app/outputs/features') / new_folder_name
        new_folder.mkdir(parents=True, exist_ok=True)

        # Save features
        features_path = new_folder / 'features.parquet'
        result.to_parquet(features_path, index=False)

        print(f"\n💾 Saved to: {features_path}")
        print(f"   Size: {features_path.stat().st_size / 1024 / 1024:.1f} MB")

        # ============================================================
        # VERIFY NEWS FEATURES
        # ============================================================
        print(f"\n🔍 Verifying news features...")

        news_cols = [col for col in result.columns if col.startswith('news_')]
        print(f"   News features: {len(news_cols)}")

        # Check data availability
        has_news = (result['news_data_available'] == 1).sum()
        total_rows = len(result)
        print(f"   Rows with news data: {has_news:,} / {total_rows:,} ({has_news/total_rows*100:.1f}%)")

        # Check non-zero sentiment
        non_zero = (result['news_sentiment_avg_7d'] != 0).sum()
        print(f"   Non-zero 7d sentiment: {non_zero:,} ({non_zero/total_rows*100:.1f}%)")

        # Check sentiment distribution
        positive = (result['news_sentiment_avg_7d'] > 0.05).sum()
        negative = (result['news_sentiment_avg_7d'] < -0.05).sum()
        neutral = ((result['news_sentiment_avg_7d'] >= -0.05) & (result['news_sentiment_avg_7d'] <= 0.05)).sum()

        print(f"\n   7d Sentiment Distribution:")
        print(f"      Positive: {positive:,} ({positive/total_rows*100:.1f}%)")
        print(f"      Negative: {negative:,} ({negative/total_rows*100:.1f}%)")
        print(f"      Neutral:  {neutral:,} ({neutral/total_rows*100:.1f}%)")

        # Check intensity (news volume)
        if 'news_intensity_7d' in result.columns:
            has_articles = (result['news_intensity_7d'] > 0).sum()
            print(f"\n   7d News intensity > 0: {has_articles:,} ({has_articles/total_rows*100:.1f}%)")

        # ============================================================
        # CREATE METADATA
        # ============================================================
        import json

        metadata = {
            'created_at': datetime.now().isoformat(),
            'num_samples': len(result),
            'num_features': len(result.columns) - 2,  # Exclude stock_id and timestamp
            'features': [col for col in result.columns if col not in ['stock_id', 'timestamp']],
            'news_features_updated': True,
            'news_features_count': len(news_cols),
            'source_dataset': 'dataset_20260210_224956',
            'update_type': 'news_features_only_feb10',
            'description': 'Feb 10 features + FinBERT sentiment'
        }

        metadata_path = new_folder / 'metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)

        print(f"\n📄 Metadata saved to: {metadata_path}")

        print("\n" + "=" * 80)
        print("✅ NEWS FEATURES UPDATE COMPLETE!")
        print("=" * 80)
        print(f"\n📂 New dataset: {new_folder_name}")
        print(f"   Features: {len(metadata['features'])}")
        print(f"   Samples: {metadata['num_samples']:,}")
        print(f"\n💡 Next steps:")
        print(f"   1. Create labels:")
        print(f"      docker exec stock_analyzer_ml_training python scripts/create_labels.py --dataset-folder {new_folder_name}")
        print(f"   2. Train ML model:")
        print(f"      docker exec stock_analyzer_ml_training python train.py --dataset-folder {new_folder_name}")
        print(f"\n" + "=" * 80)

    else:
        print("\n❌ No news features to update!")


if __name__ == "__main__":
    main()
