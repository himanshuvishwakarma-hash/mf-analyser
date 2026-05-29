"""Orchestrate upstream data sources into the funds table.

v3.3A: AMFI master is the primary universe source. NSE + TER scrapers slot
in via additional helpers in later versions.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.services import cache

logger = logging.getLogger(__name__)


def apply_amfi_master(session: Session, rows: list[dict]) -> dict[str, int]:
    """Upsert AMFI scheme rows into the funds table.

    Always refreshes: category, sub_category, plan_type, fund_name, source.
    Only sets amc if currently NULL (preserves manual overrides).
    """
    inserted = 0
    updated = 0
    for row in rows:
        existing = session.get(Fund, row["scheme_code"])
        if existing is None:
            session.add(Fund(
                scheme_code=row["scheme_code"],
                fund_name=row["scheme_name"],
                amc=row["amc"],
                category=row["category"],
                sub_category=row["sub_category"],
                plan_type=row["plan_type"],
                is_active=True,
                source="amfi",
            ))
            inserted += 1
        else:
            existing.fund_name = row["scheme_name"]
            existing.category = row["category"]
            existing.sub_category = row["sub_category"]
            existing.plan_type = row["plan_type"]
            existing.is_active = True
            existing.source = "amfi"
            if existing.amc is None:
                existing.amc = row["amc"]
            updated += 1
    session.commit()
    cache.invalidate("funds:")
    cache.invalidate("categories:")
    out = {"inserted": inserted, "updated": updated, "total": len(rows)}
    logger.info("apply_amfi_master: %s", out)
    return out
