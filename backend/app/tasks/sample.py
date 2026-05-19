"""Sprint 0 heartbeat task — proves the Celery worker and beat are alive."""
from __future__ import annotations

import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.sample.tick")
def tick() -> str:
    logger.info("celery tick — worker alive")
    return "tick"
