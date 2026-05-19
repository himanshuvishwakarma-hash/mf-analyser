"""AMFI Total Expense Ratio (TER) scraper.

AMFI publishes scheme-wise TER as a monthly Excel sheet on their disclosures
page. The exact URL changes monthly; this scraper:

1. Tries the configured base URL (env: AMFI_TER_URL, optional)
2. Otherwise discovers the latest file by scraping the index page
3. Parses Excel via pandas + openpyxl
4. Maps AMFI scheme codes to our funds table
5. Upserts expense_ratio + expense_ratio_as_of

Defensive: if any step fails, the existing expense_ratio values are left
untouched and the task returns a status of "no_change" so the caller can
alert. Manual CSV upload (admin endpoint) is the fallback.

Network calls live in `_download_latest()` so unit tests can monkeypatch
them without standing up a real HTTP server.
"""
from __future__ import annotations

import io
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import httpx
import pandas as pd
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.fund import Fund

logger = logging.getLogger(__name__)

# AMFI page that lists the latest TER disclosures.
DEFAULT_INDEX_URL = "https://www.amfiindia.com/research-information/other-data/total-expense-ratio-of-mutual-fund-schemes"

# Columns we look for in the Excel (case-insensitive fuzzy match).
SCHEME_CODE_COLS = ["scheme code", "amfi code", "code"]
EXPENSE_COLS = ["expense ratio", "ter", "total expense ratio"]


@dataclass
class ScrapeResult:
    status: str  # "ok" | "no_change" | "error"
    rows_in_file: int = 0
    rows_matched: int = 0
    rows_updated: int = 0
    as_of: date | None = None
    error: str | None = None


def _column_finder(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    """Return the first DataFrame column whose lowercased name contains any candidate."""
    lower = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        for key, original in lower.items():
            if cand in key:
                return original
    return None


def _download_latest(index_url: str = DEFAULT_INDEX_URL) -> tuple[bytes, date]:
    """Return (excel_bytes, as_of_date).

    Strategy: pull the index page, find the most recent .xlsx link, download
    it. The as_of date is parsed from the link text or filename.
    """
    settings = get_settings()
    override = getattr(settings, "amfi_ter_url", None) if hasattr(settings, "amfi_ter_url") else None

    with httpx.Client(timeout=30.0, trust_env=False) as client:
        if override:
            resp = client.get(override)
            resp.raise_for_status()
            return resp.content, date.today()

        index = client.get(index_url)
        index.raise_for_status()
        # Naive .xlsx link extraction; ignore embedded scripts.
        links = re.findall(r'href="([^"]+\.xlsx)"', index.text, flags=re.IGNORECASE)
        if not links:
            raise RuntimeError("No .xlsx link found on AMFI TER page")

        # Pick the first link (AMFI lists newest first).
        href = links[0]
        if href.startswith("/"):
            href = f"https://www.amfiindia.com{href}"

        # Try to extract as-of date from filename, e.g. "TER_Oct2025.xlsx".
        as_of = _date_from_filename(href) or date.today()

        resp = client.get(href)
        resp.raise_for_status()
        return resp.content, as_of


def _date_from_filename(filename: str) -> date | None:
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{4})", filename, re.IGNORECASE)
    if not m:
        return None
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    return date(int(m.group(2)), months[m.group(1).lower()[:3]], 1)


def parse_excel(content: bytes) -> pd.DataFrame:
    """Read the AMFI TER Excel and return a normalised DataFrame with two cols:
    scheme_code (int) and expense_ratio (float, percent).
    """
    df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    code_col = _column_finder(df, SCHEME_CODE_COLS)
    exp_col = _column_finder(df, EXPENSE_COLS)
    if not code_col or not exp_col:
        raise RuntimeError(
            f"AMFI TER schema unrecognised. Columns seen: {list(df.columns)[:10]}"
        )

    out = pd.DataFrame({
        "scheme_code": pd.to_numeric(df[code_col], errors="coerce"),
        "expense_ratio": pd.to_numeric(df[exp_col], errors="coerce"),
    }).dropna()
    out["scheme_code"] = out["scheme_code"].astype(int)
    return out


def upsert_expense_ratios(
    session: Session, parsed: pd.DataFrame, as_of: date
) -> tuple[int, int]:
    """Apply parsed (scheme_code, expense_ratio) rows to the funds table.

    Returns (matched_in_db, updated_rows).
    """
    matched = 0
    updated = 0
    for row in parsed.itertuples(index=False):
        existing = session.get(Fund, int(row.scheme_code))
        if existing is None:
            continue
        matched += 1
        if existing.expense_ratio != float(row.expense_ratio):
            updated += 1
        existing.expense_ratio = float(row.expense_ratio)
        # Only set if column exists (migration 0002 adds it).
        if hasattr(existing, "expense_ratio_as_of"):
            existing.expense_ratio_as_of = as_of
    session.commit()
    return matched, updated


def run_amfi_scrape(session: Session) -> ScrapeResult:
    """End-to-end: download, parse, upsert. Caller handles cache invalidation."""
    try:
        content, as_of = _download_latest()
    except Exception as e:
        logger.exception("AMFI download failed")
        return ScrapeResult(status="error", error=f"download: {e}")

    try:
        parsed = parse_excel(content)
    except Exception as e:
        logger.exception("AMFI Excel parse failed")
        return ScrapeResult(status="error", error=f"parse: {e}")

    if parsed.empty:
        return ScrapeResult(status="no_change", as_of=as_of)

    matched, updated = upsert_expense_ratios(session, parsed, as_of)
    return ScrapeResult(
        status="ok",
        rows_in_file=len(parsed),
        rows_matched=matched,
        rows_updated=updated,
        as_of=as_of,
    )


def apply_manual_csv(session: Session, csv_text: str) -> ScrapeResult:
    """Admin manual upload path. CSV must have headers scheme_code,expense_ratio."""
    try:
        df = pd.read_csv(io.StringIO(csv_text))
    except Exception as e:
        return ScrapeResult(status="error", error=f"csv parse: {e}")

    if not {"scheme_code", "expense_ratio"}.issubset(df.columns):
        return ScrapeResult(
            status="error",
            error="CSV must include columns: scheme_code, expense_ratio",
        )

    df = pd.DataFrame({
        "scheme_code": pd.to_numeric(df["scheme_code"], errors="coerce"),
        "expense_ratio": pd.to_numeric(df["expense_ratio"], errors="coerce"),
    }).dropna()
    df["scheme_code"] = df["scheme_code"].astype(int)

    matched, updated = upsert_expense_ratios(session, df, date.today())
    return ScrapeResult(
        status="ok",
        rows_in_file=len(df),
        rows_matched=matched,
        rows_updated=updated,
        as_of=date.today(),
    )


# Future: bulk SQL Server UPDATE for performance when row counts explode.
_ = update  # keep import; will be used in a later optimisation pass
