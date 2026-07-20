# Audit Summary — Capstone

**Date:** 2026-07-20 · **Branch:** `chore/audit-restructure` (11 commits, reversible, unmerged)
**Scope:** swing-trading app — **backend (BU1–BU7) + frontend (FU) + cross-cutting (X1–2) all
complete.** This is a finished audit; the deliverable below is the starting point for the
stabilization + 24/7 paper-trading work. **Goal of this work:** establish a solid starting point for future
development — stabilize/improve what exists, then resume feature work and put the system
into **24/7 paper-trading** (virtual money, weeks/months) to validate recommendations.

> Read this first, then the per-unit reports in `docs/audit/` for evidence.

---

## 1. What the audit produced

| Deliverable | Where |
|---|---|
| 3 safe fixes applied + tested | B1 (restored RSI/MACD/SMA scoring), B2 (ADX div guard), R1/R2 (risk div-zero guards) |
| 7 unit reports (BU1–BU7) | `docs/audit/BU*_*.md` |
| 7 characterization test files | `backend/tests/test_bu*_*.py` — all green, run with `python3 …` (no DB) |
| Canonical architecture/plan | `docs/ARCHITECTURE.md`, `docs/AUDIT_PLAN.md`, `docs/RESTRUCTURE_CHANGELOG.md` |
| Dead code archived, artifacts untracked | `archive/`, `.gitignore` |
| ~35 findings, 6 false positives corrected | per reports |
| 25 parked decisions | D1–D25 (see §9) |

## 2. Unit results at a glance

| Unit | Commit | Headline |
|---|---|---|
| BU1 brain | f3ca19f | **B1/B2 fixed** · B3/B4 documented |
| BU2 indicators | ddb58d1 | look-ahead = **false positives** · B5 36× copy churn · B6 RSI parity |
| BU3 patterns | 448377d | **over-filter bug P1** + strict R² 0.85 |
| BU4 ingestion | a9bd361 | **TZ root cause F2** · no global rate limiter F3 |
| BU5 risk/order | e56bd1c | **R1/R2 fixed** · two duplicate risk impls |
| BU6 DB/schema | 9ed254b | **all-TIMESTAMP-naive** · 5 unindexed FKs |
| BU7 routes | 597132b | unbounded pagination (9 sites) · ml.py partial stub |

## 3. Honest ratings

**Overall: a competent prototype that grew into a working system without refactoring
discipline.** ~6/10 production reliability, ~7.5/10 ambition/domain-knowledge.

- **Real strengths:** proper schema (DECIMAL money, cascades, CheckConstraints, TimescaleDB
  hypertable); correct FastAPI/SQLAlchemy-2.0/Celery usage; thoughtful domain logic
  (multi-timeframe, TCR regime, 35 indicators, ATR risk). Built by someone who knows trading.
- **Real weaknesses:** pervasive duplication; mixed tz conventions; accumulating dead code;
  hardcoded magic numbers; **no original test suite**; a few swallowed errors.

**Most impactful bug found: B1** — RSI/MACD/golden-cross silently contributed *nothing* to
~23% of the recommendation weight in the Celery path. The kind only an audit catches.

## 4. Coverage honesty — these are NOT all the bugs

The findings are a **biased sample**, not a complete set. Bias: backend hot path, static
patterns (div-zero, duplication, tz, unbounded queries), and things verifiable **without a
running DB/frontend**. **Under-covered:** frontend (in progress), security beyond CORS,
runtime/data-dependent logic, concurrency races, the ML training project, and load
performance. ~6 initial hypotheses were false positives → precision-when-verified is high,
recall is not 100%. Expect more bugs in the uncovered areas and in edge cases a running
system would expose.

## 5. Recurring themes (the real story)

1. **Duplication** — two rec engines (B4), two risk impls (R7), quiverquant v1/v2, dead
   `_calculate_levels` v1. Every fix applied twice; they will drift.
