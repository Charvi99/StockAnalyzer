"""
Professional-Grade Feature Normalization for Time Series ML

This module implements proper feature normalization for financial time series data,
designed to prevent data leakage and ensure reproducibility across different model types.

Key Features:
- Per-stock normalization for price/volume features
- Global normalization for ratios and indicators
- Time-aware fitting (train-only to prevent leakage)
- Handles different feature types appropriately
- Saves normalization parameters for reproducibility
"""

import logging
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from sklearn.preprocessing import RobustScaler, StandardScaler, MinMaxScaler
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NormalizationParams:
    """Store normalization parameters for reproducibility"""
    feature_name: str
    method: str
    per_stock: bool
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'feature_name': self.feature_name,
            'method': self.method,
            'per_stock': self.per_stock,
            'params': self.params
        }


class PerStockScaler:
    """
    Wrapper that applies scaling per-stock (group-based normalization)

    This ensures that patterns learned by the model transfer across stocks
    regardless of their absolute price/volume levels.
    """

    def __init__(self, base_scaler, feature_name: str):
        self.base_scaler = base_scaler
        self.feature_name = feature_name
        self.stock_params_ = {}  # Store per-stock parameters

    def fit(self, df: pd.DataFrame, feature_col: str, stock_col: str = 'stock_id'):
        """
        Fit scaler per-stock on training data

        Args:
            df: Training data only! (to prevent leakage)
            feature_col: Feature column to normalize
            stock_col: Stock identifier column
        """
        for stock_id in df[stock_col].unique():
            stock_data = df[df[stock_col] == stock_id][feature_col].dropna()

            if len(stock_data) == 0:
                continue

            # Fit base scaler on this stock's data
            scaler = self.base_scaler.__class__()
            scaler.fit(stock_data.values.reshape(-1, 1))

            # Store parameters
            self.stock_params_[stock_id] = {
                'center': getattr(scaler, 'center_', None),
                'scale': getattr(scaler, 'scale_', None),
                'min_': getattr(scaler, 'min_', None),
                'data_min_': getattr(scaler, 'data_min_', None),
                'data_max_': getattr(scaler, 'data_max_', None),
                'n_samples_seen_': getattr(scaler, 'n_samples_seen_', None),
            }

        return self

    def transform(self, df: pd.DataFrame, feature_col: str, stock_col: str = 'stock_id') -> np.ndarray:
        """Transform feature using per-stock parameters"""
        result = np.zeros(len(df))

        for stock_id in df[stock_col].unique():
            if stock_id not in self.stock_params_:
                # Stock not seen during fit - use median parameters
                stock_params = self._get_median_params()
            else:
                stock_params = self.stock_params_[stock_id]

            stock_mask = df[stock_col] == stock_id
            stock_data = df.loc[stock_mask, feature_col].fillna(0).values

            # Apply transformation manually
            if hasattr(self.base_scaler, 'center_'):
                # RobustScaler or StandardScaler
                center = stock_params.get('center', 0)
                scale = stock_params.get('scale', 1)
                if scale is not None and scale > 0:
                    result[stock_mask] = (stock_data - center) / scale
                else:
                    result[stock_mask] = stock_data - center
            else:
                # MinMaxScaler or other
                result[stock_mask] = stock_data

        return result

    def _get_median_params(self) -> Dict:
        """Get median parameters across all stocks for unseen stocks"""
        if not self.stock_params_:
            return {'center': 0, 'scale': 1}

        centers = [p['center'] for p in self.stock_params_.values() if p['center'] is not None]
        scales = [p['scale'] for p in self.stock_params_.values() if p['scale'] is not None]

        return {
            'center': np.median(centers) if centers else 0,
            'scale': np.median(scales) if scales else 1
        }

    def get_params(self) -> Dict:
        """Get normalization parameters for saving"""
        return self.stock_params_


