"""
Configuration Management for ML Training

Uses YAML config files + Python dataclasses for type safety
"""
from dataclasses import dataclass, field, fields
from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml
import os


def _detect_docker_environment() -> bool:
    """Detect if running inside Docker container."""
    # Check if /app directory exists (Docker volume mount point)
    if os.path.exists('/app'):
        return True
    # Check Docker-related environment variables
    if os.getenv('DOCKER_CONTAINER'):
        return True
    return False


@dataclass
class ProjectConfig:
    """Project metadata"""
    name: str = "ml-training"
    version: str = "3.0.0"
    description: str = "Stock price prediction using machine learning"


@dataclass
class DataConfig:
    """Data configuration"""

    # Base paths
    base_path: str = "/home/jakub/StockAnalyzer"
    features_path: str = "ml-training/outputs/features"
    models_path: str = "ml-training/outputs/models"
    cache_dir: str = "ml-training/.cache"

    # Explicit dataset/labels paths (optional - if set, overrides auto-detection)
    dataset_dir: Optional[str] = None  # e.g., "outputs/features/dataset_20260211_193232"
    labels_file: Optional[str] = None  # e.g., "labels_3class.parquet"

    # Database
    database_url: str = "postgresql://stockuser:stockpass@db:5432/stockanalyzer"

    # Data split ratios (for temporal splitting)
    train_ratio: float = 0.7  # 70% for training
    val_ratio: float = 0.15  # 15% for validation
    # Remaining (test) = 1 - train_ratio - val_ratio = 15%

    # Docker environment
    running_in_docker: bool = field(default_factory=_detect_docker_environment)


@dataclass
class FeaturesConfig:
    """Feature engineering configuration"""
    technical_indicators: bool = True
    swing_features: bool = True
    insider_features: bool = True
    market_features: bool = True
    news_features: bool = False


@dataclass
class LabelsConfig:
    """Label configuration"""
    type: str = "binary"  # binary | 3class | 5class
    lookahead_days: List[int] = field(default_factory=lambda: [5, 10, 20])
    quantiles: int = 5


@dataclass
class BacktestingConfig:
    """Backtesting configuration"""
    initial_capital: int = 10000
    commission: float = 0.001
    strategies: List[str] = field(default_factory=lambda: ["buy_and_hold", "ml_signal", "ensemble"])


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    mlflow_tracking: bool = True
    tensorboard: bool = False
    log_dir: str = "ml-training/logs"


@dataclass
class TrainingConfig:
    """Training configuration"""

    # Model selection
    default_model: str = "catboost"
    available_models: List[str] = field(default_factory=lambda: ["xgboost", "catboost", "tabnet", "autogluon", "fttransformer"])

    # Training parameters
    test_size: float = 0.2
    random_seed: int = 42
    n_trials: int = 10
    n_folds: int = 5
    cv_method: str = "stratified"
    timeout: int = 3600  # 1 hour timeout for hyperparameter tuning
    gpu_enabled: bool = True
    early_stopping_rounds: int = 100


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
class TabNetConfig:
    """TabNet hyperparameters"""

    # Architecture
    n_d: int = 8  # Number of decision steps
    n_a: int = 8  # Number of attention steps
    n_steps: int = 3  # Number of steps in each decision block

    # Tunable parameters
    n_d_range: tuple = (4, 16)
    n_a_range: tuple = (4, 16)
    n_steps_range: tuple = (1, 5)
    gamma: float = 1.5  # Relaxation parameter
    n_independent: int = 2  # Number of GLM layers (masked)
    n_shared: int = 2  # Number of shared layers
    learning_rate: tuple = (0.001, 0.1)  # Log scale
    lambda_sparse: float = 1e-4  # Sparsity regularization

    # Training
    batch_size: int = 256
    virtual_batch_size: int = 128
    max_epochs: int = 100
    patience: int = 10
    num_workers: int = 0

    # Model settings
    mask_type: str = "sparsemax"
    scheduler_params: Dict = field(default_factory=lambda: {"step_size": 10, "gamma": 0.9})
    seed: int = 42
    verbose: int = 1
    device_name: str = "auto"  # "auto", "cpu", "cuda"


@dataclass
class AutoGluonConfig:
    """AutoGluon hyperparameters"""

    # AutoGluon presets
    presets: str = "medium_quality_faster_train"  # or "best_quality", "high_quality"
    time_limit: int = 3600  # 1 hour max training time
    num_bag_folds: int = 5
    num_bag_sets: int = 1
    num_stack_levels: int = 1

    # Feature engineering
    verbosity: int = 2  # 0=silent, 1=warning, 2=info, 3=debug
    use_gpu: bool = True


