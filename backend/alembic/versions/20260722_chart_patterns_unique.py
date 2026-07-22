"""chart_patterns unique constraint (audit H3)

Revision ID: 20260722_cpuniq
Revises: 20260721_fk
Create Date: 2026-07-22 00:00:00.000000

Adds UNIQUE(stock_id, pattern_name, end_date) to chart_patterns. The pattern
detection upsert was check-then-insert (H4) with no uniqueness guard, so under
Celery ``acks_late`` redelivery it could write duplicate (stock_id, pattern_name,
end_date) rows. This constraint makes the upsert idempotent (ON CONFLICT DO
NOTHING) and prevents any future dups.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20260722_cpuniq'
down_revision = '20260721_fk'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the unique constraint, removing any pre-existing dups first."""
    # Keep the highest-id row per (stock_id, pattern_name, end_date) tuple so the
    # constraint can be created. No-op on clean data (0 dups at migration time).
    op.execute(
        "DELETE FROM chart_patterns a USING chart_patterns b "
        "WHERE a.id < b.id "
        "AND a.stock_id = b.stock_id "
        "AND a.pattern_name = b.pattern_name "
        "AND a.end_date = b.end_date"
    )
    op.create_unique_constraint(
        'uq_chart_patterns_stock_name_end',
        'chart_patterns',
        ['stock_id', 'pattern_name', 'end_date'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_chart_patterns_stock_name_end',
        'chart_patterns',
        type_='unique',
    )
