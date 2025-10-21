"""initial migration

Revision ID: c45f1698d64d
Revises:
Create Date: 2025-10-21 08:51:22.389877

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'c45f1698d64d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # Create stocks table
    op.create_table(
        'stocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('is_tracked', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stocks_id'), 'stocks', ['id'], unique=False)
    op.create_index(op.f('ix_stocks_symbol'), 'stocks', ['symbol'], unique=True)

    # Create sequence for stock_prices.id
    op.execute("CREATE SEQUENCE IF NOT EXISTS stock_prices_id_seq")

    # Create stock_prices table
    op.create_table(
        'stock_prices',
        sa.Column('id', sa.Integer(), server_default=sa.text("nextval('stock_prices_id_seq'::regclass)"), nullable=True),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('open', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('high', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('low', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('close', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.Column('adjusted_close', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('timestamp', 'stock_id')
    )

    # Convert stock_prices to hypertable
    op.execute("SELECT create_hypertable('stock_prices', 'timestamp', if_not_exists => TRUE)")

    # Create predictions table
    op.create_table(
        'predictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('prediction_date', sa.TIMESTAMP(), nullable=False),
        sa.Column('target_date', sa.TIMESTAMP(), nullable=False),
        sa.Column('predicted_price', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('predicted_change_percent', sa.DECIMAL(precision=8, scale=4), nullable=True),
        sa.Column('confidence_score', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('recommendation', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.CheckConstraint("recommendation IN ('BUY', 'SELL', 'HOLD')", name='check_recommendation'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_predictions_id'), 'predictions', ['id'], unique=False)
    op.create_index('idx_predictions_stock_id', 'predictions', ['stock_id'], unique=False)
    op.create_index('idx_predictions_target_date', 'predictions', ['target_date'], unique=False)

    # Create prediction_performance table
    op.create_table(
        'prediction_performance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prediction_id', sa.Integer(), nullable=False),
        sa.Column('actual_price', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('actual_change_percent', sa.DECIMAL(precision=8, scale=4), nullable=True),
        sa.Column('prediction_error', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('accuracy_score', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('evaluated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prediction_performance_id'), 'prediction_performance', ['id'], unique=False)

    # Create technical_indicators table
    op.create_table(
        'technical_indicators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('indicator_name', sa.String(length=50), nullable=False),
        sa.Column('value', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'timestamp', 'indicator_name')
    )
    op.create_index(op.f('ix_technical_indicators_id'), 'technical_indicators', ['id'], unique=False)
    op.create_index('idx_technical_indicators_stock_timestamp', 'technical_indicators', ['stock_id', 'timestamp'], unique=False)

    # Create sentiment_scores table
    op.create_table(
        'sentiment_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('sentiment_index', sa.DECIMAL(precision=8, scale=4), nullable=True),
        sa.Column('positive_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('negative_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('neutral_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('positive_pct', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('negative_pct', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('neutral_pct', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('total_articles', sa.Integer(), server_default='0', nullable=True),
        sa.Column('trend', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.CheckConstraint("trend IN ('Rise', 'Fall', 'Neutral')", name='check_trend'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sentiment_scores_id'), 'sentiment_scores', ['id'], unique=False)
    op.create_index('idx_sentiment_scores_stock_id', 'sentiment_scores', ['stock_id'], unique=False)
    op.create_index('idx_sentiment_scores_timestamp', 'sentiment_scores', ['timestamp'], unique=False)

    # Create candlestick_patterns table
    op.create_table(
        'candlestick_patterns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('pattern_name', sa.String(length=100), nullable=False),
        sa.Column('pattern_type', sa.String(length=20), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('confidence_score', sa.DECIMAL(precision=5, scale=4), server_default='1.0', nullable=True),
        sa.Column('candle_data', JSONB, nullable=True),
        sa.Column('user_confirmed', sa.Boolean(), nullable=True),
        sa.Column('confirmed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('confirmed_by', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.CheckConstraint("pattern_type IN ('bullish', 'bearish', 'neutral')", name='check_pattern_type'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'pattern_name', 'timestamp')
    )
    op.create_index(op.f('ix_candlestick_patterns_id'), 'candlestick_patterns', ['id'], unique=False)
    op.create_index('idx_candlestick_patterns_stock_id', 'candlestick_patterns', ['stock_id'], unique=False)
    op.create_index('idx_candlestick_patterns_timestamp', 'candlestick_patterns', ['timestamp'], unique=False)
    op.create_index('idx_candlestick_patterns_confirmed', 'candlestick_patterns', ['user_confirmed'], unique=False)

    # Create chart_patterns table
    op.create_table(
        'chart_patterns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('pattern_name', sa.String(length=100), nullable=False),
        sa.Column('pattern_type', sa.String(length=20), nullable=False),
        sa.Column('signal', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.TIMESTAMP(), nullable=False),
        sa.Column('end_date', sa.TIMESTAMP(), nullable=False),
        sa.Column('breakout_price', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('target_price', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('stop_loss', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('confidence_score', sa.DECIMAL(precision=5, scale=4), server_default='0.5', nullable=True),
        sa.Column('key_points', JSONB, nullable=True),
        sa.Column('trendlines', JSONB, nullable=True),
        sa.Column('user_confirmed', sa.Boolean(), nullable=True),
        sa.Column('confirmed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('confirmed_by', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.CheckConstraint("pattern_type IN ('reversal', 'continuation')", name='check_chart_pattern_type'),
        sa.CheckConstraint("signal IN ('bullish', 'bearish', 'neutral')", name='check_chart_signal'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chart_patterns_id'), 'chart_patterns', ['id'], unique=False)
    op.create_index('idx_chart_patterns_stock_id', 'chart_patterns', ['stock_id'], unique=False)
    op.create_index('idx_chart_patterns_end_date', 'chart_patterns', ['end_date'], unique=False)

    # Create view for latest stock prices
    op.execute("""
        CREATE OR REPLACE VIEW latest_stock_prices AS
        SELECT DISTINCT ON (s.id)
            s.id,
            s.symbol,
            s.name,
            sp.timestamp,
            sp.close,
            sp.volume
        FROM stocks s
        LEFT JOIN stock_prices sp ON s.id = sp.stock_id
        ORDER BY s.id, sp.timestamp DESC
    """)

    # Add comments
    op.execute("COMMENT ON TABLE stocks IS 'Stores information about tracked stocks'")
    op.execute("COMMENT ON TABLE stock_prices IS 'Time-series data for stock prices (using TimescaleDB)'")
    op.execute("COMMENT ON TABLE predictions IS 'ML model predictions for stock prices'")
    op.execute("COMMENT ON TABLE prediction_performance IS 'Tracks accuracy of predictions vs actual results'")
    op.execute("COMMENT ON TABLE technical_indicators IS 'Stores calculated technical indicator values'")
    op.execute("COMMENT ON TABLE sentiment_scores IS 'Stores news sentiment analysis results using FinBERT'")
    op.execute("COMMENT ON TABLE candlestick_patterns IS 'Stores detected candlestick patterns with user confirmation for ML training'")

    # Insert sample stocks
    op.execute("""
        INSERT INTO stocks (symbol, name, sector, industry) VALUES
            ('AAPL', 'Apple Inc.', 'Technology', 'Consumer Electronics'),
            ('GOOGL', 'Alphabet Inc.', 'Technology', 'Internet Services'),
            ('MSFT', 'Microsoft Corporation', 'Technology', 'Software'),
            ('TSLA', 'Tesla, Inc.', 'Automotive', 'Electric Vehicles'),
            ('AMZN', 'Amazon.com Inc.', 'Consumer Cyclical', 'E-commerce')
        ON CONFLICT (symbol) DO NOTHING
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop view
    op.execute("DROP VIEW IF EXISTS latest_stock_prices")

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_index('idx_chart_patterns_end_date', table_name='chart_patterns')
    op.drop_index('idx_chart_patterns_stock_id', table_name='chart_patterns')
    op.drop_index(op.f('ix_chart_patterns_id'), table_name='chart_patterns')
    op.drop_table('chart_patterns')

    op.drop_index('idx_candlestick_patterns_confirmed', table_name='candlestick_patterns')
    op.drop_index('idx_candlestick_patterns_timestamp', table_name='candlestick_patterns')
    op.drop_index('idx_candlestick_patterns_stock_id', table_name='candlestick_patterns')
    op.drop_index(op.f('ix_candlestick_patterns_id'), table_name='candlestick_patterns')
    op.drop_table('candlestick_patterns')

    op.drop_index('idx_sentiment_scores_timestamp', table_name='sentiment_scores')
    op.drop_index('idx_sentiment_scores_stock_id', table_name='sentiment_scores')
    op.drop_index(op.f('ix_sentiment_scores_id'), table_name='sentiment_scores')
    op.drop_table('sentiment_scores')

    op.drop_index('idx_technical_indicators_stock_timestamp', table_name='technical_indicators')
    op.drop_index(op.f('ix_technical_indicators_id'), table_name='technical_indicators')
    op.drop_table('technical_indicators')

    op.drop_index(op.f('ix_prediction_performance_id'), table_name='prediction_performance')
    op.drop_table('prediction_performance')

    op.drop_index('idx_predictions_target_date', table_name='predictions')
    op.drop_index('idx_predictions_stock_id', table_name='predictions')
    op.drop_index(op.f('ix_predictions_id'), table_name='predictions')
    op.drop_table('predictions')

    op.drop_table('stock_prices')
    op.execute("DROP SEQUENCE IF EXISTS stock_prices_id_seq")

    op.drop_index(op.f('ix_stocks_symbol'), table_name='stocks')
    op.drop_index(op.f('ix_stocks_id'), table_name='stocks')
    op.drop_table('stocks')
