"""
Dividend & Stock Split Trading Signals API

Provides upcoming dividend ex-dates and stock splits as trading signals.
Focus: Entry/Exit timing for swing trading, not income investing.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, date, timedelta
from typing import List, Optional
from app.db.database import get_db
from app.models.stock import Stock, StockPrice
from app.models.dividend import Dividend
from app.models.stock_split import StockSplit
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dividend-split-signals", tags=["dividend-split-signals"])


@router.get("/stocks/{stock_id}/upcoming")
def get_upcoming_catalysts(
    stock_id: int,
    days_ahead: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get upcoming trading catalysts (dividends, splits) for a stock

    Returns catalysts that can be used for entry/exit timing:
    - Upcoming ex-dividend dates (for exit before drop, entry after drop)
    - Upcoming splits (for pre-split rally entry, split-day exit)
    - Recent splits (for post-split re-entry opportunity)

    Args:
        stock_id: Stock ID
        days_ahead: Look ahead window (default 30 days)

    Returns:
        Dict with dividend and split catalysts, including trading signals
    """
    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get current price
    latest_price = db.query(StockPrice).filter(
        StockPrice.stock_id == stock_id
    ).order_by(StockPrice.timestamp.desc()).first()

    current_price = float(latest_price.close) if latest_price else None

    today = date.today()
    future_date = today + timedelta(days=days_ahead)
    past_date = today - timedelta(days=14)  # Look back for recent splits

    # Get upcoming dividends
    upcoming_dividends = db.query(Dividend).filter(
        and_(
            Dividend.stock_id == stock_id,
            Dividend.ex_dividend_date >= today,
            Dividend.ex_dividend_date <= future_date
        )
    ).order_by(Dividend.ex_dividend_date).all()

    # Get upcoming and recent splits
    splits = db.query(StockSplit).filter(
        and_(
            StockSplit.stock_id == stock_id,
            StockSplit.execution_date >= past_date,
            StockSplit.execution_date <= future_date
        )
    ).order_by(StockSplit.execution_date).all()

    # Process dividends into trading signals
    dividend_catalysts = []
    for div in upcoming_dividends:
        days_until = (div.ex_dividend_date - today).days
        dividend_yield_pct = (float(div.cash_amount) / current_price * 100) if current_price else 0

        # Determine signal type
        if 1 <= days_until <= 3:
            signal_type = "EXIT"
            signal_strength = "moderate"
            recommendation = f"Sell before ex-date to avoid {dividend_yield_pct:.2f}% drop"
            timing = "Before market close today" if days_until <= 1 else f"Within {days_until} days"
        elif days_until == 0 or days_until == -1:
            signal_type = "ENTRY"
            signal_strength = "moderate"
            recommendation = f"Buy post-dividend dip (~{dividend_yield_pct:.2f}% discount)"
            timing = "During opening dip"
        else:
            signal_type = "WATCH"
            signal_strength = "low"
            recommendation = f"Monitor as ex-date approaches ({days_until} days)"
            timing = f"Act in {days_until - 3} days"

        dividend_catalysts.append({
            "type": "dividend",
            "event": "Ex-Dividend Date",
            "date": div.ex_dividend_date.isoformat(),
            "days_until": days_until,
            "signal": signal_type,
            "signal_strength": signal_strength,
            "recommendation": recommendation,
            "timing": timing,
            "details": {
                "cash_amount": float(div.cash_amount),
                "yield_pct": round(dividend_yield_pct, 2),
                "expected_drop_pct": round(dividend_yield_pct, 2),
                "frequency": div.frequency or 4,  # Default quarterly
                "payment_date": div.payment_date.isoformat() if div.payment_date else None
            }
        })

    # Process splits into trading signals
    split_catalysts = []
    for split in splits:
        days_until = (split.execution_date - today).days
        split_ratio_text = f"{int(split.split_to)}-for-{int(split.split_from)}"

        # Determine signal type
        if 5 <= days_until <= 30:
            # Pre-split rally period
            signal_type = "ENTRY"
            signal_strength = "strong"
            recommendation = f"{split_ratio_text} split in {days_until} days. Typical +5-15% pre-split rally"
            timing = "Enter now, exit before split execution"
            expected_move = "+5% to +15%"
        elif -2 <= days_until <= 2:
            # Split execution window
            signal_type = "EXIT"
            signal_strength = "strong"
            recommendation = f"Split executing. Take profits from pre-split rally"
            timing = "Exit today or tomorrow"
            expected_move = "Profit-taking period"
        elif -14 <= days_until <= -7:
            # Post-split consolidation
            signal_type = "REENTRY"
            signal_strength = "moderate"
            recommendation = f"Post-split consolidation. Consider re-entry"
            timing = "Enter after cooldown"
            expected_move = "+3% to +8% recovery typical"
        elif days_until < -14:
            # Old split - informational only
            signal_type = "HISTORICAL"
            signal_strength = "none"
            recommendation = "Historical split - no current signal"
            timing = "N/A"
            expected_move = "N/A"
        else:
            signal_type = "WATCH"
            signal_strength = "low"
            recommendation = f"Split announced. Monitor for entry opportunity"
            timing = f"Wait {5 - days_until} more days for optimal entry"
            expected_move = "Rally typically starts 5-30 days before"

        split_catalysts.append({
            "type": "split",
            "event": "Stock Split",
            "date": split.execution_date.isoformat(),
            "days_until": days_until,
            "signal": signal_type,
            "signal_strength": signal_strength,
            "recommendation": recommendation,
            "timing": timing,
            "details": {
                "split_ratio": float(split.split_ratio),
                "split_ratio_text": split_ratio_text,
                "split_from": float(split.split_from),
                "split_to": float(split.split_to),
                "expected_move": expected_move,
                "is_upcoming": days_until > 0,
                "is_recent": -14 <= days_until < 0
            }
        })

    # Combine and prioritize
    all_catalysts = dividend_catalysts + split_catalysts

    # Sort by signal strength and proximity
    signal_priority = {"strong": 3, "moderate": 2, "low": 1, "none": 0}
    all_catalysts.sort(
        key=lambda x: (signal_priority.get(x["signal_strength"], 0), -abs(x["days_until"])),
        reverse=True
    )

    return {
        "stock_id": stock_id,
        "symbol": stock.symbol,
        "current_price": current_price,
        "catalysts": all_catalysts,
        "dividend_count": len(dividend_catalysts),
        "split_count": len(split_catalysts),
        "has_active_signals": any(c["signal_strength"] in ["strong", "moderate"] for c in all_catalysts)
    }


