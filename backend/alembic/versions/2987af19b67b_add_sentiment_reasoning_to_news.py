"""add_sentiment_reasoning_to_news

Revision ID: 2987af19b67b
Revises: 20251106_092731
Create Date: 2025-11-07 15:39:36.815548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2987af19b67b'
down_revision: Union[str, Sequence[str], None] = '20251106_092731'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add sentiment_reasoning and ticker columns to news table."""
    # Add sentiment_reasoning column to store Polygon's sentiment explanation
    op.add_column('news', sa.Column('sentiment_reasoning', sa.Text(), nullable=True))

    # Add ticker column to handle multi-ticker articles (news can mention multiple stocks)
    op.add_column('news', sa.Column('ticker', sa.String(length=10), nullable=True))

    # Add index on ticker for faster lookups
    op.create_index(op.f('ix_news_ticker'), 'news', ['ticker'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove sentiment_reasoning and ticker columns."""
    # Drop index first
    op.drop_index(op.f('ix_news_ticker'), table_name='news')

    # Drop columns
    op.drop_column('news', 'ticker')
    op.drop_column('news', 'sentiment_reasoning')
