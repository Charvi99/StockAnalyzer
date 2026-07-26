#!/usr/bin/env python3
"""
Backfill SEC 8-K categorized material-event disclosures.

The endpoint IGNORES ticker filters (probe-confirmed) and pages GLOBALLY by
filing_date, so we sweep the whole market in the window and ROUTE each record
to our universe by matching its `tickers` list to our stock symbols.

  GET /stocks/filings/8-K/vX/disclosures?filing_date.gte=...&filing_date.lt=...
    -> {tickers:[...], cik, accession_number, filing_date, primary_category,
        secondary_category, tertiary_category, supporting_text, ...}

A single filing can yield several disclosure records (one per event category)
and list several tickers; we insert one row per (matched stock x disclosure).
Writes `sec_disclosures` with ON CONFLICT upsert.

Env:
  ALT_MAX_STOCKS   universe size (first N by id; default 100)
  ALT_START_DATE   sweep start 'YYYY-MM-DD' (default 2024-01-01)
  ALT_END_DATE     sweep end   'YYYY-MM-DD' (default 2026-07-01)
  POLYGON_DELAY    per-request floor seconds (default 0.15)

Run:  docker exec stock_analyzer_backend python /app/scripts/fetch_8k_disclosures.py
"""
from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from polygon_client import polygon_paginate, NotAuthorized  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fetch_8k_disclosures")


def _flush(db, batch):
    if not batch:
        return
    db.execute(
        text("""
            INSERT INTO sec_disclosures
                (stock_id, filing_date, accession_number, cik, tickers,
                 primary_category, secondary_category, tertiary_category, supporting_text)
            VALUES (:sid, :fd, :acc, :cik, :tk, :pc, :sc, :tc, :st)
            ON CONFLICT (stock_id, accession_number, primary_category,
                         secondary_category, tertiary_category)
            DO NOTHING
        """),
        batch,
    )


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start = os.getenv("ALT_START_DATE", "2024-01-01")
    end = os.getenv("ALT_END_DATE", "2026-07-01")
    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT id, symbol FROM stocks ORDER BY id LIMIT :n"), {"n": max_stocks}
        ).all()
        sym2id = {sym.upper(): sid for sid, sym in rows}
        log.info("sweeping 8-K disclosures %s..%s, routing to %d universe symbols", start, end, len(sym2id))

        seen = matched = flushed = 0
        batch = []
        try:
            for rec in polygon_paginate(
                "/stocks/filings/8-K/vX/disclosures",
                {"filing_date.gte": start, "filing_date.lt": end, "limit": 1000},
                max_pages=20000,
            ):
                seen += 1
                tks = rec.get("tickers") or []
                hits = [sym2id[t] for t in tks if t in sym2id]
                if not hits:
                    continue
                matched += 1
                fd = rec.get("filing_date")
                acc = rec.get("accession_number")
                cik = rec.get("cik")
                pc = rec.get("primary_category")
                sc = rec.get("secondary_category")
                tc = rec.get("tertiary_category")
                st = rec.get("supporting_text")
                for sid in hits:
                    batch.append({
                        "sid": sid, "fd": fd, "acc": acc, "cik": cik,
                        "tk": tks, "pc": pc, "sc": sc, "tc": tc, "st": st,
                    })
                if len(batch) >= 2000:
                    _flush(db, batch)
                    flushed += len(batch)
                    db.commit()
                    batch = []
                    log.info("  seen=%d matched=%d rows inserted~=%d", seen, matched, flushed)
        except NotAuthorized as e:
            log.error("NOT AUTHORIZED — %s", e)
            return

        if batch:
            _flush(db, batch)
            flushed += len(batch)
        db.commit()
        n = db.execute(text("SELECT count(*) FROM sec_disclosures")).scalar()
        log.info("done: swept=%d disclosure records, matched=%d, sec_disclosures rows=%s",
                 seen, matched, n)
    finally:
        db.close()


if __name__ == "__main__":
    main()
