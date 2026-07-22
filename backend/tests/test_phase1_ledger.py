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


# ── Step 5: Celery task + beat wiring ─────────────────────────────────────────
LEDGER_TASKS_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "tasks", "ledger_tasks.py")
CELERY_APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "celery_app.py")


def _fn(tree, name):
    """Top-level FunctionDef `name` in an AST, or None."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _func_calls(fn) -> set:
    """All Name/attribute names CALLED anywhere within function `fn`."""
    return _called_names(list(ast.walk(fn)))


def test_ledger_task_registered_and_delegates_to_service():
    """run_paper_trading_cycle is a @celery_app.task that owns the transaction and
    delegates the cycle to LedgerService.run_cycle (H4: task is a thin wrapper)."""
    tree = ast.parse(_src("app/tasks/ledger_tasks.py"))
    fn = _fn(tree, "run_paper_trading_cycle")
    assert fn is not None, "run_paper_trading_cycle not found"
    # Decorated with celery_app.task.
    dec_names = []
    for d in fn.decorator_list:
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute):
            dec_names.append(d.func.attr)
        elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name):
            dec_names.append(d.func.id)
    assert "task" in dec_names, "run_paper_trading_cycle must be a @celery_app.task"
    calls = _func_calls(fn)
    # Delegates to the service and owns the DB transaction lifecycle.
    assert "LedgerService" in calls, "task must construct LedgerService"
    assert "run_cycle" in calls, "task must call LedgerService.run_cycle"
    assert "commit" in calls, "task owns the commit (service only flushes)"
    assert "rollback" in calls, "task rolls back on failure"
    assert "close" in calls, "task closes the session (finally)"


def test_ledger_task_retries_on_transient_failure():
    """A generic except branch re-queues via self.retry (idempotent on cycle_id,
    so a retry is a safe no-op for rows already written)."""
    fn = _fn(ast.parse(_src("app/tasks/ledger_tasks.py")), "run_paper_trading_cycle")
    # Find the generic `except Exception` handler (no specific type) and assert it retries.
    retry_found = False
    for node in ast.walk(fn):
        if isinstance(node, ast.ExceptHandler):
            is_generic = node.type is None or (
                isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"))
            if is_generic and "retry" in _called_names(list(ast.walk(node))):
                retry_found = True
    assert retry_found, "generic except must call self.retry for transient failures"


def test_ledger_task_does_not_retry_config_errors():
    """A ValueError (e.g. account not seeded) is a config error — retrying can't fix
    it, so the except ValueError branch must NOT call self.retry (it returns)."""
    fn = _fn(ast.parse(_src("app/tasks/ledger_tasks.py")), "run_paper_trading_cycle")
    for node in ast.walk(fn):
        if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name) \
                and node.type.id == "ValueError":
            assert "retry" not in _called_names(list(ast.walk(node))), (
                "ValueError (config error) must not be retried"
            )
            return
    raise AssertionError("expected an `except ValueError` handler in the task")


def test_ledger_task_skips_non_trading_days():
    """The cycle must not run on weekends/holidays — no fresh bar, and a flat
    snapshot under a non-trading date is pure noise on the audit trail."""
    src = _src("app/tasks/ledger_tasks.py")
    assert "is_weekend" in src and "is_market_holiday" in src, (
        "task must guard against non-trading days (is_weekend/is_market_holiday)"
    )


def _kw_value(call, name):
    """Constant value of keyword `name` in an ast.Call, else None."""
    for kw in getattr(call, "keywords", []):
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def _routes_map(tree):
    """task_routes as {pattern: {queue: ...}} — the Dict whose keys all end in .*."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            routes = {}
            all_star = bool(node.keys)
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value.endswith(".*"):
                    q = {}
                    if isinstance(v, ast.Dict):
                        for kk, vv in zip(v.keys, v.values):
                            if isinstance(kk, ast.Constant) and isinstance(vv, ast.Constant):
                                q[kk.value] = vv.value
                    routes[k.value] = q
                else:
                    all_star = False
            if all_star:
                return routes
    return {}


