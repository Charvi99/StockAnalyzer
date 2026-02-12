# Dataset Creation Pipeline

Professional-grade dataset creation pipeline for TCN, LSTM, and Transformer models.

## Overview

This pipeline creates properly normalized, stock-wise sequential data for time-series ML models. It handles:

- **Data loading** from PostgreSQL database
- **Feature engineering** (technical indicators + lag features)
- **Label creation** (binary, 3-class, 5-class)
- **Sequence creation** (stock-wise, not mixed)
- **Feature normalization** (RobustScaler, train-only fit to prevent leakage)

## Key Features

### Professional Data Quality

- **Time-series aware**: Temporal train/val/test split (no look-ahead bias)
- **No data leakage**: Normalization fitted on training data only
- **Stock-wise sequences**: Each sequence contains consecutive days from SAME stock
- **Outlier handling**: RobustScaler handles extreme values (insider trading data)
- **Validation at each stage**: Automatic checks with detailed error reporting

### Reusable Datasets

- **No baked-in labels**: Normalized sequences can be reused for all label types
- **Metadata saved**: All parameters and feature types documented
- **Reproducible**: Normalization parameters saved for consistency

## Directory Structure

```
ml-training/pipelines/
├── README.md                           # This file
├── dataset_creation/
│   ├── __init__.py
│   ├── pipeline.py                     # Main orchestration script
│   └── stages/
│       ├── __init__.py
│       ├── stage1_load_data.py         # Load from database
│       ├── stage2_feature_engineering.py  # Technical indicators
│       ├── stage3_create_labels.py     # Binary/3class/5class
│       ├── stage4_create_sequences.py  # Stock-wise sequences
│       └── stage5_normalize_sequences.py  # RobustScaler normalization
└── utils/
    ├── __init__.py
    ├── validators.py                   # Validation functions
    └── helpers.py                      # Helper utilities
```

## Usage

### Quick Start - Run Full Pipeline

```bash
# Run complete pipeline with default settings
python -m pipelines.dataset_creation.pipeline --full

# Run with specific label type
python -m pipelines.dataset_creation.pipeline --full --label-type 3class

# Run with custom parameters
python -m pipelines.dataset_creation.pipeline --full \
    --label-type binary \
    --sequence-length 20 \
    --start-date 2018-01-01 \
    --upside-threshold 0.05
```

### Run Specific Stages

```bash
# Run only stages 1-3 (load data, feature engineering, create labels)
python -m pipelines.dataset_creation.pipeline --stages 1 2 3

# Run only normalization (stage 5) on existing features
python -m pipelines.dataset_creation.pipeline --stages 5 \
    --dataset-name dataset_lags_20260206_111644
```

### Command-Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--full` | flag | - | Run full pipeline (all stages) |
| `--stages` | int[] | - | Run specific stages (e.g., `--stages 1 2 3`) |
| `--dataset-name` | str | auto | Dataset folder name (auto-generates with timestamp) |
| `--label-type` | str | binary | Label type: binary, 3class, 5class |
| `--sequence-length` | int | 20 | Sequence length in days |
| `--start-date` | str | 2018-01-01 | Start date for data loading |
| `--no-lags` | flag | - | Skip lag features |
| `--forward-days` | int | 5 | Forward days for label calculation |
| `--upside-threshold` | float | 0.03 | Upside threshold (0.03 = 3%) |
| `--downside-threshold` | float | -0.03 | Downside threshold (-0.03 = -3%) |
| `--train-ratio` | float | 0.70 | Train ratio for temporal split |
| `--log-level` | str | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Pipeline Stages

### Stage 1: Load Data

Loads stock price data from PostgreSQL database.

**Inputs:**
- Database connection (PostgreSQL)
- Start date (default: 2018-01-01)

**Outputs:**
- DataFrame with: stock_id, timestamp, open, high, low, close, volume, adj_close

**Validation checks:**
- Required columns exist
- No NaN in stock_id or timestamp
- Timestamp is datetime type
- No extreme values (>1 trillion = parsing error)

### Stage 2: Feature Engineering

Creates technical indicators and lag features.

**Inputs:**
- Price data from Stage 1

**Outputs:**
- 261 features:
  - Technical indicators (RSI, MACD, Bollinger Bands, etc.)
  - Lag features (1, 2, 3, 5, 10, 20 day lags)
  - Volume indicators
  - Price ratios

**Validation checks:**
- All columns numeric
- No excessive NaN (>50%)
- No parsing errors (extreme values)

### Stage 3: Create Labels

Creates prediction labels for ML training.

**Inputs:**
- Features from Stage 2
- Label type (binary/3class/5class)
- Forward days (default: 5)
- Thresholds (default: ±3%)

**Outputs:**
- `label` column added to DataFrame

**Label types:**

| Type | Classes | Distribution |
|------|---------|--------------|
| binary | 0, 1 | 0: price down/flat, 1: price up >3% |
| 3class | 0, 1, 2 | 0: down >3%, 1: flat ±3%, 2: up >3% |
| 5class | 0, 1, 2, 3, 4 | Quintiles of 5-day returns |

**Validation checks:**
- Label column exists
- Label distribution is reasonable
- No excessive NaN labels

### Stage 5: Normalize Sequences

Applies professional feature normalization and creates normalized sequences.

**Normalization strategy:**
- **RobustScaler** for all features: (x - median) / IQR
- **Train-only fit**: Fit on first 70% of data (temporal split)
- **Global normalization**: Not per-stock (simpler, more reliable)
- **No log transforms**: Avoids NaN issues with negative values (OBV)

