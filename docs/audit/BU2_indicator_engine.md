# BU2 — Indicator Engine (audit report)

Verified 2026-07-20 against `backend/app/services/technical_indicators.py` (2983 LOC).
Tag legend: ✅ confirmed · ❓ needs more proof · ⛔ false positive (corrected).

## Headline
The two scariest-sounding candidates from the plan — **look-ahead bias** at Bollinger
(`:222`) and VWAP (`:828`) — are **⛔ false positives**. No `shift(-n)` (future-leak)
exists anywhere in the file; the signals compare the last close to a band/average
computed from data **through that same bar inclusive**, which is the correct causal
definition. The real issues are **perf** (copy churn) and two **design-level**
correctness gaps (RSI parity, VWAP anchoring).

## Environment fact (read before trusting any indicator value)
`TA-Lib==0.4.32` is listed in `backend/requirements.txt` and every method has a
`TALIB_AVAILABLE` fast-path, **but `import talib` fails in this environment**
(`ModuleNotFoundError: No module named 'talib'`). That means:
- Here, **every indicator runs the pandas fallback**, not the TA-Lib fast-path.
- ⚠️ **Action required (verify, not fix):** confirm the Docker runtime actually
  installs the TA-Lib C library + Python bindings. If the container also lacks it,
  the "10–50x faster" claims in the docstrings are fiction and *all* indicator
  values come from the hand-written pandas formulas audited below.

## Findings

### B5 ✅ CONFIRMED (perf) — every indicator method copies the whole frame
36 `df = data.copy()` calls (one per `calculate_*` method). `calculate_all_indicators`
already does `df = data.copy()` at `:2510`, then chains ~30 sub-methods each of which
copies again (`df = TechnicalIndicators.calculate_rsi(df)` → another full copy inside).
Each copy duplicates **all** accumulated columns (OHLCV + every indicator added so far),
so cost grows super-linearly as the pipeline progresses: copy #30 carries ~60+ columns.

**Blast radius:** every HTTP recommendation and every Celery comprehensive analysis.
With 200 bars × ~60 columns × ~30 copies, that is roughly **360K cell-copies of pure
overhead per stock per run**, and the frame is thrown away each call (no caching).
This is the single biggest BU2 perf lever.

**Fix (deferred — needs sign-off):** collapse to **one** copy: have `calculate_all_indicators`
copy once and have the sub-methods mutate-and-return in place (drop the per-method
`data.copy()`). This changes the per-method contract from "never mutates input" to
"consumes input" — safe *inside* the pipeline, but every external caller that reuses
its DataFrame after calling a single `calculate_*` would break. Need a call-site audit
before applying. **No code changed yet.**

### B6 ✅ CONFIRMED (correctness, live) — pandas RSI is non-canonical; div-by-zero self-corrects
`calculate_rsi` fallback (`:74-78`):
```python
gain = delta.where(delta>0,0).rolling(window=period).mean()   # SMA of gains
loss = -delta.where(delta<0,0).rolling(window=period).mean()  # SMA of losses
rs  = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))
```
Two distinct concerns:

1. **Parity gap (real).** Canonical Wilder RSI uses an **EMA/Wilder smoothing** of
   gains/losses (`alpha=1/period`). This code uses a plain **SMA**. TA-Lib uses Wilder.
   → When the pandas fallback runs (i.e. this env, and any env without the C lib), RSI
   values systematically differ from the TA-Lib reference and from what every charting
   platform reports. Overbought/oversold trips at the wrong bars. One of the
   highest-weight inputs (23% technical, and RSI is Phase-1). **Documented; not
   auto-fixed** (fixing = port Wilder smoothing — money-adjacent, needs sign-off).

2. **Div-by-zero (self-correcting — ⛔ NOT a bug).** `rs = gain/loss` with `loss==0`
   yields `inf`, then `100/(1+inf)=0`, so `rsi = 100`. That is the *correct* RSI for a
   window with zero down-bars. The `gain==0 and loss==0` case yields NaN and is already
   skipped by `not np.isnan(latest_rsi)`. No inf reaches the stored `rsi` column.
   Original div-zero hypothesis was a **false positive**; recorded to calibrate trust.

### B7 ✅ CONFIRMED (semantic, low-med) — VWAP anchored to an arbitrary fetch window
`calculate_vwap` (`:824`):
```python
df['vwap'] = df['tp_volume'].cumsum() / df['volume'].cumsum()
```
This is a **cumulative** VWAP from the first bar of whatever slice was passed in. The
anchor is therefore the fetch `limit`, not a trading session:
- `recommendation_engine` fetches `.limit(60)` → VWAP = 60-bar volume-weighted mean.
- `market_regime` fetches `.limit(100)` → VWAP = 100-bar mean.
- Same stock, same instant, **different VWAP, different BUY/SELL** depending on which
  caller asked. VWAP is an intraday/session-anchored metric; on daily bars a
  cumulative-from-arbitrary-start value is a misuse, and its window-dependence makes
  the signal non-reproducible. Low weight in the final blend (one signal among ~20),
  but semantically wrong and worth a decision (fixed-window rolling VWAP, or drop on
  daily bars). **Not look-ahead** (no future data) — that part of the original
  hypothesis was a false positive.

## False positives (corrected — same discipline as BU1)
- ⛔ **Look-ahead at Bollinger `:222`.** Compares `close[-1]` to `bb_upper[-1]` /
  `bb_lower[-1]`, where the bands are `rolling(20).mean() ± 2·rolling(20).std()` — i.e.
  a function of closes `[−19 … −1]`, **inclusive of the last bar**. That is the textbook
  definition of a Bollinger touch, not future leakage. Correct as written.
- ⛔ **Look-ahead at VWAP `:828`.** `vwap[-1]` uses `cumsum` through bar −1 inclusive;
  `close[-1]` vs `vwap[-1]` is causal. The real VWAP problem is window-anchoring (B7),
  not lookahead.
- ⛔ **RSI div-by-zero `:70,77`.** See B6(2) — self-corrects to RSI=100.

## `generate_recommendation` (HTTP path) — spot-checked, OK
`:2582` reads `latest = df.iloc[-1]` and accesses via `latest.get('rsi_signal')`,
`latest['rsi']`, etc. — correct Series access, mirrors the BU1 fix shape. Uses the
`*_signal`/`*_reason` columns populated by each `calculate_*` method. No dict-vs-DataFrame
class of bug here (that was BU1/B1, Celery path only).

## Status
- B5, B6, B7: **documented, not fixed** — all three are either perf refactors or
  money-adjacent semantics needing a decision. Safe fixes preferred over clever ones.
- Two false positives closed (look-ahead ×2), one downgraded-to-non-bug (RSI div0).
- **Verify before next unit:** is the TA-Lib C lib actually present in the Docker
  runtime? Determines whether B6's parity gap is live in prod or only in dev.

## Open decisions added (feed into AUDIT_PLAN §5)
- D6: Apply the one-copy refactor (B5)? Requires call-site audit for single-method
  callers that reuse their frame.
- D7: Port Wilder smoothing into the pandas RSI fallback (B6), or mandate TA-Lib at
  deploy time?
- D8: VWAP on daily bars — fixed-window rolling, session-anchored, or drop (B7)?
