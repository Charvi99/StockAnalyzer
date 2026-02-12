"""Model implementations"""
from .xgboost_model import XGBoostModel
from .catboost_model import CatBoostModel
from .tabnet_model import TabNetModel
from .autogluon_model import AutoGluonModel
# FT Transformer disabled due to OOM on 3GB GPU
# from .fttransformer_model import FTTransformerModel
# TCN disabled - not using
# from .tcn_model import TCNModel
# Chronos disabled - not used anymore
# from .chronos_model import ChronosModel

__all__ = [
    'XGBoostModel',
    'CatBoostModel',
    'TabNetModel',
    'AutoGluonModel',
    # 'FTTransformerModel',  # OOM on 3GB GPU
    # 'TCNModel',  # Disabled
    # 'ChronosModel',  # Disabled - not used
]
