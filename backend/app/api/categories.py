"""Category listing endpoint (spec section 5.2 - /api/v1/categories)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fund import CategoryBenchmark, Fund
from app.services import cache

router = APIRouter()


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> dict[str, Any]:
    """List categories with fund counts and median benchmark metrics."""

    def loader() -> dict[str, Any]:
        stmt = (
            select(Fund.category, func.count(Fund.scheme_code).label("n"))
            .where(Fund.is_active.is_(True))
            .where(
                (Fund.plan_type == "Regular")
                | (
                    (Fund.plan_type.is_(None))
                    & (func.lower(Fund.fund_name).not_like("%direct%"))
                )
            )
            .group_by(Fund.category)
            .order_by(Fund.category)
        )
        rows = db.execute(stmt).all()

        benchmarks = db.execute(
            select(
                CategoryBenchmark.category,
                CategoryBenchmark.metric_name,
                CategoryBenchmark.percentile_50,
            )
        ).all()
        bench_map: dict[str, dict[str, float | None]] = {}
        for cat, metric_name, p50 in benchmarks:
            bench_map.setdefault(cat, {})[metric_name] = p50

        return {
            "categories": [
                {
                    "category": cat or "Unclassified",
                    "fund_count": int(n),
                    "median_metrics": bench_map.get(cat, {}),
                }
                for (cat, n) in rows
            ]
        }

    return cache.get_or_set("categories:all", loader)