**Inputs:**
- Features + labels from Stage 3
- Sequence length (default: 20 days)
- Train ratio (default: 0.70)

**Outputs:**
- `sequences_normalized_20d.npz`: Normalized sequences
  - `X`: (n_sequences, sequence_length, n_features) - normalized features
  - `stock_ids`: Stock ID for each sequence
  - `timestamps`: Timestamp for each sequence
  - `feature_columns`: Feature names
  - `normalization_method`: 'global_robust_scaler'

- `normalization_metadata.json`: Metadata
  - num_features, num_sequences, date_created

**Validation checks:**
- No NaN/Inf values
- Mean ~0, Std ~1 (properly normalized)
- No extreme values (>1 billion)

## Output Files

After running the full pipeline, you'll have:

```
/app/outputs/features/
└── dataset_YYYYMMDD_HHMMSS/
    ├── features.parquet              # Engineered features (all stages)
    ├── sequences_normalized_20d.npz  # Normalized sequences (for ML)
    └── normalization_metadata.json   # Metadata
```

## Using the Output

### Load Normalized Sequences

```python
import numpy as np

# Load
data = np.load('/app/outputs/features/dataset_20260206_120000/sequences_normalized_20d.npz')

X = data['X']                    # (n_sequences, 20, 261)
stock_ids = data['stock_ids']    # (n_sequences,)
timestamps = data['timestamps']  # (n_sequences,)
feature_columns = data['feature_columns']  # Feature names

print(f"Sequences: {X.shape}")
print(f"Features: {len(feature_columns)}")
```

### Merge with Labels Dynamically

```python
import pandas as pd

# Load features
df = pd.read_parquet('/app/outputs/features/dataset_20260206_120000/features.parquet')

# Create labels for different types
from scripts.create_labels import create_binary_labels, create_3class_labels

df_binary = create_binary_labels(df.copy(), forward_days=5, upside_threshold=0.03)
df_3class = create_3class_labels(df.copy(), forward_days=5)

# Use with normalized sequences (which have no baked-in labels)
# This allows reusing the same normalized sequences for all label types!
```

## Validation and Error Handling

The pipeline includes comprehensive validation at each stage:

### Automatic Validation

Each stage runs automatic checks:
- Required columns exist
- Data types are correct
- No critical issues (excessive NaN, extreme values, etc.)

### Validation Output

```
======================================================================
Validation Summary
======================================================================
✅ PASS: Loaded Data: 433,756 rows, 10 cols
✅ PASS: Engineered Features: 433,756 rows, 274 cols - 261 features
✅ PASS: Created binary labels
✅ PASS: Normalized Sequences: mean=0.1234, std=1.4567
======================================================================
✅ All validations passed!
======================================================================
```

### Validation Failures

If validation fails, you'll see:
- ❌ Error message
- Detailed issues list
- Traceback for debugging

```
❌ FAIL: Engineered Features - 3 issues found
  Issues:
    - Extreme values in insider_buy_value_30d: max=4.00e+15 (>1 trillion)
    - Excessive NaN values: 65.3%
    - Missing required columns: {'volume'}
```

## Troubleshooting

### Common Issues

**Issue:** `RuntimeWarning: invalid value encountered in log1p`

**Cause:** OBV or other indicators have values < -1, log1p() can't handle negative values

**Solution:** Pipeline uses RobustScaler (no log transform) to avoid this

**Issue:** `Extreme values detected: max=4.00e+15`

**Cause:** Parsing errors in insider trading data (AIG, PRU)

**Solution:** Remove problematic stocks or fix parsing in backend

**Issue:** CUDA Out of Memory

**Cause:** Sequence length too long for GPU memory

**Solution:** Reduce `--sequence-length` (default: 20 is optimized for 12GB GPU)

### Debug Mode

For detailed logging, use `--log-level DEBUG`:

```bash
python -m pipelines.dataset_creation.pipeline --full --log-level DEBUG
```

### Continuing from Intermediate Stage

If pipeline fails at a stage, you can continue from the next stage:

```bash
# Pipeline failed at stage 3, continue from stage 5
python -m pipelines.dataset_creation.pipeline --stages 5 \
    --dataset-name dataset_20260206_120000
```

## Integration with ML Training

### For TCN Training

```python
from ml_framework.config import TCNConfig, DataConfig

# Update config to use pre-created sequences
config = TCNConfig(
    data=DataConfig(
        dataset_folder="dataset_lags_20260206_111644",
        label_type="binary"
    ),
    sequence_length=20
)

# Train TCN with pre-normalized sequences
# (This bypasses sequence creation in trainer.py)
```

## Performance

### Typical Runtime

- Stage 1 (Load data): ~5 minutes (433k rows)
- Stage 2 (Feature engineering): ~15 minutes (261 features)
- Stage 3 (Create labels): ~2 minutes
- Stage 5 (Normalize): ~15 minutes

**Total:** ~45-60 minutes for full pipeline

### Memory Usage

- Peak RAM: ~8 GB (when creating sequences)
- Disk usage: ~1 GB (features.parquet + sequences_normalized_20d.npz)

## Contributing

### Adding New Stages

1. Create new stage file in `stages/`
2. Inherit from base pattern (validate → process → save)
3. Add to `stages/__init__.py`
4. Update `pipeline.py` to run new stage

### Adding New Validations

Add new validation functions in `utils/validators.py`:
- Follow `ValidationResult` pattern
- Return is_valid, message, details dict
- Add to relevant stage's validation
