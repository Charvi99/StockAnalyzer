# StockAnalyzer — Ultimate Audit Plan (canonical)

> Living document. Created 2026-07-20. Read alongside `ARCHITECTURE.md`.
> Goal: a structured, unit-by-unit review of the swing-trading app focused on
> **performance, bugs, implementation correctness, and optimization**.

## 0. Principles
- **Verify, don't trust.** Every finding must be confirmed against code (cite `file:line`).
  Suspected bugs are tagged `CONFIRMED` (reproduced/obvious) or `SUSPECTED` (needs proof).
- **One unit per session.** Units are sized so a focused review fits one working session,
  with a written report and a triaged fix list at the end.
- **Fixes are separate from findings.** First document, then fix in priority order — never
  edit-while-reviewing (it hides regressions).
- **Every fix ships with a test.** The backend has only ~14 test files for ~28k LOC; the
  audit must grow the test net, not just patch code.

## 1. Phases
| Phase | Goal | Status |
|---|---|---|
| **0 — Restructure & cleanup** | Remove dead code, untrack artifacts, reconcile docs/schema | 🟡 in progress (see `RESTRUCTURE_CHANGELOG.md`) |
| **1 — Bug hunt** | Correctness: div-by-zero, look-ahead bias, TZ/DST, swallowed errors | planned |
| **2 — Performance** | Cache integration, Polars consistency, bulk upserts, frontend virtualization | planned |
| **3 — Implementation quality** | Refactor monster files, dedup, types, tests | planned |

Phase 0 is intentionally done first so reviewers don't chase dead code.

## 2. Review-unit decomposition

### Backend
| Unit | Files (LOC) | Focus | Risk |
|---|---|---|---|
| **BU1 — Analysis brain** | `api/routes/analysis.py` (1591), `recommendation_engine`, `market_regime`, `analysis_completeness` | request flow, weighted scoring, cache hit/miss, weekly-trend override | 🔴 BUY/SELL correctness |
| **BU2 — Indicator engine** | `services/technical_indicators.py` (2983) | math correctness, NaN/div-zero, TA-Lib vs pandas parity, look-ahead | 🔴 propagates everywhere |
| **BU3 — Pattern detection** | `chart_patterns` (2307), `candlestick_patterns` (1379), `multi_timeframe_patterns`, `volume_analyzer` | detection correctness, O(n²) scans, false positives | 🟠 |
| **BU4 — Data ingestion & tasks** | `polygon_fetcher`, `sec_edgar_fetcher`, `quiverquant_fetcher_v2`, `tasks/*`, `celery_app`, `market_hours` | rate limits, retries, idempotency, TZ, bulk writes | 🟠 freshness/races |
| **BU5 — Risk & order calc** | `order_calculator` (1122), `risk_management`, `utils/risk_utils` | entry/stop/target math, position sizing | 🔴 real-money math |
| **BU6 — DB layer & schema** | `models/*`, `alembic/versions`, `db/database.py`, `timeframe_service/aggregator` | schema drift vs `init.sql`, indexes, hypertable, migrations | 🟡 |
| **BU7 — Remaining API** | `stocks`, `prices`, `news`, `sentiment`, `dividend_split_signals`, `strategies`, `ml_predictions`, `health` | sync-in-async, pagination, payloads | 🟡 |

### Frontend
| Unit | Files (LOC) | Focus |
|---|---|---|
| **FU1 — Data & dashboard** | `services/api.js` (372), `StockList.jsx` (1297), `App.jsx` | polling/abort, chunk loading, state, no virtualization |
| **FU2 — Visualization** | `ChartPatterns.jsx` (2064), `TechnicalAnalysis.jsx` (1440), `StockChart.jsx` (840), `CandlestickPatterns.jsx` | chart re-renders, memoization, filter cost |
| **FU3 — Supporting** | `StockCard`, `OrderCalculator`, `PortfolioHeatMonitor`, `SentimentAnalysis`, `MarketRegime`, modals | prop drilling, re-renders |

### Cross-cutting
| Unit | Scope |
|---|---|
| **X1 — Config/deps/security** | `requirements.txt` (TF+torch bloat), `.env`, Dockerfiles, CORS (`main.py:45`), secrets |
| **X2 — Repo hygiene** | finish archive, `.gitignore`, reconcile ML dirs/docs (this phase 0) |

