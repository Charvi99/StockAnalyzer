"""add multi-timeframe fields to chart_patterns

Revision ID: 20251029_mtf_fields
Revises: 20251029_mtf
Create Date: 2025-10-29 22:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '20251029_mtf_fields'
down_revision = '20251029_mtf'
branch_labels = None
depends_on = None


def upgrade():
    # Add multi-timeframe analysis fields to chart_patterns table
    op.add_column('chart_patterns', sa.Column('primary_timeframe', sa.String(10), server_default='1d'))
    op.add_column('chart_patterns', sa.Column('detected_on_timeframes', JSONB, nullable=True))
    op.add_column('chart_patterns', sa.Column('confirmation_level', sa.Integer, server_default='1'))
    op.add_column('chart_patterns', sa.Column('base_confidence', sa.DECIMAL(5, 4), nullable=True))
    op.add_column('chart_patterns', sa.Column('alignment_score', sa.DECIMAL(5, 4), nullable=True))


def downgrade():
    # Remove multi-timeframe fields
    op.drop_column('chart_patterns', 'alignment_score')
    op.drop_column('chart_patterns', 'base_confidence')
    op.drop_column('chart_patterns', 'confirmation_level')
    op.drop_column('chart_patterns', 'detected_on_timeframes')
    op.drop_column('chart_patterns', 'primary_timeframe')
