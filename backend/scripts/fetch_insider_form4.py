#!/usr/bin/env python3
"""
Backfill SEC Form-4 insider transactions via Polygon (global sweep).

The endpoint IGNORES ticker filters (probe-confirmed) and pages GLOBALLY by
filing_date, so we sweep the whole market in the window and ROUTE each record
to our universe by matching its `tickers` list to our stock symbols — same
pattern as fetch_8k_disclosures.py. This avoids EDGAR SGML/XML parsing and CIK
mapping: Polygon returns fully-parsed transaction fields.

  GET /stocks/filings/vX/form-4?filing_date.gte=...&filing_date.lt=...
    -> per-transaction records: {tickers, filing_date, transaction_date,
       transaction_code, transaction_shares, transaction_price_per_share,
       transaction_value, transaction_acquired_disposed, owner_name, owner_cik,
       is_director, is_officer, is_ten_percent_owner, accession_number, ...}

transaction_code mapping -> transaction_type (matches the insider_trades CHECK):
  P -> BUY (open-market purchase)        S -> SELL (open-market sale)
  M -> OPTION_EXERCISE                   A/other -> OTHER
filing_date is the PUBLIC date (Form-4 filed within 2 business days).

Env:
  ALT_MAX_STOCKS   universe size (first N by id; default 100)
  ALT_START_DATE   sweep start 'YYYY-MM-DD' (default 2021-07-26)
  ALT_END_DATE     sweep end   'YYYY-MM-DD' (default 2026-07-25)
  POLYGON_DELAY    per-request floor seconds (default 0.15)

Run:  docker exec stock_analyzer_backend python /app/scripts/fetch_insider_form4.py
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
log = logging.getLogger("fetch_insider_form4")

_CODE_MAP = {"P": "BUY", "S": "SELL", "M": "OPTION_EXERCISE"}


def _flush(db, batch):
    if not batch:
        return
    db.execute(
        text("""
            INSERT INTO insider_trades
                (stock_id, insider_name, insider_title, owner_cik, is_director,
                 is_officer, is_ten_percent_owner, transaction_type, transaction_code,
                 shares, price, total_value, trade_date, filing_date, accession_number)
            VALUES (:sid, :name, NULL, :ocik, :dir, :off, :ten, :ttype, :tcode,
                    :shares, :price, :tval, :td, :fd, :acc)
            ON CONFLICT (stock_id, accession_number, owner_cik, trade_date, transaction_code)
            DO NOTHING
        """),
        batch,
    )


def main():
    max_stocks = int(os.getenv("ALT_MAX_STOCKS", "100"))
    start = os.getenv("ALT_START_DATE", "2021-07-26")
    end = os.getenv("ALT_END_DATE", "2026-07-25")
    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT id, symbol FROM stocks ORDER BY id LIMIT :n"), {"n": max_stocks}
        ).all()
        sym2id = {sym.upper(): sid for sid, sym in rows}
        log.info("sweeping Form-4 %s..%s, routing to %d universe symbols", start, end, len(sym2id))

        seen = matched = flushed = 0
        batch = []
        try:
            for rec in polygon_paginate(
                "/stocks/filings/vX/form-4",
                {"filing_date.gte": start, "filing_date.lt": end, "limit": 1000},
                max_pages=40000,
            ):
                seen += 1
                tks = rec.get("tickers") or []
                hits = [sym2id[t] for t in tks if t in sym2id]
                if not hits:
                    continue
                code = rec.get("transaction_code") or ""
                ttype = _CODE_MAP.get(code, "OTHER")
                td = rec.get("transaction_date") or rec.get("period_of_report")
                fd = rec.get("filing_date")
                if not td or not fd:
                    continue
                shares = rec.get("transaction_shares")
                if shares is None:
                    continue  # non-transaction row (e.g. holding-only); skip
                common = {
                    "name": (rec.get("owner_name") or "")[:255],
                    "ocik": rec.get("owner_cik"),
                    "dir": rec.get("is_director"),
                    "off": rec.get("is_officer"),
                    "ten": rec.get("is_ten_percent_owner"),
                    "ttype": ttype,
                    "tcode": code,
                    "shares": shares,
                    "price": rec.get("transaction_price_per_share"),
                    "tval": rec.get("transaction_value"),
                    "td": td,
                    "fd": fd,
                    "acc": rec.get("accession_number"),
                }
                for sid in hits:
                    batch.append({"sid": sid, **common})
                matched += 1
                if len(batch) >= 2000:
                    _flush(db, batch)
                    flushed += len(batch)
                    db.commit()
                    batch = []
                    log.info("  seen=%d matched-txns=%d inserted~=%d", seen, matched, flushed)
        except NotAuthorized as e:
            log.error("NOT AUTHORIZED — %s", e)
            return

        if batch:
            _flush(db, batch)
            flushed += len(batch)
        db.commit()
        n = db.execute(text("SELECT count(*) FROM insider_trades")).scalar()
        log.info("done: swept=%d form-4 records, matched=%d, insider_trades rows=%s",
                 seen, matched, n)
    finally:
        db.close()


if __name__ == "__main__":
    main()
