#!/usr/bin/env python3
"""
Regime-switching backtest — the first evidence-backed system for BOTH regimes.

Builds on two validated conditional findings (regime_conditional_attribution.py +
tsmomentum_probe.py):
  - BULL (market >= 200d MA): 252-day momentum has real edge (bull Sharpe up to 1.57).
  - BEAR (market <  200d MA): mean-reversion (oversold vs MA) has real edge
    (val IC +0.08..+0.11 across horizons) — the snap-back bounce; momentum is NEGATIVE.

So: run momentum in bulls, mean-reversion snap-back in bears. This PARTICIPATES in bulls
AND CAPTURES bear opportunities (instead of hiding in cash). One honest config (no sweeping
— dist_ma50 was the standout); reported with PSR0, a regime-split Sharpe, and side-by-side
vs pure-momentum and equal-weight buy-&-hold.

METHOD:
  - Market regime = equal-weight universe index vs its 200d MA (robust, no SPY fetch needed).
  - Bull weight: long if mom252>0, size = target_vol/realized_vol (63d), capped, gross<=100%.
  - Bear weight: long if close<sma50 (below MA), strength ∝ -(close/sma50-1) clipped at 20%
    (more beaten-down -> bigger), vol-scaled, capped, gross<=100%.
  - DECISION at T close, EARNED at T+1 (weight.shift(1)) -> no look-ahead. 5bps round-trip.
  - PSR0 + multiple-testing note (Bailey & Lopez de Prado).

Pure pandas -> seconds. No live-path, no DB writes.
Run: docker exec stock_analyzer_backend python /app/scripts/regime_switch_backtest.py
Env: RS_MAX_STOCKS=80 RS_TARGET_VOL=0.10 RS_MAX_WEIGHT=0.05 RS_COST_BPS=5
"""
import os
import sys
from math import log, sqrt

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, "/app")

from app.db.database import SessionLocal  # noqa: E402
from app.services.backtest.runner import prepare_backtest  # noqa: E402
from app.services.benchmark_service import get_spy_series_for_window  # noqa: E402


def _psr0(sharpe, ret):
    r = ret.dropna()
    n = len(r)
    if n < 30 or sharpe == 0:
        return float("nan")
    T = n / 252.0
    sk = r.skew()
    ku = r.kurt() + 3.0
    inner = 1 - sk * sharpe + (ku - 1) / 4.0 * sharpe ** 2
    if T <= 1 or inner <= 0:
        return float("nan")
    return float(norm.cdf(sharpe * sqrt(T - 1) / sqrt(inner)))


def _summary(ret):
    r = ret.dropna()
    if len(r) < 2:
        return dict(sharpe=float("nan"), total=float("nan"), maxdd=float("nan"),
                    ann_ret=float("nan"), ann_vol=float("nan"), psr0=float("nan"))
    ann_ret = r.mean() * 252
    ann_vol = r.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
    eq = (1 + r).cumprod()
    return dict(sharpe=float(sharpe), total=float(eq.iloc[-1] - 1),
                maxdd=float((eq / eq.cummax() - 1).min()), ann_ret=float(ann_ret),
                ann_vol=float(ann_vol), psr0=_psr0(sharpe, r))


def _weights(closes, mode, target_vol, max_weight):
    rets = closes.pct_change()
    vol = rets.rolling(63, min_periods=21).std() * np.sqrt(252)
    raw = (target_vol / vol).clip(upper=max_weight).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if mode == "bull":  # 252-day momentum
        long_sig = (closes.pct_change(252) > 0).astype(float)
        strength = 1.0
    else:  # bear: mean-reversion snap-back (oversold vs sma50)
        sma50 = closes.rolling(50, min_periods=20).mean()
        dist = closes / sma50 - 1.0
        long_sig = (dist < 0).astype(float)
        strength = (-dist).clip(upper=0.20)  # more below MA -> bigger, cap at 20%
    w = long_sig * strength * raw
    gross = w.sum(axis=1)
    scale = (1.0 / gross).where(gross > 1.0, 1.0)
    return w.mul(scale, axis=0)


def _port_ret(closes, w, cost_bps):
    rets = closes.pct_change()
    w_lag = w.shift(1).fillna(0.0)
    pr = (w_lag * rets).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    pr = pr - turnover * (cost_bps / 1e4)
    return pr, w_lag.sum(axis=1).mean(), turnover.mean()


