"""
Central pattern-detection thresholds for the swing-trading background tasks.

The 4 task sites — ``analysis_tasks.analyze_stock_comprehensive`` and the three
``processor_tasks.detect_patterns_*`` priority tasks — previously hardcoded these
identical kwargs. Centralizing them:
  - removes the 4x duplication, and
  - makes the pattern over-filtering (audit P1/P2 — "are the strict thresholds too
    strict, starving recall?") tunable in ONE place instead of across 4 sites.

Notes on the values:
  - 'Rounding Top' / 'Rounding Bottom' are excluded because they historically
    produced high false positives.
  - ``min_r_squared=0.85`` + ``min_confidence=0.7`` are the strict filters under
    review for being too aggressive.

These accessors return FRESH dicts so call sites can ``**``-spread them without
risking shared-state mutation. The HTTP route (``routes/chart_patterns.py``)
intentionally uses its OWN looser Pydantic defaults (return-everything) and is
NOT wired here — it is a client-tuning boundary, not a copy of these thresholds.

(Stage 3 collapse — see plan expressive-shimmying-quail.)
"""


def swing_detector_kwargs():
    """Constructor kwargs for MultiTimeframePatternDetector (formation/quality gates)."""
    return {
        "min_pattern_length": 5,
        "peak_order": 5,
        "min_confidence": 0.7,
        "min_r_squared": 0.85,
    }


def swing_detect_kwargs():
    """``detect_all_patterns`` kwargs (lookback window + overlap/exclude filtering)."""
    return {
        "days": 30,
        "exclude_patterns": ["Rounding Top", "Rounding Bottom"],
        "remove_overlaps": True,
        "overlap_threshold": 0.3,
    }
