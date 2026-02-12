#!/bin/bash
# Training with 40 features dataset
# This script loads the new dataset, fixes data types, and runs training

echo "=================================================================="
echo "Training with 40-Feature Dataset (28 Technical + 12 Insider)"
echo "=================================================================="

cd /app

# Load the new 40-feature dataset
echo "Loading 40-feature dataset..."
python << 'EOF'
import pandas as pd
import os

# Load features
features_file = "/app/outputs/features/features_20260203_092936.parquet"
labels_file = "/app/outputs/features/labels_20260203_092936.parquet"

print(f"Loading features from: {features_file}")
features_df = pd.read_parquet(features_file)
labels_df = pd.read_parquet(labels_file)

print(f"Features shape: {features_df.shape}")
print(f"Labels shape: {labels_df.shape}")
print(f"Features columns ({len(features_df.columns)}):")
print(features_df.columns.tolist())

# Identify string columns that need encoding
string_cols = features_df.select_dtypes(include=['object']).columns.tolist()
print(f"\nString columns to encode: {string_cols}")

# Encode string columns
for col in string_cols:
    if col == 'macd_trend':
        # -1: SOLD, 0: HOLD, 1: BUY
        encoding = {'SOLD': -1, 'HOLD': 0, 'BUY': 1}
        features_df[col] = features_df[col].map(encoding).fillna(0)
    else:
        # For other string columns, use label encoding or one-hot
        features_df[col] = pd.to_numeric(features_df[col], errors='coerce').fillna(0)

# Convert all columns to float32
for col in features_df.columns:
    if features_df[col].dtype == 'object':
        features_df[col] = pd.to_numeric(features_df[col], errors='coerce').fillna(0)
    features_df[col] = features_df[col].astype('float32')

# Save cleaned dataset
output_dir = "/app/outputs/features"
timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
features_out = f"{output_dir}/features_40feat_{timestamp}.parquet"
labels_out = f"{output_dir}/labels_40feat_{timestamp}.parquet"

print(f"\nSaving cleaned dataset...")
features_df.to_parquet(features_out, index=False)
labels_df.to_parquet(labels_out, index=False)

print(f"✅ Saved to: {features_out}")
print(f"✅ Saved to: {labels_out}")
print(f"\nReady for training!")
EOF
