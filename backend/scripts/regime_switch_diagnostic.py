#!/usr/bin/env python3
"""
Diagnostic: reconcile the regime-switch BEAR leg's negative Sharpe with the attribution's
positive rank IC. Is the negative P&L a BUG, or real (rank IC is relative, not absolute)?

The attribution (regime_conditional_attribution.py) found +0.08..+0.11 RANK IC for oversold
(dist_ma50) in bear-regime days. RANK IC is a RELATIVE measure: "more-oversold names bounce
MORE than less-oversold ones." It says NOTHING about the ABSOLUTE return. In a bear where the
whole market falls, every name can have negative forward return yet the oversold still rank
above the rest -> positive IC + negative absolute P&L, simultaneously.

This script MEASURES both, on the same data, to settle it:
  1. rank IC of -dist_ma50 vs fwd_{5,10,21} in the bear regime (must match the attribution ~+0.08).
  2. MEAN ABSOLUTE forward return of: all names | below-MA names | bottom-20% most-oversold.
  3. verdict based on the sign of the below-MA mean.

If mean(below-MA fwd) < 0 in the bear (even while IC > 0) => the backtest is CORRECT and the
long-only leg legitimately loses (relative != absolute). If mean(below-MA fwd) > 0 => BUG.

Also fixes the MA-warmup classification (only count days where the 200d MA is valid) so the
bear bucket matches the attribution's ~19.5%, not the backtest's warmup-inflated 27.4%.

Run: docker exec stock_analyzer_backend python /app/scripts/regime_switch_diagnostic.py
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from attribution_lib import HORIZONS, attach_forward_returns, load_universe, session  # noqa: E402


def _rank_ic(sig, ret):
    s = pd.DataFrame({"s": sig, "r": ret}).dropna()
    if len(s) < 30:
        return float("nan"), len(s)
    return float(spearmanr(s["s"], s["r"]).correlation), len(s)


def main():
    max_stocks = int(os.getenv("RCA_MAX_STOCKS", "80"))
    db = session()
    try:
        prices = load_universe(db, max_stocks, "2021-07-26", "2026-07-25")
    finally:
        db.close()

    # market index + 200d MA (only valid after warmup)
    ret_frames = {sid: d.sort_values("ts").assign(ret=d["close"].pct_change()).set_index("ts")["ret"].rename(sid)
                  for sid, d in prices.items()}
    retmat = pd.concat(ret_frames.values(), axis=1).sort_index()
    mkt_idx = (1 + retmat.mean(axis=1)).cumprod()
    mkt_ma = mkt_idx.rolling(200, min_periods=100).mean()
    valid = mkt_ma.notna()
    is_bear = valid & (mkt_idx < mkt_ma)   # warmup excluded
    bear_frac = float(is_bear.mean())

    rows = []
    for sid, df in prices.items():
        d = df.sort_values("ts").copy()
        d = attach_forward_returns(d, HORIZONS).reset_index(drop=True)
        d["sma50"] = d["close"].rolling(50, min_periods=20).mean()
        d["dist"] = d["close"] / d["sma50"] - 1.0
        d["fwd_1"] = d["close"].shift(-1) / d["close"] - 1.0  # NEXT-DAY return (what a daily-rebalanced book earns)
        d["bear"] = d["ts"].map(lambda t: bool(is_bear.get(t, False)) if pd.notna(t) else False)
        d["below_ma"] = d["dist"] < 0
        rows.append(d[["ts", "bear", "below_ma", "dist", "fwd_1", "fwd_5", "fwd_10", "fwd_21"]])
    big = pd.concat(rows, ignore_index=True)
    bear = big[big["bear"]].copy()

    print("=" * 88)
    print(f"REGIME-SWITCH BEAR DIAGNOSTIC   stocks={len(prices)}  bear-regime days = {bear_frac*100:.1f}% "
          f"(warmup excluded — should match attribution's ~19.5%)")
    print("=" * 88)
    print(f"bear rows = {len(bear)}  | below-MA rows = {int(bear['below_ma'].sum())} "
          f"({bear['below_ma'].mean()*100:.0f}%)")

    print("\n[1] RANK IC of -dist_ma50 vs forward return in BEAR (relative prediction):")
    print(f"{'horizon':>8} | {'rank IC':>8} | {'N':>7}")
    for h in HORIZONS:
        ic, n = _rank_ic(-bear["dist"], bear[f"fwd_{h}"])
        print(f"{'h='+str(h):>8} | {ic:>+8.3f} | {n:>7}")

    print("\n[2] MEAN ABSOLUTE forward return in BEAR (fwd_1 = next-day = what a daily book earns):")
    print(f"{'group':>26} | {'mean fwd_1':>10} | {'mean fwd_5':>10} | {'mean fwd_10':>11} | {'mean fwd_21':>11} | {'N':>7}")
    print("-" * 95)
    bear["os_rank"] = bear.groupby("ts")["dist"].rank(pct=True)  # low rank = more oversold
    for label, m in [("ALL names", np.ones(len(bear), bool)),
                     ("below-MA (dist<0)", bear["below_ma"]),
                     ("bottom-20% most oversold", bear["os_rank"] <= 0.20),
                     ("bottom-50% (more oversold)", bear["os_rank"] <= 0.50)]:
        sub = bear[m]
        print(f"{label:>26} | {sub['fwd_1'].mean()*100:>+9.3f}% | {sub['fwd_5'].mean()*100:>+9.3f}% | "
              f"{sub['fwd_10'].mean()*100:>+10.3f}% | {sub['fwd_21'].mean()*100:>+10.3f}% | {len(sub):>7}")

    print("\n[3] Verdict (fwd_1 is decisive — the backtest rebalances daily):")
    mean_below_f1 = bear.loc[bear["below_ma"], "fwd_1"].mean()
    mean_below_f5 = bear.loc[bear["below_ma"], "fwd_5"].mean()
    print(f"  below-MA next-day (fwd_1) = {mean_below_f1*100:+.4f}%   |   5-day (fwd_5) = {mean_below_f5*100:+.3f}%")
    if mean_below_f1 < 0 < mean_below_f5:
        print("  -> fwd_1 NEGATIVE but fwd_5 POSITIVE: the snap-back is a MULTI-DAY bounce, but on any")
        print("     given NEXT day below-MA names still drift down on average. A daily-rebalanced long")
        print("     bleeds between bounces -> the backtest's negative bearSh is REAL (not a bug), just")
        print("     the wrong tactic. Fix: hold the snap-back for the full bounce horizon (buy extreme")
        print("     oversold, hold ~5-10d, exit) instead of re-selecting daily. Then re-test.")
    elif mean_below_f1 >= 0:
        print("  -> fwd_1 POSITIVE: a daily-rebalanced long SHOULD profit. The regime_switch_backtest")
        print("     bear leg has a SIZING/SHIFT BUG (re-check vol-scale/strength/shift). Investigate.")
    else:
        print("  -> both fwd_1 and fwd_5 NEGATIVE: long-only mean-reversion genuinely loses in the bear")
        print("     (relative IC only). Needs long-short to monetize. Backtest is NOT a bug.")
    print("=" * 95)


if __name__ == "__main__":
    main()
