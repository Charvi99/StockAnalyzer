"""add priority system to stocks

Revision ID: 20251030_priority
Revises: 20251029_mtf_fields
Create Date: 2025-10-30 14:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision = '20251030_priority'
down_revision = '20251029_mtf_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add priority fields to stocks table
    op.add_column('stocks', sa.Column('priority', sa.String(10), server_default='medium', nullable=False))
    op.add_column('stocks', sa.Column('priority_score', sa.DECIMAL(8, 2), server_default='50.0', nullable=False))
    op.add_column('stocks', sa.Column('priority_updated_at', TIMESTAMP, nullable=True))

    # Add check constraint for priority values
    op.create_check_constraint(
        'check_priority_value',
        'stocks',
        "priority IN ('high', 'medium', 'low')"
    )

    # Add index on priority for faster queries
    op.create_index('idx_stocks_priority', 'stocks', ['priority', 'is_tracked'])

    # Add volume and volatility tracking fields (for priority calculation)
    op.add_column('stocks', sa.Column('avg_volume_30d', sa.BigInteger, nullable=True))
    op.add_column('stocks', sa.Column('avg_price_30d', sa.DECIMAL(12, 4), nullable=True))
    op.add_column('stocks', sa.Column('volatility_30d', sa.DECIMAL(8, 4), nullable=True))  # Standard deviation
    op.add_column('stocks', sa.Column('pattern_count_30d', sa.Integer, server_default='0', nullable=False))
    op.add_column('stocks', sa.Column('last_pattern_date', TIMESTAMP, nullable=True))


def downgrade():
    # Remove indexes
    op.drop_index('idx_stocks_priority', 'stocks')

    # Remove check constraint
    op.drop_constraint('check_priority_value', 'stocks', type_='check')

    # Remove tracking fields
    op.drop_column('stocks', 'last_pattern_date')
    op.drop_column('stocks', 'pattern_count_30d')
    op.drop_column('stocks', 'volatility_30d')
    op.drop_column('stocks', 'avg_price_30d')
    op.drop_column('stocks', 'avg_volume_30d')

    # Remove priority fields
    op.drop_column('stocks', 'priority_updated_at')
    op.drop_column('stocks', 'priority_score')
    op.drop_column('stocks', 'priority')
