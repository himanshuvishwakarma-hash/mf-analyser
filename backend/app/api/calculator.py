"""SIP / Lumpsum projection endpoints (spec section 5.2, section 7)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.montecarlo import simulate_lumpsum, simulate_sip
from app.db import get_db
from app.models.fund import Fund, FundMetric

router = APIRouter()


class SIPRequest(BaseModel):
    scheme_code: int | None = None
    monthly_amount: float = Field(gt=0)
    duration_years: int = Field(gt=0, le=40)
    expected_return_pct: float | None = None
    expected_volatility_pct: float | None = None
    n_sims: int = Field(default=10000, ge=1000, le=50000)


class LumpsumRequest(BaseModel):
    scheme_code: int | None = None
    amount: float = Field(gt=0)
    duration_years: int = Field(gt=0, le=40)
    expected_return_pct: float | None = None
    expected_volatility_pct: float | None = None
    n_sims: int = Field(default=10000, ge=1000, le=50000)


def _resolve_assumptions(
    db: Session,
    scheme_code: int | None,
    explicit_return: float | None,
    explicit_vol: float | None,
) -> tuple[float, float, dict[str, Any]]:
    """Pick (mu, sigma) annual decimals. Priority: explicit override > fund metrics > defaults."""
    source: dict[str, Any] = {"source": "default"}
    mu = 0.12
    sigma = 0.18

    if scheme_code is not None:
        fund = db.get(Fund, scheme_code)
        if fund is None:
            raise HTTPException(status_code=404, detail=f"Fund {scheme_code} not found")
        metric = db.get(FundMetric, scheme_code)
        if metric is not None:
            if metric.cagr_5y is not None:
                mu = float(metric.cagr_5y)
                source = {"source": "fund_5y_history", "scheme_code": scheme_code}
            elif metric.cagr_3y is not None:
                mu = float(metric.cagr_3y)
                source = {"source": "fund_3y_history", "scheme_code": scheme_code}
            if metric.std_dev is not None and metric.std_dev > 0:
                sigma = float(metric.std_dev)

    if explicit_return is not None:
        mu = explicit_return / 100.0
        source = {"source": "user_override"}
    if explicit_vol is not None:
        sigma = explicit_vol / 100.0

    return mu, sigma, source


def _down_sample(series: list[float], every: int = 12) -> list[float]:
    """Yearly snapshots from a monthly series so the JSON stays small."""
    return [series[i] for i in range(every - 1, len(series), every)]


@router.post("/sip")
def sip_projection(req: SIPRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings()
    mu, sigma, source = _resolve_assumptions(
        db, req.scheme_code, req.expected_return_pct, req.expected_volatility_pct
    )
    n = req.n_sims or settings.monte_carlo_simulations

    result = simulate_sip(
        monthly=req.monthly_amount,
        years=req.duration_years,
        mu_annual=mu,
        sigma_annual=sigma,
        n_sims=n,
    )
    total_invested = req.monthly_amount * req.duration_years * 12

    return {
        "mode": "sip",
        "monthly_amount": req.monthly_amount,
        "duration_years": req.duration_years,
        "total_invested": total_invested,
        "assumptions": {
            "mu_annual": mu,
            "sigma_annual": sigma,
            **source,
            "n_sims": n,
        },
        # Yearly snapshots for charting
        "yearly": {
            "p10": _down_sample(result["p10"]),
            "p50": _down_sample(result["p50"]),
            "p90": _down_sample(result["p90"]),
            "expected": _down_sample(result["expected"]),
        },
        "final": result["final"],
    }


@router.post("/lumpsum")
def lumpsum_projection(req: LumpsumRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings()
    mu, sigma, source = _resolve_assumptions(
        db, req.scheme_code, req.expected_return_pct, req.expected_volatility_pct
    )
    n = req.n_sims or settings.monte_carlo_simulations

    result = simulate_lumpsum(
        amount=req.amount,
        years=req.duration_years,
        mu_annual=mu,
        sigma_annual=sigma,
        n_sims=n,
    )

    return {
        "mode": "lumpsum",
        "amount": req.amount,
        "duration_years": req.duration_years,
        "total_invested": req.amount,
        "assumptions": {
            "mu_annual": mu,
            "sigma_annual": sigma,
            **source,
            "n_sims": n,
        },
        "yearly": {
            "p10": _down_sample(result["p10"]),
            "p50": _down_sample(result["p50"]),
            "p90": _down_sample(result["p90"]),
            "expected": _down_sample(result["expected"]),
        },
        "final": result["final"],
    }
