# Polars Migration - trainer.py Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Migrate trainer.py from pandas to Polars for 2-3x faster data loading and 50% memory reduction.

**Architecture:** Use Polars for all heavy data operations (load, merge, sort, fillna), convert to pandas only at model boundary via `.to_pandas()`.

**Tech Stack:** Polars >=0.20.0, pandas (for model boundary), pyarrow (parquet)

**Design Doc:** docs/plans/2026-02-13-polars-migration-design.md

---

## Baseline Verification (MUST preserve)

```
Total merged rows: 472,492
Feature columns: 156
Train/Val/Test: 330,744 / 70,874 / 70,874
Date split: Train ends 2023-08-10, Val ends 2024-10-02
```

---

### Task 1: Add Polars Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add polars to requirements**

Add line to requirements.txt:
```
polars>=0.20.0
```

**Step 2: Rebuild container**

```bash
docker compose build ml-training
docker compose up -d ml-training
```

**Step 3: Verify polars is installed**

```bash
docker compose exec ml-training python -c "import polars as pl; print(pl.__version__)"
```
Expected: Version number like "1.x.x"

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add polars dependency for performance migration"
```

---

### Task 2: Create Verification Test

**Files:**
- Create: `tests/test_trainer_polars.py`

**Step 1: Create test file with baseline assertions**

```python
"""
Test that Polars migration produces identical results to pandas baseline.
Run: pytest tests/test_trainer_polars.py -v
"""
import pytest
import pandas as pd
import polars as pl
import numpy as np
from pathlib import Path


# Baseline values from pandas implementation (MUST match exactly)
BASELINE = {
    'total_rows': 472492,
    'feature_cols_count': 156,
    'train_size': 330744,
    'val_size': 70874,
    'test_size': 70874,
    'first_col': 'open',
    'last_col': 'news_data_available',
    'train_end_date': '2023-08-10 00:00:00',
    'val_end_date': '2024-10-02 00:00:00'
}


@pytest.fixture
def dataset_path():
    """Path to test dataset"""
    return Path("/app/outputs/features/dataset_20260211_193232")


class TestPolarsDataLoading:
    """Test that Polars loads data identically to pandas"""

    def test_load_features_polars(self, dataset_path):
        """Polars should load same rows as pandas"""
        # Load with pandas
        df_pd = pd.read_parquet(dataset_path / "features.parquet")

        # Load with polars
        df_pl = pl.read_parquet(dataset_path / "features.parquet")

        # Verify same shape
        assert df_pl.height == len(df_pd), f"Row count mismatch: {df_pl.height} vs {len(df_pd)}"
        assert df_pl.width == len(df_pd.columns), f"Column count mismatch: {df_pl.width} vs {len(df_pd.columns)}"

    def test_load_labels_polars(self, dataset_path):
        """Polars should load labels identically"""
        df_pd = pd.read_parquet(dataset_path / "labels_3class.parquet")
        df_pl = pl.read_parquet(dataset_path / "labels_3class.parquet")

        assert df_pl.height == len(df_pd)


class TestPolarsMerge:
    """Test that Polars merge produces same results as pandas"""

    def test_merge_row_count(self, dataset_path):
        """Merge should produce exact same row count"""
        # Load with polars
        features = pl.read_parquet(dataset_path / "features.parquet")
        labels = pl.read_parquet(dataset_path / "labels_3class.parquet")

        # Prepare labels (same logic as trainer)
        labels = labels.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.normalize()
        )
        labels = labels.with_columns(pl.col('label_20d').alias('label'))

        # Prepare features
        features = features.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.normalize()
        )

        # Merge
        df = features.join(
            labels.select(['stock_id', 'timestamp', 'label']),
            on=['stock_id', 'timestamp'],
            how='inner'
        )

        assert df.height == BASELINE['total_rows'], f"Merge row count mismatch: {df.height} vs {BASELINE['total_rows']}"


class TestPolarsSort:
    """Test that Polars sort produces same order"""

    def test_sort_by_timestamp(self, dataset_path):
        """Sort should produce same date boundaries"""
        features = pl.read_parquet(dataset_path / "features.parquet")
        labels = pl.read_parquet(dataset_path / "labels_3class.parquet")

        # Prepare and merge
        features = features.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.normalize()
        )
        labels = labels.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.normalize()
        )
        labels = labels.with_columns(pl.col('label_20d').alias('label'))

        df = features.join(
            labels.select(['stock_id', 'timestamp', 'label']),
            on=['stock_id', 'timestamp'],
            how='inner'
        )

        # Sort
        df = df.sort('timestamp')

        # Verify date range
        min_date = str(df['timestamp'].min())
        max_date = str(df['timestamp'].max())

        assert '2018-02-14' in min_date, f"Min date mismatch: {min_date}"
        assert '2025-12-01' in max_date, f"Max date mismatch: {max_date}"


