#!/usr/bin/env python3
"""
Compare CatBoost, XGBoost, and TabNet models on test set
"""
import numpy as np
import pandas as pd
from pathlib import Path
import json
import sys
import os

# Load test data
print("=" * 70)
print("LOADING DATA")
print("=" * 70)

features_dir = Path("/app/outputs/features")
dataset_folder = "dataset_lags_20260206_111644"

# Load features and labels from parquet
features_path = features_dir / dataset_folder / "features.parquet"
labels_path = features_dir / dataset_folder / "labels_3class.parquet"

print(f"Loading features from {features_path}")
features = pd.read_parquet(features_path)
print(f"Loading labels from {labels_path}")
labels = pd.read_parquet(labels_path)

# Merge features and labels
df = pd.merge(
    features,
    labels[['stock_id', 'timestamp', 'label']],
    on=['stock_id', 'timestamp'],
    how='inner'
)

print(f"Merged to {len(df)} samples")

# Define feature columns
exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
feature_cols = [col for col in df.columns if col not in exclude_cols]

# Handle missing values
X = df[feature_cols].fillna(0)
y = df['label']

# Temporal split (same as trainer)
unique_timestamps = np.sort(df['timestamp'].unique())
n_timestamps = len(unique_timestamps)
train_end_idx = int(n_timestamps * 0.70)
val_end_idx = int(n_timestamps * 0.85)

train_timestamps = unique_timestamps[:train_end_idx]
val_timestamps = unique_timestamps[train_end_idx:val_end_idx]
test_timestamps = unique_timestamps[val_end_idx:]

# Create test set
test_mask = df['timestamp'].isin(test_timestamps)
X_test = X[test_mask].values
y_test = y[test_mask].values

print(f"Test set size: {X_test.shape}")
print(f"Test set distribution:")
unique, counts = np.unique(y_test, return_counts=True)
for cls, count in zip(unique, counts):
    print(f"  Class {cls}: {count} ({count/len(y_test)*100:.1f}%)")

# Load models
print("\n" + "=" * 70)
print("LOADING MODELS")
print("=" * 70)

from catboost import CatBoostClassifier
import xgboost as xgb
from pytorch_tabnet.tab_model import TabNetClassifier

# Load CatBoost
print("\nLoading CatBoost...")
catboost_meta = json.load(open('/app/outputs/models/catboost/v1.0.0-3class/metadata.json'))
print(f"  Validation AUC: {catboost_meta.get('validation_auc', 'N/A')}")
catboost_model = CatBoostClassifier()
catboost_model.load_model('/app/outputs/models/catboost/v1.0.0-3class/model.cbm')

# Load XGBoost (using native API to avoid sklearn compatibility issues)
print("\nLoading XGBoost...")
xgboost_meta = json.load(open('/app/outputs/models/xgboost/v1.0.0-3class/metadata.json'))
print(f"  Validation AUC: {xgboost_meta.get('validation_auc', 'N/A')}")
xgboost_model = xgb.Booster()
xgboost_model.load_model('/app/outputs/models/xgboost/v1.0.0-3class/model.json')

# Load TabNet
print("\nLoading TabNet...")
try:
    tabnet_meta = json.load(open('/app/outputs/models/tabnet/latest/metadata.json'))
    print(f"  Validation AUC: {tabnet_meta.get('validation_auc', 'N/A')}")
except:
    print("  Warning: Could not load metadata, continuing...")
tabnet_model = TabNetClassifier()
tabnet_model.load_model('/app/outputs/models/tabnet/latest/tabnet_model.zip.zip')

models = {
    'catboost': catboost_model,
    'tabnet': tabnet_model
}
# Note: XGBoost model has feature mismatch with current dataset, skipping

# Evaluate all models
print("\n" + "=" * 70)
print("TEST SET EVALUATION")
print("=" * 70)

from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix, roc_auc_score

results = {}

# CatBoost
model_name = 'catboost'
print(f"\n{model_name.upper()}:")
print("-" * 70)

y_pred = models[model_name].predict(X_test)
y_proba = models[model_name].predict_proba(X_test)

accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, average='weighted')
recall = recall_score(y_test, y_pred, average='weighted')
auc = roc_auc_score(y_test, y_proba, multi_class='ovr', average='weighted')
cm = confusion_matrix(y_test, y_pred)

