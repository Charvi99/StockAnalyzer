# StockAnalyzer → Cutting-Edge Swing-Trading Tool: The Ultimate Roadmap

> **Status:** living document. **v2 — revised 2026-07-21** after an `ecc:planner`
> review grounded in the actual codebase.
> **Thesis:** a *legit foundation that was silently broken and is being fixed* — its
> trading value is **unproven and unknowable until measured**. This roadmap turns
> "nicely-looking" into "either it works or we find out it doesn't," as fast and
> honestly as possible.

### What changed in v2 (from the review)
- Added **Phase 0.5 — Data foundation** (survivorship-clean universe, delist dates, Polygon-tier decision, seeding). The v1 "no survivorship bias" line was infeasible without it.
- **Moved the pure-signal-function refactor into Phase 0** — v1 wrongly claimed the live signal services could be replayed directly; they're DB-bound (`generate_final_recommendation(db, stock_id)`, `MultiTimeframePatternDetector(db, …)`, `AnalysisCompletenessService`). Only `TechnicalIndicators` + `ChartPatternDetector` are pure today.
- **Pinned the exit-rule contract in Phase 1** — without it "expectancy" is undefined.
- **Reuse existing infra, don't reinvent** — `ml-training/backtesting/` (Backtester, Portfolio, MetricsCalculator, `BaseStrategy`) and `ml-training/scripts/label_creation/create_labels.py` (barrier labels) already exist; Phase 2/5 adapt them.
- **Folded the unaudited "Trading Strategies" tab** (a third signal surface + backtest UI) into the Phase 0 audit tail and Phase 2 reuse.
- **Regime-conditional scoreboard** (aggregate expectancy hides bleed-in-chop); **honest statistical power** (n=30 is data-collection, not verdict → n≥200/cell); **edge-decay monitoring**; **Phase 7** for the genuinely cutting-edge work; **Phase 3 pinned** to one ablation pass (not "ongoing"); **Phase 6 scoped research-only**; cut the nightly DB snapshot and `AnalysisCompletenessService`.

---

## 0. The honest starting line

What we have (after the 2026-07 audit + fix sprints):

- A real architecture: Polygon → TimescaleDB hypertable → multi-timeframe aggregation → indicators / chart patterns / candlesticks / market regime / sentiment / dividend-split → recommendation → Celery + React dashboard.
- **Three** signal surfaces (sprawl): Engine #1 (systematic, `recommendation_engine`), Engine #2 (realtime swing, `realtime_recommendation`), and the **Strategies framework** (`BaseStrategy` + execute/backtest/consensus, surfaced by the "Trading Strategies" tab — *not audited until now*).
- An **already-built backtest + metrics + label stack** in `ml-training/backtesting/` and `ml-training/scripts/label_creation/` that earlier planning ignored.
- A broad component set (35 indicators, multi-timeframe chart patterns, swing validation, regime detection, ATR position sizing, order calculator).

What we **don't** have:

- **Zero validated performance** — no forward paper-trading ledger, no out-of-sample hit-rate/expectancy. Signals never measured against reality.
- A **hand-tuned kitchen-sink signal** (35 indicators + patterns + sentiment + regime, weights set by hand). More features ≠ more edge.
- **No cost/slippage/risk-of-ruin model.** Any return without costs is fiction.
- **No survivorship-clean universe** — the `stocks` model has no list/delist fields; backtests would be biased to survivors.
- An **ML component that is a placeholder** (ml-training not wired to outcomes).
- A signal path that was, until days ago, **riddled with silent bugs** (wrong RSI, infinite VWAP, dropped components, dead sentiment table, unrouted pipeline, unreachable completeness, …).

**Governing principle:**

> **Validate, don't decorate.** No new indicators/patterns/UI/capital until the existing signal is measured honestly, net of costs, out of sample, by regime.

---

## 1. Non-negotiable principles

