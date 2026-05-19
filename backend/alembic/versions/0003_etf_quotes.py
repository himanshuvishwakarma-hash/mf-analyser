"""add etf_quotes table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-18
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "etf_quotes",
        sa.Column("scheme_code", sa.Integer(), nullable=False),
        sa.Column("symbol_yahoo", sa.String(length=32), nullable=False),
        sa.Column("last_price", sa.Float(), nullable=True),
        sa.Column("prev_close", sa.Float(), nullable=True),
        sa.Column("day_change_pct", sa.Float(), nullable=True),
        sa.Column("last_traded_at", sa.DateTime(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True, server_default="INR"),
        sa.Column("source", sa.String(length=32), nullable=True, server_default="yahoo"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scheme_code"], ["funds.scheme_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scheme_code"),
    )
    op.create_index("ix_etf_quotes_symbol", "etf_quotes", ["symbol_yahoo"])
    op.create_index("ix_etf_quotes_updated", "etf_quotes", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_etf_quotes_updated", table_name="etf_quotes")
    op.drop_index("ix_etf_quotes_symbol", table_name="etf_quotes")
    op.drop_table("etf_quotes")
