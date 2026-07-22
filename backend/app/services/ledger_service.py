"""
Paper-trading ledger service (Phase 1, step 4).

Orchestrates virtual trades from the FRESH recommendation signal
(:mod:`ledger_signal_adapter`) through the order calculator
(:class:`OrderCalculatorService`) and :mod:`risk_utils`, recording entry/exit/
mark-to-market/equity over time so recommendation quality can be measured over
weeks/months and the two engines A/B-scored (decision D35).

Design rules (from the ecc review — see ``/home/jakub/.claude/plans/expressive-shimmying-quail.md``):
  - C1 — exits-first loop: ``log_signals -> check_exits(open w/ entry<today)
    -> open_fresh_buys -> mark_to_market -> snapshot_equity``. A trade opened
    this cycle is never exit-evaluated against its birth bar.
  - C2 — fresh signal only (the adapter never uses the indicator cache).
  - C3/C4 — the order calc is called with ``recommendation='BUY'`` (no Engine #2
    re-call); per-stock errors are caught so one bad row can't abort the cycle.
  - Idempotency — ``cycle_id`` threads through everything; ``paper_signal_log``
    and the equity snapshot upsert on conflict, and the partial unique index on
    ``paper_trades`` makes open/close idempotent under Celery ``acks_late``.

The decision math (exit reason, fresh-BUY detection, realized P&L, slippage,
split scaling) is extracted as PURE module-level functions so it is unit-tested
without a database. The DB-bound orchestration lives on the class.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ledger import (
    PaperAccount, PaperEquitySnapshot, PaperSignalLog, PaperTrade,
)
from app.models.stock import Stock, StockPrice
from app.models.stock_split import StockSplit
from app.services.ledger_signal_adapter import signal_for_ledger
from app.services.order_calculator import OrderCalculatorService
from app.services.signal.types import SignalResult
from app.utils.risk_utils import calculate_portfolio_heat

logger = logging.getLogger(__name__)

# ── v1 knobs (optimistic: relative comparison only; no slippage/fees) ──────────
# Each is a config lever for later. Defaults give a clean relative A/B score.
LEDGER_SLIPPAGE_BPS = 0          # applied to the BUY entry fill (0 = none)
LEDGER_COMMISSION_PER_SHARE = 0.0  # per-leg commission (0 = none)
LEDGER_RISK_PERCENT = 2.0        # max risk per trade (% of account)
LEDGER_MAX_PORTFOLIO_HEAT = 6.0  # max combined open risk (% of starting cash)
LEDGER_MAX_HOLD_DAYS = 60        # trading-day cap before a stale position is closed


# ──────────────────────────────────────────────────────────────────────────────
# PURE decision math (unit-tested in test_phase1_ledger.py — no DB)
# ──────────────────────────────────────────────────────────────────────────────
def _is_fresh_buy(last_logged_signal: Optional[str], current_signal: str) -> bool:
    """A fresh BUY = the signal just turned BUY (it was NOT BUY last cycle).

    A continuous BUY (last was BUY) is NOT fresh, so an open position is not
    pyramided — v1 holds one position per (account, stock)."""
    return last_logged_signal != "BUY" and current_signal == "BUY"


def _exit_reason(
    day_high: Optional[float],
    day_low: Optional[float],
    stop_loss: Optional[float],
    take_profit: Optional[float],
    trading_days_held: int,
    current_signal: Optional[str],
    max_hold_days: int = LEDGER_MAX_HOLD_DAYS,
) -> Optional[str]:
    """Decide why (if at all) an open long should close this cycle.

    Priority — hard price barriers first, SL-wins-conservatively when a single
    day's range spans BOTH the stop and the target (assume the stop hit first):
      1. ``stop_loss``    day_low <= stop_loss
      2. ``take_profit``  day_high >= take_profit
      3. ``signal_flip``  the engine flipped to SELL
      4. ``max_hold``     held >= max_hold_days (time cap)
    Returns the reason, or ``None`` to stay open.
    """
    # 1. Stop loss — checked first so a same-day TP+SL span resolves to SL.
    if day_low is not None and stop_loss is not None and day_low <= stop_loss:
        return "stop_loss"
    # 2. Take profit.
    if day_high is not None and take_profit is not None and day_high >= take_profit:
        return "take_profit"
    # 3. Signal flip — the engine actively says SELL.
    if current_signal == "SELL":
        return "signal_flip"
    # 4. Max-hold time cap — recycle stale capital.
    if trading_days_held >= max_hold_days:
        return "max_hold"
    return None


def _exit_fill_price(
    reason: str, stop_loss: Optional[float], take_profit: Optional[float], market_price: float
) -> float:
    """Fill price for a close: the barrier price for SL/TP (optimistic — fills
    exactly at the level), otherwise the current market price (signal_flip/max_hold)."""
    if reason == "stop_loss" and stop_loss is not None:
        return stop_loss
    if reason == "take_profit" and take_profit is not None:
        return take_profit
    return market_price


def _apply_slippage(price: float, bps: int = LEDGER_SLIPPAGE_BPS) -> float:
    """For a BUY, slippage makes the fill slightly HIGHER (worse). 0 bps = none."""
    return price * (1.0 + bps / 10000.0)


def _realized_pnl_long(
    entry_price: float, fill_price: float, position_size: int,
    commission_per_share: float = LEDGER_COMMISSION_PER_SHARE,
) -> Tuple[float, float]:
    """Realized P&L for a closed long, net of both-leg commissions.

    Matches the cash accounting exactly: cost = entry*size + entry commission,
    proceeds = fill*size - exit commission, so pnl = proceeds - cost.
    Returns (realized_pnl, realized_pnl_pct) where pct is vs the cost basis.
    """
    total_commission = commission_per_share * position_size * 2  # entry + exit
    pnl = (fill_price - entry_price) * position_size - total_commission
    cost_basis = entry_price * position_size + commission_per_share * position_size
    pct = (pnl / cost_basis) if cost_basis else 0.0
    return pnl, pct


def _scale_price_for_split(price: float, split_ratio: float) -> float:
    """A split_ratio > 1 (e.g. 2-for-1) halves prices; guard div-by-zero."""
    return price / split_ratio if split_ratio else price


def _scale_size_for_split(position_size: int, split_ratio: float) -> int:
    """A split_ratio > 1 multiplies share count; e.g. 2-for-1 doubles shares."""
    return int(round(position_size * split_ratio)) if split_ratio else position_size


# ──────────────────────────────────────────────────────────────────────────────
# LedgerService — DB-bound exits-first orchestration
# ──────────────────────────────────────────────────────────────────────────────
class LedgerService:
    """Runs one paper-trading cycle for one engine's account.

    Constructed per Celery task with its own session (H4: one task per engine,
    isolated, replayable). All writes are idempotent on ``cycle_id`` so an
    ``acks_late`` redelivery is a no-op.
    """

    def __init__(self, db: Session, engine: str):
        self.db = db
        self.engine = engine
        self.account = db.query(PaperAccount).filter(PaperAccount.engine == engine).first()
        if self.account is None:
            raise ValueError(
                f"No paper_account seeded for engine {engine!r}; "
                "seed it before running a cycle."
            )
        # Keep the account's config_version fresh (informational; per-trade is authoritative).
        self.account.config_version = self._engine_config_version()

    # ── config_version lookup (informational) ─────────────────────────────────
    def _engine_config_version(self) -> Optional[str]:
        """The current config_version for this engine's pure signal (None if unknown)."""
        try:
            if self.engine == "engine_1":
                from app.services.signal.systematic import signal_systematic
                import pandas as pd
                return signal_systematic(pd.DataFrame(), [], [], None, "unknown", None).config_version
            # engine_2 not yet enabled (step 8).
        except Exception as e:
            logger.warning(f"[ledger {self.engine}] config_version lookup failed: {e}")
        return None

    # ── the cycle ─────────────────────────────────────────────────────────────
    def run_cycle(self, cycle_id: date, cycle_dt: Optional[datetime] = None) -> Dict:
        """
        Run one exits-first trading cycle (C1 ordering).

        Args:
            cycle_id: the logical trading date (idempotency key for signals/snapshot).
            cycle_dt: the run timestamp for entry/exit stamps (default now UTC).

        Returns a small summary dict (counts) for logging/health.
        """
        cycle_dt = cycle_dt or datetime.now(timezone.utc)

        # 1. Compute + log signals for every stock; build the fresh-BUY set.
        current_signals, fresh_buys = self._compute_and_log_signals(cycle_id)

        # 2. Exits FIRST (frees cash before opens). C1 guard: entry_date < cycle.
        closed = self._check_exits(cycle_id, cycle_dt, current_signals)

        # 3. Open fresh BUYs.
        opened = self._open_fresh_buys(cycle_dt, current_signals, fresh_buys)

        # 4. Mark to market.
        self.mark_to_market()

        # 5. Snapshot equity (idempotent on cycle_id).
        self.snapshot_equity(cycle_id)

        self.db.flush()
        return {
            "engine": self.engine,
            "cycle_id": str(cycle_id),
            "signals_logged": len(current_signals),
            "fresh_buys": len(fresh_buys),
            "opened": opened,
            "closed": closed,
        }

    # ── step 1: signals + fresh-BUY detection ─────────────────────────────────
    def _compute_and_log_signals(self, cycle_id: date) -> Tuple[Dict[int, Optional[SignalResult]], set]:
        """Compute the fresh signal for every stock, log it (idempotent), and flag
        fresh BUYs. C4: a per-stock failure is caught — that stock is skipped, it
        never aborts the cycle."""
        current_signals: Dict[int, Optional[SignalResult]] = {}
        fresh_buys: set = set()

        stocks = self.db.query(Stock).all()
        for stock in stocks:
            try:
                sr = signal_for_ledger(self.db, stock, self.engine)
            except Exception as e:  # C4: one bad stock never aborts the cycle
                logger.warning(f"[ledger {self.engine}] signal failed for {stock.symbol} (id={stock.id}): {e}")
                current_signals[stock.id] = None
                continue

            current_signals[stock.id] = sr
            last = self._last_logged_signal(stock.id)  # BEFORE logging this cycle
            if _is_fresh_buy(last, sr.signal):
                fresh_buys.add(stock.id)
            self._log_signal(stock.id, cycle_id, sr)  # idempotent (ON CONFLICT DO NOTHING)

        return current_signals, fresh_buys

    def _last_logged_signal(self, stock_id: int) -> Optional[str]:
        """Most recent logged signal for this account+stock (before the current cycle)."""
        row = (
            self.db.query(PaperSignalLog.signal)
            .filter(PaperSignalLog.account_id == self.account.id, PaperSignalLog.stock_id == stock_id)
            .order_by(PaperSignalLog.cycle_id.desc(), PaperSignalLog.id.desc())
            .first()
        )
        return row[0] if row else None

    def _log_signal(self, stock_id: int, cycle_id: date, sr: SignalResult) -> None:
        """Append a signal row; idempotent on (account, stock, cycle_id)."""
        stmt = pg_insert(PaperSignalLog).values(
            account_id=self.account.id,
            stock_id=stock_id,
            engine=self.engine,
            cycle_id=cycle_id,
            signal=sr.signal,
            confidence=sr.confidence,
            config_version=sr.config_version,
        )
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_paper_signal_log_account_stock_cycle"
        )
        self.db.execute(stmt)

    # ── step 2: exits ─────────────────────────────────────────────────────────
    def _check_exits(self, cycle_id: date, cycle_dt: datetime,
                     current_signals: Dict[int, Optional[SignalResult]]) -> int:
        """Evaluate open positions (C1 guard: entry_date < cycle) for exit. Returns count closed."""
        open_trades = (
            self.db.query(PaperTrade)
            .filter(PaperTrade.account_id == self.account.id, PaperTrade.status == "open")
            .all()
        )
        closed = 0
        for trade in open_trades:
            # C1: never exit-evaluate a trade against its birth bar.
            if trade.entry_date and trade.entry_date.date() >= cycle_id:
                continue
            day_high, day_low, market_close = self._latest_daily_bar(trade.stock_id)
            if market_close is None:
                continue  # no price data to evaluate against

            sr = current_signals.get(trade.stock_id)
            current_signal = sr.signal if sr else None
            days_held = self.trading_days_between(trade.stock_id, trade.entry_date, cycle_dt)

            reason = _exit_reason(
                day_high=day_high,
                day_low=day_low,
                stop_loss=float(trade.stop_loss),
                take_profit=float(trade.take_profit),
                trading_days_held=days_held,
                current_signal=current_signal,
            )
            if reason is None:
                continue

            fill = _exit_fill_price(reason, float(trade.stop_loss), float(trade.take_profit), market_close)
            self.close_trade(trade, reason, fill, cycle_dt, signal_result=sr)
            closed += 1
        return closed

    # ── step 3: opens ─────────────────────────────────────────────────────────
    def _open_fresh_buys(self, cycle_dt: datetime,
                         current_signals: Dict[int, Optional[SignalResult]], fresh_buys: set) -> int:
        """Open a trade for each fresh BUY (after exits freed cash). Returns count opened."""
        opened = 0
        for stock_id in fresh_buys:
            sr = current_signals.get(stock_id)
            if sr is None:
                continue
            # Skip if a position is already open for this stock (v1: one per stock).
            if self._has_open_position(stock_id):
                continue
            stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
            if stock is None:
                continue
            try:
                trade = self.open_trade(stock, sr, cycle_dt)
                if trade is not None:
                    opened += 1
            except IntegrityError:
                # Partial unique index backstop: a race/redelivery already opened it.
                self.db.rollback()
                logger.info(f"[ledger {self.engine}] open for stock {stock_id} already exists (race) — skipped")
            except Exception as e:  # C4
                self.db.rollback()
                logger.warning(f"[ledger {self.engine}] open_trade failed for stock {stock_id}: {e}")
        return opened

    def _has_open_position(self, stock_id: int) -> bool:
        exists = (
            self.db.query(PaperTrade.id)
            .filter(PaperTrade.account_id == self.account.id,
                    PaperTrade.stock_id == stock_id,
                    PaperTrade.status == "open")
            .first()
        )
        return exists is not None

    def open_trade(self, stock: Stock, signal_result: SignalResult, cycle_dt: datetime) -> Optional[PaperTrade]:
        """Size + open a long from a fresh BUY signal (C3: order calc gets recommendation='BUY').

        Returns the new PaperTrade, or None if the trade was declined (no size,
        portfolio-heat limit, or insufficient cash)."""
        # C3: pass the known signal so order calc skips its Engine #2 re-call.
        order = OrderCalculatorService(self.db).calculate_order_parameters(
            stock_id=stock.id,
            account_size=float(self.account.cash),
            risk_percentage=LEDGER_RISK_PERCENT,
            recommendation="BUY",
        )

        size = int(order["position_size"] or 0)
        if size <= 0:
            logger.info(f"[ledger {self.engine}] {stock.symbol}: sized 0 — skipped")
            return None

        entry_price = _apply_slippage(float(order["entry_price"]))
        stop_loss = float(order["stop_loss"])
        take_profit = float(order["take_profit"])

        # Portfolio-heat guard: would adding this exceed the max combined risk?
        if not self._within_portfolio_heat(entry_price, stop_loss, size):
            logger.info(f"[ledger {self.engine}] {stock.symbol}: portfolio-heat limit — skipped")
            return None

        cost = entry_price * size + LEDGER_COMMISSION_PER_SHARE * size
        if cost > float(self.account.cash):
            logger.info(f"[ledger {self.engine}] {stock.symbol}: insufficient cash — skipped")
            return None

        self.account.cash = float(self.account.cash) - cost
        trade = PaperTrade(
            account_id=self.account.id,
            stock_id=stock.id,
            engine=self.engine,
            direction="long",
            signal_at_entry=signal_result.signal,
            config_version=signal_result.config_version,
            entry_confidence=signal_result.confidence,
            entry_price=entry_price,
            entry_date=cycle_dt,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=size,
            position_value=float(order["position_value"]),
            risk_amount=float(order["risk_amount"]),
            status="open",
        )
        self.db.add(trade)
        self.db.flush()  # surface partial-unique-index violation immediately
        logger.info(
            f"[ledger {self.engine}] OPEN {stock.symbol} @ {entry_price:.2f} "
            f"size={size} SL={stop_loss:.2f} TP={take_profit:.2f} cv={signal_result.config_version}"
        )
        return trade

    def _within_portfolio_heat(self, entry_price: float, stop_loss: float, size: int) -> bool:
        """Would opening this position keep total portfolio heat under the cap?"""
        open_trades = (
            self.db.query(PaperTrade)
            .filter(PaperTrade.account_id == self.account.id, PaperTrade.status == "open")
            .all()
        )
        positions = [
            {"entry_price": float(t.entry_price), "stop_loss": float(t.stop_loss),
             "position_size": int(t.position_size)}
            for t in open_trades
        ]
        positions.append({"entry_price": entry_price, "stop_loss": stop_loss, "position_size": size})
        heat = calculate_portfolio_heat(
            open_positions=positions,
            account_capital=float(self.account.starting_cash),
            max_portfolio_heat_percent=LEDGER_MAX_PORTFOLIO_HEAT,
        )
        return bool(heat.get("can_add_position", False))

    # ── close ─────────────────────────────────────────────────────────────────
    def close_trade(self, trade: PaperTrade, reason: str, fill_price: float,
                    cycle_dt: datetime, signal_result: Optional[SignalResult] = None) -> None:
        """Close a trade at fill_price: record exit fields, credit cash.

        On a signal_flip the current signal's attribution is recorded (exit_signal/
        exit_config_version/exit_confidence); other reasons leave them null."""
        size = int(trade.position_size)
        pnl, pct = _realized_pnl_long(
            float(trade.entry_price), fill_price, size, LEDGER_COMMISSION_PER_SHARE
        )
        proceeds = fill_price * size - LEDGER_COMMISSION_PER_SHARE * size
        self.account.cash = float(self.account.cash) + proceeds

        trade.exit_price = fill_price
        trade.exit_date = cycle_dt
        trade.exit_reason = reason
        trade.realized_pnl = pnl
        trade.realized_pnl_pct = pct
        trade.mark_price = fill_price
        trade.unrealized_pnl = 0.0
        trade.status = "closed"
        trade.closed_at = cycle_dt
        if signal_result is not None and reason == "signal_flip":
            trade.exit_signal = signal_result.signal
            trade.exit_config_version = signal_result.config_version
            trade.exit_confidence = signal_result.confidence
        self.db.flush()
        logger.info(
            f"[ledger {self.engine}] CLOSE reason={reason} pnl={pnl:.2f} ({pct*100:.2f}%)"
        )

    # ── step 4: mark to market ────────────────────────────────────────────────
    def mark_to_market(self) -> None:
        """Update mark_price + unrealized_pnl on every open trade."""
        open_trades = (
            self.db.query(PaperTrade)
            .filter(PaperTrade.account_id == self.account.id, PaperTrade.status == "open")
            .all()
        )
        for trade in open_trades:
            price = self._latest_close(trade.stock_id)
            if price is None:
                continue
            trade.mark_price = price
            trade.unrealized_pnl = (price - float(trade.entry_price)) * int(trade.position_size)

    # ── step 5: equity snapshot ───────────────────────────────────────────────
    def snapshot_equity(self, cycle_id: date) -> None:
        """Upsert one equity-curve row for this cycle (idempotent on (account, date))."""
        open_trades = (
            self.db.query(PaperTrade)
            .filter(PaperTrade.account_id == self.account.id, PaperTrade.status == "open")
            .all()
        )
        open_value = sum(
            float(t.mark_price or t.entry_price) * int(t.position_size) for t in open_trades
        )
        realized_cum = (
            self.db.query(func.coalesce(func.sum(PaperTrade.realized_pnl), 0))
            .filter(PaperTrade.account_id == self.account.id, PaperTrade.status == "closed")
            .scalar()
            or 0
        )
        cash = float(self.account.cash)
        equity = cash + open_value

        stmt = pg_insert(PaperEquitySnapshot).values(
            account_id=self.account.id,
            date=cycle_id,
            cash=cash,
            open_positions_value=open_value,
            equity=equity,
            realized_pnl_cumulative=float(realized_cum),
            open_trades_count=len(open_trades),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_paper_equity_account_date",
            set_={
                "cash": stmt.excluded.cash,
                "open_positions_value": stmt.excluded.open_positions_value,
                "equity": stmt.excluded.equity,
                "realized_pnl_cumulative": stmt.excluded.realized_pnl_cumulative,
                "open_trades_count": stmt.excluded.open_trades_count,
            },
        )
        self.db.execute(stmt)

    # ── split adjustment (v1) ─────────────────────────────────────────────────
    def adjust_for_splits(self, trade: PaperTrade, as_of_dt: datetime) -> bool:
        """Scale an open trade's entry/SL/TP/size for any splits since entry_date.

        Appends each adjustment to ``trade.adjustments`` (JSONB audit trail).
        Returns True if at least one split was applied. (Delisting is deferred.)"""
        splits = (
            self.db.query(StockSplit)
            .filter(StockSplit.stock_id == trade.stock_id,
                    StockSplit.execution_date > trade.entry_date.date(),
                    StockSplit.execution_date <= as_of_dt.date())
            .order_by(StockSplit.execution_date.asc())
            .all()
        )
        if not splits:
            return False

        adjustments = list(trade.adjustments or [])
        for sp in splits:
            ratio = float(sp.split_ratio) or 1.0
            if ratio == 1.0:
                continue
            before = {
                "entry_price": float(trade.entry_price),
                "stop_loss": float(trade.stop_loss),
                "take_profit": float(trade.take_profit),
                "position_size": int(trade.position_size),
            }
            trade.entry_price = _scale_price_for_split(float(trade.entry_price), ratio)
            trade.stop_loss = _scale_price_for_split(float(trade.stop_loss), ratio)
            trade.take_profit = _scale_price_for_split(float(trade.take_profit), ratio)
            trade.position_size = _scale_size_for_split(int(trade.position_size), ratio)
            adjustments.append({
                "execution_date": str(sp.execution_date),
                "split_ratio": ratio,
                "before": before,
                "after": {
                    "entry_price": float(trade.entry_price),
                    "stop_loss": float(trade.stop_loss),
                    "take_profit": float(trade.take_profit),
                    "position_size": int(trade.position_size),
                },
            })
        trade.adjustments = adjustments
        return True

    # ── helpers ───────────────────────────────────────────────────────────────
    def trading_days_between(self, stock_id: int, entry_date: datetime, as_of_dt: datetime) -> int:
        """Count distinct daily bars strictly after entry_date up to as_of_dt
        (an NYSE-calendar proxy for trading days held)."""
        count = (
            self.db.query(func.count(StockPrice.id.distinct()))
            .filter(
                StockPrice.stock_id == stock_id,
                StockPrice.timeframe == "1d",
                StockPrice.timestamp > entry_date,
                StockPrice.timestamp <= as_of_dt,
            )
            .scalar()
        )
        return int(count or 0)

    def _latest_daily_bar(self, stock_id: int) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """(high, low, close) of the most recent 1d bar, or (None,None,None)."""
        p = (
            self.db.query(StockPrice)
            .filter(StockPrice.stock_id == stock_id, StockPrice.timeframe == "1d")
            .order_by(StockPrice.timestamp.desc())
            .first()
        )
        if not p:
            return None, None, None
        return float(p.high), float(p.low), float(p.close)

    def _latest_close(self, stock_id: int) -> Optional[float]:
        """Most recent daily close, or None."""
        _, _, close = self._latest_daily_bar(stock_id)
        return close
