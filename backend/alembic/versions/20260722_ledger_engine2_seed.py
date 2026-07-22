"""seed engine_2 paper account (Phase 1.10)

Revision ID: 20260722_ledger_engine2_seed
Revises: 20260722_ledger_reasoning
Create Date: 2026-07-22 00:00:00.000000

Idempotently inserts the ``engine_2`` virtual account ($100k starting cash) so
engine_2 can be enabled alongside engine_1 for the A/B comparison (audit decision
D35). ON CONFLICT (engine) DO NOTHING so re-running is safe.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260722_ledger_engine2_seed'
down_revision = '20260722_ledger_reasoning'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "INSERT INTO paper_accounts (engine, starting_cash, cash) "
        "VALUES ('engine_2', 100000.00, 100000.00) "
        "ON CONFLICT (engine) DO NOTHING"
    ))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM paper_accounts WHERE engine = 'engine_2'"))
