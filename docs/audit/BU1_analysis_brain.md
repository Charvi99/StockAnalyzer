# BU1 — Analysis Brain (audit report)

Verified 2026-07-20 against real code. Tag legend: ✅ confirmed · ❓ needs more proof · ⛔ false positive (corrected).

## Findings

### B1 ✅ CONFIRMED — RSI/MACD/SMA scoring silently dead in Celery path
`recommendation_engine.generate_final_recommendation` treated the DataFrame from
`calculate_all_indicators` (returns `pd.DataFrame`, `technical_indicators.py:2497`)
as a dict: `indicators['rsi']['value']` (`:153`), `indicators['macd'].get('signal')`
(`:162`), `indicators['sma_50']['value']` (`:171`). Indexing a Series with `'value'`
raises `KeyError`, swallowed by the bare `except` at `:280`. **Effect:** RSI, MACD and
golden/death-cross never contributed to the `technical_indicators` component (23% weight)
in the Celery comprehensive-analysis path. Only the Phase-2/3 `*_signal` columns scored.
**Blast radius:** `analysis_tasks.py` only — the HTTP route uses a different path
(`TechnicalIndicators.generate_recommendation(df)`), which is correct.
**Fix applied:** read via `.iloc[-1]` with correct columns (`rsi`, `macd_trend`,
`sma_50`, `sma_200`). Test: `backend/tests/test_bu1_fixes.py`.

### B2 ✅ CONFIRMED (downgraded) — ADX/DI division not zero-guarded
`market_regime.calculate_adx` divided by `atr` (`:69-70`) and `(plus_di+minus_di)`
(`:73`) with no guard. On a purely flat bar this yields NaN (0/0, benign → 'range');
the inf case (numerator>0, denom=0) is rarer but would poison ADX. **Fix applied:**
`.replace(0, np.nan)` before dividing — guarantees no `inf` reaches ADX. This is
robustness hardening, not a confirmed common-case misclassification.

### B3 ✅ CONFIRMED — TZ-naive vs TZ-aware datetime (NOT fixed — needs DB check)
`analysis_completeness.py` uses tz-naive `datetime.utcnow()` (`:62,128,208,293`) and
subtracts `stock.last_*`. If any `last_*` column is tz-aware → `TypeError`. Inconsistent
with `recommendation_engine.py` (tz-aware). **Not auto-fixed:** requires confirming the
column types in `models/stock.py` to pick the right direction (make all tz-aware, or all
naive). Tracked in AUDIT_PLAN §5.

### B4 ✅ CONFIRMED — two divergent recommendation engines
HTTP path → `TechnicalIndicators.generate_recommendation(df)`; Celery path →
`generate_final_recommendation`. Different scoring, drift risk. Architectural — needs a
decision (consolidate or formally document both).

## False positives (corrected — builds trust in the process)
- ⛔ `recommendation_engine.py:88` div-by-zero — **guarded** by `if bullish+bearish > 0` (`:87`). Same for candlestick (`:108`).
- ⛔ `analysis.py:109` MA-slope div-by-zero — line 109 is a docstring; the real `calculate_ma_slope` is **guarded** (`market_regime.py:108`).
- ⛔ `_detect_swing_points` "O(n²)" — it is O(5·n) (`analysis.py:124`), negligible.

## Status
- B1, B2: fixed + tested (this branch).
- B3: documented, needs a DB check (naive vs aware `last_*` columns) — see AUDIT_PLAN §5.
- B4: resolved as a deliberate **A/B pair** (decision D35, below) — not collapsed.

### D35 — recommendation engines are an A/B pair (defer unification to post-ledger)
The two engines are **two different products**, not duplicates:
- **Engine #1** — `recommendation_engine.generate_final_recommendation(db, stock_id)`:
  systematic 6-factor weighted score (chart 28% / candlestick 14% / technical 23% /
  sentiment 13% / regime 12% / dividend 10%), BUY/SELL threshold 0.3. Used by the
  background `analyze_stock_comprehensive` task to set `Stock.analysis_score`.
- **Engine #2** — `analysis._get_recommendation_for_stock(stock, db)` (~717 LOC incl.
  helpers): realtime, swing-trading-aware — dynamic weights, weekly-trend override,
  swing-point filters, multi-layer confidence adjustment. Returns the frontend
  `RecommendationResponse`.

**Decision:** keep both until the **paper-trading ledger** can score each on real data
(hit-rate / R-multiple / drawdown), then unify around the winner with evidence — not by
guessing. A low-risk `regime_to_score()` helper extraction exists but is deliberately
NOT done: it would couple the two products we're keeping separate.

**Stage 4A (layering fix) deferred:** Engine #2's ~717 LOC lives inline in a route
(`api/routes/analysis.py:375`) and `services/order_calculator.py:99` imports it *from the
route* (a service→route inversion). The fix — a behavior-preserving move to
`services/realtime_recommendation.py` — is queued as a focused follow-up (largest,
most transcription-sensitive stage; done fresh rather than rushed). The inversion is a
smell, not a bug — the code works today.
