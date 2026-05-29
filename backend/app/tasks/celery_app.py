"""Celery application + beat schedule."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "mf_analyser",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.sample", "app.tasks.refresh"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=2 * 60 * 60,
    task_soft_time_limit=110 * 60,
)

# Beat schedule. Run at 23:00 IST (spec section 9.2).
# Sequence:
#   23:00 fund master refresh (~5 min)
#   23:10 nav history refresh (incremental, ~30-60 min)
#   00:30 metrics recompute (~2 min)
#   00:45 category benchmarks
#   00:50 composite scoring
HOUR = settings.celery_schedule_hour

celery_app.conf.beat_schedule = {
    "nightly-fund-master": {
        "task": "app.tasks.refresh.refresh_fund_master",
        "schedule": crontab(hour=HOUR, minute=0),
    },
    "nightly-nav-history": {
        "task": "app.tasks.refresh.refresh_nav_history",
        "schedule": crontab(hour=HOUR, minute=10),
    },
    "nightly-metrics": {
        "task": "app.tasks.refresh.compute_metrics",
        "schedule": crontab(hour=(HOUR + 1) % 24, minute=30),
    },
    "nightly-benchmarks": {
        "task": "app.tasks.refresh.compute_benchmarks",
        "schedule": crontab(hour=(HOUR + 1) % 24, minute=45),
    },
    "weekly-expense-ratios": {
        "task": "app.tasks.refresh.refresh_expense_ratios",
        "schedule": crontab(hour=4, minute=0, day_of_week="sun"),
    },
    "nightly-scoring": {
        "task": "app.tasks.refresh.compute_scores",
        "schedule": crontab(hour=(HOUR + 1) % 24, minute=50),
    },
    # v3.3A: AMFI scheme master refresh nightly at 22:55 IST (5 min before legacy
    # fund_master task) so newer authoritative category + plan_type values land first.
    "nightly-amfi-master": {
        "task": "app.tasks.refresh.refresh_universe",
        "schedule": crontab(hour=HOUR, minute=55) if (False) else crontab(hour=22, minute=55),
    },
    # ETF live quotes via Yahoo: every 5 min during NSE hours (Mon-Fri 09:15-15:30 IST).
    # The task itself re-checks is_market_open() as a defensive gate.
    "etf-live-quotes": {
        "task": "app.tasks.refresh.refresh_etf_quotes",
        "schedule": crontab(minute="*/5", hour="9-15", day_of_week="mon-fri"),
    },
    # Nightly ETF NAV backfill (Phase H.2). Runs at 23:25 IST so it follows
    # the main fund-master + NAV cascade (23:00 + 23:10) but finishes before
    # compute_metrics (00:30). ETFs have plan_type=NULL and are otherwise
    # skipped by the regular-only NAV refresh.
    "nightly-etf-nav": {
        "task": "app.tasks.refresh.refresh_etf_nav_history",
        "schedule": crontab(hour=HOUR, minute=25),
    },
    # H.4: deactivate funds with no NAV in 60+ days (closed-ended / discontinued).
    # Runs nightly at 00:55 IST, right after compute_scores (00:50).
    "deactivate-stale-funds": {
        "task": "app.tasks.refresh.deactivate_stale_funds",
        "schedule": crontab(hour=(HOUR + 1) % 24, minute=55),
    },
}
