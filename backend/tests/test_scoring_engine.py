"""End-to-end tests for the scoring engine using the in-memory SQLite fixture."""
from __future__ import annotations

from app.core.scoring_engine import (
    recompute_all_scores,
    recompute_category_benchmarks,
    score_fund,
)
from app.models.fund import CategoryBenchmark, Fund, FundMetric, FundScore


def _seed_category(db_session, n: int = 5, category: str = "Equity") -> list[Fund]:
    """Seed N Regular-plan Equity funds with monotonically improving metrics."""
    funds: list[Fund] = []
    for i in range(n):
        f = Fund(
            scheme_code=1000 + i,
            fund_name=f"Test Fund {i}",
            amc="Test AMC",
            category=category,
            sub_category="Large Cap",
            plan_type="Regular",
            expense_ratio=2.0 - i * 0.2,  # decreasing cost -> better
            aum_cr=1000 + i * 1000,
            is_active=True,
        )
        m = FundMetric(
            scheme_code=1000 + i,
            cagr_1y=0.05 + i * 0.03,
            cagr_3y=0.08 + i * 0.02,
            cagr_5y=0.10 + i * 0.015,
            sharpe_ratio=0.5 + i * 0.2,
            std_dev=0.20 - i * 0.02,        # lower vol -> better consistency
            max_drawdown=-0.40 + i * 0.05,  # less severe drawdown -> better
            momentum_3m=0.02 + i * 0.01,
            momentum_6m=0.04 + i * 0.01,
        )
        db_session.add(f)
        db_session.add(m)
        funds.append(f)
    db_session.commit()
    return funds


def test_recompute_benchmarks_writes_one_row_per_metric_per_category(db_session) -> None:
    _seed_category(db_session, n=4)
    result = recompute_category_benchmarks(db_session)
    assert result["benchmarks_written"] > 0

    rows = db_session.query(CategoryBenchmark).all()
    by_metric = {r.metric_name for r in rows}
    # All factor names with non-null populations should appear.
    assert "sharpe" in by_metric
    assert "cagr_3y" in by_metric
    assert "expense" in by_metric


def test_recompute_all_scores_orders_best_fund_on_top(db_session) -> None:
    _seed_category(db_session, n=5)
    recompute_all_scores(db_session)

    scores = (
        db_session.query(FundScore)
        .order_by(FundScore.composite_score.desc())
        .all()
    )
    assert len(scores) == 5
    # Top score should belong to the "best" seeded fund (index 4 -> scheme_code 1004).
    assert scores[0].scheme_code == 1004
    assert scores[-1].scheme_code == 1000
    # Score range is sane.
    for s in scores:
        assert 0.0 <= s.composite_score <= 100.0


def test_score_fund_returns_higher_score_for_better_metrics(db_session) -> None:
    funds = _seed_category(db_session, n=5)
    from app.core.scoring_engine import _build_category_populations

    pop = _build_category_populations(db_session)["Equity"]

    best = funds[4]
    worst = funds[0]
    best_metric = db_session.get(FundMetric, best.scheme_code)
    worst_metric = db_session.get(FundMetric, worst.scheme_code)

    best_result = score_fund(best, best_metric, pop)
    worst_result = score_fund(worst, worst_metric, pop)
    assert best_result["composite_score"] > worst_result["composite_score"]


def test_recompute_all_scores_skips_funds_without_metrics(db_session) -> None:
    _seed_category(db_session, n=3)
    # Add an extra fund w/ no metric row -> shouldn't get scored.
    db_session.add(
        Fund(
            scheme_code=9999,
            fund_name="No Metric Fund",
            category="Equity",
            plan_type="Regular",
            is_active=True,
        )
    )
    db_session.commit()
    result = recompute_all_scores(db_session)
    assert result["scored"] == 3
    assert db_session.query(FundScore).filter_by(scheme_code=9999).first() is None
