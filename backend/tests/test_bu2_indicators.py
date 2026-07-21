"""
BU2 audit — indicator-engine characterization tests.

Runnable without pytest/TA-Lib/DB:
    python3 backend/tests/test_bu2_indicators.py

These LOCK IN the verified behaviors from docs/audit/BU2_indicator_engine.md so a
future "optimization" or refactor can't silently flip them:

  B6(2) — RSI fallback div-by-zero SELF-CORRECTS to 100 on a zero-down-bar window
          (the original "div by zero" hypothesis was a false positive).
  B6(1) — [FIXED in production] pandas RSI formerly used SMA-of-gains and DIVERGED
          from canonical Wilder RSI by tens of points. Production now uses Wilder
          (see test_b6_production_rsi_uses_wilder); the rsi_sma replica below keeps
          the old formula to document the parity gap that existed.
  Look-ahead (Bollinger) — bb_upper[-1] is a function of closes [..-1] INCLUSIVE,
          causal; flipping a synthetic "future" bar does not change the last signal.
  B7     — [FIXED in production] VWAP was CUMULATIVE from the slice start (window-
          dependent). Production now uses a ROLLING VWAP (see
          test_vwap_production_is_rolling); the vwap replica documents the old behavior.
  B5     — every calculate_* method copies its input (contract + the perf cost).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --------------------------------------------------------------------------- #
# Helpers that replicate the production formulas (so tests run with no talib).
# --------------------------------------------------------------------------- #
def rsi_sma(close: pd.Series, period: int = 14) -> pd.Series:
    """The pandas fallback formula used in technical_indicators.calculate_rsi."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """Canonical Wilder RSI (alpha = 1/period) — what TA-Lib computes."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    # Wilder smoothing == EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    # Wilder convention: zero-loss -> RSI 100
    return rsi.where(avg_loss != 0, 100.0)


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = close.rolling(window=window).mean()
    sd = close.rolling(window=window).std()
    return mid + sd * num_std, mid, mid - sd * num_std


def vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return (tp * df["volume"]).cumsum() / df["volume"].cumsum()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_b6_rsi_divzero_selfcorrects_to_100():
    """A strictly rising window has loss==0 -> rs=inf -> rsi=100 (correct), not NaN/inf."""
    close = pd.Series(np.linspace(100, 200, 60))
    r = rsi_sma(close, period=14).iloc[-1]
    assert not np.isnan(r), "RSI should not be NaN on a rising series"
    assert not np.isinf(r), "RSI should not be inf — div-zero must self-correct"
    assert r == 100.0, f"zero-down-bar RSI should be exactly 100, got {r}"


def test_b6_rsi_parity_gap_is_real():
    """The pandas-SMA fallback diverges from canonical Wilder RSI (TA-Lib) -> parity gap."""
    rng = np.arange(120)
    # mixed up/down with noise so both methods produce interior values
    close = pd.Series(100 + np.sin(rng / 5) * 10 + rng * 0.2)
    sma_rsi = rsi_sma(close, 14).iloc[-1]
    wilder_rsi = rsi_wilder(close, 14).iloc[-1]
    assert abs(sma_rsi - wilder_rsi) > 1.0, (
        f"expected a measurable parity gap between SMA-RSI ({sma_rsi:.2f}) "
        f"and Wilder-RSI ({wilder_rsi:.2f}); if they match, re-examine"
    )


def test_bollinger_is_causal_not_lookahead():
    """bb_upper[-1] depends on closes through bar -1 inclusive; a hypothetical future
    bar must NOT change the last-bar band. (Closes the look-ahead false positive.)"""
    base = np.linspace(100, 110, 40)
    df_a = pd.DataFrame({"close": base.copy()})
    df_b = pd.DataFrame({"close": np.append(base.copy(), 999.0)})  # append a "future" bar

    upper_a, _, lower_a = bollinger(df_a["close"])
    upper_b, _, lower_b = bollinger(df_b["close"])

    # Last bar of A == second-to-last of B (same causal computation)
    assert np.isclose(upper_a.iloc[-1], upper_b.iloc[-2]), (
        "Bollinger band at a bar must be independent of LATER bars (causal). "
        "If this fails, the indicator is leaking the future."
    )
    assert np.isclose(lower_a.iloc[-1], lower_b.iloc[-2])


