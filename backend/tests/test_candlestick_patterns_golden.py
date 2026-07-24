"""
Golden equivalence test for the candlestick-pattern detector vectorization.

Mirrors ``test_chart_patterns_golden.py``: the vectorization (numpy array
accessors instead of per-bar ``df.iloc[i]`` Series creation) must preserve EXACT
output — ``CandlestickPatternDetector(df).detect_all_patterns()`` must be
bit-identical to the pre-refactor reference (``CandlestickPatternDetectorRef`` in
``tests/_candlestick_patterns_ref.py`` — a frozen snapshot of the detector) on
every pattern-dict field. The detector is on the LIVE paper-trading + GA path, so
output-equivalence is the hard gate.

Run in the container (needs scipy + the DB):
    docker exec stock_analyzer_backend python /app/tests/test_candlestick_patterns_golden.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.models.stock import Stock, StockPrice  # noqa: E402
from app.services.candlestick_patterns import CandlestickPatternDetector  # noqa: E402
from tests._candlestick_patterns_ref import CandlestickPatternDetectorRef  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if (detail and not cond) else ""))
    if not cond:
        FAILURES.append(name)


def _deep_equal(a, b, tol=1e-12):
    """Recursive equality: floats within tol, dicts/lists/strings exact."""
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= tol
        except (TypeError, ValueError):
            return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(_deep_equal(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_deep_equal(x, y, tol) for x, y in zip(a, b))
    return a == b


def _sort_key(p):
    return (str(p.get("pattern_name")), str(p.get("pattern_type")), str(p.get("timestamp")))


def _compare(df, tag):
    ref = sorted(CandlestickPatternDetectorRef(df.copy()).detect_all_patterns(), key=_sort_key)
    live = sorted(CandlestickPatternDetector(df.copy()).detect_all_patterns(), key=_sort_key)
    if len(ref) != len(live):
        check(f"{tag}: pattern count", False, f"ref={len(ref)} live={len(live)}")
        return len(ref)
    for i, (r, l) in enumerate(zip(ref, live)):
        if not _deep_equal(r, l):
            check(f"{tag}: pattern #{i} ({r.get('pattern_name')})", False,
                  f"\n   ref={r}\n   live={l}")
            break
    else:
        check(f"{tag}: {len(ref)} patterns bit-exact", True)
    return len(ref)


def _load_dfs():
    db = SessionLocal()
    out = []
    for s in db.query(Stock).order_by(Stock.id).limit(8).all():
        rows = (db.query(StockPrice)
                .filter(StockPrice.stock_id == s.id, StockPrice.timeframe == "1d")
                .order_by(StockPrice.timestamp.asc()).all())
        if len(rows) < 260:
            continue
        df = pd.DataFrame([{"timestamp": r.timestamp, "open": float(r.open), "high": float(r.high),
                            "low": float(r.low), "close": float(r.close), "volume": int(r.volume or 0)}
                           for r in rows])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.normalize()
        df = df.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp").reset_index(drop=True)
        out.append((s.symbol, df))
    db.close()
    return out


def main():
    print("[1] ref == live, bit-exact, across real stocks × window sizes")
    dfs = _load_dfs()
    print(f"    loaded {len(dfs)} stocks")
    total = 0
    # CANDLE_LOOKBACK=60 is the production window; larger windows exercise more
    # bars (more loop iterations across the vectorized paths) for coverage.
    for sym, df in dfs:
        for window in (60, 120, 250):
            if len(df) < window:
                continue
            # Several as-of truncation points so different tail(60/120/250) sets run.
            for off in (1, 40, 90):
                if off >= len(df):
                    continue
                base = df.iloc[: len(df) - off + 1]
                if len(base) < window:
                    continue
                w = base.tail(window).copy()
                total += _compare(w, f"{sym}@win{window}-off{off}")

    print(f"\ncompared {total} patterns total across all windows")
    check("at least one pattern fired (coverage)", total > 0, f"total={total}")


if __name__ == "__main__":
    print("=" * 60)
    print("test_candlestick_patterns_golden (ref == vectorized)")
    print("=" * 60)
    main()
    print("=" * 60)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s): {FAILURES}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
    sys.exit(0)
