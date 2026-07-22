"""
Paper-trading ledger API (Phase 1, step 6).

Read-only surface over the ledger tables — the dashboard for measuring
recommendation quality and A/B-scoring the two engines (D35):

  - ``GET /accounts``   per-engine cash / equity / realized / unrealized / open count
  - ``GET /trades``     paginated trade list (filter by engine/status/stock)
  - ``GET /equity``     per-engine equity-curve snapshots
  - ``GET /summary``    the scorecard: win rate, avg R:R, avg hold, P&L, counts
  - ``GET /health``     the heartbeat — last snapshot per engine + trades opened
                         this week; a stale/missing snapshot means the beat stalled

All endpoints are GET and compute from the live tables, so they return a correct
empty-state (seeded account, no trades/snapshots) even before the first cycle has
run. Mounted under ``/api/v1/paper-trading`` (registered in ``main.py``).

DB-bound read handlers are sync ``def`` (run in the threadpool, don't block the
event loop — the Phase 0.6 H7 lesson). All DECIMAL columns are cast to float for
JSON serialization.
"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.ledger import PaperAccount, PaperEquitySnapshot, PaperTrade
from app.models.stock import Stock
from app.utils.market_hours import get_current_et_time

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────
def _f(value):
    """DECIMAL → float for JSON; None passes through."""
    return float(value) if value is not None else None


def _avg(xs):
    """Mean of a list, or None when empty (so the JSON omits a misleading 0)."""
    return sum(xs) / len(xs) if xs else None


def _account_ids(db: Session, engine: Optional[str]) -> dict:
    """{engine: account_id}, optionally filtered to one engine."""
    q = db.query(PaperAccount)
    if engine:
        q = q.filter(PaperAccount.engine == engine)
    return {a.engine: a.id for a in q.all()}


def _account_summary_rows(db: Session):
    """One dict per account: live cash/equity/unrealized/realized/open + last
    snapshot date. Computed from the tables so it's correct with zero snapshots."""
    accounts = db.query(PaperAccount).order_by(PaperAccount.engine).all()

    # Open-position market value + unrealized, grouped by account. mark_price is set
    # each cycle; fall back to entry_price before the first mark-to-market.
    open_agg = {
        r.account_id: r
        for r in db.query(
            PaperTrade.account_id.label("aid"),
            func.sum(
                func.coalesce(PaperTrade.mark_price, PaperTrade.entry_price)
                * PaperTrade.position_size
            ).label("open_value"),
            func.sum(func.coalesce(PaperTrade.unrealized_pnl, 0)).label("unrealized"),
            func.count(PaperTrade.id).label("open_count"),
        )
        .filter(PaperTrade.status == "open")
        .group_by(PaperTrade.account_id)
        .all()
    }

    # Cumulative realized P&L per account (closed trades).
    realized_agg = {
        r.account_id: r
        for r in db.query(
            PaperTrade.account_id.label("aid"),
            func.sum(func.coalesce(PaperTrade.realized_pnl, 0)).label("realized"),
            func.count(PaperTrade.id).label("closed_count"),
        )
        .filter(PaperTrade.status == "closed")
        .group_by(PaperTrade.account_id)
        .all()
    }

    # Latest snapshot date per account (the heartbeat timestamp).
    last_snap = {
        r.account_id: r.last_date
        for r in db.query(
            PaperEquitySnapshot.account_id.label("aid"),
            func.max(PaperEquitySnapshot.date).label("last_date"),
        )
        .group_by(PaperEquitySnapshot.account_id)
        .all()
    }

    rows = []
    for a in accounts:
        o = open_agg.get(a.id)
        rz = realized_agg.get(a.id)
        open_value = _f(o.open_value) if o else 0.0
        cash = _f(a.cash)
        rows.append(
            {
                "engine": a.engine,
                "starting_cash": _f(a.starting_cash),
                "cash": cash,
                "config_version": a.config_version,
                "open_positions_value": open_value,
                "unrealized_pnl": _f(o.unrealized) if o else 0.0,
                "open_trades": int(o.open_count) if o else 0,
                "realized_pnl": _f(rz.realized) if rz else 0.0,
                "closed_trades": int(rz.closed_count) if rz else 0,
                "equity": cash + open_value,
                "last_snapshot_date": last_snap.get(a.id),
            }
        )
    return rows


