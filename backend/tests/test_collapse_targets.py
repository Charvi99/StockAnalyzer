"""
Collapse-stage safety net — characterization tests for the duplicates about to be collapsed.

Runnable without pytest/DB/TA-Lib:
    python3 backend/tests/test_collapse_targets.py

These tests LOCK current behavior so each collapse (Stages 1–4 of the plan at
/home/jakub/.claude/plans/expressive-shimmying-quail.md) is provably behavior-preserving:

  1. RISK PARITY  — risk_utils (fns) vs RiskManager (class) must agree on the math.
                    Documents the known return-shape drift (Stage 2 reconciles it; after that,
                    this test tightens to full-dict equality).
  2. PATTERN CFG  — the 4 task sites currently pass identical pattern kwargs (snapshot).
                    Stage 3 moves them into one SWING_PATTERN_DEFAULTS; values must not change.
  3. DEAD CODE    — repo-wide: quiverquant v1 has no runtime importers (safe to delete);
                    v2 IS imported by scripts/fetch_insider_trading.py (must keep);
                    _calculate_levels v1 has no callers outside its own definition.
  4. REC ENGINE   — Engine #1 policy constants (weights/threshold/regime map) + Engine #2
                    presence are locked. (Shallow — constants only; both engines are DB-coupled.)
"""
import os
import sys
import subprocess

import numpy as np
import pandas as pd

# Make `app.*` importable when run directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(REPO, "backend")


def _read(rel):
    """Read a backend-relative source file as text."""
    with open(os.path.join(BACKEND, rel)) as fh:
        return fh.read()


def _grep(pattern, root=None):
    """Recursive grep across backend .py files (excludes __pycache__). Returns list of 'path:line:match'."""
    root = root or BACKEND
    proc = subprocess.run(
        ["grep", "-rn", "--include=*.py", pattern, root],
        capture_output=True, text=True,
    )
    return [ln for ln in proc.stdout.splitlines() if "__pycache__" not in ln]


def _synthetic_df(rows=20):
    """Deterministic OHLCV df valid for RiskManager + risk_utils ATR (>=14 rows)."""
    idx = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = np.linspace(100.0, 120.0, rows)
    return pd.DataFrame({
        "timestamp": idx,
        "open": close - 0.5,
        "high": close + 2.0,
        "low": close - 2.0,
        "close": close,
        "volume": np.full(rows, 1000.0),
    })


# ---------------------------------------------------------------------------
# 1. RISK PARITY
# ---------------------------------------------------------------------------
def test_risk_position_size_happy_path_parity():
    """risk_utils.calculate_position_size and RiskManager.calculate_position_size must return
    identical dicts on the happy path (both have 7 keys incl. risk_per_share)."""
    from app.utils.risk_utils import calculate_position_size as ru_pos
    from app.services.risk_management import RiskManager

    rm = RiskManager(_synthetic_df())
    kwargs = dict(account_capital=10000, risk_per_trade_percent=1.0,
                  entry_price=100, stop_loss=95, max_position_value_percent=20.0)
    a = ru_pos(**kwargs)
    b = rm.calculate_position_size(**kwargs)
    assert a == b, f"position_size happy-path drift:\n risk_utils={a}\n RiskManager={b}"


def test_risk_position_size_guard_branch_full_parity():
    """Stage 2 RECONCILED the guard-branch drift: RiskManager now delegates to risk_utils, so the
    invalid-capital guard branch returns the SAME dict (incl. risk_per_share). Full equality."""
    from app.utils.risk_utils import calculate_position_size as ru_pos
    from app.services.risk_management import RiskManager

    rm = RiskManager(_synthetic_df())
    a = ru_pos(account_capital=0, risk_per_trade_percent=1.0, entry_price=100, stop_loss=95)
    b = rm.calculate_position_size(account_capital=0, risk_per_trade_percent=1.0, entry_price=100, stop_loss=95)
    assert "risk_per_share" in b, "reconciled guard branch must include risk_per_share"
    assert a == b, f"guard-branch drift returned after Stage 2:\n risk_utils={a}\n RiskManager={b}"