@dataclass
class FTTransformerConfig:
    """FT-Transformer hyperparameters"""

    # Architecture
    d_model: int = 64  # Dimension of features
    nhead: int = 4  # Number of attention heads
    num_layers: int = 4  # Number of transformer layers

    # Tunable parameters
    d_ff: int = 256  # Dimension of feed-forward network
    dropout: float = 0.1
    learning_rate: tuple = (0.0001, 0.01)
    batch_size: int = 64
    epochs: int = 100

    # Training
    early_stopping_patience: int = 10
    device: str = "cuda"  # Use GPU (may OOM with 3GB)


@dataclass
class EnsembleConfig:
    """Ensemble configuration"""

    # Models to train
    models: List[str] = field(default_factory=lambda: ["xgboost", "catboost"])

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

    # Project metadata
    project: ProjectConfig = field(default_factory=ProjectConfig)

    # Data paths
    data: DataConfig = field(default_factory=DataConfig)

    # Feature toggles
    features: FeaturesConfig = field(default_factory=FeaturesConfig)

    # Label configuration
    labels: LabelsConfig = field(default_factory=LabelsConfig)

    # Training configuration
    training: TrainingConfig = field(default_factory=TrainingConfig)

    # Model-specific configs
    xgboost: XGBoostConfig = field(default_factory=XGBoostConfig)
    catboost: CatBoostConfig = field(default_factory=CatBoostConfig)
    tabnet: TabNetConfig = field(default_factory=TabNetConfig)
    autogluon: AutoGluonConfig = field(default_factory=AutoGluonConfig)
    fttransformer: FTTransformerConfig = field(default_factory=FTTransformerConfig)

    # Ensemble configuration
    ensemble: EnsembleConfig = field(default_factory=EnsembleConfig)

    # Backtesting configuration
    backtesting: BacktestingConfig = field(default_factory=BacktestingConfig)

    # Logging configuration
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Docker environment detection
    running_in_docker: bool = field(default_factory=_detect_docker_environment)

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Config":
        """Load configuration from YAML file"""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        return cls(
            data=DataConfig(**data.get('data', {})),
            xgboost=XGBoostConfig(**data.get('xgboost', {})),
            catboost=CatBoostConfig(**data.get('catboost', {})),
            tabnet=TabNetConfig(**data.get('tabnet', {})),
            autogluon=AutoGluonConfig(**data.get('autogluon', {})),
            fttransformer=FTTransformerConfig(**data.get('fttransformer', {})),
            training=TrainingConfig(**data.get('training', {})),
            ensemble=EnsembleConfig(**data.get('ensemble', {}))
        )

    def to_yaml(self, yaml_path: Path):
        """Save configuration to YAML file"""
        data = {
            'data': self.data.__dict__,
            'xgboost': self.xgboost.__dict__,
            'catboost': self.catboost.__dict__,
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


# ============================================================================
# YAML Configuration Loading Functions
# ============================================================================

def _load_config_dict(config_path: str) -> Dict[str, Any]:
    """
    Load YAML config as dictionary (for internal use in extends logic).

    Args:
        config_path: Path to YAML config file

    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    if not config_file.is_absolute():
        # Relative to ml-training directory
        config_file = Path(__file__).parent.parent / config_path

    # Load YAML config
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Handle extends directive recursively
    if 'extends' in config:
        base_config = _load_config_dict(config['extends'] + '.yaml')
        # Merge base config with current config (current overrides base)
        config = _deep_merge(base_config, config)

    return config


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file with environment variable overrides.

    Args:
        config_path: Path to YAML config file. If None, loads default.yaml

    Returns:
        Config dataclass with loaded and merged values

    Example:
        >>> config = load_config()  # Loads default.yaml
        >>> config = load_config("configs/binary_classification.yaml")
        >>> # Override with env var: ML_TRAINING_GPU_ENABLED=false
    """
    # Determine config file path
    if config_path is None:
        config_path = "configs/default.yaml"

    config_file = Path(config_path)
    if not config_file.is_absolute():
        # Relative to ml-training directory
        config_file = Path(__file__).parent.parent / config_path

    # Load YAML config
    with open(config_file, 'r') as f:
        config_dict = yaml.safe_load(f)

    # Handle extends directive for config inheritance
    if 'extends' in config_dict:
        base_config_dict = _load_config_dict(config_dict['extends'] + '.yaml')
        # Merge base config with current config (current overrides base)
        config_dict = _deep_merge(base_config_dict, config_dict)

    # Apply environment variable overrides
    config_dict = _apply_env_overrides(config_dict)

    # Map YAML sections to dataclass fields
    # Each YAML section maps to a corresponding dataclass

    # Project section
    project_dict = config_dict.get('project', {})
    project_config = {k: v for k, v in project_dict.items()}

    # Data section - map YAML names to dataclass field names
    data_dict = config_dict.get('data', {})
    data_config = {}

    # Map base_path to database_url (legacy field name)
    if 'database_url' in data_dict:
        data_config['database_url'] = data_dict['database_url']

    # Keep other data fields as-is
    for key in ['base_path', 'features_path', 'models_path', 'cache_dir']:
        if key in data_dict:
            data_config[key] = data_dict[key]

    # Override paths for Docker environment
    # In Docker, /app IS the ml-training directory (from volume mount: ./ml-training:/app)
    if _detect_docker_environment():
        data_config['base_path'] = "/app"
        # Remove 'ml-training/' prefix from relative paths since /app is already ml-training
        for key in ['features_path', 'models_path', 'cache_dir']:
            if key in data_config and data_config[key].startswith('ml-training/'):
                data_config[key] = data_config[key].replace('ml-training/', '', 1)

    # Features section
    features_dict = config_dict.get('features', {})
    features_config = {k: v for k, v in features_dict.items()}

    # Labels section
    labels_dict = config_dict.get('labels', {})
    labels_config = {k: v for k, v in labels_dict.items()}

    # Training section - field names already match
    training_dict = config_dict.get('training', {})

    # Backtesting section
    backtesting_dict = config_dict.get('backtesting', {})
    backtesting_config = {k: v for k, v in backtesting_dict.items()}

    # Logging section
    logging_dict = config_dict.get('logging', {})
    logging_config = {k: v for k, v in logging_dict.items()}

    # Model-specific configs (xgboost, catboost, tabnet, autogluon)
    xgboost_dict = config_dict.get('xgboost', {})
    catboost_dict = config_dict.get('catboost', {})
    tabnet_dict = config_dict.get('tabnet', {})
    autogluon_dict = config_dict.get('autogluon', {})
    fttransformer_dict = config_dict.get('fttransformer', {})

    # Ensemble section - map available_models from training to models in ensemble
    ensemble_dict = config_dict.get('ensemble', {})
    if 'models' not in ensemble_dict and 'available_models' in training_dict:
        ensemble_dict['models'] = training_dict['available_models']

    # Build Config dataclass with all sections
    return Config(
        project=ProjectConfig(**project_config),
        data=DataConfig(**data_config),
        features=FeaturesConfig(**features_config),
        labels=LabelsConfig(**labels_config),
        training=TrainingConfig(**training_dict),
        xgboost=XGBoostConfig(**xgboost_dict),
        catboost=CatBoostConfig(**catboost_dict),
        tabnet=TabNetConfig(**tabnet_dict),
        autogluon=AutoGluonConfig(**autogluon_dict),
        fttransformer=FTTransformerConfig(**fttransformer_dict),
        ensemble=EnsembleConfig(**ensemble_dict),
        backtesting=BacktestingConfig(**backtesting_config),
        logging=LoggingConfig(**logging_config)
    )


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to config."""
    # Environment variables use ML_TRAINING_ prefix
    # Example: ML_TRAINING_GPU_ENABLED=false

    def update_nested(d: Dict[str, Any], path: str, value: Any):
        """Update nested dictionary using dot-notation path."""
        keys = path.split('.')
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    # Check for ML_TRAINING_* environment variables
    for key, value in os.environ.items():
        if key.startswith('ML_TRAINING_'):
            # Remove prefix and convert to lowercase
            config_path = key[12:].lower().replace('__', '.')
            # Convert string value to appropriate type
            parsed_value = _parse_env_value(value)
            update_nested(config, config_path, parsed_value)

    return config


def _parse_env_value(value: str) -> Any:
    """Parse environment variable value to appropriate type."""
    # Boolean
    if value.lower() in ('true', 'yes', '1'):
        return True
    if value.lower() in ('false', 'no', '0'):
        return False

    # Number
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # List (comma-separated)
    if ',' in value:
        return [item.strip() for item in value.split(',')]

    # String
    return value
