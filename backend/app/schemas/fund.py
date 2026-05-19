"""Pydantic schemas for fund-related responses."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class FundSummary(BaseModel):
    scheme_code: int
    fund_name: str
    amc: str | None = None
    category: str | None = None
    sub_category: str | None = None
    expense_ratio: float | None = None
    aum_cr: float | None = None
    cagr_1y: float | None = None
    cagr_3y: float | None = None
    cagr_5y: float | None = None
    composite_score: float | None = None


class FundListResponse(BaseModel):
    items: list[FundSummary]
    total: int
    page: int = 1
    limit: int = 20


class FundMetrics(BaseModel):
    cagr_1y: float | None = None
    cagr_3y: float | None = None
    cagr_5y: float | None = None
    cagr_10y: float | None = None
    sharpe_ratio: float | None = None
    std_dev: float | None = None
    max_drawdown: float | None = None
    drawdown_duration_months: int | None = None
    recovery_months: int | None = None
    momentum_3m: float | None = None
    momentum_6m: float | None = None


class LiveQuote(BaseModel):
    """Intraday quote for an ETF (Yahoo Finance source)."""

    symbol: str
    last_price: float | None = None
    prev_close: float | None = None
    day_change_pct: float | None = None
    last_traded_at: datetime | None = None
    source: str = "yahoo"
    stale: bool = False


class FundDetail(BaseModel):
    scheme_code: int
    fund_name: str
    amc: str | None = None
    category: str | None = None
    sub_category: str | None = None
    expense_ratio: float | None = None
    exit_load: str | None = None
    aum_cr: float | None = None
    nav_latest: float | None = None
    nav_date: date | None = None
    metrics: FundMetrics = Field(default_factory=FundMetrics)
    composite_score: float | None = None
    is_etf: bool = False
    live_quote: LiveQuote | None = None
