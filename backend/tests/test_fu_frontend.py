"""
FU frontend audit — source-inspection tests (runnable without node_modules):
    python3 backend/tests/test_fu_frontend.py

Static guards for the frontend findings (proper component tests should use the
CRA jest setup; this is a no-dep guard that reads the .jsx/.js sources):
  POSITIVE — api.js is centralized + env-configured (REACT_APP_API_URL).
  POSITIVE — polling effect cleans up its interval (no leak) — FU2 false-positive lock.
  FU3      — counts dev markers (console.log/TODO/FIXME/HACK); asserts the known noise exists.
  FU1      — confirms multiple components import services/api (no data layer).
"""
import sys
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")


def _read(rel):
    path = os.path.join(ROOT, rel)
    try:
        with open(path) as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def _grep(pattern, where="components"):
    import re
    base = os.path.join(ROOT, where)
    hits = []
    if not os.path.isdir(base):
        return hits
    for fn in sorted(os.listdir(base)):
        if not (fn.endswith(".jsx") or fn.endswith(".js")):
            continue
        src = _read(os.path.join(where, fn))
        for m in re.finditer(pattern, src):
            line = src[: m.start()].count("\n") + 1
            hits.append(f"{fn}:{line}")
    return hits


def test_positive_api_layer_is_centralized_and_env_configured():
    api = _read(os.path.join("services", "api.js"))
    assert "axios.create" in api, "expected a single axios instance"
    assert "REACT_APP_API_URL" in api, "base URL must be env-configurable"


def test_positive_polling_cleans_up_interval_no_leak():
    """FU2 false-positive lock: the StockList polling effect DOES clear its interval."""
    src = _read(os.path.join("components", "StockList.jsx"))
    assert "setInterval" in src and "clearInterval" in src, (
        "polling present but cleanup missing — re-check FU2"
    )


def test_fu1_multiple_components_import_api_directly():
    """No data layer: several components import services/api themselves."""
    importers = _grep(r"services/api")
    assert len(importers) >= 6, (
        f"expected >=6 components to import services/api (no data layer); got {len(importers)}"
    )


def test_fu3_dev_markers_present():
    """FU3: dev noise (console.log/TODO/FIXME/HACK) exists in components. If cleaned up,
    update the FU report."""
    markers = _grep(r"console\.log|TODO|FIXME|HACK")
    assert len(markers) >= 20, (
        f"expected substantial dev-marker noise (FU3); found only {len(markers)}"
    )
    print(f"   FU3 dev markers across components: {len(markers)}")


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