def _trade_dict(t: PaperTrade, symbol: Optional[str]) -> dict:
    return {
        "id": t.id,
        "engine": t.engine,
        "symbol": symbol,
        "signal_at_entry": t.signal_at_entry,
        "config_version": t.config_version,
        "entry_confidence": _f(t.entry_confidence),
        "entry_price": _f(t.entry_price),
        "entry_date": t.entry_date.isoformat() if t.entry_date else None,
        "stop_loss": _f(t.stop_loss),
        "take_profit": _f(t.take_profit),
        "position_size": t.position_size,
        "position_value": _f(t.position_value),
        "risk_amount": _f(t.risk_amount),
        "status": t.status,
        "exit_price": _f(t.exit_price),
        "exit_date": t.exit_date.isoformat() if t.exit_date else None,
        "exit_reason": t.exit_reason,
        "exit_signal": t.exit_signal,
        "exit_config_version": t.exit_config_version,
        "realized_pnl": _f(t.realized_pnl),
        "realized_pnl_pct": _f(t.realized_pnl_pct),
        "mark_price": _f(t.mark_price),
        "unrealized_pnl": _f(t.unrealized_pnl),
    }


def _engine_stats(db: Session, account_id: int) -> dict:
    """The A/B scorecard for one engine's account."""
    closed = (
        db.query(PaperTrade)
        .filter(PaperTrade.account_id == account_id, PaperTrade.status == "closed")
        .all()
    )
    wins = [t for t in closed if (t.realized_pnl or 0) > 0]

    # Planned R:R at entry (long): reward (TP-entry) / risk (entry-SL).
    rr_planned = [
        float((t.take_profit - t.entry_price) / (t.entry_price - t.stop_loss))
        for t in closed
        if (t.entry_price - t.stop_loss) not in (None, 0)
    ]
    # Realized R: realized_pnl / risk_amount (the multiple of R actually captured).
    realized_r = [
        float((t.realized_pnl or 0) / t.risk_amount)
        for t in closed
        if (t.risk_amount or 0) > 0
    ]
    # Holding period in days.
    holds = [
        (t.exit_date - t.entry_date).days
        for t in closed
        if t.entry_date and t.exit_date and (t.exit_date - t.entry_date).days >= 0
    ]

    open_count = (
        db.query(PaperTrade)
        .filter(PaperTrade.account_id == account_id, PaperTrade.status == "open")
        .count()
    )

    return {
        "closed_trades": len(closed),
        "open_trades": open_count,
        "win_rate": (len(wins) / len(closed)) if closed else None,
        "avg_rr_planned": _avg(rr_planned),
        "avg_realized_r": _avg(realized_r),
        "avg_hold_days": _avg(holds),
        "total_realized_pnl": sum(float(t.realized_pnl or 0) for t in closed),
    }


def _stale_threshold_days() -> int:
    """Calendar-day slack before a missing snapshot is flagged 'stale'. The beat
    is daily but skips weekends/holidays, so allow a long-weekend buffer (3)."""
    return 3


# ── endpoints ─────────────────────────────────────────────────────────────────
@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    """Per-engine account state: cash, equity, realized/unrealized, open count."""
    return {"accounts": _account_summary_rows(db)}


