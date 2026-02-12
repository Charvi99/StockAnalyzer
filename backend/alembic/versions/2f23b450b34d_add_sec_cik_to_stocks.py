"""add_sec_cik_to_stocks

Revision ID: 2f23b450b34d
Revises: b756c9f7b98b
Create Date: 2026-02-02 14:20:34.716330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f23b450b34d'
down_revision: Union[str, Sequence[str], None] = 'b756c9f7b98b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add SEC CIK columns to stocks table."""
    # Add SEC CIK column
    op.add_column('stocks', sa.Column('sec_cik', sa.String(length=20), nullable=True))

    # Add official name column
    op.add_column('stocks', sa.Column('official_name', sa.String(length=500), nullable=True))

    # Create index on sec_cik for faster lookups
    op.create_index('ix_stocks_sec_cik', 'stocks', ['sec_cik'], unique=True)


def downgrade() -> None:
    """Downgrade schema - Remove SEC CIK columns."""
    op.drop_index('ix_stocks_sec_cik', table_name='stocks')
    op.drop_column('stocks', 'official_name')
    op.drop_column('stocks', 'sec_cik')
