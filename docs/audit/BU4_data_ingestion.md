# BU4 — Data Ingestion & Celery Tasks (audit report)

Verified 2026-07-20 against `app/celery_app.py`, `app/tasks/fetcher_tasks.py`
(1231 LOC, 12 tasks), `app/services/polygon_fetcher.py`,
`app/services/quiverquant_fetcher{,_v2}.py`, `app/services/scheduler.py`.
Tag legend: ✅ confirmed · ❓ needs more proof · ⛔ false positive (corrected).

## Headline
Data ingestion is **functional but fragile under scale/concurrency**. The single most
important finding (F2) is the **root cause of the systemic TZ bug** flagged as B3/R6 —
confirmed here, and it points to the fix direction (enforce naive-as-UTC everywhere, or
go fully tz-aware). Rate limiting is **not safe with more than one fetcher worker** (F3),
which is a Polygon-ban risk. No code changed (audit-only, per request).

## Findings

### F1 ✅ CONFIRMED (perf) — N+1 query upsert for price bars
`fetcher_tasks.py:158-187`: for **each** bar in the fetch result, the code issues
`db.query(StockPrice).filter(...).first()` to test existence, then updates or inserts.
A lookback fetch of N bars = N round-trips just for the existence check. Should be a
single `SELECT ... WHERE timestamp IN (...)` to pre-load, or a bulk upsert
(`ON CONFLICT ... DO UPDATE`). Compounds with the hourly cadence → steady DB load.

### F2 ✅ CONFIRMED (correctness, systemic) — TZ handling is inconsistent within fetcher_tasks (B3 root cause)
The file's own comment admits the design: *"database stores naive timestamps"* (`:155`).
But the code is not consistent with that intent:
- `:153` builds `bar_timestamp` **tz-aware** (`fromtimestamp(..., tz=timezone.utc)`).
- `:155-156` then **strips** tz: `bar_timestamp_naive = bar_timestamp.replace(tzinfo=None)`.
- `:179` stores the **naive** value.
- BUT `:291, 437, 573` assign `stock.last_fetch_at = datetime.now(timezone.utc)` — **tz-aware** — to a column.
- `:80-82` reads `last_timestamp` and, if naive, *assumes* UTC (`replace(tzinfo=timezone.utc)`).

So: bar timestamps are explicitly made naive; `last_fetch_at` is assigned aware; readers
guess. Comparing an aware vs naive datetime raises `TypeError` in Python. Meanwhile
Celery is configured `timezone='America/New_York'` (`celery_app.py:37`) and
`recommendation_engine.py` uses aware UTC. **This is the B3/R6 root cause** — the fix is
to pick ONE convention (recommend: store tz-aware `TIMESTAMPTZ` everywhere, drop the
`:155-156` strip and the `:80-82` guess) and enforce it. Blocked on confirming the actual
PG column types (`models/stock.py`) — same blocker as B3. **Highest-value BU4 finding.**

### F3 ✅ CONFIRMED (correctness/reliability) — no GLOBAL rate limiter (Polygon ban risk)
Polygon's 100 req/min is enforced by **three independent per-worker mechanisms**:
1. Celery `task_annotations` `fetch_stock_prices: rate_limit='100/m'` (`celery_app.py:68-70`) — **per worker**.
2. `time.sleep(1)` after each fetch in the task (`fetcher_tasks.py:331, 343, 475, 482`).
3. `PolygonFetcher.rate_limit_delay = 1` (`polygon_fetcher.py:35`) + `time.sleep` (`:416,467,518`).

None is global. `worker_prefetch_multiplier=1` (`:52`) only serializes within a single
worker. **With ≥2 fetcher workers, aggregate rate doubles/triples → Polygon 429s and
potential plan suspension.** The compounding also *over*-throttles a single worker
(100/m Celery floor + 1s sleep ≈ ≤60/min effective). Decision: a single shared limiter
(Redis token bucket) or mandate `--concurrency=1` on the fetcher queue.

### F4 ✅ CONFIRMED (reliability) — no task time limits
`celery_app.py` sets no `task_time_limit` / `task_soft_time_limit`. With `task_acks_late=True`
(`:56`), a fetch that hangs on a stalled HTTP connection holds the worker **indefinitely**
and is not redelivered until the process dies. Add per-task soft/hard time limits (e.g.
`soft_time_limit=120, time_limit=180` for fetches).

### F5 ✅ CONFIRMED (minor) — schedule pile-up at the top of the hour
At `:00` of 9, 12, 16, etc., multiple beat entries fire together: `check-market-status`
(pri 8), `fetch-high-priority-stocks` (pri 10), and news fetches. Different queues, so not
fatal, but they compete for the shared Polygon rate-limit budget (F3) and spike load.
Staggering market-status to `:02` would decouple it.

### F6 ✅ CONFIRMED (duplication) — quiverquant v1/v2
`quiverquant_fetcher.py` (421 LOC) and `quiverquant_fetcher_v2.py` (352 LOC) both present.
Open decision D3 (archive v1 once v2 confirmed sole user). Unchanged.

### F7 ✅ CONFIRMED (minor) — `print()` instead of `logger` in Celery signal handlers
`celery_app.py:222,227,232,237` use `print()` for task start/success/failure/retry. In
production these bypass structured logging and log levels. Trivial swap to `logger`.

### F8 ✅ CONFIRMED (architecture) — two schedulers (APScheduler + Celery Beat), different roles
`app/services/scheduler.py` (`PredictionEvaluationScheduler`) is started in-process by
`main.py:20` (`init_scheduler`) via APScheduler `CronTrigger`. Celery Beat handles data
fetching. They are **not** double-firing the same task, but:
- APScheduler runs **inside the API process** → with `uvicorn --workers N`, the prediction-
  evaluation job fires **N times** (no distributed lock) unless guarded.
- It couples ML evaluation to the web tier (web restart interrupts it).
Decision (reuse D5): move prediction evaluation to a Celery Beat task for consistency and
single-execution guarantee, or add a Redis-based leader-election lock to APScheduler.

## Status
- **Audit-only — no app code changed** (per request; fixes deferred).
- **Highest leverage:** F2 (unblocks the systemic TZ fix B3/R6) and F3 (Polygon ban risk).
- Test: `python3 backend/tests/test_bu4_ingestion.py` → characterizes the tz-strip
  behavior (proving the naive-as-UTC storage pattern that makes F2 a defect) and the
  rate-limit math.

## Open decisions added (feed into AUDIT_PLAN §5)
- **D16:** Pick one TZ convention (recommend tz-aware everywhere) and enforce — fixes F2/B3/R6.
- **D17:** Add a global Polygon rate limiter (Redis token bucket) or pin fetcher
  `--concurrency=1` — fixes F3.
- **D18:** Add Celery `soft_time_limit`/`time_limit` to fetch tasks — F4.
- **D19:** Bulk-upsert price bars (kill the N+1) — F1.
- Reuse **D5** (APScheduler vs Celery Beat) for F8.
