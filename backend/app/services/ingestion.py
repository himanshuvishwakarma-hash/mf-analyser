"""Ingestion service: parse MFApi.in payloads and upsert into Postgres.

Public surface:
    - parse_plan_type(scheme_name) -> "Direct" | "Regular" | None
    - parse_main_category(scheme_category) -> high-level bucket
    - upsert_funds(session, raw_list, details_map=None) -> counts
    - upsert_nav_history(session, scheme_code, raw_data) -> counts
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.fund import Fund, NavHistory

logger = logging.getLogger(__name__)

# Postgres has a hard 32,767 parameter limit per statement.
# Fund table has 7 mutable columns; cap at 1000 rows per batch (= 7000 params, safe).
_FUND_BATCH_SIZE = 1000
# NavHistory has 3 columns; cap at 5000 rows per batch (= 15,000 params, safe).
_NAV_BATCH_SIZE = 5000
# Columns preserved when an upsert sends NULL (don't wipe AMFI-authored values
# with empty mfapi metadata). Mirrors the Postgres path's COALESCE behaviour
# so the SQLite test path keeps parity.
_PRESERVE_IF_NULL_COLS = frozenset({"amc", "category", "sub_category", "plan_type"})


# Parsers ---------------------------------------------------------------------

def parse_plan_type(scheme_name: str) -> str | None:
    if not scheme_name:
        return None
    name = scheme_name.lower()
    if "direct" in name:
        return "Direct"
    if "regular" in name:
        return "Regular"
    return None


_MAIN_CATEGORY_PREFIXES = (
    ("Equity Scheme", "Equity"),
    ("Debt Scheme", "Debt"),
    ("Hybrid Scheme", "Hybrid"),
    ("Solution Oriented Scheme", "Solution"),
    ("Other Scheme", "Other"),
    ("Index Funds", "Index/ETF"),
    ("Exchange Traded Funds", "Index/ETF"),
    ("Fund of Funds", "Other"),
)


def parse_main_category(scheme_category: str | None) -> str | None:
    if not scheme_category:
        return None
    for prefix, bucket in _MAIN_CATEGORY_PREFIXES:
        if scheme_category.startswith(prefix):
            return bucket
    return "Other"


def parse_sub_category(scheme_category: str | None) -> str | None:
    if not scheme_category:
        return None
    if " - " in scheme_category:
        return scheme_category.split(" - ", 1)[1].strip()
    return scheme_category.strip()


def parse_nav_date(value: str) -> date:
    return datetime.strptime(value, "%d-%m-%Y").date()


# Upserts ---------------------------------------------------------------------

@dataclass
class UpsertCounts:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def upsert_funds(
    session: Session,
    raw_list: Iterable[dict[str, Any]],
    details: dict[int, dict[str, Any]] | None = None,
) -> UpsertCounts:
    """Upsert rows from GET /mf into the funds table.

    Postgres path uses ON CONFLICT DO UPDATE in batches of _FUND_BATCH_SIZE
    to stay under the 32,767 parameter limit.
    """
    counts = UpsertCounts()
    details = details or {}

    rows: list[dict[str, Any]] = []
    for item in raw_list:
        scheme_code = item.get("schemeCode")
        scheme_name = item.get("schemeName")
        if scheme_code is None or not scheme_name:
            counts.skipped += 1
            continue

        meta = (details.get(scheme_code) or {}).get("meta") or {}
        rows.append(
            {
                "scheme_code": int(scheme_code),
                "fund_name": scheme_name,
                "amc": meta.get("fund_house"),
                "category": parse_main_category(meta.get("scheme_category")),
                "sub_category": parse_sub_category(meta.get("scheme_category")),
                "plan_type": parse_plan_type(scheme_name),
                "is_active": True,
            }
        )

    if not rows:
        return counts

    dialect = session.bind.dialect.name if session.bind else ""
    if dialect == "postgresql":
        update_cols_template = None
        total = 0
        for batch in _chunks(rows, _FUND_BATCH_SIZE):
            stmt = pg_insert(Fund.__table__).values(batch)
            if update_cols_template is None:
                update_cols_template = {
                    "fund_name": stmt.excluded.fund_name,
                    "amc": stmt.excluded.amc,
                    "category": stmt.excluded.category,
                    "sub_category": stmt.excluded.sub_category,
                    "plan_type": stmt.excluded.plan_type,
                    "is_active": stmt.excluded.is_active,
                }
            # COALESCE: keep existing AMFI-authored values when mfapi sends NULL.
            # mfapi's list endpoint returns NULL for amc/category/sub_category/plan_type
            # unless populate_meta=True (which is off by default), so without coalesce
            # we'd nightly wipe everything that refresh_universe set at 22:55.
            fund_tbl = Fund.__table__
            stmt = stmt.on_conflict_do_update(
                index_elements=["scheme_code"],
                set_={
                    "fund_name": stmt.excluded.fund_name,
                    "amc": func.coalesce(stmt.excluded.amc, fund_tbl.c.amc),
                    "category": func.coalesce(stmt.excluded.category, fund_tbl.c.category),
                    "sub_category": func.coalesce(stmt.excluded.sub_category, fund_tbl.c.sub_category),
                    "plan_type": func.coalesce(stmt.excluded.plan_type, fund_tbl.c.plan_type),
                    "is_active": stmt.excluded.is_active,
                },
            )
            session.execute(stmt)
            total += len(batch)
            session.commit()
            logger.info(
                "upsert_funds: batch committed (%d rows, running total %d)",
                len(batch),
                total,
            )
        counts.inserted = total
    else:
        # SQLite (used in tests) - row-by-row merge with COALESCE parity.
        for row in rows:
            existing = session.get(Fund, row["scheme_code"])
            if existing is None:
                session.add(Fund(**row))
                counts.inserted += 1
            else:
                for k, v in row.items():
                    if k in _PRESERVE_IF_NULL_COLS and v is None:
                        continue
                    setattr(existing, k, v)
                counts.updated += 1
        session.commit()

    logger.info(
        "upsert_funds done: inserted/upserted=%d updated=%d skipped=%d",
        counts.inserted,
        counts.updated,
        counts.skipped,
    )
    return counts


def upsert_nav_history(
    session: Session,
    scheme_code: int,
    raw_data: list[dict[str, str]],
) -> UpsertCounts:
    """Bulk insert NAV history for a single scheme, chunked to stay under the
    Postgres parameter limit."""
    counts = UpsertCounts()
    if not raw_data:
        return counts

    parsed: list[dict[str, Any]] = []
    for item in raw_data:
        try:
            d = parse_nav_date(item["date"])
            nav = float(item["nav"])
        except (KeyError, ValueError, TypeError):
            counts.skipped += 1
            continue
        if nav <= 0:
            counts.skipped += 1
            continue
        parsed.append({"scheme_code": scheme_code, "nav_date": d, "nav": nav})

    if not parsed:
        return counts

    existing_dates = {
        d
        for (d,) in session.execute(
            select(NavHistory.nav_date).where(NavHistory.scheme_code == scheme_code)
        ).all()
    }

    new_rows = [r for r in parsed if r["nav_date"] not in existing_dates]
    counts.skipped += len(parsed) - len(new_rows)

    if new_rows:
        for batch in _chunks(new_rows, _NAV_BATCH_SIZE):
            session.bulk_insert_mappings(NavHistory, batch)
            session.commit()
        counts.inserted = len(new_rows)

    return counts
