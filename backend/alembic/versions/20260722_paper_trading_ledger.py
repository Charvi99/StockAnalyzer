"""paper-trading ledger (Phase 1)

Revision ID: 20260722_ledger
Revises: 20260722_cpuniq
Create Date: 2026-07-22 00:00:00.000000

Adds the paper-trading ledger tables (paper_accounts, paper_trades,
paper_signal_log, paper_equity_snapshots), the partial unique index enforcing
one open position per (account, stock), and seeds the engine_1 virtual account.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260722_ledger'
down_revision = '20260722_cpuniq'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── paper_accounts ─────────────────────────────────────────────────────
    op.create_table(
        'paper_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engine', sa.String(length=20), nullable=False),
        sa.Column('starting_cash', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('cash', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('config_version', sa.String(length=12), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('engine', name='paper_accounts_engine_key'),
    )
    op.create_index('ix_paper_accounts_engine', 'paper_accounts', ['engine'], unique=True)

    # ── paper_trades ───────────────────────────────────────────────────────
    op.create_table(
        'paper_trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('engine', sa.String(length=20), nullable=False),
        sa.Column('direction', sa.String(length=10), nullable=False, server_default=sa.text("'long'")),
        sa.Column('signal_at_entry', sa.String(length=10), nullable=False),
        sa.Column('config_version', sa.String(length=12), nullable=True),
        sa.Column('entry_confidence', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('entry_price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('entry_date', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('stop_loss', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('take_profit', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('position_size', sa.Integer(), nullable=False),
        sa.Column('position_value', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('risk_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default=sa.text("'open'")),
        sa.Column('exit_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('exit_date', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('exit_reason', sa.String(length=20), nullable=True),
        sa.Column('exit_signal', sa.String(length=10), nullable=True),
        sa.Column('exit_config_version', sa.String(length=12), nullable=True),
        sa.Column('exit_confidence', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('realized_pnl', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('realized_pnl_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('mark_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('unrealized_pnl', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('adjustments', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('closed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.CheckConstraint("direction IN ('long')", name='check_paper_trade_direction'),
        sa.CheckConstraint("status IN ('open', 'closed')", name='check_paper_trade_status'),
    )
    op.create_index('ix_paper_trades_account_id', 'paper_trades', ['account_id'])
    op.create_index('ix_paper_trades_stock_id', 'paper_trades', ['stock_id'])
    op.create_index('ix_paper_trades_engine', 'paper_trades', ['engine'])
    op.create_index('ix_paper_trades_status', 'paper_trades', ['status'])
    # One open position per (account, stock); also makes open/close idempotent under acks_late.
    op.create_index(
        'uq_paper_trades_one_open', 'paper_trades', ['account_id', 'stock_id'],
        unique=True, postgresql_where=sa.text("status = 'open'"),
    )

    # ── paper_signal_log ──────────────────────────────────────────────────
    op.create_table(
        'paper_signal_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('engine', sa.String(length=20), nullable=False),
        sa.Column('cycle_id', sa.Date(), nullable=False),
        sa.Column('signal', sa.String(length=10), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('config_version', sa.String(length=12), nullable=True),
        sa.Column('logged_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('account_id', 'stock_id', 'cycle_id', name='uq_paper_signal_log_account_stock_cycle'),
    )
    op.create_index('ix_paper_signal_log_account_id', 'paper_signal_log', ['account_id'])
    op.create_index('ix_paper_signal_log_stock_id', 'paper_signal_log', ['stock_id'])
    op.create_index('ix_paper_signal_log_engine_stock_logged', 'paper_signal_log', ['engine', 'stock_id', 'logged_at'])

    # ── paper_equity_snapshots ────────────────────────────────────────────
    op.create_table(
        'paper_equity_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('cash', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('open_positions_value', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('equity', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('realized_pnl_cumulative', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('open_trades_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('account_id', 'date', name='uq_paper_equity_account_date'),
    )
    op.create_index('ix_paper_equity_snapshots_account_id', 'paper_equity_snapshots', ['account_id'])

    # ── seed the engine_1 virtual account ($100,000) ──────────────────────
    op.execute(
        "INSERT INTO paper_accounts (engine, starting_cash, cash) "
        "VALUES ('engine_1', 100000, 100000) "
        "ON CONFLICT (engine) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table('paper_equity_snapshots')
    op.drop_table('paper_signal_log')
    op.drop_index('uq_paper_trades_one_open', table_name='paper_trades')
    op.drop_table('paper_trades')
    op.drop_table('paper_accounts')
