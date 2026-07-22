"""add_technical_indicators_cache_table

Revision ID: 87e562fc4ffb
Revises: 2987af19b67b
Create Date: 2025-11-13 08:45:04.598599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87e562fc4ffb'
down_revision: Union[str, Sequence[str], None] = '2987af19b67b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add technical_indicators cache table."""
    # The initial migration (c45f1698d64d) created technical_indicators in a
    # "tall" one-row-per-indicator shape; this revision REPLACES it with the
    # "wide" JSONB-cache shape. Drop the tall table first so a from-empty
    # `alembic upgrade head` doesn't die with "relation already exists".
    # Safe: no real DB is mid-chain (production is stamped at head and never
    # re-runs this), so this only affects fresh deployments.
    op.execute("DROP TABLE IF EXISTS technical_indicators CASCADE")
    # Create technical_indicators table for caching pre-computed indicators
    op.create_table(
        'technical_indicators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False, server_default='1d'),

        # Store all 35 indicators as JSONB
        sa.Column('indicators', sa.dialects.postgresql.JSONB(), nullable=False),

        # Store pre-computed recommendation
        sa.Column('recommendation', sa.String(length=10), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('signals', sa.dialects.postgresql.JSONB(), nullable=True),

        # Cache metadata
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('price_hash', sa.String(length=32), nullable=True),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('stock_id', 'timeframe', name='uq_tech_ind_stock_timeframe')
    )

    # Create indexes for fast queries
    op.create_index('idx_tech_ind_stock_timeframe', 'technical_indicators', ['stock_id', 'timeframe'])
    op.create_index('idx_tech_ind_calculated_at', 'technical_indicators', ['calculated_at'])


def downgrade() -> None:
    """Downgrade schema - Remove technical_indicators table."""
    op.drop_index('idx_tech_ind_calculated_at', table_name='technical_indicators')
    op.drop_index('idx_tech_ind_stock_timeframe', table_name='technical_indicators')
    op.drop_table('technical_indicators')
