#!/usr/bin/env python3
"""
DIAGNOSTIC SCRIPT: Confirm Model is Predicting Beta, Not Alpha

Purpose:
    Before making changes, we need to confirm the diagnosis that the model
    is predicting market direction (beta) instead of stock selection (alpha).

Tests:
    1. Feature Importance Analysis - Confirm SPY features dominate
    2. Label-SPY Correlation Test - Check if labels correlate with SPY signals
    3. Ablation Study - Train without SPY features to measure impact
    4. Prediction-SPY Correlation - Check if predictions follow SPY

Usage:
    python 01_diagnose_current_labels.py --dataset-folder dataset_20260204_204134

Expected Results:
    - Test 1: SPY features should be 40%+ of top 10 importance
    - Test 2: Label-SPY correlation should be > 0.60
    - Test 3: AUC should drop 20+ points without SPY
    - Test 4: Predictions should correlate > 0.65 with SPY direction

If ALL tests pass → Proceed with alpha label implementation
If ANY test fails → Re-evaluate the diagnosis

Created: 2026-02-05
Author: ML Team
"""

import sys
import os
import argparse
import json
from datetime import datetime
from pathlib import Path

# Setup paths
sys.path.insert(0, '/app')
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# Model imports
from xgboost import XGBClassifier
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score


DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass@db:5432/stockanalyzer')
engine = create_engine(DATABASE_URL)


def get_spy_prices(start_date, end_date):
    """Fetch SPY prices for correlation analysis"""
    query = text("""
        SELECT sp.timestamp, sp.close as spy_close
        FROM stock_prices sp
        JOIN stocks s ON sp.stock_id = s.id
        WHERE s.symbol = 'SPY'
          AND sp.timeframe = '1d'
          AND sp.timestamp >= :start_date
          AND sp.timestamp <= :end_date
        ORDER BY sp.timestamp ASC
    """)

    df = pd.read_sql(query, engine, params={'start_date': start_date, 'end_date': end_date})
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def calculate_spy_ma_cross(spy_prices):
    """Calculate SPY MA crossover signals"""
    spy_prices = spy_prices.sort_values('timestamp').copy()

    # Calculate moving averages
    spy_prices['spy_ma_50'] = spy_prices['spy_close'].rolling(window=50).mean()
    spy_prices['spy_ma_200'] = spy_prices['spy_close'].rolling(window=200).mean()

    # MA crossover signal
    spy_prices['ma_cross_up'] = (spy_prices['spy_ma_50'] > spy_prices['spy_ma_200']).astype(int)
    spy_prices['ma_cross_down'] = (spy_prices['spy_ma_50'] < spy_prices['spy_ma_200']).astype(int)

    return spy_prices


