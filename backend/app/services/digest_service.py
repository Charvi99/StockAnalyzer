"""
Daily status digest for the paper-trading ledger (Phase 1.11b).

Composes the "I don't need to open the frontend" daily email: a scannable
plain-text report of system health, both engines' A/B standing, a high-conviction
BUY watchlist, the S&P benchmark, today's top open movers, and portfolio heat/cash.

Sent twice daily (morning pre-market + evening after close) by the
``send_daily_digest`` Celery task via ``alert_service.notify_alert`` (→ Gmail when
SMTP is configured). The digest ALWAYS sends — it doubles as the system-up
heartbeat: if it ever fails to arrive, the beat/worker is down. An in-stack task
cannot detect its own scheduler dying, so "no digest today" IS the down-signal.

Subject convention (so Gmail can filter on the ``[StockAnalyzer]`` prefix):
  - routine : ``[StockAnalyzer] Digest — 2026-07-22 PM``
  - problem : ``[StockAnalyzer] Alert — <one-line reason>``

Morning (AM) shows yesterday's-close state (no cycle has run yet); evening (PM)
shows today's full results. The SAME builder runs both — content is computed fresh
each time, so it is always correct for the moment it sends.

All sections are read-only queries; this service never mutates state.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ledger import (
    PaperAccount, PaperEquitySnapshot, PaperSignalLog, PaperTrade,
)
from app.models.stock import Stock, StockPrice
from app.services.benchmark_service import get_spy_series
from app.services.ledger_health_service import compute_engine_health, reconcile_account
from app.services.ledger_service import LEDGER_MAX_PORTFOLIO_HEAT
from app.utils.market_hours import get_current_et_time

logger = logging.getLogger(__name__)

# ── v1 knobs ──────────────────────────────────────────────────────────────────
DIGEST_BUY_CONFIDENCE = 0.70   # watchlist: BUY signals at/above this confidence
DATA_STALE_HOURS = 26          # price data older than this ⇒ 🔴 on ingestion
TOP_MOVERS_N = 3               # winners + losers shown


def _f(value):
    return float(value) if value is not None else None


def _open_value(db: Session, account_id: int) -> float:
    """Σ (mark_price ∨ entry_price) × size over open trades (mark falls back to entry)."""
    rows = (
        db.query(PaperTrade.mark_price, PaperTrade.entry_price, PaperTrade.position_size)
        .filter(PaperTrade.account_id == account_id, PaperTrade.status == "open")
        .all()
    )
    return sum(float(r.mark_price or r.entry_price) * int(r.position_size) for r in rows)


# ── section builders ──────────────────────────────────────────────────────────
def _system_status(db: Session, now, health, recon) -> List[dict]:
    """Green/red checklist of pipeline stages, read from DB freshness (the task
    can't see Docker, but it can see when data last landed)."""
    since = now - timedelta(hours=24)
    last_price = (
        db.query(func.max(StockPrice.timestamp))
        .filter(StockPrice.timeframe == "1d").scalar()
    )
    n_prices = (
        db.query(func.count(StockPrice.stock_id.distinct()))
        .filter(StockPrice.timeframe == "1d", StockPrice.timestamp > since)
        .scalar() or 0
    )
    price_age_h = (now - last_price).total_seconds() / 3600 if last_price else None
    price_ok = price_age_h is not None and price_age_h <= DATA_STALE_HOURS

    latest_cycle = db.query(func.max(PaperSignalLog.cycle_id)).scalar()
    snap_today = (
        db.query(func.count(PaperEquitySnapshot.id))
        .filter(PaperEquitySnapshot.date == now.date()).scalar() or 0
    ) > 0
    all_recon_ok = all(r.get("ok") for r in recon.values())

    return [
        {"label": "Price ingestion", "ok": price_ok,
         "detail": (f"last {last_price:%Y-%m-%d %H:%M} ET, {n_prices} stocks in 24h"
                    if last_price else "no price data yet")},
        {"label": "Signal analysis", "ok": bool(latest_cycle),
         "detail": (f"last cycle {latest_cycle}" if latest_cycle else "no signals logged yet")},
        {"label": "Ledger snapshot today", "ok": snap_today,
         "detail": "yes" if snap_today else "not yet (cycle runs 19:00 ET)"},
        {"label": "Worker", "ok": True,
         "detail": "this digest was sent ⇒ up"},
        {"label": "Books reconcile", "ok": all_recon_ok,
         "detail": "ok" if all_recon_ok else "drift detected (see warnings)"},
    ]


def _engine_row(db: Session, account: PaperAccount) -> dict:
    """One engine's headline numbers. Equity is taken from the latest snapshot
    (authoritative mark-to-market) when available, else computed live."""
    snaps = (
        db.query(PaperEquitySnapshot)
        .filter(PaperEquitySnapshot.account_id == account.id)
        .order_by(PaperEquitySnapshot.date.desc()).limit(2).all()
    )
    starting = float(account.starting_cash)
    live_equity = float(account.cash) + _open_value(db, account.id)
    if snaps:
        equity = float(snaps[0].equity)
        prev = float(snaps[1].equity) if len(snaps) > 1 else starting
        day_delta = equity - prev
    else:
        equity = live_equity
        day_delta = live_equity - starting

    closed = (
        db.query(PaperTrade)
        .filter(PaperTrade.account_id == account.id, PaperTrade.status == "closed")
        .all()
    )
    wins = [t for t in closed if (t.realized_pnl or 0) > 0]
    open_n = (
        db.query(PaperTrade)
        .filter(PaperTrade.account_id == account.id, PaperTrade.status == "open")
        .count()
    )
    return {
        "engine": account.engine,
        "equity": equity,
        "starting": starting,
        "cash": float(account.cash),
        "total_return_pct": (equity - starting) / starting if starting else 0.0,
        "day_delta_pct": (day_delta / starting) if starting else 0.0,
        "open": int(open_n),
        "closed": len(closed),
        "win_rate": (len(wins) / len(closed)) if closed else None,
        "config_version": account.config_version,
    }


def _high_conviction_buys(db: Session) -> List[dict]:
    """Latest cycle's BUY signals at/above the watchlist threshold, highest first."""
    latest = db.query(func.max(PaperSignalLog.cycle_id)).scalar()
    if latest is None:
        return []
    rows = (
        db.query(PaperSignalLog, Stock.symbol)
        .join(Stock, PaperSignalLog.stock_id == Stock.id)
        .filter(PaperSignalLog.cycle_id == latest,
                PaperSignalLog.signal == "BUY",
                PaperSignalLog.confidence >= DIGEST_BUY_CONFIDENCE)
        .order_by(PaperSignalLog.confidence.desc()).all()
    )
    return [{"engine": log.engine, "symbol": sym, "confidence": float(log.confidence)}
            for log, sym in rows]


def _top_movers(db: Session) -> dict:
    """Top-N open-position winners + losers by unrealized % (mark vs entry, per
    share — size-independent so it ranks the actual price moves)."""
    rows = (
        db.query(PaperTrade, Stock.symbol)
        .join(Stock, PaperTrade.stock_id == Stock.id)
        .filter(PaperTrade.status == "open").all()
    )
    items = []
    for t, sym in rows:
        entry = float(t.entry_price) if t.entry_price else None
        mark = float(t.mark_price or t.entry_price)
        pct = (mark / entry - 1.0) if entry else 0.0
        items.append({"engine": t.engine, "symbol": sym, "pct": pct})
    winners = sorted(items, key=lambda x: x["pct"], reverse=True)[:TOP_MOVERS_N]
    losers = sorted(items, key=lambda x: x["pct"])[:TOP_MOVERS_N]
    return {"winners": winners, "losers": losers}


def _portfolio_heat_cash(db: Session, accounts) -> dict:
    """Combined open risk vs the heat cap + cash runway (both engines pooled)."""
    open_trades = db.query(PaperTrade).filter(PaperTrade.status == "open").all()
    total_risk = sum(float(t.risk_amount or 0) for t in open_trades)
    total_open_value = sum(
        float(t.mark_price or t.entry_price) * int(t.position_size) for t in open_trades
    )
    total_cash = sum(float(a.cash) for a in accounts)
    total_starting = sum(float(a.starting_cash) for a in accounts)
    heat_pct = (total_risk / total_starting * 100.0) if total_starting else 0.0
    return {
        "open_positions": len(open_trades),
        "open_value": total_open_value,
        "cash": total_cash,
        "heat_pct": heat_pct,
        "heat_cap_pct": float(LEDGER_MAX_PORTFOLIO_HEAT),
        "heat_util": (heat_pct / float(LEDGER_MAX_PORTFOLIO_HEAT)) if LEDGER_MAX_PORTFOLIO_HEAT else 0.0,
    }


def _vs_spy(db: Session, accounts, now) -> dict:
    """Each engine's total return vs SPY over the same calendar run."""
    first = db.query(func.min(PaperEquitySnapshot.date)).scalar()
    run_days = ((now.date() - first).days + 1) if first else 0
    spy_series = get_spy_series(max(run_days, 1) + 3) if run_days else get_spy_series(30)
    spy_return = spy_series[-1]["return_pct"] if spy_series else None
    engines = []
    for a in accounts:
        eq = float(a.cash) + _open_value(db, a.id)
        starting = float(a.starting_cash)
        engines.append({"engine": a.engine,
                        "return_pct": (eq - starting) / starting if starting else 0.0})
    return {"run_days": run_days, "spy_return_pct": spy_return, "engines": engines}


def _warnings(health, recon, system) -> List[str]:
    """Human-readable issue lines (staleness, reconciliation drift, stale data)."""
    w = []
    for h in health:
        if h["status"] in ("stale", "no_data"):
            w.append(f"{h['engine']} {h['status']} — last snapshot "
                     f"{h['last_snapshot_date']} ({h['days_since_snapshot']}d ago)")
    for eng, r in recon.items():
        if r.get("has_snapshot") and not r.get("ok"):
            d = r["deltas"]
            w.append(f"{eng} books don't reconcile — cash Δ${d['cash']:.2f}, "
                     f"equity Δ${d['equity']:.2f}, realized Δ${d['realized']:.2f}")
    for s in system:
        if not s["ok"] and s["label"] != "Worker":  # Worker is always up (this ran)
            w.append(f"{s['label']} not fresh — {s['detail']}")
    return w


# ── compose ───────────────────────────────────────────────────────────────────
def build_digest(db: Session, window: str = "PM") -> dict:
    """Compose the structured digest. ``window`` ∈ {'AM','PM'} labels the briefing."""
    now = get_current_et_time()
    health = compute_engine_health(db, now)
    accounts = db.query(PaperAccount).order_by(PaperAccount.engine).all()
    recon = {a.engine: reconcile_account(db, a.id) for a in accounts}

    system = _system_status(db, now, health, recon)
    warnings = _warnings(health, recon, system)
    return {
        "window": window,
        "date": now.date().isoformat(),
        "has_issues": bool(warnings),
        "system": system,
        "engines": [_engine_row(db, a) for a in accounts],
        "watchlist": _high_conviction_buys(db),
        "movers": _top_movers(db),
        "heat": _portfolio_heat_cash(db, accounts),
        "spy": _vs_spy(db, accounts, now),
        "warnings": warnings,
    }


def _pct(x) -> str:
    return f"{x * 100:+.2f}%" if x is not None else "n/a"


def _money(x) -> str:
    return f"${x:,.0f}" if x is not None else "n/a"


def render_digest_text(d: dict) -> str:
    """Scannable plain-text email body (the whole point: read in 30s)."""
    L: List[str] = []
    win_label = "Morning briefing (pre-market)" if d["window"] == "AM" else "Evening digest (after close)"
    L.append(f"📈 StockAnalyzer — {win_label} — {d['date']}")
    L.append("=" * 56)

    if d["warnings"]:
        L.append("")
        L.append("⚠️  ISSUES")
        for w in d["warnings"]:
            L.append(f"  • {w}")

    L.append("")
    L.append("SYSTEM STATUS")
    for s in d["system"]:
        L.append(f"  {'🟢' if s['ok'] else '🔴'} {s['label']}: {s['detail']}")

    L.append("")
    L.append("PAPER-TRADING ENGINES (A/B)")
    for e in d["engines"]:
        wr = f"{e['win_rate'] * 100:.0f}%" if e["win_rate"] is not None else "—"
        L.append(
            f"  {e['engine']}: equity {_money(e['equity'])} ({_pct(e['total_return_pct'])} total, "
            f"{_pct(e['day_delta_pct'])} today) | {e['open']} open / {e['closed']} closed | "
            f"win {wr} | cash {_money(e['cash'])} | cv {e['config_version']}"
        )

    L.append("")
    L.append(f"HIGH-CONVICTION BUY (≥{int(DIGEST_BUY_CONFIDENCE * 100)}% confidence)")
    if d["watchlist"]:
        for w in d["watchlist"]:
            L.append(f"  {w['symbol']:6} [{w['engine']}] {w['confidence'] * 100:.0f}%")
    else:
        L.append("  (none this cycle)")

    spy = d["spy"]
    L.append("")
    L.append(f"vs S&P 500 (over {spy['run_days']}d run)")
    L.append(f"  SPY : {_pct(spy['spy_return_pct'])}")
    for e in spy["engines"]:
        L.append(f"  {e['engine']}: {_pct(e['return_pct'])}")

    L.append("")
    L.append("TOP OPEN MOVERS")
    mv = d["movers"]
    if mv["winners"]:
        L.append("  winners:")
        for m in mv["winners"]:
            L.append(f"    {m['symbol']:6} [{m['engine']}] {_pct(m['pct'])}")
        L.append("  losers:")
        for m in mv["losers"]:
            L.append(f"    {m['symbol']:6} [{m['engine']}] {_pct(m['pct'])}")
    else:
        L.append("  (no open positions)")

    h = d["heat"]
    L.append("")
    L.append("PORTFOLIO HEAT & CASH")
    L.append(f"  {h['open_positions']} open | open value {_money(h['open_value'])} | "
             f"cash {_money(h['cash'])}")
    L.append(f"  heat {h['heat_pct']:.1f}% / cap {h['heat_cap_pct']:.0f}% "
             f"({h['heat_util'] * 100:.0f}% utilized)")

    L.append("")
    L.append("— heartbeat: if this stops arriving, the scheduler/worker is down —")
    return "\n".join(L)


def compose_daily_digest(db: Session, window: str = "PM") -> dict:
    """Build + render the digest, returning the notify_alert payload.

    Subject is ``[StockAnalyzer] Alert — …`` when there are issues (so it stands
    out / you can filter 'alert'), else ``[StockAnalyzer] Digest — <date> <window>``.
    """
    d = build_digest(db, window)
    body = render_digest_text(d)
    if d["has_issues"]:
        subject = f"[StockAnalyzer] Alert — {d['warnings'][0][:60]}"
        severity = "error"
    else:
        subject = f"[StockAnalyzer] Digest — {d['date']} {window}"
        severity = "info"
    return {"subject": subject, "body": body, "severity": severity, "has_issues": d["has_issues"]}
