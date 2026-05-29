"""ORM models for fund universe, NAV history, metrics, and scores.

Phase 1 starter schema. Fields kept lean; expand as data exploration drives changes.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Fund(Base):
    __tablename__ = "funds"

    scheme_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    fund_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    sub_category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    plan_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # Regular / Direct
    expense_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_load: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expense_ratio_as_of: Mapped["date | None"] = mapped_column(Date, nullable=True)
    aum_cr: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    nav_history: Mapped[list["NavHistory"]] = relationship(back_populates="fund", cascade="all, delete-orphan")
    metrics: Mapped["FundMetric | None"] = relationship(back_populates="fund", uselist=False, cascade="all, delete-orphan")
    scores: Mapped[list["FundScore"]] = relationship(back_populates="fund", cascade="all, delete-orphan")


class NavHistory(Base):
    __tablename__ = "nav_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_code: Mapped[int] = mapped_column(ForeignKey("funds.scheme_code", ondelete="CASCADE"), nullable=False)
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float] = mapped_column(Float, nullable=False)

    fund: Mapped[Fund] = relationship(back_populates="nav_history")

    __table_args__ = (
        Index("ix_nav_scheme_date", "scheme_code", "nav_date", unique=True),
    )


class FundMetric(Base):
    __tablename__ = "fund_metrics"

    scheme_code: Mapped[int] = mapped_column(ForeignKey("funds.scheme_code", ondelete="CASCADE"), primary_key=True)
    cagr_1y: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_10y: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    std_dev: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    drawdown_duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recovery_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    momentum_3m: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_6m: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    fund: Mapped[Fund] = relationship(back_populates="metrics")


class FundScore(Base):
    __tablename__ = "fund_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_code: Mapped[int] = mapped_column(ForeignKey("funds.scheme_code", ondelete="CASCADE"), nullable=False, index=True)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_1y_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_3y_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr_5y_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    drawdown_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expense_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    aum_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_overlay: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_load_penalty: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    fund: Mapped[Fund] = relationship(back_populates="scores")


class CategoryBenchmark(Base):
    __tablename__ = "category_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    percentile_25: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentile_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentile_75: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class EtfQuote(Base):
    """Live (intraday) quote for an ETF, sourced from Yahoo Finance."""

    __tablename__ = "etf_quotes"

    scheme_code: Mapped[int] = mapped_column(
        ForeignKey("funds.scheme_code", ondelete="CASCADE"), primary_key=True
    )
    symbol_yahoo: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    prev_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    day_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_traded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True, default="INR")
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, default="yahoo")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