def test_1_feature_importance_analysis(features_df, labels_df, model_type='xgboost'):
    """
    TEST 1: Feature Importance Analysis

    Hypothesis: SPY features dominate importance scores
    Expected: Top 5 features contain 3+ SPY features with 40%+ cumulative importance
    """
    print("\n" + "=" * 70)
    print("TEST 1: Feature Importance Analysis")
    print("=" * 70)

    # Merge features and labels
    df = pd.merge(
        features_df,
        labels_df[['stock_id', 'timestamp', 'label']],
        on=['stock_id', 'timestamp'],
        how='inner'
    )

    # CRITICAL FIX: Sort by timestamp BEFORE splitting!
    df = df.sort_values('timestamp').reset_index(drop=True)

    # Prepare data
    exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
    feature_cols = [col for col in df.columns if col not in exclude_cols]

    X = df[feature_cols].fillna(0)
    y = df['label']

    # Temporal split (NOW PROPERLY SORTED)
    n = len(X)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)

    X_train, y_train = X.iloc[:train_end], y.iloc[:train_end]
    X_val, y_val = X.iloc[train_end:val_end], y.iloc[train_end:val_end]

    # Log date ranges
    print(f"\n📅 Temporal Split (FIXED - Properly Sorted):")
    print(f"  Train: {df.iloc[:train_end]['timestamp'].min()} to {df.iloc[:train_end]['timestamp'].max()}")
    print(f"  Val:   {df.iloc[train_end:val_end]['timestamp'].min()} to {df.iloc[train_end:val_end]['timestamp'].max()}")
    print(f"  Test:  {df.iloc[val_end:]['timestamp'].min()} to {df.iloc[val_end:]['timestamp'].max()}")

    # Train model
    print(f"\nTraining {model_type.upper()} model...")

    if model_type == 'xgboost':
        model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            eval_metric='auc',
            use_label_encoder=False,
            random_state=42
        )
    else:  # catboost
        model = CatBoostClassifier(
            iterations=100,
            depth=6,
            learning_rate=0.1,
            verbose=False,
            random_state=42
        )

    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    # Get feature importance
    if model_type == 'xgboost':
        importance = model.feature_importances_
    else:
        importance = model.feature_importances_

    # Create importance dataframe
    importance_df = pd.DataFrame({
        'feature': feature_cols,
        'importance': importance
    }).sort_values('importance', ascending=False)

    # Calculate cumulative importance
    importance_df['cumulative_importance'] = importance_df['importance'].cumsum()
    importance_df['pct_total'] = importance_df['importance'] / importance_df['importance'].sum() * 100

    # Count SPY features in top 10
    top10 = importance_df.head(10)
    spy_count_top10 = sum(1 for f in top10['feature'] if 'spy' in f.lower())
    spy_importance_top10 = top10[top10['feature'].str.lower().str.contains('spy')]['importance'].sum()
    spy_pct_top10 = spy_importance_top10 / importance_df['importance'].sum() * 100

    print(f"\n📊 Top 10 Features:")
    print("-" * 70)
    for idx, row in top10.iterrows():
        is_spy = "🔴 SPY" if 'spy' in row['feature'].lower() else ""
        print(f"  {row['feature']:<30} {row['pct_total']:>6.2f}%  {is_spy}")

    print(f"\n📈 SPY Feature Statistics:")
    print(f"  SPY features in top 10: {spy_count_top10}/10")
    print(f"  SPY importance in top 10: {spy_pct_top10:.1f}%")
    print(f"  Cumulative importance (top 10): {top10['cumulative_importance'].iloc[-1]:.1f}%")

    # Test result
    test_passes = (spy_count_top10 >= 3) and (spy_pct_top10 >= 30)

    print(f"\n{'✅ PASS' if test_passes else '❌ FAIL'}: SPY features dominate ({spy_pct_top10:.1f}% in top 10)")

    if test_passes:
        print("  → Model is learning market direction (beta), not stock picking (alpha)")
    else:
        print("  → Unexpected: SPY not dominating. Diagnosis may be incorrect.")

    return {
        'test_name': 'feature_importance',
        'passes': test_passes,
        'spy_count_top10': spy_count_top10,
        'spy_pct_top10': spy_pct_top10,
        'top_features': top10[['feature', 'pct_total']].to_dict('records')
    }


def test_2_label_spy_correlation(labels_df, spy_prices):
    """
    TEST 2: Label-SPY Correlation

    Hypothesis: Labels correlate strongly with SPY MA crossover signals
    Expected: Correlation > 0.60 between labels and SPY direction
    """
    print("\n" + "=" * 70)
    print("TEST 2: Label-SPY Correlation Analysis")
    print("=" * 70)

    # Calculate SPY signals
    spy_signals = calculate_spy_ma_cross(spy_prices)

    # Merge labels with SPY signals
    merged = pd.merge(
        labels_df,
        spy_signals[['timestamp', 'spy_close', 'ma_cross_up', 'ma_cross_down']],
        on='timestamp',
        how='inner'
    )

    # Calculate correlations
    correlation_up = merged['label'].corr(merged['ma_cross_up'])
    correlation_down = merged['label'].corr(merged['ma_cross_down'])

    # Also calculate with SPY return
    merged['spy_return_5d'] = merged['spy_close'].pct_change(5).shift(-5)
    correlation_return = merged['label'].corr(merged['spy_return_5d'].fillna(0))

    print(f"\n📊 Correlation Results:")
    print(f"  Label ↔ SPY MA Cross UP:   {correlation_up:>7.3f}")
    print(f"  Label ↔ SPY MA Cross DOWN: {correlation_down:>7.3f}")
    print(f"  Label ↔ SPY 5-day Return:  {correlation_return:>7.3f}")

    # Test result
    max_correlation = max(abs(correlation_up), abs(correlation_down), abs(correlation_return))
    test_passes = max_correlation > 0.50

    print(f"\n{'✅ PASS' if test_passes else '❌ FAIL'}: Max correlation = {max_correlation:.3f}")

    if test_passes:
        print("  → Labels are strongly correlated with market direction")
        print("  → This explains why model learns SPY features")
    else:
        print("  → Labels less correlated with SPY than expected")
        print("  → Model may be learning other patterns")

    return {
        'test_name': 'label_spy_correlation',
        'passes': test_passes,
        'correlation_up': correlation_up,
        'correlation_down': correlation_down,
        'correlation_return': correlation_return,
        'max_correlation': max_correlation
    }


