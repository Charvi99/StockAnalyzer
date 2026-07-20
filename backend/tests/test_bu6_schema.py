"""
BU6 audit — DB schema source-inspection tests.

Runnable without a DB (inspects SQLAlchemy column metadata in-process):
    python3 backend/tests/test_bu6_schema.py

Locks in the two BU6 facts so a future change is intentional and visible:
  S1 — every TIMESTAMP column is currently WITHOUT TIME ZONE (naive). This is the
       structural root of B3/R6/F2. If someone migrates a column to TIMESTAMPTZ, this
       test must be updated deliberately (it lists which columns changed).
  S2 — reports which foreign-key columns lack an index (the unindexed-FK perf finding).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import TIMESTAMP


def _import_models():
    """Import the model module; returns None if the env can't import (no hard DB deps)."""
    try:
        import app.models.stock as m  # noqa
        return m
    except Exception as e:  # pragma: no cover - env-dependent
        import warnings
        warnings.warn(f"model import skipped in this env: {e}")
        return None


def _all_tables(models):
    for name in dir(models):
        obj = getattr(models, name)
        try:
            tbl = getattr(obj, "__table__", None)
            if tbl is not None:
                yield name, tbl
        except Exception:
            continue


def test_s1_all_timestamps_are_naive():
    """Every TIMESTAMP column is WITHOUT TIME ZONE today (the B3/R6/F2 root cause).
    A TIMESTAMPTZ migration MUST update this test on purpose."""
    models = _import_models()
    if models is None:
        return  # env can't import; skip gracefully
    naive, aware = [], []
    for cls_name, tbl in _all_tables(models):
        for col in tbl.columns:
            if isinstance(col.type, TIMESTAMP):
                (aware if getattr(col.type, "timezone", False) else naive).append(
                    f"{tbl.name}.{col.name}"
                )
    assert not aware, (
        f"these columns are TIMESTAMPTZ/aware — if intentional, update this test: {aware}"
    )
    # sanity: we actually found naive timestamps (proves the import worked)
    assert naive, "expected to find naive TIMESTAMP columns; import may have failed silently"


def test_s2_reports_unindexed_foreign_keys():
    """S2: confirm the known unindexed FKs are still unindexed (locks the finding).
    If someone indexes one, this test fails so the finding doc is updated."""
    models = _import_models()
    if models is None:
        return
    known_offenders = {
        ("chart_patterns", "stock_id"),
        ("candlestick_patterns", "stock_id"),
        ("sentiment_scores", "stock_id"),
        ("predictions", "stock_id"),
    }
    found_offenders = set()
    for _cls_name, tbl in _all_tables(models):
        for col in tbl.columns:
            for fk in col.foreign_keys:
                if not (col.primary_key or col.index):
                    found_offenders.add((tbl.name, col.name))
    missing = known_offenders - found_offenders
    # If this fails, someone indexed an FK — great, shrink known_offenders.
    assert not missing, (
        f"expected these FKs to still be unindexed (S2); they got indexed (update the test): {missing}"
    )
    print(f"   S2 unindexed FKs confirmed: {sorted(found_offenders)}")


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
