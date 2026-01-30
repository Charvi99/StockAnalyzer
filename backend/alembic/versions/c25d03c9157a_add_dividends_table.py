"""add_dividends_table

Revision ID: c25d03c9157a
Revises: 1c82bb3590ab
Create Date: 2025-10-31 07:11:09.541566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c25d03c9157a'
down_revision: Union[str, Sequence[str], None] = '1c82bb3590ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create dividends table for storing dividend payment history."""
    op.create_table(
        'dividends',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('stock_id', sa.Integer, sa.ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ex_dividend_date', sa.Date, nullable=False, index=True),  # Date stock trades ex-dividend
        sa.Column('payment_date', sa.Date, nullable=True),  # Actual payment date
        sa.Column('record_date', sa.Date, nullable=True),  # Date to be on record
        sa.Column('declaration_date', sa.Date, nullable=True),  # Date dividend was declared
        sa.Column('cash_amount', sa.DECIMAL(12, 4), nullable=False),  # Dividend amount per share
        sa.Column('frequency', sa.Integer, nullable=True),  # 1=annually, 4=quarterly, 12=monthly
        sa.Column('dividend_type', sa.String(50), nullable=True),  # 'CD' = cash dividend, 'SC' = stock dividend, etc.
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.now(), onupdate=sa.func.now()),
        # Prevent duplicate dividends for same stock and ex-dividend date
        sa.UniqueConstraint('stock_id', 'ex_dividend_date', name='uq_stock_ex_dividend_date')
    )

    # Create indexes for common queries
    op.create_index('idx_dividends_payment_date', 'dividends', ['payment_date'])
    op.create_index('idx_dividends_frequency', 'dividends', ['frequency'])


def downgrade() -> None:
    """Drop dividends table."""
    op.drop_index('idx_dividends_frequency', 'dividends')
    op.drop_index('idx_dividends_payment_date', 'dividends')
    op.drop_table('dividends')
