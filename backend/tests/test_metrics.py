"""Unit tests for metric computations.

Phase 1 will expand these; Sprint 0 only sanity-checks the public helpers.
"""
from __future__ import annotations

import math

import pandas as pd

from app.core.metrics import cagr, max_drawdown, momentum, sharpe_ratio


def test_cagr_zero_years_returns_zero() -> None:
    assert cagr(100, 200, 0) == 0.0


def test_cagr_doubles_in_one_year() -> None:
    assert math.isclose(cagr(100, 200, 1), 1.0, rel_tol=1e-9)


def test_cagr_negative_start_returns_zero() -> None:
    assert cagr(-1, 100, 5) == 0.0


def test_sharpe_with_zero_volatility_returns_zero() -> None:
    flat = pd.Series([0.0] * 252)
    assert sharpe_ratio(flat) == 0.0


def test_sharpe_positive_for_strong_positive_returns() -> None:
    # 0.1% daily for a year — strong returns, low vol
    s = pd.Series([0.001] * 252)
    assert sharpe_ratio(s) > 0


def test_max_drawdown_simple_case() -> None:
    nav = pd.Series([100, 110, 90, 95, 120], index=pd.date_range("2024-01-01", periods=5, freq="ME"))
    dd, fall_months, recovery_months = max_drawdown(nav)
    assert math.isclose(dd, (90 - 110) / 110, rel_tol=1e-9)
    # Peak (110) at month 2, trough (90) at month 3 -> roughly 1 month between them.
    assert fall_months >= 0
    # Recovery: NAV goes from 90 -> 120 by month 5, exceeds 110 peak.
    assert recovery_months >= 1


def test_max_drawdown_returns_zero_for_monotonic_rise() -> None:
    nav = pd.Series([100, 105, 110, 120, 130], index=pd.date_range("2024-01-01", periods=5, freq="ME"))
    dd, fall_months, recovery_months = max_drawdown(nav)
    assert dd == 0.0
    assert fall_months == 0
    assert recovery_months == 0


def test_max_drawdown_no_recovery_yet() -> None:
    # Peak at index 1 (110), trough at index 4 (60), never recovered.
    nav = pd.Series([100, 110, 90, 70, 60], index=pd.date_range("2024-01-01", periods=5, freq="ME"))
    dd, fall_months, recovery_months = max_drawdown(nav)
    assert math.isclose(dd, (60 - 110) / 110, rel_tol=1e-9)
    assert fall_months >= 1
    assert recovery_months == 0


def test_momentum_short_series_returns_zero() -> None:
    nav = pd.Series([100, 105, 110])
    assert momentum(nav, 3) == 0.0
