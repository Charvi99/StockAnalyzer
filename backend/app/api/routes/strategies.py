"""
API Routes for Trading Strategies
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel

from app.db.database import get_db
from app.services.strategy_manager import strategy_manager


router = APIRouter()


class ExecuteStrategyRequest(BaseModel):
    """Request model for executing a strategy."""
    strategy_name: str
    parameters: Optional[Dict[str, Any]] = None


class BacktestStrategyRequest(BaseModel):
    """Request model for backtesting a strategy."""
    strategy_name: str
    initial_balance: Optional[float] = 10000.0
    parameters: Optional[Dict[str, Any]] = None


@router.get("/list")
async def list_strategies():
    """
    Get a list of all available trading strategies.

    Returns:
        List of strategies with their metadata
    """
    try:
        strategies = strategy_manager.list_strategies()
        return {
            "strategies": strategies,
            "total": len(strategies)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_name}")
async def get_strategy_details(strategy_name: str):
    """
    Get details about a specific strategy.

    Args:
        strategy_name: Name of the strategy

    Returns:
        Strategy details including name, description, and parameters
    """
    strategy = strategy_manager.get_strategy(strategy_name)

    if not strategy:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{strategy_name}' not found"
        )

    return {
        "name": strategy.name,
        "description": strategy.description,
        "parameters": strategy.get_parameters(),
        "default_parameters": strategy.get_default_parameters(),
        "min_data_points": strategy.get_min_data_points()
    }


@router.post("/{stock_id}/execute")
async def execute_strategy(
    stock_id: int,
    request: ExecuteStrategyRequest,
    db: Session = Depends(get_db)
):
    """
    Execute a strategy on a specific stock.

    Args:
        stock_id: ID of the stock to analyze
        request: Strategy execution parameters

    Returns:
        Strategy analysis results with signal, confidence, and details
    """
    try:
        strategy_manager.validate_parameters(request.strategy_name, request.parameters)
    except ValueError as e:
        # Unknown/misnamed parameter keys (audit S3) → 422, distinct from 404 below.
        raise HTTPException(status_code=422, detail=str(e))
    try:
        result = strategy_manager.execute_strategy(
            strategy_name=request.strategy_name,
            stock_id=stock_id,
            db=db,
            parameters=request.parameters
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{stock_id}/backtest")
async def backtest_strategy(
    stock_id: int,
    request: BacktestStrategyRequest,
    db: Session = Depends(get_db)
):
    """
    Run a backtest of a strategy on historical data.

    Args:
        stock_id: ID of the stock
        request: Backtest parameters

    Returns:
        Backtest results including returns, win rate, trades, etc.
    """
    # Phase 0.5: the toy in-base backtest was lookahead-biased (audit S2) and is
    # removed. A real backtester lands in Phase 2. Return 410 Gone in the meantime.
    raise HTTPException(
        status_code=410,
        detail="Backtest deprecated; a real backtester is coming in Phase 2. "
               "Use GET /api/v1/strategies/{stock_id}/snapshot for current strategy signals.",
    )


@router.get("/{stock_id}/snapshot")
async def strategy_snapshot(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    One-call snapshot: every registered strategy's current signal + the
    aggregated consensus for a stock (Phase 0.5). Powers the per-strategy list
    in the UI; the consensus also feeds the engine's "strategy" vote component.
    """
    try:
        return strategy_manager.snapshot(stock_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{stock_id}/execute-all")
async def execute_all_strategies(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    Execute all available strategies on a stock and return the consensus.

    Phase 0.5: the consensus is the SAME confidence-weighted vote
    (``compute_strategy_consensus``) used by ``GET /snapshot`` and by the
    recommendation engine's "strategy" component — so the Strategies tab, the
    radar axis, and the engine's final recommendation always agree. The raw
    per-signal counts are still returned for the breakdown display, but they no
    longer drive the consensus (a near-zero-confidence vote shouldn't outweigh a
    confident one).

    Args:
        stock_id: ID of the stock to analyze

    Returns:
        Dictionary with consensus + per-strategy results
    """
    try:
        # One indicator pass + the weighted consensus (reuses /snapshot).
        snap = strategy_manager.snapshot(stock_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    breakdown = snap.get('strategies', [])
    consensus_obj = snap.get('consensus') or {}

    # Count signals — exclude errored strategies from the denominator (audit S4).
    valid = [b for b in breakdown if b.get('signal') != 'ERROR']
    buy_count = sum(1 for b in valid if b.get('signal') == 'BUY')
    sell_count = sum(1 for b in valid if b.get('signal') == 'SELL')
    hold_count = sum(1 for b in valid if b.get('signal') == 'HOLD')

    # Reshape the snapshot breakdown into the per-strategy "results" the tab
    # already renders (strategy_name / signal / confidence / details.reason).
    results = []
    for b in breakdown:
        item = {
            'strategy_name': b.get('name'),
            'signal': b.get('signal'),
            'confidence': b.get('confidence', 0.0),
            'details': {'reason': b.get('reason', '')},
        }
        if b.get('error'):
            item['error'] = b.get('reason', '')
        results.append(item)

    return {
        'stock_id': stock_id,
        'total_strategies': len(valid),
        'consensus': consensus_obj.get('signal') or 'HOLD',
        'consensus_confidence': consensus_obj.get('confidence'),
        'signal_counts': {
            'buy': buy_count,
            'sell': sell_count,
            'hold': hold_count
        },
        'results': results,
        'source_version': snap.get('source_version'),
    }
