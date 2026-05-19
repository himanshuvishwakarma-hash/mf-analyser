"""Scoring endpoint (spec section 5.2 - /api/v1/funds/{code}/score)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.scoring_engine import FACTOR_WEIGHTS, score_tier
from app.db import get_db
from app.models.fund import Fund, FundScore

router = APIRouter()


@router.get("/{scheme_code}/score")
def get_score(scheme_code: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Composite score and sub-score breakdown."""
    fund = db.get(Fund, scheme_code)
    if fund is None:
        raise HTTPException(status_code=404, detail=f"Fund {scheme_code} not found")

    score = db.execute(
        select(FundScore)
        .where(FundScore.scheme_code == scheme_code)
        .order_by(desc(FundScore.computed_at))
        .limit(1)
    ).scalar_one_or_none()

    if score is None:
        raise HTTPException(
            status_code=404,
            detail=f"No score computed yet for {scheme_code}. Run compute_scores task.",
        )

    return {
        "scheme_code": scheme_code,
        "category": fund.category,
        "composite_score": score.composite_score,
        "tier": score_tier(score.composite_score),
        "computed_at": score.computed_at.isoformat() if score.computed_at else None,
        "sub_scores": {
            "sharpe": score.sharpe_score,
            "cagr_1y": score.cagr_1y_score,
            "cagr_3y": score.cagr_3y_score,
            "cagr_5y": score.cagr_5y_score,
            "consistency": score.consistency_score,
            "drawdown": score.drawdown_score,
            "expense": score.expense_score,
            "momentum": score.momentum_score,
            "aum": score.aum_score,
        },
        "overlays": {
            "momentum_overlay": score.momentum_overlay,
            "exit_load_penalty": score.exit_load_penalty,
        },
        "weights": FACTOR_WEIGHTS,
    }
