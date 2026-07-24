"""ga runs (Phase 3 genetic-algorithm weight optimization)

Revision ID: 20260724_ga_runs
Revises: 20260723_backtest_runs
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '20260724_ga_runs'
down_revision = '20260723_backtest_runs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ga_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engine', sa.String(length=20), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('best_weights', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('best_train_fitness', sa.Numeric(10, 6), nullable=True),
        sa.Column('best_val_fitness', sa.Numeric(10, 6), nullable=True),
        sa.Column('train_val_gap', sa.Numeric(10, 6), nullable=True),
        sa.Column('best_train_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('best_val_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('generations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('config_version', sa.String(length=12), nullable=True),
        sa.Column('best_train_run_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['best_train_run_id'], ['backtest_runs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ga_runs_engine', 'ga_runs', ['engine'])
    op.create_index('ix_ga_runs_status', 'ga_runs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_ga_runs_status', table_name='ga_runs')
    op.drop_index('ix_ga_runs_engine', table_name='ga_runs')
    op.drop_table('ga_runs')