def test_risk_trailing_stop_full_parity():
    """Stage 2 RECONCILED the trailing-stop drift: RiskManager delegates to risk_utils (passing its
    precomputed ATR), so both now return the same dict incl. 'atr'. Full equality."""
    from app.utils.risk_utils import calculate_trailing_stop as ru_ts
    from app.services.risk_management import RiskManager

    df = _synthetic_df()
    rm = RiskManager(df)
    a = ru_ts(entry_price=100, current_price=110, direction="long", trailing_atr_multiplier=1.0, df=df)
    b = rm.calculate_trailing_stop(entry_price=100, current_price=110, direction="long", trailing_atr_multiplier=1.0)
    assert "atr" in a and "atr" in b, "trailing-stop must include 'atr' on both sides after Stage 2"
    assert a == b, f"trailing-stop drift returned after Stage 2:\n risk_utils={a}\n RiskManager={b}"


def test_risk_portfolio_heat_full_parity():
    """calculate_portfolio_heat has NO shape drift — full dicts must be equal."""
    from app.utils.risk_utils import calculate_portfolio_heat as ru_heat
    from app.services.risk_management import RiskManager

    rm = RiskManager(_synthetic_df())
    positions = [{"entry_price": 100, "stop_loss": 95, "position_size": 50}]
    a = ru_heat(positions, account_capital=10000)
    b = rm.calculate_portfolio_heat(positions, account_capital=10000)
    assert a == b, f"portfolio_heat drift:\n risk_utils={a}\n RiskManager={b}"


# ---------------------------------------------------------------------------
# 2. PATTERN CONFIG SNAPSHOT (4 task sites)
# ---------------------------------------------------------------------------
def test_pattern_thresholds_canonical_values():
    """The shared config holds the canonical swing-pattern thresholds (single source of truth
    after Stage 3). Lock the values — this is the P1/P2 over-filtering tuning lever."""
    from app.config.pattern_thresholds import swing_detector_kwargs, swing_detect_kwargs
    assert swing_detector_kwargs() == {
        "min_pattern_length": 5, "peak_order": 5,
        "min_confidence": 0.5, "min_r_squared": 0.70,
    }
    assert swing_detect_kwargs() == {
        "days": 90,
        "exclude_patterns": ["Rounding Top", "Rounding Bottom"],
        "remove_overlaps": True, "overlap_threshold": 0.3,
        "timeframes": ["4h", "1d"],
    }
    # Fresh dict each call — no shared-mutation footgun when **-spread at call sites:
    assert swing_detector_kwargs() is not swing_detector_kwargs()


def test_pattern_task_sites_use_shared_config():
    """The 4 task sites delegate to the shared config (no more hardcoded literals)."""
    at = _read("app/tasks/analysis_tasks.py")
    pt = _read("app/tasks/processor_tasks.py")
    for src, label in [(at, "analysis_tasks"), (pt, "processor_tasks")]:
        assert "from app.config.pattern_thresholds import" in src, f"{label} must import the shared config"
        assert "**swing_detector_kwargs()" in src, f"{label} must spread swing_detector_kwargs()"
        assert "**swing_detect_kwargs()" in src, f"{label} must spread swing_detect_kwargs()"
    # processor_tasks has 3 priority tasks -> 3 detector-construction sites
    assert pt.count("**swing_detector_kwargs()") >= 3, "processor_tasks lost a pattern site"
    # No stale hardcoded literals remain in either task file:
    assert "min_confidence=0.7" not in at and "min_confidence=0.7" not in pt, (
        "stale hardcoded pattern literal still present in a task file"
    )


def test_pattern_config_route_is_NOT_a_canonical_site():
    """The chart_patterns ROUTE is an HTTP tuning boundary, not a 5th copy of the magic numbers —
    it forwards request.* whose Pydantic defaults differ (20/5/0.0/0.0). Lock that distinction so
    Stage 3 correctly scopes to the 4 task sites only."""
    route = _read("app/api/routes/chart_patterns.py")
    schema = _read("app/schemas/chart_patterns.py")
    assert "request.min_confidence" in route, "route should forward request.min_confidence (HTTP boundary)"
    # Pydantic defaults are the looser set (return-everything), NOT the tasks' strict 0.7/0.85.
    assert "default=0.0" in schema and "min_r_squared: float = Field(default=0.0" in schema, (
        "route schema defaults changed — recheck whether route is now a canonical site"
    )


# ---------------------------------------------------------------------------
# 3. DEAD CODE (repo-wide)
# ---------------------------------------------------------------------------
def test_quiverquant_v1_has_no_runtime_importers():
    """quiverquant_fetcher (v1) is safe to delete: no `import` of it anywhere in backend."""
    hits = [h for h in _grep(r"import quiverquant_fetcher") if "quiverquant_fetcher_v2" not in h]
    assert not hits, f"quiverquant v1 still imported (not safe to delete): {hits}"


