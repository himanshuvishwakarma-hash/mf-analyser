"""Helper: print scheme_code + fund_name for likely-ETF schemes in the DB.

Use this to look up AMFI scheme codes before adding rows to
data/etf_symbol_map.csv.

Usage:
    python -m app.scripts.find_etf_codes [search-term]

Examples:
    python -m app.scripts.find_etf_codes              # all funds with "ETF" in name
    python -m app.scripts.find_etf_codes gold         # gold ETFs
    python -m app.scripts.find_etf_codes "nifty 50"   # Nifty 50 ETFs

Pair the scheme_code with the Yahoo symbol from finance.yahoo.com
(search for the fund name, NSE-listed, add ".NS" suffix).
"""
from __future__ import annotations

import sys

from sqlalchemy import or_, select

from app.db import SessionLocal
from app.models.fund import Fund


def main() -> int:
    term = " ".join(sys.argv[1:]).strip().lower() if len(sys.argv) > 1 else ""

    session = SessionLocal()
    try:
        stmt = select(Fund.scheme_code, Fund.fund_name, Fund.amc).where(
            Fund.is_active.is_(True)
        )
        if term:
            pattern = f"%{term}%"
            stmt = stmt.where(Fund.fund_name.ilike(pattern))
        else:
            # Default: anything with "ETF" or "BeES" in the name.
            stmt = stmt.where(
                or_(
                    Fund.fund_name.ilike("%ETF%"),
                    Fund.fund_name.ilike("%BeES%"),
                )
            )
        rows = session.execute(stmt.order_by(Fund.fund_name)).all()
    finally:
        session.close()

    print(f"{'scheme_code':>12}  {'amc':<25}  fund_name")
    print("-" * 100)
    for code, name, amc in rows:
        print(f"{code:>12}  {(amc or '-')[:25]:<25}  {name}")
    print(f"\n{len(rows)} matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
