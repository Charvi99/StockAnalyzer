#!/usr/bin/env python3
"""
Time-series momentum (TSMOM) probe — the decisive "is there ANY edge in our large-cap
daily data" test we have not run (Pillar A of docs/EDUCATION_AND_EDGE.md).

Trend-following is the single most robust documented out-of-sample anomaly (Moskowitz,
Ooi & Pedersen 2012). Unlike our rule engines (score-blending over 40 indicators), TSMOM
asks one question per asset: "is it trending?" — go long when its own past return > 0,
volatility-scaled so each name carries equal risk. Mechanically simple; theoretically the
most likely thing to show residual edge on the data we already hold.

METHOD (done right so we can trust a positive OR null result):
  - Long-only, position weight = target_vol / realized_vol_annual (63d), capped per name,
    gross exposure scaled to <= 100%.
  - DECISION at T's close, EARNED at T+1's return (weight.shift(1)) -> no look-ahead.
  - Round-trip cost (default 5bps x daily turnover) included.
  - HONESTY: reports the Probabilistic Sharpe Ratio P(true Sharpe > 0 | observed) per
    config, AND the multiple-testing "luck" threshold ≈ sqrt(2 ln N / T) across the N
    lookbacks tried (Bailey & Lopez de Prado). A "winner" must clear both to be believed.
  - Regime split: Sharpe in the 2022 bear vs the 2024-26 bull (edge must survive both).

Pure pandas (a wide date x stock close matrix) -> seconds, not hours. No live-path,
no DB writes. Reuses runner.prepare_backtest (prices) + benchmark_service (SPY).

Env:
  TSM_START      = YYYY-MM-DD (default 2021-07-26, ~5y)
  TSM_END        = YYYY-MM-DD (default 2026-07-25)
  TSM_MAX_STOCKS = N          (default 50; momentum needs breadth)
  TSM_LOOKBACKS  = csv        (default 21,63,126,252)
  TSM_TARGET_VOL = 0.10       (annualized vol target per name)
  TSM_MAX_WEIGHT = 0.05       (per-name cap)
  TSM_COST_BPS   = 5          (round-trip cost)

Run: docker exec stock_analyzer_backend python /app/scripts/tsmomentum_probe.py
"""
import os
import sys
from math import log, sqrt

import numpy as np
import pandas as pd

sys.path.insert(0, "/app")

from scipy.stats import norm  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.services.backtest.runner import prepare_backtest  # noqa: E402
from app.services.benchmark_service import get_spy_series_for_window  # noqa: E402


def _spy_total(start, end):
    """SPY cumulative total return over [start, end] (benchmark_service returns cumulative
    snapshots, NOT daily returns — so we use the last value as the window total)."""
    try:
        s = get_spy_series_for_window(start, end)
        if s:
            return float(s[-1]["return_pct"]) / 100.0
    except Exception as e:
        print(f"[warn] SPY benchmark unavailable: {e}")
    return None


def _psr0(sharpe, ret: pd.Series):
    """Probabilistic Sharpe Ratio P(true Sharpe > 0 | observed) — Bailey & Lopez de Prado.

    Accounts for non-normality (skew/kurt) and sample length (years). > 0.95 => 'probably real'.
    """
    r = ret.dropna()
    n = len(r)
    if n < 30 or sharpe == 0:
        return float("nan")
    T = n / 252.0
    sk = r.skew()
    ku_pearson = r.kurt() + 3.0  # pandas kurt is excess (Fisher) -> +3
    inner = 1 - sk * sharpe + (ku_pearson - 1) / 4.0 * sharpe ** 2
    if T <= 1 or inner <= 0:
        return float("nan")
    z = sharpe * sqrt(T - 1) / sqrt(inner)
    return float(norm.cdf(z))


def _summary(ret: pd.Series):
    r = ret.dropna()
    if len(r) < 2:
        return dict(total=float("nan"), ann_ret=float("nan"), ann_vol=float("nan"),
                    sharpe=float("nan"), maxdd=float("nan"))
    ann_ret = r.mean() * 252
    ann_vol = r.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
    eq = (1 + r).cumprod()
    maxdd = float((eq / eq.cummax() - 1).min())
    return dict(total=float(eq.iloc[-1] - 1), ann_ret=float(ann_ret), ann_vol=float(ann_vol),
                sharpe=float(sharpe), maxdd=maxdd, psr0=_psr0(sharpe, r))