def _beat_entry(tree, task_substr):
    """The beat_schedule entry dict whose 'task' contains task_substr."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            tgt_names = []
            for t in node.targets:
                if isinstance(t, ast.Name):
                    tgt_names.append(t.id)
                elif isinstance(t, ast.Attribute):
                    tgt_names.append(t.attr)  # celery_app.conf.beat_schedule
            if "beat_schedule" not in tgt_names or not isinstance(node.value, ast.Dict):
                continue
            for v in node.value.values:
                if not isinstance(v, ast.Dict):
                    continue
                for kk, vv in zip(v.keys, v.values):
                    if isinstance(kk, ast.Constant) and kk.value == "task" \
                            and isinstance(vv, ast.Constant) and task_substr in vv.value:
                        return v
    return None


def _entry_field(entry, key):
    """The ast node for entry[key] (a beat entry dict)."""
    for kk, vv in zip(entry.keys, entry.values):
        if isinstance(kk, ast.Constant) and kk.value == key:
            return vv
    return None


def test_celery_app_wires_ledger_task():
    """celery_app.py: include has ledger_tasks, routes it to maintenance, and the
    beat schedules engine_1 daily at 19:00 ET (after analysis) on maintenance."""
    tree = ast.parse(_src("app/celery_app.py"))

    # include list contains the module (so the worker imports + registers the task).
    include = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "Celery":
            for kw in node.keywords:
                if kw.arg == "include" and isinstance(kw.value, ast.List):
                    include = [c.value for c in kw.value.elts if isinstance(c, ast.Constant)]
    assert "app.tasks.ledger_tasks" in include, (
        "ledger_tasks must be in the Celery include list (else the worker never imports it)"
    )

    # task_routes -> maintenance (else a manual .delay() lands in the unconsumed
    # default queue, same trap that silently killed the analysis pipeline).
    routes = _routes_map(tree)
    assert routes.get("app.tasks.ledger_tasks.*") == {"queue": "maintenance"}, (
        f"ledger task must route to maintenance; got {routes.get('app.tasks.ledger_tasks.*')}"
    )

    # beat entry: engine_1 daily at 19:00 ET.
    entry = _beat_entry(tree, "ledger_tasks")
    assert entry is not None, "no beat_schedule entry references ledger_tasks"
    sched = _entry_field(entry, "schedule")
    assert isinstance(sched, ast.Call), "beat schedule must be a crontab(...) call"
    assert _kw_value(sched, "hour") == 19, "engine_1 beat must run at hour=19 (7pm ET)"
    assert _kw_value(sched, "minute") == 0, "engine_1 beat must run at minute=0"
    # options: maintenance queue + engine_1 kwarg.
    opts = _entry_field(entry, "options")
    assert isinstance(opts, ast.Dict), "beat entry needs an options dict"
    opt_map = {}
    for kk, vv in zip(opts.keys, opts.values):
        if isinstance(kk, ast.Constant) and isinstance(vv, ast.Constant):
            opt_map[kk.value] = vv.value
    assert opt_map.get("queue") == "maintenance", "beat queue must be maintenance"
    # kwargs.engine == engine_1.
    kwargs_node = None
    for kk, vv in zip(opts.keys, opts.values):
        if isinstance(kk, ast.Constant) and kk.value == "kwargs":
            kwargs_node = vv
    assert isinstance(kwargs_node, ast.Dict), "beat entry must pass kwargs.engine"
    kw = {kk.value: vv.value for kk, vv in zip(kwargs_node.keys, kwargs_node.values)
          if isinstance(kk, ast.Constant) and isinstance(vv, ast.Constant)}
    assert kw.get("engine") == "engine_1", f"beat must target engine_1; got {kw}"


# ── Step 6: ledger routes + /health ───────────────────────────────────────────
LEDGER_ROUTE_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "api", "routes", "ledger.py")
LEDGER_HANDLERS = {"list_accounts", "list_trades", "equity_curve", "summary", "health"}


def test_ledger_routes_define_five_endpoints():
    """The route module exposes the five documented GET endpoints."""
    tree = ast.parse(_src("app/api/routes/ledger.py"))
    paths = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for d in node.decorator_list:
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) \
                        and d.func.attr == "get" and d.args and isinstance(d.args[0], ast.Constant):
                    paths.add(d.args[0].value)
    expected = {"/accounts", "/trades", "/equity", "/summary", "/health"}
    assert expected <= paths, f"missing ledger endpoints: {expected - paths}"


def test_ledger_routes_registered_in_main():
    """main.py mounts the ledger router under /api/v1/paper-trading."""
    tree = ast.parse(_src("app/main.py"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "include_router":
            arg0 = node.args[0] if node.args else None
            is_ledger = (isinstance(arg0, ast.Attribute) and isinstance(arg0.value, ast.Name)
                         and arg0.value.id == "ledger" and arg0.attr == "router")
            prefix = next((kw.value.value for kw in node.keywords
                           if kw.arg == "prefix" and isinstance(kw.value, ast.Constant)), None)
            if is_ledger and prefix == "/api/v1/paper-trading":
                return
    raise AssertionError("main.py must include_router(ledger.router, prefix='/api/v1/paper-trading')")


def test_ledger_route_handlers_are_sync():
    """DB-bound read handlers must be sync def, NOT async def (H7: an async def
    handler doing ORM work blocks the event loop)."""
    tree = ast.parse(_src("app/api/routes/ledger.py"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in LEDGER_HANDLERS:
            raise AssertionError(f"handler {node.name} must be sync def, not async (H7)")
        if isinstance(node, ast.FunctionDef) and node.name in LEDGER_HANDLERS:
            found.add(node.name)
    assert LEDGER_HANDLERS <= found, f"missing handlers: {LEDGER_HANDLERS - found}"


def test_ledger_routes_cast_decimals_to_float():
    """DECIMAL columns must be cast via _f so they're JSON-serializable (FastAPI
    500s on a raw Decimal). _trade_dict is the densest DECIMAL surface."""
    src = _src("app/api/routes/ledger.py")
    assert "def _f(" in src, "DECIMAL->float helper _f must be defined"
    assert "_f(t.entry_price)" in src and "_f(t.realized_pnl)" in src, (
        "_trade_dict must cast DECIMAL columns via _f (else FastAPI 500s on Decimal)"
    )


# ── Step 1.8a: persist per-trade reasoning ────────────────────────────────────
def test_reasoning_payload_extracts_the_why():
    """_reasoning_payload pulls component_scores + reasoning + regime off a
    SignalResult (the explainability data the pure functions already compute)."""
    from app.services.ledger_service import _reasoning_payload

    sr = SignalResult(
        signal="BUY", confidence=0.7, weighted_score=0.5,
        component_scores={"tech": 0.6, "sentiment": 0.2},
        config_version="abc123def456",
        reasoning=["tech strong", "sentiment neutral"],
        regime="trending_up",
    )
    assert _reasoning_payload(sr) == {
        "component_scores": {"tech": 0.6, "sentiment": 0.2},
        "reasoning": ["tech strong", "sentiment neutral"],
        "regime": "trending_up",
    }
    # None signal → None payload (no reasoning to record).
    assert _reasoning_payload(None) is None


def test_paper_trade_model_has_reasoning_columns():
    """PaperTrade declares entry_reasoning + exit_reasoning (the 'why' JSONB)."""
    import app.models.ledger as ledger
    cols = {c.name for c in ledger.PaperTrade.__table__.columns}
    assert "entry_reasoning" in cols and "exit_reasoning" in cols, (
        f"missing reasoning columns; have {sorted(cols)}"
    )


def test_open_close_trade_persist_reasoning():
    """open_trade sets entry_reasoning and close_trade sets exit_reasoning via
    _reasoning_payload (so day-1 trades carry their 'why'). Source guard."""
    src = _src("app/services/ledger_service.py")
    assert "entry_reasoning=_reasoning_payload(signal_result)" in src, (
        "open_trade must persist entry_reasoning"
    )
    assert "trade.exit_reasoning = _reasoning_payload(signal_result)" in src, (
        "close_trade must persist exit_reasoning"
    )


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
