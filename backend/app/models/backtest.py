"""
Backtest result models (Phase 2).

A ``BacktestRun`` is one historical replay of an engine over a date range; its
daily equity curve is stored as ``BacktestEquityPoint`` rows (mirroring the live
``PaperEquitySnapshot`` shape). The computed metrics + a composite fitness
scalar are stored on the run so runs are comparable and the Phase-3 genetic
algorithm can read fitness directly off the row.

These tables are written ONLY by the backtester — the live paper-trading ledger
(``paper_*``) is untouched. Backtests never mutate live state.
"""
from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, DECIMAL, ForeignKey, Date,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class BacktestRun(Base):
    """One historical backtest run of an engine over a date window."""

    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, index=True)
    engine = Column(String(20), nullable=False, index=True)        # 'engine_1' / 'engine_2'
    # Replay config + provenance: start/end dates, capital, risk knobs, the
    # signal config_version replayed, and the inputs excluded at price-technical
    # fidelity (sentiment/ML/dividend) so the run is self-documenting.
    config = Column(JSONB, nullable=True)
    config_version = Column(String(12), nullable=True)
    status = Column(String(20), nullable=False, server_default="pending", index=True)  # pending/running/completed/failed
    metrics = Column(JSONB, nullable=True)      # {total_return, cagr, sharpe, max_drawdown, ...}
    fitness = Column(DECIMAL(10, 6), nullable=True)   # composite GA objective (Phase 3)

    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    error = Column(Text, nullable=True)

    equity_points = relationship(
        "BacktestEquityPoint", back_populates="run", cascade="all, delete-orphan"
    )


class BacktestEquityPoint(Base):
    """One row per trading day per run — the backtest equity curve."""

    __tablename__ = "backtest_equity_points"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    cash = Column(DECIMAL(14, 2), nullable=False)
    open_positions_value = Column(DECIMAL(14, 2), nullable=False)
    equity = Column(DECIMAL(14, 2), nullable=False)                # cash + open market value
    realized_pnl_cumulative = Column(DECIMAL(14, 2), nullable=False)
    open_trades_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("run_id", "date", name="uq_backtest_equity_run_date"),
    )

    run = relationship("BacktestRun", back_populates="equity_points")
