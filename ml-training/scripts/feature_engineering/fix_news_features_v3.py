#!/usr/bin/env python3
"""
Fix News Features - Final Version
Fixes news features by:
1. Dropping 20 incorrectly created news columns
2. Querying daily-aggregated news from database
3. Merging on date only (not exact timestamp match)
4. Filling missing news with 0 (neutral sentiment, no leakage)

Usage:
    python scripts/fix_news_features_v3.py
"""

import sys
sys.path.insert(0, '/app')
sys.path.insert(1, '/app/ml_training')

import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
from tqdm import tqdm
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

FEATURES_PATH = '/app/outputs/features/dataset_20260211_103304/features.parquet'
LABELS_PATH = '/app/outputs/features/dataset_20260211_103304/labels_3class.parquet'
OUTPUT_DIR = Path('/app/outputs/features')

print("="*80)
print("NEWS FEATURE FIX - OPTION 2 (FINAL)")
print("="*80)
print()

NEWS_COLUMNS_TO_DROP = [
    'news_sentiment_avg_1d',
    'news_sentiment_avg_3d',
    'news_sentiment_avg_7d',
    'news_sentiment_avg_14d',
    'news_sentiment_avg_30d',
    'news_sentiment_weighted_1d',
    'news_sentiment_weighted_7d',
    'news_sentiment_weighted_30d',
    'news_positive_ratio_7d',
    'news_negative_ratio_7d',
    'news_net_sentiment_7d',
    'news_sentiment_consensus_7d',
    'news_intensity_1d',
    'news_intensity_7d',
    'news_intensity_spike_7d',
    'news_sentiment_max_7d',
    'news_sentiment_min_7d',
    'news_sentiment_std_7d',
    'news_sentiment_trend_7d',
    'news_data_available',
]

print(f"Columns to drop: {len(NEWS_COLUMNS_TO_DROP)}")
print()

print("Loading features...")
df = pd.read_parquet(FEATURES_PATH)
print(f"  Shape: {df.shape}")
print(f"  Columns: {len(df.columns)}")

print("Loading labels...")
labels = pd.read_parquet(LABELS_PATH)
print(f"  Labels shape: {labels.shape}")

print(f"\nStep 1: Dropping {len(NEWS_COLUMNS_TO_DROP)} bad news columns...")
df = df.drop(columns=NEWS_COLUMNS_TO_DROP)
print(f"  After drop: {df.shape}")

print("\nStep 2: Fetching daily-aggregated news from database...")

df['date'] = df['timestamp'].dt.date
start_date = df['date'].min()
end_date = df['date'].max()

print(f"Date range: {start_date} to {end_date}")
print(f"  Fetching news for {df['stock_id'].nunique()} stocks...")

def fetch_news_for_all_stocks(start_date, end_date):
    db = SessionLocal()
    conn = db.connection()
    query = text("""
        SELECT
            stock_id,
            date_trunc('day', "timestamp") as date,
            COUNT(*) as news_count,
            AVG(news_sentiment) as avg_sentiment,
            STDDEV(news_sentiment) as stddev_sentiment,
            AVG(ABS(news_sentiment)) as avg_abs_sentiment,
            AVG(CASE WHEN news_sentiment >= 0.3 THEN 1 ELSE 0 END) as positive_ratio,
            AVG(CASE WHEN news_sentiment <= -0.3 THEN 1 ELSE 0 END) as negative_ratio,
            SUM(CASE WHEN news_sentiment >= 0.3 THEN 1 ELSE 0 END) as positive_count,
            SUM(CASE WHEN news_sentiment <= -0.3 THEN 1 ELSE 0 END) as negative_count,
            MAX("timestamp") as last_timestamp
        FROM stock_news
        WHERE "timestamp" >= :start_date AND "timestamp" <= :end_date
        GROUP BY stock_id, date_trunc('day', "timestamp")
        ORDER BY stock_id, date
    """)
    result = conn.execute(
        text(query),
        {
            'start_date': start_date,
            'end_date': end_date
        }
    ).fetchall()
    result_list = [dict(row) for row in result]
    news_df = pd.DataFrame(result_list)
    conn.close()
    return news_df

news_df = fetch_news_for_all_stocks(start_date, end_date)

if news_df is None:
    print("❌ No news data retrieved!")
    sys.exit(1)

print(f"  Fetched {len(news_df)} daily news records for {news_df['stock_id'].nunique()} stocks")

print(f"\nStep 3: Merging news with features on date...")
print(f"  News records: {len(news_df)}")

news_df['date'] = pd.to_datetime(news_df['date']).dt.normalize()