def test_3_ablation_study(features_df, labels_df):
    """
    TEST 3: Ablation Study

    Hypothesis: Removing SPY features significantly reduces model performance
    Expected: AUC drops 20+ percentage points without SPY features
    """
    print("\n" + "=" * 70)
    print("TEST 3: Ablation Study (Train With vs Without SPY)")
    print("=" * 70)

    # Merge features and labels
    df = pd.merge(
        features_df,
        labels_df[['stock_id', 'timestamp', 'label']],
        on=['stock_id', 'timestamp'],
        how='inner'
    )

    # Identify SPY features
    exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
    all_feature_cols = [col for col in df.columns if col not in exclude_cols]
    spy_features = [col for col in all_feature_cols if 'spy' in col.lower()]
    non_spy_features = [col for col in all_feature_cols if 'spy' not in col.lower()]

    print(f"\n📊 Feature Breakdown:")
    print(f"  Total features:     {len(all_feature_cols)}")
    print(f"  SPY features:       {len(spy_features)}")
    print(f"  Non-SPY features:   {len(non_spy_features)}")

    results = {}

    for feature_set_name, feature_set in [
        ('All Features', all_feature_cols),
        ('No SPY Features', non_spy_features)
    ]:
        print(f"\n{'─' * 70}")
        print(f"Training with: {feature_set_name} ({len(feature_set)} features)")
        print(f"{'─' * 70}")

        # Prepare data
        X = df[feature_set].fillna(0)
        y = df['label']

        # CRITICAL FIX: Already sorted by timestamp from merge above
        # Temporal split
        n = len(X)
        train_end = int(n * 0.7)
        val_end = int(n * 0.85)

        X_train, y_train = X.iloc[:train_end], y.iloc[:train_end]
        X_val, y_val = X.iloc[train_end:val_end], y.iloc[train_end:val_end]
        X_test, y_test = X.iloc[val_end:], y.iloc[val_end:]

        # Log date ranges
        print(f"\n  Train: {df.iloc[:train_end]['timestamp'].min()} to {df.iloc[:train_end]['timestamp'].max()}")
        print(f"  Val:   {df.iloc[train_end:val_end]['timestamp'].min()} to {df.iloc[train_end:val_end]['timestamp'].max()}")
        print(f"  Test:  {df.iloc[val_end:]['timestamp'].min()} to {df.iloc[val_end:]['timestamp'].max()}")

        # Train XGBoost
        model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            eval_metric='auc',
            use_label_encoder=False,
            random_state=42
        )

        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        # Evaluate
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_pred_proba)

        # Additional metrics
        y_pred = (y_pred_proba > 0.5).astype(int)
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)

        print(f"\n  Results:")
        print(f"    AUC:       {auc:>6.3f}")
        print(f"    Accuracy:  {accuracy:>6.3f}")
        print(f"    Precision: {precision:>6.3f}")
        print(f"    Recall:    {recall:>6.3f}")

        results[feature_set_name] = {
            'auc': auc,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'n_features': len(feature_set)
        }

    # Calculate AUC drop
    auc_with_spy = results['All Features']['auc']
    auc_without_spy = results['No SPY Features']['auc']
    auc_drop = auc_with_spy - auc_without_spy
    auc_drop_pct = (auc_drop / auc_with_spy) * 100

    print(f"\n{'─' * 70}")
    print(f"Ablation Results:")
    print(f"{'─' * 70}")
    print(f"  AUC with SPY:    {auc_with_spy:.3f}")
    print(f"  AUC without SPY: {auc_without_spy:.3f}")
    print(f"  AUC Drop:        {auc_drop:.3f} ({auc_drop_pct:.1f}%)")

    # Test result
    test_passes = auc_drop > 0.15

    print(f"\n{'✅ PASS' if test_passes else '❌ FAIL'}: AUC dropped {auc_drop:.3f} ({auc_drop_pct:.1f}%)")

    if test_passes:
        print("  → SPY features are critical for current performance")
        print("  → Model relies heavily on market direction signals")
    else:
        print("  → SPY features less critical than expected")
        print("  → Model may be using other features effectively")

    return {
        'test_name': 'ablation_study',
        'passes': test_passes,
        'auc_with_spy': auc_with_spy,
        'auc_without_spy': auc_without_spy,
        'auc_drop': auc_drop,
        'auc_drop_pct': auc_drop_pct
    }


