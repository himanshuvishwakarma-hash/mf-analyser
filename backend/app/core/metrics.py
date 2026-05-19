"""Performance / risk metric computations.

Phase 1 — CAGR, Sharpe, std dev, max drawdown, momentum.
Stubs to be fleshed out in Week 3.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.config import get_settings

settings = get_settings()


def cagr(start_value: float, end_value: float, years: float) -> float:
    """Compound Annual Growth Rate. Returns 0 if start_value <= 0 or years <= 0."""
    if start_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1 / years) - 1


def annualised_std_dev(daily_returns: pd.Series) -> float:
    """Annualised volatility of daily returns (sqrt(252) scaling)."""
    if daily_returns.empty:
        return 0.0
    return float(daily_returns.std(ddof=0) * math.sqrt(252))


def sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float | None = None) -> float:
    """(Annualised return − risk-free rate) / annualised std dev.

    Risk-free rate defaults to RISK_FREE_RATE env var (8%).
    """
    rf = settings.risk_free_rate if risk_free_rate is None else risk_free_rate
    if daily_returns.empty:
        return 0.0
    annual_return = float((1 + daily_returns.mean()) ** 252 - 1)
    sigma = annualised_std_dev(daily_returns)
    if sigma == 0:
        return 0.0
    return (annual_return - rf) / sigma


def max_drawdown(nav_series: pd.Series) -> tuple[float, int, int]:
    """Max drawdown plus durations.

    Returns (drawdown, peak_to_trough_months, recovery_months) where:
      * drawdown                - negative number, e.g. -0.32 for a 32% fall
      * peak_to_trough_months   - months it took to fall from peak to trough
      * recovery_months         - months from trough back to peak (0 if not recovered)
    """
    if nav_series.empty:
        return 0.0, 0, 0
    running_max = nav_series.cummax()
    drawdown = (nav_series - running_max) / running_max
    mdd_idx = drawdown.idxmin()
    mdd = float(drawdown.loc[mdd_idx])

    # Find the peak that preceded the trough (last point where NAV == running_max
    # at-or-before mdd_idx).
    peak_value = running_max.loc[mdd_idx]
    pre = nav_series.loc[:mdd_idx]
    peak_candidates = pre[pre >= peak_value]
    peak_idx = peak_candidates.index[-1] if not peak_candidates.empty else pre.index[0]
    peak_to_trough_months = int(((mdd_idx - peak_idx).days) // 30)

    recovered = nav_series.loc[mdd_idx:][nav_series.loc[mdd_idx:] >= peak_value]
    if recovered.empty:
        return mdd, max(peak_to_trough_months, 0), 0
    recovery_idx = recovered.index[0]
    recovery_months = int(((recovery_idx - mdd_idx).days) // 30)
    return mdd, max(peak_to_trough_months, 0), max(recovery_months, 0)


def momentum(nav_series: pd.Series, months: int) -> float:
    """Point-to-point return over the trailing N months."""
    if nav_series.empty or months <= 0:
        return 0.0
    days = months * 30
    if len(nav_series) < days:
        return 0.0
    start = float(nav_series.iloc[-days])
    end = float(nav_series.iloc[-1])
    if start <= 0:
        return 0.0
    return end / start - 1


def daily_returns_from_nav(nav_series: pd.Series) -> pd.Series:
    """Convert a NAV time series to daily simple returns, dropping NaNs."""
    return nav_series.pct_change().dropna()


def _placeholder() -> None:  # keep numpy import alive for future use
    _ = np.array([0.0])