@router.get("/stocks/{stock_id}/dividends")
def get_stock_dividends(
    stock_id: int,
    limit: int = 12,
    db: Session = Depends(get_db)
):
    """
    Get dividend history for a stock

    Args:
        stock_id: Stock ID
        limit: Number of recent dividends to return (default 12 = 3 years quarterly)

    Returns:
        List of dividends with ex-dates and amounts
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    dividends = db.query(Dividend).filter(
        Dividend.stock_id == stock_id
    ).order_by(Dividend.ex_dividend_date.desc()).limit(limit).all()

    return {
        "stock_id": stock_id,
        "symbol": stock.symbol,
        "count": len(dividends),
        "dividends": [
            {
                "ex_dividend_date": div.ex_dividend_date.isoformat(),
                "payment_date": div.payment_date.isoformat() if div.payment_date else None,
                "cash_amount": float(div.cash_amount),
                "frequency": div.frequency,
                "dividend_type": div.dividend_type
            }
            for div in dividends
        ]
    }


@router.get("/stocks/{stock_id}/splits")
def get_stock_splits(
    stock_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get stock split history

    Args:
        stock_id: Stock ID
        limit: Number of recent splits to return (default 10)

    Returns:
        List of stock splits with ratios and dates
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    splits = db.query(StockSplit).filter(
        StockSplit.stock_id == stock_id
    ).order_by(StockSplit.execution_date.desc()).limit(limit).all()

    return {
        "stock_id": stock_id,
        "symbol": stock.symbol,
        "count": len(splits),
        "splits": [
            {
                "execution_date": split.execution_date.isoformat(),
                "split_ratio": float(split.split_ratio),
                "split_from": float(split.split_from),
                "split_to": float(split.split_to),
                "split_ratio_text": f"{int(split.split_to)}-for-{int(split.split_from)}"
            }
            for split in splits
        ]
    }
