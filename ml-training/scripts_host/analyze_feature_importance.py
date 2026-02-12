"""
Ensemble Feature Importance Analysis

Analyzes feature importance across ALL trained models (XGBoost, CatBoost).
Only removes features that ALL models agree are unimportant.

Usage:
    python scripts/analyze_feature_importance.py --conservative
    python scripts/analyze_feature_importance.py --top-n 30 --threshold 0.005
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# Setup paths
sys.path.insert(0, '/app')

def load_model_with_importance(model_dir: Path, model_type: str):
    """Load model and extract feature importance"""
    print(f"  Loading {model_type.upper()}...")

    try:
        # Load metadata to get feature names
        metadata_path = model_dir / 'metadata.json'
        if metadata_path.exists():
            import json
            with open(metadata_path) as f:
                metadata = json.load(f)
            feature_names = metadata.get('feature_cols', None)
            if not feature_names:
                print(f"    ❌ No feature_cols in metadata")
                return None, None, None
        else:
            print(f"    ❌ No metadata.json found")
            return None, None, None

        # Get num_classes from metadata
        num_classes = metadata.get('params', {}).get('classes_count') or \
                     metadata.get('params', {}).get('num_class') or \
                     metadata.get('params', {}).get('num_classes')
        if not num_classes:
            # Try to infer from loss_function or objective
            loss_function = metadata.get('params', {}).get('loss_function', '')
            objective = metadata.get('params', {}).get('objective', '')
            if 'binary' in loss_function.lower() or 'binary' in objective.lower():
                num_classes = 2
            elif 'multi' in loss_function.lower() or 'multi' in objective.lower():
                num_classes = 5  # Default for multi
            else:
                num_classes = 'unknown'

        if model_type == 'xgboost':
            import xgboost as xgb
            # Use raw Booster API to avoid sklearn issues
            booster = xgb.Booster()
            booster.load_model(str(model_dir / 'model.json'))

            # Get importance using gain (better than default weight)
            importance_dict = booster.get_score(importance_type='gain')

            if not importance_dict:
                print(f"    ❌ No importance data found")
                return None, None, None

            # XGBoost returns f0, f1, f2... need to map to actual names
            importance = np.array([importance_dict.get(f'f{i}', 0) for i in range(len(feature_names))])

        elif model_type == 'catboost':
            from catboost import CatBoost
            # Use Pool API instead of sklearn wrapper
            model = CatBoost()
            model.load_model(str(model_dir / 'model.cbm'))

            # Get feature importance using get_feature_importance() method
            importance = model.get_feature_importance()

            # Get feature names from model
            feature_names = model.feature_names_

            if not feature_names:
                print(f"    ❌ No feature names in CatBoost model")
                return None, None, None

        # Convert to numpy array if not already
        importance = np.array(importance)

        # Check for empty or None importance
        if importance.size == 0:
            print(f"    ❌ Empty importance array")
            return None, None, None

        # Normalize importance to percentages
        total = importance.sum()
        if total > 0:
            importance = importance / total * 100
        else:
            print(f"    ❌ All importance values are 0 (total={total})")
            return None, None, None

        print(f"    ✅ Loaded {len(importance)} features ({num_classes} classes)")
        return list(feature_names), importance, num_classes

    except Exception as e:
        import traceback
        print(f"    ❌ Error: {e}")
        print(f"    Traceback: {traceback.format_exc()}")
        return None, None, None


def find_models_by_classification(models_base: Path):
    """
    Find all model folders organized by classification type.

    Looks for folders like:
    - v1.0.0-binary/
    - v1.0.0-3class/
    - v1.0.0-5class/
    """
    print("\n" + "=" * 70)
    print("SCANNING FOR MODELS BY CLASSIFICATION TYPE")
    print("=" * 70)

    classification_models = {}

    # Map version suffix to classification type
    suffix_map = {
        'binary': 'binary',
        '2class': 'binary',
        '3class': '3class',
        '5class': '5class',
    }

    for model_type in ['xgboost', 'catboost']:
        model_type_dir = models_base / model_type
        if not model_type_dir.exists():
            continue

        # List all subdirectories (versions)
        for version_dir in model_type_dir.iterdir():
            if not version_dir.is_dir():
                continue

            version_name = version_dir.name

            # Skip non-version folders
            if version_name == 'latest':
                continue

            # Extract classification type from version name
            class_type = None
            for suffix, type_name in suffix_map.items():
                if version_name.endswith(suffix):
                    class_type = type_name
                    break

            if not class_type:
                continue

            # Initialize classification entry if needed
            if class_type not in classification_models:
                classification_models[class_type] = {}

            if model_type not in classification_models[class_type]:
                classification_models[class_type][model_type] = version_dir

            print(f"  ✅ Found: {model_type.upper()} - {class_type} ({version_name})")

    if not classification_models:
        print("\n❌ No models found with version suffixes (binary/3class/5class)")
        print("   Train models with:")
        print("     python train.py --label-type binary --version binary")
        print("     python train.py --label-type 3class --version 3class")
        print("     python train.py --label-type 5class --version 5class")

    return classification_models


def main():
    parser = argparse.ArgumentParser(
        description='Analyze feature importance across ALL trained models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/analyze_feature_importance.py --conservative
  python scripts/analyze_feature_importance.py --top-n 30 --threshold 0.005

Strategies:
  --conservative  Only remove features ALL models agree are unimportant (safest)
  --default       Use mean importance across models (balanced)
        """
    )

    parser.add_argument(
        '--models-dir',
        type=str,
        default=None,
        help='Base models directory (default: /app/outputs/models)'
    )

    parser.add_argument(
        '--top-n',
        type=int,
        default=None,
        help='Show top N features (default: show all)'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=0.005,
        help='Importance threshold for removing features (default: 0.005)'
    )

    parser.add_argument(
        '--strategy',
        type=str,
        choices=['conservative', 'default'],
        default='conservative',
        help='Feature selection strategy (default: conservative)'
    )

    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare feature importance across classification types (binary/3class/5class)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='/app/outputs/analysis',
        help='Output directory for results'
    )

    args = parser.parse_args()

    print("=" * 70)
    print(" " * 10)
    if args.compare:
        print("Multi-Class Feature Importance Comparison")
    else:
        print("Ensemble Feature Importance Analysis")
    print(" " * 10)
    print("=" * 70)

    # ============================================================
    # BRANCH: COMPARISON MODE vs NORMAL MODE
    # ============================================================

    if args.compare:
        # COMPARISON MODE: Compare across binary/3class/5class
        run_comparison_mode(args)
    else:
        # NORMAL MODE: Analyze 'latest' models only
        run_normal_mode(args)


