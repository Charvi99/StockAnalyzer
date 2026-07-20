"""convert all timestamp columns to TIMESTAMPTZ (timezone-aware, UTC)

Closes the audit's B3/R6/F2/S1 family: the app mixed tz-aware and tz-naive
datetimes against naive TIMESTAMP columns (e.g. analysis_completeness compared
naive datetime.utcnow() against last_* columns that could hold aware values ->
TypeError, crashing the re-analysis auto-trigger). This makes every timestamp
column TIMESTAMPTZ and lets the code move to one convention: datetime.now(timezone.utc).

Existing values are interpreted as UTC and are NOT shifted (the USING clause
pins interpretation to UTC regardless of the session timezone).

NOTE: stock_prices is a TimescaleDB hypertable on `timestamp`; TIMESTAMPTZ is
Timescale's recommended time-column type. Test on a DB copy before applying to
production (pg_dump -> restore -> alembic upgrade head). Reversible via downgrade.

Revision ID: 20260720_tz
Revises: c421e271c733
"""
from alembic import op
import sqlalchemy as sa


revision = '20260720_tz'
down_revision = 'c421e271c733'
branch_labels = None
depends_on = None


# Every naive TIMESTAMP column -> TIMESTAMPTZ. (table, column) pairs, enumerated
# from app/models/*.py. stock_prices.timestamp is the hypertable time column and
# part of the composite PK (stock_id, timeframe, timestamp) — type widening
# TIMESTAMP -> TIMESTAMPTZ is allowed on a PK column.
_COLUMNS = [
    # stocks
    ("stocks", "priority_updated_at"),
    ("stocks", "last_pattern_date"),
    ("stocks", "last_fetch_at"),
    ("stocks", "next_fetch_at"),
    ("stocks", "last_chart_pattern_detection"),
    ("stocks", "last_candlestick_detection"),
    ("stocks", "last_sentiment_analysis"),
    ("stocks", "last_technical_analysis"),
    ("stocks", "last_ml_prediction"),
    ("stocks", "last_comprehensive_analysis"),
    ("stocks", "created_at"),
    ("stocks", "updated_at"),
    # stock_prices (hypertable)
    ("stock_prices", "timestamp"),
    # predictions
    ("predictions", "prediction_date"),
    ("predictions", "target_date"),
    ("predictions", "created_at"),
    # prediction_performance
    ("prediction_performance", "evaluated_at"),
    # technical_indicators
    ("technical_indicators", "calculated_at"),
    # sentiment_scores
    ("sentiment_scores", "timestamp"),
    ("sentiment_scores", "created_at"),
    # candlestick_patterns
    ("candlestick_patterns", "timestamp"),
    ("candlestick_patterns", "confirmed_at"),
    ("candlestick_patterns", "created_at"),
    # chart_patterns
    ("chart_patterns", "start_date"),
    ("chart_patterns", "end_date"),
    ("chart_patterns", "confirmed_at"),
    ("chart_patterns", "created_at"),
    # news
    ("news", "published_utc"),
    ("news", "created_at"),
    ("news", "updated_at"),
    # short_interest
    ("short_interest", "created_at"),
    ("short_interest", "updated_at"),
    # dividends
    ("dividends", "created_at"),
    ("dividends", "updated_at"),
    # stock_splits
    ("stock_splits", "created_at"),
    ("stock_splits", "updated_at"),
    # insider_trades / alternative_data are migration-only tables (no ORM model);
    # only their created_at is TIMESTAMP (trade_date/filing_date/date are DATE).
    ("insider_trades", "created_at"),
    ("alternative_data", "created_at"),
]


def upgrade():
    # `col AT TIME ZONE 'UTC'` interprets the existing naive value as UTC and
    # returns a timestamptz, so wall-times do not shift regardless of session tz.
    for table, col in _COLUMNS:
        op.alter_column(
            table,
            col,
            type_=sa.TIMESTAMP(timezone=True),
            postgresql_using=f"{col} AT TIME ZONE 'UTC'",
        )


def downgrade():
    # Strip tz back to naive (UTC wall-time); timestamptz::timestamp yields naive.
    for table, col in reversed(_COLUMNS):
        op.alter_column(
            table,
            col,
            type_=sa.TIMESTAMP(timezone=False),
            postgresql_using=f"{col}::timestamp",
        )
