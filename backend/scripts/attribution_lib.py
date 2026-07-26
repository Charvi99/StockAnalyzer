"""
Shared attribution harness for the alternative-data edge probes.

Extracted from backend/scripts/sentiment_attribution.py (the proven shape):
build a signal as-of each trading date T from CAUSAL data (public_date <= T),
compare it to forward returns, and report Spearman rank IC (val / train), N,
coverage, and sign hit-rate. Train/val is a chronological 0.7/0.3 split.

Each <source>_attribution.py is a thin caller:
  db = session()
  prices = load_universe(db, max_stocks, start, end)        # {sid: DataFrame[ts,close]}
  <load source table; build per-stock signal column(s) aligned by T>
  df = long-form: columns = [sid, T, <sig cols...>, fwd_5, fwd_10, fwd_21]
  run_attribution("SOURCE", df, [(label, col), ...])

NO-LOOK-AHEAD invariant: the signal for date T must be built ONLY from source
rows with public_date <= T (filing_date / settlement_date / date). Enforced by
construction in each caller; backend/tests/test_alt_attribution_point_in_time.py
guards it. (The AST no-look-ahead guard scopes only the backtest adapter, not
these standalone scripts.)

Forward returns are the LABEL (close[T+h]/close[T]-1), never a feature.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import text

from app.db.database import SessionLocal

HORIZONS = [5, 10, 21]


def session():
    return SessionLocal()


def load_universe(db, max_stocks: int, start: str, end: str) -> Dict[int, pd.DataFrame]:
    """First max_stocks-by-id (matches runner.prepare_backtest's ORDER BY id LIMIT N)
    + daily closes. Returns {sid: DataFrame[ts, close]} trimmed to [start, end]."""
    rows = db.execute(
        text("""
            SELECT s.id AS sid, sp.timestamp AS ts, sp.close AS close
            FROM stocks s
            JOIN stock_prices sp ON sp.stock_id = s.id AND sp.timeframe = '1d'
            WHERE s.id <= (SELECT id FROM stocks ORDER BY id LIMIT 1 OFFSET :lim_minus_1)
              AND sp.timestamp >= :warmup
            ORDER BY s.id, sp.timestamp
        """),
        {"lim_minus_1": max_stocks - 1, "warmup": pd.Timestamp(start) - pd.Timedelta(days=400)},
    ).all()
    prices: Dict[int, list] = {}
    for sid, ts, close in rows:
        prices.setdefault(sid, []).append((pd.Timestamp(ts).tz_convert("UTC").normalize(), float(close)))
    out: Dict[int, pd.DataFrame] = {}
    s_lo, s_hi = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    for sid, recs in prices.items():
        df = pd.DataFrame(recs, columns=["ts", "close"]).drop_duplicates("ts").sort_values("ts")
        df = df[(df["ts"] >= s_lo) & (df["ts"] <= s_hi)].reset_index(drop=True)
        if len(df) > 30:
            out[sid] = df
    return out


def attach_forward_returns(df: pd.DataFrame, horizons: List[int] = HORIZONS) -> pd.DataFrame:
    """Add fwd_{h} columns = close[T+h]/close[T]-1 to a per-stock price frame
    (sorted by ts). These are LABELS — computed from future prices, never used
    as features."""
    closes = df["close"].to_numpy()
    n = len(df)
    for h in horizons:
        fwd = np.full(n, np.nan)
        for i in range(n):
            j = i + h
            if j < n and closes[i] and np.isfinite(closes[j]):
                fwd[i] = closes[j] / closes[i] - 1.0
        df[f"fwd_{h}"] = fwd
    return df


def rank_ic(sig, ret) -> Tuple[float, int]:
    """Spearman rank IC over non-null pairs; returns (ic, n). NaN if n<30."""
    mask = sig.notna() & ret.notna()
    n = int(mask.sum())
    if n < 30:
        return np.nan, n
    r, _ = spearmanr(sig[mask], ret[mask])
    return (float(r) if np.isfinite(r) else np.nan), n


def chronological_split(df: pd.DataFrame, train_split: float = 0.7):
    """Chronological split on the T column -> (train, val, split_ts)."""
    all_ts = sorted(df["T"].unique())
    split = all_ts[int(len(all_ts) * train_split)]
    return df[df["T"] < split], df[df["T"] >= split], split


def run_attribution(
    name: str,
    df: pd.DataFrame,
    sig_specs: List[Tuple[str, str]],
    horizons: List[int] = HORIZONS,
    train_split: float = 0.7,
    baseline_hint: str = "",
):
    """Print the val/train IC table for the given signal columns.

    Args:
        name: human label for the source.
        df: long-form frame with columns T, fwd_{h}, and one column per signal.
        sig_specs: list of (label, column_name) — each signal to score.
    """
    train, val, split = chronological_split(df, train_split)
    print(f"\n{'=' * 74}\n{name} rank IC  (val / train, N=val-with-signal)\n{'=' * 74}")
    print(f"samples: {len(df)}  train={len(train)} val={len(val)} (split {pd.Timestamp(split).date()})")
    print(f"{'signal':<24}" + "".join(f"{f'h=' + str(h):>20}" for h in horizons))
    print("-" * 84)
    for label, col in sig_specs:
        cells = []
        for h in horizons:
            ic_v, n_v = rank_ic(val[col], val[f"fwd_{h}"])
            ic_t, _ = rank_ic(train[col], train[f"fwd_{h}"])
            cells.append(f"{ic_v:+.3f}/{ic_t:+.3f}({n_v})")
        print(f"{label:<24}" + "".join(f"{c:>20}" for c in cells))

    label0, col0 = sig_specs[0]
    cov = df[col0].notna().mean()
    print(f"\ncoverage ({label0}, samples with signal): {cov:.1%}")
    h0 = horizons[0]
    m = val[col0].notna() & val[f"fwd_{h0}"].notna()
    if int(m.sum()) > 0:
        hit = (np.sign(val.loc[m, col0]) == np.sign(val.loc[m, f"fwd_{h0}"])).mean()
        print(f"hit-rate (val, sign match, {label0} h={h0}): {hit:.1%}  (>52% real; ~50% coin flip)")
    print(
        f"\nInterpretation: compare to the OHLCV/sentiment baseline (~0.00) and\n"
        f"RSI (+0.06 -> +0.14). val IC persistently > 0.03-0.05 across signals /\n"
        f"horizons = first real edge -> engine-wiring candidate. {baseline_hint}\n"
        f"{'=' * 74}"
    )
