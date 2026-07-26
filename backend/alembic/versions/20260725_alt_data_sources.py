"""alt_data_sources

Revision ID: 20260725_alt_data_sources
Revises: 20260724_ga_runs
Create Date: 2026-07-25

Adds clean tables for the alternative-data edge probes:
  insider_trades   - SEC Form-4 insider transactions (EDGAR source)
  sec_disclosures  - SEC 8-K categorized material-event disclosures
  short_volume     - FINRA daily short-sale volume (short_interest already exists)
  risk_factors     - SEC standardized 10-K risk-factor disclosures
  stock_floats     - free-float per stock (normalization input)

NOTE: the older `insider_trades` / `alternative_data` migration drafts
(7c8no8sb3gqi, b756c9f7b98b) sit on a dead branch (down_revision
87e562fc4ffb) and were never applied; this migration is independent and
does not depend on them. 13-F (institutional_holdings) and fundamentals
are intentionally omitted here (13-F endpoint is global-only/impractical;
financials are 403 on the current plan) — add later if scoped.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision: str = "20260725_alt_data_sources"
down_revision: Union[str, Sequence[str], None] = "20260724_ga_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- insider_trades (Form-4, EDGAR source) ----
    op.create_table(
        "insider_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("insider_name", sa.String(255), nullable=False),
        sa.Column("insider_title", sa.String(100), nullable=True),
        sa.Column("owner_cik", sa.String(20), nullable=True),
        sa.Column("is_director", sa.Boolean(), nullable=True),
        sa.Column("is_officer", sa.Boolean(), nullable=True),
        sa.Column("is_ten_percent_owner", sa.Boolean(), nullable=True),
        # BUY/SELL/OPTION_EXERCISE/OTHER (matches sec_edgar_fetcher normalization)
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("transaction_code", sa.String(4), nullable=True),  # P/S/A/...
        sa.Column("shares", sa.Numeric(20, 0), nullable=True),
        sa.Column("price", sa.Numeric(12, 4), nullable=True),
        sa.Column("total_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=True),  # PUBLIC date (causality key)
        sa.Column("accession_number", sa.String(40), nullable=True),
        sa.Column("is_congressional", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("raw_data", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stock_id", "accession_number", "owner_cik", "trade_date", "transaction_code",
            name="uq_insider_trades_dedup",
        ),
    )
    op.create_index("ix_insider_trades_stock_id", "insider_trades", ["stock_id"])
    op.create_index("ix_insider_trades_filing_date", "insider_trades", ["filing_date"])
    op.create_index("ix_insider_trades_stock_filing", "insider_trades", ["stock_id", "filing_date"])

    # ---- sec_disclosures (8-K categorized) ----
    op.create_table(
        "sec_disclosures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),  # PUBLIC date
        sa.Column("accession_number", sa.String(40), nullable=False),
        sa.Column("cik", sa.String(20), nullable=True),
        sa.Column("tickers", ARRAY(sa.String()), nullable=True),
        sa.Column("primary_category", sa.String(120), nullable=True),
        sa.Column("secondary_category", sa.String(120), nullable=True),
        sa.Column("tertiary_category", sa.String(120), nullable=True),
        sa.Column("supporting_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stock_id", "accession_number", "primary_category", "secondary_category", "tertiary_category",
            name="uq_sec_disclosures_dedup",
        ),
    )
    op.create_index("ix_sec_disclosures_stock_id", "sec_disclosures", ["stock_id"])
    op.create_index("ix_sec_disclosures_filing_date", "sec_disclosures", ["filing_date"])
    op.create_index("ix_sec_disclosures_stock_filing", "sec_disclosures", ["stock_id", "filing_date"])

    # ---- short_volume (FINRA daily) ----
    op.create_table(
        "short_volume",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),  # PUBLIC date
        sa.Column("total_volume", sa.Numeric(20, 0), nullable=True),
        sa.Column("short_volume", sa.Numeric(20, 0), nullable=True),
        sa.Column("short_volume_ratio", sa.Numeric(6, 2), nullable=True),
        sa.Column("exempt_volume", sa.Numeric(20, 0), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "date", name="uq_short_volume_stock_date"),
    )
    op.create_index("ix_short_volume_stock_id", "short_volume", ["stock_id"])
    op.create_index("ix_short_volume_date", "short_volume", ["date"])
    op.create_index("ix_short_volume_stock_date", "short_volume", ["stock_id", "date"])

    # ---- risk_factors (10-K standardized) ----
    op.create_table(
        "risk_factors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),  # PUBLIC date
        sa.Column("cik", sa.String(20), nullable=True),
        sa.Column("accession_number", sa.String(40), nullable=True),
        sa.Column("primary_category", sa.String(120), nullable=True),
        sa.Column("secondary_category", sa.String(120), nullable=True),
        sa.Column("tertiary_category", sa.String(120), nullable=True),
        sa.Column("supporting_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stock_id", "filing_date", "primary_category", "secondary_category", "tertiary_category",
            name="uq_risk_factors_dedup",
        ),
    )
    op.create_index("ix_risk_factors_stock_id", "risk_factors", ["stock_id"])
    op.create_index("ix_risk_factors_filing_date", "risk_factors", ["filing_date"])
    op.create_index("ix_risk_factors_stock_filing", "risk_factors", ["stock_id", "filing_date"])

    # ---- stock_floats (normalization input) ----
    op.create_table(
        "stock_floats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("free_float", sa.Numeric(20, 0), nullable=True),
        sa.Column("free_float_percent", sa.Numeric(6, 2), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "effective_date", name="uq_stock_floats_stock_date"),
    )
    op.create_index("ix_stock_floats_stock_id", "stock_floats", ["stock_id"])
    op.create_index("ix_stock_floats_stock_eff", "stock_floats", ["stock_id", "effective_date"])


def downgrade() -> None:
    for tbl in ("stock_floats", "risk_factors", "short_volume", "sec_disclosures", "insider_trades"):
        op.drop_table(tbl)