def run_normal_mode(args):
    """Original analysis mode - scans 'latest' folder only"""
    # ============================================================
    # FIND MODELS
    # ============================================================

    models_base = Path(args.models_dir) if args.models_dir else Path('/app/outputs/models')

    print("\n" + "=" * 70)
    print("SCANNING FOR TRAINED MODELS")
    print("=" * 70)

    available_models = []
    for model_name in ['xgboost', 'catboost']:
        model_path = models_base / model_name / 'latest'
        if model_path.exists():
            available_models.append((model_name, model_path))
            print(f"  ✅ Found: {model_name.upper()}")
        else:
            print(f"  ❌ Not found: {model_name.upper()}")

    if not available_models:
        print("\n❌ No trained models found")
        return

    # ============================================================
    # LOAD ALL MODELS
    # ============================================================

    print("\n" + "=" * 70)
    print("LOADING MODELS")
    print("=" * 70)

    importances_dict = {}
    all_feature_names = None

    for model_name, model_dir in available_models:
        feature_names, importance, _ = load_model_with_importance(model_dir, model_name)

        if feature_names is not None and importance is not None:
            importances_dict[model_name] = {feature_names[i]: importance[i] for i in range(len(feature_names))}

            if all_feature_names is None:
                all_feature_names = feature_names

    if not importances_dict:
        print("\n❌ No models loaded successfully")
        return

    print(f"\n✅ Loaded {len(importances_dict)} model(s)")

    # ============================================================
    # BUILD DATAFRAME
    # ============================================================

    print("\n" + "=" * 70)
    print("COMPUTING AGGREGATE IMPORTANCE")
    print("=" * 70)

    # Build DataFrame
    df_list = []
    for model_name, imp_dict in importances_dict.items():
        df_temp = pd.DataFrame(list(imp_dict.items()), columns=['feature', model_name])
        df_list.append(df_temp)

    # Merge all model importances
    from functools import reduce
    df = reduce(lambda left, right: pd.merge(left, right, on='feature', how='outer'), df_list)
    df = df.fillna(0)  # Missing features = 0 importance

    # Compute aggregate statistics
    model_cols = list(importances_dict.keys())
    df['mean_importance'] = df[model_cols].mean(axis=1)
    df['max_importance'] = df[model_cols].max(axis=1)
    df['min_importance'] = df[model_cols].min(axis=1)
    df['std_importance'] = df[model_cols].std(axis=1)

    # Vote: how many models consider this feature important (>threshold)
    threshold_pct = args.threshold * 100
    df['vote_count'] = (df[model_cols] > threshold_pct).sum(axis=1)

    # Sort by mean importance
    df = df.sort_values('mean_importance', ascending=False)
    df['rank'] = range(1, len(df) + 1)

    print(f"\nTotal features: {len(df)}")
    print(f"Models analyzed: {', '.join(model_cols)}")

    # ============================================================
    # DISPLAY TOP FEATURES
    # ============================================================

    print("\n" + "=" * 70)
    print("TOP FEATURES")
    print("=" * 70)

    top_n = args.top_n if args.top_n else 50
    print(f"\nTop {top_n} Features by Mean Importance:")
    print("─" * 90)

    for idx, row in df.head(top_n).iterrows():
        model_scores = ' | '.join([f"{row[m]:>5.2f}%" for m in model_cols])
        print(f"  {row['rank']:>3}. {row['feature']:<30} Mean: {row['mean_importance']:>5.2f}%  [{model_scores}]")

    # ============================================================
    # ANALYSIS
    # ============================================================

    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    # Determine which column to use for filtering
    if args.strategy == 'conservative':
        filter_col = 'min_importance'
        strategy_desc = "MIN importance across models (most conservative)"
        print(f"\nStrategy: {strategy_desc}")
        print("  → Only removes features if ALL models agree they're unimportant")
    else:
        filter_col = 'mean_importance'
        strategy_desc = "MEAN importance across models (balanced)"
        print(f"\nStrategy: {strategy_desc}")

    # Count features by importance
    high_importance = (df[filter_col] >= 1.0).sum()
    medium_importance = ((df[filter_col] >= 0.1) & (df[filter_col] < 1.0)).sum()
    low_importance = ((df[filter_col] >= threshold_pct) & (df[filter_col] < 0.1)).sum()
    very_low_importance = (df[filter_col] < threshold_pct).sum()

    print(f"\nFeature Distribution (using {filter_col}):")
    print(f"  High importance (≥1%):       {high_importance:3} features")
    print(f"  Medium importance (0.1-1%):  {medium_importance:3} features")
    print(f"  Low importance ({threshold_pct}%-0.1%):  {low_importance:3} features")
    print(f"  Very low (<{threshold_pct}%):        {very_low_importance:3} features")

    # Pareto check
    df['cumulative_mean'] = df['mean_importance'].cumsum()
    pareto_80 = df[df['cumulative_mean'] <= 80].shape[0]
    pareto_90 = df[df['cumulative_mean'] <= 90].shape[0]

    print(f"\nPareto Analysis (mean importance):")
    print(f"  Top {pareto_80:3} features → 80% of total importance")
    print(f"  Top {pareto_90:3} features → 90% of total importance")

    # Consensus check
    unanimous = (df['vote_count'] == len(model_cols)).sum()
    divided = (df['vote_count'] == 1).sum()

    print(f"\nModel Agreement:")
    print(f"  Features ALL models agree are important (>0.5%): {unanimous:3}")
    print(f"  Features only ONE model finds important:         {divided:3}")

    # ============================================================
    # RECOMMENDATIONS
    # ============================================================

    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)

    if very_low_importance > 0:
        print(f"\n📊 Features with very low importance (<{threshold_pct}%):")
        low_features = df[df[filter_col] < threshold_pct][['feature', filter_col]].sort_values(by=filter_col)

        for _, row in low_features.head(20).iterrows():
            print(f"  ❌ {row['feature']:<30} {row[filter_col]:>5.2f}%")
        if len(low_features) > 20:
            print(f"  ... and {len(low_features) - 20} more")

        print(f"\n  Total: {very_low_importance} features could be removed")

    # ============================================================
    # SAVE RESULTS
    # ============================================================

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save full CSV
    csv_file = output_dir / f'feature_importance_ensemble_{timestamp}.csv'
    df.to_csv(csv_file, index=False)
    print(f"\n✅ Full results saved to: {csv_file}")

    # Save feature lists
    if very_low_importance > 0:
        keep_file = output_dir / f'features_to_keep_{args.strategy}_{timestamp}.txt'
        features_to_keep = df[df[filter_col] >= threshold_pct]['feature'].tolist()

        with open(keep_file, 'w') as f:
            f.write(f'# Features to keep for training\n')
            f.write(f'# Strategy: {strategy_desc}\n')
            f.write(f'# Threshold: {threshold_pct}% importance\n')
            f.write(f'# Generated: {timestamp}\n\n')
            for feature in features_to_keep:
                f.write(f'{feature}\n')

        print(f"✅ Feature list saved to: {keep_file}")

        remove_file = output_dir / f'features_to_remove_{args.strategy}_{timestamp}.txt'
        features_to_remove = df[df[filter_col] < threshold_pct]['feature'].tolist()

        with open(remove_file, 'w') as f:
            f.write(f'# Features to REMOVE (low importance)\n')
            f.write(f'# Strategy: {strategy_desc}\n')
            f.write(f'# Threshold: {threshold_pct}% importance\n')
            f.write(f'# Generated: {timestamp}\n\n')
            for feature in features_to_remove:
                f.write(f'{feature}\n')

        print(f"✅ Remove list saved to: {remove_file}")

    print("\n" + "=" * 70)
    print(f"\n💡 KEY INSIGHT:")
    print(f"   Your AUC plateaued at ~64.8% during 200 trials.")
    print(f"   This suggests the current features have hit their ceiling.")
    print(f"   Consider:")
    print(f"   1. Removing low-importance features (may help or may not)")
    print(f"   2. Adding new features (momentum, volatility, market regime)")
    print(f"   3. Label refinement (current labels may be too noisy)")
    print(f"   4. Trying different model architectures (TCN, Transformer)")

    print("\n" + "=" * 70)