results[model_name] = {
    'accuracy': accuracy,
    'precision': precision,
    'recall': recall,
    'auc': auc,
    'confusion_matrix': cm,
    'predictions': y_pred,
    'probabilities': y_proba
}

print(f"  Accuracy:  {accuracy*100:.2f}%")
print(f"  Precision: {precision*100:.2f}%")
print(f"  Recall:    {recall*100:.2f}%")
print(f"  AUC:       {auc*100:.2f}%")
print(f"\n  Confusion Matrix:")
print(f"  {cm}")

# TabNet
model_name = 'tabnet'
print(f"\n{model_name.upper()}:")
print("-" * 70)

# TabNet was trained with 126 features, use first 126
X_test_tabnet = X_test[:, :126]
print(f"  Note: Using first 126 features (TabNet expects {models[model_name].input_dim} features)")

y_proba = models[model_name].predict_proba(X_test_tabnet)
y_pred = np.argmax(y_proba, axis=1)

accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, average='weighted')
recall = recall_score(y_test, y_pred, average='weighted')
auc = roc_auc_score(y_test, y_proba, multi_class='ovr', average='weighted')
cm = confusion_matrix(y_test, y_pred)

results[model_name] = {
    'accuracy': accuracy,
    'precision': precision,
    'recall': recall,
    'auc': auc,
    'confusion_matrix': cm,
    'predictions': y_pred,
    'probabilities': y_proba_cpu
}

print(f"  Accuracy:  {accuracy*100:.2f}%")
print(f"  Precision: {precision*100:.2f}%")
print(f"  Recall:    {recall*100:.2f}%")
print(f"  AUC:       {auc*100:.2f}%")
print(f"\n  Confusion Matrix:")
print(f"  {cm}")

# Compare models
print("\n" + "=" * 70)
print("MODEL COMPARISON")
print("=" * 70)

comparison_data = []
for model_name in ['catboost', 'tabnet']:
    comparison_data.append({
        'Model': model_name.upper(),
        'Accuracy': f"{results[model_name]['accuracy']*100:.2f}%",
        'Precision': f"{results[model_name]['precision']*100:.2f}%",
        'Recall': f"{results[model_name]['recall']*100:.2f}%",
        'AUC': f"{results[model_name]['auc']*100:.2f}%"
    })

comparison_df = pd.DataFrame(comparison_data)
print(comparison_df.to_string(index=False))

# Find best model for each metric
print("\n" + "-" * 70)
print("BEST PER MODEL:")
print("-" * 70)
metrics = ['accuracy', 'precision', 'recall', 'auc']
for metric in metrics:
    best_model = max(results.items(), key=lambda x: x[1][metric])
    print(f"  {metric.upper():12s}: {best_model[0].upper():10s} ({best_model[1][metric]*100:.2f}%)")

# Analyze error patterns
print("\n" + "=" * 70)
print("ERROR PATTERN ANALYSIS")
print("=" * 70)

for model_name, result in results.items():
    print(f"\n{model_name.upper()}:")
    cm = result['confusion_matrix']

    # Calculate per-class recall (how many of each class were correctly identified)
    class_recall = cm.diagonal() / cm.sum(axis=1)
    print(f"  Per-class Recall (sensitivity):")
    for i, recall in enumerate(class_recall):
        print(f"    Class {i}: {recall*100:.2f}%")

    # Calculate per-class precision (how many predictions for each class were correct)
    class_precision = cm.diagonal() / cm.sum(axis=0)
    print(f"  Per-class Precision (positive predictive value):")
    for i, precision in enumerate(class_precision):
        print(f"    Class {i}: {precision*100:.2f}%")

# Check prediction correlation (for ensemble potential)
print("\n" + "=" * 70)
print("ENSEMBLE POTENTIAL ANALYSIS")
print("=" * 70)

print("\nPrediction Correlation Matrix:")
model_names = list(results.keys())
n_models = len(model_names)
correlation_matrix = np.zeros((n_models, n_models))

for i, model1 in enumerate(model_names):
    for j, model2 in enumerate(model_names):
        if i == j:
            correlation_matrix[i, j] = 1.0
        else:
            # Calculate agreement percentage
            agreement = np.mean(results[model1]['predictions'] == results[model2]['predictions'])
            correlation_matrix[i, j] = agreement

correlation_df = pd.DataFrame(
    correlation_matrix * 100,
    index=[m.upper() for m in model_names],
    columns=[m.upper() for m in model_names]
)
print(correlation_df.round(2).to_string())

