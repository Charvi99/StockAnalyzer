#!/usr/bin/env python3
"""
Attribution: do SEC 8-K material-event disclosures predict forward returns?

Signals (CAUSAL, as-of each trading date T). Each disclosure is first "seen" on
the first trading day >= its publication date (filing_date + 1 calendar day).
  sig_count_7  : number of disclosures seen in the trailing 7 calendar days.
  sig_count_30 : number of disclosures seen in the trailing 30 calendar days.
  sig_polarity_30 : sum over disclosures seen in the trailing 30d of a PER-CATEGORY
                 polarity. Polarity[primary_category] = MEAN forward-21d return of
                 that category's disclosures IN THE TRAIN PERIOD ONLY (train-only
                 feature -> no look-ahead). Categories with <5 train events -> 0.

rank IC vs forward {5,10,21}d, chronological 0.7 train/val.

Env: ALT_MAX_STOCKS (default 100)
Run:  docker exec stock_analyzer_backend python /app/scripts/disclosures_8k_attribution.py
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Dict

import numpy as np
import pandas as pd

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from sqlalchemy import text  # noqa: E402

from attribution_lib import (  # noqa: E402
    HORIZONS, attach_forward_returns, chronological_split, load_universe, run_attribution, session,
)

PUB_LAG = pd.Timedelta(days=1)
MIN_CAT_EVENTS = 5


def load_disclosures(db, stock_ids) -> Dict[int, list]:
    rows = db.execute(
        text("SELECT stock_id, filing_date, primary_category "
             "FROM sec_disclosures WHERE stock_id = ANY(:ids) AND filing_date IS NOT NULL"),
        {"ids": list(stock_ids)},
    ).all()
    out: Dict[int, list] = defaultdict(list)
    for sid, fd, cat in rows:
        out[sid].append((pd.Timestamp(fd).tz_localize("UTC") + PUB_LAG, cat))
    return out


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start, end = "2024-06-01", "2026-06-01"
    db = session()
    try:
        prices = load_universe(db, max_stocks, start, end)
        disc = load_disclosures(db, list(prices.keys()))
        print(f"[8-K] universe={len(prices)} stocks  with disclosures={len(disc)}")

        per_stock = {}  # sid -> (df_with_counts, [(cat, fwd21, seen_ts)])
        for sid, df in prices.items():
            df = attach_forward_returns(df.sort_values("ts").copy(), HORIZONS).reset_index(drop=True)
            ts = df["ts"].values  # datetime64[ns, UTC]
            n = len(df)
            cnt7 = np.zeros(n); cnt30 = np.zeros(n)
            seen = []
            for pub, cat in disc.get(sid, []):
                pub_np = np.datetime64(pub)
                i = int(np.searchsorted(ts, pub_np, side="left"))
                if i >= n:
                    seen.append((cat, np.nan, pd.NaT))
                    continue
                j30 = int(np.searchsorted(ts, np.datetime64(pub + pd.Timedelta(days=30)), side="left"))
                j7 = int(np.searchsorted(ts, np.datetime64(pub + pd.Timedelta(days=7)), side="left"))
                cnt30[i:j30] += 1
                cnt7[i:j7] += 1
                seen.append((cat, df["fwd_21"].iloc[i], df["ts"].iloc[i]))
            df["sig_count_7"] = cnt7
            df["sig_count_30"] = cnt30
            per_stock[sid] = (df, seen)
    finally:
        db.close()

    # chronological split (over all T) defines the train period for polarity
    frames = []
    for sid, (df, _) in per_stock.items():
        f = df[["ts", "sig_count_7", "sig_count_30"] + [f"fwd_{h}" for h in HORIZONS]].copy()
        f["sid"] = sid
        frames.append(f)
    big0 = pd.concat(frames, ignore_index=True).rename(columns={"ts": "T"})
    _, _, split = chronological_split(big0, 0.7)

    cat_sums = defaultdict(list)
    for sid, (_, seen) in per_stock.items():
        for cat, fwd, seen_ts in seen:
            if cat is None or pd.isna(fwd) or seen_ts is pd.NaT:
                continue
            if seen_ts < split:
                cat_sums[cat].append(float(fwd))
    polarity = {c: float(np.mean(v)) for c, v in cat_sums.items() if len(v) >= MIN_CAT_EVENTS}
    print(f"[8-K] learned polarity for {len(polarity)} primary categories "
          f"(of {len(cat_sums)} seen in train)")

    for sid, (df, _) in per_stock.items():
        ts = df["ts"].values
        n = len(df)
        pol30 = np.zeros(n)
        for pub, cat in disc.get(sid, []):
            pol = polarity.get(cat, 0.0)
            if pol == 0.0:
                continue
            i = int(np.searchsorted(ts, np.datetime64(pub), side="left"))
            if i >= n:
                continue
            j30 = int(np.searchsorted(ts, np.datetime64(pub + pd.Timedelta(days=30)), side="left"))
            pol30[i:j30] += pol
        df["sig_polarity_30"] = pol30

    frames = []
    for sid, (df, _) in per_stock.items():
        f = df[["ts", "sig_count_7", "sig_count_30", "sig_polarity_30"] + [f"fwd_{h}" for h in HORIZONS]].copy()
        f["sid"] = sid
        frames.append(f)
    big = pd.concat(frames, ignore_index=True).rename(columns={"ts": "T"})

    run_attribution(
        "SEC 8-K DISCLOSURES", big,
        [("count_7d", "sig_count_7"), ("count_30d", "sig_count_30"),
         ("polarity_30d(train-learned)", "sig_polarity_30")],
        baseline_hint="(event-driven: category polarity learned train-only)",
    )


if __name__ == "__main__":
    main()
