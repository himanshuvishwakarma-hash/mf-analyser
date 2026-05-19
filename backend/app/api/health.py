"""Health probe endpoints.

- /health      cheap liveness probe (DB ping only)
- /health/deep includes Redis, Celery worker availability, and freshness
                of the last nightly refresh + ETF live quotes (Phase F.3).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fund import CategoryBenchmark, EtfQuote, Fund, FundScore, NavHistory
from app.services import cache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Cheap liveness probe for load balancers."""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # pragma: no cover
        db_ok = False
    return {"status": "ok", "db": "ok" if db_ok else "down"}


def _hours_since(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


@router.get("/health/deep")
def health_deep(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Deep health probe: DB + Redis + Celery + data freshness + ETF quotes."""
    checks: dict[str, Any] = {}

    # DB
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = {"status": "ok"}
    except Exception as e:  # pragma: no cover
        checks["db"] = {"status": "down", "error": str(e)}

    # Redis
    client = cache.get_client()
    if client is None:
        checks["redis"] = {"status": "down"}
    else:
        try:
            client.ping()
            checks["redis"] = {"status": "ok"}
        except Exception as e:  # pragma: no cover
            checks["redis"] = {"status": "down", "error": str(e)}

    # Celery worker presence
    celery_status: dict[str, Any] = {"status": "unknown"}
    try:
        from app.tasks.celery_app import celery_app

        insp = celery_app.control.inspect(timeout=1.0)
        active = insp.active() if insp else None
        if active:
            celery_status = {"status": "ok", "workers": list(active.keys())}
        else:
            celery_status = {"status": "warn", "detail": "no workers responded in 1s"}
    except Exception as e:  # pragma: no cover
        celery_status = {"status": "warn", "error": str(e)}
    checks["celery"] = celery_status

    # Data freshness
    fund_count = db.scalar(select(func.count()).select_from(Fund)) or 0
    score_count = db.scalar(select(func.count()).select_from(FundScore)) or 0
    bench_count = db.scalar(select(func.count()).select_from(CategoryBenchmark)) or 0
    latest_nav_dt = db.scalar(select(func.max(NavHistory.nav_date)))
    latest_score_dt = db.scalar(select(func.max(FundScore.computed_at)))
    score_age_h = _hours_since(latest_score_dt) if latest_score_dt else None

    freshness_status = "ok"
    if score_age_h is None or score_age_h > 48:
        freshness_status = "warn"
    if score_age_h is not None and score_age_h > 12:
        # 12-48h is still "ok" yellow-ish in UI but flagged in the data block.
        pass

    checks["data"] = {
        "status": freshness_status,
        "funds_total": int(fund_count),
        "funds_scored": int(score_count),
        "category_benchmarks": int(bench_count),
        "latest_nav_date": latest_nav_dt.isoformat() if latest_nav_dt else None,
        "latest_score_computed_at": latest_score_dt.isoformat() if latest_score_dt else None,
        "score_age_hours": round(score_age_h, 1) if score_age_h is not None else None,
    }

    # ETF live quote freshness (Phase F.3)
    etf_count = db.scalar(select(func.count()).select_from(EtfQuote)) or 0
    latest_etf_dt = db.scalar(select(func.max(EtfQuote.updated_at)))
    etf_age_h = _hours_since(latest_etf_dt) if latest_etf_dt else None
    etf_status = "ok"
    if etf_count == 0:
        etf_status = "unknown"  # no ETFs configured = neutral
    elif etf_age_h is None or etf_age_h > 24:
        etf_status = "warn"
    checks["etf_quotes"] = {
        "status": etf_status,
        "tracked": int(etf_count),
        "latest_updated_at": latest_etf_dt.isoformat() if latest_etf_dt else None,
        "age_hours": round(etf_age_h, 1) if etf_age_h is not None else None,
    }

    # Roll up (down > warn > ok). "unknown" doesn't degrade.
    rollup = "ok"
    for v in checks.values():
        s = v.get("status")
        if s == "down":
            rollup = "down"
            break
        if s == "warn" and rollup != "down":
            rollup = "warn"

    return {"status": rollup, "checks": checks}
