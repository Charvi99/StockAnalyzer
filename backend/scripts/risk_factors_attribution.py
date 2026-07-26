#!/usr/bin/env python3
"""
Attribution: do SEC 10-K risk-factor disclosures predict forward returns?

Signals (CAUSAL, as-of each trading date T), from the most-recent 10-K whose
PUBLICATION date (filing_date + 1 calendar day) is <= T:
  sig_riskcount : number of distinct categorized risk factors in that 10-K.
  sig_newrisks  : number of risk-factor categories in that 10-K that were NOT
                  present in the company's immediately-prior 10-K (the documented
                  "added risk factors -> negative future returns" anomaly).

new-vs-prior is computed across consecutive 10-Ks (both filed <= T). The signal
is annual and carries forward daily from the last 10-K. rank IC vs forward
{5,10,21}d, chronological 0.7 train/val.

Env: ALT_MAX_STOCKS (default 100)
Run:  docker exec stock_analyzer_backend python /app/scripts/risk_factors_attribution.py
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

import pandas as pd

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from sqlalchemy import text  # noqa: E402

from attribution_lib import (  # noqa: E402
    HORIZONS, attach_forward_returns, load_universe, run_attribution, session,
)

PUB_LAG = pd.Timedelta(days=1)


def load_filings(db, stock_ids) -> Dict[int, List[Tuple]]:
    """Per stock: list of (pub_ts, riskcount, newrisks) sorted by pub_ts."""
    rows = db.execute(
        text("SELECT stock_id, filing_date, primary_category, secondary_category, tertiary_category "
             "FROM risk_factors WHERE stock_id = ANY(:ids) AND filing_date IS NOT NULL "
             "ORDER BY stock_id, filing_date"),
        {"ids": list(stock_ids)},
    ).all()
    by_stock: Dict[int, Dict[pd.Timestamp, set]] = {}
    for sid, fd, pc, sc, tc in rows:
        cat = (pc, sc, tc)
        by_stock.setdefault(sid, {}).setdefault(pd.Timestamp(fd), set()).add(cat)
    out: Dict[int, List[Tuple]] = {}
    for sid, filings in by_stock.items():
        ordered = sorted(filings.items())  # [(filing_date, set), ...]
        seq = []
        prev_set: set = set()
        for fd, catset in ordered:
            pub_ts = fd.tz_localize("UTC") + PUB_LAG
            newrisks = len(catset - prev_set) if prev_set else len(catset)
            seq.append((pub_ts, len(catset), newrisks))
            prev_set = catset
        out[sid] = seq
    return out


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start = os.getenv("ALT_START_DATE", "2024-06-01")
    end = os.getenv("ALT_END_DATE", "2026-06-01")
    db = session()
    try:
        prices = load_universe(db, max_stocks, start, end)
        filings = load_filings(db, list(prices.keys()))
        print(f"[risk] universe={len(prices)} stocks  with risk_filings={len(filings)}")

        records = []
        for sid, df in prices.items():
            df = attach_forward_returns(df.sort_values("ts").copy(), HORIZONS)
            seq = filings.get(sid)
            if seq:
                ff = pd.DataFrame(seq, columns=["pub_ts", "sig_riskcount", "sig_newrisks"])
                df = pd.merge_asof(df, ff, left_on="ts", right_on="pub_ts", direction="backward")
            else:
                df["sig_riskcount"] = pd.NA
                df["sig_newrisks"] = pd.NA
            for _, r in df.iterrows():
                records.append({
                    "sid": sid, "T": r["ts"],
                    "sig_riskcount": r.get("sig_riskcount"),
                    "sig_newrisks": r.get("sig_newrisks"),
                    **{f"fwd_{h}": r[f"fwd_{h}"] for h in HORIZONS},
                })
    finally:
        db.close()

    big = pd.DataFrame.from_records(records)
    run_attribution(
        "SEC RISK FACTORS", big,
        [("risk_count(latest 10-K)", "sig_riskcount"), ("new_risks(vs prior 10-K)", "sig_newrisks")],
        baseline_hint="(documented: added risk factors -> negative fwd returns)",
    )


if __name__ == "__main__":
    main()
