"""AMFI Total Expense Ratio scraper - URL discovery (v3.3A rewrite).

Picks the newest TER-YYYY-MM.xlsx link off the AMFI research page.
Full download + parse pipeline lives in v3.3A.1.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

INDEX_URL = (
    "https://www.amfiindia.com/research-information/other-data/"
    "total-expense-ratio-of-mutual-fund-schemes"
)

_TER_NAME_RE = re.compile(r"TER[-_](\d{4})[-_](\d{2})\.xlsx$", re.IGNORECASE)


def find_latest_xlsx_url(html: str, *, base: str) -> str | None:
    """Parse HTML, return absolute URL of newest TER xlsx, or None."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[tuple[int, int], str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _TER_NAME_RE.search(href)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            candidates.append(((year, month), urljoin(base, href)))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]
