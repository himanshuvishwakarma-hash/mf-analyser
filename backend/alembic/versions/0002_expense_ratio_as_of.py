"""add expense_ratio_as_of to funds

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-17
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "funds",
        sa.Column("expense_ratio_as_of", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("funds", "expense_ratio_as_of")
