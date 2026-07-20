# BU6 — DB Layer & Schema (audit report)

Verified 2026-07-20 against `app/models/*.py` (stock.py 252 LOC + 6 others),
`alembic/versions/` (17 migrations), `database/init.sql`.
Tag legend: ✅ confirmed · ❓ needs more proof · ⛔ false positive (corrected).

## Headline
This unit **resolves the systemic TZ blocker.** Every timestamp column in the schema is
`TIMESTAMP WITHOUT TIME ZONE` (naive) — that is the structural reason B3/R6/F2 exist and
why the code must defensively cast everywhere. The schema is otherwise sound (cascades,
DECIMAL money types, hypertable), but **foreign-key columns on the hot pattern tables are
unindexed** and **`init.sql` has drifted from alembic**. No code changed.

## Findings

### S1 ✅ CONFIRMED (correctness, systemic) — ALL timestamps are `TIMESTAMP WITHOUT TIME ZONE`
Grepped every model: `stock.py`, `news.py`, `dividend.py`, `stock_split.py`,
`short_interest.py`, `timeframe.py` — every `created_at`, `updated_at`, `last_*`,
`timestamp`, `published_utc`, `start_date`/`end_date`, `evaluated_at`, `calculated_at` is
`Column(TIMESTAMP, ...)`. **Zero** `TIMESTAMPTZ` / `timezone=True`. `server_default=func.now()`
therefore writes naive server-local time, and Python reads tz-naive `datetime`s back.

This is the **root cause of B3/R6/F2**: because the DB is naive, the fetcher strips tz on
write (`fetcher_tasks.py:156`) but assigns tz-aware on `last_fetch_at` (`:291`), and readers
guess (`:80-82`). **Resolution (recommendation):** migrate timestamp columns to `TIMESTAMPTZ`
in a new alembic revision, then drop the `:155-156` strip and the `:80-82` defensive cast and
use `datetime.now(timezone.utc)` uniformly. This single change closes B3, R6, and F2 together.
Alternative: keep naive but enforce `datetime.utcnow()` everywhere (lower-effort, less clean).

### S2 ✅ CONFIRMED (perf) — unindexed FK columns + zero composite indexes
`grep "Index(" alembic/versions/*.py` returns **nothing** — no explicit composite indexes
anywhere; only PKs and per-column `index=True`. PostgreSQL does **not** auto-index FKs, and
these hot FK columns have no `index=True`:
- `ChartPattern.stock_id` (`stock.py:220`), `CandlestickPattern.stock_id` (`:196`)
- `SentimentScore.stock_id` (`:171`), `Prediction.stock_id` (`:98`)
- `PredictionPerformance.prediction_id` (`:121`)

`recommendation_engine` and `order_calculator` query `ChartPattern`/`CandlestickPattern` by
`stock_id` (+ a `created_at` range that is *also* unindexed) on every recommendation →
**sequential scans** on tables that grow daily. Compounds F1 (N+1 upsert) and B5 (copy churn)
into a triple-perf hit on the hot path. Fix: add `index=True` to the FK columns and a
composite `(stock_id, created_at)` on the pattern tables. (Only `TechnicalIndicator.stock_id`
and `Prediction.id` are indexed today.)

### S3 ✅ CONFIRMED (minor) — DECIMAL prices cast to float in services
Prices are correctly `DECIMAL(12,4)` in the schema, but every consumer casts to float
(`float(p.close)` in recommendation_engine, order_calculator, market_regime, risk code).
DECIMAL was presumably chosen for money precision, then discarded at the read boundary.
For a swing-trading app the rounding error is negligible, but the intent is lost. Note, don't
necessarily change.

### S4 ✅ CONFIRMED (perf/config) — hypertable not repartitioned for multi-timeframe
`c45f1698d64d_initial_migration.py:63` creates the hypertable on `stock_prices.timestamp`.
The later `20251029_add_multi_timeframe.py` added `timeframe` to the composite PK but
**explicitly could not repartition** the existing hypertable (`:95-100`, RAISE NOTICE
"Partitioning not modified"). So multi-timeframe rows share one time-partitioning scheme —
correct, but queries filtering `(stock_id, timeframe, timestamp)` may not hit the optimal
chunk layout. Documented in-code; flag for a planned repartition if multi-TF queries dominate.

### S5 ✅ CONFIRMED (hygiene) — `database/init.sql` has drifted from alembic
`init.sql` (165 LOC) defines **8 tables**; alembic (17 migrations) defines the full set
(stocks, stock_prices, predictions, prediction_performance, technical_indicators,
sentiment_scores, candlestick_patterns, chart_patterns, news, dividends, stock_splits,
short_interest, alternative_data, …). `init.sql` is a stale bootstrap — alembic is canonical
(already noted in repo memory). Risk: a fresh env bootstrapped from `init.sql` is missing
tables/columns. **Decision (D20):** delete `init.sql` (or regenerate it from a `pg_dump` of
the current schema) so there's one schema source.

### S6 ✅ CONFIRMED (positive) — cascade deletes are correct
Every FK is `ondelete="CASCADE"` and every parent relationship is `cascade="all, delete-orphan"`
(`stock.py:54-63`). Deleting a Stock cleans its prices/patterns/news/etc. No orphan risk.
CheckConstraints on enums (`priority`, `recommendation`, `pattern_type`, `signal`, `trend`,
`timeframe`) are present and match code. Good defensive schema.

### S7 ✅ CONFIRMED (minor) — dual key on StockPrice
`stock_prices` has a composite PK `(stock_id, timeframe, timestamp)` **and** a surrogate
`id` from `stock_prices_id_seq` (`:74`). Unusual to carry both; the `id` exists for ORM
convenience but doubles the index footprint on the hypertable. Note, not a defect.

## Status
- **Audit-only — no app/migration code changed.**
- **Highest leverage:** S1 (closes B3/R6/F2 in one migration) and S2 (indexes on the hot
  pattern tables — cheap, big win alongside F1/B5).
- Test: `python3 backend/tests/test_bu6_schema.py` → imports the models and asserts (a) every
  TIMESTAMP column is naive (locks in the S1 fact so a future `TIMESTAMPTZ` migration is
  intentional and visible), and (b) reports which FK columns currently lack an index (S2).

## Open decisions added (feed into AUDIT_PLAN §5)
- **D20:** Migrate timestamp columns to `TIMESTAMPTZ` (closes B3/R6/F2/S1) — recommended.
- **D21:** Add FK indexes + `(stock_id, created_at)` composite on pattern tables (S2).
- **D22:** Delete or regenerate `database/init.sql` (S5).
- **D23:** Planned hypertable repartition for multi-timeframe (S4).
