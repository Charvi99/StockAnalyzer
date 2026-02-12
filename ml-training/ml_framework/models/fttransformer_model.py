"""
FT-Transformer Model Implementation

FT-Transformer (Feature Tokenizer Transformer)
Paper: "Revisiting Deep Learning Models for Tabular Data" (2021)
https://arxiv.org/abs/2106.11959

Key advantages for tabular data:
- Applies Transformer architecture to tabular features
- Handles both continuous and categorical features
- Learns feature interactions via self-attention
- State-of-the-art performance on many benchmarks
- No need for feature engineering
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import logging
import torch

try:
    from pytorch_tabular import TabularModel
    # Use fully-qualified import to avoid conflict with our config class
    from pytorch_tabular.models.ft_transformer.config import FTTransformerConfig as PyTorchFTTransformerConfig
    from pytorch_tabular.config import DataConfig, OptimizerConfig, TrainerConfig
    # Also import our config class for non-tuning case
    from ml_framework.config import FTTransformerConfig as OurFTTransformerConfig
    PYTORCH_TABULAR_AVAILABLE = True
except ImportError:
    PYTORCH_TABULAR_AVAILABLE = False
    TabularModel = None
    PyTorchFTTransformerConfig = None
    OurFTTransformerConfig = None

from ml_framework.base import BaseModel
logger = logging.getLogger(__name__)

# Class names for multi-class
CLASS_NAMES = {
    0: 'STRONG SELL',
    1: 'SELL',
    2: 'HOLD',
    3: 'BUY',
    4: 'STRONG BUY'
}


class FTTransformerModel(BaseModel):
    """FT-Transformer model wrapper for tabular deep learning"""

    def __init__(self, config: PyTorchFTTransformerConfig, trial_params: Optional[Dict] = None):
        """
        Initialize FT-Transformer model

        Args:
            config: PyTorchFTTransformerConfig (pytorch-tabular) configuration
            trial_params: Hyperparameters from Optuna trial (overrides config)
        """
        if not PYTORCH_TABULAR_AVAILABLE:
            raise ImportError(
                "pytorch-tabular is not installed. "
                "Install it with: pip install pytorch-tabular"
            )

        super().__init__(config, "fttransformer")
        self.trial_params = trial_params or {}

        # Detect device
        if torch.cuda.is_available():
            self.device = torch.device('cuda')
            self._device_str = 'cuda'
            logger.info(f"✅ FT-Transformer using GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = torch.device('cpu')
            self._device_str = 'cpu'
            logger.info("✅ FT-Transformer using CPU")

        # For storing column info
        self.categorical_cols = []
        self.continuous_cols = []

    def build_model(self, **kwargs):
        """Build FT-Transformer model"""
        # Detect if multi-class
        num_classes = kwargs.get('num_classes', 2)
        is_multiclass = num_classes > 2

        # Get parameters from config or trial params
        params = {
            'd_model': self._get_param('d_model', 192),
            'n_heads': self._get_param('n_heads', 8),
            'n_layers': self._get_param('n_layers', 6),
            'd_ffn': self._get_param('d_ffn', 256),
            'dropout': self._get_param('dropout', 0.1),
            'attention_dropout': self._get_param('attention_dropout', 0.1),
            'ffn_dropout': self._get_param('ffn_dropout', 0.1),
            'embedding_dropout': self._get_param('embedding_dropout', 0.1),
        }

        self.model_params = params

        mode_str = "multi-class" if is_multiclass else "binary"
        logger.info(f"✅ FT-Transformer model built ({mode_str}) with params: {params}")

        # Note: Actual model is built in train() method after we see the data
        return None

    def _get_param(self, param_name: str, default: Any) -> Any:
        """Get parameter from trial_params or use default"""
        if param_name in self.trial_params:
            return self.trial_params[param_name]

        # Check if it's a tuple (search space) - use midpoint
        if hasattr(self.config, param_name):
            val = getattr(self.config, param_name)
            if isinstance(val, tuple) and len(val) == 2:
                # Return midpoint of search space
                return (val[0] + val[1]) / 2
            return val

        return default

    def _detect_column_types(self, X_train: pd.DataFrame):
        """Detect categorical and continuous columns"""
        # Exclude identifier columns
        exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
        feature_cols = [col for col in X_train.columns if col not in exclude_cols]

        # Categorical columns are those with low cardinality or object type
        # For this dataset, most are numeric, but check for any string/object columns
        categorical_cols = []
        continuous_cols = []

        for col in feature_cols:
            unique_count = X_train[col].nunique()
            dtype = X_train[col].dtype

            # Consider categorical if:
            # - Object type
            # - Low cardinality (< 10 unique values)
            # - Integer type with few unique values
            if dtype == 'object' or (unique_count < 10 and dtype in ['int64', 'int32']):
                categorical_cols.append(col)
            else:
                continuous_cols.append(col)

        return categorical_cols, continuous_cols

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """
        Train FT-Transformer model

        Args:
            X_train: Training features (DataFrame or numpy array)
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
        """
        # Detect number of classes from training data
        num_classes = len(np.unique(y_train))
        is_multiclass = num_classes > 2

        # Build model if not already built
        if self.model is None:
            self.build_model(num_classes=num_classes)

        # Convert to DataFrame if needed
        if not isinstance(X_train, pd.DataFrame):
            X_train = pd.DataFrame(X_train)
        if not isinstance(X_val, pd.DataFrame):
            X_val = pd.DataFrame(X_val)

        if not isinstance(y_train, pd.Series):
            y_train = pd.Series(y_train)
        if not isinstance(y_val, pd.Series):
            y_val = pd.Series(y_val)

        # Detect column types
        categorical_cols, continuous_cols = self._detect_column_types(X_train)
        self.categorical_cols = categorical_cols
        self.continuous_cols = continuous_cols

        self.feature_cols = continuous_cols + categorical_cols

        # Prepare train and validation data with labels
        train_data = X_train[self.feature_cols].copy()
        train_data['target'] = y_train.values

        val_data = X_val[self.feature_cols].copy()
        val_data['target'] = y_val.values

        logger.info(f"✅ Continuous features: {len(continuous_cols)}")
        logger.info(f"✅ Categorical features: {len(categorical_cols)}")

        # Configure FT-Transformer
        # pytorch-tabular 1.1.0 requires task as positional arg, then set attributes
        logger.info(f"📋 PyTorchFTTransformerConfig type: {type(PyTorchFTTransformerConfig)}")
        logger.info(f"📋 PyTorchFTTransformerConfig module: {PyTorchFTTransformerConfig.__module__}")

        model_config = PyTorchFTTransformerConfig(task="classification")
        logger.info(f"✅ FTTransformerConfig created with task={model_config.task}")

        model_config.d_model = int(self._get_param('d_model', 192))
        model_config.num_heads = int(self._get_param('n_heads', 8))
        model_config.num_attn_blocks = int(self._get_param('n_layers', 6))
        model_config.ff_hidden_multiplier = int(self._get_param('d_ffn', 256)) // int(self._get_param('d_model', 192))
        model_config.attn_dropout = self._get_param('attention_dropout', 0.1)
        model_config.add_norm_dropout = self._get_param('ffn_dropout', 0.1)
        model_config.embedding_dropout = self._get_param('embedding_dropout', 0.1)

        logger.info(f"✅ FTTransformerConfig configured: d_model={model_config.d_model}, num_heads={model_config.num_heads}")

        # Data config
        data_config = DataConfig(
            target=["target"],
            continuous_cols=continuous_cols,
            categorical_cols=categorical_cols if categorical_cols else [],
            date_columns=[],  # Explicitly set to empty list
        )

        # Trainer config - minimal required parameters only
        trainer_config = TrainerConfig(
            max_epochs=self.config.max_epochs,
            batch_size=self.config.batch_size,
            accelerator='gpu' if self._device_str == 'cuda' else 'cpu',
            devices=1,
        )

        # Optimizer config
        optimizer_config = OptimizerConfig(
            optimizer=self.config.optimizer,
        )

        # Create and train model
        self.model = TabularModel(
            data_config=data_config,
            model_config=model_config,
            optimizer_config=optimizer_config,
            trainer_config=trainer_config,
        )

        logger.info("🚂 Starting FT-Transformer training...")

        self.model.fit(
            train=train_data,
            validation=val_data,
        )

        self.is_fitted = True
        logger.info(f"✅ FT-Transformer trained")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        # Convert to DataFrame if needed
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.feature_cols)

        # Use only feature columns
        X_subset = X[self.feature_cols]

        # Get predictions
        predictions = self.model.predict(X_subset)

        # Extract class predictions (column names may be 'prediction' or similar)
        if isinstance(predictions, pd.DataFrame):
            # Check for common prediction column names
            for col in ['prediction', 'pred', 'class', 'label']:
                if col in predictions.columns:
                    return predictions[col].values
            # Use first column if none match
            return predictions.iloc[:, 0].values

        return predictions

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities"""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        # Convert to DataFrame if needed
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.feature_cols)

        # Use only feature columns
        X_subset = X[self.feature_cols]

        # Get predictions
        predictions = self.model.predict(X_subset)

        # Extract probabilities
        if isinstance(predictions, pd.DataFrame):
            # Look for probability columns
            proba_cols = [col for col in predictions.columns if 'prob' in col.lower() or 'score' in col.lower()]
            if proba_cols:
                return predictions[proba_cols].values

            # If no probability columns, return prediction as one-hot
            pred_col = predictions.columns[0]
            classes = sorted(predictions[pred_col].unique())
            n_classes = len(classes)
            proba = np.zeros((len(predictions), n_classes))
            for i, cls in enumerate(classes):
                proba[predictions[pred_col] == cls, i] = 1.0
            return proba

        return predictions

    def evaluate(self, X_test, y_test) -> Dict[str, float]:
        """
        Evaluate model on test set

        Returns:
            Dict with metrics
        """
        y_pred = self.predict(X_test)
        y_prob = self.predict_proba(X_test)

        # Detect if multi-class
        num_classes = len(np.unique(y_test))
        is_multiclass = num_classes > 2

        if is_multiclass:
            # Multi-class metrics
            accuracy = accuracy_score(y_test, y_pred)

            # Use macro averaging for precision/recall
            precision = precision_score(y_test, y_pred, average='macro', zero_division=0)
            recall = recall_score(y_test, y_pred, average='macro', zero_division=0)

            # For multi-class AUC, use one-vs-rest with macro averaging
            try:
                auc = roc_auc_score(y_test, y_prob, multi_class='ovr', average='macro')
            except:
                auc = 0.5  # Fallback

            metrics = {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'auc': auc
            }

            # Add per-class metrics if 5 classes
            if num_classes == 5:
                for i in range(5):
                    class_mask = y_test == i
                    if class_mask.sum() > 0:
                        class_acc = accuracy_score(y_test[class_mask], y_pred[class_mask])
                        metrics[f'class_{i}_{CLASS_NAMES[i]}_acc'] = class_acc
        else:
            # Binary metrics
            # Handle both 2-column and 1-column probability outputs
            if y_prob.ndim == 2 and y_prob.shape[1] == 2:
                y_prob_binary = y_prob[:, 1]
            elif y_prob.ndim == 1:
                y_prob_binary = y_prob
            else:
                # Fallback
                y_prob_binary = y_prob.ravel() if y_prob.size > 0 else np.zeros(len(y_test))

            # Convert probabilities to binary predictions
            y_pred = (y_prob_binary >= 0.5).astype(int)

            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'auc': roc_auc_score(y_test, y_prob_binary)
            }

        return metrics

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from FT-Transformer"""
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        # FT-Transformer in pytorch-tabular doesn't directly expose feature importance
        # Return a message indicating this limitation
        logger.warning("⚠️  FT-Transformer does not support feature importance extraction")
        return pd.DataFrame({'feature': self.feature_cols, 'importance': 0.0})

    def _save_model(self, path: Path):
        """Save FT-Transformer model"""
        # pytorch-tabular saves to a directory
        model_dir = path / 'fttransformer_model'
        model_dir.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(model_dir))

    def _load_model(self, path: Path):
        """Load FT-Transformer model"""
        model_dir = path / 'fttransformer_model'
        # Load using pytorch-tabular's load method
        self.model = TabularModel.load_from_checkpoint(str(model_dir))
        self.is_fitted = True


def check_fttransformer_available() -> bool:
    """Check if FT-Transformer is available"""
    return PYTORCH_TABULAR_AVAILABLE