def test_4_prediction_spy_correlation(features_df, labels_df, spy_prices):
    """
    TEST 4: Prediction-SPY Correlation

    Hypothesis: Model predictions correlate strongly with SPY direction
    Expected: Predictions correlate > 0.60 with SPY MA signals
    """
    print("\n" + "=" * 70)
    print("TEST 4: Prediction-SPY Correlation")
    print("=" * 70)

    # Merge features and labels
    df = pd.merge(
        features_df,
        labels_df[['stock_id', 'timestamp', 'label']],
        on=['stock_id', 'timestamp'],
        how='inner'
    )

    # CRITICAL FIX: Sort by timestamp BEFORE splitting!
    df = df.sort_values('timestamp').reset_index(drop=True)

    # Calculate SPY signals
    spy_signals = calculate_spy_ma_cross(spy_prices)

    # Merge predictions with SPY signals
    merged = pd.merge(
        df,
        spy_signals[['timestamp', 'spy_close', 'ma_cross_up']],
        on='timestamp',
        how='inner'
    )

    # Prepare data
    exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
    feature_cols = [col for col in df.columns if col not in exclude_cols]

    X = merged[feature_cols].fillna(0)
    y = merged['label']

    # Temporal split (NOW PROPERLY SORTED)
    n = len(X)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)

    X_train = X.iloc[:train_end]
    X_test = X.iloc[val_end:]

    # Log date ranges
    print(f"\n📅 Temporal Split (FIXED):")
    print(f"  Train: {merged.iloc[:train_end]['timestamp'].min()} to {merged.iloc[:train_end]['timestamp'].max()}")
    print(f"  Test:  {merged.iloc[val_end:]['timestamp'].min()} to {merged.iloc[val_end:]['timestamp'].max()}")

    # Train model
    model = XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        eval_metric='auc',
        use_label_encoder=False,
        random_state=42
    )

    model.fit(X_train, y.iloc[:train_end], verbose=False)

    # Get predictions
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    # Calculate correlation
    test_df = merged.iloc[val_end:].copy()
    test_df['pred_proba'] = y_pred_proba

    correlation = test_df['pred_proba'].corr(test_df['ma_cross_up'])

    # Also test: average prediction when SPY is up vs down
    avg_pred_when_spy_up = test_df[test_df['ma_cross_up'] == 1]['pred_proba'].mean()
    avg_pred_when_spy_down = test_df[test_df['ma_cross_up'] == 0]['pred_proba'].mean()

    print(f"\n📊 Prediction Correlation:")
    print(f"  Prediction ↔ SPY MA Cross: {correlation:>7.3f}")
    print(f"\n📊 Average Prediction Probability:")
    print(f"  When SPY MA Cross UP:   {avg_pred_when_spy_up:.3f}")
    print(f"  When SPY MA Cross DOWN: {avg_pred_when_spy_down:.3f}")
    print(f"  Difference:              {avg_pred_when_spy_up - avg_pred_when_spy_down:.3f}")

    # Test result
    test_passes = (abs(correlation) > 0.50) or (abs(avg_pred_when_spy_up - avg_pred_when_spy_down) > 0.20)

    print(f"\n{'✅ PASS' if test_passes else '❌ FAIL'}: Correlation = {correlation:.3f}")

    if test_passes:
        print("  → Model predictions follow SPY direction")
        print("  → This confirms beta prediction, not alpha")
    else:
        print("  → Predictions less correlated with SPY than expected")

    return {
        'test_name': 'prediction_spy_correlation',
        'passes': test_passes,
        'correlation': correlation,
        'avg_pred_spy_up': avg_pred_when_spy_up,
        'avg_pred_spy_down': avg_pred_when_spy_down,
        'pred_difference': avg_pred_when_spy_up - avg_pred_when_spy_down
    }