1. **Measure before you build.** The ledger (Phase 1) precedes everything.
2. **Simplify the signal.** A lean validated signal beats a 35-feature soup.
3. **Costs always** — fees, slippage, spread, borrow — in every measured return.
4. **Reuse, don't reinvent.** Existing `ml-training/` backtest/label infra is the foundation.
5. **Reproducibility.** Every signal is a pure function of `(data, config_version)`; every recommendation carries a `signal_version` hash.
6. **Out-of-sample is the only score that counts.** Walk-forward / purged CV; never tune on the test set.
7. **Regime-conditional, not global.** Edges live in specific regimes; aggregate numbers hide bleed.
8. **Kill silent failures.** Never `except: pass`. Raise, or log + emit a metric.
9. **One source of truth (eventually).** Unify the engines via a strategy facade *after* the ledger scores them (decision D35) — not before.

---

## 2. Phased roadmap

Each phase has a **hard, measurable acceptance criterion**.

### Phase 0 — Stabilize, refactor for replay, audit the Strategies tab  *(~2–3 weeks)*

Trust + replayability before anything is measured on top of it.

- Close the audit tail (remaining review units X1/X2).
- **Fix completeness scoring** so `analysis_complete` is reachable (stop counting ML/sentiment when absent) → kills the "⚠ 60% forever" display + the re-analysis loop. Then **retire `AnalysisCompletenessService`** once the ledger replaces "completeness" with "did the signal fire + get logged?"
- Fix the residual datetime bug (`volume score: datetime64 vs Timestamp`).
- Land Tier-1 reliability: **Docker log rotation**, **Polygon rate limiter**, **Celery soft/hard time limits**.
- **🔑 Pure-signal-function refactor (moved here from "assumed").** Extract a pure entry point:
  `signal(df_prices, df_indicators, df_patterns_at_t, regime, config_version) -> recommendation`
  Both engines become thin DB→DataFrame adapters over this pure function. *Until this exists, the ledger and backtest cannot measure the same thing.* Only `TechnicalIndicators` + `ChartPatternDetector` are pure today; the rest (`generate_final_recommendation`, `MultiTimeframePatternDetector`, `AnalysisCompletenessService`) read live DB state and must be unwound.
- **Audit the Strategies framework** (`BaseStrategy`, execute/backtest/consensus routes, the `TradingStrategies` tab) — it's a third, unaudited signal+backtest surface; apply the same silent-bug sweep.
- **Reconcile the two `BaseStrategy` classes** (`backend/app/services/base_strategy.py` vs `ml-training/backtesting/strategies/base.py`) — pick one, delete the other.
- **Regression test for every silent bug found this audit** (RSI Wilder, VWAP rolling, dropped components, dead sentiment table, `p.signal`, unrouted pipeline, unreachable completeness). Golden tests — they prevent regression of the exact failures that made the signal untrustworthy.
- Repair the Alembic chain; commit + merge the fix sprints.

**Acceptance:** full `backend/tests/` green; one clean `alembic upgrade head` from empty; a fresh boot ingests + analyzes with no swallowed exceptions; **the signal is computable from a DataFrame alone** (no live DB read inside the pure function).

### Phase 0.5 — Data foundation  *(~1–2 weeks)*  [NEW]

Without this, every later number is biased or slow.

- **Survivorship-clean universe:** migrate `stocks` to add `list_date`, `delist_date`, `delisted`; build the universe from Polygon `v3/reference/tickers?include_delisted=true` (or a curated index-membership file). Backtest/inference filter to "did this name exist on day T."
- **Polygon-tier decision (resolve the contradiction):** `polygon_fetcher.py` says "Starter 100/min," `README.md` says "free 5/min." This single decision determines whether ledger bootstrap takes **days or weeks** — decide and document it.
- **Adjusted-vs-split price policy** (one explicit rule, applied consistently).
- **Seed the universe** (`stocks` is currently empty per the audit-status memory).
- **Data-quality backfill:** gap/stale-bar detection, the Polygon wide-pull truncation guard (the 1y→stale bug class).

