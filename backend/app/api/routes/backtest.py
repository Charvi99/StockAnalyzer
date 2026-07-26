"""
Backtest API routes (Phase 2).

  POST   /api/v1/backtests         create a backtest run (status=pending) + enqueue it
  GET    /api/v1/backtests         list runs (optional ?engine=)
  GET    /api/v1/backtests/{id}    a run + its equity curve + metrics + fitness

Runs execute asynchronously on the maintenance Celery worker (a backtest can
take minutes), so POST returns immediately with ``status=pending``; poll GET
until ``status`` is ``completed`` (or ``failed``).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.backtest import BacktestRun, BacktestEquityPoint

router = APIRouter()


class BacktestRequest(BaseModel):
    engine: str
    start_date: str            # YYYY-MM-DD
    end_date: str              # YYYY-MM-DD
    max_stocks: Optional[int] = 30   # scope the universe (perf; full 5y×200-stock runs exceed the worker time limit)
    starting_cash: float = 100_000.0
    dd_penalty: float = 0.5
    trade_count_floor: int = 5
    # Phase 2.5: regime de-risk overlay strength in [0,1]. 0.0 (default) => OFF,
    # byte-identical to every prior run. >0 => proportional bear-market suppression
    # (engine_1: buy-score scale; engine_2: position-size scale).
    regime_overlay_strength: float = 0.0


def _run_dict(r: BacktestRun) -> dict:
    return {
        "id": r.id,
        "engine": r.engine,
        "status": r.status,
        "config_version": r.config_version,
        "fitness": float(r.fitness) if r.fitness is not None else None,
        "metrics": r.metrics,
        "config": r.config,
        "error": r.error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }


def _point_dict(p: BacktestEquityPoint) -> dict:
    return {
        "date": p.date.isoformat() if p.date else None,
        "cash": float(p.cash),
        "open_positions_value": float(p.open_positions_value),
        "equity": float(p.equity),
        "realized_pnl_cumulative": float(p.realized_pnl_cumulative),
        "open_trades_count": p.open_trades_count,
    }


@router.post("")
def create_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    if req.engine not in ("engine_1", "engine_2"):
        raise HTTPException(status_code=400, detail="engine must be 'engine_1' or 'engine_2'")
    # Validate dates: ISO YYYY-MM-DD and start < end (else a silent empty run).
    from datetime import datetime
    try:
        s = datetime.fromisoformat(req.start_date)
        e = datetime.fromisoformat(req.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="start_date/end_date must be YYYY-MM-DD")
    if s >= e:
        raise HTTPException(status_code=400, detail="start_date must precede end_date")
    if not 0.0 <= req.regime_overlay_strength <= 1.0:
        raise HTTPException(status_code=400, detail="regime_overlay_strength must be in [0, 1]")
    from app.tasks.backtest_tasks import run_backtest_task

    run = BacktestRun(
        engine=req.engine,
        status="pending",
        config={
            "start_date": req.start_date,
            "end_date": req.end_date,
            "max_stocks": req.max_stocks,
            "starting_cash": req.starting_cash,
            "dd_penalty": req.dd_penalty,
            "trade_count_floor": req.trade_count_floor,
            "regime_overlay_strength": req.regime_overlay_strength,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    run_backtest_task.delay(run.id)
    return _run_dict(run)


@router.get("")
def list_backtests(
    engine: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(BacktestRun)
    if engine:
        q = q.filter(BacktestRun.engine == engine)
    rows = q.order_by(BacktestRun.created_at.desc()).limit(limit).all()
    return {"runs": [_run_dict(r) for r in rows]}


@router.get("/{run_id}")
def get_backtest(run_id: int, db: Session = Depends(get_db)):
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="backtest run not found")
    points = (
        db.query(BacktestEquityPoint)
        .filter(BacktestEquityPoint.run_id == run_id)
        .order_by(BacktestEquityPoint.date.asc())
        .all()
    )
    return {**_run_dict(run), "equity_curve": [_point_dict(p) for p in points]}