print("\n" + "-" * 70)
print("Interpretation:")
print("  - Lower correlation = Models make different errors = GOOD for ensemble")
print("  - Higher correlation = Models make similar errors = LESS beneficial")
print("  - Ideal: Correlation < 90% indicates diverse error patterns")

# Simple voting ensemble
print("\n" + "=" * 70)
print("SIMPLE VOTING ENSEMBLE")
print("=" * 70)

from scipy.stats import mode

# Get all predictions
all_predictions = np.array([results[m]['predictions'] for m in model_names])
ensemble_pred, _ = mode(all_predictions, axis=0, keepdims=True)
ensemble_pred = ensemble_pred.flatten()

ensemble_accuracy = accuracy_score(y_test, ensemble_pred)
ensemble_precision = precision_score(y_test, ensemble_pred, average='weighted')
ensemble_recall = recall_score(y_test, ensemble_pred, average='weighted')

print(f"\nEnsemble Performance (Majority Vote):")
print(f"  Accuracy:  {ensemble_accuracy*100:.2f}%")
print(f"  Precision: {ensemble_precision*100:.2f}%")
print(f"  Recall:    {ensemble_recall*100:.2f}%")

cm_ensemble = confusion_matrix(y_test, ensemble_pred)
print(f"\n  Confusion Matrix:")
print(f"  {cm_ensemble}")

print("\n" + "-" * 70)
print("Improvement over best single model:")
best_accuracy = max(results[m]['accuracy'] for m in model_names)
improvement = (ensemble_accuracy - best_accuracy) * 100
print(f"  Accuracy: {improvement:+.2f}%")

if improvement > 0:
    print(f"  ✅ Ensemble beats best single model!")
else:
    print(f"  ⚠️  Ensemble does not beat best single model")
    print(f"      Consider weighted voting or stacking instead")

# Weighted voting (by AUC)
print("\n" + "=" * 70)
print("WEIGHTED VOTING ENSEMBLE (by AUC)")
print("=" * 70)

# Get weights from test AUC
weights = []
test_aucs = {m: results[m]['auc'] for m in model_names}

for m in model_names:
    weights.append(test_aucs[m])
weights = np.array(weights) / sum(weights)  # Normalize

print(f"\nWeights (based on test AUC):")
for m, w in zip(model_names, weights):
    print(f"  {m.upper()}: {w:.3f}")

# Weighted voting
all_proba = np.array([results[m]['probabilities'] for m in model_names])
weighted_proba = np.average(all_proba, axis=0, weights=weights)
weighted_pred = np.argmax(weighted_proba, axis=1)

weighted_accuracy = accuracy_score(y_test, weighted_pred)
weighted_precision = precision_score(y_test, weighted_pred, average='weighted')
weighted_recall = recall_score(y_test, weighted_pred, average='weighted')

print(f"\nWeighted Ensemble Performance:")
print(f"  Accuracy:  {weighted_accuracy*100:.2f}%")
print(f"  Precision: {weighted_precision*100:.2f}%")
print(f"  Recall:    {weighted_recall*100:.2f}%")

improvement = (weighted_accuracy - best_accuracy) * 100
print(f"\nImprovement over best single model:")
print(f"  Accuracy: {improvement:+.2f}%")

if improvement > 0:
    print(f"  ✅ Weighted ensemble beats best single model!")
else:
    print(f"  ⚠️  Weighted ensemble does not beat best single model")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print("\nKey Findings:")
print(f"1. Best single model: {max(results.items(), key=lambda x: x[1]['accuracy'])[0].upper()}")
print(f"2. Model correlation: {correlation_matrix[0,1]*100:.1f}% (CatBoost vs TabNet)")
print(f"3. Note: XGBoost model excluded due to feature mismatch")
if ensemble_accuracy > best_accuracy:
    print(f"4. ✅ Simple voting ensemble provides +{(ensemble_accuracy-best_accuracy)*100:.2f}% accuracy improvement")
else:
    print(f"4. ⚠️  Simple voting ensemble does not improve accuracy")
if weighted_accuracy > best_accuracy:
    print(f"5. ✅ Weighted ensemble provides +{(weighted_accuracy-best_accuracy)*100:.2f}% accuracy improvement")
else:
    print(f"5. ⚠️  Weighted ensemble does not improve accuracy")

print("\n" + "=" * 70)
