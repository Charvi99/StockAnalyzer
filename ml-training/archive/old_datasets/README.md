# Dataset Archiving Status

## Current State (Main Directory)

As of 2026-02-12, the main directory contains:
- **Feature datasets**: 19 directories in `/home/jakub/StockAnalyzer/ml-training/outputs/features/`
- **Model directories**: 6 directories in `/home/jakub/StockAnalyzer/ml-training/outputs/models/`

## Refactoring Worktree Status

This is the refactoring worktree (feature/refactor-ml-training). The outputs/ directory does not exist in this worktree as it represents a clean slate for the v3.0.0 restructure.

## Archiving Strategy

When merging this refactoring back to main, the following archiving will be performed:

### Feature Datasets (keep latest 5)
```bash
cd /home/jakub/StockAnalyzer/ml-training/outputs/features
ls -dt */ 2>/dev/null | tail -n +6 | while read dir; do
    mv "$dir" ../../../archive/old_datasets/
done
```
**Expected**: Archive 14 old datasets (keep latest 5)

### Models (keep latest 3)
```bash
cd /home/jakub/StockAnalyzer/ml-training/outputs/models
ls -dt */ 2>/dev/null | tail -n +4 | while read dir; do
    mv "$dir" ../../../archive/old_datasets/
done
```
**Expected**: Archive 3 old models (keep latest 3)

## Migration Notes

- This refactoring worktree creates a clean structure
- The archive/old_datasets/ directory is ready to receive archived datasets
- Archiving should be performed during the merge-back process to main
- Expected disk space recovery: TBD (will be measured after archiving)

## Estimated Results

After archiving:
- Feature datasets: 5 (latest)
- Model directories: 3 (latest)
- Archived items: 17 total (14 datasets + 3 models)

## Date Created
2026-02-12 (Refactoring v3.0.0)