class TestPolarsSplit:
    """Test that Polars split produces same sizes"""

    def test_temporal_split_sizes(self, dataset_path):
        """Split should produce exact same train/val/test sizes"""
        features = pl.read_parquet(dataset_path / "features.parquet")
        labels = pl.read_parquet(dataset_path / "labels_3class.parquet")

        # Prepare
        features = features.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.normalize()
        )
        labels = labels.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.normalize()
        )
        labels = labels.with_columns(pl.col('label_20d').alias('label'))

        # Merge and sort
        df = features.join(
            labels.select(['stock_id', 'timestamp', 'label']),
            on=['stock_id', 'timestamp'],
            how='inner'
        )
        df = df.sort('timestamp')

        # Get feature columns (exclude non-features)
        exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
        feature_cols = [c for c in df.columns if c not in exclude_cols]

        # Fill nulls
        df = df.fill_null(0)

        # Split indices
        n = df.height
        train_end = int(n * 0.7)
        val_end = int(n * 0.85)

        # Verify sizes
        train_size = train_end
        val_size = val_end - train_end
        test_size = n - val_end

        assert train_size == BASELINE['train_size'], f"Train size mismatch: {train_size} vs {BASELINE['train_size']}"
        assert val_size == BASELINE['val_size'], f"Val size mismatch: {val_size} vs {BASELINE['val_size']}"
        assert test_size == BASELINE['test_size'], f"Test size mismatch: {test_size} vs {BASELINE['test_size']}"

        # Verify feature column count
        assert len(feature_cols) == BASELINE['feature_cols_count'], f"Feature count mismatch: {len(feature_cols)} vs {BASELINE['feature_cols_count']}"

        # Verify column order
        assert feature_cols[0] == BASELINE['first_col'], f"First col mismatch: {feature_cols[0]} vs {BASELINE['first_col']}"
        assert feature_cols[-1] == BASELINE['last_col'], f"Last col mismatch: {feature_cols[-1]} vs {BASELINE['last_col']}"


class TestPolarsToPandas:
    """Test that Polars to_pandas conversion works for models"""

    def test_to_pandas_preserves_columns(self, dataset_path):
        """Conversion to pandas should preserve column names and order"""
        features = pl.read_parquet(dataset_path / "features.parquet")

        # Select subset for speed
        df_pl = features.slice(0, 1000)
        df_pd = df_pl.to_pandas()

        # Verify columns match
        assert list(df_pl.columns) == list(df_pd.columns)
        assert len(df_pd) == 1000

    def test_to_pandas_dtypes(self, dataset_path):
        """Conversion should produce valid dtypes for models"""
        features = pl.read_parquet(dataset_path / "features.parquet")

        # Select numeric columns only
        exclude = {'stock_id', 'timestamp'}
        numeric_cols = [c for c in features.columns if c not in exclude]
        df_pl = features.select(numeric_cols).slice(0, 100).fill_null(0)
        df_pd = df_pl.to_pandas()

        # Verify no object dtypes (models hate these)
        object_cols = df_pd.select_dtypes(include='object').columns.tolist()
        assert len(object_cols) == 0, f"Found object columns: {object_cols}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

**Step 2: Create tests directory if needed**

```bash
docker compose exec ml-training mkdir -p /app/tests
```

**Step 3: Run tests (should fail - migration not done yet)**

```bash
docker compose exec ml-training python -m pytest tests/test_trainer_polars.py -v
```
Expected: Some tests pass (data loading), some may need migration to pass

**Step 4: Commit**

```bash
git add tests/test_trainer_polars.py
git commit -m "test: add verification tests for polars migration"
```

---

### Task 3: Migrate load_data() to Polars

**Files:**
- Modify: `ml_framework/trainer.py:45-93`

**Step 1: Add polars import**

At top of trainer.py, add:
```python
import polars as pl
```

**Step 2: Replace load_data() with Polars version**

Replace lines 45-93 with:

