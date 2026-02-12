"""
Validation utilities for dataset creation pipeline
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationResult:
    """Holds validation result information"""

    def __init__(self, is_valid: bool, message: str = "", details: Optional[Dict] = None):
        self.is_valid = is_valid
        self.message = message
        self.details = details or {}

    def __bool__(self):
        return self.is_valid

    def __str__(self):
        status = "✅ PASS" if self.is_valid else "❌ FAIL"
        return f"{status}: {self.message}"


def validate_dataframe(df: pd.DataFrame, stage_name: str = "DataFrame") -> ValidationResult:
    """
    Validate DataFrame has required columns and no critical issues

    Args:
        df: DataFrame to validate
        stage_name: Name of the pipeline stage for error reporting

    Returns:
        ValidationResult with status and details
    """
    logger.debug(f"Validating {stage_name}...")

    issues = []

    # Check if empty
    if df is None or len(df) == 0:
        return ValidationResult(
            is_valid=False,
            message=f"{stage_name}: DataFrame is empty",
            details={"reason": "empty_dataframe"}
        )

    # Check for required columns
    required_cols = {'stock_id', 'timestamp'}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        issues.append(f"Missing required columns: {missing_cols}")

    # Check for NaN in critical columns
    if 'stock_id' in df.columns and df['stock_id'].isna().any():
        issues.append(f"NaN values in stock_id column: {df['stock_id'].isna().sum()}")

    if 'timestamp' in df.columns and df['timestamp'].isna().any():
        issues.append(f"NaN values in timestamp column: {df['timestamp'].isna().sum()}")

    # Check data types
    if 'timestamp' in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            issues.append("timestamp column is not datetime type")

    # Check for extreme values (potential parsing errors)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if col in ['stock_id']:
            continue

        # Check for values > 1 trillion (likely parsing errors)
        max_val = df[col].abs().max()
        if max_val > 1e12:
            issues.append(f"Extreme values in {col}: max={max_val:.2e} (>1 trillion)")

    # Check for excessive NaN
    nan_percentage = (df[numeric_cols].isna().sum().sum() / (len(df) * len(numeric_cols))) * 100
    if nan_percentage > 50:
        issues.append(f"Excessive NaN values: {nan_percentage:.1f}%")

    is_valid = len(issues) == 0

    details = {
        "n_rows": len(df),
        "n_columns": len(df.columns),
        "n_stocks": df['stock_id'].nunique() if 'stock_id' in df.columns else 0,
        "date_range": (
            str(df['timestamp'].min()),
            str(df['timestamp'].max())
        ) if 'timestamp' in df.columns else None,
        "nan_percentage": nan_percentage,
        "issues": issues
    }

    message = f"{stage_name}: {len(df):,} rows, {len(df.columns)} cols"
    if issues:
        message += f" - {len(issues)} issues found"

    return ValidationResult(is_valid=is_valid, message=message, details=details)


def validate_sequences(X: np.ndarray, stage_name: str = "Sequences") -> ValidationResult:
    """
    Validate sequence array has correct shape and no critical issues

    Args:
        X: Sequence array (n_sequences, sequence_length, n_features)
        stage_name: Name of the pipeline stage

    Returns:
        ValidationResult with status and details
    """
    logger.debug(f"Validating {stage_name}...")

    issues = []

    # Check dimensions
    if X.ndim != 3:
        issues.append(f"Wrong dimensions: expected 3D array, got {X.ndim}D")
        return ValidationResult(
            is_valid=False,
            message=f"{stage_name}: Wrong dimensions",
            details={"ndim": X.ndim, "shape": X.shape, "issues": issues}
        )

    n_sequences, seq_length, n_features = X.shape

    # Check if empty
    if n_sequences == 0:
        issues.append("No sequences created")

    # Check for NaN/Inf
    nan_count = np.isnan(X).sum()
    inf_count = np.isinf(X).sum()

    if nan_count > 0:
        issues.append(f"NaN values: {nan_count:,}")

    if inf_count > 0:
        issues.append(f"Inf values: {inf_count:,}")

    # Check for extreme values (suggests normalization failed)
    if np.abs(X).max() > 1e6:
        issues.append(f"Extreme values detected: max={np.abs(X).max():.2e}")

    # Check statistics
    mean_val = np.nanmean(X)
    std_val = np.nanstd(X)

    # Properly normalized data should have mean ~0, std ~1
    # (but not strictly required at this stage)
    is_normalized = abs(mean_val) < 10 and abs(std_val) < 100

    is_valid = len(issues) == 0

    details = {
        "shape": X.shape,
        "n_sequences": n_sequences,
        "sequence_length": seq_length,
        "n_features": n_features,
        "mean": float(mean_val),
        "std": float(std_val),
        "min": float(np.nanmin(X)),
        "max": float(np.nanmax(X)),
        "nan_count": int(nan_count),
        "inf_count": int(inf_count),
        "appears_normalized": is_normalized,
        "issues": issues
    }

    message = f"{stage_name}: {n_sequences:,} sequences × {seq_length} × {n_features}"
    if issues:
        message += f" - {len(issues)} issues found"

    return ValidationResult(is_valid=is_valid, message=message, details=details)


def validate_normalization(X: np.ndarray, feature_names: list, stage_name: str = "Normalization") -> ValidationResult:
    """
    Validate normalization was applied correctly

    Args:
        X: Normalized feature array
        feature_names: List of feature names
        stage_name: Name of the pipeline stage

    Returns:
        ValidationResult with status and details
    """
    logger.debug(f"Validating {stage_name}...")

    issues = []

    # Check for NaN/Inf
    nan_count = np.isnan(X).sum()
    inf_count = np.isinf(X).sum()

    if nan_count > 0:
        issues.append(f"NaN values: {nan_count:,}")

    if inf_count > 0:
        issues.append(f"Inf values: {inf_count:,}")

    # Check statistics - use median for robustness against outliers
    median_val = np.nanmedian(X)
    mean_val = np.nanmean(X)
    std_val = np.nanstd(X)
    min_val = np.nanmin(X)
    max_val = np.nanmax(X)

    # Calculate IQR and MAD for robust statistics
    q25 = np.nanpercentile(X, 25)
    q75 = np.nanpercentile(X, 75)
    iqr = q75 - q25

    # Properly normalized data should have median near 0
    # Mean can be skewed by outliers, so use median
    if abs(median_val) > 10:
        issues.append(f"Median too large: {median_val:.4f} (expected ~0)")

    # Check IQR is reasonable (not too small or too large)
    if iqr > 100:
        issues.append(f"IQR too large: {iqr:.4f} (normalization may be insufficient)")

    # Only check for obviously unnormalized data (extreme values)
    # Values < 1 trillion are acceptable with RobustScaler and outlier features
    if abs(max_val) > 1e12:
        issues.append(f"Max value extreme: {max_val:.2e} (>1 trillion, check parsing)")

    # Primary check: No NaN/Inf (already checked above)
    # Secondary check: Median near 0 and reasonable IQR

    is_valid = len(issues) == 0

    details = {
        "n_features": len(feature_names),
        "n_samples": X.shape[0],
        "median": float(median_val),
        "mean": float(mean_val),
        "std": float(std_val),
        "iqr": float(iqr),
        "min": float(min_val),
        "max": float(max_val),
        "nan_count": int(nan_count),
        "inf_count": int(inf_count),
        "issues": issues
    }

    message = f"{stage_name}: median={median_val:.4f}, iqr={iqr:.4f}, mean={mean_val:.2f}, std={std_val:.2f}"
    if issues:
        message += f" - {len(issues)} issues found"

    return ValidationResult(is_valid=is_valid, message=message, details=details)


def print_validation_summary(results: list, title: str = "Validation Summary"):
    """Print formatted validation summary"""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    all_passed = True
    for result in results:
        print(result)
        if not result.is_valid:
            all_passed = False
            if result.details.get("issues"):
                print("  Issues:")
                for issue in result.details["issues"]:
                    print(f"    - {issue}")

    print("=" * 70)
    if all_passed:
        print("✅ All validations passed!")
    else:
        print("❌ Some validations failed - check issues above")
    print("=" * 70)

    return all_passed
