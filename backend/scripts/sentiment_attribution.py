"""
Standalone attribution: does as-of-T NEWS SENTIMENT predict forward returns?

Tests the independent-data hypothesis directly — without touching engine code.
The indicator attribution showed the price-technical stack has ~no standalone
edge (val IC ~ 0). News sentiment is INDEPENDENT of price, so it's the first
place real edge could come from. This measures whether it actually does.

METHODOLOGY (audit it):
  - Signal = news sentiment as-of each trading date T, computed causally from
    articles published in (T-lookback, T] (lookback in {7,14,30} days). STRICT
    published_utc <= T (no look-ahead). Article-weighted:
    sum(sentiment_score) / count(articles) in the window.
  - Label = forward return close[T+h]/close[T]-1, h in {5,10,21} (the LABEL, not
    a feature -> no look-ahead).
  - Edge = Spearman rank IC between signal and forward return, over samples that
    HAVE news in the window (N reported, so coverage is visible).
  - Out-of-sample: chronological 0.7 train / 0.3 val split (matches the GA);
    report val IC (+ train IC to expose any gap).

Run (after the backfill has populated the news table):
  docker exec stock_analyzer_backend python /app/scripts/sentiment_attribution.py \
      --max-stocks 100 --start 2024-06-01 --end 2026-06-01
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402

LOOKBACKS = [7, 14, 30]
HORIZONS = [5, 10, 21]


def load_universe(db, max_stocks, start, end):
    """First max_stocks-by-id (matches runner.prepare_backtest) + daily closes."""
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
    out = {}
    s_lo = pd.Timestamp(start, tz="UTC")
    s_hi = pd.Timestamp(end, tz="UTC")
    for sid, recs in prices.items():
        df = pd.DataFrame(recs, columns=["ts", "close"]).drop_duplicates("ts").sort_values("ts")
        df = df[(df["ts"] >= s_lo) & (df["ts"] <= s_hi)].reset_index(drop=True)
        if len(df) > 30:
            out[sid] = df
    return out


def load_news(db, stock_ids):
    """All news+sentiment for the universe."""
    if not stock_ids:
        return pd.DataFrame()
    rows = db.execute(
        text("SELECT stock_id, published_utc, sentiment_score FROM news "
             "WHERE stock_id = ANY(:ids) AND sentiment_score IS NOT NULL"),
        {"ids": list(stock_ids)},
    ).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([(r[0], pd.Timestamp(r[1]).tz_convert("UTC").normalize(), float(r[2])) for r in rows],
                      columns=["sid", "date", "score"])
    return df


def build_signals(prices, news, lookbacks, horizons):
    records = []
    for sid, df in prices.items():
        closes = df["close"].to_numpy()
        ts = df["ts"].to_numpy()
        fwd = {h: np.full(len(df), np.nan) for h in horizons}
        for i in range(len(df)):
            for h in horizons:
                j = i + h
                if j < len(df) and closes[i] and np.isfinite(closes[j]):
                    fwd[h][i] = closes[j] / closes[i] - 1.0
        sigs = {lb: np.full(len(df), np.nan) for lb in lookbacks}
        if not news.empty:
            st = news[news["sid"] == sid]
            if len(st):
                daily = st.groupby("date")["score"].agg(["sum", "count"])
                daily_idx = daily.index
                for lb in lookbacks:
                    for i, t in enumerate(ts):
                        t = pd.Timestamp(t)
                        lo = t - pd.Timedelta(days=lb)
                        mask = (daily_idx > lo) & (daily_idx <= t)
                        c = int(daily["count"][mask].sum())
                        if c > 0:
                            sigs[lb][i] = float(daily["sum"][mask].sum()) / c
        for i in range(len(df)):
            rec = {"sid": sid, "T": pd.Timestamp(ts[i])}
            for lb in lookbacks:
                rec[f"sig_{lb}"] = sigs[lb][i]
            for h in horizons:
                rec[f"fwd_{h}"] = fwd[h][i]
            records.append(rec)
    return pd.DataFrame.from_records(records)


def _rank_ic(sig, ret):
    mask = sig.notna() & ret.notna()
    n = int(mask.sum())
    if n < 30:
        return np.nan, n
    r, _ = spearmanr(sig[mask], ret[mask])
    return (float(r) if np.isfinite(r) else np.nan), n


def main():
    ap = argparse.ArgumentParser(description="News-sentiment attribution (standalone edge test)")
    ap.add_argument("--max-stocks", type=int, default=100)
    ap.add_argument("--start", default="2024-06-01")
    ap.add_argument("--end", default="2026-06-01")
    ap.add_argument("--train-split", type=float, default=0.7)
    args = ap.parse_args()

    db = SessionLocal()
    print(f"[sentiment] universe<= {args.max_stocks} stocks  window={args.start}..{args.end}")
    prices = load_universe(db, args.max_stocks, args.start, args.end)
    print(f"[sentiment] stocks with prices: {len(prices)}")
    news = load_news(db, list(prices.keys()))
    n_news = 0 if news.empty else len(news)
    print(f"[sentiment] news rows (with sentiment) for universe: {n_news}")
    db.close()
    if n_news == 0:
        print("[sentiment] NO news/sentiment in DB for the universe — run the backfill first. Aborting.")
        return

    df = build_signals(prices, news, LOOKBACKS, HORIZONS)
    all_ts = sorted(df["T"].unique())
    split = all_ts[int(len(all_ts) * args.train_split)]
    val = df[df["T"] >= split]
    train = df[df["T"] < split]

    print(f"[sentiment] samples: {len(df)}  train={len(train)} val={len(val)} (split {split.date()})")
    print(f"\n{'='*74}\nNEWS SENTIMENT rank IC  (val / train, N=val-with-news)\n{'='*74}")
    print(f"{'lookback':<10}" + "".join(f"{f'h='+str(h):>20}" for h in HORIZONS))
    print("-" * 70)
    for lb in LOOKBACKS:
        cells = []
        for h in HORIZONS:
            ic_v, n_v = _rank_ic(val[f"sig_{lb}"], val[f"fwd_{h}"])
            ic_t, _ = _rank_ic(train[f"sig_{lb}"], train[f"fwd_{h}"])
            cells.append(f"{ic_v:+.3f}/{ic_t:+.3f}({n_v})")
        print(f"{'lb='+str(lb)+'d':<10}" + "".join(f"{c:>20}" for c in cells))

    lb, h = LOOKBACKS[0], HORIZONS[0]
    cov = df[f"sig_{lb}"].notna().mean()
    print(f"\ncoverage (samples with news in {lb}d window): {cov:.1%}")
    m = val[f"sig_{lb}"].notna() & val[f"fwd_{h}"].notna()
    if int(m.sum()) > 0:
        hit = (np.sign(val.loc[m, f"sig_{lb}"]) == np.sign(val.loc[m, f"fwd_{h}"])).mean()
        print(f"hit-rate (val, sign match, lb={lb} h={h}): {hit:.1%}  (>52% real; ~50% coin flip)")
    print(f"\n{'='*74}\nInterpretation: compare these ICs to the INDICATOR attribution\n"
          f"(~0.00 across the board). If news-sentiment val IC is persistently\n"
          f"> 0.03-0.05 across lookbacks/horizons, it's the first signal with real\n"
          f"standalone edge -> worth wiring into the engine. If also ~0, even\n"
          f"independent public sentiment won't break the ceiling.\n{'='*74}")


if __name__ == "__main__":
    main()
