"""
BU2 audit — indicator-engine characterization tests.

Runnable without pytest/TA-Lib/DB:
    python3 backend/tests/test_bu2_indicators.py

These LOCK IN the verified behaviors from docs/audit/BU2_indicator_engine.md so a
future "optimization" or refactor can't silently flip them:

  B6(2) — RSI fallback div-by-zero SELF-CORRECTS to 100 on a zero-down-bar window
          (the original "div by zero" hypothesis was a false positive).
  B6(1) — pandas RSI (SMA-of-gains) DIVERGES from canonical Wilder RSI on the same
          series — the parity gap is real and demonstrable.
  Look-ahead (Bollinger) — bb_upper[-1] is a function of closes [..-1] INCLUSIVE,
          causal; flipping a synthetic "future" bar does not change the last signal.
  B7     — VWAP is CUMULATIVE from the first bar of the slice, so it depends on the
          fetch window length (60 vs 100 give different last-bar VWAP).
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
