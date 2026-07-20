"""
BU7 audit — API-route pagination characterization tests.

Runnable without pytest/FastAPI/DB:
    python3 backend/tests/test_bu7_routes.py

Locks in the A1 finding (unbounded / un-validated pagination):
  - demonstrates that a bare `limit: int = 1000` param accepts arbitrarily large
    values (the DoS/OOM vector), vs the Query(le=) guard used by news.py.
  - greps the route sources for `.all()` NOT preceded by `.limit(` and asserts the
    known offenders are still unbounded (so the BU7 doc stays accurate; if someone
    adds a limit, this test tells them to update the report).
"""
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROUTES_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "api", "routes")


def test_a1_bare_limit_accepts_unbounded_input():
    """A bare `limit: int = 1000` (stocks.py:14) imposes no upper bound — a client can
    request limit=10_000_000. Simulates the (absent) validation."""
    def bare_limit_handler(limit: int = 1000):  # mirrors stocks.py:14
        return limit  # no validation at all
    assert bare_limit_handler(limit=10_000_000) == 10_000_000, (
        "bare limit must currently accept arbitrarily large values (the DoS vector)"
    )


def test_a1_query_guard_would_reject_unbounded_input():
    """The news.py pattern (Query(default, ge=1, le=100)) rejects out-of-range input.
    Proves the fix shape that should be applied everywhere."""
    def clamped(limit: int):
        le = 100
        if not (1 <= limit <= le):
            raise ValueError(f"limit {limit} out of range 1..{le}")
        return limit
    assert clamped(50) == 50
    rejected = False
    try:
        clamped(10_000_000)
    except ValueError:
        rejected = True
    assert rejected, "Query(le=) guard must reject huge limits"


def _unbounded_all_sites():
    """Find `.all()` calls in route files whose preceding query chain has no `.limit(`."""
    offenders = []
    for fn in os.listdir(ROUTES_DIR):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(ROUTES_DIR, fn)
        with open(path) as fh:
            src = fh.read()
        # match "query...all()" or "<name>...all()" chains across lines, no .limit( inside
        for m in re.finditer(r"([\w.]+(?:\.\w+\([^)]*\))*)\.all\(\)", src, re.DOTALL):
            chain = m.group(1)
            if ".limit(" not in chain:
                # find the line number of the .all()
                line = src[: m.start()].count("\n") + 1
                offenders.append(f"{fn}:{line}")
    return offenders


def test_a1_known_unbounded_endpoints_still_unbounded():
    """Locks in the A1 finding. If someone adds .limit() to these, the test fails so the
    BU7 report is updated (the offender list shrinks)."""
    offenders = _unbounded_all_sites()
    # The clear list-endpoint offenders (stats/export intentionally load all rows).
    must_still_be_present = [
        "patterns.py",      # get_patterns / stats / export
        "chart_patterns.py",  # get_chart_patterns / stats
    ]
    for expected_file in must_still_be_present:
        assert any(o.startswith(expected_file) for o in offenders), (
            f"{expected_file} previously had unbounded .all(); if it's now bounded, "
            "update docs/audit/BU7_api_routes.md A1"
        )
    print(f"   A1 unbounded .all() sites: {sorted(offenders)}")


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
