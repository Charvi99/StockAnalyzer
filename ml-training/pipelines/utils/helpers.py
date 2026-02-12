"""
Helper utilities for dataset creation pipeline
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Paths
OUTPUTS_DIR = Path('/app/outputs')
FEATURES_DIR = OUTPUTS_DIR / 'features'


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    """
    Setup logging for pipeline execution

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file to log to

    Returns:
        Configured logger
    """
    logger = logging.getLogger("dataset_pipeline")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_latest_dataset_folder() -> Optional[Path]:
    """
    Get the most recent dataset folder

    Returns:
        Path to latest dataset folder or None if no datasets exist
    """
    if not FEATURES_DIR.exists():
        return None

    dataset_folders = [
        d for d in FEATURES_DIR.iterdir()
        if d.is_dir() and d.name.startswith('dataset_')
    ]

    if not dataset_folders:
        return None

    # Sort by modification time (most recent first)
    dataset_folders.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return dataset_folders[0]


def create_dataset_folder_name() -> str:
    """
    Generate timestamped dataset folder name

    Returns:
        Folder name like "dataset_20260206_123045"
    """
    return f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def get_or_create_dataset_folder(dataset_name: Optional[str] = None) -> Path:
    """
    Get existing dataset folder or create new one

    Args:
        dataset_name: Specific dataset folder name (uses latest if None)

    Returns:
        Path to dataset folder
    """
    if dataset_name:
        folder = FEATURES_DIR / dataset_name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    # Use latest or create new
    latest = get_latest_dataset_folder()
    if latest:
        return latest

    new_name = create_dataset_folder_name()
    folder = FEATURES_DIR / new_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def print_stage_header(stage_name: str, description: str = ""):
    """Print formatted stage header"""
    print("\n" + "=" * 70)
    print(f"STAGE: {stage_name}")
    if description:
        print(f"       {description}")
    print("=" * 70)


def print_stage_success(stage_name: str, details: str = ""):
    """Print formatted stage success message"""
    print(f"\n✅ {stage_name} completed successfully")
    if details:
        print(f"   {details}")


def print_stage_error(stage_name: str, error: Exception):
    """Print formatted stage error message"""
    print(f"\n❌ {stage_name} failed")
    print(f"   Error: {str(error)}")
    import traceback
    print("\nTraceback:")
    traceback.print_exc()


def format_size(bytes_size: int) -> str:
    """Format bytes to human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


def format_number(num: int) -> str:
    """Format number with thousands separator"""
    return f"{num:,}"
