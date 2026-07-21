"""
Strategy registry characterization tests (Phase 0.5).

Locks the rewritten :mod:`app.services.strategies` package:
  - auto-discovery finds the 5 built-in strategies (no manual list),
  - the registry holds CLASSES, not instances — fresh per call (audit S1),
  - parameter overrides never leak across calls (S1 regression),
  - canonical param names only; unknown keys rejected (S3),
  - the pure ``compute_strategy_consensus`` aggregates strategies into one vote,
  - the strategy-consensus source has a stable ``config_version``-style hash.

Runnable without pytest/DB:
    python3 backend/tests/test_strategy_registry.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.strategies import strategy_manager  # noqa: E402


def _ohlcv(n=60, start=100.0, end=110.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = np.linspace(start, end, n)
    return pd.DataFrame({
        "timestamp": idx, "open": close, "high": close + 1.0, "low": close - 1.0,
        "close": close, "volume": np.full(n, 1000.0),
    })


def _bullish_indicators():
    """An indicator dict that pushes most strategies toward BUY."""
    return {
        'RSI': {'value': 25.0},
        'MACD': {'macd': 0.5, 'signal_line': 0.2, 'histogram': 0.3},
        'Moving_Averages': {'ma_short': 109.0, 'ma_long': 104.0},
        'Bollinger_Bands': {'upper': 116.0, 'middle': 105.0, 'lower': 98.0},
        'ADX': {'value': 30.0},
    }


# ── auto-discovery ──────────────────────────────────────────────────────────
def test_auto_discovery_finds_five_strategies():
    names = {s['name'] for s in strategy_manager.list_strategies()}
    assert len(names) == 5, f"expected 5 built-in strategies, got {sorted(names)}"
    assert "RSI Oversold/Overbought" in names
    assert "MACD Crossover" in names


# ── S1: registry holds classes; instances are fresh & isolated ──────────────
def test_get_strategy_returns_fresh_instances():
    a = strategy_manager.get_strategy("RSI Oversold/Overbought")
    b = strategy_manager.get_strategy("RSI Oversold/Overbought")
    assert a is not None and b is not None
    assert a is not b, "get_strategy must return a fresh instance each call (S1)"


def test_s1_no_param_leak_across_calls():
    """Mutating one instance (or constructing with overrides) must not leak into
    a later default instance. This is the audit-S1 regression test."""
    overridden = strategy_manager.get_strategy("RSI Oversold/Overbought")
    overridden.set_parameters({'oversold_threshold': 20})  # mutate this instance
    assert overridden.parameters['oversold_threshold'] == 20

    fresh = strategy_manager.get_strategy("RSI Oversold/Overbought")
    assert fresh.parameters['oversold_threshold'] == 30, (
        "override leaked into a fresh instance (S1 regression)"
    )


# ── S3: canonical param names ───────────────────────────────────────────────
def test_macd_uses_canonical_indicator_param_names():
    """S3 root fix: MACD params are macd_fast/macd_slow/macd_signal (matching
    calculate_all_indicators kwargs), not the old fast_period/slow_period."""
    params = strategy_manager.get_strategy("MACD Crossover").get_default_parameters()
    assert {"macd_fast", "macd_slow", "macd_signal"} <= set(params), params
    assert "fast_period" not in params and "slow_period" not in params


def test_validate_parameters_rejects_unknown_keys():
    try:
        strategy_manager.validate_parameters("MACD Crossover", {"fast_period": 12})
        assert False, "unknown key 'fast_period' was accepted (S3)"
    except ValueError:
        pass  # expected
    # canonical names are accepted
    strategy_manager.validate_parameters("MACD Crossover", {"macd_fast": 8})
    # None / empty is accepted
    strategy_manager.validate_parameters("MACD Crossover", None)


# ── pure consensus ──────────────────────────────────────────────────────────
def test_consensus_bullish_when_strategies_agree():
    rec, conf, breakdown = strategy_manager.compute_strategy_consensus(
        _ohlcv(), _bullish_indicators()
    )
    assert rec == "BUY", f"expected BUY consensus, got {rec}"
    assert conf is not None and conf > 0
    assert len(breakdown) == 5
    assert all(b['signal'] in ('BUY', 'SELL', 'HOLD', 'ERROR') for b in breakdown)


def test_consensus_none_when_no_strategy_votes():
    """A too-short frame makes every strategy return HOLD @0.0 (insufficient
    data) → no usable votes → consensus (None, None)."""
    short = _ohlcv(n=5)  # below every strategy's min_data_points
    rec, conf, breakdown = strategy_manager.compute_strategy_consensus(short, {})
    assert rec is None and conf is None
    assert len(breakdown) == 5
    # the breakdown still lists each strategy (as HOLD/insufficient), not ERROR
    assert all(b['signal'] in ('HOLD', 'ERROR') for b in breakdown)


def test_consensus_overrides_flow_through():
    """Per-strategy canonical-param overrides change the outcome (RSI threshold)."""
    df = _ohlcv()
    ind = {'RSI': {'value': 35.0}, 'MACD': {'macd': 0.0, 'signal_line': 0.0, 'histogram': 0.0},
           'Moving_Averages': {'ma_short': 100.0, 'ma_long': 100.0},
           'Bollinger_Bands': {'upper': 110, 'middle': 105, 'lower': 100}, 'ADX': {'value': 10.0}}
    # default oversold=30 -> RSI(35) is neutral HOLD; override oversold=40 -> RSI(35) is BUY
    breakdown_default = strategy_manager.compute_strategy_consensus(df, ind)[2]
    breakdown_override = strategy_manager.compute_strategy_consensus(
        df, ind, overrides={'RSI Oversold/Overbought': {'oversold_threshold': 40}}
    )[2]
    rsi_default = next(b for b in breakdown_default if b['name'] == 'RSI Oversold/Overbought')
    rsi_override = next(b for b in breakdown_override if b['name'] == 'RSI Oversold/Overbought')
    assert rsi_default['signal'] == 'HOLD'
    assert rsi_override['signal'] == 'BUY', "override did not flow through to the strategy"


# ── source version (ledger key) ─────────────────────────────────────────────
def test_source_version_is_stable_hash():
    v = strategy_manager.source_version
    assert isinstance(v, str) and len(v) == 12
    assert v == strategy_manager.source_version  # stable across reads


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
            except Exception as e:
                failures += 1
                print(f"ERROR {name}: {e!r}")
    print(f"\n{'All passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
