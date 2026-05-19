"""Tests for the metrics_engine module."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from app.core.metrics_engine import compute_fund_metrics
from app.core.scoring_engine import _percentile_rank as scoring_percentile
from app.core.scoring_engine import _quantile, score_tier


def _synthetic_nav(years: float, daily_return: float = 0.0005, start: float = 100.0):
    """Build a NAV series of `years` years of trading days at constant daily return."""
    days = int(years * 365)
    end = date.today()
    idx = [end - timedelta(days=(days - i)) for i in range(days)]
    vals = [start * (1 + daily_return) ** i for i in range(days)]
    return pd.Series(vals, index=idx)


def test_compute_fund_metrics_empty_series_returns_all_nones() -> None:
    out = compute_fund_metrics(pd.Series(dtype=float))
    assert out["cagr_1y"] is None
    assert out["sharpe_ratio"] is None
    assert out["max_drawdown"] is None


def test_compute_fund_metrics_strong_uptrend_has_positive_returns() -> None:
    nav = _synthetic_nav(5, daily_return=0.0005)  # ~13% annual
    out = compute_fund_metrics(nav)
    assert out["cagr_1y"] is not None
    assert out["cagr_3y"] > 0.10
    assert out["cagr_5y"] > 0.10
    assert out["sharpe_ratio"] is not None
    assert out["sharpe_ratio"] > 0


def test_compute_fund_metrics_short_history_skips_long_cagrs() -> None:
    nav = _synthetic_nav(0.5)  # only 6 months
    out = compute_fund_metrics(nav)
    assert out["cagr_3y"] is None
    assert out["cagr_5y"] is None


def test_compute_fund_metrics_short_history_skips_sharpe() -> None:
    # Need at least MIN_NAV_HISTORY_MONTHS = 36 for Sharpe.
    nav = _synthetic_nav(1)  # 1 year = ~12 months of history
    out = compute_fund_metrics(nav)
    assert out["sharpe_ratio"] is None


# ----- scoring helpers -----

def test_percentile_rank_middle_value() -> None:
    pop = [1.0, 2.0, 3.0, 4.0, 5.0]
    p = scoring_percentile(3.0, pop)
    assert 40 <= p <= 60


def test_percentile_rank_top_value() -> None:
    pop = [1.0, 2.0, 3.0, 4.0, 5.0]
    p = scoring_percentile(10.0, pop)
    assert p == pytest.approx(100.0)


def test_percentile_rank_bottom_value() -> None:
    pop = [1.0, 2.0, 3.0, 4.0, 5.0]
    p = scoring_percentile(0.0, pop)
    assert p == pytest.approx(0.0)


def test_quantile_median() -> None:
    assert _quantile([1.0, 2.0, 3.0, 4.0, 5.0], 0.5) == pytest.approx(3.0)


def test_quantile_p25() -> None:
    assert _quantile([1.0, 2.0, 3.0, 4.0, 5.0], 0.25) == pytest.approx(2.0)


def test_score_tier_thresholds() -> None:
    assert score_tier(80) == "Strong"
    assert score_tier(65) == "Accumulate"
    assert score_tier(50) == "Neutral"
    assert score_tier(30) == "Caution"
    assert score_tier(10) == "Avoid"
    assert score_tier(None) == "Unrated"


