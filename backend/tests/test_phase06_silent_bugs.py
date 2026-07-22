"""
Phase 0.6 silent-bug regression tests.

Locks the audit's silent-failure fixes so they can't regress. These are
source/AST-inspection tests (no DB, no pytest, no running stack) — they mirror
the characterization-test convention used across the ``backend/tests`` suite
(grep/AST guards, like ``test_bu6_schema`` / ``test_bu7_routes``).

Covered here:
  H1  double-scheduled comprehensive analysis (now batched by fetched stock_ids)
  H2  dead task_annotations referencing non-existent tasks (removed)
  H7  async def route handlers blocking the event loop (now sync def)

(H3/H4/H6 tests are added alongside their fixes in later commits.)

Runnable without pytest/DB:
    python3 backend/tests/test_phase06_silent_bugs.py
"""
import ast
import os
import sys

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND)


def _src(rel: str) -> str:
    with open(os.path.join(BACKEND, rel), encoding="utf-8") as fh:
        return fh.read()


# ── H7: the 5 analysis endpoints must be plain def, not async def ───────────
# They do sync SQLAlchemy work; async def blocks the event loop. FastAPI runs
# plain def handlers in a threadpool, which is the correct choice here.
_ANALYSIS_ENDPOINTS = (
    "analyze_complete",
    "calculate_order_parameters",
    "calculate_trailing_stop",
    "calculate_portfolio_risk",
    "get_market_regime",
)


def test_h7_analysis_endpoints_are_sync():
    tree = ast.parse(_src("app/api/routes/analysis.py"))
    funcs = {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in _ANALYSIS_ENDPOINTS:
        assert name in funcs, f"{name} not found in analysis.py"
        assert isinstance(funcs[name], ast.FunctionDef), (
            f"H7: {name} must be a plain def, not async def "
            "(async handlers do sync DB work and block the event loop)"
        )


# ── H2: no dead task_annotations referencing non-existent tasks ─────────────
# The old block keyed fetch_stock_prices / fetch_stock_news / fetch_stock_metadata,
# none of which exist (real tasks are fetch_high/medium/low_priority_stocks etc.),
# so the rate-limits were no-ops. The block was removed. This guard inspects the
# actual task_annotations dict keys (AST), so comments are ignored and a legit
# future re-add pointing at REAL tasks is allowed.
_DEAD_TASK_NAMES = ("fetch_stock_prices", "fetch_stock_news", "fetch_stock_metadata")


def _task_annotation_keys(tree):
    """Yield every key string literal from any task_annotations mapping in the module."""
    for node in ast.walk(tree):
        # task_annotations={...} passed as a kwarg (Celery(...) / conf.update(...))
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "task_annotations" and isinstance(kw.value, ast.Dict):
                    for key in kw.value.keys:
                        if isinstance(key, ast.Constant):
                            yield str(key.value)
        # conf.task_annotations = {...}
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Attribute) and tgt.attr == "task_annotations"
                        and isinstance(node.value, ast.Dict)):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant):
                            yield str(key.value)


def test_h2_no_dead_task_annotation_names():
    for key in _task_annotation_keys(ast.parse(_src("app/celery_app.py"))):
        for dead in _DEAD_TASK_NAMES:
            assert dead not in key, (
                f"H2: dead task '{key}' in task_annotations — that task doesn't "
                f"exist, so the rate-limit was a no-op"
            )


# ── H1: comprehensive analysis must not be double-scheduled ─────────────────
# The fetch loop must NOT queue per-stock analyze_stock_comprehensive (that ran
# each stock twice per cycle, plus re-analyzed fetch failures). Analysis now
# runs once, after the batch, via analyze_<priority>_priority_stocks(stock_ids).
def test_h1_fetch_loop_does_not_queue_per_stock_analysis():
    src = _src("app/tasks/fetcher_tasks.py")
    assert "analyze_stock_comprehensive.apply_async" not in src, (
        "H1 regression: per-stock analyze_stock_comprehensive.apply_async is back "
        "in the fetch loop (causes double-scheduled analysis)"
    )


def test_h1_batch_analyzers_filter_by_stock_ids():
    tree = ast.parse(_src("app/tasks/analysis_tasks.py"))
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in ("analyze_high_priority_stocks",
                 "analyze_medium_priority_stocks",
                 "analyze_low_priority_stocks"):
        assert name in funcs, f"{name} missing from analysis_tasks.py"
        args = [a.arg for a in funcs[name].args.args]
        assert "stock_ids" in args, (
            f"H1: {name} must accept a stock_ids param so the fetch batch can "
            "restrict analysis to freshly-fetched stocks"
        )


# ── H6: partial-failure timestamp ───────────────────────────────────────────
# Verification (Phase 0.6): analyze_stock_comprehensive sets
# last_comprehensive_analysis even on partial failure, but this does NOT hide
# stale analysis in practice, because (a) the scheduled fetch→analyze pipeline
# (H1) re-runs the full analysis every fetch cycle regardless of the timestamp,
# and (b) the dashboard auto-trigger intentionally cools down via the
# `recently_analyzed` guard in the completeness check — removing it would
# reintroduce the infinite re-analysis loop (Phase 0.1 fix: sentiment/ML are
# structurally absent, capping the score at ~0.6 < 0.8, so flagging-by-score
# loops forever). So H6 is a NON-BUG given the current architecture. This test
# locks that cooldown guard so it can't be removed.
def test_h6_dashboard_refresh_keeps_cooldown_guard():
    src = _src("app/api/routes/analysis.py")
    assert "recently_analyzed" in src and "needs_refresh" in src, (
        "H6: the dashboard completeness check must keep its `recently_analyzed` "
        "cooldown guard — without it, structurally-incomplete stocks (ML/sentiment "
        "absent) re-analyze in an infinite loop. H6's 'hidden partial failure' is "
        "acceptable because the scheduled fetch→analyze pipeline retries every cycle."
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
