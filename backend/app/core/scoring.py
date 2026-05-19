"""Composite scoring engine (Phase 2 stub).

Implements the 10-factor model per spec §3. Implementation lands in Phase 2.
"""
from __future__ import annotations

FACTOR_WEIGHTS: dict[str, float] = {
    "sharpe": 0.20,
    "cagr_3y": 0.15,
    "cagr_1y": 0.10,
    "cagr_5y": 0.15,
    "consistency": 0.10,
    "drawdown": 0.10,
    "expense": 0.10,
    "momentum": 0.05,
    "aum": 0.05,
}

LOWER_IS_BETTER = {"expense", "drawdown"}


def score_tier(score: float) -> str:
    """Map a 0–100 score to its display label (spec §10.2)."""
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Accumulate"
    if score >= 40:
        return "Neutral"
    if score >= 20:
        return "Caution"
    return "Avoid"
