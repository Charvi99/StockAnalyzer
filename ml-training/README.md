# ML-Training

Stock price prediction using machine learning with ensemble methods.

**Performance:** Uses Polars for 2-3x faster data loading and 50-70% memory reduction.

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   # For GPU support (NVIDIA):
   pip install -r requirements.gpu.txt
   ```

2. **Generate features**
   ```bash
   python scripts/create_features.py --config configs/default.yaml
   ```

3. **Create labels**
   ```bash
   python scripts/create_labels.py --config configs/binary_classification.yaml
   ```

4. **Train model**
   ```bash
   python scripts/train.py --config configs/binary_classification.yaml --model catboost
   ```

5. **Backtest**
   ```bash
   python scripts/backtest.py --model outputs/models/latest/model.pkl
   ```

## Performance

**Binary Classification (Production Ready)**
- CatBoost: 76.7% AUC, 77.2% accuracy, 0% catastrophic error
- XGBoost: 75.3% AUC, 76.8% accuracy
- Status: ✅ Production ready

**Multi-Class Classification**
- 3-Class: 78.0% AUC, 60.2% accuracy, 11.8% catastrophic error
- 5-Class: 75.4% AUC, 52.4% accuracy, 18.4% catastrophic error
- Status: ⚠️ Use with caution

## Configuration

Project uses YAML configuration files in `configs/`:

- `default.yaml` - Base configuration
- `binary_classification.yaml` - Binary buy/sell prediction
- `multiclass.yaml` - Multi-class prediction

Override with environment variables:
```bash
export ML_TRAINING_GPU_ENABLED=false
export ML_TRAINING_N_TRIALS=5
```

## Documentation

- [Quick Start Guide](QUICKSTART.md) - Detailed 4-step setup
- [Guides](docs/guides/) - How-to guides and tutorials
- [Implementation Notes](docs/implementation/) - Development summaries and session notes
- [Results](docs/results/) - Training results and comparisons
- [Plans](docs/plans/) - Roadmaps and TODOs
- [Architecture](docs/architecture.md) - System design and components
- [Framework](docs/framework.md) - ML Framework documentation
- [Configuration](docs/configuration.md) - YAML and CLI options

## Available Models

- **CatBoost** (Recommended) - Best performance, GPU support
- **XGBoost** - Strong performance, widely used
- **TabNet** - Deep learning for tabular data
- **AutoGluon** - AutoML ensemble
- **FT-Transformer** - Transformer for tabular data

## Hardware

- GPU: NVIDIA RTX 3060 12GB (optional)
- RAM: 32GB DDR4 recommended
- Storage: SSD recommended for feature caching

## Version

**Version 3.1.0** - Polars migration for 2-3x faster data operations
- Data loading: 2.4x faster
- Memory usage: ~60% reduction
- Sort operations: 2.8x faster
- Merge operations: 3.1x faster
