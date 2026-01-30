"""add_analysis_tracking

Revision ID: 20251106_092731
Revises: e29f036ebfa7
Create Date: 2025-11-06 09:27:31.000000

This migration adds analysis tracking fields to the stocks table to enable:
- Detection of missing/incomplete analysis data
- Tracking when each analysis component was last executed
- Avoiding redundant analysis of stocks that already have recent data
- Smart triggering of background analysis only for stocks that need it
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251106_092731'
down_revision = 'e29f036ebfa7'
branch_labels = None
depends_on = None


def upgrade():
    """Add analysis tracking fields to stocks table"""

    # Add timestamp columns for tracking when each analysis component was last executed
    op.add_column('stocks', sa.Column('last_chart_pattern_detection', sa.TIMESTAMP(), nullable=True))
    op.add_column('stocks', sa.Column('last_candlestick_detection', sa.TIMESTAMP(), nullable=True))
    op.add_column('stocks', sa.Column('last_sentiment_analysis', sa.TIMESTAMP(), nullable=True))
    op.add_column('stocks', sa.Column('last_technical_analysis', sa.TIMESTAMP(), nullable=True))
    op.add_column('stocks', sa.Column('last_ml_prediction', sa.TIMESTAMP(), nullable=True))

    # Add overall analysis status fields
    op.add_column('stocks', sa.Column('analysis_complete', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('stocks', sa.Column('analysis_score', sa.DECIMAL(precision=3, scale=2), server_default='0.00', nullable=False))
    op.add_column('stocks', sa.Column('last_comprehensive_analysis', sa.TIMESTAMP(), nullable=True))

    # Create indexes on timestamp columns for efficient querying
    # These indexes enable fast queries like "find all stocks with stale sentiment"
    op.create_index('ix_stocks_last_chart_pattern_detection', 'stocks', ['last_chart_pattern_detection'])
    op.create_index('ix_stocks_last_candlestick_detection', 'stocks', ['last_candlestick_detection'])
    op.create_index('ix_stocks_last_sentiment_analysis', 'stocks', ['last_sentiment_analysis'])
    op.create_index('ix_stocks_last_technical_analysis', 'stocks', ['last_technical_analysis'])
    op.create_index('ix_stocks_last_ml_prediction', 'stocks', ['last_ml_prediction'])
    op.create_index('ix_stocks_last_comprehensive_analysis', 'stocks', ['last_comprehensive_analysis'])

    # Create composite index for common query pattern: tracked stocks with incomplete analysis
    op.create_index('ix_stocks_tracked_incomplete', 'stocks', ['is_tracked', 'analysis_complete'])

    # Create index for finding stocks needing analysis (low score)
    op.create_index('ix_stocks_analysis_score', 'stocks', ['analysis_score'])


def downgrade():
    """Remove analysis tracking fields from stocks table"""

    # Drop indexes first
    op.drop_index('ix_stocks_analysis_score', table_name='stocks')
    op.drop_index('ix_stocks_tracked_incomplete', table_name='stocks')
    op.drop_index('ix_stocks_last_comprehensive_analysis', table_name='stocks')
    op.drop_index('ix_stocks_last_ml_prediction', table_name='stocks')
    op.drop_index('ix_stocks_last_technical_analysis', table_name='stocks')
    op.drop_index('ix_stocks_last_sentiment_analysis', table_name='stocks')
    op.drop_index('ix_stocks_last_candlestick_detection', table_name='stocks')
    op.drop_index('ix_stocks_last_chart_pattern_detection', table_name='stocks')

    # Drop columns
    op.drop_column('stocks', 'last_comprehensive_analysis')
    op.drop_column('stocks', 'analysis_score')
    op.drop_column('stocks', 'analysis_complete')
    op.drop_column('stocks', 'last_ml_prediction')
    op.drop_column('stocks', 'last_technical_analysis')
    op.drop_column('stocks', 'last_sentiment_analysis')
    op.drop_column('stocks', 'last_candlestick_detection')
    op.drop_column('stocks', 'last_chart_pattern_detection')
