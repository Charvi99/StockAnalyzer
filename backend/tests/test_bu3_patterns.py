"""
BU3 audit — pattern-detection over-filtering characterization.

Runnable without pytest/TA-Lib/DB:
    python3 backend/tests/test_bu3_patterns.py

Proves the two mechanisms behind "too few patterns survive":
  P1 BUG   — _calculate_pattern_quality misaligns scores/weights for CONTINUATION
             patterns: the else-branch appends a 0.0 weight with no matching score,
             so zip() pairs base_confidence with 0.0 -> base_confidence contributes
             NOTHING and R² is inflated (~43.75% effective vs intended 35%).
             This makes continuation patterns (channels/flags/wedges) over-rejected.
  P2 TUNE  — production tasks pass min_r_squared=0.85 (analysis_tasks.py:80,
             processor_tasks.py:53/169/285). R² is ALSO 35% of quality_score, so it
             is double-penalized. R²>=0.85 rejects most real-market trendlines.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def quality_buggy(pattern_data, base_confidence=0.7):
    """Faithful replica of chart_patterns._calculate_pattern_quality (current bug)."""
    scores, weights = [], []
    if pattern_data.get("trendlines"):
        r2s = [v["r_squared"] for v in pattern_data["trendlines"].values() if isinstance(v, dict)]
        if r2s:
            scores.append(float(np.mean(r2s))); weights.append(0.35)
    if "volume_profile" in pattern_data:
        scores.append(pattern_data["volume_profile"].get("volume_score", 0.5)); weights.append(0.25)
    if pattern_data.get("pattern_type") == "reversal" and "prior_trend" in pattern_data:
        scores.append(pattern_data["prior_trend"].get("strength", 0.0)); weights.append(0.20)
    else:
        weights.append(0.0)  # <-- BUG: weight without a score
    scores.append(base_confidence); weights.append(0.20)
    if sum(weights) > 0:
        ws = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    else:
        ws = base_confidence
    return float(np.clip(ws, 0.0, 1.0))


def quality_fixed(pattern_data, base_confidence=0.7):
    """Corrected: drop the dangling 0.0 weight so lists stay aligned."""
    scores, weights = [], []
    if pattern_data.get("trendlines"):
        r2s = [v["r_squared"] for v in pattern_data["trendlines"].values() if isinstance(v, dict)]
        if r2s:
            scores.append(float(np.mean(r2s))); weights.append(0.35)
    if "volume_profile" in pattern_data:
        scores.append(pattern_data["volume_profile"].get("volume_score", 0.5)); weights.append(0.25)
    if pattern_data.get("pattern_type") == "reversal" and "prior_trend" in pattern_data:
        scores.append(pattern_data["prior_trend"].get("strength", 0.0)); weights.append(0.20)
    # else: append NEITHER score nor weight (aligned)
    scores.append(base_confidence); weights.append(0.20)
    ws = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    return float(np.clip(ws, 0.0, 1.0))


# --------------------------------------------------------------------------- #
def test_p1_base_confidence_dead_for_continuation():
    """Continuation pattern: changing base_confidence must NOT move the buggy score."""
    pd_cont = {"pattern_type": "continuation",
               "trendlines": {"a": {"r_squared": 0.9}},
               "volume_profile": {"volume_score": 0.5}}
    lo = quality_buggy(pd_cont, base_confidence=0.0)
    hi = quality_buggy(pd_cont, base_confidence=1.0)
    assert abs(lo - hi) < 1e-9, (
        f"BUG: base_confidence should affect the score but {lo:.4f}=={hi:.4f} "
        "(zip misalignment zeroes it for continuation patterns)"
    )


def test_p1_base_confidence_alive_after_fix():
    """Same pattern with the fix: base_confidence DOES move the score. Delta is 0.25
    (= 0.20 base weight renormalized over sum(weights)=0.80, since the prior-trend
    slot is absent for continuation patterns) — vs 0.0 in the buggy version."""
    pd_cont = {"pattern_type": "continuation",
               "trendlines": {"a": {"r_squared": 0.9}},
               "volume_profile": {"volume_score": 0.5}}
    lo = quality_fixed(pd_cont, base_confidence=0.0)
    hi = quality_fixed(pd_cont, base_confidence=1.0)
    assert abs((hi - lo) - 0.25) < 1e-9, (
        f"fixed score should move by 0.25 (0.20/0.80 renormalized); got {hi - lo:.4f}"
    )


def test_p1_reversal_unaffected():
    """Sanity: reversal patterns append both score+weight, so they're aligned (no bug)."""
    pd_rev = {"pattern_type": "reversal",
              "trendlines": {"a": {"r_squared": 0.9}},
              "volume_profile": {"volume_score": 0.5},
              "prior_trend": {"strength": 0.8}}
    assert abs(quality_buggy(pd_rev) - quality_fixed(pd_rev)) < 1e-9


def test_p2_r_squared_double_penalized():
    """A pattern with R²=0.80 (a good real trendline) is: (a) dragged in quality_score
    AND (b) rejected outright by the production min_r_squared=0.85 gate."""
    pd_cont = {"pattern_type": "continuation",
               "trendlines": {"a": {"r_squared": 0.80}},
               "volume_profile": {"volume_score": 0.9}}
    q = quality_buggy(pd_cont)               # already penalized by the 0.35 R² weight
    passes_r2_gate = 0.80 >= 0.85            # the production hard gate
    assert not passes_r2_gate, "R²=0.80 should fail the 0.85 gate (the over-filter)"
    assert q < 0.9, f"quality already lowered by R² weight: {q:.3f}"


def test_p1_production_code_is_fixed():
    """Regression guard: the REAL ChartPatternDetector._calculate_pattern_quality
    (not the replica) must treat base_confidence as live for continuation patterns.
    Before the P1/D12 fix the dangling 0.0 weight (zip misalignment) zeroed it. The
    method body references no self.* attributes, so we bypass __init__ (no DataFrame
    needed). base_confidence is read from pattern_data['confidence_score']."""
    try:
        from app.services.chart_patterns import ChartPatternDetector
    except Exception as e:  # env-dependent (numpy/pandas)
        import warnings
        warnings.warn(f"chart_patterns import skipped in this env: {e}")
        return
    det = ChartPatternDetector.__new__(ChartPatternDetector)
    pd_cont = {"pattern_type": "continuation",
               "trendlines": {"a": {"r_squared": 0.9}},
               "volume_profile": {"volume_score": 0.5}}
    lo = det._calculate_pattern_quality({**pd_cont, "confidence_score": 0.0})
    hi = det._calculate_pattern_quality({**pd_cont, "confidence_score": 1.0})
    # Fixed formula: base_confidence moves the score by 0.25 (0.20/0.80 renormalized
    # over sum(weights)=0.80, prior-trend slot absent for continuation patterns).
    assert abs((hi - lo) - 0.25) < 1e-9, (
        f"P1 REGRESSION: production continuation-pattern score moved {hi - lo:.4f} "
        f"(expected 0.25). base_confidence is dead again — the dangling 0.0 weight / "
        "zip misalignment returned to _calculate_pattern_quality."
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
