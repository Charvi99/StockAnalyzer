#!/usr/bin/env python3
"""
Backfill SEC standardized 10-K risk-factor disclosures.

Endpoint (ticker-filterable, verified by probe):
  GET /stocks/filings/vX/risk-factors?ticker=<SYM>
    -> {cik, ticker, filing_date, primary_category, secondary_category,
        tertiary_category, supporting_text}

These are annual (per 10-K), so volume per stock is small. Writes `risk_factors`
with ON CONFLICT upsert. The "newly added vs prior year" diff is computed at
attribution time (causally, filing_date <= T), not here.

Env:
  ALT_MAX_STOCKS   first N stocks by id (default 100)
  ALT_START_DATE   backfill start 'YYYY-MM-DD' (default 2020-01-01; annual data)
  POLYGON_DELAY    per-request floor seconds (default 0.15)

Run:  docker exec stock_analyzer_backend python /app/scripts/fetch_risk_factors.py
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
log = logging.getLogger("fetch_risk_factors")


def _backfill(db, stock_id, symbol, start):
    n = 0
    for r in polygon_paginate(
        "/stocks/filings/vX/risk-factors",
        {"ticker": symbol, "filing_date.gte": start, "limit": 100},
        max_pages=10,
    ):
        fd = r.get("filing_date")
        if not fd or fd < start:
            continue
        db.execute(
            text("""
                INSERT INTO risk_factors
                    (stock_id, filing_date, cik, primary_category,
                     secondary_category, tertiary_category, supporting_text)
                VALUES (:sid, :fd, :cik, :pc, :sc, :tc, :st)
                ON CONFLICT (stock_id, filing_date, primary_category,
                             secondary_category, tertiary_category)
                DO UPDATE SET supporting_text = EXCLUDED.supporting_text,
                              cik = EXCLUDED.cik
            """),
            {
                "sid": stock_id, "fd": fd, "cik": r.get("cik"),
                "pc": r.get("primary_category"), "sc": r.get("secondary_category"),
                "tc": r.get("tertiary_category"), "st": r.get("supporting_text"),
            },
        )
        n += 1
    return n


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start = os.getenv("ALT_START_DATE", "2020-01-01")
    db = SessionLocal()
    try:
        stocks = db.execute(
            text("SELECT id, symbol FROM stocks ORDER BY id LIMIT :n"), {"n": max_stocks}
        ).all()
        log.info("backfilling risk-factors for %d stocks from %s", len(stocks), start)

        total = errs = 0
        for i, (stock_id, symbol) in enumerate(stocks, 1):
            try:
                total += _backfill(db, stock_id, symbol, start)
                if i % 10 == 0:
                    db.commit()
                    log.info("  %d/%d stocks (rows=%d)", i, len(stocks), total)
            except NotAuthorized as e:
                log.error("NOT AUTHORIZED (%s) — %s", symbol, e)
                errs += 1
                if errs >= 3:
                    log.error("repeated 403; aborting")
                    break
            except Exception as e:
                log.warning("%s: %s", symbol, e)
                errs += 1
        db.commit()
        log.info("done: risk_factors +=%d errs=%d", total, errs)
        n = db.execute(text("SELECT count(*) FROM risk_factors")).scalar()
        log.info("risk_factors total rows: %s", n)
    finally:
        db.close()


if __name__ == "__main__":
    main()
