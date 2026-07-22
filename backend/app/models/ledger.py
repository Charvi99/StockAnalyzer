"""
Paper-trading ledger models (Phase 1).

Records virtual trades opened from recommendation signals, marks them to market,
and snapshots per-engine equity over time so recommendation quality can be
measured over weeks/months and the two engines A/B-scored (audit decision D35).

Design notes:
  - `config_version` is stored per trade (and in the signal log) so every outcome
    is attributable to the exact signal-config that was live at entry/exit.
  - One open position per (account, stock) is enforced by a **partial unique index**
    (`WHERE status='open'`) created in the migration — it also makes open/close
    idempotent under Celery ``acks_late`` redelivery.
  - `paper_signal_log` is append-only with a (account, stock, cycle_id) unique key +
    ON CONFLICT DO NOTHING, so a redelivered cycle never double-logs/double-fires.
"""
from sqlalchemy import (
    Column, Integer, String, TIMESTAMP, DECIMAL, ForeignKey, CheckConstraint,
    Date, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class PaperAccount(Base):
    """One virtual trading account per engine (engine_1 / engine_2)."""

    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, index=True)
    engine = Column(String(20), nullable=False, unique=True)  # 'engine_1' / 'engine_2'
    starting_cash = Column(DECIMAL(14, 2), nullable=False)
    cash = Column(DECIMAL(14, 2), nullable=False)
    # The engine's current signal config_version (informational; per-trade is authoritative).
    config_version = Column(String(12), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    trades = relationship("PaperTrade", back_populates="account")
    snapshots = relationship("PaperEquitySnapshot", back_populates="account")
    signal_logs = relationship("PaperSignalLog", back_populates="account")


class PaperTrade(Base):
    """A single virtual trade (open or closed)."""

    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    engine = Column(String(20), nullable=False, index=True)  # denormalized for filtering
    direction = Column(String(10), nullable=False, server_default="long")  # 'long' (v1)

    # ── signal attribution (the ledger key) ──
    signal_at_entry = Column(String(10), nullable=False)  # 'BUY'
    config_version = Column(String(12), nullable=True)
    entry_confidence = Column(DECIMAL(5, 4), nullable=True)

    # ── entry ──
    entry_price = Column(DECIMAL(12, 4), nullable=False)
    entry_date = Column(TIMESTAMP(timezone=True), nullable=False)
    stop_loss = Column(DECIMAL(12, 4), nullable=False)
    take_profit = Column(DECIMAL(12, 4), nullable=False)
    position_size = Column(Integer, nullable=False)        # shares
    position_value = Column(DECIMAL(14, 2), nullable=False)
    risk_amount = Column(DECIMAL(14, 2), nullable=False)

    # ── status ──
    status = Column(String(10), nullable=False, server_default="open", index=True)

    # ── exit ──
    exit_price = Column(DECIMAL(12, 4), nullable=True)
    exit_date = Column(TIMESTAMP(timezone=True), nullable=True)
    exit_reason = Column(String(20), nullable=True)        # take_profit/stop_loss/max_hold/signal_flip
    exit_signal = Column(String(10), nullable=True)
    exit_config_version = Column(String(12), nullable=True)
    exit_confidence = Column(DECIMAL(5, 4), nullable=True)
    realized_pnl = Column(DECIMAL(14, 2), nullable=True)
    realized_pnl_pct = Column(DECIMAL(8, 4), nullable=True)

    # ── mark-to-market ──
    mark_price = Column(DECIMAL(12, 4), nullable=True)
    unrealized_pnl = Column(DECIMAL(14, 2), nullable=True)
    adjustments = Column(JSONB, nullable=True)             # split-adjustment audit trail

    closed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("direction IN ('long')", name="check_paper_trade_direction"),
        CheckConstraint("status IN ('open', 'closed')", name="check_paper_trade_status"),
        # One open position per (account, stock): enforced by the partial unique index
        # uq_paper_trades_one_open (WHERE status='open'), created in the migration.
    )

    account = relationship("PaperAccount", back_populates="trades")
    stock = relationship("Stock")


class PaperSignalLog(Base):
    """Append-only signal history per (stock, engine); fresh-BUY detection + audit."""

    __tablename__ = "paper_signal_log"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    engine = Column(String(20), nullable=False)
    cycle_id = Column(Date, nullable=False)                # logical trading date (idempotency key)
    signal = Column(String(10), nullable=False)            # BUY/SELL/HOLD
    confidence = Column(DECIMAL(5, 4), nullable=True)
    config_version = Column(String(12), nullable=True)
    logged_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "stock_id", "cycle_id", name="uq_paper_signal_log_account_stock_cycle"),
    )

    account = relationship("PaperAccount", back_populates="signal_logs")
    stock = relationship("Stock")


class PaperEquitySnapshot(Base):
    """One row per day per account — the equity curve."""

    __tablename__ = "paper_equity_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    cash = Column(DECIMAL(14, 2), nullable=False)
    open_positions_value = Column(DECIMAL(14, 2), nullable=False)
    equity = Column(DECIMAL(14, 2), nullable=False)        # cash + open market value
    realized_pnl_cumulative = Column(DECIMAL(14, 2), nullable=False)
    open_trades_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "date", name="uq_paper_equity_account_date"),
    )

    account = relationship("PaperAccount", back_populates="snapshots")