def run_comparison_mode(args):
    """Comparison mode - compare across binary/3class/5class models"""
    models_base = Path(args.models_dir) if args.models_dir else Path('/app/outputs/models')

    # Find models by classification type
    classification_models = find_models_by_classification(models_base)

    if not classification_models:
        return

    # Load models for each classification type
    print("\n" + "=" * 70)
    print("LOADING MODELS")
    print("=" * 70)

    results = {}

    for class_type, model_types in classification_models.items():
        print(f"\n{class_type.upper()}:")

        results[class_type] = {}

        for model_type, model_dir in model_types.items():
            feature_names, importance, num_classes = load_model_with_importance(model_dir, model_type)

            if feature_names is not None:
                # Create dataframe for this model
                df = pd.DataFrame({
                    'feature': feature_names,
                    'importance': importance
                }).sort_values('importance', ascending=False)

                results[class_type][model_type] = df

    # Compare across classification types
    print("\n" + "=" * 70)
    print("CROSS-CLASSIFICATION COMPARISON")
    print("=" * 70)

    # For each classification type, show top features
    for class_type in ['binary', '3class', '5class']:
        if class_type not in results:
            print(f"\n⚠️  No {class_type} models found")
            continue

        print(f"\n{'─' * 70}")
        print(f"  {class_type.upper()} CLASSIFICATION")
        print(f"{'─' * 70}")

        class_models = results[class_type]

        # Merge all models for this classification
        if len(class_models) == 1:
            # Single model
            model_name = list(class_models.keys())[0]
            df = class_models[model_name].copy()
            df.columns = ['feature', f'{model_name}_importance']
        else:
            # Multiple models - merge them
            dfs = []
            for model_name, model_df in class_models.items():
                df_temp = model_df.copy()
                df_temp = df_temp.rename(columns={'importance': f'{model_name}_importance'})
                dfs.append(df_temp)

            from functools import reduce
            df = reduce(lambda left, right: pd.merge(left, right, on='feature', how='outer'), dfs)
            df = df.fillna(0)

            # Calculate mean importance
            importance_cols = [f'{m}_importance' for m in class_models.keys()]
            df['mean_importance'] = df[importance_cols].mean(axis=1)
            df = df.sort_values('mean_importance', ascending=False)

        # Display top N features
        top_n = args.top_n if args.top_n else 50
        print(f"\nTop {min(top_n, len(df))} Features:")

        for idx, row in df.head(top_n).iterrows():
            feature = row['feature']

            # Build importance string
            if 'mean_importance' in row:
                imp_str = f"{row['mean_importance']:>5.2f}% (mean)"
                details = ' | '.join([f"{m}: {row[f'{m}_importance']:>5.2f}%" for m in class_models.keys()])
                print(f"  {feature:<35} {imp_str:<15} [{details}]")
            else:
                imp_col = [c for c in df.columns if c != 'feature'][0]
                print(f"  {feature:<35} {row[imp_col]:>5.2f}%")

    # Find common important features across all classifications
    if len(results) >= 2:
        print("\n" + "=" * 70)
        print("COMMON IMPORTANT FEATURES (ACROSS ALL CLASSIFICATIONS)")
        print("=" * 70)

        # Get top features from each classification
        top_features_per_class = {}
        for class_type, class_models in results.items():
            # Merge models within classification
            dfs = []
            for model_name, model_df in class_models.items():
                df_temp = model_df.copy()
                df_temp = df_temp.rename(columns={'importance': f'{model_name}_importance'})
                dfs.append(df_temp)

            from functools import reduce
            df = reduce(lambda left, right: pd.merge(left, right, on='feature', how='outer'), dfs)
            df = df.fillna(0)

            importance_cols = [f'{m}_importance' for m in class_models.keys()]
            df['mean_importance'] = df[importance_cols].mean(axis=1)
            df = df.sort_values('mean_importance', ascending=False)

            top_features_per_class[class_type] = set(df.head(30)['feature'].tolist())

        # Find intersection
        if len(top_features_per_class) >= 2:
            common_features = set.intersection(*top_features_per_class.values())

            print(f"\n✅ Features in Top 30 for ALL classifications:")
            if common_features:
                for i, feature in enumerate(sorted(common_features), 1):
                    print(f"  {i:2}. {feature}")

                print(f"\n   Total: {len(common_features)} common top features")
            else:
                print("  None - no overlap in top 30 features")

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for class_type, class_models in results.items():
        # Merge models within classification
        dfs = []
        for model_name, model_df in class_models.items():
            df_temp = model_df.copy()
            df_temp = df_temp.rename(columns={'importance': f'{model_name}_importance'})
            dfs.append(df_temp)

        from functools import reduce
        df = reduce(lambda left, right: pd.merge(left, right, on='feature', how='outer'), dfs)
        df = df.fillna(0)

        importance_cols = [f'{m}_importance' for m in class_models.keys()]
        df['mean_importance'] = df[importance_cols].mean(axis=1)
        df = df.sort_values('mean_importance', ascending=False)

        csv_file = output_dir / f'feature_importance_{class_type}_{timestamp}.csv'
        df.to_csv(csv_file, index=False)
        print(f"✅ Saved: {csv_file}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
