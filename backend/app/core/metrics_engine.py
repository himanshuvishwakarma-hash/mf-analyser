"""Per-fund metric computation from NAV history.

Public surface:
    - compute_fund_metrics(nav_series, today=None) -> dict
    - recompute_all_fund_metrics(session, limit=None) -> dict

Each metric is a single scalar saved to the `fund_metrics` table:
    cagr_1y, cagr_3y, cagr_5y, cagr_10y, sharpe_ratio, std_dev,
    max_drawdown, recovery_months, momentum_3m, momentum_6m

NAV series is a pandas Series indexed by datetime.date, sorted ascending.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import metrics as m
from app.models.fund import Fund, FundMetric, NavHistory

logger = logging.getLogger(__name__)


def _years_between(start: date, end: date) -> float:
    return (end - start).days / 365.25


def _cagr_over_years(nav_series: pd.Series, years: int, today: date) -> float | None:
    """CAGR computed over the trailing N years from `today`. None if not enough history."""
    if nav_series.empty:
        return None
    cutoff = today - timedelta(days=int(years * 365.25))
    start_window = nav_series.loc[nav_series.index >= cutoff]
    if start_window.empty:
        return None
    start_val = float(start_window.iloc[0])
    end_val = float(nav_series.iloc[-1])
    actual_years = _years_between(start_window.index[0], nav_series.index[-1])
    if actual_years < years * 0.9:  # need at least ~90% of window
        return None
    if start_val <= 0:
        return None
    return m.cagr(start_val, end_val, actual_years)


def compute_fund_metrics(
    nav_series: pd.Series, today: date | None = None
) -> dict[str, Any]:
    """Given a NAV time series, return a dict of all derived metrics.

    Missing values come back as None instead of NaN so SQLAlchemy maps them cleanly.
    """
    if nav_series.empty:
        return {
            "cagr_1y": None, "cagr_3y": None, "cagr_5y": None, "cagr_10y": None,
            "sharpe_ratio": None, "std_dev": None,
            "max_drawdown": None, "drawdown_duration_months": None, "recovery_months": None,
            "momentum_3m": None, "momentum_6m": None,
        }

    nav_series = nav_series.sort_index()
    if today is None:
        today = nav_series.index[-1]

    # Need >= MIN_NAV_HISTORY_MONTHS for Sharpe.
    settings = get_settings()
    months_of_history = len(nav_series) / 21  # ~21 trading days per month
    have_min_history = months_of_history >= settings.min_nav_history_months

    daily = m.daily_returns_from_nav(nav_series)
    mdd, drawdown_months, recovery = m.max_drawdown(nav_series)

    return {
        "cagr_1y": _cagr_over_years(nav_series, 1, today),
        "cagr_3y": _cagr_over_years(nav_series, 3, today),
        "cagr_5y": _cagr_over_years(nav_series, 5, today),
        "cagr_10y": _cagr_over_years(nav_series, 10, today),
        "sharpe_ratio": m.sharpe_ratio(daily) if have_min_history else None,
        "std_dev": m.annualised_std_dev(daily) if have_min_history else None,
        "max_drawdown": mdd if mdd != 0.0 else None,
        "drawdown_duration_months": drawdown_months if drawdown_months > 0 else None,
        "recovery_months": recovery if recovery > 0 else None,
        "momentum_3m": m.momentum(nav_series, 3) or None,
        "momentum_6m": m.momentum(nav_series, 6) or None,
    }


def _load_nav_series(session: Session, scheme_code: int) -> pd.Series:
    rows = session.execute(
        select(NavHistory.nav_date, NavHistory.nav)
        .where(NavHistory.scheme_code == scheme_code)
        .order_by(NavHistory.nav_date)
    ).all()
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex([d for (d, _) in rows]).date
    vals = [float(n) for (_, n) in rows]
    return pd.Series(vals, index=idx)


def _upsert_metrics(session: Session, scheme_code: int, values: dict[str, Any]) -> None:
    """Postgres-only upsert (test path is exercised at higher level)."""
    dialect = session.bind.dialect.name if session.bind else ""
    if dialect == "postgresql":
        stmt = pg_insert(FundMetric.__table__).values(scheme_code=scheme_code, **values)
        stmt = stmt.on_conflict_do_update(index_elements=["scheme_code"], set_=values)
        session.execute(stmt)
    else:
        existing = session.get(FundMetric, scheme_code)
        if existing is None:
            session.add(FundMetric(scheme_code=scheme_code, **values))
        else:
            for k, v in values.items():
                setattr(existing, k, v)


def recompute_all_fund_metrics(
    session: Session, limit: int | None = None
) -> dict[str, int]:
    """Loop over every Regular-plan fund that has any NAV history and refresh metrics."""
    # Match the API universe filter so every visible fund gets metrics:
    # explicit Regular plan OR plan_type IS NULL where name has no Direct marker.
    from sqlalchemy import func, or_
    name_lower = func.lower(Fund.fund_name)
    stmt = (
        select(Fund.scheme_code)
        .where(Fund.is_active.is_(True))
        .where(Fund.category.is_not(None))
        .where(
            or_(
                Fund.plan_type == "Regular",
                (Fund.plan_type.is_(None))
                & ~name_lower.like("%direct%")
                & ~name_lower.like("%(d)%")
                & ~name_lower.like("%-direct-%"),
            )
        )
        .order_by(Fund.scheme_code)
    )
    codes = [c for (c,) in session.execute(stmt).all()]
    if limit:
        codes = codes[:limit]

    processed = 0
    skipped_no_data = 0

    for code in codes:
        nav = _load_nav_series(session, code)
        if nav.empty:
            skipped_no_data += 1
            continue
        values = compute_fund_metrics(nav)
        _upsert_metrics(session, code, values)
        processed += 1
        if processed % 200 == 0:
            session.commit()
            logger.info("compute_metrics progress: %d/%d", processed, len(codes))

    session.commit()
    logger.info(
        "compute_metrics done: processed=%d skipped_no_data=%d total_funds=%d",
        processed, skipped_no_data, len(codes),
    )
    return {
        "processed": processed,
        "skipped_no_data": skipped_no_data,
        "total_funds": len(codes),
    }
