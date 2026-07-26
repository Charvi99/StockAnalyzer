#!/usr/bin/env python3
"""
Attribution: do fundamentals (accruals / profitability) predict returns?

SELF-CONTAINED EDGAR XBRL probe (Polygon financials are 403 on our plan; EDGAR
is free). Fetches SEC companyfacts (data.sec.gov) per stock, computes
point-in-time fundamentals, attributes. No DB table/migration — if edge shows,
THEN promote to a persisted table + engine integration.

Anomalies tested (signal as-of T = latest fiscal year whose filing date <= T):
  accruals   : (NetIncome - OperatingCashFlow) / TotalAssets  (Sloan 1996)
               high accruals -> earnings overstatement -> NEGATIVE future returns.
  grossprof  : GrossProfit / TotalAssets  (Novy-Marx profitability) -> POSITIVE.
  roe        : NetIncome / StockholdersEquity.

Annual (10-K) facts; point-in-time by each fact's `filed` date. SEC throttles
per-IP, so fetches use retry+backoff and a polite cadence (~3 req/s).

Env: ALT_MAX_STOCKS (default 100)
Run:  docker exec stock_analyzer_backend python /app/scripts/fundamentals_attribution.py
"""
from __future__ import annotations

import logging
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from sqlalchemy import text  # noqa: E402

from attribution_lib import (  # noqa: E402
    HORIZONS, attach_forward_returns, load_universe, run_attribution, session,
)

UA = "StockAnalyzer stock-analyzer@example.com"
WWW = "https://www.sec.gov"
DATA = "https://data.sec.gov"
SEC_DELAY = float(os.getenv("SEC_DELAY", "0.33"))  # ~3 req/s (SEC fair-access is 10/s)

CONCEPTS = {
    "ni": ("us-gaap", ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]),
    "ocf": ("us-gaap", ["NetCashProvidedByUsedInOperatingActivities",
                        "CashFlowFromContinuingOperatingActivities",
                        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]),
    "assets": ("us-gaap", ["Assets"]),
    "gp": ("us-gaap", ["GrossProfit"]),
    "equity": ("us-gaap", ["StockholdersEquity"]),
}


def _sec_get(url: str, tries: int = 6, timeout: int = 30):
    """GET with exponential backoff — SEC per-IP throttling drops bursty traffic."""
    backoff = 2.0
    for _ in range(tries):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
            if r.status_code in (429, 503):
                time.sleep(backoff); backoff *= 2; continue
            return r
        except requests.RequestException:
            time.sleep(backoff); backoff *= 2
    return None


def fetch_cik_map() -> dict:
    r = _sec_get(f"{WWW}/files/company_tickers.json")
    r.raise_for_status()
    return {v["ticker"].upper(): str(v["cik_str"]) for v in r.json().values()}


def annual_series(facts: dict, ns: str, concept: str) -> dict:
    """{period_end: (val, filed)} for annual (FY / 10-K) USD facts of a concept."""
    node = facts.get("facts", {}).get(ns, {}).get(concept)
    if not node:
        return {}
    out: dict = {}
    for unit_name, rows in node.get("units", {}).items():
        if unit_name != "USD":
            continue
        for r in rows:
            if r.get("fp") == "FY" or (r.get("form") or "") == "10-K":
                end = r.get("end")
                val = r.get("val")
                filed = r.get("filed") or ""
                if end and val is not None:
                    cur = out.get(end)
                    if cur is None or filed > cur[1]:
                        out[end] = (float(val), filed)
    return out


def _series_first(facts: dict, ns: str, concepts) -> dict:
    for c in concepts:
        s = annual_series(facts, ns, c)
        if s:
            return s
    return {}


def build_fundamentals(cik: str):
    r = _sec_get(f"{DATA}/api/xbrl/companyfacts/CIK{int(cik):010d}.json")
    if r is None or r.status_code != 200:
        return None
    facts = r.json()
    series = {k: _series_first(facts, ns, concepts) for k, (ns, concepts) in CONCEPTS.items()}
    rows = []
    for end, a in series["assets"].items():
        if not a or a[0] == 0:
            continue
        ni = series["ni"].get(end); ocf = series["ocf"].get(end)
        gp = series["gp"].get(end); eq = series["equity"].get(end)
        filed = max([x[1] for x in (ni, ocf, a, gp, eq) if x] or [""])
        if not filed:
            continue
        rec = {"end": end, "filed": filed, "assets": a[0]}
        if ni and ocf:
            rec["accruals"] = (ni[0] - ocf[0]) / a[0]
        if gp:
            rec["grossprof"] = gp[0] / a[0]
        if ni and eq and eq[0] != 0:
            rec["roe"] = ni[0] / eq[0]
        rows.append(rec)
    return rows


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start, end = "2021-07-26", "2026-07-24"
    db = session()
    fund: dict = {}
    try:
        prices = load_universe(db, max_stocks, start, end)
        sids = list(prices.keys())
        rows = db.execute(text("SELECT id, symbol FROM stocks WHERE id = ANY(:ids)"),
                          {"ids": sids}).all()
        sid2sym = {sid: sym for sid, sym in rows}
        cik_map = fetch_cik_map()
        print(f"[fund] universe={len(sids)}  cik_map={len(cik_map)}")

        miss = 0
        for i, sid in enumerate(sids, 1):
            cik = cik_map.get((sid2sym.get(sid) or "").upper())
            if not cik:
                miss += 1
                continue
            per = build_fundamentals(cik)
            time.sleep(SEC_DELAY)
            if not per:
                miss += 1
                continue
            df = pd.DataFrame(per)
            df["filed_ts"] = pd.to_datetime(df["filed"]).dt.tz_localize("UTC")
            for c in ("accruals", "grossprof", "roe"):
                if c not in df.columns:
                    df[c] = np.nan
            fund[sid] = df.sort_values("filed_ts")
            if i % 20 == 0:
                print(f"  {i}/{len(sids)} (got={len(fund)})", flush=True)
        print(f"[fund] got fundamentals for {len(fund)}/{len(sids)} stocks (miss={miss})")
    finally:
        db.close()

    records = []
    for sid, df in prices.items():
        df = attach_forward_returns(df.sort_values("ts").copy(), HORIZONS).reset_index(drop=True)
        f = fund.get(sid)
        if f is None or f.empty:
            df["accruals"] = np.nan; df["grossprof"] = np.nan; df["roe"] = np.nan
        else:
            m = f[["filed_ts", "accruals", "grossprof", "roe"]].dropna(subset=["filed_ts"])
            df = pd.merge_asof(df, m, left_on="ts", right_on="filed_ts", direction="backward")
        for _, r in df.iterrows():
            records.append({
                "sid": sid, "T": r["ts"],
                "sig_accruals": r.get("accruals"), "sig_grossprof": r.get("grossprof"),
                "sig_roe": r.get("roe"),
                **{f"fwd_{h}": r[f"fwd_{h}"] for h in HORIZONS},
            })

    big = pd.DataFrame.from_records(records)
    run_attribution(
        "FUNDAMENTALS (EDGAR XBRL)", big,
        [("accruals(Sloan)", "sig_accruals"), ("gross_profitability", "sig_grossprof"), ("roe", "sig_roe")],
        baseline_hint="(Sloan: high accruals -> NEG; Novy-Marx grossprof -> POS)",
    )


if __name__ == "__main__":
    main()
