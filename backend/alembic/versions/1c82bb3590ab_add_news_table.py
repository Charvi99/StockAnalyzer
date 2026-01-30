"""add_news_table

Revision ID: 1c82bb3590ab
Revises: 20251030_priority
Create Date: 2025-10-31 07:05:08.130203

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c82bb3590ab'
down_revision: Union[str, Sequence[str], None] = '20251030_priority'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create news table for storing stock news and sentiment."""
    op.create_table(
        'news',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('stock_id', sa.Integer, sa.ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('article_id', sa.String(255), unique=True, nullable=False, index=True),  # Polygon article ID
        sa.Column('publisher', sa.String(255), nullable=True),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('author', sa.String(255), nullable=True),
        sa.Column('published_utc', sa.TIMESTAMP, nullable=False, index=True),
        sa.Column('article_url', sa.Text, nullable=True),
        sa.Column('image_url', sa.Text, nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('keywords', sa.ARRAY(sa.String), nullable=True),
        sa.Column('sentiment', sa.String(20), nullable=True),  # 'positive', 'negative', 'neutral'
        sa.Column('sentiment_score', sa.DECIMAL(5, 4), nullable=True),  # -1.0 to 1.0
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create indexes for common queries
    op.create_index('idx_news_stock_published', 'news', ['stock_id', 'published_utc'])
    op.create_index('idx_news_sentiment', 'news', ['sentiment'])


def downgrade() -> None:
    """Drop news table."""
    op.drop_index('idx_news_sentiment', 'news')
    op.drop_index('idx_news_stock_published', 'news')
    op.drop_table('news')
