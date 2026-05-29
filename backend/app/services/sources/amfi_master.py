"""AMFI scheme master fetcher and parser.

Source: https://www.amfiindia.com/spages/NAVAll.txt
Format: semicolon-delimited text with interleaved section headers naming
the scheme category and AMC.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
TIMEOUT_SEC = 30

_CATEGORY_HEADER_RE = re.compile(r"^(Open|Close) Ended Schemes\((.+?)\)\s*$")
_FIELD_HEADER = "Scheme Code;ISIN Div Payout"


@dataclass
class AmfiScheme:
    scheme_code: int
    scheme_name: str
    amc: str
    category: str
    sub_category: str | None
    plan_type: str
    isin_growth: str | None
    isin_dividend: str | None
    nav: float | None
    nav_date: str | None


def _classify_category(raw: str) -> tuple[str, str]:
    raw_lower = raw.lower()
    if "equity" in raw_lower:
        top = "Equity"
    elif "debt" in raw_lower or "liquid" in raw_lower or "income" in raw_lower:
        top = "Debt"
    elif "hybrid" in raw_lower or "balanced" in raw_lower:
        top = "Hybrid"
    else:
        top = "Other"
    sub = raw.split("-", 1)[1].strip() if "-" in raw else raw
    return top, sub


def _detect_plan_type(name: str) -> str:
    return "Direct" if "direct" in name.lower() else "Regular"


def parse_navall(text: str) -> list[dict]:
    """Parse NAVAll.txt into list of dicts (one per scheme)."""
    out: list[dict] = []
    current_category: tuple[str, str] | None = None
    current_amc: str | None = None
    in_data = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            in_data = False
            continue

        m = _CATEGORY_HEADER_RE.match(line)
        if m:
            current_category = _classify_category(m.group(2))
            current_amc = None
            in_data = False
            continue

        if line.startswith(_FIELD_HEADER):
            in_data = True
            continue

        if ";" not in line and not in_data:
            current_amc = line
            continue

        if ";" in line and in_data and current_amc and current_category:
            parts = [p.strip() for p in line.split(";")]
            if len(parts) < 6:
                continue
            try:
                scheme_code = int(parts[0])
            except ValueError:
                continue
            isin_growth = parts[1] if parts[1] not in ("", "-") else None
            isin_div = parts[2] if parts[2] not in ("", "-") else None
            scheme_name = parts[3]
            try:
                nav = float(parts[4])
            except ValueError:
                nav = None
            nav_date = parts[5] or None
            top, sub = current_category
            out.append({
                "scheme_code": scheme_code,
                "scheme_name": scheme_name,
                "amc": current_amc,
                "category": top,
                "sub_category": sub,
                "plan_type": _detect_plan_type(scheme_name),
                "isin_growth": isin_growth,
                "isin_dividend": isin_div,
                "nav": nav,
                "nav_date": nav_date,
            })
    return out


async def fetch_navall(client: httpx.AsyncClient | None = None) -> list[dict]:
    """Download NAVAll.txt and return parsed list."""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(trust_env=False, timeout=TIMEOUT_SEC)
    try:
        resp = await client.get(NAVALL_URL)
        resp.raise_for_status()
        return parse_navall(resp.text)
    finally:
        if own_client:
            await client.aclose()
