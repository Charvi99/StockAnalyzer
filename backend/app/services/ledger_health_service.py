"""
Ledger health diagnostics (Phase 1.11 hardening).

Two read-only checks used by the ``check_ledger_health`` Celery task AND surfaced
by the API, so the task and ``GET /health`` can never drift apart:

  - ``compute_engine_health(db)`` — per-engine staleness. A missing/old equity
    snapshot means the daily beat (or the worker, or the cycle) stalled. This is
    the exact logic the ``/health`` route previously inlined; it now lives here so
    the task and the endpoint share one implementation.
  - ``reconcile_account(db, account_id)`` — three bookkeeping invariants that catch
    silent drift (a crash mid-cycle that debited cash without recording the trade,
    a mark-to-market bug, etc.) which would otherwise corrupt weeks of A/B data:
      1. snapshot.cash          ≈ account.cash
      2. snapshot.equity        ≈ account.cash + Σ(open mark value)
      3. snapshot.realized_cum  ≈ Σ(closed realized_pnl)

Both are DB-bound (live diagnostics), so they are exercised by source/structure
guards in ``backend/tests`` rather than pure unit tests. They never mutate state.

The stale threshold mirrors the beat cadence: the cycle is daily but skips
weekends/holidays, so a few calendar days of slack avoids false alarms on a long
weekend. The reconcile tolerance is a few cents — snapshots and account.cash are
DECIMAL(14,2) written by the same cycle, so any non-trivial delta is a real signal.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ledger import PaperAccount, PaperEquitySnapshot, PaperTrade
from app.utils.market_hours import get_current_et_time

logger = logging.getLogger(__name__)

STALE_THRESHOLD_DAYS = 3      # calendar-day slack (beat is daily, skips weekends/holidays)
RECONCILE_TOLERANCE = 0.05    # USD — snapshots are cent-precision, so this is generous


def _f(value):
    """DECIMAL → float for JSON; None passes through (mirrors the route helper)."""
    return float(value) if value is not None else None


def compute_engine_health(db: Session, now_et=None) -> List[dict]:
    """Per-engine health: staleness status + the headline numbers for an alert.

    Returns one dict per account with the SAME shape ``GET /health`` returns, so
    swapping that route to delegate here is a no-op for callers:

        {engine, status, last_snapshot_date, days_since_snapshot,
         open_trades, trades_opened_this_week, equity, cash}

    ``status`` is ``no_data`` (never snapshotted), ``stale`` (older than the
    threshold), or ``ok``.
    """
    now = now_et or get_current_et_time()
    now_date = now.date()
    week_ago = now - timedelta(days=7)

    accounts = db.query(PaperAccount).order_by(PaperAccount.engine).all()

    # Latest snapshot date per account (the heartbeat).
    last_snap = {
        r.account_id: r.last_date
        for r in db.query(
            PaperEquitySnapshot.account_id,
            func.max(PaperEquitySnapshot.date).label("last_date"),
        ).group_by(PaperEquitySnapshot.account_id).all()
    }
    # Open-position market value + count per account (mark_price, fall back to entry).
    open_agg = {
        r.account_id: r
        for r in db.query(
            PaperTrade.account_id,
            func.sum(
                func.coalesce(PaperTrade.mark_price, PaperTrade.entry_price)
                * PaperTrade.position_size
            ).label("open_value"),
            func.count(PaperTrade.id).label("open_count"),
        ).filter(PaperTrade.status == "open").group_by(PaperTrade.account_id).all()
    }
    # Trades opened this week, per engine (for the "is it still active?" signal).
    opened_this_week = {
        r.engine: r.c
        for r in db.query(
            PaperTrade.engine, func.count(PaperTrade.id).label("c")
        ).filter(PaperTrade.entry_date >= week_ago).group_by(PaperTrade.engine).all()
    }

    out: List[dict] = []
    for a in accounts:
        last = last_snap.get(a.id)
        o = open_agg.get(a.id)
        open_value = _f(o.open_value) if o else 0.0
        cash = _f(a.cash)

        if last is None:
            status = "no_data"
        elif (now_date - last).days > STALE_THRESHOLD_DAYS:
            status = "stale"
        else:
            status = "ok"

        out.append({
            "engine": a.engine,
            "status": status,
            "last_snapshot_date": last.isoformat() if last else None,
            "days_since_snapshot": (now_date - last).days if last else None,
            "open_trades": int(o.open_count) if o else 0,
            "trades_opened_this_week": int(opened_this_week.get(a.engine, 0)),
            "equity": cash + open_value,
            "cash": cash,
        })
    return out


def reconcile_account(db: Session, account_id: int) -> dict:
    """Verify the latest snapshot against a fresh recomputation from the live tables.

    Returns ``{has_account, has_snapshot, engine, snapshot_date?, deltas, ok}``.
    ``has_snapshot=False`` is not itself a fault (a just-seeded account has none;
    the staleness check covers that). ``ok=False`` means a bookkeeping invariant
    drifted beyond ``RECONCILE_TOLERANCE`` — alert-worthy.
    """
    acct = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
    if acct is None:
        return {"has_account": False, "has_snapshot": False}

    snap = (
        db.query(PaperEquitySnapshot)
        .filter(PaperEquitySnapshot.account_id == account_id)
        .order_by(PaperEquitySnapshot.date.desc())
        .first()
    )
    if snap is None:
        return {"has_account": True, "has_snapshot": False, "engine": acct.engine}

    # Recompute live: open market value + cumulative realized P&L.
    open_rows = (
        db.query(PaperTrade)
        .filter(PaperTrade.account_id == account_id, PaperTrade.status == "open")
        .all()
    )
    open_value = sum(
        float(t.mark_price or t.entry_price) * int(t.position_size) for t in open_rows
    )
    realized = (
        db.query(func.coalesce(func.sum(PaperTrade.realized_pnl), 0))
        .filter(PaperTrade.account_id == account_id, PaperTrade.status == "closed")
        .scalar()
        or 0
    )

    cash = float(acct.cash)
    deltas = {
        "cash": float(snap.cash) - cash,                       # snapshot cash vs live cash
        "equity": float(snap.equity) - (cash + open_value),    # snapshot equity vs recomputed
        "realized": float(snap.realized_pnl_cumulative) - float(realized),
    }
    ok = all(abs(v) <= RECONCILE_TOLERANCE for v in deltas.values())

    return {
        "has_account": True,
        "has_snapshot": True,
        "engine": acct.engine,
        "snapshot_date": snap.date.isoformat(),
        "deltas": deltas,
        "tolerance": RECONCILE_TOLERANCE,
        "ok": ok,
    }
