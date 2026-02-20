"""
Filter Features Dataset

Keeps only selected features from the features.parquet file.
"""
import pandas as pd
from pathlib import Path


def load_features(dataset_folder):
    """Load features from dataset folder"""
    dataset_path = Path("/app/outputs/features") / dataset_folder
    features_file = dataset_path / "features.parquet"

    print(f"📂 Loading features from: {features_file}")
    df = pd.read_parquet(features_file)
    print(f"   Loaded {len(df.columns)} columns, {len(df)} rows")

    return df


def load_feature_list(feature_list_file):
    """Load list of features to keep"""
    with open(feature_list_file, 'r') as f:
        features = [line.strip() for line in f if line.strip()]

    print(f"📋 Loaded {len(features)} features to keep")
    return features


def filter_features(df, features_to_keep):
    """
    Filter features to keep only selected ones.

    Keeps:
    - All features in features_to_keep list
    - Required columns: stock_id, timestamp
    """
    # Required columns that must always be kept
    required_columns = ['stock_id', 'timestamp']

    # Find available features
    available_features = set(df.columns) - set(required_columns)

    # Match features (case-insensitive)
    features_to_keep_lower = [f.lower() for f in features_to_keep]
    available_lower = {f.lower(): f for f in available_features}

    matched_features = []
    for feature_lower in features_to_keep_lower:
        if feature_lower in available_lower:
            matched_features.append(available_lower[feature_lower])

    # Build final column list
    final_columns = required_columns + matched_features

    # Add back label column if it exists
    if 'label' in df.columns:
        final_columns.append('label')

    print(f"\n✅ Feature matching:")
    print(f"   Requested: {len(features_to_keep)}")
    print(f"   Matched: {len(matched_features)}")
    print(f"   Not found: {len(features_to_keep) - len(matched_features)}")

    if len(matched_features) < len(features_to_keep):
        not_found = set(features_to_keep_lower) - set(matched_features)
        print(f"\n   Features not found:")
        for f in sorted(not_found)[:10]:
            print(f"      - {f}")
        if len(not_found) > 10:
            print(f"      ... and {len(not_found) - 10} more")

    # Filter dataframe
    df_filtered = df[final_columns]

    print(f"\n✅ Final dataset:")
    print(f"   Columns: {len(df_filtered.columns)}")
    print(f"   Rows: {len(df_filtered)}")

    return df_filtered


def save_filtered_features(df, dataset_folder):
    """Save filtered features to new dataset folder"""
    from datetime import datetime

    # Create new dataset folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_folder_name = f"dataset_filtered_{timestamp}"
    new_folder_path = Path("/app/outputs/features") / new_folder_name
    new_folder_path.mkdir(parents=True, exist_ok=True)

    # Save features
    features_file = new_folder_path / "features.parquet"
    df.to_parquet(features_file, index=False)
    print(f"\n✅ Saved features to: {features_file}")

    # Copy label files if they exist in source
    source_folder = Path("/app/outputs/features") / dataset_folder
    for label_file in source_folder.glob("labels_*.parquet"):
        import shutil
        dest_file = new_folder_path / label_file.name
        shutil.copy(label_file, dest_file)
        print(f"✅ Copied {label_file.name}")

    # Copy metadata if exists
    metadata_file = source_folder / "metadata.json"
    if metadata_file.exists():
        import shutil
        dest_metadata = new_folder_path / "metadata.json"
        shutil.copy(metadata_file, dest_metadata)
        print(f"✅ Copied metadata.json")

    # Create new metadata
    new_metadata = {
        "created_at": datetime.now().isoformat(),
        "source_dataset": dataset_folder,
        "filtering": "top100_features_plus_insider",
        "n_features": len(df.columns) - 2,  # Exclude stock_id, timestamp
        "n_rows": len(df),
        "features_kept": len(df.columns) - 2,
        "features_removed": 261 - (len(df.columns) - 2)
    }

    metadata_file = new_folder_path / "metadata.json"
    with open(metadata_file, 'w') as f:
        import json
        json.dump(new_metadata, f, indent=2)

    print(f"✅ Created metadata.json")

    return new_folder_name


def main():
    print("=" * 70)
    print("FILTER FEATURES DATASET")
    print("=" * 70)

    # Load feature list
    feature_list_file = "/app/outputs/analysis/features_to_keep_top113.txt"
    features_to_keep = load_feature_list(feature_list_file)

    # Load features (use the dataset folder from training)
    dataset_folder = "dataset_lags_20260206_111644"
    df = load_features(dataset_folder)

    # Filter features
    df_filtered = filter_features(df, features_to_keep)

    # Save filtered dataset
    new_folder = save_filtered_features(df_filtered, dataset_folder)

    print("\n" + "=" * 70)
    print("✅ FILTERING COMPLETE!")
    print("=" * 70)
    print(f"\nNew dataset folder: {new_folder}")
    print(f"Location: /app/outputs/features/{new_folder}")
    print("\nReady to train with:")
    print(f"  python train.py --trials 30 --dataset-folder {new_folder} --label-type binary")
    print("=" * 70)


if __name__ == "__main__":
    main()
