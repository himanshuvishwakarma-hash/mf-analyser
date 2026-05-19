"""FastAPI entrypoint for the Z1N Capital Mutual Fund Analyser."""
from __future__ import annotations

import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.api import admin, calculator, categories, funds, health, scores
from app.config import get_settings
from app.db import SessionLocal
from app.models.fund import Fund

settings = get_settings()

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
    )

app = FastAPI(
    title="Z1N Capital - MF Analyser API",
    version="0.1.0",
    description="Internal API for mutual fund scoring, comparison, and projection.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(funds.router, prefix=f"{API_PREFIX}/funds", tags=["funds"])
app.include_router(scores.router, prefix=f"{API_PREFIX}/funds", tags=["scores"])
app.include_router(categories.router, prefix=API_PREFIX, tags=["categories"])
app.include_router(calculator.router, prefix=f"{API_PREFIX}/calculator", tags=["calculator"])
app.include_router(admin.router, prefix=f"{API_PREFIX}/admin", tags=["admin"])


@app.on_event("startup")
def first_boot_seed_check() -> None:
    """Phase F.1: on startup, if funds table is empty, dispatch the seed cascade.

    Runs once at app boot. Dispatches Celery tasks so the request thread
    returns immediately. The frontend polls /admin/seed-status to show
    progress. Failure here is non-fatal (Celery may not be wired in tests).
    """
    try:
        with SessionLocal() as session:
            n = int(session.scalar(select(func.count()).select_from(Fund)) or 0)
        if n > 0:
            logger.info("first_boot_seed_check: funds table has %d rows, skip", n)
            return
        logger.info("first_boot_seed_check: funds table empty, dispatching seed cascade")
        from app.tasks import refresh as refresh_tasks

        refresh_tasks.refresh_fund_master.delay(populate_meta=False)
        refresh_tasks.refresh_nav_history.delay(
            scheme_code=None, regular_only=True, limit=200
        )
        refresh_tasks.compute_metrics.delay()
        refresh_tasks.compute_benchmarks.delay()
        refresh_tasks.compute_scores.delay()
    except Exception as exc:  # noqa: BLE001
        logger.warning("first_boot_seed_check skipped: %s", exc)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "mf-analyser", "version": "0.1.0", "docs": "/docs"}