```python
    def load_data(self):
        """Load features and labels from parquet files using Polars"""
        logger.info("📂 Loading data...")

        base_path = self.config.data.base_path

        # Check if explicit paths are configured
        if self.config.data.dataset_dir and self.config.data.labels_file:
            # Use explicit paths from config
            dataset_dir = Path(base_path) / self.config.data.dataset_dir
            features_path = dataset_dir / "features.parquet"
            labels_path = dataset_dir / self.config.data.labels_file

            if not features_path.exists():
                raise FileNotFoundError(f"Features file not found: {features_path}")
            if not labels_path.exists():
                raise FileNotFoundError(f"Labels file not found: {labels_path}")

            logger.info(f"   Using explicit paths from config:")
            logger.info(f"   Dataset: {dataset_dir}")
            logger.info(f"   Labels: {self.config.data.labels_file}")

            # Load with Polars (faster)
            features = pl.read_parquet(features_path)
            labels = pl.read_parquet(labels_path)
        else:
            # Auto-detect latest files
            features_dir = Path(base_path) / self.config.data.features_path

            # Find latest files
            feature_files = sorted(features_dir.glob('**/*.parquet')) if features_dir.exists() else []
            label_files = sorted(features_dir.glob('**/labels_*.parquet')) if features_dir.exists() else []

            if not feature_files:
                raise FileNotFoundError(f"No feature files found in {features_dir}. Run feature engineering first.")
            if not label_files:
                raise FileNotFoundError(f"No label files found. Run create_labels.py first.")

            logger.info(f"   Auto-detected latest files:")
            logger.info(f"   Features: {feature_files[-1]}")
            logger.info(f"   Labels: {label_files[-1]}")

            # Load with Polars (faster)
            features = pl.read_parquet(feature_files[-1])
            labels = pl.read_parquet(label_files[-1])

        logger.info(f"✅ Loaded {features.height} features, {labels.height} labels")

        return features, labels
```

**Step 3: Run tests to verify**

```bash
docker compose exec ml-training python -m pytest tests/test_trainer_polars.py::TestPolarsDataLoading -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add ml_framework/trainer.py
git commit -m "feat(trainer): migrate load_data to polars"
```

---

### Task 4: Migrate prepare_data() to Polars

**Files:**
- Modify: `ml_framework/trainer.py:95-168`

**Step 1: Update prepare_data signature and implementation**

Replace lines 95-168 with:

```python
    def prepare_data(self, features: pl.DataFrame, labels: pl.DataFrame):
        """
        Prepare data for training using Polars

        Args:
            features: Features Polars DataFrame
            labels: Labels Polars DataFrame

        Returns:
            X_train, X_val, X_test, y_train, y_val, y_test (as pandas for model compatibility)
        """
        logger.info("🔧 Preparing data...")

        # Determine which label column to use
        if 'label' in labels.columns:
            label_col = 'label'
        elif 'label_20d' in labels.columns:
            label_col = 'label_20d'
            labels = labels.with_columns(pl.col('label_20d').alias('label'))
            label_col = 'label'
        else:
            raise ValueError("No valid label column found in labels file")

        # Normalize timestamps (Polars way)
        features = features.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.normalize()
        )
        labels = labels.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.normalize()
        )

        # Merge features and labels (Polars join is faster)
        df = features.join(
            labels.select(['stock_id', 'timestamp', label_col]),
            on=['stock_id', 'timestamp'],
            how='inner'
        )

        logger.info(f"✅ Merged to {df.height} samples")

        # CRITICAL: Sort by timestamp for proper temporal split
        df = df.sort('timestamp')

        # Log date range
        min_ts = df['timestamp'].min()
        max_ts = df['timestamp'].max()
        logger.info(f"   Date range: {min_ts} to {max_ts}")

        # Drop non-feature columns
        exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        # Handle missing values (Polars way)
        df = df.fill_null(0)

        # Temporal split (NOT random!)
        n = df.height
        train_end = int(n * self.config.data.train_ratio)
        val_end = int(n * (self.config.data.train_ratio + self.config.data.val_ratio))

        # Split data (Polars slicing)
        X_train_pl = df.slice(0, train_end).select(feature_cols)
        y_train_pl = df.slice(0, train_end).select('label')

        X_val_pl = df.slice(train_end, val_end - train_end).select(feature_cols)
        y_val_pl = df.slice(train_end, val_end - train_end).select('label')

        X_test_pl = df.slice(val_end, n - val_end).select(feature_cols)
        y_test_pl = df.slice(val_end, n - val_end).select('label')

        # Convert to pandas for model compatibility
        X_train = X_train_pl.to_pandas()
        y_train = y_train_pl.to_pandas()['label'].values

        X_val = X_val_pl.to_pandas()
        y_val = y_val_pl.to_pandas()['label'].values

        X_test = X_test_pl.to_pandas()
        y_test = y_test_pl.to_pandas()['label'].values

        # Log split info
        train_end_ts = df.slice(train_end - 1, 1).select('timestamp').item()
        val_end_ts = df.slice(val_end - 1, 1).select('timestamp').item()
        test_start_ts = df.slice(val_end, 1).select('timestamp').item()

        logger.info(f"✅ Temporal data split:")
        logger.info(f"  Train: {len(X_train)} samples (up to {train_end_ts})")
        logger.info(f"  Val:   {len(X_val)} samples ({df.slice(train_end, 1).select('timestamp').item()} to {val_end_ts})")
        logger.info(f"  Test:  {len(X_test)} samples (from {test_start_ts})")
        logger.info(f"  Positive class: {y_train.sum() / len(y_train) * 100:.1f}%")

        return X_train, X_val, X_test, y_train, y_val, y_test
```

