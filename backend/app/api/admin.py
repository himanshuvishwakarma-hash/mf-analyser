"""Admin endpoints. Behind a shared secret in v2; full auth in v3.

Pass `X-Admin-Token: <token>` header. The token is read from env
`ADMIN_TOKEN`. If unset, all admin endpoints return 503.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import cache
from app.services.amfi_scraper import apply_manual_csv, run_amfi_scrape

router = APIRouter(tags=["admin"])


def _require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Admin endpoints disabled (ADMIN_TOKEN unset)")
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.post("/expense-upload")
async def expense_upload(
    file: UploadFile,
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> dict[str, Any]:
    """Accept a CSV (scheme_code, expense_ratio) and update funds in bulk."""
    csv_text = (await file.read()).decode("utf-8")
    result = apply_manual_csv(db, csv_text)
    cache.invalidate("funds:")
    return {
        "status": result.status,
        "rows_in_file": result.rows_in_file,
        "rows_matched": result.rows_matched,
        "rows_updated": result.rows_updated,
        "error": result.error,
    }


@router.post("/expense-scrape")
def expense_scrape_now(
    db: Session = Depends(get_db), _auth: None = Depends(_require_admin)
) -> dict[str, Any]:
    """Trigger the AMFI scrape immediately (otherwise runs Sun 04:00 IST)."""
    result = run_amfi_scrape(db)
    cache.invalidate("funds:")
    return {
        "status": result.status,
        "rows_in_file": result.rows_in_file,
        "rows_matched": result.rows_matched,
        "rows_updated": result.rows_updated,
        "as_of": result.as_of.isoformat() if result.as_of else None,
        "error": result.error,
    }


# ---- Phase F: first-boot status + manual cascade -----------------------

from sqlalchemy import func, select  # noqa: E402

from app.models.fund import Fund, FundScore, NavHistory  # noqa: E402


@router.get("/seed-status")
def seed_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Lightweight, NO-AUTH endpoint used by the first-boot modal.

    Returns enough signal for the frontend to decide whether to show
    the 'Setting up your fund universe' progress modal.
    """
    fund_count = int(db.scalar(select(func.count()).select_from(Fund)) or 0)
    nav_count = int(db.scalar(select(func.count()).select_from(NavHistory)) or 0)
    score_count = int(db.scalar(select(func.count()).select_from(FundScore)) or 0)
    return {
        "seeded": fund_count > 0 and nav_count > 0,
        "fund_count": fund_count,
        "nav_count": nav_count,
        "score_count": score_count,
        # Heuristic for "in progress": funds present but no scores yet.
        "in_progress": fund_count > 0 and score_count == 0,
    }


@router.post("/run-cascade")
def run_cascade_now(
    _auth: None = Depends(_require_admin),
) -> dict[str, Any]:
    """Trigger the full nightly cascade right now (fund master -> nav -> metrics -> scores).

    Useful on first boot or after an outage. Returns the Celery task IDs.
    """
    # Local import to avoid module-load cost in tests that don't use celery.
    from app.tasks import refresh as refresh_tasks

    master = refresh_tasks.refresh_fund_master.delay(populate_meta=False)
    nav = refresh_tasks.refresh_nav_history.delay(scheme_code=None, regular_only=True, limit=200)
    metrics = refresh_tasks.compute_metrics.delay()
    benchmarks = refresh_tasks.compute_benchmarks.delay()
    scores = refresh_tasks.compute_scores.delay()
    return {
        "dispatched": True,
        "tasks": {
            "fund_master": master.id,
            "nav_history": nav.id,
            "compute_metrics": metrics.id,
            "compute_benchmarks": benchmarks.id,
            "compute_scores": scores.id,
        },
    }