**Recommended order:** BU1 → BU2 → BU5 → BU3 → BU4 → BU6 → BU7 → FU1 → FU2 → FU3 → X1.
(BU1+BU2 first per the agreed priority; BU5 next because it's real-money math.)

## 3. Findings register (verified, top items)

Severity: 🔴 critical · 🟠 high · 🟡 medium. Tag: ✅ confirmed · ❓ suspect.

| # | Sev | Tag | Finding | Location | Unit | Phase |
|---|---|---|---|---|---|---|
| 1 | 🔴 | ✅ | CORS `allow_origins=["*"]` + `allow_credentials=True` (insecure + broken in browsers) | `main.py:45` | X1 | 1 |
| 2 | 🔴 | ❓ | Look-ahead-bias risk: VWAP/Bollinger signal compares close to same-bar band/vwap (should lag) | `technical_indicators.py:222,828` | BU2 | 1 |
| 3 | 🔴 | ✅ | Div-by-zero in pattern scoring when counts are 0 | `recommendation_engine.py:88` | BU1 | 1 |
| 4 | 🔴 | ✅ | Div-by-zero in MA slope (`slope/avg_price`) | `analysis.py:109` | BU1 | 1 |
| 5 | 🔴 | ✅ | NaN in ADX (`dx = 100*|pdi-mdi|/(pdi+mdi)`) when both DI=0 | `market_regime.py:73` | BU1 | 1 |
| 6 | 🔴 | ✅ | Div-by-zero: RSI `rs = gain/loss` when loss=0 (flat price) | `technical_indicators.py:70,77` | BU2 | 1 |
| 7 | 🔴 | ✅ | TZ-naive `datetime.utcnow()` vs TZ-aware DB cols → DST comparison errors | `analysis_completeness.py:62`, `fetcher_tasks.py:156` | BU1/BU4 | 1 |
| 8 | 🟠 | ✅ | `market_hours` always-true condition → needless Polygon calls | `market_hours.py:234` | BU4 | 1 |
| 9 | 🟠 | ✅ | Per-stock exceptions swallowed; no visibility into partial fetch failures | `fetcher_tasks.py:333-340` | BU4 | 1 |
| 10 | 🟠 | ✅ | Chained fetch→aggregate→cache→analysis with no lock; overlap clobbers aggregates | `fetcher_tasks.py:282-323` | BU4 | 1 |
| 11 | 🟠 | ✅ | Indicator/pattern subsystem 100% pandas (0 Polars) vs migrated fetchers → conversion churn; and these files never use `IndicatorCacheService` | `technical_indicators.py`, `chart_patterns.py`, `candlestick_patterns.py` | BU2/BU3 | 2 |
| 12 | 🟠 | ✅ | `calculate_all_indicators()` computes 40+ indicators every request even if 3 needed; 36 `.copy()` per pass | `technical_indicators.py` | BU2 | 2 |
| 13 | 🟠 | ✅ | Sequential per-stock loops with `time.sleep(1)`; row-by-row upserts (no bulk `ON CONFLICT`) | `fetcher_tasks.py:280-343`, `timeframe_service.py:221-257` | BU4 | 2 |
| 14 | 🟠 | ✅ | Cache invalidation recomputes all 35 indicators if any of last 10 bars change | `indicator_cache_service.py:94-98` | BU4 | 2 |
| 15 | 🟡 | ✅ | Frontend: 30s polling with no abort-on-unmount; no list virtualization (335+ rows); filter runs every render | `StockList.jsx:307,442,726` | FU1 | 2 |
| 16 | 🟡 | ✅ | `init.sql` stale vs 16 alembic migrations (real schema drift) | `database/init.sql`, `backend/alembic/versions/` | BU6 | 3 |
| 17 | 🟡 | ✅ | Two schedulers (Celery Beat + in-process APScheduler) | `celery_app.py`, `services/scheduler.py` | BU4 | 3 |
| 18 | 🟡 | ✅ | `ml.py` route is a 501 stub but still mounted | `main.py:6,58`, `api/routes/ml.py` | BU7 | 3 |
| 19 | 🟡 | ❓ | ATR / swing-point / weekly-trend logic duplicated across 3–4 modules | `risk_management.py`, `order_calculator.py`, `analysis.py` | BU5 | 3 |
| 20 | 🟡 | ✅ | `backend/requirements.txt` pins TensorFlow + torch + scikit-learn + TA-Lib (heavy, partly for legacy ML path) | `requirements.txt` | X1 | 3 |

> Full per-unit checklists below contain the longer tail of findings.

## 4. Per-unit checklists

### BU1 — Analysis brain (priority)
- [ ] Trace `_get_recommendation_for_stock()` end-to-end; document the exact weight blend and where overrides apply.
- [ ] **Confirm/fix** div-by-zero: `analysis.py:109`, `recommendation_engine.py:88`, `market_regime.py:73`.
- [ ] **Confirm/fix** TZ handling in `analysis_completeness.py:62` (use tz-aware UTC throughout).
- [ ] Verify the "weekly-trend override" can't silently flip a valid signal due to a stale weekly bar.
- [ ] Audit every `except Exception: logger.warning(...)` (e.g. `analysis.py:729`) — ensure stale/missing data is surfaced, not hidden.
- [ ] Add tests: a stock with flat prices (loss=0), a stock with <window bars, a stock with all-bullish/all-bearish patterns.

### BU2 — Indicator engine (priority)
- [ ] **Confirm/fix look-ahead bias** at `technical_indicators.py:222,828` (VWAP/Bollinger must compare to prior bar).
- [ ] **Add guards** for div-by-zero/NaN: RSI (`:70,77`), ADX path, MFI, all `.iloc[-1]` reads.
- [ ] Verify TA-Lib and pandas fallback produce identical outputs (property test on a sample series).
- [ ] Decide Polars strategy: at minimum stop converting fetcher Polars→pandas back→pandas; ideally vectorize in Polars/NumPy.
- [ ] Split the 2983-LOC file: momentum / trend-volume / volatility-advanced / orchestration.
- [ ] Wire `IndicatorCacheService` so indicator functions read cache instead of recomputing.

### BU5 — Risk & order calc
- [ ] **Re-derive every formula** (entry, stop via swing low / Volume Profile POC, target via ATR multiple, R/R).
- [ ] Confirm position-sizing math against `risk_utils.py`; remove duplication with `order_calculator.py`.
- [ ] Guard None/zero ATR, None swing-low (`order_calculator.py:848`).
- [ ] Property tests on known OHLCV fixtures.

### BU3 — Pattern detection
- [ ] Confirm `chart_patterns_old.py`/`chart_patterns_extended.py` are archived (done) and no live refs.
- [ ] Validate detection on labeled patterns (use the user-confirmation dataset as ground truth).
- [ ] Profile 335 stocks × 3 timeframes; flag O(n²) peak-triple matching.
- [ ] Candlestick: consolidate 40 independent passes into one computed-features pass.

### BU4 — Data ingestion & tasks
- [ ] Fix `market_hours.py:234` always-true; add DST-correct ET handling (`market_hours.py:116`).
- [ ] Replace per-row upserts with bulk `ON CONFLICT` (`timeframe_service.py:221`, `fetcher_tasks.py:159`).
- [ ] Add idempotency/unique constraints for dividends/splits (`fetcher_tasks.py:928,1024`).
- [ ] Add per-stock failure metrics (don't swallow — `fetcher_tasks.py:333`).
- [ ] Decide APScheduler vs moving prediction-eval into Celery Beat.

### BU6 — DB & schema
- [ ] Regenerate `init.sql`/ERD from migrations; delete or relabel the stale one.
- [ ] Audit indexes for the real query patterns (dashboard eager load, pattern lookups).
- [ ] Confirm TimescaleDB chunk interval sensible for `stock_prices`.

### BU7 / FU1–3 / X1
- [ ] Convert sync DB handlers in async routes to `run_in_threadpool` or make them sync routes (consistent).
- [ ] Remove or implement the `ml.py` 501 stub (paired `main.py` edit).
- [ ] Frontend: add `react-window` virtualization; abort in-flight polls on unmount; `useMemo` filters.
- [ ] Slim `requirements.txt`; move heavy ML deps behind an extra if only the legacy path needs them.

## 5. Decision items (need user input — not auto-fixed)
1. **ML model lineage** — legacy LSTM/GRU (`ml_training/`) vs TabNet stack (`ml-training/`). Which is canonical? (See `ARCHITECTURE.md` §5.)
2. **`ml.py` route** — remove the 501 stub (needs `main.py` edit) or implement it?
3. **`quiverquant_fetcher` v1** — already not imported; confirm safe to archive.
4. **`ml-training/saved_models/*.ckpt`** — untrack from git (large) or keep as deployed artifacts?
5. **APScheduler** — keep the second scheduler or consolidate into Celery Beat?

## 6. Recommended workflow per unit
1. **Read** the unit's files + `ARCHITECTURE.md` section.
2. **List findings** with `file:line`, severity, CONFIRMED/SUSPECTED, suggested fix.
3. **Adversarially verify** each CONFIRMED bug with a minimal repro or test.
4. **Triage** into: fix-now (phase-relevant) · fix-later · wontfix (with reason).
5. **Open one PR per unit** with fixes + tests; link the unit's checklist.

## 7. Definition of done (per unit)
- Findings register updated (new items added, closed items marked).
- Every fix-now item has a commit + a test.
- No new `except Exception: pass` introduced.
- Unit's section of `ARCHITECTURE.md` still accurate.