**Acceptance:** a survivorship-clean, point-in-time-queryable universe with a documented Polygon tier + adjusted-price policy.

### Phase 1 — The Truth Machine: paper-trading ledger  *(~2–3 weeks to first data; months to verdict)*  🔑 **#1 GOAL**

Everything else is opinion until this exists. Records **per signal fired**:

```
{ timestamp, stock, signal_version, surface(#1/#2/strategies), signal(BUY/SELL/HOLD),
  confidence, component_scores, regime, entry, stop, target, position_size,
  costs_model_version, EXIT_RULE_VERSION }
```

…then marks the **outcome**:

```
{ exit_time, exit_price, gross_return, cost, net_return, hold_days,
  hit_stop/hit_target, MFE, MAE, r_multiple }
```

Hard requirements:

- **🔑 Exit-rule contract pinned here (not deferred):** pick exactly one and freeze it as `EXIT_RULE_VERSION` — (a) **barrier** (stop or target first — what `create_labels.py` already does: +3% before −2% in 20d), (b) **time exit** at N days, or (c) **signal reversal**. Different rules → different "expectancy" on the same signals; the rule is part of the metric.
- **All three surfaces logged** → real A/B/C comparison; this is the evidence that justifies D35 unification instead of guessing.
- **Costs in every outcome** (placeholder model now; refined Phase 4; never cost-free).
- **Regime-stratified dashboard:** hit-rate/expectancy/drawdown **per regime** (Trend/Channel/Range × vol bucket), not just global. Aggregate expectancy hides a signal that prints in trend and bleeds in chop.
- **MFE/MAE are used, not just stored** — "did we leave money on the table?" questions the *exit rule itself* (feeds Phase 3 ablation).
- **Idempotent + immutable** rows.

