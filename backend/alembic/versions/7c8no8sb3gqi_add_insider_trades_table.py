"""add_insider_trades_table

Revision ID: 7c8no8sb3gqi
Revises: 87e562fc4ffb
Create Date: 2025-02-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '7c8no8sb3gqi'
down_revision: Union[str, Sequence[str], None] = '87e562fc4ffb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add insider_trades table."""

    # Create insider_trades table for storing corporate insider trading data
    op.create_table(
        'insider_trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),

        # Insider information
        sa.Column('insider_name', sa.String(length=255), nullable=False),
        sa.Column('insider_title', sa.String(length=100), nullable=True),

        # Transaction details
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('shares', sa.BigInteger(), nullable=False),
        sa.Column('price', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('total_value', sa.DECIMAL(precision=18, scale=2), nullable=True),

        # Dates
        sa.Column('trade_date', sa.DATE(), nullable=False),
        sa.Column('filing_date', sa.DATE(), nullable=True),

        # Additional data
        sa.Column('is_congressional', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('raw_data', JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),

        # Constraints
        sa.CheckConstraint("transaction_type IN ('BUY', 'SELL', 'OPTION_EXERCISE', 'OTHER')", name='check_insider_transaction_type'),
        sa.CheckConstraint("shares > 0", name='check_insider_shares_positive'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient queries
    op.create_index('ix_insider_trades_id', 'insider_trades', ['id'], unique=False)
    op.create_index('idx_insider_trades_stock_id', 'insider_trades', ['stock_id'], unique=False)
    op.create_index('idx_insider_trades_trade_date', 'insider_trades', ['trade_date'], unique=False)
    op.create_index('idx_insider_trades_transaction_type', 'insider_trades', ['transaction_type'], unique=False)
    op.create_index('idx_insider_trades_is_congressional', 'insider_trades', ['is_congressional'], unique=False)

    # Create composite index for common queries (stock + date range)
    op.create_index('idx_insider_trades_stock_date', 'insider_trades', ['stock_id', 'trade_date'], unique=False)

    # Add table comment
    op.execute("COMMENT ON TABLE insider_trades IS 'Stores corporate insider trading data from Quiver Quant API'")


def downgrade() -> None:
    """Downgrade schema - Remove insider_trades table."""

    # Drop indexes
    op.drop_index('idx_insider_trades_stock_date', table_name='insider_trades')
    op.drop_index('idx_insider_trades_is_congressional', table_name='insider_trades')
    op.drop_index('idx_insider_trades_transaction_type', table_name='insider_trades')
    op.drop_index('idx_insider_trades_trade_date', table_name='insider_trades')
    op.drop_index('idx_insider_trades_stock_id', table_name='insider_trades')
    op.drop_index('ix_insider_trades_id', table_name='insider_trades')

    # Drop table
    op.drop_table('insider_trades')
