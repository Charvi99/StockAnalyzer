# BU7 — Remaining API Routes (audit report)

Verified 2026-07-20 against `app/api/routes/*.py` (14 files; `analysis.py` covered in
BU1, `risk_management.py` in BU5 — excluded here). Tag legend: ✅ confirmed · ❓ needs more proof · ⛔ false positive.

## Headline
The route layer is **cleaner than expected** — no raw-SQL injection, no bare `except:`,
and two routes (`news.py`, `dividend_split_signals.py`) demonstrate correct bounded
pagination. The real issue is **inconsistent pagination**: several list endpoints return
`.all()` with no limit or use un-validated `limit` params, which is a DoS/OOM vector on
tables that grow daily. `ml.py` is **partially stubbed**, not fully. No code changed.

## Findings

### A1 ✅ CONFIRMED (DoS/OOM) — unbounded / un-validated pagination on growing tables
PostgreSQL + SQLAlchemy will happily materialize whatever the client asks for. Several
endpoints don't cap it:
- `stocks.py:13-14` — `skip: int = 0, limit: int = 1000` with **no `Query(ge=, le=)`**. A
  client can request `?limit=10000000` and force the API to load/serialize the whole table.
- `patterns.py:160` `get_patterns` → `.all()` **no limit** (all candlestick patterns for a stock).
- `patterns.py:256` `get_pattern_stats` and `:306` `export_training_data` → `query.all()` (loads every row into memory).
- `chart_patterns.py:186` `get_chart_patterns` → `.all()` **no limit**; `:284` stats → `.all()`.
- `sentiment.py:254,311` — bare `limit: int = 10/20`, no `Query(ge=, le=)` caps (small defaults soften this).

**Contrast (the in-repo correct pattern):** `news.py:188` — `limit: int = Query(10, ge=1, le=100)`
and `offset: int = Query(0, ge=0)`. `dividend_split_signals.py:224,265` use `.limit(limit)`.

**Fix (cheap, uniform):** every list endpoint should use `Query(default, ge=1, le=<cap>)` and
chain `.limit(...)`. For the pattern tables specifically (which accumulate forever and are
already unindexed — S2), an unbounded `.all()` is both an OOM and a slow-scan risk. This is
the highest-leverage BU7 fix.

### A2 ✅ CONFIRMED (refines D2) — `ml.py` is partially stubbed, not fully
`ml.py` returns HTTP 501 for `train_model` (`:46`) and `predict_with_ml` (`:115`), but
`list_available_models` (`:189`) and `delete_model` (`:210`) are implemented and functional.
So D2 ("remove or implement the ml.py stub") is more precisely: **train + predict are the
501 stubs**; the model-management endpoints work. The mounted `/ml` router isn't dead — it
serves list/delete. Decision: either wire train/predict to the `ml-training` TabNet stack
(D1 lineage) or return 501 consistently with a clear "not implemented" body.

### A3 ✅ CONFIRMED (security, cross-cutting → X1) — write endpoints are unauthenticated
`stocks.py` POST/PATCH/DELETE, `ml.py` delete/train, pattern endpoints — none require auth.
Combined with the CORS `allow_origins=["*"] + allow_credentials=True` already found at
`main.py:45`, any origin can create/delete stocks and trigger model ops. This is the X1
(config/deps/security) unit's lead item; noted here for completeness, not double-counted.

### A4 ✅ CONFIRMED (minor, design) — hard delete cascades all history
`stocks.py:104` `delete_stock` does `db.delete(stock)`, which (via S6's correct cascades)
deletes **all** prices, patterns, predictions, news for that stock. For a data/trading app a
soft delete (`is_tracked=False`, already a column) is usually preferable to irreversible
history loss. No bug — the cascade works as designed — but `DELETE /stocks/{id}` is
destructive and undocumented as such. Note.

## Positives (verified)
- ⛔ **No raw-SQL injection** — the only `text()/execute()` in routes is `health.py:18`
  `SELECT 1`. All other queries use the ORM.
- ⛔ **No bare `except:`** in any route file (all use typed `except Exception`).
- `news.py` and `dividend_split_signals.py` show the correct pagination pattern to mirror.
- `stocks.py` consistently uppercases symbols on create/lookup (no case-collision duplicates).

## Status
- **Audit-only — no route code changed.**
- **Highest leverage:** A1 (uniform bounded pagination — cheap, prevents OOM on the
  growing pattern tables that are also unindexed per S2).
- Test: `python3 backend/tests/test_bu7_routes.py` → demonstrates the bare-`limit` DoS
  vector vs the `Query(le=)` guard, and greps the route sources to lock in the known
  unbounded `.all()` endpoints (fails if someone adds limits, so the doc stays accurate).

## Open decisions added (feed into AUDIT_PLAN §5)
- **D24:** Add `Query(ge=, le=)` caps + `.limit()` to all list endpoints (A1) — recommended,
  low-risk.
- **D2 (refined):** wire `ml.py` train/predict to the TabNet stack, or return 501 consistently (A2).
- **D25:** Soft-delete stocks instead of cascade hard-delete (A4).
- A3 folds into X1 (auth + CORS).
