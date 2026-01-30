"""
Dividend & Stock Split Detection Service

Detects upcoming dividends and stock splits for use in recommendation engine.
Returns actionable signals that can adjust recommendation scores.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date, timedelta
from typing import Dict, Optional, List
import logging

from app.models.stock import Stock
from app.models.dividend import Dividend
from app.models.stock_split import StockSplit

logger = logging.getLogger(__name__)


class DividendSplitDetector:
    """
    Service for detecting dividend and split events that affect trading decisions.

    Used by recommendation engine to:
    1. Reduce BUY score if ex-dividend date approaching (EXIT signal)
    2. Increase BUY score for post-dividend dip (ENTRY signal)
    3. Increase BUY score for pre-split rally (ENTRY signal)
    4. Reduce BUY score around split execution (EXIT signal)
    """

    def __init__(self):
        pass

    def get_signals_for_recommendation(
        self,
        stock_id: int,
        db: Session,
        days_ahead: int = 30
    ) -> Dict:
        """
        Get dividend/split signals that should influence recommendation.

        Args:
            stock_id: Stock ID
            db: Database session
            days_ahead: Look ahead window (default 30 days)

        Returns:
            {
                'has_signal': bool,
                'signal_type': str,  # 'dividend_exit', 'dividend_entry', 'split_entry', 'split_exit'
                'signal_strength': str,  # 'strong', 'moderate', 'low'
                'score_adjustment': int,  # -20 to +20 points for recommendation
                'reasoning': str,  # Human-readable explanation
                'event_date': str,  # ISO date of event
                'days_until': int,
                'details': dict  # Additional event details
            }
        """
        today = date.today()
        future_date = today + timedelta(days=days_ahead)
        past_date = today - timedelta(days=14)

        # Check for dividend signals
        dividend_signal = self._check_dividend_signals(stock_id, db, today, future_date)
        if dividend_signal['has_signal']:
            return dividend_signal

        # Check for split signals
        split_signal = self._check_split_signals(stock_id, db, today, future_date, past_date)
        if split_signal['has_signal']:
            return split_signal

        # No signals found
        return {
            'has_signal': False,
            'signal_type': None,
            'signal_strength': None,
            'score_adjustment': 0,
            'reasoning': None,
            'event_date': None,
            'days_until': None,
            'details': {}
        }

    def _check_dividend_signals(
        self,
        stock_id: int,
        db: Session,
        today: date,
        future_date: date
    ) -> Dict:
        """Check for dividend-related trading signals"""

        # Get upcoming dividends
        dividends = db.query(Dividend).filter(
            and_(
                Dividend.stock_id == stock_id,
                Dividend.ex_dividend_date >= today - timedelta(days=1),
                Dividend.ex_dividend_date <= future_date
            )
        ).order_by(Dividend.ex_dividend_date).all()

        if not dividends:
            return {'has_signal': False}

        # Get the nearest dividend
        div = dividends[0]
        days_until = (div.ex_dividend_date - today).days

        # EXIT SIGNAL: 1-3 days before ex-dividend date
        if 1 <= days_until <= 3:
            return {
                'has_signal': True,
                'signal_type': 'dividend_exit',
                'signal_strength': 'moderate',
                'score_adjustment': -15,  # Reduce BUY recommendation
                'reasoning': f"Exit signal: Ex-dividend date in {days_until} days. Stock typically drops by dividend amount (${float(div.cash_amount):.2f}). Consider selling before the drop.",
                'event_date': div.ex_dividend_date.isoformat(),
                'days_until': days_until,
                'details': {
                    'dividend_amount': float(div.cash_amount),
                    'payment_date': div.payment_date.isoformat() if div.payment_date else None,
                    'timing': 'Sell before market close' if days_until <= 1 else f'Sell within {days_until} days'
                }
            }

        # ENTRY SIGNAL: Day of or day after ex-dividend (buy the dip)
        elif days_until == 0 or days_until == -1:
            return {
                'has_signal': True,
                'signal_type': 'dividend_entry',
                'signal_strength': 'moderate',
                'score_adjustment': +10,  # Boost BUY recommendation
                'reasoning': f"Entry signal: Post-dividend dip opportunity. Stock dropped by dividend amount (${float(div.cash_amount):.2f}). Typical recovery in 1-3 days. Buy the discount.",
                'event_date': div.ex_dividend_date.isoformat(),
                'days_until': days_until,
                'details': {
                    'dividend_amount': float(div.cash_amount),
                    'expected_recovery_days': '1-3 days',
                    'timing': 'Buy during opening dip'
                }
            }

        # No actionable signal (too far away)
        return {'has_signal': False}

    def _check_split_signals(
        self,
        stock_id: int,
        db: Session,
        today: date,
        future_date: date,
        past_date: date
    ) -> Dict:
        """Check for stock split trading signals"""

        # Get upcoming and recent splits
        splits = db.query(StockSplit).filter(
            and_(
                StockSplit.stock_id == stock_id,
                StockSplit.execution_date >= past_date,
                StockSplit.execution_date <= future_date
            )
        ).order_by(StockSplit.execution_date).all()

        if not splits:
            return {'has_signal': False}

        # Get the nearest split
        split = splits[0]
        days_until = (split.execution_date - today).days
        split_ratio_text = f"{int(split.split_to)}-for-{int(split.split_from)}"

        # ENTRY SIGNAL: 5-30 days before split (pre-split rally)
        if 5 <= days_until <= 30:
            return {
                'has_signal': True,
                'signal_type': 'split_entry',
                'signal_strength': 'strong',
                'score_adjustment': +20,  # Strong BUY recommendation
                'reasoning': f"Strong entry signal: {split_ratio_text} stock split in {days_until} days. Historical data shows 5-15% pre-split rally is typical. Enter now, exit 1-2 days before split execution.",
                'event_date': split.execution_date.isoformat(),
                'days_until': days_until,
                'details': {
                    'split_ratio': split_ratio_text,
                    'expected_move': '+5% to +15%',
                    'timing': 'Enter now for pre-split rally',
                    'exit_timing': f'Exit {days_until - 2} days from now (before split)'
                }
            }

        # EXIT SIGNAL: Around split execution (-2 to +2 days)
        elif -2 <= days_until <= 2:
            return {
                'has_signal': True,
                'signal_type': 'split_exit',
                'signal_strength': 'strong',
                'score_adjustment': -20,  # Strong SELL recommendation
                'reasoning': f"Exit signal: {split_ratio_text} split executing {'today' if days_until == 0 else 'in ' + str(days_until) + ' days'}. Take profits from pre-split rally. Typical profit-taking period.",
                'event_date': split.execution_date.isoformat(),
                'days_until': days_until,
                'details': {
                    'split_ratio': split_ratio_text,
                    'timing': 'Exit today or tomorrow',
                    'note': 'Lock in pre-split gains'
                }
            }

        # RE-ENTRY SIGNAL: 7-14 days after split (post-split consolidation)
        elif -14 <= days_until <= -7:
            return {
                'has_signal': True,
                'signal_type': 'split_reentry',
                'signal_strength': 'moderate',
                'score_adjustment': +10,  # Moderate BUY recommendation
                'reasoning': f"Re-entry signal: {split_ratio_text} split completed {-days_until} days ago. Post-split consolidation period. +3% to +8% recovery typical. Good re-entry point.",
                'event_date': split.execution_date.isoformat(),
                'days_until': days_until,
                'details': {
                    'split_ratio': split_ratio_text,
                    'expected_move': '+3% to +8%',
                    'timing': 'Enter after cooldown period',
                    'days_since_split': -days_until
                }
            }

        # No actionable signal
        return {'has_signal': False}

    def get_all_signals(
        self,
        stock_ids: List[int],
        db: Session,
        days_ahead: int = 30
    ) -> Dict[int, Dict]:
        """
        Get signals for multiple stocks (for dashboard/screener).

        Args:
            stock_ids: List of stock IDs
            db: Database session
            days_ahead: Look ahead window

        Returns:
            Dictionary mapping stock_id to signal dict
        """
        signals = {}
        for stock_id in stock_ids:
            signal = self.get_signals_for_recommendation(stock_id, db, days_ahead)
            if signal['has_signal']:
                signals[stock_id] = signal

        return signals
