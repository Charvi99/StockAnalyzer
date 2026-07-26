#!/usr/bin/env python3
"""
Regime-conditional attribution — do mean-reversion signals have edge SPECIFICALLY in
bear-regime days? (The "bear-market snap-back / opportunity" hypothesis.)

Every prior attribution measured each signal's rank IC UNCONDITIONALLY across the whole
sample. That hides regime-conditional structure: mean-reversion (oversold -> bounce) may
work in bears but not bulls, and momentum works in bulls but whipsaws in bears. This probe
splits (stock, T) rows by MARKET regime (equal-weight index vs its 200-day MA) and measures
each signal's IC WITHIN each regime, with chronological train/val to catch false positives.

Hypothesis: if bear mean-reversion shows persistent val IC > 0.03-0.05 (and momentum does
NOT in the bear), the snap-backs are tradeable -> a regime-switching system (momentum in
bull, mean-reversion in bear) is worth building. If null, bear opportunities aren't
reliably capturable with public daily data (EMH on the snap-back trade).

Signals (all constructed so POSITIVE IC == "signal predicts UP"):
  rsi_rev     = -RSI(14)          (low RSI / oversold -> expect bounce)    [mean-reversion]
  dist_ma50   = -(close/sma50-1)  (far below MA -> expect bounce)          [mean-reversion]
  reversal5   = -past_5d_return   (sharp drop -> bounce)                   [short-term reversal]
  mom252      = past_252d_return  (CONTROL: expect +IC in bull, ~0/- in bear)

Reuses attribution_lib (load_universe / attach_forward_returns / rank_ic / HORIZONS) so the
IC numbers are directly comparable to the alt-data / sentiment attributions.

Run: docker exec stock_analyzer_backend python /app/scripts/regime_conditional_attribution.py
Env: RCA_MAX_STOCKS (default 80), RCA_START, RCA_END.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from attribution_lib import HORIZONS, attach_forward_returns, load_universe, session  # noqa: E402


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    down = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _rank_ic(sig, ret):
    s = pd.DataFrame({"sig": sig, "ret": ret}).dropna()
    if len(s) < 30:
        return float("nan"), int(len(s))
    return float(spearmanr(s["sig"], s["ret"]).correlation), len(s)


def _chrono_split(sub, frac=0.7):
    ts = np.sort(sub["ts"].unique())
    if len(ts) < 10:
        return sub, sub
    cut = ts[int(len(ts) * frac)]
    return sub[sub["ts"] < cut], sub[sub["ts"] >= cut]


SIGNALS = [
    ("rsi_rev(mean-rev)", "sig_rsi_rev"),
    ("dist_ma50(mean-rev)", "sig_dist_ma50"),
    ("reversal5d", "sig_reversal5"),
    ("mom252(CTRL)", "sig_mom252"),
]


def main():
    max_stocks = int(os.getenv("RCA_MAX_STOCKS", "80"))
    start = os.getenv("RCA_START", "2021-07-26")
    end = os.getenv("RCA_END", "2026-07-25")

    db = session()
    try:
        prices = load_universe(db, max_stocks, start, end)
    finally:
        db.close()

    # equal-weight MARKET index (from our universe) + its 200d MA -> market regime per day.
    ret_frames = []
    for sid, df in prices.items():
        d = df.sort_values("ts").copy()
        d["ret"] = d["close"].pct_change()
        ret_frames.append(d.set_index("ts")["ret"].rename(sid))
    retmat = pd.concat(ret_frames, axis=1).sort_index()
    mkt_ret = retmat.mean(axis=1)
    mkt_idx = (1 + mkt_ret).cumprod()
    mkt_ma = mkt_idx.rolling(200, min_periods=100).mean()
    mkt_bear = (mkt_idx < mkt_ma)  # True = bear regime that day
    bear_frac = float(mkt_bear.fillna(False).mean())

    records = []
    for sid, df in prices.items():
        d = df.sort_values("ts").copy()
        d = attach_forward_returns(d, HORIZONS).reset_index(drop=True)
        d["rsi"] = _rsi(d["close"])
        d["sma50"] = d["close"].rolling(50, min_periods=20).mean()
        d["ret5d"] = d["close"].pct_change(5)
        d["mom252"] = d["close"].pct_change(252)
        d["bear"] = d["ts"].map(lambda t: bool(mkt_bear.get(t, False)) if pd.notna(t) else False)
        d["sid"] = sid
        d["sig_rsi_rev"] = -d["rsi"]
        d["sig_dist_ma50"] = -(d["close"] / d["sma50"] - 1)
        d["sig_reversal5"] = -d["ret5d"]
        d["sig_mom252"] = d["mom252"]
        keep = ["sid", "ts", "bear"] + [c for _, c in SIGNALS] + [f"fwd_{h}" for h in HORIZONS]
        records.append(d[keep])
    big = pd.concat(records, ignore_index=True)

    print("=" * 96)
    print(f"REGIME-CONDITIONAL ATTRIBUTION   stocks={len(prices)}  window={start}..{end}")
    print(f"market regime = equal-weight index vs 200d MA;  bear-regime days = {bear_frac*100:.1f}% of sample")
    print("POSITIVE IC == signal predicts UP. mean-reversion edge = persistent val IC > 0.03-0.05 IN BEAR.")
    print("=" * 96)

    for name, mask in [("BEAR (market < 200d MA)", big["bear"] == True),   # noqa: E712
                        ("BULL (market >= 200d MA)", big["bear"] == False),  # noqa: E712
                        ("ALL (unconditional) ", np.ones(len(big), dtype=bool))]:
        sub = big[mask].copy()
        n_days = sub["ts"].nunique()
        train, val = _chrono_split(sub)
        print(f"\n{name}   rows={len(sub)}  days={n_days}  (train={len(train)}/val={len(val)})")
        print(f"{'signal':>22} | {'h=5 val/train(N)':>22} | {'h=10 val/train(N)':>22} | {'h=21 val/train(N)':>22}")
        print("-" * 96)
        for label, col in SIGNALS:
            cells = []
            for h in HORIZONS:
                ic_t, nt = _rank_ic(train[col], train[f"fwd_{h}"])
                ic_v, nv = _rank_ic(val[col], val[f"fwd_{h}"])
                cells.append(f"{ic_v:+.3f}/{ic_t:+.3f}({nv})")
            print(f"{label:>22} | {cells[0]:>22} | {cells[1]:>22} | {cells[2]:>22}")

    print("\n" + "=" * 96)
    print("READ: look at the BEAR block. If rsi_rev/dist_ma50/reversal5 show val IC persistently")
    print("> +0.03 across horizons IN BEAR (and mom252 does NOT), bear mean-reversion is tradeable")
    print("-> regime-switching system is worth building. If ~0, bear ops aren't capturable (EMH).")
    print("=" * 96)


if __name__ == "__main__":
    main()
