"""
Adaptive Resource Manager for ML Training

Automatically detects hardware capabilities and adjusts training parameters
to prevent OOM errors and system crashes.
"""
import os
import psutil
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import torch

logger = logging.getLogger(__name__)


@dataclass
class HardwareSpecs:
    """Detected hardware capabilities"""
    total_ram_gb: float
    available_ram_gb: float
    cpu_count: int
    gpu_available: bool
    gpu_name: Optional[str]
    gpu_total_memory_gb: float
    gpu_free_memory_gb: float

    def __str__(self):
        gpu_info = f"{self.gpu_name} ({self.gpu_total_memory_gb:.1f}GB)" if self.gpu_available else "None"
        return (
            f"Hardware Specs:\n"
            f"  RAM: {self.available_ram_gb:.1f}GB / {self.total_ram_gb:.1f}GB\n"
            f"  CPU: {self.cpu_count} cores\n"
            f"  GPU: {gpu_info}"
        )


class AdaptiveResourceManager:
    """
    Manages system resources and adapts training parameters to hardware.

    Prevents:
    - OOM (Out Of Memory) errors
    - System freezes
    - Docker container crashes
    """

    # Minimum resources required
    MIN_RAM_GB = 4.0
    MIN_GPU_MEMORY_GB = 2.0

    # Safety margins (percentage of memory to keep free)
    RAM_SAFETY_MARGIN = 0.30  # Keep 30% RAM free
    GPU_SAFETY_MARGIN = 0.25  # Keep 25% GPU memory free

    def __init__(self):
        """Initialize resource manager and detect hardware"""
        self.specs = self._detect_hardware()
        self._log_specs()

    def _detect_hardware(self) -> HardwareSpecs:
        """Detect system hardware capabilities"""
        # RAM
        ram = psutil.virtual_memory()
        total_ram_gb = ram.total / (1024**3)
        available_ram_gb = ram.available / (1024**3)

        # CPU
        cpu_count = os.cpu_count() or 4

        # GPU
        gpu_available = torch.cuda.is_available()
        gpu_name = None
        gpu_total_memory_gb = 0.0
        gpu_free_memory_gb = 0.0

        if gpu_available:
            try:
                gpu_name = torch.cuda.get_device_name(0)
                gpu_props = torch.cuda.get_device_properties(0)
                gpu_total_memory_gb = gpu_props.total_memory / (1024**3)

                # Get free memory
                torch.cuda.empty_cache()
                gpu_free_memory_gb = torch.cuda.mem_get_info()[0] / (1024**3)
            except Exception as e:
                logger.warning(f"GPU detection failed: {e}")
                gpu_available = False

        return HardwareSpecs(
            total_ram_gb=total_ram_gb,
            available_ram_gb=available_ram_gb,
            cpu_count=cpu_count,
            gpu_available=gpu_available,
            gpu_name=gpu_name,
            gpu_total_memory_gb=gpu_total_memory_gb,
            gpu_free_memory_gb=gpu_free_memory_gb
        )

    def _log_specs(self):
        """Log detected hardware"""
        logger.info("=" * 60)
        logger.info("🖥️  Hardware Detection")
        logger.info("=" * 60)
        logger.info(str(self.specs))
        logger.info("")

        # Warnings
        if self.specs.available_ram_gb < self.MIN_RAM_GB:
            logger.warning(f"⚠️  Low RAM: {self.specs.available_ram_gb:.1f}GB < {self.MIN_RAM_GB}GB")

        if self.specs.gpu_available and self.specs.gpu_total_memory_gb < self.MIN_GPU_MEMORY_GB:
            logger.warning(f"⚠️  Low GPU memory: {self.specs.gpu_total_memory_gb:.1f}GB < {self.MIN_GPU_MEMORY_GB}GB")

        logger.info("")

    def get_safe_batch_size(self, model_type: str, default_batch_size: int = 32) -> int:
        """
        Calculate safe batch size based on available resources.

        Args:
            model_type: 'xgboost', 'catboost', or 'tcn'
            default_batch_size: Default batch size if resources are plentiful

        Returns:
            Safe batch size for the model
        """
        # TCN uses GPU memory
        if model_type == 'tcn' and self.specs.gpu_available:
            safe_gpu_memory = self.specs.gpu_free_memory_gb * (1 - self.GPU_SAFETY_MARGIN)

            # TCN memory heuristic: ~100MB per sample for batch size 1
            # Approximate: batch_size * sample_memory * safety_factor
            # TCN uses more memory (sequences + gradients)
            estimated_mb_per_sample = 150
            safe_batch_size = int((safe_gpu_memory * 1024) / estimated_mb_per_sample)

            # Clamp to reasonable range
            safe_batch_size = max(1, min(safe_batch_size, 64))

            logger.info(f"📊 {model_type.upper()}: Safe batch size = {safe_batch_size} (based on {safe_gpu_memory:.1f}GB GPU)")
            return safe_batch_size

        # XGBoost and CatBoost use GPU but less memory per sample
        elif model_type in ['xgboost', 'catboost']:
            # These models handle batching internally
            return default_batch_size

        # CPU models - use RAM
        else:
            safe_ram = self.specs.available_ram_gb * (1 - self.RAM_SAFETY_MARGIN)

            # Estimate: ~1GB per 100K samples in memory
            # For batch size: smaller is safer
            if safe_ram < 2.0:
                return 8
            elif safe_ram < 4.0:
                return 16
            elif safe_ram < 8.0:
                return 32
            else:
                return default_batch_size

    def get_max_trials(self, model_type: str, default_trials: int = 100) -> int:
        """
        Calculate max trials based on hardware.

        Args:
            model_type: Model type
            default_trials: Default number of trials

        Returns:
            Adjusted number of trials
        """
        # Reduce trials for low-memory systems
        if self.specs.gpu_available:
            if self.specs.gpu_total_memory_gb < 4.0:
                # GTX 1060 3GB or similar
                reduction = 0.5
            elif self.specs.gpu_total_memory_gb < 8.0:
                # RTX 3060/3070 or similar
                reduction = 0.75
            else:
                # High-end GPU
                reduction = 1.0
        else:
            # CPU training - reduce trials significantly
            reduction = 0.25

        # TCN needs fewer trials on low GPU memory
        if model_type == 'tcn' and self.specs.gpu_available:
            if self.specs.gpu_total_memory_gb < 4.0:
                reduction = 0.15  # Very few trials for TCN on 3GB GPU

        max_trials = int(default_trials * reduction)
        max_trials = max(5, min(max_trials, default_trials))

        logger.info(f"📊 {model_type.upper()}: Max trials = {max_trials} (reduced from {default_trials})")
        return max_trials

    def get_safe_sequence_length(self, default_sequence_length: int = 60, n_features: int = 90, n_samples: int = 300000) -> int:
        """
        Calculate safe sequence length for TCN based on available RAM.

        NEW: Sequences are created on-demand per trial, not upfront.
        This allows much longer sequences since we only hold one batch in memory at a time.

        Memory calculation now assumes:
        - Batch size = 32-64 samples
        - Only sequences for one batch in memory at a time
        - Feature data stays in memory (~2GB)

        Args:
            default_sequence_length: Default sequence length (60)
            n_features: Number of features (default 90 for cleaned dataset)
            n_samples: Total number of samples (not used for calculation anymore)

        Returns:
            Safe sequence length based on available RAM
        """
        # For on-demand sequence creation, we only need memory for:
        # - One batch of sequences at a time
        # - Feature data (stays in RAM)
        # - Model and optimizer state

        batch_size = 64  # Maximum batch size
        # Memory for one batch of sequences
        safe_ram_gb = self.specs.available_ram_gb * 0.60  # Use 60% (more aggressive)
        features_overhead_gb = 2.5  # Feature data + model + optimizer
        available_for_sequences_gb = safe_ram_gb - features_overhead_gb

        if available_for_sequences_gb < 0.5:
            available_for_sequences_gb = 0.5

        # Calculate max sequence length for ONE BATCH
        # memory_gb = (batch_size * sequence_length * n_features * 4) / (1024^3)
        bytes_per_gb = 1024**3
        bytes_per_sample = n_features * 4  # float32

        max_sequence_length = int((available_for_sequences_gb * bytes_per_gb) / (batch_size * bytes_per_sample))

        # Adaptive sequence length based on available RAM tier
        if self.specs.available_ram_gb < 8:
            safe_length = min(60, max_sequence_length, default_sequence_length)
            tier = "Low RAM (<8GB)"
        elif self.specs.available_ram_gb < 12:
            safe_length = min(90, max_sequence_length, default_sequence_length)
            tier = "Medium RAM (8-12GB)"
        elif self.specs.available_ram_gb < 20:
            safe_length = min(120, max_sequence_length, default_sequence_length)
            tier = "High RAM (12-20GB)"
        else:
            # 24GB+ system - can handle very long sequences
            safe_length = min(180, max_sequence_length, default_sequence_length)
            tier = "Ultra RAM (20GB+)"

        # Enforce minimum
        safe_length = max(10, safe_length)

        # Estimate memory usage for one batch
        batch_memory_gb = (batch_size * safe_length * n_features * 4) / bytes_per_gb
        total_memory_gb = features_overhead_gb + batch_memory_gb

        logger.info(f"📊 TCN Sequence Length ({tier}, on-demand mode):")
        logger.info(f"   Available RAM: {self.specs.available_ram_gb:.1f}GB")
        logger.info(f"   Features: {n_features}")
        logger.info(f"   Sequence length: {safe_length} (default: {default_sequence_length})")
        logger.info(f"   Per-batch memory: {batch_memory_gb:.1f}GB (sequences) + {features_overhead_gb:.1f}GB (features/model) = {total_memory_gb:.1f}GB")
        logger.info(f"   Note: Sequences created on-demand per trial, not upfront")

        if total_memory_gb > self.specs.available_ram_gb * 0.70:
            logger.warning(f"⚠️  Per-batch memory ({total_memory_gb:.1f}GB) is high!")
            logger.warning(f"   Consider reducing sequence length or batch size.")

        return safe_length

    def get_tcn_num_channels(self, default_channels: list = None) -> list:
        """
        Get TCN num_channels based on both RAM and GPU memory.

        Args:
            default_channels: Default channel configuration

        Returns:
            Adjusted channel configuration based on available resources
        """
        if default_channels is None:
            default_channels = [64, 128, 64]  # Default from config.py

        # Factor in both RAM and GPU memory
        ram_limit = self.specs.available_ram_gb
        gpu_limit = self.specs.gpu_total_memory_gb if self.specs.gpu_available else 0

        # Determine tier based on both resources
        if ram_limit < 8 or gpu_limit < 4:
            # Low resource system
            channels = [32, 64, 32]
            tier = "Low (RAM <8GB or GPU <4GB)"
        elif ram_limit < 12 or gpu_limit < 8:
            # Medium resource system
            channels = [48, 96, 48]
            tier = "Medium (RAM 8-12GB or GPU 4-8GB)"
        elif ram_limit < 20 or gpu_limit < 12:
            # High resource system
            channels = [64, 128, 64]
            tier = "High (RAM 12-20GB or GPU 8-12GB)"
        else:
            # Ultra resource system (24GB RAM + high-end GPU)
            channels = [96, 192, 96]
            tier = "Ultra (RAM 20GB+ or GPU 12GB+)"

        logger.info(f"📊 TCN Channels ({tier}): {channels}")
        return channels

    def should_use_gpu(self, model_type: str) -> bool:
        """
        Determine if GPU should be used for a model.

        Args:
            model_type: Model type

        Returns:
            True if GPU should be used
        """
        if not self.specs.gpu_available:
            return False

        # TCN needs GPU
        if model_type == 'tcn':
            return True

        # XGBoost and CatBoost can use GPU
        if model_type in ['xgboost', 'catboost']:
            return True

        return False

    def get_safe_n_estimators(self, model_type: str, default_estimators: int = 1000) -> int:
        """
        Get safe number of estimators for tree-based models.

        Args:
            model_type: Model type
            default_estimators: Default n_estimators

        Returns:
            Safe n_estimators
        """
        if model_type not in ['xgboost', 'catboost']:
            return default_estimators

        # Reduce for low memory
        if self.specs.available_ram_gb < 4.0:
            return 500
        elif self.specs.available_ram_gb < 8.0:
            return 750
        else:
            return default_estimators

    def estimate_memory_usage(self, n_samples: int, n_features: int) -> Dict[str, float]:
        """
        Estimate memory usage for dataset.

        Args:
            n_samples: Number of samples
            n_features: Number of features

        Returns:
            Dict with estimated memory usage in GB
        """
        # DataFrame memory (float64)
        df_memory_gb = (n_samples * n_features * 8) / (1024**3)

        # Sequence memory for TCN (sequence_length * features * batch_size)
        seq_memory_gb = (60 * n_features * 16 * 4) / (1024**3)

        # Gradient memory (for training)
        gradient_multiplier = 2.0

        return {
            'dataframe_gb': df_memory_gb,
            'sequence_gb': seq_memory_gb,
            'total_gb': (df_memory_gb + seq_memory_gb) * gradient_multiplier,
            'available_gb': self.specs.available_ram_gb,
            'gpu_available_gb': self.specs.gpu_free_memory_gb if self.specs.gpu_available else 0
        }

    def check_memory_before_training(self, model_type: str, n_samples: int, n_features: int) -> bool:
        """
        Check if there's enough memory for training.

        Args:
            model_type: Model type
            n_samples: Number of training samples
            n_features: Number of features

        Returns:
            True if safe to train
        """
        usage = self.estimate_memory_usage(n_samples, n_features)

        logger.info(f"📊 Memory Estimate for {model_type.upper()}:")
        logger.info(f"  Dataset: {usage['dataframe_gb']:.2f}GB")
        logger.info(f"  Sequences: {usage['sequence_gb']:.2f}GB")
        logger.info(f"  Total needed: {usage['total_gb']:.2f}GB")
        logger.info(f"  Available RAM: {usage['available_gb']:.2f}GB")

        if self.specs.gpu_available:
            logger.info(f"  Available GPU: {usage['gpu_available_gb']:.2f}GB")

        # Check if enough RAM
        if usage['total_gb'] > usage['available_gb']:
            logger.warning(f"⚠️  Insufficient RAM: Need {usage['total_gb']:.2f}GB, have {usage['available_gb']:.2f}GB")
            return False

        # Check GPU memory for GPU models
        if model_type == 'tcn' and self.specs.gpu_available:
            if usage['total_gb'] > usage['gpu_available_gb']:
                logger.warning(f"⚠️  Insufficient GPU memory: Need {usage['total_gb']:.2f}GB, have {usage['gpu_available_gb']:.2f}GB")
                return False

        return True

    def clear_gpu_cache(self):
        """Clear GPU cache to free memory"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("GPU cache cleared")

    def get_current_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage"""
        ram = psutil.virtual_memory()

        result = {
            'ram_used_gb': ram.used / (1024**3),
            'ram_available_gb': ram.available / (1024**3),
            'ram_percent': ram.percent
        }

        if torch.cuda.is_available():
            result['gpu_used_gb'] = torch.cuda.memory_allocated() / (1024**3)
            result['gpu_reserved_gb'] = torch.cuda.memory_reserved() / (1024**3)
            result['gpu_free_gb'] = torch.cuda.mem_get_info()[0] / (1024**3)

        return result


# Singleton instance
_resource_manager = None


def get_resource_manager() -> AdaptiveResourceManager:
    """Get singleton resource manager instance"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = AdaptiveResourceManager()
    return _resource_manager
