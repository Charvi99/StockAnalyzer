"""
Configuration Management for ML Training

Uses YAML config files + Python dataclasses for type safety
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml


@dataclass
class DataConfig:
    """Data configuration"""

    # Database
    database_url: str = "postgresql://stockuser:stockpass@db:5432/stockanalyzer"

    # Time range
    train_start_date: str = "2022-01-01"  # 2 years of data
    train_end_date: str = "2024-01-01"

    # Timeframe
    timeframe: str = "1d"  # Daily for swing trading

    # Split ratios
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15

    # Label parameters
    profit_target: float = 0.03  # +3%
    stop_loss: float = -0.02  # -2%
    lookahead_days: int = 20

    # Feature engineering
    use_technical_indicators: bool = True
    use_chart_patterns: bool = True
    use_candlestick_patterns: bool = True
    use_market_regime: bool = True
    use_price_history: bool = True

    # Output directories
    features_dir: Path = Path("/app/outputs/features")
    models_dir: Path = Path("/app/outputs/models")
    logs_dir: Path = Path("/app/outputs/logs")


@dataclass
class XGBoostConfig:
    """XGBoost hyperparameters"""

    # Fixed parameters
    objective: str = "binary:logistic"
    eval_metric: str = "auc"
    tree_method: str = "hist"  # Faster training, supports GPU
    device: str = "cuda"  # Use GPU for XGBoost (GTX 1060)
    n_jobs: int = 1  # GPU doesn't use n_jobs

    # Tunable parameters (search space)
    max_depth: tuple = (4, 8)  # (min, max)
    learning_rate: tuple = (0.001, 0.1)  # Log scale
    n_estimators: int = 2000
    subsample: tuple = (0.6, 0.9)
    colsample_bytree: tuple = (0.6, 0.9)
    reg_lambda: tuple = (0.0, 2.0)
    reg_alpha: tuple = (0.0, 1.0)
    min_child_weight: tuple = (1, 10)
    gamma: tuple = (0.0, 5.0)

    # Training parameters
    early_stopping_rounds: int = 100
    scale_pos_weight: Optional[float] = None  # Auto-calculated


@dataclass
class CatBoostConfig:
    """CatBoost hyperparameters"""

    # Fixed parameters
    loss_function: str = "Logloss"
    eval_metric: str = "AUC"
    task_type: str = "GPU"  # Changed to "GPU" for GTX 1060
    verbose: bool = False

    # Tunable parameters
    depth: tuple = (4, 10)
    learning_rate: tuple = (0.001, 0.1)  # Log scale
    iterations: int = 2000
    l2_leaf_reg: tuple = (1.0, 10.0)
    bagging_temperature: tuple = (0.0, 1.0)
    border_count: tuple = (64, 256)
    random_strength: tuple = (0.5, 1.5)

    # Training parameters
    early_stopping_rounds: int = 100
    class_weights: Optional[List[float]] = None  # Auto-calculated


@dataclass
class TCNConfig:
    """TCN (Temporal Convolutional Network) hyperparameters"""

    # Architecture
    input_channels: int = None  # Set based on number of features
    num_channels: List[int] = field(default_factory=lambda: [64, 128, 64])
    kernel_size: int = 3
    dropout: float = 0.2
    relu_alpha: float = 0.3  # LeakyReLU

    # Tunable parameters
    num_layers: tuple = (2, 4)
    kernel_size_range: tuple = (2, 5)  # Renamed to avoid conflict
    dropout_range: tuple = (0.1, 0.4)  # Renamed for clarity
    learning_rate: tuple = (0.0001, 0.01)  # Log scale
    batch_size: int = 64
    epochs: int = 100

    # Training
    early_stopping_patience: int = 10
    reduce_lr_patience: int = 5

    # Device
    device: str = "cuda"  # Changed to "cuda" for GPU (GTX 1060 3GB)


@dataclass
class ChronosConfig:
    """Chronos-tiny hyperparameters (Amazon's pretrained transformer)"""

    # Model
    model_name: str = "amazon/chronos-t5-tiny"  # Smallest, fastest
    context_length: int = 64  # Days of history to use
    prediction_length: int = 20  # Days to forecast
    device: str = "cuda"  # Changed to "cuda" for GPU (GTX 1060 3GB)

    # Threshold optimization (Chronos is pretrained)
    threshold_range: tuple = (0.2, 0.6)  # Search range for optimal threshold
    threshold_step: float = 0.05  # Step size for threshold search


@dataclass
class TrainingConfig:
    """Training configuration"""

    # Experiment tracking
    experiment_name: str = "stockanalyzer_ensemble"
    mlflow_tracking_uri: str = "file:///app/outputs/mlflow"

    # Optimization
    n_trials: int = 50  # Number of Optuna trials
    timeout: Optional[int] = None  # Max training time (seconds)

    # Validation
    n_folds: int = 5  # For time series cross-validation
    cv_method: str = "timeseries"  # or "purged_kfold"

    # Scoring
    primary_metric: str = "auc"  # Optimize this
    secondary_metrics: List[str] = field(default_factory=lambda: ["accuracy", "precision", "recall"])

    # Random seed
    random_seed: int = 42


@dataclass
class EnsembleConfig:
    """Ensemble configuration"""

    # Models to train
    models: List[str] = field(default_factory=lambda: ["xgboost", "catboost", "tcn", "chronos"])

    # Ensemble method
    method: str = "weighted_average"  # or "stacking", "voting"

    # Weights (if using weighted_average)
    # Will be learned by meta-learner if not specified
    weights: Optional[Dict[str, float]] = None

    # Meta-learner (for stacking)
    meta_learner: str = "logistic_regression"  # or "xgboost"


@dataclass
class Config:
    """Master configuration"""

    data: DataConfig = field(default_factory=DataConfig)
    xgboost: XGBoostConfig = field(default_factory=XGBoostConfig)
    catboost: CatBoostConfig = field(default_factory=CatBoostConfig)
    tcn: TCNConfig = field(default_factory=TCNConfig)
    chronos: ChronosConfig = field(default_factory=ChronosConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    ensemble: EnsembleConfig = field(default_factory=EnsembleConfig)

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Config":
        """Load configuration from YAML file"""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        return cls(
            data=DataConfig(**data.get('data', {})),
            xgboost=XGBoostConfig(**data.get('xgboost', {})),
            catboost=CatBoostConfig(**data.get('catboost', {})),
            tcn=TCNConfig(**data.get('tcn', {})),
            training=TrainingConfig(**data.get('training', {})),
            ensemble=EnsembleConfig(**data.get('ensemble', {}))
        )

    def to_yaml(self, yaml_path: Path):
        """Save configuration to YAML file"""
        data = {
            'data': self.data.__dict__,
            'xgboost': self.xgboost.__dict__,
            'catboost': self.catboost.__dict__,
            'tcn': self.tcn.__dict__,
            'training': self.training.__dict__,
            'ensemble': self.ensemble.__dict__
        }

        with open(yaml_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def save(self, yaml_path: Path = Path("/app/outputs/config.yaml")):
        """Save configuration"""
        self.to_yaml(yaml_path)
        print(f"✅ Configuration saved to {yaml_path}")


# Default configuration
DEFAULT_CONFIG = Config()
