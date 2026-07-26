#!/usr/bin/env python3
"""
Attribution: do FINRA short-interest / short-volume predict forward returns?

Signals (CAUSAL, as-of each trading date T):
  sig_dtc : days_to_cover from the most-recent short_interest report whose
            PUBLICATION date (settlement_date + 3 calendar days, the FINRA
            publication lag) is <= T. High DTC = bearish crowding OR squeeze
            fuel; the IC sign reveals which.
  sig_svr : short_volume_ratio (short/total volume, %) from the most-recent
            short_volume day whose publication date (trade date + 1, FINRA
            T+1 reporting) is <= T. High = heavier daily short selling.

Publication-lag shifts keep this strictly point-in-time (no look-ahead).
Compares rank IC vs forward {5,10,21}d returns, chronological 0.7 train/val.

Env: ALT_MAX_STOCKS (default 100)
Run:  docker exec stock_analyzer_backend python /app/scripts/short_interest_attribution.py
"""
from __future__ import annotations

import os
import sys
from typing import Dict

import pandas as pd

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from sqlalchemy import text  # noqa: E402

from attribution_lib import (  # noqa: E402
    HORIZONS, attach_forward_returns, load_universe, run_attribution, session,
)

SI_PUB_LAG = pd.Timedelta(days=3)   # short-interest published ~settlement + 3 days
SV_PUB_LAG = pd.Timedelta(days=1)   # short-volume reported T+1


def load_short(db, stock_ids) -> Dict[int, pd.DataFrame]:
    rows = db.execute(
        text("SELECT stock_id, settlement_date, days_to_cover "
             "FROM short_interest WHERE stock_id = ANY(:ids) AND days_to_cover IS NOT NULL"),
        {"ids": list(stock_ids)},
    ).all()
    out: Dict[int, pd.DataFrame] = {}
    for sid, sd, dtc in rows:
        out.setdefault(sid, []).append((pd.Timestamp(sd).tz_localize("UTC") + SI_PUB_LAG, float(dtc)))
    return {sid: pd.DataFrame(v, columns=["pub_ts", "days_to_cover"]).sort_values("pub_ts")
            for sid, v in out.items() if v}


def load_short_vol(db, stock_ids) -> Dict[int, pd.DataFrame]:
    rows = db.execute(
        text("SELECT stock_id, date, short_volume_ratio "
             "FROM short_volume WHERE stock_id = ANY(:ids) AND short_volume_ratio IS NOT NULL"),
        {"ids": list(stock_ids)},
    ).all()
    out: Dict[int, pd.DataFrame] = {}
    for sid, d, svr in rows:
        out.setdefault(sid, []).append((pd.Timestamp(d).tz_localize("UTC") + SV_PUB_LAG, float(svr)))
    return {sid: pd.DataFrame(v, columns=["pub_ts", "short_volume_ratio"]).sort_values("pub_ts")
            for sid, v in out.items() if v}


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start, end = "2024-06-01", "2026-06-01"
    db = session()
    try:
        prices = load_universe(db, max_stocks, start, end)
        sids = list(prices.keys())
        si = load_short(db, sids)
        sv = load_short_vol(db, sids)
        print(f"[short] universe={len(sids)} stocks  with SI={len(si)}  with SV={len(sv)}")

        records = []
        for sid, df in prices.items():
            df = attach_forward_returns(df.sort_values("ts").copy(), HORIZONS)
            if sid in si:
                m = si[sid]
                df = pd.merge_asof(df, m, left_on="ts", right_on="pub_ts", direction="backward")
            else:
                df["days_to_cover"] = pd.NA
            if sid in sv:
                m = sv[sid]
                df = pd.merge_asof(df, m[["pub_ts", "short_volume_ratio"]],
                                   left_on="ts", right_on="pub_ts", direction="backward")
            else:
                df["short_volume_ratio"] = pd.NA
            for _, r in df.iterrows():
                records.append({
                    "sid": sid, "T": r["ts"],
                    "sig_dtc": r.get("days_to_cover"),
                    "sig_svr": r.get("short_volume_ratio"),
                    **{f"fwd_{h}": r[f"fwd_{h}"] for h in HORIZONS},
                })
    finally:
        db.close()

    big = pd.DataFrame.from_records(records)
    run_attribution(
        "SHORT INTEREST / VOLUME", big,
        [("days_to_cover", "sig_dtc"), ("short_vol_ratio", "sig_svr")],
        baseline_hint="(high-DTC squeeze vs crowding: sign reveals direction)",
    )


if __name__ == "__main__":
    main()