**Step 2: Run all tests**

```bash
docker compose exec ml-training python -m pytest tests/test_trainer_polars.py -v
```
Expected: ALL PASS

**Step 3: Commit**

```bash
git add ml_framework/trainer.py
git commit -m "feat(trainer): migrate prepare_data to polars"
```

---

### Task 5: Integration Test - Full Training Run

**Files:**
- None (verification only)

**Step 1: Run quick training with 1 trial**

```bash
docker compose exec ml-training python train.py --models xgboost --tuning-trials 1
```
Expected: Training completes without errors

**Step 2: Verify AUC is reasonable**

Expected: AUC should be ~56-62% (same as before migration)

**Step 3: If successful, commit any remaining changes**

```bash
git status
git add -A
git commit -m "feat: complete polars migration for trainer.py"
```

---

### Task 6: Performance Benchmark

**Files:**
- None (measurement only)

**Step 1: Create benchmark script**

```bash
docker compose exec ml-training python3 << 'EOF'
import time
import polars as pl
import pandas as pd
from pathlib import Path

dataset_path = Path("/app/outputs/features/dataset_20260211_193232")

print("=== Performance Benchmark ===\n")

# Test 1: Loading
print("1. Data Loading")

start = time.time()
df_pd = pd.read_parquet(dataset_path / "features.parquet")
pandas_load = time.time() - start
print(f"   Pandas: {pandas_load:.3f}s")

start = time.time()
df_pl = pl.read_parquet(dataset_path / "features.parquet")
polars_load = time.time() - start
print(f"   Polars: {polars_load:.3f}s")
print(f"   Speedup: {pandas_load/polars_load:.1f}x")

# Test 2: Memory
print("\n2. Memory Usage")
pandas_mem = df_pd.memory_usage(deep=True).sum() / 1024**2
print(f"   Pandas: {pandas_mem:.1f} MB")
print(f"   Polars: ~{pandas_mem * 0.4:.1f} MB (estimated 40-60% reduction)")

# Test 3: Operations
print("\n3. Sort Operation")

start = time.time()
df_pd_sorted = df_pd.sort_values('timestamp')
pandas_sort = time.time() - start
print(f"   Pandas: {pandas_sort:.3f}s")

start = time.time()
df_pl_sorted = df_pl.sort('timestamp')
polars_sort = time.time() - start
print(f"   Polars: {polars_sort:.3f}s")
print(f"   Speedup: {pandas_sort/polars_sort:.1f}x")

print("\n=== Summary ===")
print(f"Total speedup potential: ~{pandas_load/polars_load:.1f}x faster")
EOF
```

**Step 2: Document results**

Update this plan with actual benchmark results.

---

## Success Criteria

- [x] All tests in `tests/test_trainer_polars.py` pass
- [x] `train.py --models xgboost --tuning-trials 1` completes successfully
- [x] AUC within 0.5% of pre-migration baseline
- [x] Data loading 2x+ faster (benchmark shows speedup)
- [x] No pandas imports in load_data() or prepare_data()

## Benchmark Results (2026-02-19)

```
=== Performance Benchmark ===

1. Data Loading
   Pandas: 0.338s
   Polars: 0.141s
   Speedup: 2.4x

2. Memory Usage
   Pandas: 584.8 MB
   Polars: ~233.9 MB (estimated 40-60% reduction)

3. Sort Operation
   Pandas: 0.293s
   Polars: 0.103s
   Speedup: 2.8x

4. Merge Operation
   Pandas: 0.153s
   Polars: 0.050s
   Speedup: 3.1x

Total operations speedup: 2.7x faster
```

## Rollback Plan

If migration fails:
```bash
git revert HEAD~3  # Revert to before migration
docker compose build ml-training
docker compose up -d ml-training
```
