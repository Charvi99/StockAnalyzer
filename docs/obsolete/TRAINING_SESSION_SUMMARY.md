# ML Training Session - Quick Start Guide

**Date**: 2026-01-30
**Status**: Data fetched, models configured, waiting for GPU driver installation

---

## 🚨 IMMEDIATE NEXT STEP (After Reboot)

### Install NVIDIA Drivers & Docker GPU Support

**You MUST reboot after installing drivers!**

```bash
# 1. Install NVIDIA proprietary driver
sudo apt update
sudo apt install nvidia-driver-535 -y

# 2. REBOOT SYSTEM
sudo reboot

# === AFTER REBOOT CONTINUE BELOW ===

# 3. Verify driver is loaded
nvidia-smi
# Should show: GeForce GTX 1060 3GB

# 4. Install NVIDIA Container Toolkit (for Docker GPU access)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 5. Restart Docker
sudo systemctl restart docker

# 6. Test GPU access from Docker
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi

# 7. Navigate to project
cd /home/jakub/StockAnalyzer

# 8. Start ML training with GPU
docker-compose down
docker-compose up -d database backend
docker-compose run --rm ml-training python /app/train.py
```

---

## 📊 Current Project Status

### Database: ✅ Ready
- **Database**: PostgreSQL initialized
- **Tables**: 13 tables created
- **Stocks**: 252 stocks tracked (was 5)
- **Data**: 333,107 hourly records fetched
- **Daily data**: ~30,400 records aggregated

### Features: ✅ Ready
- **Samples**: 25,480 training samples
- **Features**: 76 numeric features per sample
- **Date range**: 2023-01-31 to 2024-06-26
- **Labels**: 41.1% positive (hit +3% target)

### Models: ⏳ Ready to Train
- **XGBoost**: Configured for GPU
- **CatBoost**: Configured for GPU
- **TCN**: Fixed shape errors
- **Chronos**: Fixed abstract methods, transformers installed

---

## 🔧 Configuration Changes Made

### 1. Database Migration Fix
**File**: `backend/alembic/versions/87e562fc4ffb_add_technical_indicators_cache_table.py`
- Added drop table before recreate to avoid conflicts

### 2. Feature Engineering Auto-Date Detection
**File**: `ml-training/scripts/01d_feature_engineering_auto_date.py`
- Created new script that auto-detects database date range
- Filters out non-numeric features (signals, reasons)
- Saves features and labels separately

### 3. ML Config - GPU Enabled
**File**: `ml-training/ml_framework/config.py`
```python
device: str = "cuda"  # GPU for XGBoost
task_type: str = "GPU"  # GPU for CatBoost
```

### 4. Docker Compose - GPU Enabled
**File**: `docker-compose.yml`
```yaml
ml-training:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### 5. TCN Model Fixed
**File**: `ml-training/ml_framework/models/tcn_model.py`
- Fixed TemporalConvNet layers list (was empty)
- Removed duplicate pooling
- Added dynamic batch size adjustment

### 6. Chronos Model Fixed
**File**: `ml-training/ml_framework/models/chronos_model.py`
- Implemented `_save_model()` method
- Implemented `_load_model()` method

### 7. Popular Stocks Script
**File**: `backend/scripts/add_popular_stocks.py`
- Created script to add 300 popular US stocks
- Sectors: Technology, Finance, Healthcare, Energy, etc.

---

## 📁 File Locations

### Key Scripts
```
ml-training/scripts/
├── 01d_feature_engineering_auto_date.py  # Main feature engineering
├── add_popular_stocks.py                   # Add 300 stocks
└── train.py                                # Main training script

backend/scripts/
├── fetch_ml_training_data.py              # Fetch hourly data
└── aggregate_to_daily.py                   # Aggregate to daily
```

### Outputs
```
ml-training/outputs/
├── features/    # features_*.parquet files
├── models/      # Trained models
├── logs/        # Training logs
└── validation/  # Metrics CSV files
```

---

## 🚀 Training Pipeline (Full Commands)

```bash
# Navigate to project
cd /home/jakub/StockAnalyzer

# 1. Start database and backend
docker-compose up -d database backend

# 2. Add stocks (already done - 252 stocks)
docker-compose exec -T backend python /app/scripts/add_popular_stocks.py

# 3. Fetch data (already done - 333K hourly records)
echo "yes" | docker-compose exec -T backend python /app/scripts/fetch_ml_training_data.py --period 3y --interval 1h --batch-size 5

# 4. Aggregate to daily (already done)
echo "yes" | docker-compose exec -T backend python /app/scripts/aggregate_to_daily.py

# 5. Run feature engineering (already done - 25,480 samples)
docker-compose run --rm ml-training python /app/scripts/01d_feature_engineering_auto_date.py

# 6. Train models (READY TO RUN AFTER GPU SETUP)
docker-compose run --rm ml-training python /app/train.py
```

---

## ⚡ Expected Training Time (with GTX 1060 GPU)

| Model | CPU Time | GPU Time |
|-------|----------|----------|
| XGBoost (50 trials) | ~3 min | ~30 sec |
| CatBoost (50 trials) | ~3 min | ~30 sec |
| TCN (50 trials) | ~5 min | ~1 min |
| Chronos | ~10 sec | ~5 sec |
| **Total** | **~12 min** | **~2 min** |

---

## 🎯 Expected Results (with 252 stocks, 25K samples)

| Model | Expected AUC | Expected Accuracy |
|-------|-------------|------------------|
| XGBoost | 65-70% | 60-65% |
| CatBoost | 65-70% | 60-65% |
| TCN | 62-68% | 58-63% |
| Chronos | 55-60% | 55-60% |
| **Ensemble** | **70-75%** | **62-68%** |

---

## 🔍 Troubleshooting

### GPU not detected in Docker?
```bash
# Check nvidia-container-toolkit is installed
dpkg -l | grep nvidia-container-toolkit

# Check Docker can see GPU
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi
```

### Database connection issues?
```bash
# Check database is running
docker-compose ps database

# Check database has tables
docker-compose exec -T database psql -U stockuser -d stock_analyzer -c "\dt"
```

### Feature engineering not creating features?
```bash
# Check date range in database
docker-compose exec -T database psql -U stockuser -d stock_analyzer -c "
SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM stock_prices WHERE timeframe='1d';
"
```

---

## 📞 Quick Reference Commands

```bash
# Project navigation
cd /home/jakub/StockAnalyzer

# Docker operations
docker-compose up -d                    # Start all services
docker-compose down                     # Stop all services
docker-compose ps                        # Check status
docker-compose logs -f ml-training        # View training logs

# Database operations
docker-compose exec -T database psql -U stockuser -d stock_analyzer
docker-compose exec backend alembic upgrade head

# Training
docker-compose run --rm ml-training python /app/train.py

# Check GPU
nvidia-smi
docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi
```

---

## 📝 Notes

- **Polygon API Key**: Configured in `.env` file
- **Data fetched**: 3 years of hourly data (2023-01-31 to 2024-06-26)
- **Training split**: 70% train, 15% val, 15% test (temporal split)
- **Target**: +3% upside within 20 days before -2% stop loss
- **Positive class**: 41.1% of samples

---

## ✅ Success Criteria

Training is successful when:
- [x] Database initialized with 252 stocks
- [x] Data fetched and aggregated
- [x] Features engineered (25,480 samples)
- [ ] All models train without GPU errors ← **NEXT STEP**
- [ ] Ensemble AUC > 70%
- [ ] Models saved to `/app/outputs/models/`

---

**Last Updated**: 2026-01-30
**Next Action**: Install NVIDIA drivers after reboot, then run training!
