"""add indexes on previously-unindexed foreign keys (audit S2/D21)

Closes the S2/D21 finding: five foreign-key columns were unindexed, so every
join / filter-by-stock / cascade-delete on predictions, sentiment_scores,
candlestick_patterns, chart_patterns (stock_id) and prediction_performance
(prediction_id) did a sequential scan. At 200 tracked tickers with thousands
of rows each, that is the dominant dashboard/analysis cost.

Index names follow SQLAlchemy's default convention (ix_<table>_<column>) so the
in-DB indexes match the `index=True` flags now set on the model columns — a fresh
`Base.metadata.create_all()` and this migration produce identical schema.

Reversible (downgrade drops all five). Index-only: no column type or data change.

Revision ID: 20260721_fk
Revises: 20260720_tz
Create Date: 2026-07-21
"""
from alembic import op


revision = '20260721_fk'
down_revision = '20260720_tz'
branch_labels = None
depends_on = None


# (index_name, table, column)
_INDEXES = [
    ('ix_predictions_stock_id', 'predictions', 'stock_id'),
    ('ix_prediction_performance_prediction_id', 'prediction_performance', 'prediction_id'),
    ('ix_sentiment_scores_stock_id', 'sentiment_scores', 'stock_id'),
    ('ix_candlestick_patterns_stock_id', 'candlestick_patterns', 'stock_id'),
    ('ix_chart_patterns_stock_id', 'chart_patterns', 'stock_id'),
]


def upgrade():
    for name, table, col in _INDEXES:
        op.create_index(name, table, [col])


def downgrade():
    for name, table, _col in _INDEXES:
        op.drop_index(name, table_name=table)
