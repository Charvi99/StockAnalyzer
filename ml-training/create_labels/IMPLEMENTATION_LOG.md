# Alpha Label Implementation Log

**Project:** StockAnalyzer ML - Alpha Label Migration
**Start Date:** 2026-02-05
**Status:** Phase 1 - Setup & Diagnosis
**Owner:** ML Team

---

## Overview

**Goal:** Migrate from beta prediction (market timing) to alpha prediction (stock selection)

**Success Metrics:**
- Win rate: 55-58% (target), 60-65% (stretch)
- Annual alpha: +4-7% (target), +10-13% (stretch)
- Sharpe ratio: 1.2-1.6
- Insider features in top 20 importance

---

## Decision Log

### Decision 1: Keep SPY Features Initially

**Date:** 2026-02-05
**Decision:** Keep SPY features during initial alpha implementation
**Rationale:**
- A/B testing needs baseline
- SPY provides market context
- Can remove later if confirmed harmful
- Better to have data than assumptions
**Status:** ✅ Implemented
**Reversible:** Yes

### Decision 2: Target 55-58% Win Rate

**Date:** 2026-02-05
**Decision:** Aim for 55-58% win rate instead of 65%
**Rationale:**
- 65% is extremely ambitious for 20-day stock picking
- Professional hedge funds target 55-60%
- Focus on risk-adjusted returns
- 55% with 2:1 risk-reward = profitable
**Status:** ✅ Confirmed
**Adjustable:** Can aim higher if initial results strong

### Decision 3: Binary Labels First

**Date:** 2026-02-05
**Decision:** Start with binary alpha labels
**Rationale:**
- Simpler and more interpretable
- Easier to validate
- 5-class adds complexity without clear benefit yet
**Status:** ✅ Implemented
**Extensible:** 5-class ready when needed

### Decision 4: Long-Only Strategy

**Date:** 2026-02-05
**Decision:** Maintain long-only approach
**Rationale:**
- Matches user's trading style
- Simpler risk management
- Focus on finding winners
**Status:** ✅ Confirmed

### Decision 5: 20-Day Lookahead

**Date:** 2026-02-05
**Decision:** Use 20-day lookahead
**Rationale:**
- Matches user's swing trading timeframe
- Short enough for signal count
- Long enough for meaningful moves
**Status:** ✅ Confirmed

---

## Implementation Timeline

### Phase 1: Diagnosis & Baseline (Week 1)

**Status:** In Progress

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Create folder structure | ✅ Complete | 2026-02-05 | create_labels/ created |
| Write diagnostic script | ✅ Complete | 2026-02-05 | 01_diagnose_current_labels.py |
| Write alpha label script | ✅ Complete | 2026-02-05 | 02_create_alpha_labels.py |
| Run diagnostics | ⏳ Pending | - | Awaiting execution |
| Generate alpha labels | ⏳ Pending | - | After diagnostics |
| Train comparison models | ⏳ Pending | - | After alpha labels |

**Expected Completion:** 2026-02-07

### Phase 2: Feature Engineering (Week 2)

**Status:** Not Started

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Engineer insider features | ⏳ Pending | - | Enhanced transformations |
| Create regime features | ⏳ Pending | - | Market/volatility regimes |
| Add interaction features | ⏳ Pending | - | Insider × technical |
| Retrain with new features | ⏳ Pending | - | Compare importance |

**Expected Start:** 2026-02-08
**Expected Completion:** 2026-02-14

### Phase 3: Advanced Models (Week 3-4)

**Status:** Not Started

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Implement stacking ensemble | ⏳ Pending | - | XGB + Cat + LightGBM |
| Add TabNet | ⏳ Pending | - | Attention-based |
| Final evaluation | ⏳ Pending | - | Full comparison |
| Production deployment | ⏳ Pending | - | If results good |

**Expected Start:** 2026-02-15
**Expected Completion:** 2026-02-28

---

## Test Results

### Diagnostic Tests (Phase 1)

**Status:** Not yet run

| Test | Expected Result | Actual Result | Pass/Fail |
|------|----------------|---------------|-----------|
| Feature Importance | SPY = 40%+ top 10 | - | - |
| Label-SPY Correlation | r > 0.60 | - | - |
| Ablation Study | AUC drop 20+ pts | - | - |
| Prediction-SPY Correlation | r > 0.50 | - | - |

