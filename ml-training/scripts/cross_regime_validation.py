#!/usr/bin/env python3
"""
Cross-regime validation of the joint ML model — the combination thesis.

ml-training's TabNet/CatBoost result (Q1-2024 +9.71%) used a single chronological
70/15/15 split over 2018-2026 -> the 2022 BEAR sits in TRAINING, never held out,
and there's no purge at the split boundary. This script holds 2022 OUT of training
and evaluates OOS on BOTH the bear and a recent bull window.

Robust edge = positive rank IC (predicted P vs forward ALPHA = excess return) in
BOTH regimes. If IC ~ 0 on the held-out bear (or on alpha), the Q1-2024 'edge'
was bull-market beta, not skill — same trap as GA #10.

Self-contained: latest feature dataset + labels, regime split, train CatBoost,
report OOS rank IC + AUC per regime.

Run (ml-training container):  python /app/scripts/cross_regime_validation.py
"""
import glob
import os
import sys

import numpy as np
import polars as pl
from catboost import CatBoostClassifier
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

FEAT_GLOB = "/app/outputs/features/dataset_*/"
LABELS = os.getenv("LABELS_FILE", "/app/labels/labels_simple_alpha_2pct.parquet")
EXCLUDE = {"stock_id", "timestamp", "label", "alpha", "forward_return", "spy_return",
           "max_upside", "max_drawdown"}


def latest_dataset():
    cands = sorted([d for d in glob.glob(FEAT_GLOB)
                    if "backtest" not in d and "lags" not in d and "filtered" not in d],
                   key=os.path.getmtime)
    return cands[-1]


def main():
    ds = latest_dataset()
    files = [f for f in sorted(glob.glob(ds + "*.parquet"))
             if "label" not in os.path.basename(f).lower()]
    feats = (pl.concat([pl.read_parquet(f) for f in files], how="vertical_relaxed")
             if len(files) > 1 else pl.read_parquet(files[0]))
    feats = feats.with_columns(pl.col("timestamp").cast(pl.Datetime).dt.truncate("1d"))
    lab = pl.read_parquet(LABELS).with_columns(
        pl.col("timestamp").cast(pl.Datetime).dt.truncate("1d"))
    df = feats.join(lab.select(["stock_id", "timestamp", "label", "alpha", "forward_return"]),
                    on=["stock_id", "timestamp"], how="inner").sort("timestamp")
    print(f"dataset={ds}")
    print(f"joined_rows={df.height}  span={df['timestamp'].min()} .. {df['timestamp'].max()}")

    feat_cols = [c for c in df.columns if c not in EXCLUDE]
    ts_np = df["timestamp"].to_numpy()  # datetime64[ns]
    bear = (ts_np >= np.datetime64("2022-01-01")) & (ts_np < np.datetime64("2023-01-01"))
    bull = ts_np >= np.datetime64("2024-01-01")
    train = ~bear & ~bull
    print(f"train={int(train.sum())}  bear_test={int(bear.sum())}  bull_test={int(bull.sum())}")

    X = df.select(feat_cols).fill_null(0).to_pandas()
    y = df["label"].to_numpy()
    if len(np.unique(y)) > 2:
        y = (y == np.max(y)).astype(int)  # top class = positive
    print(f"features={len(feat_cols)}  train pos_rate={y[train].mean():.3f}")

    model = CatBoostClassifier(iterations=500, depth=6, learning_rate=0.05,
                               eval_metric="AUC", random_seed=42, verbose=100,
                               allow_writing_files=False)
    model.fit(X[train], y[train])

    alpha = df["alpha"].cast(pl.Float64).to_numpy()
    fr = df["forward_return"].cast(pl.Float64).to_numpy()
    print("\n================ CROSS-REGIME OOS RESULTS ================")
    for name, m in [("BEAR 2022 (held-out OOS)", bear), ("BULL 2024+ (held-out OOS)", bull)]:
        if m.sum() == 0:
            continue
        p = model.predict_proba(X[m])[:, 1]
        auc = roc_auc_score(y[m], p) if len(np.unique(y[m])) > 1 else float("nan")
        print(f"\n{name}  (n={int(m.sum())})")
        print(f"  AUC vs label = {auc:.3f}")
        for tgt_name, tgt in [("alpha (excess)", alpha), ("forward_return", fr)]:
            v = tgt[m]
            ok = np.isfinite(v)
            ic = spearmanr(p[ok], v[ok])[0] if ok.sum() > 30 else float("nan")
            print(f"  rank IC (pred vs {tgt_name:18s}) = {ic:+.4f}   (N={int(ok.sum())})")
    print("\nInterpretation: robust edge needs rank IC vs ALPHA persistently > ~0.03 in")
    print("BOTH bear and bull. ~0 on the bear (or on alpha) => Q1-2024 'edge' was beta.")
    print("=========================================================")


if __name__ == "__main__":
    main()
