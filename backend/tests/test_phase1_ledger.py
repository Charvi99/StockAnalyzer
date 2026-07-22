"""
Phase 1 (paper-trading ledger) tests.

Grows across the phase:
  - Step 2 (here now): the fresh-signal adapter ``ledger_signal_adapter``.
  - Step 4 (appended later): ``LedgerService`` pure math — exit-reason ordering,
    realized P&L, fresh-BUY detection, equity = cash + open value, split-adjustment
    math, trading-day count.

Adapter tests run with NO database: a fake session whose ``.query(...)`` raises
forces every per-component fetch into its fault-tolerant default (empty/None), so
the pure ``signal_systematic`` runs on empty inputs deterministically. That proves
the adapter (a) returns a config-bearing ``SignalResult`` (not a legacy dict),
(b) stamps the SAME ``config_version`` the pure function does, and (c) is
deterministic — the properties the ledger's attribution depends on.

Runnable without pytest/DB:
    python3 backend/tests/test_phase1_ledger.py
"""
import ast
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.signal.types import SignalResult
from app.services.signal.systematic import signal_systematic
from app.services.ledger_signal_adapter import signal_for_ledger
from app.services.ledger_service import (
    _is_fresh_buy,
    _exit_reason,
    _exit_fill_price,
    _apply_slippage,
    _realized_pnl_long,
    _scale_price_for_split,
    _scale_size_for_split,
    LEDGER_MAX_HOLD_DAYS,
)

ADAPTER_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "services", "ledger_signal_adapter.py")
ORDER_CALC_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "services", "order_calculator.py")


def _src(rel):
    with open(os.path.join(os.path.dirname(__file__), "..", rel), encoding="utf-8") as fh:
        return fh.read()


# ── fakes ─────────────────────────────────────────────────────────────────────
class _BrokenDB:
    """Fake session whose every ``.query(...)`` raises.

    Forces each adapter fetch into its fault-tolerant default, so signal_systematic
    runs on empty inputs with no real database involved."""

    def query(self, *args, **kwargs):
        raise RuntimeError("no real DB in unit test")


class _FakeStock:
    id = 42
    symbol = "TEST"


# ── Step 2: the fresh-signal adapter ──────────────────────────────────────────
def test_engine1_returns_signalresult_on_empty_inputs():
    """Adapter returns a SignalResult (config-bearing), not a legacy dict."""
    sr = signal_for_ledger(_BrokenDB(), _FakeStock(), "engine_1")
    assert isinstance(sr, SignalResult), f"expected SignalResult, got {type(sr)!r}"
    # Empty inputs -> every component 0 -> weighted_score 0 -> HOLD @ 0.5.
    assert sr.signal == "HOLD"
    assert sr.confidence == 0.5
    assert abs(sr.weighted_score) < 1e-12


def test_engine1_stamps_canonical_config_version():
    """The adapter stamps the SAME config_version the pure signal_systematic does.

    This is the attribution contract: a trade opened from this signal records this
    config_version, and it must equal what the pure Engine #1 function produces, so
    outcomes are attributable to the exact signal definition that was live."""
    sr = signal_for_ledger(_BrokenDB(), _FakeStock(), "engine_1")
    canonical = signal_systematic(pd.DataFrame(), [], [], None, "unknown", None).config_version
    assert sr.config_version == canonical, (
        f"adapter config_version {sr.config_version!r} != systematic {canonical!r}; "
        "the ledger would misattribute trades to the wrong signal definition"
    )
    assert len(sr.config_version) == 12


def test_engine1_is_deterministic():
    """Same inputs -> identical result across calls (the ledger relies on this)."""
    a = signal_for_ledger(_BrokenDB(), _FakeStock(), "engine_1")
    b = signal_for_ledger(_BrokenDB(), _FakeStock(), "engine_1")
    assert a.signal == b.signal
    assert a.confidence == b.confidence
    assert a.config_version == b.config_version


def test_unknown_engine_raises_value_error():
    try:
        signal_for_ledger(_BrokenDB(), _FakeStock(), "engine_99")
    except ValueError:
        return
    raise AssertionError("expected ValueError for an unknown engine")


def test_engine2_not_yet_enabled_before_step8():
    """engine_2 ledger signal is enabled in Phase 1 step 8; until then it must
    raise NotImplementedError (not silently return a wrong signal)."""
    try:
        signal_for_ledger(_BrokenDB(), _FakeStock(), "engine_2")
    except NotImplementedError:
        return
    raise AssertionError("expected NotImplementedError for engine_2 before step 8")


