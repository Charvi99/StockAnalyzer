"""add_splits_and_short_interest_tables

Revision ID: 198a0e1e4d5f
Revises: c25d03c9157a
Create Date: 2025-10-31 07:12:40.769246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '198a0e1e4d5f'
down_revision: Union[str, Sequence[str], None] = 'c25d03c9157a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_splits and short_interest tables."""

    # ============================================
    # STOCK SPLITS TABLE
    # ============================================
    op.create_table(
        'stock_splits',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('stock_id', sa.Integer, sa.ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('execution_date', sa.Date, nullable=False, index=True),  # Date split takes effect
        sa.Column('split_from', sa.DECIMAL(12, 6), nullable=False),  # Original shares (e.g., 1.0)
        sa.Column('split_to', sa.DECIMAL(12, 6), nullable=False),  # New shares (e.g., 2.0 for 2-for-1)
        sa.Column('split_ratio', sa.DECIMAL(12, 6), nullable=False),  # Calculated ratio (split_to / split_from)
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.now(), onupdate=sa.func.now()),
        # Prevent duplicate splits for same stock and execution date
        sa.UniqueConstraint('stock_id', 'execution_date', name='uq_stock_execution_date')
    )

    op.create_index('idx_splits_execution_date', 'stock_splits', ['execution_date'])

    # ============================================
    # SHORT INTEREST TABLE
    # ============================================
    op.create_table(
        'short_interest',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('stock_id', sa.Integer, sa.ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('settlement_date', sa.Date, nullable=False, index=True),  # Settlement date of the short interest report
        sa.Column('short_interest', sa.BigInteger, nullable=False),  # Number of shares sold short
        sa.Column('avg_volume_30d', sa.BigInteger, nullable=True),  # 30-day average volume (for calculating days to cover)
        sa.Column('days_to_cover', sa.DECIMAL(8, 2), nullable=True),  # short_interest / avg_volume_30d
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.now(), onupdate=sa.func.now()),
        # Prevent duplicate short interest for same stock and settlement date
        sa.UniqueConstraint('stock_id', 'settlement_date', name='uq_stock_settlement_date')
    )

    op.create_index('idx_short_interest_settlement', 'short_interest', ['settlement_date'])


def downgrade() -> None:
    """Drop stock_splits and short_interest tables."""
    op.drop_index('idx_short_interest_settlement', 'short_interest')
    op.drop_table('short_interest')

    op.drop_index('idx_splits_execution_date', 'stock_splits')
    op.drop_table('stock_splits')
