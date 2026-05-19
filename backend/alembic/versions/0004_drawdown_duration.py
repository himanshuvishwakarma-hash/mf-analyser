"""add drawdown_duration_months to fund_metrics

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-18
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fund_metrics",
        sa.Column("drawdown_duration_months", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fund_metrics", "drawdown_duration_months")
