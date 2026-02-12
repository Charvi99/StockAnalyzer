"""add_alternative_data_table

Revision ID: b756c9f7b98b
Revises: 7c8no8sb3gqi
Create Date: 2026-02-02 13:34:45.757590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b756c9f7b98b'
down_revision: Union[str, Sequence[str], None] = '7c8no8sb3gqi'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add alternative_data table."""
    op.create_table(
        'alternative_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DATE(), nullable=False),
        sa.Column('data_source', sa.String(length=50), nullable=False),

        # WallStreetBets columns
        sa.Column('mention_count', sa.Integer(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('activity_score', sa.Float(), nullable=True),
        sa.Column('discussion_rank', sa.Integer(), nullable=True),
        sa.Column('positivity_ratio', sa.Float(), nullable=True),

        # Off-Exchange Short Volume columns
        sa.Column('off_exchange_volume', sa.BigInteger(), nullable=True),
        sa.Column('total_volume', sa.BigInteger(), nullable=True),
        sa.Column('short_interest', sa.Float(), nullable=True),

        # Raw JSON data from API
        sa.Column('raw_data', sa.JSON(), nullable=True),

        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),

        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unique constraint on stock_id + date + data_source
    op.create_index(
        'ix_alternative_data_stock_date_source',
        'alternative_data',
        ['stock_id', 'date', 'data_source'],
        unique=True
    )

    # Create indexes for common queries
    op.create_index(
        'ix_alternative_data_stock_id',
        'alternative_data',
        ['stock_id'],
        unique=False
    )
    op.create_index(
        'ix_alternative_data_date',
        'alternative_data',
        ['date'],
        unique=False
    )
    op.create_index(
        'ix_alternative_data_data_source',
        'alternative_data',
        ['data_source'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema - Remove alternative_data table."""
    op.drop_index('ix_alternative_data_data_source', table_name='alternative_data')
    op.drop_index('ix_alternative_data_date', table_name='alternative_data')
    op.drop_index('ix_alternative_data_stock_id', table_name='alternative_data')
    op.drop_index('ix_alternative_data_stock_date_source', table_name='alternative_data')
    op.drop_table('alternative_data')
