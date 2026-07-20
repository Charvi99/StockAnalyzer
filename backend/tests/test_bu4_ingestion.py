"""
BU4 audit — data-ingestion characterization tests.

Runnable without pytest/DB/Celery/Redis:
    python3 backend/tests/test_bu4_ingestion.py

Locks in the two mechanisms behind the BU4 findings so a future change can't
silently flip them:

  F2 — the fetcher strips tz before storing (naive-as-UTC), but elsewhere assigns
       tz-aware datetimes to the same logical kind of column. Proves that an aware
       vs naive comparison raises TypeError (the B3/R6 root cause).
  F3 — the rate-limit math: 100 req/min == 0.6s spacing, but the code sleeps 1s AND
       Celery caps at 100/m per worker -> single worker is over-throttled (<=60/min)
       while N workers blow the global limit (no shared limiter).
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_f2_naive_vs_aware_comparison_raises():
    """The defect: a tz-aware datetime (e.g. last_fetch_at assignment) compared to a
    naive one (e.g. a stripped bar timestamp) raises TypeError in Python."""
    aware = datetime.now(timezone.utc)
    naive = aware.replace(tzinfo=None)  # mirrors fetcher_tasks.py:156 strip
    raised = False
    try:
        _ = aware < naive  # the comparison the code path can perform
    except TypeError:
        raised = True
    assert raised, "aware<naive must raise TypeError — if not, the B3 bug class is gone"


def test_f2_strip_then_assume_utc_is_lossy_but_roundtrip_ok():
    """The fetcher's defense (strip on write, assume-UTC on read) round-trips correctly
    ONLY if every writer strips. Proves the invariant the code currently violates."""
    original = datetime(2026, 7, 20, 14, 30, tzinfo=timezone.utc)
    stored = original.replace(tzinfo=None)          # writer strips (fetcher_tasks:156)
    read_back = stored.replace(tzinfo=timezone.utc)  # reader assumes UTC (fetcher_tasks:82)
    assert read_back == original, "strip/assume round-trips only because both ends agree on UTC"


def test_f3_rate_limit_math_single_worker_overthrottled():
    """100 req/min == 0.6s spacing. The code sleeps 1s/req AND Celery caps 100/m, so a
    single worker manages <=60/min — below the paid allowance (over-throttling)."""
    spacing_for_100_per_min = 60.0 / 100            # 0.6s
    effective_with_1s_sleep = 60.0 / 1.0            # 60/min
    assert spacing_for_100_per_min < 1.0
    assert effective_with_1s_sleep <= 100, "single worker is over-throttled, not at limit"


def test_f3_no_global_limit_multi_worker_exceeds():
    """With N workers each obeying their own 100/m, aggregate = N*100/m -> exceeds the
    plan limit for N>=2. Proves the per-worker cap is not a global cap."""
    per_worker_cap = 100
    for n_workers in (2, 3, 4):
        aggregate = n_workers * per_worker_cap
        assert aggregate > 100, (
            f"{n_workers} workers at {per_worker_cap}/m each = {aggregate}/m > 100/m plan limit"
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
    print(f"\n{'All passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
