#!/usr/bin/env python3
"""
Backfill FINRA short-interest (2-week cadence) + short-volume (daily).

Both endpoints are ticker-filterable (verified by probe):
  GET /stocks/v1/short-interest?ticker=<SYM>  -> {settlement_date, short_interest,
                                                  avg_daily_volume, days_to_cover}
  GET /stocks/v1/short-volume?ticker=<SYM>    -> {date, total_volume, short_volume,
                                                  short_volume_ratio, exempt_volume, ...}

Writes:
  short_interest (existing): settlement_date, short_interest, avg_volume_30d,
                             days_to_cover
  short_volume (new):        date, total_volume, short_volume, short_volume_ratio,
                             exempt_volume

Env:
  ALT_MAX_STOCKS   first N stocks by id (default 100)
  ALT_START_DATE   backfill start 'YYYY-MM-DD' (default 2023-06-01)
  POLYGON_DELAY    per-request floor seconds (default 0.15)

Run:  docker exec stock_analyzer_backend python /app/scripts/fetch_short_interest.py
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
log = logging.getLogger("fetch_short_interest")


def _backfill_short_interest(db, stock_id, symbol, start):
    n = 0
    for r in polygon_paginate(
        "/stocks/v1/short-interest",
        {"ticker": symbol, "settlement_date.gte": start, "limit": 1000},
        max_pages=20,
    ):
        sd = r.get("settlement_date")
        if not sd or sd < start:
            continue
        db.execute(
            text("""
                INSERT INTO short_interest
                    (stock_id, settlement_date, short_interest, avg_volume_30d, days_to_cover)
                VALUES (:sid, :sd, :si, :av, :dtc)
                ON CONFLICT (stock_id, settlement_date) DO UPDATE
                SET short_interest = EXCLUDED.short_interest,
                    avg_volume_30d = EXCLUDED.avg_volume_30d,
                    days_to_cover = EXCLUDED.days_to_cover
            """),
            {
                "sid": stock_id, "sd": sd, "si": r.get("short_interest"),
                "av": r.get("avg_daily_volume"), "dtc": r.get("days_to_cover"),
            },
        )
        n += 1
    return n


def _backfill_short_volume(db, stock_id, symbol, start):
    n = 0
    for r in polygon_paginate(
        "/stocks/v1/short-volume",
        {"ticker": symbol, "date.gte": start, "limit": 1000},
        max_pages=40,
    ):
        d = r.get("date")
        if not d or d < start:
            continue
        db.execute(
            text("""
                INSERT INTO short_volume
                    (stock_id, date, total_volume, short_volume, short_volume_ratio, exempt_volume)
                VALUES (:sid, :d, :tv, :sv, :svr, :ev)
                ON CONFLICT (stock_id, date) DO UPDATE
                SET total_volume = EXCLUDED.total_volume,
                    short_volume = EXCLUDED.short_volume,
                    short_volume_ratio = EXCLUDED.short_volume_ratio,
                    exempt_volume = EXCLUDED.exempt_volume
            """),
            {
                "sid": stock_id, "d": d, "tv": r.get("total_volume"),
                "sv": r.get("short_volume"), "svr": r.get("short_volume_ratio"),
                "ev": r.get("exempt_volume"),
            },
        )
        n += 1
    return n


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start = os.getenv("ALT_START_DATE", "2023-06-01")
    db = SessionLocal()
    try:
        stocks = db.execute(
            text("SELECT id, symbol FROM stocks ORDER BY id LIMIT :n"), {"n": max_stocks}
        ).all()
        log.info("backfilling short-interest+volume for %d stocks from %s", len(stocks), start)

        si_total = sv_total = errs = 0
        for i, (stock_id, symbol) in enumerate(stocks, 1):
            try:
                si_total += _backfill_short_interest(db, stock_id, symbol, start)
                sv_total += _backfill_short_volume(db, stock_id, symbol, start)
                if i % 10 == 0:
                    db.commit()
                    log.info("  %d/%d stocks (si=%d sv=%d)", i, len(stocks), si_total, sv_total)
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
        log.info("done: short_interest +=%d  short_volume +=%d  errs=%d", si_total, sv_total, errs)
        a = db.execute(text("SELECT count(*) FROM short_interest")).scalar()
        b = db.execute(text("SELECT count(*) FROM short_volume")).scalar()
        log.info("table totals -> short_interest=%s short_volume=%s", a, b)
    finally:
        db.close()


if __name__ == "__main__":
    main()
