# Education & the Search for Edge

**Why this doc exists:** every signal we've tested on liquid US large-cap daily data
came back null — 8/8 standalone signal families, the GA weight-optimization, and the
156-feature joint ML model (cross-regime AUC 0.504 in the 2022 bear). That is *not* a
bug; it is exactly what finance theory predicts. This doc maps the theory that explains
our nulls, points at where real edge actually lives, and lays out the principled
architecture (momentum → meta-labeling → honest methodology) for the next attempts.

---

## 1. Why we keep finding nulls (the theory)

- **Efficient Market Hypothesis (EMH).** Public, daily, liquid large-cap is the *most*
  efficient corner of the market — the one place where EMH holds strongest. Discretionary
  retail-scale prediction here is hard for *everyone*, institutions included.
- **Anomaly decay.** *McLean & Pontiff (2016), "Does Academic Research Destroy Stock
  Return Predictability?"* — published anomalies lose **~30% of power out-of-sample and
  ~50% after publication**, because arbitrage trades them away. This is *why* Sloan
  accruals and Novy-Marx profitability didn't replicate for us: they were real 20+ years
  ago and have been arb'd since.
- **Backtest overfitting.** *Bailey & López de Prado* — the **deflated Sharpe ratio** and
  **probability of backtest overfitting (PBO)**. With enough parameter combinations you
  will always find something that "worked" in-sample. Our GA #10/#13 and the "+9.71%
  TabNet" result are textbook cases. Rule of thumb: among **N** random strategies, the
  best shows ≈ **√(2·ln N)** Sharpe *by luck alone*.
- **Limits to arbitrage.** *Shleifer & Vishny (1997)* — even *real* mispricings are hard
  to monetize (fundamental risk, noise-trader risk, implementation costs). Sets honest
  expectations for any edge we do find.

**Implication:** stop blending more of the same daily features. The realistic edge sources
are (a) a **different market** (small caps, international, crypto — less efficient),
(b) a **different horizon** (intraday/microstructure — needs order-flow data),
(c) **momentum / factors done as a portfolio**, or (d) **reframing ML as meta-labeling**
over a primary that has a sliver of edge.

---

## 2. The three pillars we can actually build on

### Pillar A — Time-series momentum (the candidate primary)
*Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum"; Jegadeesh & Titman (1993).*

- **The idea:** hold a position proportional to the asset's *own* past return. Go long
  when price > its N-day MA (or 12-month return > 0); **volatility-scale** the size so each
  name carries equal risk (target vol per position, e.g. 10% annualized).
- **Why it survives:** trend-following is the single most robust documented out-of-sample
  anomaly. It's also mechanically different from score-blending — it asks "is this asset
  trending?", not "does this feature bag point up?".
