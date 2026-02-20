"""
Compare Feature Importance: 261 vs 113 Features
"""
import pandas as pd
from pathlib import Path


def load_importance(file_pattern):
    """Load latest feature importance file matching pattern"""
    analysis_dir = Path("/app/outputs/analysis")
    files = sorted(analysis_dir.glob(file_pattern))
    if files:
        df = pd.read_csv(files[-1])
        return df
    return None


def main():
    print("=" * 80)
    print("FEATURE IMPORTANCE COMPARISON: 261 vs 113 Features")
    print("=" * 80)

    # Load both importance files
    importance_261 = load_importance("feature_importance_*124927*.csv")  # 261 features
    importance_113 = load_importance("feature_importance_*131006*.csv")  # 113 features

    if importance_261 is None or importance_113 is None:
        print("❌ Could not load feature importance files")
        return

    print(f"\n📊 Dataset Comparison:")
    print(f"   Original: {len(importance_261)} features")
    print(f"   Cleaned:  {len(importance_113)} features")
    print(f"   Removed:  {len(importance_261) - len(importance_113)} features")

    # Get top 20 from each
    top20_261 = importance_261.head(20)
    top20_113 = importance_113.head(20)

    print(f"\n" + "=" * 80)
    print("TOP 20 FEATURES COMPARISON")
    print("=" * 80)

    print(f"\n{'Rank':<6} {'Feature (261)':<30} {'Importance':<12} {'Feature (113)':<30} {'Importance':<12}")
    print("-" * 80)

    for i in range(20):
        feat_261 = top20_261.iloc[i]['feature']
        imp_261 = top20_261.iloc[i]['mean_importance']

        if i < len(top20_113):
            feat_113 = top20_113.iloc[i]['feature']
            imp_113 = top20_113.iloc[i]['mean_importance']
            # Check if feature changed position
            position_113 = top20_113[top20_113['feature'] == feat_261].index
            if len(position_113) > 0:
                pos_113 = position_113[0] + 1
                change = pos_113 - (i + 1)
                if change != 0:
                    change_str = f"({change:+d})"
                else:
                    change_str = ""
            else:
                change_str = "(removed)"
        else:
            feat_113 = "-"
            imp_113 = "-"
            change_str = ""

        print(f"{i+1:<6} {feat_261:<30} {imp_261:>10.2f}%      {feat_113:<30} {imp_113 if isinstance(imp_113, str) else f'{imp_113:>10.2f}%':<12}")

    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)

    # Features that dropped in importance
    print("\n📉 Features that dropped in ranking:")
    for i, row in top20_261.head(10).iterrows():
        feat = row['feature']
        imp_261 = row['mean_importance']
        position_113 = importance_113[importance_113['feature'] == feat].index
        if len(position_113) > 0:
            pos_113 = position_113[0]
            if pos_113 >= 20:  # Dropped out of top 20
                imp_113 = importance_113.iloc[pos_113]['mean_importance']
                print(f"   {feat:<30} {i+1:2d}→{pos_113+1:2d} ({imp_261:.2f}% → {imp_113:.2f}%)")

    # Features that rose in importance
    print("\n📈 Features that rose in ranking (new to top 20):")
    for i, row in top20_113.head(20).iterrows():
        feat = row['feature']
        imp_113 = row['mean_importance']
        position_261 = importance_261[importance_261['feature'] == feat].index
        if len(position_261) > 0:
            pos_261 = position_261[0]
            if pos_261 >= 20:  # Was outside top 20
                imp_261 = importance_261.iloc[pos_261]['mean_importance']
                print(f"   {feat:<30} {pos_261+1:2d}→{i+1:2d} ({imp_261:.2f}% → {imp_113:.2f}%)")
        else:
            print(f"   {feat:<30} NEW ({imp_113:.2f}%)")

    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)

    # Concentration of importance
    cumsum_261 = importance_261['mean_importance'].head(28).sum()
    cumsum_113 = importance_113['mean_importance'].head(28).sum()

    print(f"\nTop 28 features cumulative importance:")
    print(f"   261 features: {cumsum_261:.1f}%")
    print(f"   113 features: {cumsum_113:.1f}%")

    # Insider features comparison
    insider_261 = importance_261[importance_261['feature'].str.startswith('insider_')]
    insider_113 = importance_113[importance_113['feature'].str.startswith('insider_')]

    print(f"\nInsider features:")
    print(f"   In 261 dataset: {len(insider_261)} features")
    print(f"   In 113 dataset: {len(insider_113)} features")
    print(f"   Top insider features preserved:")
    for feat in insider_113.head(5)['feature']:
        imp = insider_113[insider_113['feature'] == feat]['mean_importance'].values[0]
        print(f"      - {feat:<40} {imp:>6.2f}%")

    # Zero importance features
    zero_261 = importance_261[importance_261['mean_importance'] == 0]
    zero_113 = importance_113[importance_113['mean_importance'] == 0]

    print(f"\nZero importance features:")
    print(f"   In 261 dataset: {len(zero_261)} features ({len(zero_261)/len(importance_261)*100:.1f}%)")
    print(f"   In 113 dataset: {len(zero_113)} features ({len(zero_113)/len(importance_113)*100:.1f}%)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
