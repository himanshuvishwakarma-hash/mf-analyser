"""initial schema — funds, nav_history, fund_metrics, fund_scores, category_benchmarks

Revision ID: 0001
Revises:
Create Date: 2026-05-14
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "funds",
        sa.Column("scheme_code", sa.Integer(), primary_key=True),
        sa.Column("fund_name", sa.String(255), nullable=False),
        sa.Column("amc", sa.String(255), nullable=True),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("sub_category", sa.String(128), nullable=True),
        sa.Column("plan_type", sa.String(32), nullable=True),
        sa.Column("expense_ratio", sa.Float(), nullable=True),
        sa.Column("exit_load", sa.String(255), nullable=True),
        sa.Column("aum_cr", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_funds_category", "funds", ["category"])
    op.create_index("ix_funds_sub_category", "funds", ["sub_category"])

    op.create_table(
        "nav_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scheme_code", sa.Integer(), sa.ForeignKey("funds.scheme_code", ondelete="CASCADE"), nullable=False),
        sa.Column("nav_date", sa.Date(), nullable=False),
        sa.Column("nav", sa.Float(), nullable=False),
    )
    op.create_index("ix_nav_scheme_date", "nav_history", ["scheme_code", "nav_date"], unique=True)

    op.create_table(
        "fund_metrics",
        sa.Column("scheme_code", sa.Integer(), sa.ForeignKey("funds.scheme_code", ondelete="CASCADE"), primary_key=True),
        sa.Column("cagr_1y", sa.Float(), nullable=True),
        sa.Column("cagr_3y", sa.Float(), nullable=True),
        sa.Column("cagr_5y", sa.Float(), nullable=True),
        sa.Column("cagr_10y", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("std_dev", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("recovery_months", sa.Integer(), nullable=True),
        sa.Column("momentum_3m", sa.Float(), nullable=True),
        sa.Column("momentum_6m", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "fund_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scheme_code", sa.Integer(), sa.ForeignKey("funds.scheme_code", ondelete="CASCADE"), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("sharpe_score", sa.Float(), nullable=True),
        sa.Column("cagr_1y_score", sa.Float(), nullable=True),
        sa.Column("cagr_3y_score", sa.Float(), nullable=True),
        sa.Column("cagr_5y_score", sa.Float(), nullable=True),
        sa.Column("consistency_score", sa.Float(), nullable=True),
        sa.Column("drawdown_score", sa.Float(), nullable=True),
        sa.Column("expense_score", sa.Float(), nullable=True),
        sa.Column("momentum_score", sa.Float(), nullable=True),
        sa.Column("aum_score", sa.Float(), nullable=True),
        sa.Column("momentum_overlay", sa.Float(), nullable=True),
        sa.Column("exit_load_penalty", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_fund_scores_scheme_code", "fund_scores", ["scheme_code"])
    op.create_index("ix_fund_scores_computed_at", "fund_scores", ["computed_at"])

    op.create_table(
        "category_benchmarks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("percentile_25", sa.Float(), nullable=True),
        sa.Column("percentile_50", sa.Float(), nullable=True),
        sa.Column("percentile_75", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_category_benchmarks_category", "category_benchmarks", ["category"])
    op.create_index("ix_category_benchmarks_metric_name", "category_benchmarks", ["metric_name"])


def downgrade() -> None:
    op.drop_table("category_benchmarks")
    op.drop_table("fund_scores")
    op.drop_table("fund_metrics")
    op.drop_table("nav_history")
    op.drop_table("funds")