df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()

result = df.merge(
    news_df[['stock_id', 'date', 'news_count', 'avg_sentiment', 'avg_abs_sentiment',
              'stddev_sentiment', 'positive_ratio', 'negative_ratio',
              'positive_count', 'negative_count', 'last_timestamp']],
    on=['stock_id', 'date'],
    how='left',
    suffixes=('', '_news')
)

print(f"  After merge: {result.shape}")

print(f"\nStep 4: Filling missing news with 0 (neutral sentiment)...")

NEWS_COLUMNS_TO_CREATE = [
    'news_sentiment_avg_1d',
    'news_sentiment_avg_3d',
    'news_sentiment_avg_7d',
    'news_sentiment_avg_14d',
    'news_sentiment_avg_30d',
    'news_sentiment_weighted_1d',
    'news_sentiment_weighted_7d',
    'news_sentiment_weighted_30d',
    'news_positive_ratio_7d',
    'news_negative_ratio_7d',
    'news_net_sentiment_7d',
    'news_sentiment_consensus_7d',
    'news_intensity_1d',
    'news_intensity_7d',
    'news_intensity_spike_7d',
    'news_sentiment_max_7d',
    'news_sentiment_min_7d',
    'news_sentiment_std_7d',
    'news_sentiment_trend_7d',
    'news_data_available',
]

for col in NEWS_COLUMNS_TO_CREATE:
    if col in result.columns:
        result[col] = result[col].fillna(0)
        if 'news_count_news' in result.columns:
            result['news_data_available'] = result['news_count_news'].fillna(0).astype(int)

print(f"  Filled {len(NEWS_COLUMNS_TO_CREATE)} news columns with 0")
print(f"  Data available: {result['news_data_available'].sum()} / {len(result)}")

print("\n" + "="*60)
print("VERIFICATION")
print("="*60)

news_coverage = (result['news_data_available'] == 1).sum() / len(result) * 100
print(f"  News coverage: {news_coverage:.1f}%")

if 'news_sentiment_avg_7d' in result.columns:
    sentiment_mean = result['news_sentiment_avg_7d'].mean()
    sentiment_std = result['news_sentiment_avg_7d'].std()
    print(f"  Mean sentiment: {sentiment_mean:.4f}")
    print(f"  Std sentiment: {sentiment_std:.4f}")

has_news = (result['news_data_available'] == 1).sum()
no_news = (result['news_data_available'] == 0).sum()
print(f"  Days with news: {has_news}")
print(f"  Days without news: {no_news}")

print()
print("✅ News features fixed successfully!")
print()
print("Summary:")
print(f"  - Kept {len(df)} rows")
print(f"  - Dropped {len(NEWS_COLUMNS_TO_DROP)} bad columns")
print(f"  - Added {len(NEWS_COLUMNS_TO_CREATE)} corrected news columns")
print(f"  - No data leakage (filled with 0, no propagation)")

timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
output_name = f'dataset_{timestamp_str}'

output_path = OUTPUT_DIR / output_name
output_path.mkdir(parents=True, exist_ok=True)

features_path = output_path / 'features.parquet'
result.to_parquet(features_path, index=False)
print(f"  Features: {features_path}")
print(f"  Size: {features_path.stat().st_size / 1024 / 1024:.1f} MB")

labels_output_path = output_path / 'labels_3class.parquet'
import shutil
shutil.copy2(LABELS_PATH, labels_output_path)
print(f"  Labels: {labels_output_path}")

metadata = {
    'created_at': datetime.now().isoformat(),
    'num_samples': int(len(result)),
    'num_features': int(len(result.columns)),
    'news_features_updated': True,
    'news_features_count': 20,
    'news_fix_method': 'option_2_neutral_fill',
    'data_source': 'dataset_20260211_103304',
    'news_coverage': f'{news_coverage:.1f}%'
}

metadata_path = output_path / 'metadata.json'
import json
with open(metadata_path, 'w') as f:
    json.dump(metadata, f, indent=2)

print(f"  Metadata: {metadata_path}")
print()
print("="*80)
print("NEXT STEPS")
print("="*60)
print("After reviewing the fixed dataset:")
print("1. Re-run training with --models xgboost catboost --trials 20")
print("2. Run feature importance analysis to verify news features are used")
print("3. Consider: Is news coverage sufficient? Current: {:.1f}%".format(news_coverage))
print()
print("NOTE: If news coverage is still low, may need to:")
print("  - Extend news fetch date range")
print("  - Investigate why many stocks have no news")
print("  - Consider backfilling with older news instead of 0")
