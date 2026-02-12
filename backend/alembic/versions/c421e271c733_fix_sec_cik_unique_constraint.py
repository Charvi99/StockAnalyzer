"""fix_sec_cik_unique_constraint

Revision ID: c421e271c733
Revises: 2f23b450b34d
Create Date: 2026-02-02 14:44:45.593872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c421e271c733'
down_revision: Union[str, Sequence[str], None] = '2f23b450b34d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Remove unique constraint from sec_cik."""
    # Drop the unique index on sec_cik
    # (Different stock classes can share the same CIK, e.g., FOX and FOXA)
    op.drop_index('ix_stocks_sec_cik', table_name='stocks')

    # Create a non-unique index instead for faster lookups
    op.create_index('ix_stocks_sec_cik_nonunique', 'stocks', ['sec_cik'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Restore unique constraint."""
    op.drop_index('ix_stocks_sec_cik_nonunique', table_name='stocks')
    op.create_index('ix_stocks_sec_cik', 'stocks', ['sec_cik'], unique=True)
