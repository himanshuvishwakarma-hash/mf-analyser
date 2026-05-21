"""Import the NSE NMF II broker master (FUNCODES-PRODCODE.xls) into our funds table.

The file ships with these columns:
    Fund, Scheme, Plan, Option, Fund Description, Product Code,
    Fund Type, Status, AllotmentDt, CloseDt, MaturityDt, ISIN,
    Fund Nature, Amfi

We use it to enrich existing funds rows where category / is_active is missing.
Only rows with a populated `Amfi` value can be mapped (it's the AMFI scheme
code = funds.scheme_code). Other rows are skipped silently.

Usage:
    python -m app.scripts.load_nse_master /path/to/FUNCODES-PRODCODE.xls
    python -m app.scripts.load_nse_master /path/to/FUNCODES-PRODCODE.xls --dry-run
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.fund import Fund
from app.services import cache

logger = logging.getLogger(__name__)


# Fund Type (NSE) -> our internal category. Anything not in this dict stays
# as "Other" so the H.4 NOT-NULL filter passes but UI still tabs it correctly.
FUND_TYPE_TO_CATEGORY: dict[str, str] = {
    "EQUITY FUND": "Equity",
    "EQUITY": "Equity",
    "Equity Fund": "Equity",
    "Equity": "Equity",
    "EQUITY FUN": "Equity",
    "E": "Equity",
    "DEBT FUND": "Debt",
    "DEBT": "Debt",
    "Debt Fund": "Debt",
    "DEBT Fund": "Debt",
    "INCOME FUND": "Debt",
    "INCOME": "Debt",
    "LIQUID FUND": "Debt",
    "LIQUID": "Debt",
    "Liquid Fund": "Debt",
    "CASH FUND": "Debt",
    "HYBRID FUND": "Hybrid",
    "HYBRID": "Hybrid",
    "Hybrid Fund": "Hybrid",
    "ETF": "Other",
    "INDEX FUND": "Other",
}


def map_category(fund_type: str | None) -> str:
    if not fund_type:
        return "Other"
    return FUND_TYPE_TO_CATEGORY.get(str(fund_type).strip(), "Other")


def load_xls(path: Path) -> pd.DataFrame:
    """Read the NSE NMF II master XLS. Requires xlrd."""
    df = pd.read_excel(path)
    needed = {"Amfi", "Fund Description", "Fund Type", "Status", "Fund Nature"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"NSE XLS missing required columns: {missing}")
    return df


def enrich_funds(
    session: Session,
    df: pd.DataFrame,
    *,
    dry_run: bool = False,
    deactivate_close_ended: bool = False,
) -> dict[str, int]:
    """Update funds rows with category + is_active from NSE master."""
    # Keep only rows with an AMFI code that we can map back to funds.scheme_code.
    df = df[df["Amfi"].notna()].copy()
    df["Amfi"] = df["Amfi"].astype(int)
    # Drop duplicate AMFI codes (file has multiple plan / option rows per scheme).
    df = df.drop_duplicates(subset=["Amfi"], keep="first")

    matched = 0
    unmatched = 0
    updated_category = 0
    updated_active = 0
    closed_ended_deactivated = 0

    for row in df.to_dict(orient="records"):
        code = int(row["Amfi"])
        fund = session.get(Fund, code)
        if fund is None:
            unmatched += 1
            continue
        matched += 1

        cat = map_category(row.get("Fund Type"))
        is_close = str(row.get("Fund Nature") or "").upper() == "CLOSE"
        is_status_active = str(row.get("Status") or "").lower() == "active"

        # Update category if currently NULL.
        if fund.category is None and cat:
            fund.category = cat
            updated_category += 1

        # Optionally deactivate close-ended FMPs. Off by default so advisors
        # can still see + recommend FMPs (some Z1N clients allocate to them).
        # Pass --deactivate-close-ended to hide them.
        if is_close and fund.is_active and deactivate_close_ended:
            fund.is_active = False
            closed_ended_deactivated += 1
        elif (not is_status_active) and fund.is_active:
            # Status=Deactive in NSE -> mark inactive too.
            fund.is_active = False
            updated_active += 1

    out = {
        "rows_in_file": int(len(df)),
        "matched_in_db": matched,
        "unmatched_amfi_codes": unmatched,
        "updated_category": updated_category,
        "deactivated_status": updated_active,
        "deactivated_close_ended": closed_ended_deactivated,
    }
    if dry_run:
        session.rollback()
        out["dry_run"] = True
    else:
        session.commit()
        cache.invalidate("funds:")
        cache.invalidate("categories:")
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("xls_path", type=Path, help="Path to FUNCODES-PRODCODE.xls")
    p.add_argument(
        "--dry-run", action="store_true", help="Show effect without committing"
    )
    p.add_argument(
        "--deactivate-close-ended",
        action="store_true",
        help="Also flip is_active=False on CLOSE-ended (FMP/closed-ended) schemes. "
        "Default: leave them active so advisors can still see + recommend them.",
    )
    args = p.parse_args(argv)

    if not args.xls_path.exists():
        logger.error("File not found: %s", args.xls_path)
        return 2

    df = load_xls(args.xls_path)
    logger.info("loaded %d rows from %s", len(df), args.xls_path)

    session = SessionLocal()
    try:
        result = enrich_funds(
            session,
            df,
            dry_run=args.dry_run,
            deactivate_close_ended=args.deactivate_close_ended,
        )
    finally:
        session.close()

    logger.info("enrich_funds: %s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