class LogTransformPerStockScaler:
    """
    Apply log transform then per-stock scaling
    For volume-based features with power-law distribution
    """

    def __init__(self, base_scaler):
        self.base_scaler = base_scaler
        self.stock_params_ = {}

    def fit(self, df: pd.DataFrame, feature_col: str, stock_col: str = 'stock_id'):
        """Fit on log-transformed data per-stock"""
        for stock_id in df[stock_col].unique():
            stock_data = df[df[stock_col] == stock_id][feature_col].dropna()

            if len(stock_data) == 0:
                continue

            # For features with negative values (like OBV), use regular scaling instead of log
            # Check if we can safely apply log1p
            min_val = stock_data.min()
            if min_val < -1:
                # Can't use log transform - use regular scaling instead
                # Use robust scaling to handle outliers
                from sklearn.preprocessing import RobustScaler
                scaler = RobustScaler()
                scaler.fit(stock_data.values.reshape(-1, 1))

                self.stock_params_[stock_id] = {
                    'center': scaler.center_[0] if hasattr(scaler, 'center_') else 0,
                    'scale': scaler.scale_[0] if hasattr(scaler, 'scale_') else 1,
                    'data_min': stock_data.min(),
                    'data_max': stock_data.max(),
                    'used_log': False,
                }
            else:
                # Apply log transform: log(x + 1) to handle zeros
                log_data = np.log1p(stock_data.values)

                # Fit scaler on log-transformed data
                scaler = self.base_scaler.__class__()
                scaler.fit(log_data.reshape(-1, 1))

                # Store parameters
                self.stock_params_[stock_id] = {
                    'center': scaler.center_[0] if hasattr(scaler, 'center_') else 0,
                    'scale': scaler.scale_[0] if hasattr(scaler, 'scale_') else 1,
                    'data_min': log_data.min(),
                    'data_max': log_data.max(),
                    'used_log': True,
                }

        return self

    def transform(self, df: pd.DataFrame, feature_col: str, stock_col: str = 'stock_id') -> np.ndarray:
        """Transform with log + per-stock scaling"""
        result = np.zeros(len(df))

        for stock_id in df[stock_col].unique():
            if stock_id not in self.stock_params_:
                # Use median parameters for unseen stocks
                stock_params = self._get_median_params()
            else:
                stock_params = self.stock_params_[stock_id]

            stock_mask = df[stock_col] == stock_id
            stock_data = df.loc[stock_mask, feature_col].fillna(0).values

            # Check if this stock used log transform during fitting
            used_log = stock_params.get('used_log', True)

            if used_log:
                # Apply log transform
                data = np.log1p(stock_data)
            else:
                # Use raw data (for features with negative values)
                data = stock_data

            # Apply scaling
            center = stock_params.get('center', 0)
            if center is None:
                center = 0
            scale = stock_params.get('scale', 1)
            if scale is None or scale == 0:
                scale = 1

            result[stock_mask] = (data - center) / scale

        return result

    def _get_median_params(self) -> Dict:
        """Get median parameters across all stocks"""
        if not self.stock_params_:
            return {'center': 0, 'scale': 1, 'used_log': False}

        centers = [p['center'] for p in self.stock_params_.values() if p.get('center') is not None]
        scales = [p['scale'] for p in self.stock_params_.values() if p.get('scale') is not None and p.get('scale') > 0]
        used_logs = [p['used_log'] for p in self.stock_params_.values() if 'used_log' in p]

        return {
            'center': np.median(centers) if centers else 0,
            'scale': np.median(scales) if scales else 1,
            'used_log': any(used_logs) if used_logs else False  # Use log if any stock used it
        }

    def get_params(self) -> Dict:
        return self.stock_params_


