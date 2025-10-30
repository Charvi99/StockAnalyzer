"""add multi-timeframe support

Revision ID: 20251029_mtf
Revises: 3aebabad216a
Create Date: 2025-10-29 10:00:00

This migration adds multi-timeframe support to stock_prices table:
- Adds 'timeframe' column
- Updates primary key to include timeframe
- Preserves existing daily data
- Adds indexes for performance
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251029_mtf'
down_revision: Union[str, Sequence[str], None] = '3aebabad216a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add multi-timeframe support"""

    print("=" * 60)
    print("STARTING MULTI-TIMEFRAME MIGRATION")
    print("=" * 60)

    # Step 1: Add timeframe column (nullable initially)
    print("\n[1/8] Adding timeframe column...")
    op.add_column('stock_prices',
        sa.Column('timeframe', sa.String(10), nullable=True)
    )

    # Step 2: Set existing data to '1d' (daily)
    print("[2/8] Setting existing records to '1d' (daily)...")
    op.execute("UPDATE stock_prices SET timeframe = '1d' WHERE timeframe IS NULL")

    # Step 3: Make timeframe NOT NULL
    print("[3/8] Making timeframe column NOT NULL...")
    op.alter_column('stock_prices', 'timeframe', nullable=False)

    # Step 4: Add CHECK constraint for valid timeframes
    print("[4/8] Adding CHECK constraint for valid timeframes...")
    op.create_check_constraint(
        'check_valid_timeframe',
        'stock_prices',
        "timeframe IN ('1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1mo')"
    )

    # Step 5: Drop old primary key
    print("[5/8] Dropping old primary key...")
    op.drop_constraint('stock_prices_pkey', 'stock_prices', type_='primary')

    # Step 6: Create new composite primary key (stock_id, timeframe, timestamp)
    print("[6/8] Creating new composite primary key (stock_id, timeframe, timestamp)...")
    op.create_primary_key(
        'stock_prices_pkey',
        'stock_prices',
        ['stock_id', 'timeframe', 'timestamp']
    )

    # Step 7: Create indexes for performance
    print("[7/8] Creating performance indexes...")

    # Index for querying by stock + timeframe
    op.create_index(
        'idx_stock_timeframe_timestamp',
        'stock_prices',
        ['stock_id', 'timeframe', 'timestamp']
    )

    # Index for timeframe queries
    op.create_index(
        'idx_timeframe',
        'stock_prices',
        ['timeframe']
    )

    # Step 8: Update TimescaleDB hypertable (if exists)
    print("[8/8] Updating TimescaleDB hypertable...")

    # Check if hypertable exists and recreate with new partitioning
    op.execute("""
        DO $$
        BEGIN
            -- Check if stock_prices is a hypertable
            IF EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'stock_prices'
            ) THEN
                -- Note: We can't easily modify an existing hypertable's partitioning
                -- So we'll just add a note for manual intervention if needed
                RAISE NOTICE 'TimescaleDB hypertable detected. Partitioning not modified.';
                RAISE NOTICE 'Consider recreating hypertable with timeframe partitioning for optimal performance.';
            ELSE
                RAISE NOTICE 'No TimescaleDB hypertable detected. Skipping hypertable configuration.';
            END IF;
        END $$;
    """)

    print("\n" + "=" * 60)
    print("MULTI-TIMEFRAME MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Update your application models to include timeframe")
    print("2. Update data fetching services to specify timeframe")
    print("3. Test queries with different timeframes")
    print("\nExample query:")
    print("  SELECT * FROM stock_prices WHERE stock_id = 1 AND timeframe = '1h' LIMIT 10;")
    print("=" * 60)


def downgrade() -> None:
    """Reverse the multi-timeframe migration"""

    print("=" * 60)
    print("ROLLING BACK MULTI-TIMEFRAME MIGRATION")
    print("=" * 60)

    # Step 1: Drop new constraints/indexes
    print("\n[1/4] Dropping indexes and constraints...")
    op.drop_constraint('check_valid_timeframe', 'stock_prices', type_='check')
    op.drop_index('idx_stock_timeframe_timestamp', table_name='stock_prices')
    op.drop_index('idx_timeframe', table_name='stock_prices')

    # Step 2: Delete non-daily data (if any)
    print("[2/4] Deleting non-daily timeframe data...")
    op.execute("DELETE FROM stock_prices WHERE timeframe != '1d'")

    # Step 3: Restore old primary key
    print("[3/4] Restoring old primary key...")
    op.drop_constraint('stock_prices_pkey', 'stock_prices', type_='primary')
    op.create_primary_key(
        'stock_prices_pkey',
        'stock_prices',
        ['stock_id', 'timestamp']
    )

    # Step 4: Remove timeframe column
    print("[4/4] Removing timeframe column...")
    op.drop_column('stock_prices', 'timeframe')

    print("\n" + "=" * 60)
    print("MULTI-TIMEFRAME MIGRATION ROLLED BACK")
    print("=" * 60)