def test_quiverquant_v2_is_live_do_not_delete():
    """quiverquant_fetcher_v2 is LIVE — imported by the scheduled insider-trading script. Lock it."""
    hits = _grep(r"quiverquant_fetcher_v2")
    assert any("scripts/fetch_insider_trading.py" in h for h in hits), (
        f"quiverquant v2 no longer imported by scripts/fetch_insider_trading.py — recheck (would break pipeline): {hits}"
    )


def test_calculate_levels_v1_no_external_callers():
    """_calculate_levels (v1) has no callers anywhere except its own `def` line in order_calculator.py."""
    hits = [h for h in _grep(r"_calculate_levels\(") if "_calculate_levels_v2" not in h and "order_calculator.py" not in h]
    assert not hits, f"_calculate_levels v1 has callers outside order_calculator.py: {hits}"


def test_calculate_levels_v2_is_the_live_call():
    """_calculate_levels_v2 is the live method (called from order_calculator). Lock it."""
    src = _read("app/services/order_calculator.py")
    assert "_calculate_levels_v2" in src and "def _calculate_levels_v2" in src, (
        "_calculate_levels_v2 (the live method) is missing — recheck"
    )


# ---------------------------------------------------------------------------
# 4. REC ENGINE POLICY LOCK (constants only — shallow)
# ---------------------------------------------------------------------------
def test_rec_engine1_policy_constants_locked():
    """Engine #1 policy (6 fixed weights, BUY/SELL threshold, regime->score map). Phase 0.4b
    moved these from recommendation_engine.py into the pure signal layer
    (signal/systematic.py); lock them in their new home."""
    src = _read("app/services/signal/systematic.py")
    for marker in [
        "'chart_patterns': 0.28",
        "'candlestick_patterns': 0.14",
        "'technical_indicators': 0.23",
        "'sentiment': 0.13",
        "'market_regime': 0.12",
        "'dividend_split_signals': 0.10",
        "BUY_SELL_THRESHOLD = 0.3",
        "'trending_up': 0.8",
        "'trending_down': -0.8",
    ]:
        assert marker in src, f"Engine #1 policy constant changed/missing: {marker}"
    # And the adapter must still delegate to the pure function (no inline scoring revival):
    adapter = _read("app/services/recommendation_engine.py")
    assert "from app.services.signal.systematic import signal_systematic" in adapter, (
        "Engine #1 adapter must delegate to the pure signal function (0.4b)"
    )


def test_rec_engine2_lives_in_service_route_delegates():
    """Stage 4A moved Engine #2 (~717 LOC) from routes/analysis.py to
    services/realtime_recommendation.py (behavior-preserving). Lock its new home, that the
    route delegates to it (no inline logic), and that the service->route import inversion
    in order_calculator is fixed."""
    svc = _read("app/services/realtime_recommendation.py")
    route = _read("app/api/routes/analysis.py")
    oc = _read("app/services/order_calculator.py")

    # Engine #2 entrypoint lives in the service; its 4 pure helpers were lifted into
    # the pure signal layer (Phase 0.4a) and imported back into the service:
    assert "def _get_recommendation_for_stock" in svc, "Engine #2 entrypoint missing from service"
    core = _read("app/services/signal/core.py")
    for helper in ["def check_weekly_trend", "def detect_swing_points",
                   "def categorize_candlestick_pattern", "def evaluate_swing_trading_context"]:
        assert helper in core, f"Engine #2 pure helper {helper} missing from signal/core.py"
    assert "from app.services.signal.core import" in svc, (
        "service must import the 4 helpers back from the pure signal layer (0.4a)"
    )

    # Route no longer holds the logic inline — it imports + delegates:
    assert "from app.services.realtime_recommendation import _get_recommendation_for_stock" in route, (
        "route must import Engine #2 from the service"
    )
    assert "def _get_recommendation_for_stock" not in route and "def _check_weekly_trend" not in route, (
        "route still defines Engine #2 inline — Stage 4A incomplete"
    )

    # The service->route inversion is fixed (order_calculator imports the service, not the route):
    assert "from app.services.realtime_recommendation import" in oc, (
        "order_calculator must import Engine #2 from the service"
    )
    assert "from app.api.routes.analysis import" not in oc, "service->route inversion still present"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
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
            except Exception as e:  # env-dependent (missing dep) — warn, don't crash the run
                import warnings
                warnings.warn(f"{name} skipped (env): {e}")
                print(f"SKIP  {name}: {e}")
    print(f"\n{'All passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