class ProfessionalFeatureNormalizer:
    """
    Professional-grade feature normalization for financial time series

    Features are categorized by type and normalized appropriately:
    - PRICE_BASED: Per-stock RobustScaler (handles outliers)
    - VOLUME_BASED: Log transform + per-stock StandardScaler
    - RATIOS: Global RobustScaler (already bounded)
    - COUNTS: MinMax to [0,1] or pass-through
    - BINARY: Pass-through (already 0/1)
    """

    def __init__(self):
        self.scalers: Dict[str, Any] = {}
        self.feature_types: Dict[str, str] = {}
        self.is_fitted = False

    def _categorize_feature(self, feature_name: str, df: pd.DataFrame) -> str:
        """
        Categorize feature by type for appropriate normalization

        Returns: price_based, volume_based, ratios, counts, binary, or pass_through
        """
        # Check if binary (0/1 or small integer range)
        unique_vals = df[feature_name].nunique()
        if unique_vals <= 10:
            sample = df[feature_name].dropna().head(100)
            if sample.between(0, 2).all():
                return 'binary'

        # Check keywords in feature name
        if any(x in feature_name for x in [
            'price', 'close', 'open', 'high', 'low', 'adj',
            'ema', 'sma', 'rsi', 'macd', 'bb_', 'atr', 'stoch',
            'adx', 'cci', 'momentum', 'roc'
        ]):
            return 'price_based'

        elif any(x in feature_name for x in [
            'volume', 'obv', 'mfv', 'tp_vol', 'off_exchange',
            'insider_buy_value', 'insider_sell_value', 'ad_line'
        ]):
            # For volume-based features, check if they can use log transform
            feature_min = df[feature_name].min()
            # Can't use log if values are < -1 (log1p requirement)
            if feature_min < -1:
                # Feature has negative values - use robust scaling without log
                return 'volume_negative'
            else:
                # Feature is non-negative - use log transform
                return 'volume_based'

        elif any(x in feature_name for x in [
            'ratio', 'pct', 'change', 'return', '_rate',
            'net_buy_ratio', 'sentiment'
        ]):
            return 'ratios'

        elif any(x in feature_name for x in ['count', 'n_', 'cluster', 'conviction']):
            return 'counts'

        else:
            # Unknown feature - check distribution
            sample = df[feature_name].dropna().head(1000)
            feature_min = df[feature_name].min()
            if sample.abs().max() > 1e6:
                if feature_min < -1:
                    return 'volume_negative'  # Large numbers but negative
                else:
                    return 'volume_based'  # Large positive numbers
            elif sample.min() >= 0 and sample.max() <= 1:
                return 'ratios'  # Already normalized
            else:
                return 'price_based'  # Default

    def _get_scaler_for_type(self, feature_type: str, feature_name: str) -> Any:
        """Get appropriate scaler for feature type"""

        if feature_type == 'price_based':
            # Per-stock RobustScaler - handles outliers, different price levels
            return PerStockScaler(RobustScaler(), feature_name)

        elif feature_type == 'volume_based':
            # Log transform + per-stock StandardScaler
            # Log handles power-law distribution, per-stock handles different scales
            return LogTransformPerStockScaler(StandardScaler())

        elif feature_type == 'volume_negative':
            # Per-stock RobustScaler WITHOUT log transform
            # For features like OBV that can be negative
            return PerStockScaler(RobustScaler(), feature_name)

        elif feature_type == 'ratios':
            # Global RobustScaler - already roughly bounded, just handle outliers
            return RobustScaler()

        elif feature_type == 'counts':
            # MinMax to [0,1] - keeps interpretation
            return MinMaxScaler(feature_range=(0, 1))

        elif feature_type == 'binary':
            # Pass-through - already 0/1
            return None

        else:
            # Default to RobustScaler
            return RobustScaler()

    def fit(self, df: pd.DataFrame, feature_columns: List[str],
            train_mask: Optional[np.ndarray] = None) -> 'ProfessionalFeatureNormalizer':
        """
        Fit normalizer on training data only (prevents leakage)

        Args:
            df: Full dataset
            feature_columns: List of feature columns to normalize
            train_mask: Boolean mask indicating training rows (temporal split)
                       If None, uses first 70% of data (simple temporal split)
        """
        logger.info("Fitting professional feature normalizer...")

        if train_mask is None:
            # Simple temporal split: first 70% is training
            n = len(df)
            split_idx = int(n * 0.70)
            train_mask = np.zeros(n, dtype=bool)
            train_mask[:split_idx] = True
            logger.info(f"  Using temporal split: first {split_idx:,} rows for training")

        train_df = df[train_mask].copy()
        logger.info(f"  Training data: {len(train_df):,} rows")

        # Categorize and fit scalers for each feature
        for i, feature in enumerate(feature_columns):
            if feature not in df.columns:
                logger.warning(f"  Feature {feature} not found, skipping")
                continue

            # Categorize feature
            feature_type = self._categorize_feature(feature, train_df)
            self.feature_types[feature] = feature_type

            # Get appropriate scaler
            scaler = self._get_scaler_for_type(feature_type, feature)

            if scaler is None:
                logger.debug(f"  {feature}: pass-through (binary)")
                self.scalers[feature] = None
                continue

            # Fit scaler
            try:
                if isinstance(scaler, (PerStockScaler, LogTransformPerStockScaler)):
                    scaler.fit(train_df, feature, 'stock_id')
                    logger.debug(f"  {feature}: per-stock {feature_type}")
                else:
                    scaler.fit(train_df[[feature]])
                    logger.debug(f"  {feature}: global {feature_type}")

                self.scalers[feature] = scaler

            except Exception as e:
                logger.error(f"  Error fitting scaler for {feature}: {e}")
                self.scalers[feature] = None

            if (i + 1) % 50 == 0:
                logger.info(f"  Processed {i+1}/{len(feature_columns)} features...")

        self.is_fitted = True
        logger.info(f"✅ Fitted {len(self.scalers)} feature scalers")

        return self

    def transform(self, df: pd.DataFrame, feature_columns: List[str]) -> np.ndarray:
        """
        Transform features using fitted scalers

        Args:
            df: Dataset to transform
            feature_columns: List of feature columns

        Returns:
            Normalized features as numpy array (n_samples, n_features)
        """
        if not self.is_fitted:
            raise ValueError("Normalizer must be fitted before transform!")

        logger.info(f"Transforming {len(df):,} samples...")

        n_samples = len(df)
        n_features = len(feature_columns)
        X_normalized = np.zeros((n_samples, n_features), dtype=np.float32)

        for i, feature in enumerate(feature_columns):
            if feature not in df.columns:
                logger.warning(f"  Feature {feature} not found, filling with zeros")
                X_normalized[:, i] = 0
                continue

            scaler = self.scalers.get(feature)

            if scaler is None:
                # Pass-through (binary features or no scaling)
                X_normalized[:, i] = df[feature].fillna(0).values
            else:
                try:
                    if isinstance(scaler, (PerStockScaler, LogTransformPerStockScaler)):
                        X_normalized[:, i] = scaler.transform(df, feature, 'stock_id')
                    elif isinstance(scaler, (RobustScaler, StandardScaler, MinMaxScaler)):
                        X_normalized[:, i] = scaler.transform(df[[feature]]).flatten()
                    else:
                        X_normalized[:, i] = scaler.transform(df[[feature]]).flatten()

                except Exception as e:
                    logger.error(f"  Error transforming {feature}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fall back to raw data
                    X_normalized[:, i] = df[feature].fillna(0).values

            if (i + 1) % 50 == 0:
                logger.info(f"  Transformed {i+1}/{len(feature_columns)} features...")

        # Log statistics (handle NaN values properly)
        logger.info(f"✅ Transformed to shape: {X_normalized.shape}")

        # Use nan-safe statistics
        valid_mask = ~np.isnan(X_normalized)
        n_valid = valid_mask.sum()

        if n_valid > 0:
            X_valid = X_normalized[valid_mask]
            logger.info(f"  Mean: {np.mean(X_valid):.4f} (from {n_valid:,} valid values)")
            logger.info(f"  Std: {np.std(X_valid):.4f}")
            logger.info(f"  Min: {np.min(X_valid):.4f}")
            logger.info(f"  Max: {np.max(X_valid):.4f}")

        nan_count = np.isnan(X_normalized).sum()
        inf_count = np.isinf(X_normalized).sum()
        logger.info(f"  NaN count: {nan_count:,}")
        logger.info(f"  Inf count: {inf_count:,}")

        # Replace any remaining NaN/Inf with 0
        if nan_count > 0 or inf_count > 0:
            logger.warning(f"  Replacing {nan_count:,} NaN and {inf_count:,} Inf values with 0")
            X_normalized = np.nan_to_num(X_normalized, nan=0.0, posinf=0.0, neginf=0.0)

        return X_normalized

    def save(self, path: Path) -> None:
        """Save normalization parameters for reproducibility"""
        save_data = {
            'feature_types': self.feature_types,
            'scaler_params': {},
            'is_fitted': self.is_fitted
        }

        # Save scaler parameters
        for feature, scaler in self.scalers.items():
            if scaler is None:
                save_data['scaler_params'][feature] = None
            elif isinstance(scaler, PerStockScaler):
                save_data['scaler_params'][feature] = {
                    'type': 'PerStockScaler',
                    'base_type': type(scaler.base_scaler).__name__,
                    'params': scaler.get_params()
                }
            elif isinstance(scaler, LogTransformPerStockScaler):
                save_data['scaler_params'][feature] = {
                    'type': 'LogTransformPerStockScaler',
                    'base_type': type(scaler.base_scaler).__name__,
                    'params': scaler.get_params()
                }
            elif hasattr(scaler, 'get_params'):
                save_data['scaler_params'][feature] = {
                    'type': type(scaler).__name__,
                    'params': scaler.get_params()
                }
            else:
                save_data['scaler_params'][feature] = {
                    'type': type(scaler).__name__,
                    'params': {}
                }

        with open(path, 'wb') as f:
            pickle.dump(save_data, f)

        logger.info(f"✅ Saved normalization parameters to {path}")

    @classmethod
    def load(cls, path: Path) -> 'ProfessionalFeatureNormalizer':
        """Load normalization parameters from disk"""
        with open(path, 'rb') as f:
            save_data = pickle.load(f)

        normalizer = cls()
        normalizer.feature_types = save_data['feature_types']
        normalizer.is_fitted = save_data['is_fitted']

        # Reconstruct scalers
        normalizer.scalers = {}
        for feature, scaler_data in save_data['scaler_params'].items():
            if scaler_data is None:
                normalizer.scalers[feature] = None
            elif scaler_data['type'] == 'PerStockScaler':
                # Reconstruct per-stock scaler
                base_type = scaler_data['base_type']
                if base_type == 'RobustScaler':
                    base_scaler = RobustScaler()
                elif base_type == 'StandardScaler':
                    base_scaler = StandardScaler()
                else:
                    base_scaler = RobustScaler()

                per_stock_scaler = PerStockScaler(base_scaler, feature)
                per_stock_scaler.stock_params_ = scaler_data['params']
                normalizer.scalers[feature] = per_stock_scaler
            elif scaler_data['type'] == 'LogTransformPerStockScaler':
                # Reconstruct log-transform per-stock scaler
                base_type = scaler_data['base_type']
                if base_type == 'StandardScaler':
                    base_scaler = StandardScaler()
                else:
                    base_scaler = StandardScaler()

                log_scaler = LogTransformPerStockScaler(base_scaler)
                log_scaler.stock_params_ = scaler_data['params']
                normalizer.scalers[feature] = log_scaler
            else:
                # Reconstruct standard scaler
                scaler_type = scaler_data['type']
                if scaler_type == 'RobustScaler':
                    scaler = RobustScaler()
                elif scaler_type == 'StandardScaler':
                    scaler = StandardScaler()
                elif scaler_type == 'MinMaxScaler':
                    scaler = MinMaxScaler()
                else:
                    scaler = RobustScaler()

                # Set params if available
                if 'params' in scaler_data and scaler_data['params']:
                    try:
                        scaler.set_params(**scaler_data['params'])
                    except:
                        pass

                normalizer.scalers[feature] = scaler

        logger.info(f"✅ Loaded normalization parameters from {path}")
        return normalizer


def create_temporal_mask(df: pd.DataFrame,
                        train_ratio: float = 0.70,
                        val_ratio: float = 0.15,
                        time_col: str = 'timestamp') -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Create temporal train/val/test masks (prevents leakage)

    Args:
        df: Dataset with timestamp column
        train_ratio: Fraction of data for training
        val_ratio: Fraction of data for validation
        time_col: Name of timestamp column

    Returns:
        (train_mask, val_mask, test_mask) - boolean arrays
    """
    # Sort by time
    df_sorted = df.sort_values(time_col)

    n = len(df_sorted)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_mask = np.zeros(n, dtype=bool)
    val_mask = np.zeros(n, dtype=bool)
    test_mask = np.zeros(n, dtype=bool)

    train_mask[:train_end] = True
    val_mask[train_end:val_end] = True
    test_mask[val_end:] = True

    # Return masks aligned with original dataframe
    original_indices = df_sorted.index
    train_mask_full = np.zeros(len(df), dtype=bool)
    val_mask_full = np.zeros(len(df), dtype=bool)
    test_mask_full = np.zeros(len(df), dtype=bool)

    train_mask_full[original_indices[:train_end]] = True
    val_mask_full[original_indices[train_end:val_end]] = True
    test_mask_full[original_indices[val_end:]] = True

    return train_mask_full, val_mask_full, test_mask_full


def main():
    """Test the normalizer"""
    import pandas as pd

    logging.basicConfig(level=logging.INFO)

    # Load sample data
    df = pd.read_parquet('/app/outputs/features/dataset_lags_20260206_111644/features.parquet')

    # Get feature columns
    exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
    feature_cols = [col for col in df.columns if col not in exclude_cols]

    # Create temporal mask
    train_mask, val_mask, test_mask = create_temporal_mask(df)

    # Fit on training data only
    normalizer = ProfessionalFeatureNormalizer()
    normalizer.fit(df, feature_cols, train_mask)

    # Transform all data
    X_norm = normalizer.transform(df, feature_cols)

    print(f"Normalized shape: {X_norm.shape}")
    print(f"Mean: {X_norm.mean():.4f}")
    print(f"Std: {X_norm.std():.4f}")
    print(f"Min: {X_norm.min():.4f}")
    print(f"Max: {X_norm.max():.4f}")

    # Save parameters
    normalizer.save(Path('/app/outputs/features/dataset_lags_20260206_111644/normalization_params.pkl'))


if __name__ == '__main__':
    main()
