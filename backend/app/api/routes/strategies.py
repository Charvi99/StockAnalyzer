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
        result = await strategy_manager.execute_strategy(
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
    try:
        result = await strategy_manager.backtest_strategy(
            strategy_name=request.strategy_name,
            stock_id=stock_id,
            db=db,
            initial_balance=request.initial_balance,
            parameters=request.parameters
        )
        return result
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
    Execute all available strategies on a stock and compare results.

    Args:
        stock_id: ID of the stock to analyze

    Returns:
        Dictionary with results from all strategies
    """
    try:
        strategies = strategy_manager.list_strategies()
        results = []

        for strategy_info in strategies:
            try:
                result = await strategy_manager.execute_strategy(
                    strategy_name=strategy_info['name'],
                    stock_id=stock_id,
                    db=db
                )
                results.append(result)
            except Exception as e:
                # Continue even if one strategy fails
                results.append({
                    'strategy_name': strategy_info['name'],
                    'error': str(e),
                    'signal': 'ERROR'
                })

        # Count signals
        buy_count = sum(1 for r in results if r.get('signal') == 'BUY')
        sell_count = sum(1 for r in results if r.get('signal') == 'SELL')
        hold_count = sum(1 for r in results if r.get('signal') == 'HOLD')

        # Calculate consensus
        total_strategies = len(results)
        if buy_count > total_strategies / 2:
            consensus = 'BUY'
        elif sell_count > total_strategies / 2:
            consensus = 'SELL'
        else:
            consensus = 'HOLD'

        return {
            'stock_id': stock_id,
            'total_strategies': total_strategies,
            'consensus': consensus,
            'signal_counts': {
                'buy': buy_count,
                'sell': sell_count,
                'hold': hold_count
            },
            'results': results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