2. **TZ systemically broken** — naive `TIMESTAMP` schema + mixed aware/naive code (B3/R6/F2/S1).
3. **Missing defensive edges** — div-zero, unbounded inputs, no time limits.
4. **Hot-path perf triple-hit** — N+1 upsert (F1) + 36× copy churn (B5) + unindexed FKs (S2).
5. **Pandas-fallback divergence** — talib absent in dev → hand-written formulas run live;
   parity unverified in prod (B6).

## 6. Architecture

**Intent: sound. Execution: eroded.** Design ideas right (modular services, priority queues,
indicator cache, hypertable). Seams rotted: duplication is the dominant smell; layering
inversions (service→route import, R8); two schedulers (Celery Beat + APScheduler); two ML
lineages (live LSTM/GRU vs TabNet); cross-project Docker coupling (`PYTHONPATH=/backend`).

## 7. Fix roadmap (priority order — most reliability per effort)

1. **Collapse duplicates** — one source of truth each: rec engine, risk math, fetcher,
   scheduler, ML lineage. Highest leverage; makes every future fix single-site.
2. **`TIMESTAMPTZ` migration + TZ policy** — closes B3/R6/F2/S1 in one revision.
3. **Thin service layer** — lift recommendation logic out of the route (fixes inversion + B4).
4. **Config, not magic numbers** — thresholds, rate limits, queue sizes → env (also fixes the
   pattern over-filter tuning, your explicit concern).
5. **Defensive-edge sweep** — FK indexes, bounded pagination, global Polygon limiter, task
   time limits.
6. **Cultural:** real test suite + CI before the next feature.

## 8. The path to 24/7 paper-trading (the actual destination)

Before running unattended with virtual money for weeks/months, the system needs to be
**observable and self-recovering**, not just correct. Reliability gaps that currently block a
confident unattended run (drawn from the audit):

- **No global Polygon rate limiter (F3)** — ≥2 workers → ban. Must be a shared (Redis) limiter
  or pinned `--concurrency=1`.
- **No task time limits (F4)** — a stalled HTTP fetch hangs a worker forever under `acks_late`.
- **TZ inconsistency (S1/F2)** — can crash time-window comparisons mid-run.
- **Paper-trading ledger does not exist yet** — there is no table/service that records "virtual
  trades taken at entry X with stop Y / target Z on date D" and marks them to market over time.
  Without this you cannot measure outcome. **This is the #1 new build for the goal.**
- **No alerting/health surface** — if the fetcher silently stops or Polygon 401s, nothing
  surfaces it. The `health.py` `SELECT 1` is alive but not wired to alerts.
- **Recommendation determinism** — the two rec engines (B4) + pattern over-filtering (P1/P2)
  mean signals are not reproducible; for paper-trading you want one deterministic pipeline.

**Recommended sequencing toward the goal:**
1. Stabilization fixes from §7 (items 1–5) — the reliability floor.
2. Build the **paper-trading ledger** (entries, exits, mark-to-market, daily P&L rollup) —
   new feature, but it's the measuring instrument you need.
3. Wire **health checks + simple alerting** (dead-man style: "no fetch in 2h → notify").
4. Run **shadow paper-trading** (record signals + simulated fills, no real execution) for 2–4
   weeks, then evaluate hit-rate / R-multiple / drawdown.
5. Only then consider resuming new feature development.

## 9. Decision inventory (D1–D25, grouped)

- **Architecture/duplication:** D6 one-copy refactor · D9 consolidate risk · D10 lift rec core
  to service · D1 ML lineage · D2/D15 ml.py + candlestick · D5 APScheduler vs Beat.
- **Correctness/money:** D7 Wilder-RSI · D8 VWAP-on-daily · D11 direction-aware R:R · D12 P1
  pattern fix · D13 relax thresholds · D14 R² double-penalty.
- **Reliability/infra:** D16 TZ convention · D17 global rate limiter · D18 task time limits ·
  D19 bulk upsert · D23 hypertable repartition.
- **Schema/hygiene:** D20 TIMESTAMPTZ · D21 FK indexes · D22 drop init.sql.
- **API:** D24 bounded pagination · D25 soft-delete.

(Full detail per decision in each report's "Open decisions" section and `AUDIT_PLAN.md §5`.)
