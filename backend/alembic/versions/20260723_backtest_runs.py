"""backtest runs + equity points

Revision ID: 20260723_backtest_runs
Revises: 20260722_ledger_engine2_seed
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '20260723_backtest_runs'
down_revision = '20260722_ledger_engine2_seed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engine', sa.String(length=20), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('config_version', sa.String(length=12), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fitness', sa.Numeric(10, 6), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_backtest_runs_engine', 'backtest_runs', ['engine'])
    op.create_index('ix_backtest_runs_status', 'backtest_runs', ['status'])

    op.create_table(
        'backtest_equity_points',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('cash', sa.Numeric(14, 2), nullable=False),
        sa.Column('open_positions_value', sa.Numeric(14, 2), nullable=False),
        sa.Column('equity', sa.Numeric(14, 2), nullable=False),
        sa.Column('realized_pnl_cumulative', sa.Numeric(14, 2), nullable=False),
        sa.Column('open_trades_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', 'date', name='uq_backtest_equity_run_date'),
    )
    op.create_index('ix_backtest_equity_points_run_id', 'backtest_equity_points', ['run_id'])


def downgrade() -> None:
    op.drop_index('ix_backtest_equity_points_run_id', table_name='backtest_equity_points')
    op.drop_table('backtest_equity_points')
    op.drop_index('ix_backtest_runs_status', table_name='backtest_runs')
    op.drop_index('ix_backtest_runs_engine', table_name='backtest_runs')
    op.drop_table('backtest_runs')
