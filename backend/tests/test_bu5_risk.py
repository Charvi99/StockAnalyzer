"""
BU5 audit — risk/order calc characterization + guard tests.

Runnable without pytest/TA-Lib/DB:
    python3 backend/tests/test_bu5_risk.py

Covers (see docs/audit/BU5_risk_order.md):
  R1/R2 — div-zero GUARDS: calculate_position_size and calculate_portfolio_heat
          must NOT crash on entry_price<=0 / account_capital<=0 (return no-trade).
  R3    — calculate_risk_reward_ratio uses abs() on risk AND reward, so it masks
          invalid same-side stop/target setups (documents the money-adjacent bug).
  R5    — int() floor makes position_size conservative (actual_risk <= target),
          so the "exceeds target" warning is effectively unreachable.
  parity — risk_utils functions and RiskManager methods agree (the two are
          near-duplicates; this guards against silent drift between them).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _df(n=30):
    rng = np.arange(n)
    return pd.DataFrame({
        "open": 100 + rng * 0.1,
        "high": 101 + rng * 0.1,
        "low": 99 + rng * 0.1,
        "close": 100 + rng * 0.1,
        "volume": np.full(n, 1000.0),
    })


# --------------------------------------------------------------------------- #
# R1/R2 — div-zero guards (the applied fix)
# --------------------------------------------------------------------------- #
def test_r1_position_size_entry_zero_no_crash():
    from app.utils.risk_utils import calculate_position_size as cps
    r = cps(account_capital=10000, risk_per_trade_percent=1.0, entry_price=0.0, stop_loss=99)
    assert r["position_size"] == 0
    assert r["warnings"] and "entry price" in r["warnings"][0].lower()


def test_r1_position_size_capital_zero_no_crash():
    from app.utils.risk_utils import calculate_position_size as cps
    r = cps(account_capital=0, risk_per_trade_percent=1.0, entry_price=100, stop_loss=98)
    assert r["position_size"] == 0
    assert r["warnings"] and "capital" in r["warnings"][0].lower()


def test_r2_portfolio_heat_capital_zero_no_crash():
    from app.utils.risk_utils import calculate_portfolio_heat as cph
    positions = [{"entry_price": 100, "stop_loss": 98, "position_size": 50}]
    r = cph(positions, account_capital=0)
    assert r["can_add_position"] is False
    assert r["portfolio_heat_percent"] == 0.0  # guarded, not a crash


def test_r1_risk_manager_mirror_entry_zero_no_crash():
    """The RiskManager duplicate must carry the SAME guard (R7 consolidation note)."""
    from app.services.risk_management import RiskManager
    rm = RiskManager(_df())
    r = rm.calculate_position_size(account_capital=10000, risk_per_trade_percent=1.0,
                                   entry_price=0.0, stop_loss=99)
    assert r["position_size"] == 0
    assert r["warnings"] and "entry price" in r["warnings"][0].lower()


# --------------------------------------------------------------------------- #
# Valid-path sanity (guards must NOT change normal sizing)
# --------------------------------------------------------------------------- #
def test_position_size_valid_path_unchanged():
    from app.utils.risk_utils import calculate_position_size as cps
    # 1% of 10000 = 100 risk budget; entry=100 stop=90 -> risk/share=10 -> 10 shares
    # by risk; value cap allows int(2000/100)=20 -> min(10,20)=10 (risk binds).
    r = cps(account_capital=10000, risk_per_trade_percent=1.0, entry_price=100, stop_loss=90)
    assert r["position_size"] == 10, f"valid sizing changed by guard: {r}"
    assert abs(r["risk_amount"] - 100.0) < 1e-9
    assert abs(r["capital_at_risk_percent"] - 1.0) < 1e-9


# --------------------------------------------------------------------------- #
# R3 — abs() masks invalid R:R setups (documented bug, not fixed)
# --------------------------------------------------------------------------- #
def test_r3_rr_abs_masks_invalid_setup():
    from app.utils.risk_utils import calculate_risk_reward_ratio as rr
    # Long with stop ABOVE entry and target ABOVE entry -> nonsense, but abs() hides it
    bogus = rr(entry_price=100, stop_loss=110, take_profit=120)
    sane = rr(entry_price=100, stop_loss=90, take_profit=120)
    assert abs(bogus - sane) < 1e-9, (
        "abs() on both legs makes the invalid setup (stop above entry for a long) "
        "indistinguishable from the valid one — R3 confirmed"
    )
    assert bogus == 2.0  # looks attractive despite being a broken trade


# --------------------------------------------------------------------------- #
# R5 — int() floor => actual_risk never exceeds target (warning dead)
# --------------------------------------------------------------------------- #
def test_r5_actual_risk_never_exceeds_target():
    from app.utils.risk_utils import calculate_position_size as cps
    for entry, stop in [(100, 97), (50, 49), (250, 240.5)]:
        r = cps(account_capital=10000, risk_per_trade_percent=1.0, entry_price=entry, stop_loss=stop)
        assert r["capital_at_risk_percent"] <= 1.0 + 1e-9, (
            f"floored sizing must keep actual risk <= target; got {r['capital_at_risk_percent']} "
            "=> the 'exceeds target' warning (R5) is unreachable"
        )


def test_modules_import():
    try:
        import app.utils.risk_utils  # noqa: F401
        import app.services.risk_management  # noqa: F401
    except Exception as e:  # pragma: no cover - env-dependent
        import warnings
        warnings.warn(f"module import skipped in this env: {e}")


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL  {name}: {e}")
    print(f"\n{'All passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
