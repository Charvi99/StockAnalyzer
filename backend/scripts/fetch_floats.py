#!/usr/bin/env python3
"""
Backfill free-float per stock (normalization input for insider & short signals).

Endpoint: GET /stocks/vX/float?ticker=<SYMBOL>  (ticker-filterable; returns the
latest free-float snapshot: {ticker, free_float, effective_date, free_float_percent}).

Float is slow-moving, so we fetch the latest snapshot per stock (one call each).
Writes to `stock_floats` (stock_id, effective_date, free_float, free_float_percent)
with ON CONFLICT upsert.

Env:
  ALT_MAX_STOCKS  first N stocks by id (default 100; matches the backtest universe)
  POLYGON_DELAY   per-request floor seconds (default 0.15)

Run:  docker exec stock_analyzer_backend python /app/scripts/fetch_floats.py
"""
from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, "/backend")

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from polygon_client import polygon_get, NotAuthorized  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fetch_floats")


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    db = SessionLocal()
    try:
        stocks = db.execute(
            text("SELECT id, symbol FROM stocks ORDER BY id LIMIT :n"),
            {"n": max_stocks},
        ).all()
        log.info("fetching float for %d stocks", len(stocks))

        ok = miss = err = 0
        for stock_id, symbol in stocks:
            try:
                j = polygon_get("/stocks/vX/float", {"ticker": symbol})
                res = j.get("results") or []
                if not res:
                    miss += 1
                    continue
                r = res[0]
                eff = r.get("effective_date")
                if not eff:
                    miss += 1
                    continue
                db.execute(
                    text("""
                        INSERT INTO stock_floats
                            (stock_id, effective_date, free_float, free_float_percent)
                        VALUES (:sid, :eff, :ff, :ffp)
                        ON CONFLICT (stock_id, effective_date) DO UPDATE
                        SET free_float = EXCLUDED.free_float,
                            free_float_percent = EXCLUDED.free_float_percent
                    """),
                    {
                        "sid": stock_id,
                        "eff": eff,
                        "ff": r.get("free_float"),
                        "ffp": r.get("free_float_percent"),
                    },
                )
                ok += 1
                if ok % 25 == 0:
                    db.commit()
                    log.info("  %d ok", ok)
            except NotAuthorized as e:
                log.error("NOT AUTHORIZED on float (%s) — %s", symbol, e)
                err += 1
                if err >= 3:
                    log.error("repeated 403; aborting")
                    break
            except Exception as e:
                log.warning("%s: %s", symbol, e)
                err += 1
        db.commit()
        log.info("done: ok=%d miss=%d err=%d", ok, miss, err)

        n = db.execute(text("SELECT count(*) FROM stock_floats")).scalar()
        log.info("stock_floats rows: %s", n)
    finally:
        db.close()


if __name__ == "__main__":
    main()