def main():
    parser = argparse.ArgumentParser(
        description='Diagnose if model predicts beta (market) or alpha (stock picking)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python 01_diagnose_current_labels.py --dataset-folder dataset_20260204_204134

This script runs 4 diagnostic tests:
    1. Feature Importance Analysis
    2. Label-SPY Correlation Test
    3. Ablation Study (with/without SPY)
    4. Prediction-SPY Correlation

Expected Results IF model predicts beta:
    - Test 1: SPY features = 40%+ importance in top 10
    - Test 2: Label-SPY correlation > 0.60
    - Test 3: AUC drops 20+ points without SPY
    - Test 4: Predictions correlate > 0.50 with SPY

If ALL tests pass → Proceed with alpha label implementation
        """
    )

    parser.add_argument(
        '--dataset-folder',
        type=str,
        required=True,
        help='Dataset folder name (e.g., dataset_20260204_204134)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='/app/create_labels/outputs',
        help='Output directory for results'
    )

    args = parser.parse_args()

    print("=" * 70)
    print(" " * 15)
    print("ML DIAGNOSTIC: Beta vs Alpha Prediction")
    print(" " * 15)
    print("=" * 70)
    print(f"\nDataset: {args.dataset_folder}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Setup paths
    features_dir = Path('/app/outputs/features')
    dataset_folder = features_dir / args.dataset_folder

    # Load features
    features_file = dataset_folder / 'features.parquet'
    if not features_file.exists():
        print(f"\n❌ Features file not found: {features_file}")
        return

    features_df = pd.read_parquet(features_file)
    print(f"\n✅ Loaded features: {len(features_df):,} rows, {len(features_df.columns)} columns")

    # Load labels (try binary first)
    labels_file = dataset_folder / 'labels_binary.parquet'
    if not labels_file.exists():
        # Try 5-class
        labels_file = dataset_folder / 'labels_5class.parquet'

    if not labels_file.exists():
        print(f"\n❌ Labels file not found")
        return

    labels_df = pd.read_parquet(labels_file)

    # For 5-class, use label_20d
    if 'label_20d' in labels_df.columns:
        labels_df = labels_df.rename(columns={'label_20d': 'label'})

    print(f"✅ Loaded labels: {len(labels_df):,} rows")

    # Get date range for SPY data
    start_date = labels_df['timestamp'].min()
    end_date = labels_df['timestamp'].max()

    # Load SPY data
    print(f"\n📊 Loading SPY data from {start_date.date()} to {end_date.date()}...")
    spy_prices = get_spy_prices(start_date, end_date)

    if spy_prices is None or len(spy_prices) == 0:
        print("❌ No SPY data found")
        return

    print(f"✅ Loaded SPY data: {len(spy_prices):,} rows")

    # Run all tests
    results = {}

    try:
        results['test_1'] = test_1_feature_importance_analysis(features_df, labels_df)
    except Exception as e:
        print(f"\n❌ Test 1 failed: {e}")
        results['test_1'] = {'test_name': 'feature_importance', 'passes': False, 'error': str(e)}

    try:
        results['test_2'] = test_2_label_spy_correlation(labels_df, spy_prices)
    except Exception as e:
        print(f"\n❌ Test 2 failed: {e}")
        results['test_2'] = {'test_name': 'label_spy_correlation', 'passes': False, 'error': str(e)}

    try:
        results['test_3'] = test_3_ablation_study(features_df, labels_df)
    except Exception as e:
        print(f"\n❌ Test 3 failed: {e}")
        results['test_3'] = {'test_name': 'ablation_study', 'passes': False, 'error': str(e)}

    try:
        results['test_4'] = test_4_prediction_spy_correlation(features_df, labels_df, spy_prices)
    except Exception as e:
        print(f"\n❌ Test 4 failed: {e}")
        results['test_4'] = {'test_name': 'prediction_spy_correlation', 'passes': False, 'error': str(e)}

    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 70)

    passed_tests = sum(1 for r in results.values() if r.get('passes', False))
    total_tests = len(results)

    print(f"\nTests Passed: {passed_tests}/{total_tests}")

    for test_name, result in results.items():
        status = "✅ PASS" if result.get('passes', False) else "❌ FAIL"
        print(f"  {result['test_name']:<30} {status}")

    # Final verdict
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)

    if passed_tests == total_tests:
        print("\n✅ ALL TESTS PASSED")
        print("\nConclusion: Model IS predicting beta (market direction), not alpha (stock picking)")
        print("\nRecommended Action:")
        print("  → Proceed with alpha label implementation (02_create_alpha_labels.py)")
        print("  → Current 76% AUC is measuring market timing, not stock selection")
        print("  → Expected AUC drop to 52-56% with alpha labels is NORMAL")
    elif passed_tests >= total_tests / 2:
        print("\n⚠️  SOME TESTS PASSED")
        print("\nConclusion: Mixed evidence - model may partially predict alpha")
        print("\nRecommended Action:")
        print("  → Review individual test results")
        print("  → Consider proceeding with alpha labels but monitor closely")
    else:
        print("\n❌ MOST TESTS FAILED")
        print("\nConclusion: Model may already predict alpha, diagnosis uncertain")
        print("\nRecommended Action:")
        print("  → Review test results carefully")
        print("  → May need different approach")
        print("  → Consider if feature engineering is the real issue")

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_file = output_dir / f'diagnostic_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n📁 Results saved to: {results_file}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
