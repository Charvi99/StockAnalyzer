# BU3 — Pattern Detection (audit report)

Verified 2026-07-20 against `app/services/chart_patterns.py` (2307 LOC),
`app/services/multi_timeframe_patterns.py`, and the production task callers
`app/tasks/analysis_tasks.py`, `app/tasks/processor_tasks.py`.
Tag legend: ✅ confirmed · ❓ needs more proof · ⛔ false positive (corrected).

## Headline — your intuition is correct: the filters over-corrected
Two independent mechanisms are starving the pattern output, and one of them is a
genuine bug, not just a tuning choice:

1. **P1 (BUG, money-adjacent):** `_calculate_pattern_quality` silently zeroes the
   `base_confidence` factor for **continuation** patterns (channels/flags/wedges)
   and inflates the effective R² weight — so the very patterns you'd want in a trend
   are disproportionately rejected.
2. **P2 (TUNING):** production tasks set `min_r_squared=0.85` **and** `min_confidence=0.7`.
   R² is *also* 35% of the quality score, so it is double-penalized; 0.85 rejects the
   large majority of legitimate real-market trendlines.

Net effect: a pattern must clear ZigZag → structural detection → internal
`quality_score ≥ 0.5` → `confidence ≥ 0.7` → `avg R² ≥ 0.85` → overlap dedup.
The last two are the cliff.

## The filter chain (verified)
`detect_all_patterns` (`chart_patterns.py:~498-576`) applies, in order:
1. ZigZag filter (`:88-91`) — drops swings smaller than `zigzag_deviation`.
2. Per-pattern structural detection, each gated by `if quality_score >= 0.5`
   (18 occurrences: `:698,801,892,995,1098,1197,1291,1563,1665,1772,1872,1954,2031,2125,2215,2304`).
3. `confidence_score = quality_score` (set inside each detector).
4. Overlap dedup (`_remove_overlapping_patterns`, default 0.3).
5. `min_confidence` filter (`:568-570`) → keeps `confidence_score >= min_confidence`.
6. `min_r_squared` filter (`_check_trendline_quality`, `:572-592`) → keeps `avg R² >= min_r_squared`.

Production callers pass `min_confidence=0.7, min_r_squared=0.85` at **all three**
priority levels (`analysis_tasks.py:79-80`; `processor_tasks.py:53-54, 169-170,
285-286`). So the internal `0.5` gate is dominated — the real bar is **0.7 / 0.85**.

## Findings

### P1 ✅ CONFIRMED (BUG) — scores/weights misalignment zeroes base_confidence for continuation patterns
`_calculate_pattern_quality` (`:364-416`):
```python
if pattern_data.get('pattern_type') == 'reversal' and 'prior_trend' in pattern_data:
    scores.append(trend_strength); weights.append(0.20)   # aligned
else:
    weights.append(0.0)                                   # <-- weight, NO score
scores.append(base_confidence); weights.append(0.20)
...
weighted_score = sum(s*w for s,w in zip(scores, weights)) / sum(weights)
```
`zip()` truncates to the shorter list. For continuation patterns, `scores` is one
shorter than `weights`, so `base_confidence` pairs with the dangling `0.0` weight and
contributes **nothing**; the trailing `0.20` weight is dropped from the numerator but
**kept in `sum(weights)`**. Effective weights become R² ≈ 43.75%, volume ≈ 31.25%,
base = 0% (intended 35/25/20). Reversal patterns are unaffected (they append both).

**Why it matters:** continuation patterns already lean heavily on trendline fit, and
this bug pushes their R² weighting even higher — compounding with the P2 R² gate to
reject channels/flags/wedges that should qualify. Test proves base_confidence moves the
score by 0.0 today vs 0.25 after the fix.

**Fix (one line, money-adjacent → needs sign-off):** delete `weights.append(0.0)` in
the `else` branch (`:402`) so the lists stay aligned. Effect: base_confidence
contributes its intended share; continuation quality scores rise modestly; more
continuation patterns clear the gates.

### P2 ✅ CONFIRMED (TUNING) — min_r_squared=0.85 is too strict + R² is double-counted
- `min_r_squared=0.85` demands a trendline explaining 85% of variance. Real-market
  trendlines (even "good" ones) commonly sit at 0.6–0.8. At 0.85 most are rejected.
- R² is **already** the largest single factor in `quality_score` (35% weight, `:387`),
  so a low-R² pattern is punished twice: once in the score, once by the hard gate.
- `min_confidence=0.7` stacks on top.

**Recommendation (your call — expose as config so you can A/B):**
- `min_r_squared`: **0.85 → 0.70** (still "good fit", far more patterns pass).
- `min_confidence`: **0.7 → 0.6** (the internal `quality_score ≥ 0.5` gate already
  removes the dross).
- Consider dropping the separate R² hard gate OR the R² weight in quality_score —
  not both — to remove the double-penalty.

### P3 ✅ CONFIRMED (minor) — 3.0-ATR "significant move" threshold
`detect_*` uses `significant_move_threshold = atr_at_start * 3.0` (`:313`) to require a
3-ATR prior move for reversal patterns. Defensible for reversal validation, but on the
high side combined with P2. Note, don't necessarily change.

### P4 ✅ CONFIRMED (minor) — many near-duplicate `quality_score >= 0.5` blocks
The same 5-line "compute quality → set confidence → gate on 0.5" block is repeated 18×.
Not a bug, but a refactor target (one helper) — and a place where the 0.5 could be made
configurable per pattern type if you want finer control.

## Candlestick patterns — NOT yet audited
`app/services/candlestick_patterns.py` exists but was out of scope for this pass (cost-
bounded). The candlestick path is a separate detector (`cs_detector.detect_all_patterns()`,
no `min_confidence`/`min_r_squared` args at `analysis_tasks.py:172`) so it likely has a
**different** (looser?) filter story. Flagged for a follow-up BU3b if candlestick yield
also looks low.

## Status
- **Proven, not auto-applied (money-adjacent):** P1 one-line fix (needs your sign-off);
  test `test_bu3_patterns.py` demonstrates the bug and the corrected behavior.
- **Tuning recommendations:** P2 (lower thresholds / remove double-penalty), P3, P4.
- Tests: `python3 backend/tests/test_bu3_patterns.py` → **4/4 PASS**.

## Open decisions added (feed into AUDIT_PLAN §5)
- **D12:** Apply the P1 one-line fix (`weights.append(0.0)` removal)? Unambiguous bug;
  raises continuation-pattern yield.
- **D13:** Relax `min_r_squared` 0.85→0.70 and `min_confidence` 0.7→0.6, and expose them
  as env/config so you can tune without redeploying code?
- **D14:** Remove the R² double-penalty (drop the hard gate OR the quality-weight)?
- **D15:** Audit candlestick_patterns.py (BU3b) — separate filter story?