**Statistical-honesty acceptance:** at **n=30/cell the deliverable is "data collection," not a verdict** (95% CI ≈ ±18pp — can't tell 52% from a coin flip). The **verdict gate is n≥200/cell** net of costs, OR **reduce cells** (kill HOLD early, pilot-kill one engine, use 2 regimes) so per-cell n climbs faster. Budget months of paper-trading for the verdict, not weeks.

### Phase 2 — Backtesting harness (reuse, don't reinvent)  *(~1–2 weeks harness; months for tracking validation)*

Replay history through the **pure signal function from Phase 0** — not a reimplementation.

- **Adapt `ml-training/backtesting/`** (Backtester, Portfolio, OrderExecutor, MetricsCalculator with Sharpe/Sortino/Calmar/VaR-95/CVaR-95/profit-factor) — write a thin adapter from the Phase-0 pure signal into `BaseStrategy.analyze`. **Do not build a second backtest engine.**
- **Point-in-time query view** (`get_state_at(t)` over the existing hypertable) — replaces v1's "nightly DB snapshot" (a half-million-row dump with no consumer).
- **No lookahead:** indicators/patterns computed only from data available at each bar's close.
- **No survivorship bias:** Phase 0.5 universe + point-in-time existence filter.
- **Split into 2a (harness working, weeks) and 2b (tracking validation, months, runs alongside Phase 3):** does backtest expectancy track forward paper-trading expectancy? Divergence ⇒ bug or overfit.

**Acceptance (2a):** the pure signal backtests on history via the existing engine. **Acceptance (2b):** backtest expectancy tracks forward paper-trading within tolerance.

### Phase 3 — Signal surgery: ONE ablation pass  *(time-boxed, not "ongoing")*

Turn the kitchen sink into a defensible signal — in a single, frozen pass.

- **Stop rule:** drop any component whose removal changes out-of-sample expectancy by < 5 bps.
- **Ablate the signal components AND the exit rule** (MFE/MAE from Phase 1 tells you if the exit is the bug).
- **Learn the weights** (logistic → gradient boosting) on labeled ledger outcomes, **validated out-of-sample** — never tuned on the test window.
- Output a frozen **`signal_version=v2`** before Phase 4 starts (Phase 4 stress tests must run against a fixed target).
- ⚠ **Do-NOT:** don't pick components by OOS performance and then re-measure on the same OOS window (in-sample contamination). Hold out a final unseen window.

**Acceptance:** a leaner (3–6 component) signal with **equal-or-better validated OOS expectancy** than today's full stack; frozen version.

### Phase 4 — Make it honestly tradeable  *(~2 weeks)*

- Realistic **cost/slippage model** per instrument (spread + impact + fees + borrow), wired into the ledger outcome writer.
- **Portfolio risk:** heat budget, correlation-aware sizing, max gross/long/short, risk-of-ruin.
- **Regime-aware sizing:** scale down in chop/high-vol (regime detector → position size).
- **Stress suite:** 2008, 2020-COVID, 2022-rate-shock, single-sector shocks.

**Acceptance:** a paper portfolio that survives the stress suite within drawdown limits. Nothing goes live that can't pass.

### Phase 5 — ML done right (reuse the label pipeline)  *(~4+ weeks, only if 1–3 show promise)*

The ledger's labeled outcomes **are** the training set.

- **Reuse `ml-training/scripts/label_creation/create_labels.py`** (barrier labels) — feed it ledger rows; don't reimplement labels.
- Wire TabNet/CatBoost to predict **risk-adjusted forward return**, not just up/down.
- **Purged + embargoed CV** (embargo = label horizon, e.g. 20d) — leakage from overlapping labels is the #1 ML-on-prices failure.
- **Fractional differentiation / stationary features** (non-stationarity is the #2 failure).
- Feature importance feeds **back into Phase 3**.

**Acceptance:** ML adds validated OOS edge on top of systematic-only — else it stays in research.

### Phase 6 — Cautious live  *(research-scoped; only after validated edge)*

- **Scope this phase as a research/design doc with hard thresholds, not an implementation sprint.** Broker integration + real money + legal is a separate project; mixing it in muddies the research/production boundary the rest of the doc protects.
- Kill-switch + max-drawdown circuit breaker + alerting.
- **Edge-decay kill threshold (concrete):** e.g. live-vs-paper expectancy drift > X pp/week, or rolling-60-trade hit-rate CUSUM trips → halt.
- Paper on the broker first, then tiny real capital; **1+ month of live matching paper within the stated tolerance** before scaling.

**Acceptance:** live reproduces paper; no unplanned circuit-breaker trips.

### Phase 7 — Genuinely cutting-edge  *(only after Phase 4 earns the right to scale)*  [NEW]

v1's title oversold "cutting-edge." This phase is what would actually earn that word:

- **Meta-labeling (López de Prado).** The signal says *direction*; a second model — trained on ledger outcomes — says *should I take this trade?* The single biggest unlock for swing-trading expectancy.
- **Per-regime specialists (ensemble, not unification).** v1 wanted "one engine post-ledger." The stronger architecture is trend-engine / range-engine / vol-spike-engine gated by the regime detector, each scored only in its home regime (the ledger already has a `regime` field). `BaseStrategy` + regime detection already support this.
- **Combinatorial Purged Cross-Validation (CPCV)** instead of a single walk-forward path — quantifies the uncertainty Phase 1's n=30 hand-waved.
- **Fractional-differentiated stationary features** for the ML layer.

**Acceptance:** meta-labeling + per-regime specialists each show validated OOS expectancy lift vs the Phase-3 frozen signal; CPCV gives a defensible confidence interval on edge.

---

## 3. Cross-cutting foundations (continuous)

- **Edge-decay monitoring (new):** rolling 60-trade expectancy vs Phase-1 baseline; **CUSUM / Page-Hinkley** regime-shift detector on hit-rate; live-vs-paper drift alert with a hard kill threshold; feature-drift watch on component scores.
- **Observability:** metrics, not just logs — signal staleness, task-failure rate, data gaps, queue depth, expected-vs-actual trade flow.
- **Data quality:** gap/stale-bar detection, adjusted-vs-split policy, **Polygon wide-pull truncation guard**.
- **Testing:** the Phase-0 silent-bug regression suite + **signal-level golden tests** (known input → known signal).
- **Reproducibility:** versioned config; `signal_version` on every recommendation; **point-in-time query view** (not DB snapshots).

---

## 4. The "Do NOT" list

- ❌ Don't add indicators/patterns until existing ones are validated.
- ❌ Don't report any return without costs.
- ❌ Don't trust a signal that hasn't been measured out-of-sample.
- ❌ Don't merge the engines before the ledger scores them (D35).
- ❌ Don't tune weights on in-sample data — and **don't conflate in-sample ablation results with OOS verdicts.**
- ❌ Don't reinvent backtest/label infra that already exists in `ml-training/`.
- ❌ Don't `except: pass` — ever.
- ❌ Don't go live without passing the Phase-4 stress suite.
- ❌ Don't conflate "it runs" with "it works."

---

## 5. The only scoreboard that matters (now regime-conditional)

> **Forward paper-trading expectancy > 0, net of realistic costs, out-of-sample,
> per regime, over n≥200 trades per cell** — with edge-decay monitored and a live
> kill-threshold in place.

Until that's true this is a **research project**, not a trading tool. Aggregate/global expectancy is not acceptable evidence — it must hold per regime.

---

## 6. Engineering principles (enforced in review)

- **One pure signal function** (Phase 0) consumed by live, ledger, and backtest alike.
- **One `BaseStrategy`** (reconcile the duplicate) + **one backtest engine** (`ml-training/backtesting/`).
- **One recommendation facade** post-ledger, strategy-pattern (specialists behind one interface) — not a god-class.
- **Idempotent, time-limited Celery tasks**; no silent failure paths.
- **Timezone-aware UTC end-to-end** (done).
- **Indexed FKs, hypertable-aware queries, no N+1** on hot paths.
- **Every PR touching the signal path adds/updates a test.**

---

## 7. Open decisions to pin before coding

| Decision | Status / Owner | Impact |
|---|---|---|
| **Polygon tier** | ✅ Resolved — **Stocks Starter, effectively unlimited calls** | Ledger bootstrap is fast (days, not weeks); rate limiter stays only as a polite guard |
| **Exit rule** | ✅ Resolved — **barrier: TP/SL from the order calculator, hit-first; max-hold time cap** so a trade can't hang forever | Defines Phase 1 expectancy; matches `create_labels.py`; Phase 5 purged-CV embargo = max-hold window |
| **Which cells to kill early** (HOLD? one engine? 2 regimes?) | Phase 1 pilot | statistical power / verdict speed |
| **Adjusted-vs-split price policy** | Phase 0.5 | every downstream number |

---

## 8. Quick-reference: phase → first concrete task

| Phase | First task |
|---|---|
| 0 | Pure-signal refactor + Strategies-tab audit + completeness fix |
| 0.5 | Resolve Polygon tier + add delist fields + seed universe |
| 1 | Design ledger schema **with the pinned exit rule** + log all 3 surfaces |
| 2 | Adapter: pure signal → `ml-training/backtesting/BaseStrategy` |
| 3 | Component-ablation switch + stop rule → freeze `signal_version=v2` |
| 4 | Cost model wired into the ledger outcome writer |
| 5 | Feed ledger rows into `create_labels.py` |
| 6 | Write the live research doc with the edge-decay kill threshold |
| 7 | Meta-labeling model on ledger outcomes (direction → take/skip) |

---

*This document is the contract between "nicely-looking" and "real." Every feature
request is evaluated against §4 (Do NOT) and §5 (the scoreboard). If it doesn't
move the scoreboard per-regime, net of costs, it waits.*