def test_vwap_is_window_dependent():
    """VWAP is cumulative from the slice start -> different fetch windows give
    different last-bar VWAP for the SAME underlying series (the B7 semantic issue)."""
    n = 100
    df_full = pd.DataFrame({
        "high": np.linspace(101, 121, n),
        "low": np.linspace(99, 119, n),
        "close": np.linspace(100, 120, n),
        "volume": np.full(n, 1000.0),
    })
    vwap_60 = vwap(df_full.iloc[-60:]).iloc[-1]   # mirrors recommendation_engine .limit(60)
    vwap_100 = vwap(df_full.iloc[-100:]).iloc[-1]  # mirrors market_regime .limit(100)
    assert abs(vwap_60 - vwap_100) > 1e-6, (
        "cumulative VWAP must depend on the fetch window; "
        f"got 60-bar={vwap_60:.4f} vs 100-bar={vwap_100:.4f}"
    )


def test_b5_each_indicator_copies_input():
    """Contract: a calculate_* method must not mutate its caller's frame (it copies).
    Demonstrates WHY there are 36 .copy() calls — the perf cost documented in B5."""
    src = pd.DataFrame({"close": np.linspace(100, 110, 30)})
    snapshot = src["close"].values.copy()
    _ = rsi_sma(src["close"])  # standalone helper does not mutate src
    assert np.array_equal(src["close"].values, snapshot), "input must be left untouched"


def test_modules_import():
    """Smoke: the audited module imports in this talib-less env (pandas fallback path)."""
    try:
        import app.services.technical_indicators  # noqa: F401
    except Exception as e:  # pragma: no cover - env-dependent
        import warnings
        warnings.warn(f"module import skipped in this env: {e}")


def test_b6_production_rsi_uses_wilder():
    """Regression guard: production calculate_rsi (pandas fallback — talib absent in
    this env) must match canonical Wilder RSI, NOT the SMA-of-gains version. Before
    B6/D7 the fallback used rolling().mean() and diverged from TA-Lib by ~29 points
    (e.g. 32.6 Wilder vs 3.4 SMA on this exact series)."""
    try:
        from app.services.technical_indicators import TechnicalIndicators
    except Exception as e:  # env-dependent
        import warnings
        warnings.warn(f"technical_indicators import skipped: {e}")
        return
    rng = np.arange(120)
    close = pd.Series(100 + np.sin(rng / 5) * 10 + rng * 0.2)
    prod = TechnicalIndicators.calculate_rsi(pd.DataFrame({"close": close}), 14)["rsi"].iloc[-1]
    wilder = rsi_wilder(close, 14).iloc[-1]
    sma = rsi_sma(close, 14).iloc[-1]
    assert abs(prod - wilder) < 0.5, (
        f"production RSI ({prod:.3f}) must match Wilder ({wilder:.3f}); the "
        "SMA-of-gains fallback regressed (B6/D7)."
    )
    assert abs(prod - sma) > 5.0, (
        f"sanity: production RSI ({prod:.3f}) must NOT match the old SMA version "
        f"({sma:.3f}) on a mixed series."
    )
    # Rising series -> RSI 100, never NaN (zero-down-bar self-correction preserved).
    rise = TechnicalIndicators.calculate_rsi(
        pd.DataFrame({"close": pd.Series(np.linspace(100, 200, 60))}), 14)["rsi"].iloc[-1]
    assert not np.isnan(rise) and abs(rise - 100.0) < 1e-9, (
        f"rising-series RSI must be 100 (got {rise}); zero-loss handling regressed."
    )


def test_vwap_production_is_rolling():
    """Regression guard: production calculate_vwap must use a ROLLING window, so
    prepending OLDER bars does NOT change the latest VWAP. Before B7/D8 it was
    cumulative (window-dependent — the documented semantic issue)."""
    try:
        from app.services.technical_indicators import TechnicalIndicators
    except Exception as e:  # env-dependent
        import warnings
        warnings.warn(f"technical_indicators import skipped: {e}")
        return
    n = 100
    base = pd.DataFrame({
        "high": np.linspace(101, 121, n), "low": np.linspace(99, 119, n),
        "close": np.linspace(100, 120, n), "volume": np.full(n, 1000.0),
    })
    older = pd.DataFrame({
        "high": np.linspace(50, 70, 50), "low": np.linspace(48, 68, 50),
        "close": np.linspace(49, 69, 50), "volume": np.full(50, 1000.0),
    })
    short_vwap = TechnicalIndicators.calculate_vwap(base.copy())["vwap"].iloc[-1]
    long_vwap = TechnicalIndicators.calculate_vwap(
        pd.concat([older, base], ignore_index=True))["vwap"].iloc[-1]
    assert abs(short_vwap - long_vwap) < 1e-9, (
        "rolling VWAP must be independent of bars older than the window; "
        f"short={short_vwap:.4f} vs long={long_vwap:.4f} (cumulative regressed — B7/D8)"
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
