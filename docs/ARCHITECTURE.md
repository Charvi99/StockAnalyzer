# StockAnalyzer — Architecture (canonical)

> **Source of truth as of 2026-07-20.** This document supersedes the stale Phase-8
> descriptions in `README.md` and `docs/CLAUDE.md` (which advertise FinBERT/LSTM/CNN
> features that no longer match the code). Where this file and other `.md` disagree,
> **this file is correct** — and when in doubt, the code wins over all docs.

## 1. Two projects in one repo

| Project | Path | Stack | Status |
|---|---|---|---|
| **Swing-trading app** | `backend/` + `frontend/` + `database/` | FastAPI · Celery · Redis · PostgreSQL/TimescaleDB · React 18 | Live, rotted (under audit) |
| **ML training** | `ml-training/` (hyphen) | Polars · TabNet · AutoGluon · CatBoost · PyTorch | Live |

Archived/dead code lives under `archive/` (moved 2026-07-20; see
`RESTRUCTURE_CHANGELOG.md`). The legacy `ml_training/` (underscore) is **not** dead —
see §5.

## 2. Swing-trading app — component map

### Backend (`backend/app/`, import root `app.`)
All imports resolve to the in-container mount `./backend:/app`, so host-path changes
do **not** affect the Python import graph.

```
app/
├── main.py                  FastAPI app, lifespan (APScheduler), router wiring, CORS
├── celery_app.py            Celery + Beat schedule (12 periodic tasks, 3 priority queues)
├── api/routes/              14 routers, ~74 endpoints (analysis, stocks, prices, patterns,
│                            chart_patterns, sentiment, news, ml_predictions, ml [stub],
│                            strategies, risk_management, dividend_split_signals, health)
├── services/                business logic (the bulk of the codebase)
│   ├── technical_indicators.py   2983 LOC — 40+ indicators, TA-Lib primary + pandas fallback
│   ├── chart_patterns.py         2307 LOC — 22 chart patterns (ATR peak detection)
│   ├── candlestick_patterns.py   1379 LOC — 40 candlestick patterns
│   ├── analysis/recommendation…  recommendation_engine, market_regime, completeness
│   ├── order_calculator.py       1122 LOC — entry/stop/target via Volume Profile + ATR
│   ├── risk_management.py        ATR stops, position sizing, portfolio heat
│   ├── polygon_fetcher.py        Polygon.io REST client (prices/news/dividends/splits)
│   ├── sec_edgar_fetcher.py      SEC Form 4 insider filings
│   ├── quiverquant_fetcher_v2.py official quiverquant package wrapper (v1 status — see §6)
│   ├── timeframe_service.py / timeframe_aggregator.py   multi-timeframe (1h→4h/1d/1w/1mo)
│   └── indicator_cache_service.py  JSONB cache of all indicators (claimed 41× speedup)
├── tasks/                   Celery tasks: fetcher_tasks (1231), processor, analysis, maintenance
├── models/                  SQLAlchemy models (the REAL schema — see §4)
├── schemas/                 Pydantic v2 schemas
├── db/database.py           session/engine
└── utils/                   market_hours (430), risk_utils
```

### Frontend (`frontend/src/`, React 18 / CRA)
No global store — pure `useState` + prop drilling. `services/api.js` is the axios
client (40+ endpoint fns). Largest components: `ChartPatterns.jsx` (2064),
`TechnicalAnalysis.jsx` (1440), `IndicatorInfo.jsx` (1394), `StockList.jsx` (1297),
`StockChart.jsx` (840, lightweight-charts).

### Data flow — ingestion pipeline (Celery Beat → DB)
```
Beat schedule (celery_app.py)
  → fetch_high/medium/low_priority_stocks   (Polygon, rate-limited 100/min)
  → TimeframeAggregator (1h → 4h/1d/1w/1mo, pandas resample)
  → IndicatorCacheService (pre-compute 35 indicators → technical_indicators_cache JSONB)
  → detect_patterns_* (chart + candlestick → chart_patterns / candlestick_patterns tables)
  → analyze_stock_comprehensive (regime + recommendation → recommendations)
News/sentiment, dividends/splits, insider (SEC)/congressional (QuiverQuant) on their own schedules.
```

