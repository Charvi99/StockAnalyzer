#!/usr/bin/env python3
"""
Attribution: do insider (Form-4) transactions predict forward returns?

Tests the documented "cluster open-market insider buying -> positive returns"
anomaly. Signals (CAUSAL, as-of each trading date T); each trade is first
"seen" on the first trading day >= its PUBLICATION date (filing_date + 1 day):

  sig_netbuy_90   : (sum BUY shares - sum SELL shares) for OPEN-MARKET trades
                    (transaction_type BUY/SELL, i.e. codes P/S) seen in the
                    trailing 90d, DIVIDED by trailing-20d avg DAILY VOLUME
                    (a liquidity scaler available historically for both train
                    and val — unlike free-float, which has only a current
                    snapshot and made the train period non-comparable).
  sig_netbuy_30   : same, trailing 30d / vol20.
  sig_offdir_90   : net open-market buying by OFFICERS or DIRECTORS only in 90d / vol20.
  sig_buyevents_30: count of BUY transactions in trailing 30d (cluster proxy).

rank IC vs forward {5,10,21}d, chronological 0.7 train/val.

Env: ALT_MAX_STOCKS (default 100)
Run:  docker exec stock_analyzer_backend python /app/scripts/insider_attribution.py
"""
from __future__ import annotations

import os
import sys
from typing import Dict

import numpy as np
import pandas as pd

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from sqlalchemy import text  # noqa: E402

from attribution_lib import (  # noqa: E402
    HORIZONS, attach_forward_returns, load_universe, run_attribution, session,
)

PUB_LAG = pd.Timedelta(days=1)
D30 = pd.Timedelta(days=30)
D90 = pd.Timedelta(days=90)


def load_trades(db, stock_ids) -> Dict[int, list]:
    rows = db.execute(
        text("SELECT stock_id, filing_date, transaction_type, shares, "
             "is_officer, is_director, owner_cik "
             "FROM insider_trades WHERE stock_id = ANY(:ids) AND filing_date IS NOT NULL "
             "AND transaction_type IN ('BUY','SELL') AND shares IS NOT NULL"),
        {"ids": list(stock_ids)},
    ).all()
    out: Dict[int, list] = {}
    for sid, fd, ttype, shares, is_off, is_dir, ocik in rows:
        out.setdefault(sid, []).append(
            (pd.Timestamp(fd).tz_localize("UTC") + PUB_LAG, ttype, float(shares),
             bool(is_off), bool(is_dir))
        )
    return out


def load_volumes(db, stock_ids) -> Dict[int, pd.DataFrame]:
    """Daily volume per stock (historical -> normalizes net buying by liquidity)."""
    rows = db.execute(
        text("SELECT stock_id, timestamp, volume FROM stock_prices "
             "WHERE timeframe='1d' AND stock_id = ANY(:ids) AND volume IS NOT NULL "
             "ORDER BY stock_id, timestamp"),
        {"ids": list(stock_ids)},
    ).all()
    by: Dict[int, list] = {}
    for sid, ts, vol in rows:
        by.setdefault(sid, []).append((pd.Timestamp(ts).tz_convert("UTC").normalize(), float(vol)))
    return {sid: pd.DataFrame(v, columns=["ts", "volume"]).sort_values("ts")
            for sid, v in by.items() if v}


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start, end = "2021-07-26", "2026-07-24"
    db = session()
    try:
        prices = load_universe(db, max_stocks, start, end)
        sids = list(prices.keys())
        trades = load_trades(db, sids)
        vols = load_volumes(db, sids)
        print(f"[insider] universe={len(sids)}  with trades={len(trades)}  with volume={len(vols)}")

        records = []
        for sid, df in prices.items():
            df = attach_forward_returns(df.sort_values("ts").copy(), HORIZONS).reset_index(drop=True)
            ts = df["ts"].values
            n = len(df)
            net90 = np.zeros(n); net30 = np.zeros(n); offdir90 = np.zeros(n); ev30 = np.zeros(n)
            for pub, ttype, shares, is_off, is_dir in trades.get(sid, []):
                pol = shares if ttype == "BUY" else -shares
                pub_np = np.datetime64(pub)
                i = int(np.searchsorted(ts, pub_np, side="left"))
                if i >= n:
                    continue
                j90 = int(np.searchsorted(ts, np.datetime64(pub + D90), side="left"))
                j30 = int(np.searchsorted(ts, np.datetime64(pub + D30), side="left"))
                net90[i:j90] += pol
                net30[i:j30] += pol
                if is_off or is_dir:
                    offdir90[i:j90] += pol
                if ttype == "BUY":
                    ev30[i:j30] += 1
            vol_df = vols.get(sid)
            if vol_df is not None:
                # map volume onto the price frame's own ts (avoids merge exploding
                # on the few duplicate daily bars in stock_prices)
                vmap = vol_df.drop_duplicates("ts").set_index("ts")["volume"]
                vol = df["ts"].map(vmap).to_numpy(dtype=float)
                avg20 = pd.Series(vol).rolling(20, min_periods=5).mean().to_numpy(dtype=float)
                with np.errstate(divide="ignore", invalid="ignore"):
                    nb90 = np.where(avg20 > 0, net90 / avg20, np.nan)
                    nb30 = np.where(avg20 > 0, net30 / avg20, np.nan)
                    od90 = np.where(avg20 > 0, offdir90 / avg20, np.nan)
            else:
                nb90 = nb30 = od90 = np.full(n, np.nan)
            df["sig_netbuy_90"] = nb90
            df["sig_netbuy_30"] = nb30
            df["sig_offdir_90"] = od90
            df["sig_buyevents_30"] = ev30
            for _, r in df.iterrows():
                records.append({
                    "sid": sid, "T": r["ts"],
                    "sig_netbuy_90": r["sig_netbuy_90"], "sig_netbuy_30": r["sig_netbuy_30"],
                    "sig_offdir_90": r["sig_offdir_90"], "sig_buyevents_30": r["sig_buyevents_30"],
                    **{f"fwd_{h}": r[f"fwd_{h}"] for h in HORIZONS},
                })
    finally:
        db.close()

    big = pd.DataFrame.from_records(records)
    run_attribution(
        "INSIDER (Form-4)", big,
        [("netbuy_90/vol20", "sig_netbuy_90"), ("netbuy_30/vol20", "sig_netbuy_30"),
         ("offdir_netbuy_90/vol20", "sig_offdir_90"), ("buyevents_30(cluster)", "sig_buyevents_30")],
        baseline_hint="(documented: open-market cluster buying -> positive fwd returns)",
    )


if __name__ == "__main__":
    main()
