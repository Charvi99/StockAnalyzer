#!/usr/bin/env python3
"""
Point-in-time causality guard for the alternative-data attribution scripts.

Pure-Python SOURCE guard (repo convention: no DB, no pytest). The AST no-look-
ahead guard (test_backtest_no_lookahead.py) scopes ONLY the backtest adapter;
these standalone attribution scripts enforce causality themselves, so this test
statically confirms they do.

Invariant every <source>_attribution.py must satisfy:
  The signal as-of trading date T is built ONLY from source rows whose
  PUBLICATION date (public_date + a publication lag) is <= T. Concretely each
  script must:
    (a) use a CAUSAL lookup  -- pandas merge_asof(direction="backward") on a
        publication timestamp, OR numpy searchsorted(side="left") onto the
        trading-day index (first trading day >= publication); AND
    (b) apply a PUBLICATION LAG (a + pd.Timedelta(...) shift on the public date,
        e.g. FINRA T+1, SEC +1d), so the signal is not readable before the data
        is actually public; AND
    (c) never use merge_asof(direction="forward") on the publication key.

Run: python3 backend/tests/test_alt_attribution_point_in_time.py
"""
import ast
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
# Guard only the alt-data attribution scripts built on the shared harness
# (they `import attribution_lib`). Older scripts (sentiment_attribution,
# component_attribution) predate the harness, use their own validated causal
# idioms, and are out of scope for this guard.
ATTRIB_FILES = sorted(
    p for p in SCRIPTS_DIR.glob("*_attribution.py")
    if "attribution_lib" in p.read_text()
)


def _uses_causal_lookup(src: str) -> bool:
    if 'direction="backward"' in src or "direction='backward'" in src:
        return True
    if 'side="left"' in src or "side='left'" in src:
        return True
    return False


def _uses_publication_lag(src: str) -> bool:
    if re.search(r"\+\s*pd\.Timedelta\(", src):
        return True
    if re.search(r"\bPUB_LAG\b|\bSI_PUB_LAG\b|\bSV_PUB_LAG\b", src):
        return True
    return False


def _no_future_lookup(src: str) -> bool:
    if 'direction="forward"' in src or "direction='forward'" in src:
        return False
    return True


def check_file(path: Path) -> list:
    src = path.read_text()
    try:
        ast.parse(src)
    except SyntaxError as e:
        return [f"{path.name}: syntax error {e}"]
    errs = []
    if not _uses_causal_lookup(src):
        errs.append(f"{path.name}: no causal lookup (merge_asof backward / searchsorted left)")
    if not _uses_publication_lag(src):
        errs.append(f"{path.name}: no publication lag (+ pd.Timedelta / PUB_LAG)")
    if not _no_future_lookup(src):
        errs.append(f"{path.name}: forbidden future lookup (direction='forward')")
    return errs


def main():
    if not ATTRIB_FILES:
        print("no *_attribution.py scripts found — nothing to guard")
        return 0
    all_errs = []
    print(f"checking {len(ATTRIB_FILES)} attribution script(s) for point-in-time causality:")
    for p in ATTRIB_FILES:
        errs = check_file(p)
        if errs:
            for e in errs:
                print(f"  FAIL  {e}")
            all_errs.extend(errs)
        else:
            print(f"  OK    {p.name}")
    if all_errs:
        print(f"\n{len(all_errs)} causality violation(s) — fix before trusting any IC.")
        return 1
    print("\nAll attribution scripts enforce public_date <= T (causal construction).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