### Data flow — analysis request (HTTP)
```
GET /api/v1/analysis/dashboard
  → eager-load stocks + prices (1d, last 200d) + predictions + sentiment + patterns
  → per stock: _get_recommendation_for_stock()
      ├─ IndicatorCache hit?  → fast path
      └─ miss → calculate_all_indicators() (40+ indicators, ~2.5s) → slow path
      → weekly-trend filter → swing-point alignment → weighted recommendation
      → combine: technical 40% · ML 40% · sentiment 20% → weekly-trend override
```

## 3. Two schedulers
- **Celery Beat** (`celery_app.py`) — data ingestion & processing, 12 periodic tasks,
  3 queues (`fetcher`/`processor`/`maintenance`), priority 0–10. The freshness backbone.
- **APScheduler** (`services/scheduler.py`, started in `main.py` lifespan) — runs
  prediction-performance evaluation daily at midnight, **in the FastAPI process**.
  No HA: stops if the web process restarts. Minimal overlap with Beat, but a second
  moving part to maintain.

## 4. Real database schema
`database/init.sql` is **stale** (describes FinBERT/predictions-only). The live schema
is the 16 Alembic migrations in `backend/alembic/versions/`. Tables in use:
`stocks`, `stock_prices` (TimescaleDB hypertable), `predictions`, `prediction_performance`,
`technical_indicators`, `technical_indicators_cache`, `sentiment_scores`,
`candlestick_patterns`, `chart_patterns`, `news`, `dividends`, `stock_splits`,
`short_interest`, `alternative_data`, `insider_trades`, `timeframe` config.
→ **Audit action:** regenerate a current `init.sql` / ERD from migrations (BU6).

## 5. ML model lineage — two coexist (open decision)
- **Legacy** — `ml_training/outputs/models/{lstm,gru}.{h5,keras}` (TensorFlow/Keras).
  Loaded **live** by `app/services/ml_predictor.py:24`
  (`models_dir="ml_training/outputs/models"`); served via `/api/v1/.../ml-predict`.
  docker-compose mounts `./ml_training:/app/ml_training`.
- **Current** — `ml-training/` project: TabNet / AutoGluon / CatBoost / FT-Transformer,
  Polars-based; models under `ml-training/outputs/models/` + `ml-training/saved_models/`.

**Which is canonical?** Undecided. If TabNet wins, retire `ml_predictor.py` + the
`ml.py`/`ml_predictions.py` routes + the `ml_training/` mount. TensorFlow is still
pinned in `backend/requirements.txt` solely for the legacy path.

## 6. Backend ↔ ml-training coupling
`ml-training` container mounts `./backend:/backend` with `PYTHONPATH=/backend` and
imports `from app.services.…`. Shared docker volume `ml_models`. **Implication:** any
future move/rename of `backend/` must update that cross-mount in `docker-compose.yml`.

## 7. External dependencies
- **Polygon.io** (Starter, 100 req/min) — prices, news, dividends, splits, market status. Key via `POLYGON_API_KEY`.
- **SEC EDGAR** — Form 4 insider filings (5 req/sec, hardcoded User-Agent).
- **QuiverQuant** — congressional trading (via official package in `quiverquant_fetcher_v2`).
- **Redis** — Celery broker/backend.
- **Finnhub** — in requirements, but not found active in code.

## 8. Known cross-cutting risks (summary — full list in AUDIT_PLAN.md)
- CORS `allow_origins=["*"]` + `allow_credentials=True` (`main.py:45`) — insecure + broken in browsers.
- Timezone: TZ-naive `datetime.utcnow()` vs TZ-aware DB columns (`analysis_completeness.py:62`, `fetcher_tasks.py:156`) — DST bugs on NYSE hours.
- Indicator/pattern subsystem is fully pandas (0 Polars) while fetchers migrated to Polars.
- ~9 division-by-zero paths in scoring/indicator math.
- Two schedulers, dual model lineage, stale schema/doc — drift, not bugs.
