"""
Component attribution for the trading engines — answers "does each signal
component actually carry standalone out-of-sample edge, and which are redundant?"

WHY: the engines blend many weighted signal sources (technical / chart /
candlestick / regime / strategy consensus / ...). A blended signal's quality is
bounded by the INDEPENDENCE of its components' errors, not their count. Most of
these components are price-derived (correlated), so a "kitchen-sink" blend gives
the weight optimizer room to overfit without adding real edge. This script turns
that from opinion into measurement, using the same weight-independent component
votes the GA caches (``_components`` from ``compute_components``).

METHODOLOGY (audit it):
  - Per-component SCALAR SIGNAL:
      * engine_1: ``comp["scores"]`` (already [-1, 1], 6 components).
      * engine_2: direction(rec) * confidence for each voting component
        (BUY=+1, SELL=-1, HOLD/None=0), plus per-indicator technical_signals.
  - Predictive edge = Rank IC (Spearman) between the component signal and the
    FORWARD RETURN close[T+h]/close[T]-1, h in {5,10,21} trading days. Forward
    return is the LABEL to predict (not a feature), so using it is correct — no
    look-ahead in the analysis. Rank-based so heterogeneous component scales
    (conf 0.3 vs 0.6) are comparable.
  - IC is computed ONLY over samples where the component actually voted (signal
    != 0); N is reported, so non-voting components (sentiment/ml in the price-only
    backtest) are exposed as ~0 votes.
  - OUT-OF-SAMPLE: the chronological train/val split (default 0.7) matches the
    GA. We report IC on the VAL half (genuinely unseen) — train IC is shown only
    to expose the train/val gap (overfitting fingerprint).

CAVEATS (do not over-read the numbers):
  - Forward-return samples overlap (daily T, multi-day h) -> t-stats are
    inflated; treat IC as a point estimate, and watch val/train stability.
  - Raw returns include MARKET BETA: a component that just tracks the index
    shows spurious IC. (Future: subtract SPY excess return; for now, treat
    uniformly-positive, low-volatility IC as suspicious.)
  - This measures STANDALONE edge per component. A component with ~0 standalone
    IC can still add value in a blend only if its errors are independent of the
    others — check the correlation matrix.

MEMORY: streams per-stock (build one stock's rows, append, discard) so it is
RAM-bounded and safe on a full 100x2y universe. Parallelized across stocks with
the same multiprocessing pattern as precompute (tiny runs fall back to serial).

Run in the container (needs the DB + scipy):
  docker exec stock_analyzer_backend python /app/scripts/component_attribution.py
  docker exec stock_analyzer_backend python /app/scripts/component_attribution.py \
      --engine engine_2 --max-stocks 100 --start 2024-06-01 --end 2026-06-01
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.models.stock import Stock, StockPrice  # noqa: E402

HORIZONS_DEFAULT = [5, 10, 21]


# ── component signal extraction ──────────────────────────────────────────────
def _dir(rec) -> float:
    """Map a BUY/SELL/HOLD/None recommendation to a signed unit vote."""
    if rec == "BUY":
        return 1.0
    if rec == "SELL":
        return -1.0
    return 0.0  # HOLD / None / anything else


def extract_signals(engine: str, comp: Dict) -> Dict[str, float]:
    """A uniform ``{component_name: scalar_signal}`` dict for one (stock, T).

    engine_1: scores are already scalars in [-1, 1]. engine_2: each voting
    component becomes direction(rec) * confidence; per-indicator technical signals
    are added as ``tech_<NAME>`` for a finer drill-down.
    """
    out: Dict[str, float] = {}
    if not isinstance(comp, dict) or not comp:
        return out
    if engine == "engine_1":
        scores = comp.get("scores") or {}
        out.update({f"{k}": float(v) for k, v in scores.items() if isinstance(v, (int, float))})
        return out
    # engine_2
    out["technical"] = _dir(comp.get("technical_rec")) * float(comp.get("technical_conf") or 0.0)
    out["chart_pattern"] = _dir(comp.get("chart_pattern_signal")) * float(comp.get("chart_pattern_conf") or 0.0)
    out["candlestick"] = _dir(comp.get("candlestick_signal")) * float(comp.get("candlestick_conf") or 0.0)
    out["strategy"] = _dir(comp.get("strat_rec")) * float(comp.get("strat_conf") or 0.0)
    out["sentiment"] = _dir(comp.get("sentiment_rec")) * float(comp.get("sentiment_conf") or 0.0)
    out["ml"] = _dir(comp.get("ml_rec")) * float(comp.get("ml_conf") or 0.0)
    for ind, sig in (comp.get("technical_signals") or {}).items():
        out[f"tech_{ind}"] = _dir(sig)
    return out


# ── per-stock worker (pure; picklable; runs in a Pool process) ────────────────
def _attribution_one_stock(task) -> List[Tuple]:
    """Build the (stock, T) attribution rows for ONE stock. Streams: assembles
    inputs, extracts the component signals, computes forward returns, then
    discards the heavy bundle — so memory is one stock at a time."""
    engine, sid, df, dates, horizons = task
    from app.services.backtest.backtest_signal_adapter import assemble_inputs, compute_components

    rows: List[Tuple] = []
    closes = df.set_index("timestamp")["close"].sort_index()
    idx_of = {ts: i for i, ts in enumerate(closes.index)}
    for T in dates:
        T = pd.Timestamp(T)
        df_T = df[df["timestamp"] <= T]
        if len(df_T) < 2:
            continue
        try:
            bundle = assemble_inputs(engine, df_T)
        except Exception:  # noqa: BLE001 — insufficient history / assembly failure -> skip
            continue
        if bundle is None:
            continue
        try:
            comp = compute_components(engine, bundle)
        except Exception:  # noqa: BLE001
            continue
        sigs = extract_signals(engine, comp)
        if not sigs:
            continue
        # Forward returns over horizons (None if not enough future bars).
        loc = idx_of.get(T)
        fwd = {h: None for h in horizons}
        if loc is not None:
            for h in horizons:
                j = loc + h
                if 0 <= j < len(closes):
                    c0 = closes.iloc[loc]
                    ch = closes.iloc[j]
                    if c0 and pd.notna(c0) and pd.notna(ch):
                        fwd[h] = float(ch) / float(c0) - 1.0
        rows.append((sid, T, sigs, fwd))
    return rows


# ── orchestration ────────────────────────────────────────────────────────────
def _load_prices(max_stocks: int) -> Dict[int, pd.DataFrame]:
    db = SessionLocal()
    out: Dict[int, pd.DataFrame] = {}
    for s in db.query(Stock).order_by(Stock.id).limit(max_stocks).all():
        rows = (db.query(StockPrice)
                .filter(StockPrice.stock_id == s.id, StockPrice.timeframe == "1d")
                .order_by(StockPrice.timestamp.asc()).all())
        if len(rows) < 80:
            continue
        df = pd.DataFrame([{"timestamp": r.timestamp, "open": float(r.open), "high": float(r.high),
                            "low": float(r.low), "close": float(r.close), "volume": int(r.volume or 0)} for r in rows])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.normalize()
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        out[s.id] = df
    db.close()
    return out


def build_rows(engine: str, prices_by_stock: Dict[int, pd.DataFrame],
               trading_dates: List, horizons: List[int], workers: int) -> pd.DataFrame:
    stocks = list(prices_by_stock.items())
    tasks = [(engine, sid, df, trading_dates, horizons) for sid, df in stocks]
    all_rows: List[Tuple] = []

    if workers < 2 or len(tasks) < 2:
        for t in tasks:
            all_rows.extend(_attribution_one_stock(t))
    else:
        import multiprocessing

        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(processes=workers) as pool:
            for sub in pool.imap_unordered(_attribution_one_stock, tasks):
                all_rows.extend(sub)

    if not all_rows:
        return pd.DataFrame()
    records = []
    for sid, T, sigs, fwd in all_rows:
        rec = {"stock_id": sid, "T": T}
        rec.update(sigs)
        rec.update({f"fwd_{h}": fwd[h] for h in horizons})
        records.append(rec)
    return pd.DataFrame(records)


# ── metrics ──────────────────────────────────────────────────────────────────
def _rank_ic(signal: pd.Series, ret: pd.Series) -> Tuple[float, int]:
    """Spearman rank IC over samples where the component VOTED (signal != 0)."""
    mask = signal.notna() & ret.notna() & (signal != 0)
    n = int(mask.sum())
    if n < 30:
        return (np.nan, n)
    r, _ = spearmanr(signal[mask], ret[mask])
    return (float(r) if np.isfinite(r) else np.nan, n)


def _hit_rate(signal: pd.Series, ret: pd.Series) -> Tuple[float, int]:
    """Fraction of voted samples whose signal sign matches the return sign."""
    mask = signal.notna() & ret.notna() & (signal != 0)
    n = int(mask.sum())
    if n == 0:
        return (np.nan, 0)
    s = np.sign(signal[mask].to_numpy())
    rr = np.sign(ret[mask].to_numpy())
    return (float((s == rr).mean()), n)


def attribution_table(df: pd.DataFrame, horizons: List[int], components: List[str],
                      split_date) -> None:
    val = df[df["T"] >= split_date]
    train = df[df["T"] < split_date]
    print(f"\nsamples: total={len(df)}  train={len(train)}  val={len(val)}  "
          f"(split at {split_date.date()})")
    print(f"components: {components}\n")

    hdr = f"{'component':<22} " + " ".join(f"{'h='+str(h):>13}" for h in horizons)
    print(hdr)
    print("-" * len(hdr))
    for c in components:
        cells = []
        for h in horizons:
            ic_v, n_v = _rank_ic(val[c], val[f"fwd_{h}"]) if len(val) else (np.nan, 0)
            ic_t, _ = _rank_ic(train[c], train[f"fwd_{h}"]) if len(train) else (np.nan, 0)
            cells.append(f"{ic_v:+.3f}/{ic_t:+.3f}({n_v})")
        print(f"{c:<22} " + " ".join(f"{x:>13}" for x in cells))
    print("\n(each cell: val_rank_IC / train_rank_IC (N_voted_in_val))")

    print("\nhit-rate (sign(signal)==sign(forward return), voted samples, val):")
    for c in components:
        hr, n = _hit_rate(val[c], val[f"fwd_{horizons[0]}"]) if len(val) else (np.nan, 0)
        tag = f"{hr:.1%}" if np.isfinite(hr) else "  -  "
        print(f"  {c:<22} {tag}  (N={n})")


def correlation_matrix(df: pd.DataFrame, components: List[str]) -> None:
    sub = df[components].copy()
    # correlation over ALL samples (incl. zeros) — reflects co-movement of the
    # components' expressed views; high off-diagonal = redundant.
    corr = sub.corr(method="spearman")

    # (1) Core voting-component matrix (readable headline; drops the tech_* drill-down).
    core = [c for c in components if not c.startswith("tech_")]
    print("\nCORE component Spearman correlation (the GA's voting components):")
    with pd.option_context("display.width", 120, "display.max_columns", 30):
        print(corr.loc[core, core].round(2).to_string())

    # (2) Most redundant pairs across ALL components (incl. per-indicator drill-down),
    # sorted by |r| — the actionable "drop one of each" list.
    pairs = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
    red = [(idx, float(v)) for idx, v in pairs.items() if np.isfinite(v) and abs(v) > 0.6]
    red.sort(key=lambda kv: -abs(kv[1]))
    print("\nmost redundant pairs (|r|>0.6) — candidates to DROP one of each:")
    if not red:
        print("  (none above 0.6)")
    else:
        for (a, b), v in red[:20]:
            print(f"  {v:+.2f}  {a}  <->  {b}")


def main():
    ap = argparse.ArgumentParser(description="Component attribution (standalone edge + redundancy)")
    ap.add_argument("--engine", default="engine_2", choices=["engine_1", "engine_2"])
    ap.add_argument("--max-stocks", type=int, default=3, help="universe size (keep small for a quick check)")
    ap.add_argument("--start", default="2024-06-01")
    ap.add_argument("--end", default="2025-06-01")
    ap.add_argument("--horizons", default="5,10,21", help="forward-return horizons in trading days")
    ap.add_argument("--train-split", type=float, default=0.7)
    ap.add_argument("--workers", type=int, default=0, help="0 => min(cpu_count-1, 6)")
    args = ap.parse_args()

    horizons = [int(x) for x in args.horizons.split(",") if x.strip()]
    workers = args.workers or max(1, min((os.cpu_count() or 2) - 1, 6))

    print(f"[attribution] engine={args.engine} universe<={args.max_stocks} "
          f"window={args.start}..{args.end} horizons={horizons} workers={workers}")
    prices = _load_prices(args.max_stocks)
    if not prices:
        print("no stocks with sufficient history — aborting")
        return
    # trading dates = union of all stocks' timestamps inside the window
    s = pd.Timestamp(args.start, tz="UTC")
    e = pd.Timestamp(args.end, tz="UTC")
    all_ts = sorted(set().union(*[set(d.loc[(d["timestamp"] >= s) & (d["timestamp"] <= e), "timestamp"]) for d in prices.values()]))
    if not all_ts:
        print("no trading dates in window — aborting")
        return
    split_date = all_ts[int(len(all_ts) * args.train_split)]

    df = build_rows(args.engine, prices, all_ts, horizons, workers)
    if df.empty:
        print("no attribution rows built — check universe/window/engine")
        return
    components = [c for c in df.columns if c not in ("stock_id", "T") and not c.startswith("fwd_")]
    components = sorted(components)

    print(f"\n{'='*70}\nCOMPONENT ATTRIBUTION — {args.engine}  ({len(prices)} stocks, "
          f"{len(all_ts)} dates)\n{'='*70}")
    attribution_table(df, horizons, components, split_date)
    correlation_matrix(df, components)
    print(f"\n{'='*70}\nInterpretation: keep components with val_IC persistently away from 0\n"
          f"across horizons AND low mutual correlation. Treat near-zero val_IC (or\n"
          f"high train/low val IC) as no standalone edge. N shows how often each\n"
          f"actually voted.\n{'='*70}")


if __name__ == "__main__":
    main()