### Model Comparison (Phase 1)

**Status:** Not yet run

| Model Type | Expected AUC | Actual AUC | Insider Used? |
|------------|--------------|------------|---------------|
| Current (beta) | 76% | - | No (0-1%) |
| Alpha + SPY | 56-60% | - | Partial (5-15%) |
| Alpha - SPY | 52-56% | - | Yes (15-25%) |

---

## Label Distribution Tracking

### Current Labels (Binary - Absolute Returns)

```
BUY (1):         ~40-45%
DON'T BUY (0):   ~55-60%
```

### New Alpha Labels (Binary - 2% Outperformance)

```
BUY (outperforms SPY by 2%+):     ~35-40%
DON'T BUY (underperforms):        ~60-65%
```

### New Alpha Labels (5-Class)

```
STRONG OUTPERFORM (>3%):          ~10%
OUTPERFORM (1-3%):                ~25%
MARKET PERFORM (-1% to 1%):       ~30%
UNDERPERFORM (-3% to -1%):        ~25%
STRONG UNDERPERFORM (<-3%):       ~10%
```

---

## Key Insights & Learnings

### Week 1 (2026-02-05)

**Insight 1:** Folder structure created with comprehensive documentation
- README.md with full strategy
- Diagnostic script for validation
- Alpha label generation script
- Implementation log (this file)

**Insight 2:** Decision to keep SPY initially allows A/B testing
- Can measure exact impact of SPY features
- Provides baseline for comparison
- Reversible decision

**Insight 3:** Target win rate adjusted to realistic levels
- 55-58% instead of 65%
- Based on professional standards
- Focus on Sharpe ratio over win rate

---

## Risk Register

### Risk 1: AUC Drop Perception

**Risk:** Stakeholders see 76% → 54% AUC drop as failure
**Mitigation:**
- Document expected drop in advance
- Explain alpha vs beta difference
- Focus on real trading metrics (Sharpe, alpha)
**Status:** Documented in README

### Risk 2: Insider Features Still Ignored

**Risk:** Even with alpha labels, insider features not used
**Mitigation:**
- Phase 2 feature engineering planned
- Remove SPY if needed
- Enhanced transformations ready
**Status:** Mitigation planned

### Risk 3: Win Rate Below Target

**Risk:** Can't achieve 55% win rate even with alpha labels
**Mitigation:**
- Adjust target if needed
- Focus on risk-adjusted returns
- May need more features or longer timeframe
**Status:** Monitor during Phase 1

### Risk 4: Overfitting to Bull Market

**Risk:** Model only works in up markets
**Mitigation:**
- Regime-specific validation
- Test on bear/ranging periods
- Regime features in Phase 2
**Status:** Mitigation planned

---

## Configuration History

### Alpha Label Config (2026-02-05)

```yaml
binary:
  alpha_target: 0.02      # 2% outperformance
  lookahead: 20           # 20 days
  beta_adjusted: false    # Simple alpha

5class:
  strong_outperform: 0.03
  outperform: 0.01
  market_perform: -0.01
  underperform: -0.03
```

---

## Open Questions

### Question 1: What If Diagnostics Don't Confirm Beta Prediction?

**Status:** Open
**Impact:** High - Would invalidate entire approach
**Decision:** Run diagnostics first before proceeding
**Date:** To be answered 2026-02-06

### Question 2: Should We Implement Beta-Adjusted Alpha?

**Status:** Open
**Impact:** Medium - Could improve accuracy
**Decision:** Test simple alpha first, add beta-adjusted if needed
**Date:** To be answered after Phase 1 results

### Question 3: What Alpha Target is Optimal?

**Status:** Open
**Impact:** High - Affects label distribution
**Options:** 1%, 2%, 3% outperformance
**Decision:** Start with 2%, adjust based on results
**Date:** Continuous evaluation

---

## Next Steps (Immediate)

1. **Review folder structure** - Confirm all scripts created
2. **Make scripts executable** - `chmod +x *.py`
3. **Run diagnostic script** - Confirm beta prediction
4. **Generate alpha labels** - Create new label files
5. **Train comparison** - Validate approach

---

## Contact & Support

**ML Team:** Available for questions
**Documentation:** See README.md in each folder
**Issue Tracking:** Update this log with any problems

---

**Last Updated:** 2026-02-05
**Next Review:** After Phase 1 completion
**Status:** On Track ✅