@router.get("/trades")
def list_trades(
    engine: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    stock_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated trade list (most-recent first), filterable by engine/status/stock."""
    q = db.query(PaperTrade, Stock.symbol).join(Stock, PaperTrade.stock_id == Stock.id)
    if engine:
        q = q.filter(PaperTrade.engine == engine)
    if status:
        q = q.filter(PaperTrade.status == status)
    if stock_id:
        q = q.filter(PaperTrade.stock_id == stock_id)

    total = q.count()
    rows = q.order_by(PaperTrade.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "trades": [_trade_dict(t, sym) for (t, sym) in rows],
    }


@router.get("/equity")
def equity_curve(
    engine: Optional[str] = Query(None),
    days: int = Query(90, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Per-engine equity curve (snapshot series) over the last `days` days."""
    now_et = get_current_et_time()
    since = (now_et - timedelta(days=days)).date()
    acct_ids = _account_ids(db, engine)
    if not acct_ids:
        return {"days": days, "series": {}}

    id_to_engine = {aid: eng for eng, aid in acct_ids.items()}
    snaps = (
        db.query(PaperEquitySnapshot)
        .filter(
            PaperEquitySnapshot.account_id.in_(list(acct_ids.values())),
            PaperEquitySnapshot.date >= since,
        )
        .order_by(PaperEquitySnapshot.account_id, PaperEquitySnapshot.date)
        .all()
    )

    series: dict = {}
    for s in snaps:
        eng = id_to_engine.get(s.account_id)
        series.setdefault(eng, []).append(
            {
                "date": s.date.isoformat(),
                "cash": _f(s.cash),
                "open_positions_value": _f(s.open_positions_value),
                "equity": _f(s.equity),
                "realized_pnl_cumulative": _f(s.realized_pnl_cumulative),
                "open_trades_count": s.open_trades_count,
            }
        )
    return {"days": days, "series": series}


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """The scorecard per engine: win rate, avg planned + realized R, avg hold,
    P&L, counts. The comparison is client-side across the per-engine dict (D35)."""
    return {"engines": {eng: _engine_stats(db, aid) for eng, aid in _account_ids(db, None).items()}}


def _engine_config(engine: str) -> Optional[dict]:
    """Read-only snapshot of an engine's live signal config (weights + thresholds
    + active tools), locked to its ``config_version``. This is the signal
    *definition* (module constants), not account state — returned for both engines
    regardless of seeding. None for an unknown engine."""
    if engine == "engine_1":
        from app.services.signal import systematic as eng
        return {
            "schema": eng.SCHEMA,
            "config_version": eng._SYSTEMATIC_CONFIG_VERSION,
            "weights": dict(eng.WEIGHTS),
            "thresholds": {"buy_sell_threshold": eng.BUY_SELL_THRESHOLD},
            "regime_scores": dict(eng.REGIME_SCORES),
            "active_components": list(eng.WEIGHTS.keys()),
        }
    if engine == "engine_2":
        from app.services.signal import swing as eng
        return {
            "schema": eng.SCHEMA,
            "config_version": eng._SWING_CONFIG_VERSION,
            "weights": dict(eng.COMPONENT_WEIGHTS),
            "thresholds": {
                "ml_confidence_gate": eng.ML_CONFIDENCE_GATE,
                "all_agree_boost": eng.ALL_AGREE_BOOST,
                "weekly_bullish_boost": eng.WEEKLY_BULLISH_BOOST,
                "bearish_override_conf_cut": eng.BEARISH_OVERRIDE_CONF_CUT,
                "final_conf_floor": eng.FINAL_CONF_FLOOR,
            },
            "active_components": list(eng.COMPONENT_WEIGHTS.keys()),
        }
    return None


@router.get("/config")
def engine_config(db: Session = Depends(get_db)):
    """Read-only live config per engine: weights, thresholds, active tools,
    schema, and config_version. Read-only (editing is deferred to Phase 3)."""
    configs = {eng: _engine_config(eng) for eng in ("engine_1", "engine_2")}
    return {"engines": {k: v for k, v in configs.items() if v is not None}}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """The heartbeat. A stale/missing last snapshot ⇒ the daily beat stalled."""
    now_et = get_current_et_time().date()
    week_ago = get_current_et_time() - timedelta(days=7)

    out = []
    for r in _account_summary_rows(db):
        eng = r["engine"]
        last = r["last_snapshot_date"]
        opened_this_week = (
            db.query(PaperTrade)
            .filter(PaperTrade.engine == eng, PaperTrade.entry_date >= week_ago)
            .count()
        )
        if last is None:
            status = "no_data"
        elif (now_et - last).days > _stale_threshold_days():
            status = "stale"
        else:
            status = "ok"
        out.append(
            {
                "engine": eng,
                "status": status,
                "last_snapshot_date": last.isoformat() if last else None,
                "days_since_snapshot": (now_et - last).days if last else None,
                "open_trades": r["open_trades"],
                "trades_opened_this_week": opened_this_week,
                "equity": r["equity"],
                "cash": r["cash"],
            }
        )
    return {"checked_at_et": now_et.isoformat(), "engines": out}