def _code_references_indicator_cache(tree) -> bool:
    """True if the AST references ``IndicatorCacheService`` in CODE (import, Name,
    or Attribute) — NOT in docstrings/comments. AST parsing (per the Phase 0.6 H2
    lesson) so this guard isn't tripped by the docstring explaining the rule."""
    for node in ast.walk(tree):
        if isinstance(node, ast.alias) and "IndicatorCacheService" in (node.asname or node.name):
            return True
        if isinstance(node, ast.Name) and node.id == "IndicatorCacheService":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "IndicatorCacheService":
            return True
    return False


def test_c2_ledger_adapter_never_uses_indicator_cache():
    """PERMANENT invariant (C2): the ledger adapter NEVER references
    IndicatorCacheService in CODE for EITHER engine. config_version hashes the
    weights, not the inputs, so a cached signal is not reproducible and cannot be
    attributed — the ledger must trade the fresh signal. Holds for engine_2 at
    step 8 too (its fresh path uses TechnicalIndicators.calculate_all_indicators,
    not cache). Inspects CODE only (AST), so the docstring may name the rule."""
    with open(ADAPTER_PATH, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    assert not _code_references_indicator_cache(tree), (
        "C2 regression: the ledger adapter must never reference IndicatorCacheService "
        "in code. Trade the fresh signal (config_version hashes weights, not inputs)."
    )


# ── Step 3: order-calc recommendation override (C3/C4) ────────────────────────
def _order_calc_method(tree):
    """Locate OrderCalculatorService.calculate_order_parameters in the AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "OrderCalculatorService":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "calculate_order_parameters":
                    return item
    return None


def _called_names(stmts):
    """Names/attrs called within a list of statements (does not cross if/else)."""
    names = set()
    for s in stmts:
        for node in ast.walk(s):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    names.add(node.func.attr)
    return names


def test_c3_order_calc_accepts_recommendation_override():
    """calculate_order_parameters has an optional `recommendation` kwarg (default
    None) so the ledger can pass its known signal in and skip the Engine #2
    re-call. Existing callers (None) are unaffected."""
    fn = _order_calc_method(ast.parse(_src("app/services/order_calculator.py")))
    assert fn is not None, "OrderCalculatorService.calculate_order_parameters not found"
    params = [a.arg for a in fn.args.args]
    assert "recommendation" in params, (
        "C3: calculate_order_parameters must accept a `recommendation` override kwarg"
    )
    # The last default must be None (the override defaults to off).
    assert fn.args.defaults and isinstance(fn.args.defaults[-1], ast.Constant) \
        and fn.args.defaults[-1].value is None, (
        "C3: the `recommendation` override must default to None (existing callers)"
    )


def test_c3_override_skips_engine2_recall():
    """When `recommendation` is provided, the Engine #2 re-call
    (_get_recommendation_for_stock) must NOT happen — it's only in the else branch.
    This is the C3 guarantee: no double work, no cross-engine contamination, and no
    cached-indicator path for the ledger."""
    fn = _order_calc_method(ast.parse(_src("app/services/order_calculator.py")))
    assert fn is not None
    # Find the override If: test is `recommendation is not None`.
    override_if = None
    for node in ast.walk(fn):
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "recommendation"):
            override_if = node
            break
    assert override_if is not None, (
        "C3: missing `if recommendation is not None:` override branch in "
        "calculate_order_parameters"
    )
    body_calls = _called_names(override_if.body)
    orelse_calls = _called_names(override_if.orelse)
    assert "_get_recommendation_for_stock" not in body_calls, (
        "C3 regression: the override (recommendation-provided) path still calls "
        "_get_recommendation_for_stock — it must skip the Engine #2 re-call"
    )
    assert "_get_recommendation_for_stock" in orelse_calls, (
        "C3: the existing callers' else branch must still call "
        "_get_recommendation_for_stock"
    )


# ── Step 4: LedgerService pure decision math ─────────────────────────────────
def test_fresh_buy_detection():
    """A fresh BUY is a transition INTO buy (last != BUY and now == BUY)."""
    assert _is_fresh_buy(None, "BUY") is True       # never logged -> fresh
    assert _is_fresh_buy("HOLD", "BUY") is True
    assert _is_fresh_buy("SELL", "BUY") is True
    assert _is_fresh_buy("BUY", "BUY") is False     # continuous BUY: not fresh (no pyramid)
    assert _is_fresh_buy("HOLD", "HOLD") is False
    assert _is_fresh_buy("BUY", "SELL") is False
    assert _is_fresh_buy(None, "HOLD") is False


def test_exit_reason_stop_loss_wins_same_day():
    """When one day's range spans BOTH stop and target, assume the stop hit first
    (conservative). This is the key exit-evaluation subtlety."""
    # low <= SL AND high >= TP  -> stop_loss wins
    assert _exit_reason(day_high=120, day_low=90, stop_loss=95, take_profit=115,
                        trading_days_held=3, current_signal="BUY") == "stop_loss"


def test_exit_reason_barrier_then_flip_then_maxhold():
    """Priority: stop_loss > take_profit > signal_flip > max_hold > None."""
    assert _exit_reason(120, 90, 95, 115, 3, "BUY") == "stop_loss"      # SL only
    assert _exit_reason(120, 100, 95, 115, 3, "BUY") == "take_profit"  # TP only (low>SL)
    assert _exit_reason(105, 100, 95, 115, 3, "SELL") == "signal_flip"  # no barrier, SELL
    assert _exit_reason(105, 100, 95, 115, 3, "HOLD") is None           # nothing, short hold
    assert _exit_reason(105, 100, 95, 115, LEDGER_MAX_HOLD_DAYS, "BUY") == "max_hold"
    # max_hold yields to signal_flip when the engine flips.
    assert _exit_reason(105, 100, 95, 115, LEDGER_MAX_HOLD_DAYS, "SELL") == "signal_flip"


def test_exit_fill_price():
    """Barrier exits fill at the barrier; discretionary exits fill at market."""
    assert _exit_fill_price("stop_loss", 95.0, 115.0, 100.0) == 95.0
    assert _exit_fill_price("take_profit", 95.0, 115.0, 100.0) == 115.0
    assert _exit_fill_price("signal_flip", 95.0, 115.0, 100.0) == 100.0
    assert _exit_fill_price("max_hold", 95.0, 115.0, 100.0) == 100.0


def test_realized_pnl_long_win_and_loss_no_commission():
    """v1 (0 commission): pnl = (fill-entry)*size; pct = pnl / (entry*size)."""
    pnl, pct = _realized_pnl_long(100.0, 110.0, 10, commission_per_share=0.0)
    assert abs(pnl - 100.0) < 1e-9
    assert abs(pct - 0.10) < 1e-9
    pnl, pct = _realized_pnl_long(100.0, 90.0, 10, commission_per_share=0.0)
    assert abs(pnl - (-100.0)) < 1e-9
    assert abs(pct - (-0.10)) < 1e-9


def test_realized_pnl_long_nets_both_leg_commissions():
    """Commission on entry+exit reduces pnl and raises the cost basis."""
    pnl, pct = _realized_pnl_long(100.0, 110.0, 10, commission_per_share=0.5)
    # pnl = (10)*10 - 0.5*10*2 = 100 - 10 = 90
    assert abs(pnl - 90.0) < 1e-9
    # cost_basis = 1000 + 5 = 1005
    assert abs(pct - (90.0 / 1005.0)) < 1e-9


def test_realized_pnl_matches_cash_accounting():
    """realized_pnl must equal the net cash change (proceeds - cost). This is the
    invariant that keeps the equity snapshot honest."""
    entry, fill, size, comm = 100.0, 108.0, 40, 0.25
    cost = entry * size + comm * size
    proceeds = fill * size - comm * size
    pnl, _ = _realized_pnl_long(entry, fill, size, commission_per_share=comm)
    assert abs((proceeds - cost) - pnl) < 1e-9


def test_equity_equals_cash_plus_open_value_no_commission():
    """With 0 commission, account equity = starting_cash + sum(unrealized)."""
    starting_cash = 100000.0
    entry, size, mark = 100.0, 50, 110.0
    cost = entry * size  # commission 0
    cash = starting_cash - cost
    open_value = mark * size
    equity = cash + open_value
    unrealized = (mark - entry) * size
    assert abs(equity - (starting_cash + unrealized)) < 1e-9


def test_apply_slippage():
    """0 bps is a no-op; positive bps worsens a BUY fill (higher price)."""
    assert _apply_slippage(100.0, 0) == 100.0
    assert abs(_apply_slippage(100.0, 10) - 100.1) < 1e-9  # +10bps = +0.1%


def test_split_scaling():
    """A 2-for-1 split halves prices and doubles share count; position value holds."""
    assert _scale_price_for_split(100.0, 2.0) == 50.0
    assert _scale_size_for_split(100, 2.0) == 200
    # value preserved: price/ratio * size*ratio == price*size
    assert abs(_scale_price_for_split(100.0, 2.0) * _scale_size_for_split(100, 2.0)
               - (100.0 * 100)) < 1e-9
    # zero-ratio guard (defensive — never divides by zero)
    assert _scale_price_for_split(100.0, 0.0) == 100.0
    assert _scale_size_for_split(100, 0.0) == 100


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
            except Exception as e:
                failures += 1
                print(f"ERROR {name}: {e!r}")
    print(f"\n{'All passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
