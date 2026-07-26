# StockAnalyzer — Status & Knowledge Snapshot

**Date:** 2026-07-25  
**Branch:** `chore/audit-restructure` (nothing merged to `main` without explicit approval)  
**Purpose:** A baseline of what we know and where things stand, so future progress can be compared against it. Read this first.

---

## TL;DR — the hard-won conclusion

A full investigation (indicator attribution → GA weight optimization → cross-regime stress tests → news-sentiment attribution) produced one central finding:

> **Public, daily-frequency signals — OHLCV technical indicators, chart & candlestick patterns, and Polygon news sentiment — have ~no standalone predictive edge for the direction of next-week-to-next-month returns on liquid US large-cap stocks.**

Measured directly: hit rates ≈ 50% (coin flip), rank IC ≈ 0.00 across the board. The single exception is **RSI** (small but real edge, val IC ~0.06 → 0.14 as horizon lengthens). This is the most-watched, most-efficient corner of the market — the result is expected (public daily price signals were arb'd away long ago) and is **not** a code bug; the measurement is sound and was confirmed three independent ways.

**Implication:** the engine should not be treated as a prediction/alpha engine. Its realistic value is **risk-managed participation** — the live default weights beat SPY in the 2022 bear (+3.5% alpha) by being defensive. That is real risk-adjusted return from *exposure management*, not from predicting direction.

---

## The signal-edge investigation (the data)

| Signal family | Standalone val rank IC | Verdict |
|---|---|---|
| ~40 technical indicators | ~0.00 (RSI the exception: +0.06→+0.14) | no edge (one small signal) |
| Chart / candlestick patterns | ~0.00 | no edge |
| GA on price signals, **bull-trained** (2024–26) | — | bull-specialized: −23% / alpha −3% in 2022 bear |
| GA on price signals, **bear-trained** (2022–24) | — | bear-specialized: +15.6% / alpha −28% in 2024–26 bull |
| **News sentiment (Polygon, independent)** | ~0.00 (−0.02 … +0.004) | no edge |

**GA cross-regime proof (definitive):** training the GA on a bull produces bull-specialized weights that fail the bear (GA #10); training on a bear produces bear-specialized weights that fail the bull (GA #13). No static weight set is robust across regimes — because the components have no predictive edge, the GA can only tune *how long-biased* to be, which is inherently regime-dependent. **The weight-optimization path is exhausted.**

---

## What the system is

StockAnalyzer: a 24/7 paper-trading + backtesting + strategy-optimization platform (FastAPI backend + Celery workers + Postgres + React frontend; separate `ml_training` project).

**Live (24/7):**
- **engine_1** (systematic) + **engine_2** (swing), running A/B as a paper-trading ledger (~83 open trades), with a twice-daily Gmail digest heartbeat.
- Signal blending across components: technical indicators, chart patterns, candlestick patterns, market regime, strategy consensus, (news sentiment in live; ML predictions).

**Backtest / analysis stack (Phase 2 + 3):**
- No-look-ahead historical backtester (`backend/app/services/backtest/`), AST-guarded.
- GA weight optimizer over the backtester's composite fitness, with train/val overfit guard.
- Per-(stock,T) input precompute (parallel) for fast GA evaluation.

---

## What was built this phase (performance + diagnostics)

- **Detector vectorization** (committed `8aecd26`): chart patterns ~10×, candlestick ~9.3×, output-identical, golden-test-gated.
- **Parallel precompute** (`precompute.py`): fans the per-(stock,T) build across CPU cores (~6×). Turned a ~5.7h GA into ~1.5–2h.
- **Threads-pool worker** (`docker-compose.yml`): required so Celery tasks can spawn multiprocessing children (prefork is daemonic → crashes). Paper-trading unaffected.
- **Attribution tooling** (the diagnostic that produced the findings above):
  - `scripts/component_attribution.py` — per-component rank IC (indicators/patterns).
  - `scripts/sentiment_attribution.py` — news-sentiment rank IC (independent-data test).
  - `scripts/stress_test_weights.py` — replay a GA's weights on any regime, head-to-head vs defaults.
- **Sentiment backfill** (`scripts/fetch_historical_news.py`, env-scopable): Polygon news+sentiment for 2024+ (37k articles, neutral 63% / positive 29% / negative 8%).

---

## Infra gotchas (for future sessions)

1. **Parallel precompute needs `--pool=threads` on the Celery worker.** Prefork runs tasks in daemonic processes that can't spawn children (`AssertionError: daemonic processes are not allowed to have children`). Set in `docker-compose.yml` (celery_worker). A daemonic-context fallback in `precompute.py` keeps it correct (serial) under prefork.
2. **Memory ceiling.** The in-memory bundle cache scales with universe × window. **4.5y × 100 stocks OOM'd the 23.4 GB host** (mid-train orphan). 2y × 100 (≈ GA #10) fits. Keep GA windows ≤ ~2y and/or ≤ ~80–100 stocks.
3. **Sentiment-backfill bug (found + fixed this phase):** `fetch_historical_news.py` matched `insight.ticker == article.get('ticker')`, but Polygon articles have a `tickers` *list* (no top-level `ticker`) → 99.8% defaulted to neutral. Fixed to match the fetched `symbol`. (The *live* fetcher was always correct.)
4. **Celery acks-on-receipt:** restarting the worker mid-GA orphans the run (happened to GA #8, #12). Don't restart while a GA is running.

---

## Commit / working-tree state

- **Committed:** `8aecd26` — chart + candlestick vectorization + both golden test suites.
- **Uncommitted (working tree, this branch):**
  - `backend/app/services/backtest/precompute.py` — parallelized + daemonic fallback.
  - `docker-compose.yml` — celery_worker `--pool=threads`.
  - `backend/scripts/` — `component_attribution.py`, `sentiment_attribution.py`, `stress_test_weights.py`.
  - `backend/scripts/fetch_historical_news.py` — env-scopable + sentiment bug fix.
  - DB now holds ~37k clean sentiment-tagged news rows (2024+) for the backtest universe.
- **Stale docs archived:** the 10 old root `.md` files moved to `docs/obsolete/`.

---

## Open decisions — the next move (to discuss)

The investigation ruled out "more of the same." Realistic options:

1. **Reframe as risk-managed participation + regime de-risk overlay (option B).** Empower `market_regime` to scale exposure down in bearish regimes (proportional, not a buy-ban). Doesn't need predictive alpha — captures what the live defaults did implicitly. Cheapest real improvement left.
2. **Change the game for predictive edge:** different data (fundamentals, alternative), different market (small caps / international / crypto — less efficient), or different horizon (intraday). Only path to genuine alpha; bigger build, untested ceiling.
3. **Accept the ceiling:** keep the engine as a defensive participation tool; stop chasing prediction.

**Lean:** (1) as the pragmatic next step; (3) as the honest framing. (2) only if you want to invest in a fundamentally different data pipeline.

---

## Alternative-data probes (2026-07-25) — round 1

After the conclusion above, we surveyed Polygon/Massive's Stocks plan for data *informationally different* from price, and probed each for standalone rank IC (same harness as the sentiment test: signal-as-of-T vs forward 5/10/21d, chronological 0.7 train/val). **Probe finding: of the 8 candidate endpoints, only 4 were usable on the current plan** — financials are `403 NOT_AUTHORIZED` (needs plan upgrade); the 3 SEC-filing endpoints (`form-4`, `8-K`, `13-F`) **ignore ticker filters and page globally** (so per-stock backfill is impractical for insider/13-F).

**Tested (4 Polygon sources + EDGAR fundamentals, backfilled + attributed):**

| Source | Best signal | val IC (h=5/10/21) | train IC | Verdict |
|---|---|---|---|---|
| Short interest + volume | days_to_cover, short_vol_ratio | DTC +0.022/+0.044/**+0.086**; SVR +0.016/+0.034/+0.033 | DTC **−0.054** (sign flip) | **not robust** — val/train sign inversion = regime noise, not edge |
| SEC 8-K disclosures | count_7/30d, train-learned category polarity | polarity −0.024/−0.029/−0.048 | polarity **+0.034** (reversal) | **not robust** — polarity overfits train, reverses OOS |
| **SEC risk factors** | **new_risks** (added vs prior 10-K) | short win −0.054/−0.067/−0.049; **full-5y −0.026/−0.030/−0.021** | full-5y train ≈ 0 | **not robust** — the short-window "candidate" was a window artifact; on full history it drops below the 0.03–0.05 bar with train ≈ 0 |
| **Insider (Form-4)** | net cluster open-market buying / vol20 (90/30d), off/dir-only, buy-event cluster | val ≈ 0 (±0.02) across all | train ≈ 0 (small +) | **no edge** — the strongest documented anomaly (cluster insider buying → +returns) does NOT replicate; 100/100 stocks, ~54k trades. An early float-normalized run showed val −0.115, but that was a float-history artifact (float has only a current snapshot → train NaN); it vanished under volume normalization |
| **Fundamentals (EDGAR XBRL)** | accruals (Sloan), gross profitability (Novy-Marx), ROE | accruals +0.012/+0.015/+0.018; grossprof +0.001/+0.001/+0.007; roe +0.003/+0.005/+0.015 | accruals +0.007/+0.011/+0.013; grossprof **−**0.018/−0.031/−0.044; roe +0.005/+0.006/+0.012 | **no edge** — both flagship anomalies wrong-sign + ~0 (Sloan predicts −, got +; Novy-Marx predicts +, train is −). 94/100 stocks, point-in-time by filing date. **Completes the investigation: all 8 signal families are null.** |

**Decision rule applied:** real edge = val IC persistently > 0.03–0.05 **and** consistent sign with train. **None of the five clear it** — short-interest/8-K fail train-val consistency; risk-factors didn't survive full-history; insider is a clean null; **fundamentals are wrong-sign + ~0 (Sloan & Novy-Marx both fail)**. Combined with the earlier indicators/patterns/sentiment nulls, **all eight public-data signal families are null**; RSI remains the lone exception. Standalone directional prediction on liquid US large-caps is **exhausted**.

**Deferred (not worth the build):** 13-F (global-only + no CUSIP map, impractical), fundamentals (`403`, needs plan upgrade or EDGAR XBRL). Insider was tested via Polygon global-sweep (54k trades) and is a null — no longer a candidate.

**Infra added this round (uncommitted, branch `chore/audit-restructure`):** `scripts/polygon_client.py` (shared REST client), `scripts/attribution_lib.py` (shared IC harness), migration `20260725_alt_data_sources` (5 tables: `insider_trades`, `sec_disclosures`, `short_volume`, `risk_factors`, `stock_floats`), backfills (`fetch_floats`, `fetch_short_interest`, `fetch_risk_factors`, `fetch_8k_disclosures`), attributions (`short_interest`, `risk_factors`, `disclosures_8k`), and `tests/test_alt_attribution_point_in_time.py` (causality source-guard, green). Live paths untouched.

---

## ML combination thesis — tested, negative (2026-07-26)

The project's core hypothesis ("combine many weak inputs → robust prediction") was tested fairly on ml-training's own model + features. `ml-training/scripts/cross_regime_validation.py` holds the 2022 bear OUT of training, trains CatBoost on the other 156 features (300,938 samples), evaluates OOS on bear + bull:

| Regime (held-out OOS) | AUC vs label | rank IC vs alpha (excess) |
|---|---|---|
| BEAR 2022 (n=61,485) | **0.504** (coin flip) | **−0.031** |
| BULL 2024+ (n=122,761) | 0.567 | +0.036 |

The headline TabNet result (+9.71%, Sharpe 2.44, Q1-2024) used a single chronological split over 2018–2026 → **the bear was in the training set, never held out**, no purge at the boundary. Held out and measured on excess returns (alpha), the model has **no bear edge** (AUC 0.504, alpha IC −0.031; the +0.056 raw-return IC is a beta artifact) and only **marginal bull alpha** (+0.036). Verdict: the combination does NOT produce robust cross-regime edge — same regime-overfit failure as the GA (#10/#13). The thesis is not supported on this market/data. (`ml_training` = legacy LSTM/GRU pattern classifier, price-only.)



**Status (2026-07-26):** probe layer COMPLETE; 8/8 standalone signal families null (table above). Infra is reusable; nothing live-touched.

**Shared-DB link (important):** `ml-training/ml_framework/insider_features.py` already reads our `insider_trades` table — our Form-4 backfill feeds it. `sec_disclosures`, `short_volume`, `risk_factors` tables exist but have **no ml-training feature modules yet**.

**DONE:**
- Shared infra: `scripts/polygon_client.py`, `scripts/attribution_lib.py`.
- Migration `20260725_alt_data_sources` (5 tables) — applied.
- Backfills (run, populated): `fetch_floats`, `fetch_short_interest` (+short volume), `fetch_risk_factors`, `fetch_8k_disclosures`, `fetch_insider_form4` (~54k trades).
- Attribution (run, all null): `short_interest`, `risk_factors`, `disclosures_8k`, `insider`, `fundamentals` (EDGAR probe, self-contained).
- Causality guard: `tests/test_alt_attribution_point_in_time.py` (green).

**REMAINING (resumable; each step gated by train/val + cross-regime):**
1. **Rigorous validation of ml-training's best model (TabNet/CatBoost)** — *the* combination test: full-history walk-forward + purged CV + cross-regime OOS (incl. 2022 bear). The Q1-2024 +9.71% result is single-bull-quarter, +1% vs B&H, unvalidated — must survive this before trusting. **Go/no-go gate for the whole combination thesis.**
2. **Persist fundamentals** — promote the EDGAR probe to a `fundamentals` table + backfill (point-in-time by `filing_date`). Only if wanted for UI/ML.
3. **Wire new alt-data into ml-training** — add `short_volume_features.py`, `disclosures_8k_features.py`, `risk_factors_features.py` in `ml-training/ml_framework/` (mirror `insider_features.py`), reading our tables, so the joint model can use them.
4. **UI integration** — read-only backend endpoints (`GET /stocks/{id}/{insider,short-interest,disclosures,risk-factors}`) + frontend panels on ticker/mainpage. Pure display, no prediction claim. Clear low-risk win.
5. **Engine/GA integration** — add alt-data as components via the Phase-3 weights seam; experimental, guard-gated (expect train/val to show no robust lift, per GA #10/#13).
6. **13-F** — SKIP (global-only, no CUSIP map, impractical; would be a 9th null).

**Resume point:** after ML inspection → run step 1 (rigorous validation). If TabNet edge survives cross-regime → steps 2–5 (wire + UI + engine). If not → pivot to risk-managed participation / regime overlay (option B).

---

## Regime de-risk overlay — built + A/B'd, NOT promoted (2026-07-26)

Built the proportional bear-market suppression overlay (STATUS option-B "risk-managed
participation" lever) and A/B-tested it. **Verdict: keep OFF (the default); it adds no value.**

**Design (default-OFF ⇒ byte-identical to today; live untouched):**
- engine_1: scale the buy-leaning `weighted_score` by `f(per-stock direction)` —
  `bearish`→×(1−s), `bearish_weak`→×(1−s/2) — before the BUY threshold (can flip BUY→HOLD).
- engine_2: replace the hard weekly-bear `BUY→HOLD` ban with **position-size scaling**
  (×(1−s)). Sizing is risk-based (stop distance), not confidence-coupled, so scaling
  SIZE (not confidence) is the real de-risk lever.
- New pure `signal/regime_overlay.py`; new pure `backtest_regime.detect_direction_from_df`
  (mirrors live `detect_tcr_regime` — parity-tested); `overlay_strength` threaded through
  the backtest + `POST /api/v1/backtests` (`regime_overlay_strength`); live
  `recommendation_engine` now reads `direction` (inert at s=0, promote-ready).
- Tests green in-container (real TA-Lib): `tests/test_regime_overlay.py` (byte-identical
  at OFF, suppression math, live parity) + `test_backtest_no_lookahead.py` (no regression).

**A/B** (in-memory, input-cache, 30 stocks, same prices; SPY window return shown):

| engine | window (SPY) | overlay 0.0 → 0.4 | return% | maxDD% | alpha% | trades |
|---|---|---|---|---|---|---|
| engine_1 | 2022 bear (−20.0%) | 0.0 / 0.4 | −0.11 / −0.10 | −0.19 / −0.17 | +0.09 / +0.10 | 103 / 92 |
| engine_2 | 2022 bear (−20.0%) | 0.0 / 0.4 | −0.10 / −0.12 | −0.14 / −0.14 | +0.10 / +0.08 | 144 / **200** |
| engine_1 | 2024-26 bull (+57.8%) | 0.0 / 0.4 | +0.06 / +0.04 | −0.09 / −0.10 | −0.51 / −0.54 | 234 / 220 |

**Why it doesn't help:**
- **engine_1 is already ~cash in every regime** (≈0% return in both the −20% bear and the
  +58% bull; tiny DD). Its buy signals rarely clear the 0.3 threshold, so there is almost
  nothing for the overlay to suppress — it is defensive by *inaction*, not by the overlay.
  (Notable side-finding: engine_1 as configured generates ~no participation/return.)
- **engine_2's hard weekly-bear ban is genuinely protective:** softening it let +56
  previously-banned buys enter (at 0.6× size) and they were net losers (same DD, slightly
  worse return). The banned trades were the right ones to ban.
- The overlay can only *suppress* longs, so in a bull it can only cost return (it did, marginally).

**Decision: overlay stays OFF (zero behavior change); engine_2 keeps its hard weekly-bear ban.**
Code/tests/API are in place if a future regime ever warrants it, but the data says no —
consistent with the no-edge conclusion (no directional edge ⇒ no risk-overlay tuning creates
return, and the engines' natural defensiveness already covers the bear).

**Infra** (branch `chore/audit-restructure`, uncommitted): `signal/regime_overlay.py`,
`backtest_regime.detect_direction_from_df`, the `overlay_strength` seam (systematic / swing /
backtest_signal_adapter / replay_engine / runner / api / recommendation_engine),
`tests/test_regime_overlay.py`, `scripts/regime_overlay_ab.py`. Nothing merged to main; live untouched.

---

*This document is the "previous status" baseline. Update it as the picture changes.*
