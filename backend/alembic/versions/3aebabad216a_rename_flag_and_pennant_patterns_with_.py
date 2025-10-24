"""rename_flag_and_pennant_patterns_with_signal

Revision ID: 3aebabad216a
Revises: c45f1698d64d
Create Date: 2025-10-23 10:02:34.989618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3aebabad216a'
down_revision: Union[str, Sequence[str], None] = 'c45f1698d64d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename Flag and Pennant patterns to include signal (Bullish/Bearish)."""
    # Update Flag patterns
    op.execute("""
        UPDATE chart_patterns
        SET pattern_name = 'Bullish Flag'
        WHERE pattern_name = 'Flag' AND signal = 'bullish'
    """)

    op.execute("""
        UPDATE chart_patterns
        SET pattern_name = 'Bearish Flag'
        WHERE pattern_name = 'Flag' AND signal = 'bearish'
    """)

    # Update Pennant patterns
    op.execute("""
        UPDATE chart_patterns
        SET pattern_name = 'Bullish Pennant'
        WHERE pattern_name = 'Pennant' AND signal = 'bullish'
    """)

    op.execute("""
        UPDATE chart_patterns
        SET pattern_name = 'Bearish Pennant'
        WHERE pattern_name = 'Pennant' AND signal = 'bearish'
    """)


def downgrade() -> None:
    """Revert Flag and Pennant pattern names back to original."""
    # Revert Bullish Flag
    op.execute("""
        UPDATE chart_patterns
        SET pattern_name = 'Flag'
        WHERE pattern_name = 'Bullish Flag'
    """)

    # Revert Bearish Flag
    op.execute("""
        UPDATE chart_patterns
        SET pattern_name = 'Flag'
        WHERE pattern_name = 'Bearish Flag'
    """)

    # Revert Bullish Pennant
    op.execute("""
        UPDATE chart_patterns
        SET pattern_name = 'Pennant'
        WHERE pattern_name = 'Bullish Pennant'
    """)

    # Revert Bearish Pennant
    op.execute("""
        UPDATE chart_patterns
        SET pattern_name = 'Pennant'
        WHERE pattern_name = 'Bearish Pennant'
    """)

