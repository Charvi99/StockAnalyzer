# BU5 — Risk / Order Calculation (audit report)

Verified 2026-07-20 against `app/utils/risk_utils.py`, `app/services/risk_management.py`,
`app/services/order_calculator.py` (1122 LOC), `app/api/routes/risk_management.py`.
Tag legend: ✅ confirmed · ❓ needs more proof · ⛔ false positive (corrected).

## Headline
There are **two parallel, live risk implementations** with near-identical math — the same
two-sources-of-truth hazard as B4 (recommendation engines) and the quiverquant v1/v2 pair.
The scariest items are **latent crashes** (unguarded division) on invalid input, which are
fixed here as trivial guards. Two money-adjacent semantic issues are **documented only**
(abs-masked R:R, tz-naive) pending your sign-off.

## Live call graph (verified by grep, not assumed)
```
analysis.py route (3 endpoints)  ─► OrderCalculatorService ─► risk_utils.*  (functions)
risk_management.py route (4 ep)  ─► RiskManager class + calculate_risk_metrics_for_pattern
                                   (near-verbatim copy of risk_utils — R7)
```
Both paths are live and serve real HTTP endpoints. `risk_utils` is imported by exactly one
caller (`order_calculator.py:17`); `RiskManager` by exactly one caller (the risk route).
`order_calculator._calculate_levels` (v1, `:973`) has **no caller** — only `_calculate_levels_v2`
is used. Dead code.

## Findings

### R1 ✅ CONFIRMED + FIXED — unguarded `/ entry_price` (ZeroDivisionError)
`calculate_position_size` computes `max_position_size_by_value = int(max_position_value / entry_price)`
(`risk_utils:82`, mirrored `risk_management:149`). With `entry_price <= 0` (bad/missing bar,
or a levels calc returning 0) this raises `ZeroDivisionError` and 500s the order-calc endpoint.
**Fix applied:** early-return no-trade dict for `entry_price <= 0`, mirroring the existing
`risk_per_share == 0` early-return shape. No valid-trade path changed (valid entries are > 0).

### R2 ✅ CONFIRMED + FIXED — unguarded `/ account_capital` (ZeroDivisionError)
Two spots:
- `calculate_portfolio_heat`: `(total_risk / account_capital) * 100` (`risk_utils:233`, mirrored
  `risk_management:261`).
- `calculate_position_size`: `(actual_risk_amount / account_capital) * 100` (`risk_utils:90`, mirrored
  `risk_management:157`) — reachable because `position_size` can be 0 while `account_capital` is 0.

**Fix applied:** early-return for `account_capital <= 0` (portfolio heat returns
`can_add_position=False`; position size returns the no-trade dict). Same trivial-guard class as the
BU1/B2 ADX guard.

### R3 ✅ CONFIRMED (NOT fixed — money-adjacent, needs sign-off) — abs() masks invalid R:R
`calculate_risk_reward_ratio` (`risk_utils:117`):
```python
risk   = abs(entry_price - stop_loss)
reward = abs(take_profit - entry_price)
return reward / risk
```
`abs()` on **both** legs means a long with the stop *above* entry (nonsense) reports the same
attractive R:R as the valid mirror setup. Test proves `entry=100, stop=110, target=120` returns
`2.0` — indistinguishable from `stop=90`. `order_calculator.py:154` surfaces this number directly
to the user, so a broken setup can look like a 2R trade. **Fix options (your call):** direction-aware
R:R, or reject setups where stop & target are on the same side of entry.

### R4 ✅ CONFIRMED (minor) — trailing-stop recommendation overwrites itself
`calculate_trailing_stop` (`risk_utils:183-186`, mirrored `risk_management:212-215`):
```python
if profit_atr_multiple >= 1.5: recommendation = 'move_stop_to_breakeven'
if profit_atr_multiple >= 3.0: recommendation = 'consider_partial_profit'   # overwrites
```
At ≥3.0 ATR the breakeven advisory is lost. Should escalate (list) or chain. Advisory text only;
no P&L impact. Documented.

### R5 ✅ CONFIRMED (minor) — "actual risk exceeds target" warning is unreachable
`calculate_position_size` warns if `actual_risk_percent > risk_per_trade_percent * 1.1`
(`risk_utils:103`, mirrored `risk_management:168`). But `position_size = int(...)` floors down,
so `position_size * risk_per_share <= max_risk_amount` always → `actual_risk_percent <= target`
always. Dead branch. Test proves it across several inputs. Cosmetic; document or remove.

### R6 ✅ CONFIRMED (systemic) — tz-naive timestamp
`order_calculator.py:215` returns `'timestamp': datetime.utcnow()` (tz-naive), while
`recommendation_engine.py` uses tz-aware `datetime.now(timezone.utc)`. Same class as B3
(`analysis_completeness.py`). Confirms tz-inconsistency is **systemic** across the analysis/risk
subsystem. Not fixed — blocked on the same DB column-type check (B3).

### R7 ✅ CONFIRMED (architecture) — two duplicate risk implementations (live)
`RiskManager` (`risk_management.py`) duplicates `risk_utils.*` line-for-line
(`calculate_position_size`, `calculate_trailing_stop`, `calculate_portfolio_heat`,
ATR). Currently near-identical → no drift *yet*, but this audit had to apply R1/R2 to **both**
copies to keep them aligned — exactly the maintenance tax the duplication creates. Plus the dead
`_calculate_levels` v1. **Decision (D9):** make `RiskManager` delegate to `risk_utils` (one source
of truth), then delete the duplicated method bodies. Refactor on money code → needs sign-off.

### R8 ✅ CONFIRMED (architecture) — service imports from a route (inverted layering)
`order_calculator.py:99` does `from app.api.routes.analysis import _get_recommendation_for_stock`
inside the method (local import to dodge a circular). A *service* depending on a *route* module is
inverted layering and a latent circular-import trap. **Decision (D10):** lift
`_get_recommendation_for_stock` (or its core) into a service so both the route and
`order_calculator` import from the service layer.

## Status
- **Fixed + tested (this branch):** R1, R2 (div-zero guards in both live copies).
- **Documented, need decision:** R3 (abs R:R — money-adjacent), R6 (tz — blocked on B3 DB check),
  R7 (consolidate duplicates), R8 (decouple from route), R4/R5 (minor).
- Tests: `python3 backend/tests/test_bu5_risk.py` → **8/8 PASS** (incl. valid-path-unchanged and
  RiskManager-mirror parity).

## Open decisions added (feed into AUDIT_PLAN §5)
- **D9:** Consolidate `RiskManager` onto `risk_utils` (one source of truth)?
- **D10:** Lift `_get_recommendation_for_stock` core into a service (fixes R8 + the BU1/B4 dual-engine)?
- **D11:** Direction-aware / same-side-rejecting R:R (R3)?
- Reuse **D6** (one-copy refactor) framing for R7 if you want a single "collapse duplicates" pass.
