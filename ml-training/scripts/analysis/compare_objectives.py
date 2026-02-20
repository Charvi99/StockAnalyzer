"""
Compare CatBoost models trained with different objectives

Backtests all models on the same period and compares performance.
"""
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from catboost import CatBoostClassifier
import json
from pathlib import Path

def load_model(model_path: Path):
    """Load CatBoost model"""
    model = CatBoostClassifier()
    model.load_model(str(model_path / 'model.cbm'))

    # Load metadata
    with open(model_path / 'metadata.json', 'r') as f:
        metadata = json.load(f)

    return model, metadata

def backtest_model(model, features, prices, model_name):
    """
    Simple backtesting for 3-class model

    Args:
        model: Trained CatBoost model
        features: Feature DataFrame
        prices: DataFrame with OHLCV
        model_name: Name for logging

    Returns:
        Dict with backtest results
    """
    print(f"\n{'='*60}")
    print(f"BACKTESTING: {model_name}")
    print(f"{'='*60}")

    # Get predictions
    pred_probs = model.predict_proba(features)

    # Generate signals
    signals = []
    for i in range(len(pred_probs)):
        sell_prob, hold_prob, buy_prob = pred_probs[i]

        # Simple strategy: highest probability wins
        if buy_prob > sell_prob and buy_prob > hold_prob:
            signals.append(1)  # BUY
        elif sell_prob > buy_prob and sell_prob > hold_prob:
            signals.append(-1)  # SELL
        else:
            signals.append(0)  # HOLD

    signals = np.array(signals)

    # Calculate returns
    returns = []
    position = 0
    entry_price = None
    transaction_cost = 0.001  # 0.1%

    for i in range(1, len(signals)):
        if signals[i] != position and position != 0:
            # Close position
            if position == 1:  # Close long
                exit_price = prices.iloc[i]['close']
                ret = (exit_price - entry_price) / entry_price - transaction_cost
                returns.append(ret)
            position = 0
            entry_price = None

        if signals[i] != 0 and position == 0:
            # Open position
            entry_price = prices.iloc[i]['open']
            position = signals[i]

    returns = pd.Series(returns)

    # Calculate metrics
    if len(returns) == 0:
        print(f"❌ No trades generated!")
        return None

    total_return = returns.sum()
    mean_return = returns.mean()
    std_return = returns.std()

    # Sharpe ratio (annualized)
    sharpe = mean_return / std_return * np.sqrt(252) if std_return > 0 else 0

    # Win rate
    win_rate = (returns > 0).mean()

    # Sortino (downside risk only)
    downside_returns = returns[returns < 0]
    sortino = mean_return / downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0

    print(f"Trades: {len(returns)}")
    print(f"Total Return: {total_return*100:.2f}%")
    print(f"Mean Return: {mean_return*100:.2f}%")
    print(f"Std Return: {std_return*100:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.3f}")
    print(f"Sortino Ratio: {sortino:.3f}")
    print(f"Win Rate: {win_rate*100:.1f}%")

    return {
        'model': model_name,
        'n_trades': len(returns),
        'total_return': total_return,
        'mean_return': mean_return,
        'std_return': std_return,
        'sharpe': sharpe,
        'sortino': sortino,
        'win_rate': win_rate
    }

def main():
    print("="*60)
    print("CatBoost Objective Comparison - Backtesting")
    print("="*60)

    # Load data
    features = pd.read_parquet('/app/outputs/features/dataset_for_autogluon/features.parquet')
    labels = pd.read_parquet('/app/outputs/features/dataset_for_autogluon/labels_3class.parquet')

    # Extract OHLCV for a test period (use last 20% of data for backtesting)
    test_start = int(len(features) * 0.8)
    features_test = features.iloc[test_start:].reset_index(drop=True)
    labels_test = labels.iloc[test_start:].reset_index(drop=True)

    # Extract price columns
    price_cols = ['open', 'high', 'low', 'close', 'volume']
    prices_test = features_test[price_cols].copy()

    print(f"\nTest period: {len(features_test)} samples")
    print(f"Date range: {features_test.iloc[0].get('timestamp', 'N/A')} to {features_test.iloc[-1].get('timestamp', 'N/A')}")

    # Define model paths
    models = {
        'AUC': Path('/app/outputs/models/catboost/auc'),
        'Sharpe': Path('/app/outputs/models/catboost/sharpe'),
        'Hybrid': Path('/app/outputs/models/catboost/hybrid'),
    }

    results = []

    # Backtest each model
    for name, path in models.items():
        if not path.exists():
            print(f"\n⚠️  {name} model not found at {path}")
            continue

        try:
            model, metadata = load_model(path)
            result = backtest_model(model, features_test, prices_test, name)

            if result:
                results.append(result)
        except Exception as e:
            print(f"❌ Error backtesting {name}: {e}")
            continue

    # Compare results
    if results:
        print(f"\n{'='*60}")
        print("COMPARISON RESULTS")
        print(f"{'='*60}\n")

        df_results = pd.DataFrame(results)
        print(df_results.to_string(index=False))

        # Find best model for each metric
        print(f"\n🏆 BEST MODELS:")
        for metric in ['total_return', 'sharpe', 'sortino', 'win_rate']:
            best_idx = df_results[metric].idxmax()
            best_model = df_results.loc[best_idx, 'model']
            best_value = df_results.loc[best_idx, metric]

            if metric == 'total_return':
                print(f"  Total Return: {best_model} ({best_value*100:.2f}%)")
            elif metric == 'win_rate':
                print(f"  Win Rate: {best_model} ({best_value*100:.1f}%)")
            else:
                print(f"  {metric.capitalize()}: {best_model} ({best_value:.3f})")

        # Save results
        df_results.to_csv('/app/catboost_objective_comparison.csv', index=False)
        print(f"\n✅ Results saved to catboost_objective_comparison.csv")

        # Calculate improvement percentages
        auc_result = df_results[df_results['model'] == 'AUC'].iloc[0]
        print(f"\n📊 VS AUC BASELINE:")
        for _, row in df_results.iterrows():
            if row['model'] != 'AUC':
                for metric in ['sharpe', 'sortino', 'total_return']:
                    if metric != 'model':
                        baseline = auc_result[metric]
                        value = row[metric]
                        if baseline > 0:
                            improvement = ((value - baseline) / baseline) * 100
                            print(f"  {row['model']}: {metric} {improvement:+.1f}% vs AUC")

if __name__ == '__main__':
    main()