- **Honest caveat:** TSMOM shines across a *diversified portfolio of asset classes*
  (AQR's trend funds). Long-only on a single country's large-caps is thinner — but it's
  the most likely thing to show *any* edge on the data we already hold.
- **Fits our framework as:** a standalone probe now → `engine_3` / a primary later. Reuses
  `prepare_backtest` (prices), `compute_metrics` + SPY alpha, and the MA/ADX machinery in
  `MarketRegimeService`. Does **not** touch the live engines.

### Pillar B — Meta-labeling (the non-redundant ML architecture)
*Marcos López de Prado (2018), "Advances in Financial Machine Learning" — Ch. 3 (meta-labeling),
Ch. 7 (purged CV), Ch. 4 (sample weighting).*

- **The idea:** split the job. A **primary** model (rules / domain knowledge) decides
  *direction* ("buy this"). A **secondary ML model** (the "meta-label") decides, *given the
  primary fired*, whether to **take the trade and at what size** — a binary side/filter
  classifier, **not** a direction predictor.
- **Why this resolves the redundancy worry:** two models are redundant only when they
  answer the **same question from the same data**. The meta-label answers a *different*
  question ("is the primary trustworthy here?"), so it is **not** redundant — and it learns
  *when* our rules work (a function of market state, recent hit-rate, vol regime).
- **Fits our framework as:** a **wrapper** over an existing engine — doesn't replace it.
  Training labels come free from our backtest trade ledger + the live `paper_signal_log`
  ("did engine_X's BUY at T profit over horizon H?"). Build this **only after** a primary
  (momentum) shows edge — meta-labeling a null primary is pointless.

### Pillar C — Honest methodology (so we trust results)
*Bailey & López de Prado (2014), "The Deflated Sharpe Ratio"; López de Prado (2018) Ch. 11–12.*

- **Probabilistic Sharpe Ratio (PSR):** P(true Sharpe > 0 | observed), accounting for
  return skew/kurtosis and sample length. > 0.95 ⇒ "probably real."
- **Deflated Sharpe:** adjust the observed Sharpe for the **number of configs tried (N)**.
  If the best config's Sharpe doesn't clear ≈√(2·ln N), it's consistent with luck.
- **Purged + embargoed CV:** when cross-validating time series, drop labels that overlap
  the train/test boundary (we hit this exact leakage with the TabNet single-split result).
- **Fits our framework as:** an **evaluation layer** over the backtester — fold these into
  `compute_metrics` / the GA's overfit guard so no "winner" is trusted un-deflated.

---

## 3. Concrete plan (order matters)

1. **Run the TSMOM probe** (`scripts/tsmomentum_probe.py`) — the decisive "is there *any*
   edge in our data" test we have not run. Long-only, vol-scaled, several lookbacks, with
   deflated-Sharpe honesty and a regime split (2022 bear vs 2024-26 bull).
2. **If momentum shows edge (PSR > 0.95, survives both regimes):** promote to `engine_3` and
   build the meta-label wrapper (Pillar B) over it.
3. **If momentum is null too:** the large-cap-daily ceiling is conclusively confirmed across
   *every* documented approach. Pivot fully to the honest framing: a defensive participation
   tool (the engine already sits ~cash in bears), and redirect edge-hunting to a different
   market/horizon.

---

## 4. Curated reading list (in order)

**Start here (rewires how you think about ML-in-finance):**
- Marcos López de Prado — *Advances in Financial Machine Learning* (2018). Read Ch. 1–3, 7,
  11–12 minimum. Companion talks: "The 10 Reasons Most Machine Learning Funds Fail."
- Bailey & López de Prado (2014), "The Deflated Sharpe Ratio" (short paper).

**Why edge is scarce:**
- McLean & Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?"
- Shleifer & Vishny (1997), "The Limits of Arbitrage."

**What actually has documented OOS edge:**
- Jegadeesh & Titman (1993) — cross-sectional momentum.
- Moskowitz, Ooi & Pedersen (2012) — *Time Series Momentum* (trend-following).
- Fama & French (1992/1993, 2015) — factor model (size, value, profitability, investment).
  Note these are **portfolio-level, long-short, months-years** — a different product than
  per-stock weekly swing.

**Always useful:** AQR's trend-following papers for how momentum is actually sized and
risk-equalized in practice.

---

*Status of each pillar: A (momentum) — probe RUN (2026-07-26). B (meta-labeling) —
designed, build gated on A. C (methodology) — PSR/deflated-Sharpe folded into the probe;
full purged-CV + PBO harness pending. See STATUS.md.*

---

## Appendix: TSMOM probe result (2026-07-26)

`scripts/tsmomentum_probe.py`, 50 stocks, 5y (2021-07..2026-07), long-only, vol-scaled
(target 10% ann), 5bps round-trip cost, decision at T close / earned at T+1 (no look-ahead).

| lookback | annRet% | Sharpe | PSR0 | maxDD% | bearSh | bullSh |
|---|---|---|---|---|---|---|
| 21d | 3.7 | 0.26 | 0.69 | −30.7 | −0.87 | 0.89 |
| 63d | 3.0 | 0.21 | 0.65 | −30.2 | −1.37 | 0.96 |
| 126d | 8.9 | 0.65 | 0.82 | −19.9 | −0.22 | 0.92 |
| **252d** | **12.8** | **1.07** | **0.85** | **−16.3** | **−0.01** | **1.57** |

Luck threshold (4 configs, 5y) ≈ 0.74. **Verdict: NULL** — best Sharpe 1.07 clears the luck
bar but **PSR0 0.85 < 0.95**, and the edge is **entirely regime-dependent**: 2022 bear
Sharpe −0.01 (no protection), 2024-26 bull Sharpe 1.57 (all of it). Short lookbacks
whipsawed (bear −0.87/−1.37). Same regime-overfit signature as GA #10/#13 and the TabNet
illusion — the "edge" is bull-market uptrend participation, not robust skill. *Caveat: the
5y SPY benchmark was a truncated fetch (unreliable); the verdict does not depend on it.*

**Notable contrast:** unlike engine_1 (which sat ~cash: +0.06% in the 2024-26 bull),
252d TSMOM *participated* in the bull (Sharpe 1.57). So momentum is a better
**bull-participation** mechanism than the rule engine — but it is still not a robust
cross-regime edge (no bear protection, PSR < 0.95). Borderline, not a promote.

**Next:** before fully dismissing, one honest walk-forward / OOS check (train lookback on
2021-23, test 2024-26) would confirm whether even the bull-participation is stable or just
in-sample. If it survives → candidate primary for meta-labeling (Pillar B). If not → the
large-cap-daily ceiling is confirmed across every documented approach.

**Walk-forward OOS — RUN (2026-07-26).** Select lookback on TRAIN (2021-07..2024-01,
includes the 2022 bear) → 252d (train Sharpe 0.38, edging 126d's 0.37 by a noise-level 0.01).
Evaluated on held-out TEST (2024-26 bull): **252d test Sharpe 1.57, +68.7%, PSR 0.75** — and
it *was* also the test-best (ranking stable, beats the 0.96 median). Script verdict:
SURVIVES. **Honest tempering:** the train signal is weak and the selection margin is
razor-thin (fragile), and the test is a single bull (we cannot OOS-test the bear — only one
exists). So: **borderline-positive, not convincing robust edge.**

**Key reframe:** this splits the project's two problems. (1) **Bull participation** —
momentum works (engine_1 fails at this: +0.06% in the same bull vs momentum's +68.7%).
(2) **Bear protection** — still unsolved (momentum −0.01 in 2022; the overlay didn't help;
engines survive only by sitting in cash). Momentum = "bull-beta done right," the most
promising thing found in the whole investigation, but not cross-regime alpha. Candidate
primary for meta-labeling *only if* paired with a real bear-defense mechanism.
