"""Seed etf_quotes table with (scheme_code, symbol_yahoo) rows from CSV.

Usage:
    python -m app.scripts.load_etf_map [path/to/etf_symbol_map.csv]

If no path given, uses backend/data/etf_symbol_map.csv.

Behavior:
- Reads CSV (columns: scheme_code, symbol_yahoo, name).
- For each row where scheme_code exists in funds table:
    * upserts a stub row into etf_quotes with symbol_yahoo set,
      leaving price columns NULL (refresh_etf_quotes Celery task will fill them).
- Skips rows whose scheme_code is not in funds (logs warning).
- Idempotent: re-running updates the symbol if changed.

This is a one-shot seed script. The CSV is the source of truth for the
ETF universe; edit and re-run to add/remove ETFs.
"""
from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.fund import EtfQuote, Fund

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "etf_symbol_map.csv"


def load_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            try:
                rows.append(
                    {
                        "scheme_code": int(r["scheme_code"]),
                        "symbol_yahoo": r["symbol_yahoo"].strip(),
                        "name": (r.get("name") or "").strip(),
                    }
                )
            except (KeyError, ValueError) as exc:
                logger.warning("skip bad row %s: %s", r, exc)
    return rows


def upsert_etf_quotes(session: Session, rows: list[dict]) -> dict[str, int]:
    """Upsert (scheme_code, symbol_yahoo) into etf_quotes. Price fields stay NULL."""
    if not rows:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    # Filter to schemes that actually exist in funds.
    codes = [r["scheme_code"] for r in rows]
    existing = {
        c for (c,) in session.execute(
            select(Fund.scheme_code).where(Fund.scheme_code.in_(codes))
        ).all()
    }
    skipped = [r for r in rows if r["scheme_code"] not in existing]
    valid = [r for r in rows if r["scheme_code"] in existing]

    for r in skipped:
        logger.warning(
            "scheme_code %s (%s) not in funds table - skip", r["scheme_code"], r["symbol_yahoo"]
        )

    if not valid:
        return {"inserted": 0, "updated": 0, "skipped": len(skipped)}

    payload = [
        {"scheme_code": r["scheme_code"], "symbol_yahoo": r["symbol_yahoo"]}
        for r in valid
    ]
    stmt = pg_insert(EtfQuote.__table__).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["scheme_code"],
        set_={"symbol_yahoo": stmt.excluded.symbol_yahoo},
    )
    session.execute(stmt)
    session.commit()
    return {
        "inserted_or_updated": len(valid),
        "skipped_not_in_funds": len(skipped),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0]) if args else DEFAULT_CSV
    if not path.exists():
        logger.error("CSV not found: %s", path)
        return 2
    rows = load_csv(path)
    logger.info("loaded %d rows from %s", len(rows), path)
    session = SessionLocal()
    try:
        result = upsert_etf_quotes(session, rows)
    finally:
        session.close()
    logger.info("etf_quotes upsert: %s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
