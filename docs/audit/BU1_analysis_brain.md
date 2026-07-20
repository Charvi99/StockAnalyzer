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
- B3, B4: documented, need a decision / DB check.
- Still to audit in BU1: `_check_weekly_trend` override edge cases, `analysis.py` eager-load query (`:803`), the weight blending in `_get_recommendation_for_stock`.