def main():
    max_stocks = int(os.getenv("RS_MAX_STOCKS", "80"))
    target_vol = float(os.getenv("RS_TARGET_VOL", "0.10"))
    max_weight = float(os.getenv("RS_MAX_WEIGHT", "0.05"))
    cost_bps = float(os.getenv("RS_COST_BPS", "5"))
    start = pd.Timestamp("2021-07-26").tz_localize("UTC")
    end = pd.Timestamp("2026-07-25").tz_localize("UTC")

    db = SessionLocal()
    try:
        prices_by_stock, trading_dates, _ = prepare_backtest(db, start, end, max_stocks)
    finally:
        db.close()

    frames = {sid: df.set_index("timestamp")["close"] for sid, df in prices_by_stock.items()}
    closes = pd.concat(frames, axis=1).sort_index()
    if closes.index.tz is None:
        closes.index = closes.index.tz_localize("UTC")
    closes.index = closes.index.tz_convert(None)
    closes = closes.ffill().dropna(how="all")

    # market regime: equal-weight index vs 200d MA.
    # Warmup (mkt_ma NaN, first ~100d) is NOT a regime. Earlier `fillna(False)` misclassified
    # the mid-2021 bull warmup as BEAR -> ran mean-reversion (long laggards) in a rising market
    # -> dragged the "bear" Sharpe negative (the bug regime_switch_diagnostic.py caught). Now:
    # bear is defined only where the MA is valid, and warmup defaults to the bull/momentum mode
    # (which is flat until 252d momentum exists, so no spurious trades).
    mkt_idx = (1 + closes.pct_change().mean(axis=1)).cumprod()
    mkt_ma = mkt_idx.rolling(200, min_periods=100).mean()
    mkt_valid = mkt_ma.notna()
    is_bull = ((mkt_idx >= mkt_ma) | ~mkt_valid)           # warmup -> bull default (flat)
    bear_mask = mkt_valid & (mkt_idx < mkt_ma)             # real bear only (matches diagnostic)
    bear_frac = float(bear_mask.mean())

    w_bull = _weights(closes, "bull", target_vol, max_weight)
    w_bear = _weights(closes, "bear", target_vol, max_weight)
    w_switch = w_bull.mask(bear_mask, w_bear)   # bear-day -> bear weights
    w_momonl = w_bull                           # pure momentum (every day)
    # equal-weight buy & hold (static long, daily-rebalanced equal weight)
    n_eq = closes.notna().sum(axis=1).replace(0, np.nan)
    ew = (1.0 / n_eq).fillna(0.0)
    w_hold = pd.DataFrame(np.repeat(ew.values[:, None], closes.shape[1], axis=1),
                          index=closes.index, columns=closes.columns).fillna(0.0)

    pr_switch, exp_sw, to_sw = _port_ret(closes, w_switch, cost_bps)
    pr_mom, exp_m, to_m = _port_ret(closes, w_momonl, cost_bps)
    pr_hold, exp_h, to_h = _port_ret(closes, w_hold, 0.0)

    # DEBUG: reconcile the bear leg vs a plain equal-weight-below-MA baseline.
    # Two methods on the SAME closes: (a) causal daily book (shift +1, past), (b) fwd_1 (shift -1, future).
    rets_dbg = closes.pct_change()
    sma50_dbg = closes.rolling(50, min_periods=20).mean()
    below_dbg = (closes < sma50_dbg).astype(float)
    eq_causal = (below_dbg.shift(1) * rets_dbg).sum(axis=1) / below_dbg.shift(1).sum(axis=1).replace(0, np.nan)
    fwd1 = closes.shift(-1) / closes - 1.0
    eq_fwd1 = (below_dbg * fwd1).sum(axis=1) / below_dbg.sum(axis=1).replace(0, np.nan)
    # row-pooled (matches diagnostic's per-(stock,T) mean exactly):
    pooled = (below_dbg * fwd1).sum().sum() / below_dbg.sum().sum()
    wswitch_bear_exp = w_switch.loc[bear_mask].sum(axis=1).mean()
    print("-" * 92)
    print(f"[DEBUG bear leg]  days={int(bear_mask.sum())}  (all on the SAME closes)")
    print(f"  regime-switch bear (realized):      mean_ret={pr_switch[bear_mask].mean()*100:+.5f}%/d  "
          f"sharpe={_summary(pr_switch[bear_mask])['sharpe']:+.2f}  exposure={wswitch_bear_exp:.3f}")
    print(f"  equal-weight below-MA CAUSAL (s+1):  mean_ret={eq_causal[bear_mask].mean()*100:+.5f}%/d")
    print(f"  equal-weight below-MA FWD_1 (s-1):   mean_ret={eq_fwd1[bear_mask].mean()*100:+.5f}%/d  "
          f"(day-pooled)   row-pooled={pooled*100:+.5f}%")
    print("  If CAUSAL and FWD_1 disagree in SIGN here -> indexing/alignment bug in this script.")
    print("  If they AGREE (both -) but the diagnostic said + -> the two scripts load different data.")
    print("-" * 92)

    T = len(closes) / 252.0
    luck = sqrt(2 * log(3) / T)  # 3 strategies compared -> expected best-by-luck Sharpe

    print("=" * 92)
    print(f"REGIME-SWITCH BACKTEST   stocks={closes.shape[1]}  days={len(closes)} ({T:.1f}y)  "
          f"bear-regime={bear_frac*100:.1f}% of days")
    print(f"target_vol={target_vol} max_weight={max_weight} cost={cost_bps}bps  "
          f"| luck threshold (3 strats, {T:.1f}y) ≈ {luck:.2f}")
    print("-" * 92)
    print(f"{'strategy':>20} | {'annRet%':>8} | {'annVol%':>8} | {'Sharpe':>7} | {'PSR0':>6} | "
          f"{'maxDD%':>7} | {'bearSh':>7} | {'bullSh':>7} | {'exposure':>8} | {'turn':>6}")
    print("-" * 92)
    for name, pr, expo, to in [("regime-switch", pr_switch, exp_sw, to_sw),
                               ("pure 252d momentum", pr_mom, exp_m, to_m),
                               ("equal-weight B&H", pr_hold, exp_h, to_h)]:
        m = _summary(pr)
        bsh = _summary(pr[bear_mask])["sharpe"] if bear_mask.sum() else float("nan")
        ush = _summary(pr[is_bull])["sharpe"] if is_bull.sum() else float("nan")
        print(f"{name:>20} | {m['ann_ret']*100:>8.2f} | {m['ann_vol']*100:>8.2f} | "
              f"{m['sharpe']:>7.2f} | {m['psr0']:>6.2f} | {m['maxdd']*100:>7.2f} | "
              f"{bsh:>7.2f} | {ush:>7.2f} | {expo:>8.2%} | {to:>6.3f}")
    spy_total = None
    try:
        s = get_spy_series_for_window(start.tz_convert(None), end.tz_convert(None))
        if s:
            spy_total = float(s[-1]["return_pct"]) / 100.0
    except Exception as e:
        print(f"[warn] SPY benchmark unavailable: {e}")
    print("=" * 92)
    sw = _summary(pr_switch)
    if spy_total is not None:
        print(f"SPY window total return = {spy_total*100:.1f}%   "
              f"regime-switch total = {sw['total']*100:.1f}%  "
              f"(alpha vs SPY = {(sw['total']-spy_total)*100:+.1f}%)")
    else:
        print(f"SPY n/a   regime-switch total = {sw['total']*100:.1f}%")
    beats = sw["sharpe"] > luck and sw["psr0"] > 0.95
    if beats:
        verdict = "REAL EDGE — clears luck + PSR>0.95; first validated system."
    else:
        verdict = ("borderline/null on the strict bar — inspect the regime split: does "
                   "bear mean-reversion carry the bear (bearSh_switch >> bearSh_mom)?")
    print(f"Verdict: Sharpe {sw['sharpe']:.2f} (PSR0 {sw['psr0']:.2f}); {verdict}")
    print("READ: regime-switch should beat pure-momentum in the BEAR (bearSh) without giving")
    print("back the bull (bullSh). If bearSh_switch >> bearSh_mom, the snap-back capture works.")


if __name__ == "__main__":
    main()