def _run_config(closes, lookback, target_vol, max_weight, cost_bps):
    """One TSMOM config -> daily portfolio return series (decision at T-1 close)."""
    rets = closes.pct_change()
    vol_ann = rets.rolling(63, min_periods=21).std() * np.sqrt(252)
    mom = closes.pct_change(lookback)
    long_sig = (mom > 0).astype(float)
    raw = (target_vol / vol_ann).clip(upper=max_weight)
    raw = raw.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    weight = long_sig * raw
    # cap gross exposure to 100% (scale down uniformly if over)
    gross = weight.sum(axis=1)
    scale = (1.0 / gross).where(gross > 1.0, 1.0)
    weight = weight.mul(scale, axis=0)
    # decide at T close, earn T+1 return -> shift weights by 1 (NO look-ahead)
    w_lag = weight.shift(1).fillna(0.0)
    port_ret = (w_lag * rets).sum(axis=1)
    # cost: daily turnover x round-trip bps
    turnover = weight.diff().abs().sum(axis=1).fillna(0.0)
    port_ret = port_ret - turnover * (cost_bps / 1e4)
    exposure = w_lag.sum(axis=1).mean()
    avg_turnover = turnover.mean()
    return port_ret, exposure, avg_turnover


def main():
    start = pd.Timestamp(os.getenv("TSM_START", "2021-07-26")).tz_localize("UTC")
    end = pd.Timestamp(os.getenv("TSM_END", "2026-07-25")).tz_localize("UTC")
    max_stocks = int(os.getenv("TSM_MAX_STOCKS", "50"))
    lookbacks = [int(x) for x in os.getenv("TSM_LOOKBACKS", "21,63,126,252").split(",")]
    target_vol = float(os.getenv("TSM_TARGET_VOL", "0.10"))
    max_weight = float(os.getenv("TSM_MAX_WEIGHT", "0.05"))
    cost_bps = float(os.getenv("TSM_COST_BPS", "5"))

    db = SessionLocal()
    try:
        prices_by_stock, trading_dates, symbols = prepare_backtest(db, start, end, max_stocks)
    finally:
        db.close()

    # wide close matrix: date x stock_id, forward-filled.
    frames = {sid: df.set_index("timestamp")["close"] for sid, df in prices_by_stock.items()}
    closes = pd.concat(frames, axis=1).sort_index()
    if closes.index.tz is None:
        closes.index = closes.index.tz_localize("UTC")
    closes.index = closes.index.tz_convert(None)  # naive UTC calendar days for regime masks
    closes = closes.ffill().dropna(how="all")

    spy_total = _spy_total(start.tz_convert(None), end.tz_convert(None))

    # regime masks on the close index (naive datetime, UTC calendar days)
    idx = closes.index
    bear = (idx >= pd.Timestamp("2022-01-01")) & (idx < pd.Timestamp("2023-01-01"))
    bull = idx >= pd.Timestamp("2024-01-01")

    N = len(lookbacks)
    T = len(closes) / 252.0
    luck_sharpe = sqrt(2 * log(max(N, 2)) / max(T, 1e-9))  # expected max Sharpe under null

    print("=" * 92)
    print(f"TSMOM PROBE   window={start.date()}..{end.date()}  stocks={closes.shape[1]}  "
          f"days={len(closes)} ({T:.1f}y)")
    print(f"target_vol={target_vol}  max_weight={max_weight}  cost={cost_bps}bps  "
          f"lookbacks={lookbacks}  N_configs={N}")
    print(f"multiple-testing 'luck' Sharpe threshold ≈ sqrt(2 ln N / T) = {luck_sharpe:.2f}  "
          f"(best config must CLEAR this AND PSR0>0.95 to be believed)")
    print("-" * 92)
    print(f"{'lookback':>8} | {'annRet%':>8} | {'annVol%':>8} | {'Sharpe':>7} | {'PSR0':>6} | "
          f"{'maxDD%':>7} | {'bearSh':>7} | {'bullSh':>7} | {'exposure':>8} | {'turn':>6}")
    print("-" * 92)
    best = None
    for lb in lookbacks:
        port_ret, expo, turn = _run_config(closes, lb, target_vol, max_weight, cost_bps)
        m = _summary(port_ret)
        bear_sh = _summary(port_ret[bear]).get("sharpe", float("nan")) if bear.sum() else float("nan")
        bull_sh = _summary(port_ret[bull]).get("sharpe", float("nan")) if bull.sum() else float("nan")
        print(f"{lb:>8} | {m['ann_ret']*100:>8.2f} | {m['ann_vol']*100:>8.2f} | "
              f"{m['sharpe']:>7.2f} | {m.get('psr0', float('nan')):>6.2f} | {m['maxdd']*100:>7.2f} | "
              f"{bear_sh:>7.2f} | {bull_sh:>7.2f} | {expo:>8.2%} | {turn:>6.3f}")
        if best is None or m["sharpe"] > best[1]["sharpe"]:
            best = (lb, m, bear_sh, bull_sh)
    print("=" * 92)
    blb, bm, bbsh, bush = best
    clears = bm["sharpe"] > luck_sharpe and (bm.get("psr0", 0) or 0) > 0.95
    if spy_total is not None:
        alpha_total = bm["total"] - spy_total
        print(f"SPY window total return = {spy_total*100:.1f}%   "
              f"TSMOM-best total = {bm['total']*100:.1f}%   "
              f"(total alpha vs SPY = {alpha_total*100:+.1f}%)")
    else:
        print(f"TSMOM-best total = {bm['total']*100:.1f}%")
    print(f"BEST config: lookback={blb}d  Sharpe={bm['sharpe']:.2f}  PSR0={bm.get('psr0', float('nan')):.2f}  "
          f"bear={bbsh:.2f}  bull={bush:.2f}")
    if clears:
        verdict = "EDGE — clears luck threshold AND PSR0>0.95 (rare; promote candidate)."
    else:
        verdict = "NULL — best Sharpe does not clear the luck threshold (consistent with no edge)."
    print(f"Verdict: {verdict}")

    # ── Walk-forward / OOS: select lookback on TRAIN, evaluate on held-out TEST ──
    split = pd.Timestamp(os.getenv("TSM_OOS_SPLIT", "2024-01-01"))
    is_test = closes.index >= split
    is_train = ~is_test
    print("\n" + "=" * 92)
    print(f"WALK-FORWARD OOS   TRAIN = {closes.index[0].date()}..{split.date()}  "
          f"TEST = {split.date()}..{closes.index[-1].date()}  (held out)")
    print("Method: pick the lookback by TRAIN-window Sharpe, then report its TEST-window "
          "metrics only. NOTE: the only bear (2022) is in TRAIN, so TEST is a bull — this")
    print("validates generalization to a held-out bull, NOT bear-protection (only 1 bear exists).")
    print("-" * 92)
    print(f"{'lookback':>8} | {'trainSh':>8} | {'trainPSR':>7} | {'testSh':>8} | "
          f"{'testPSR':>7} | {'testRet%':>9} | {'testDD%':>8}")
    print("-" * 92)
    rows = []
    for lb in lookbacks:
        pr, _, _ = _run_config(closes, lb, target_vol, max_weight, cost_bps)
        tr = _summary(pr[is_train])
        te = _summary(pr[is_test])
        rows.append((lb, tr, te))
        print(f"{lb:>8} | {tr['sharpe']:>8.2f} | {tr.get('psr0', float('nan')):>7.2f} | "
              f"{te['sharpe']:>8.2f} | {te.get('psr0', float('nan')):>7.2f} | "
              f"{te['total']*100:>9.1f} | {te['maxdd']*100:>8.2f}")
    train_best = max(rows, key=lambda r: r[1]["sharpe"])
    test_best = max(rows, key=lambda r: r[2]["sharpe"])
    test_sharpes = [r[2]["sharpe"] for r in rows]
    median_test = sorted(test_sharpes)[len(test_sharpes) // 2]
    wlb, wtr, wte = train_best
    ranking_stable = (train_best[0] == test_best[0])
    beats_median = wte["sharpe"] > median_test
    print("-" * 92)
    print(f"TRAIN-selected lookback = {wlb}d (train Sharpe {wtr['sharpe']:.2f})  ->  "
          f"OOS test Sharpe = {wte['sharpe']:.2f} (PSR0 {wte.get('psr0', float('nan')):.2f}, "
          f"ret {wte['total']*100:.1f}%, DD {wte['maxdd']*100:.2f}%)")
    print(f"Test-best lookback = {test_best[0]}d ({test_best[2]['sharpe']:.2f}); "
          f"median test Sharpe across lookbacks = {median_test:.2f}")
    print(f"Ranking stable (train-best == test-best)? {'YES' if ranking_stable else 'NO'}; "
          f"train-best beats median test Sharpe? {'YES' if beats_median else 'NO'}")
    if ranking_stable and beats_median:
        wf = "SURVIVES OOS — the in-sample lookback choice generalizes; bull-participation is stable. Candidate primary for meta-labeling."
    else:
        wf = "FAILS OOS — in-sample lookback choice does NOT generalize (ranking unstable / not above median). Consistent with no robust edge."
    print(f"OOS verdict: {wf}")
    print("=" * 92)


if __name__ == "__main__":
    main()
