"""
GA API routes (Phase 3).

  POST   /api/v1/ga-runs        create a GA run (status=pending) + enqueue it
  GET    /api/v1/ga-runs        list GA runs (optional ?engine=)
  GET    /api/v1/ga-runs/{id}   a run + best weights + train/val fitness + the
                                 per-generation fitness summary + the best
                                 individual's TRAIN-window equity curve

A GA runs asynchronously on the maintenance Celery worker (it can take many
minutes), so POST returns immediately with ``status=pending``; poll GET until
``status`` is ``completed`` (or ``failed``).

NOTE: keep ``max_stocks`` + the date window SMALL — the per-(stock, T) input cache
is held in memory for the whole run, so a large universe/window is memory-heavy.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.backtest import BacktestEquityPoint, BacktestRun, GARun

router = APIRouter()


class GARequest(BaseModel):
    engine: str
    start_date: str                      # YYYY-MM-DD
    end_date: str                        # YYYY-MM-DD
    max_stocks: Optional[int] = 10       # keep small — the input cache is in-memory
    pop_size: int = 20
    generations: int = 15
    seed: int = 0
    train_split: float = 0.7             # chronological train/val split (overfit guard)
    dd_penalty: float = 0.5
    trade_count_floor: int = 5
    starting_cash: float = 100_000.0


def _ga_dict(r: GARun) -> dict:
    return {
        "id": r.id,
        "engine": r.engine,
        "status": r.status,
        "config": r.config,
        "config_version": r.config_version,
        "best_weights": r.best_weights,
        "best_train_fitness": float(r.best_train_fitness) if r.best_train_fitness is not None else None,
        "best_val_fitness": float(r.best_val_fitness) if r.best_val_fitness is not None else None,
        "train_val_gap": float(r.train_val_gap) if r.train_val_gap is not None else None,
        "best_train_metrics": r.best_train_metrics,
        "best_val_metrics": r.best_val_metrics,
        "generations": r.generations,
        "best_train_run_id": r.best_train_run_id,
        "error": r.error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }


def _point_dict(p: BacktestEquityPoint) -> dict:
    return {
        "date": p.date.isoformat() if p.date else None,
        "equity": float(p.equity),
        "cash": float(p.cash),
        "open_positions_value": float(p.open_positions_value),
        "realized_pnl_cumulative": float(p.realized_pnl_cumulative),
        "open_trades_count": p.open_trades_count,
    }


@router.post("")
def create_ga_run(req: GARequest, db: Session = Depends(get_db)):
    if req.engine not in ("engine_1", "engine_2"):
        raise HTTPException(status_code=400, detail="engine must be 'engine_1' or 'engine_2'")
    from datetime import datetime
    try:
        s = datetime.fromisoformat(req.start_date)
        e = datetime.fromisoformat(req.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="start_date/end_date must be YYYY-MM-DD")
    if s >= e:
        raise HTTPException(status_code=400, detail="start_date must precede end_date")
    if not (0 < req.train_split < 1):
        raise HTTPException(status_code=400, detail="train_split must be in (0, 1)")
    from app.tasks.backtest_tasks import run_ga_task

    run = GARun(
        engine=req.engine,
        status="pending",
        config={
            "start_date": req.start_date,
            "end_date": req.end_date,
            "max_stocks": req.max_stocks,
            "pop_size": req.pop_size,
            "generations": req.generations,
            "seed": req.seed,
            "train_split": req.train_split,
            "dd_penalty": req.dd_penalty,
            "trade_count_floor": req.trade_count_floor,
            "starting_cash": req.starting_cash,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    run_ga_task.delay(run.id)
    return _ga_dict(run)


@router.get("")
def list_ga_runs(
    engine: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(GARun)
    if engine:
        q = q.filter(GARun.engine == engine)
    rows = q.order_by(GARun.created_at.desc()).limit(limit).all()
    return {"runs": [_ga_dict(r) for r in rows]}


@router.get("/{ga_run_id}")
def get_ga_run(ga_run_id: int, db: Session = Depends(get_db)):
    run = db.query(GARun).filter(GARun.id == ga_run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="GA run not found")
    equity_curve = []
    if run.best_train_run_id is not None:
        pts = (
            db.query(BacktestEquityPoint)
            .filter(BacktestEquityPoint.run_id == run.best_train_run_id)
            .order_by(BacktestEquityPoint.date.asc())
            .all()
        )
        equity_curve = [_point_dict(p) for p in pts]

    # Default-weights "original engine" baseline run — config-tagged by run_ga_task
    # (located by ga_run_id + is_baseline, no FK/migration needed).
    baseline_equity_curve: list = []
    baseline_metrics = None
    baseline = (
        db.query(BacktestRun)
        .filter(BacktestRun.config["ga_run_id"].astext == str(ga_run_id))
        .filter(BacktestRun.config["is_baseline"].astext == "true")
        .order_by(BacktestRun.id.desc())
        .first()
    )
    if baseline is not None:
        baseline_metrics = baseline.metrics
        bpts = (
            db.query(BacktestEquityPoint)
            .filter(BacktestEquityPoint.run_id == baseline.id)
            .order_by(BacktestEquityPoint.date.asc())
            .all()
        )
        baseline_equity_curve = [_point_dict(p) for p in bpts]

    # S&P 500 benchmark over the SAME span as the equity curve (the train window),
    # scaled to starting_cash by the frontend. Only fetched once the run completes
    # (equity_curve is empty while running → no Polygon hit during 3s polling).
    benchmark: list = []
    if equity_curve:
        cfg = run.config or {}
        start_d = cfg.get("start_date")
        end_d = equity_curve[-1].get("date")
        if start_d and end_d:
            from app.services.benchmark_service import get_spy_series_for_window

            benchmark = get_spy_series_for_window(start_d, end_d)

    return {
        **_ga_dict(run),
        "equity_curve": equity_curve,
        "baseline_equity_curve": baseline_equity_curve,
        "baseline_metrics": baseline_metrics,
        "benchmark": benchmark,
    }
