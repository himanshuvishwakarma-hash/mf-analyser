"""Composite scoring engine (spec section 3).

Public surface:
    - recompute_category_benchmarks(session) -> dict
    - recompute_all_scores(session) -> dict
    - score_fund(metric_row, percentile_map, exit_load_raw=None) -> dict

Pipeline:
    1. recompute_category_benchmarks  builds p25/p50/p75 per (category, metric).
    2. recompute_all_scores  walks every Regular-plan fund that has metrics,
       converts each metric to a percentile rank within its category,
       applies weights from FACTOR_WEIGHTS (spec section 3.2), then writes
       a new row to fund_scores.

Lower-is-better metrics (expense_ratio, max_drawdown) are inverted before
percentile ranking so a low expense gets a high score.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.fund import CategoryBenchmark, Fund, FundMetric, FundScore

logger = logging.getLogger(__name__)


# Spec section 3.2 weights. Sum should equal 1.0.
FACTOR_WEIGHTS: dict[str, float] = {
    "sharpe": 0.20,
    "cagr_3y": 0.15,
    "cagr_5y": 0.15,
    "cagr_1y": 0.10,
    "consistency": 0.10,  # 1 / std_dev
    "drawdown": 0.10,
    "expense": 0.10,
    "momentum": 0.05,
    "aum": 0.05,
}

# Metrics for which "lower is better": inverted before ranking.
_LOWER_IS_BETTER = {"expense", "drawdown"}

# Map factor name -> attribute on FundMetric / Fund used as raw input.
_FACTOR_TO_ATTR = {
    "sharpe": ("metric", "sharpe_ratio"),
    "cagr_1y": ("metric", "cagr_1y"),
    "cagr_3y": ("metric", "cagr_3y"),
    "cagr_5y": ("metric", "cagr_5y"),
    "consistency": ("metric", "std_dev"),
    "drawdown": ("metric", "max_drawdown"),
    "momentum": ("metric", "momentum_6m"),
    "expense": ("fund", "expense_ratio"),
    "aum": ("fund", "aum_cr"),
}


def score_tier(score: float | None) -> str:
    if score is None:
        return "Unrated"
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Accumulate"
    if score >= 40:
        return "Neutral"
    if score >= 20:
        return "Caution"
    return "Avoid"


def _percentile_rank(value: float, sorted_pop: list[float]) -> float:
    """0-100 percentile rank of `value` within `sorted_pop`.

    Linear interpolation between empirical CDF steps. Returns 50 if pop empty.
    """
    n = len(sorted_pop)
    if n == 0:
        return 50.0
    if n == 1:
        return 50.0
    # Count strict-less and less-or-equal.
    lo = 0
    hi = n
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_pop[mid] < value:
            lo = mid + 1
        else:
            hi = mid
    less = lo
    # Average of less and less_or_equal positions.
    le = less
    while le < n and sorted_pop[le] <= value:
        le += 1
    return ((less + le) / 2.0) / n * 100.0


def _gather_raw(fund: Fund, metric: FundMetric, factor: str) -> float | None:
    source, attr = _FACTOR_TO_ATTR[factor]
    obj = metric if source == "metric" else fund
    return getattr(obj, attr, None)


def _adjust_for_direction(factor: str, raw: float) -> float:
    """Lower-is-better metrics get inverted so ranking still flows high=good."""
    if factor == "consistency":
        # Lower std_dev is better. Invert: high score for low vol.
        return -raw
    if factor in _LOWER_IS_BETTER:
        return -raw
    return raw


def _build_category_populations(
    session: Session,
) -> dict[str, dict[str, list[float]]]:
    """For each category, a dict of factor -> sorted list of raw values."""
    rows = session.execute(
        select(Fund, FundMetric)
        .join(FundMetric, FundMetric.scheme_code == Fund.scheme_code)
        .where(Fund.is_active.is_(True))
        .where(Fund.plan_type == "Regular")
    ).all()

    by_cat: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for fund, metric in rows:
        cat = fund.category or "Unclassified"
        for factor in FACTOR_WEIGHTS:
            raw = _gather_raw(fund, metric, factor)
            if raw is None or (isinstance(raw, float) and math.isnan(raw)):
                continue
            by_cat[cat][factor].append(_adjust_for_direction(factor, float(raw)))

    for _, by_factor in by_cat.items():
        for factor in by_factor:
            by_factor[factor].sort()
    return by_cat


def _percentile_of(value: float, factor: str, sorted_pop: list[float]) -> float:
    adj = _adjust_for_direction(factor, value)
    return _percentile_rank(adj, sorted_pop)


def score_fund(
    fund: Fund,
    metric: FundMetric,
    sorted_pop_by_factor: dict[str, list[float]],
) -> dict[str, Any]:
    """Compute composite + sub-scores for a single fund."""
    sub_scores: dict[str, float] = {}
    weighted_total = 0.0
    weight_used = 0.0

    for factor, weight in FACTOR_WEIGHTS.items():
        raw = _gather_raw(fund, metric, factor)
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            sub_scores[factor] = None
            continue
        pop = sorted_pop_by_factor.get(factor, [])
        if not pop:
            sub_scores[factor] = None
            continue
        pct = _percentile_of(float(raw), factor, pop)
        sub_scores[factor] = pct
        weighted_total += pct * weight
        weight_used += weight

    # Re-scale composite using only available weights, so missing data
    # doesn't drag the score to zero (spec section 3 Step 3).
    composite = (weighted_total / weight_used) if weight_used > 0 else 0.0

    # Momentum overlay: nudge by +/-5 based on 3m signal vs category.
    momentum_overlay = 0.0
    if metric.momentum_3m is not None:
        m3_pop = sorted_pop_by_factor.get("momentum", [])
        if m3_pop:
            m3_pct = _percentile_rank(float(metric.momentum_3m), m3_pop)
            momentum_overlay = (m3_pct - 50.0) / 50.0 * 5.0

    # Exit-load penalty (binary signal, up to -5 points).
    exit_load_penalty = 0.0
    if fund.exit_load:
        s = fund.exit_load.lower()
        if "1%" in s or "1.0%" in s or "365" in s or "year" in s:
            exit_load_penalty = -5.0

    final_score = max(0.0, min(100.0, composite + momentum_overlay + exit_load_penalty))

    return {
        "composite_score": round(final_score, 2),
        "sharpe_score": sub_scores.get("sharpe"),
        "cagr_1y_score": sub_scores.get("cagr_1y"),
        "cagr_3y_score": sub_scores.get("cagr_3y"),
        "cagr_5y_score": sub_scores.get("cagr_5y"),
        "consistency_score": sub_scores.get("consistency"),
        "drawdown_score": sub_scores.get("drawdown"),
        "expense_score": sub_scores.get("expense"),
        "momentum_score": sub_scores.get("momentum"),
        "aum_score": sub_scores.get("aum"),
        "momentum_overlay": round(momentum_overlay, 2),
        "exit_load_penalty": exit_load_penalty,
    }


def recompute_category_benchmarks(session: Session) -> dict[str, int]:
    """Drop and rebuild category_benchmarks (p25 / p50 / p75 per metric per category)."""
    by_cat = _build_category_populations(session)

    session.execute(delete(CategoryBenchmark))
    rows_added = 0
    for cat, by_factor in by_cat.items():
        for factor, sorted_pop in by_factor.items():
            if not sorted_pop:
                continue
            session.add(
                CategoryBenchmark(
                    category=cat,
                    metric_name=factor,
                    percentile_25=_quantile(sorted_pop, 0.25),
                    percentile_50=_quantile(sorted_pop, 0.50),
                    percentile_75=_quantile(sorted_pop, 0.75),
                )
            )
            rows_added += 1
    session.commit()
    logger.info("compute_benchmarks done: %d rows", rows_added)
    return {"benchmarks_written": rows_added, "categories": len(by_cat)}


def _quantile(sorted_pop: list[float], q: float) -> float:
    if not sorted_pop:
        return 0.0
    pos = (len(sorted_pop) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_pop) - 1)
    frac = pos - lo
    return sorted_pop[lo] * (1 - frac) + sorted_pop[hi] * frac


def recompute_all_scores(session: Session) -> dict[str, int]:
    """Score every Regular-plan fund that has a metric row."""
    pop_by_cat = _build_category_populations(session)

    rows = session.execute(
        select(Fund, FundMetric)
        .join(FundMetric, FundMetric.scheme_code == Fund.scheme_code)
        .where(Fund.is_active.is_(True))
        .where(Fund.plan_type == "Regular")
    ).all()

    # Wipe previous scores to keep one row per scheme_code (spec keeps history;
    # we keep just the latest here for simplicity).
    session.execute(delete(FundScore))

    now = datetime.utcnow()
    scored = 0
    for fund, metric in rows:
        cat = fund.category or "Unclassified"
        pop = pop_by_cat.get(cat, {})
        if not pop:
            continue
        values = score_fund(fund, metric, pop)
        session.add(
            FundScore(
                scheme_code=fund.scheme_code,
                computed_at=now,
                **values,
            )
        )
        scored += 1
        if scored % 200 == 0:
            session.commit()

    session.commit()
    logger.info("compute_scores done: scored=%d", scored)
    return {"scored": scored, "total_funds": len(rows)}
