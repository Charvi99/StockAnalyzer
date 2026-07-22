"""paper-trading ledger reasoning columns (Phase 1.8)

Revision ID: 20260722_ledger_reasoning
Revises: 20260722_ledger
Create Date: 2026-07-22 00:00:00.000000

Adds ``entry_reasoning`` + ``exit_reasoning`` JSONB columns to ``paper_trades`` so
each virtual trade carries the signal's per-component scores + reasoning lines +
regime (the "why" it was opened/closed). The data already flows through
``SignalResult``; this just persists it. Nullable so existing rows are unaffected
and the column is simply absent-pre-trade until a cycle writes it.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '20260722_ledger_reasoning'
down_revision = '20260722_ledger'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('paper_trades', sa.Column('entry_reasoning', JSONB(), nullable=True))
    op.add_column('paper_trades', sa.Column('exit_reasoning', JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('paper_trades', 'exit_reasoning')
    op.drop_column('paper_trades', 'entry_reasoning')
