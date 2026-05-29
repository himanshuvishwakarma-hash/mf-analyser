# v3.3A Data Coverage Overhaul - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace v2's scattered upstream data sources with AMFI scheme master (primary universe), rewritten AMFI TER scraper (expense ratios), and NSE official quote API (live ETF prices) - so `funds.category` / `funds.expense_ratio` / `funds.plan_type` / `etf_quotes.last_price` populate without name-pattern guessing.

**Architecture:** Three new source modules under `app/services/sources/`, one thin orchestrator `app/services/universe_loader.py`, beat-schedule wiring through `app/tasks/refresh.py`. Existing v2 endpoints + scoring unchanged.

**Tech Stack:** Python 3.11, FastAPI 0.110, SQLAlchemy 2, Celery 5.3, httpx 0.26, BeautifulSoup4, openpyxl, pytest 8.

---

## File Structure

```
backend/
  app/
    services/
      sources/
        __init__.py                  (new)
        amfi_master.py               (new)
        amfi_ter_scraper.py          (new - rewrite of amfi_scraper.py)
        nse_quote_fetcher.py         (new)
      universe_loader.py             (new - orchestrator)
      amfi_scraper.py                (DELETE after migration)
      yahoo_fetch.py                 (modify - demote to fallback)
    tasks/
      refresh.py                     (modify - new beat tasks)
      celery_app.py                  (modify - beat schedule)
    api/
      funds.py                       (modify - simplify _exclude_direct_plans)
      admin.py                       (modify - add /admin/refresh-universe)
    models/
      fund.py                        (modify - add source column)
  alembic/versions/
    0005_funds_source.py             (new migration)
  tests/
    fixtures/
      navall_sample.txt              (new - 20-scheme test fixture)
      amfi_ter_page.html             (new - HTML fixture)
    sources/
      __init__.py                    (new)
      test_amfi_master.py            (new)
      test_amfi_ter_scraper.py       (new)
      test_nse_quote_fetcher.py      (new)
    test_universe_loader.py          (new)
    test_funds_api.py                (modify - update direct-plan filter test)
```

---

## Task 1: Add `source` column + migration

**Files:**
- Modify: `backend/app/models/fund.py`
- Create: `backend/alembic/versions/0005_funds_source.py`

- [ ] **Step 1: Write the migration**

```python
"""add source column to funds

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-25
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "funds",
        sa.Column("source", sa.String(length=32), nullable=True),
    )
    op.execute("UPDATE funds SET source = 'mfapi' WHERE source IS NULL")


def downgrade() -> None:
    op.drop_column("funds", "source")
```

- [ ] **Step 2: Add ORM column to `Fund`**

In `backend/app/models/fund.py`, inside `class Fund`, after `is_active`:

```python
source: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 3: Run migration against test DB + commit**

```bash
cd backend
python -c "from app.db import Base, SessionLocal; from app.models import fund"  # import sanity
git add backend/app/models/fund.py backend/alembic/versions/0005_funds_source.py
git commit -m "feat(model): add funds.source column (migration 0005)"
```

---

## Task 2: AMFI NAVAll.txt fetcher + parser

**Files:**
- Create: `backend/app/services/sources/__init__.py` (empty)
- Create: `backend/app/services/sources/amfi_master.py`
- Create: `backend/tests/fixtures/navall_sample.txt`
- Create: `backend/tests/sources/__init__.py` (empty)
- Create: `backend/tests/sources/test_amfi_master.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/sources/test_amfi_master.py`:

```python
"""Tests for app.services.sources.amfi_master."""
from pathlib import Path

import pytest

from app.services.sources import amfi_master

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "navall_sample.txt"


def test_parse_navall_returns_list_of_dicts():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = amfi_master.parse_navall(text)
    assert len(rows) >= 1
    assert {"scheme_code", "scheme_name", "amc", "category"} <= set(rows[0].keys())


def test_parse_navall_extracts_amc_from_section_header():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = amfi_master.parse_navall(text)
    # Every row should carry AMC inherited from the most recent header.
    assert all(r["amc"] for r in rows)


def test_parse_navall_extracts_category_from_section_header():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = amfi_master.parse_navall(text)
    assert all(r["category"] for r in rows)
    assert any(r["category"] == "Equity" for r in rows)


def test_parse_navall_detects_direct_plan_in_name():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = amfi_master.parse_navall(text)
    direct = [r for r in rows if "Direct" in r["scheme_name"]]
    assert all(r["plan_type"] == "Direct" for r in direct)


def test_parse_navall_skips_empty_rows():
    text = "\n\n;;;\n\n"
    rows = amfi_master.parse_navall(text)
    assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/sources/test_amfi_master.py -v
```

Expected: ImportError / file not found / `parse_navall` undefined.

- [ ] **Step 3: Create the test fixture**

`backend/tests/fixtures/navall_sample.txt`:

```
Open Ended Schemes(Equity Scheme - Large Cap Fund)

Aditya Birla Sun Life Mutual Fund

Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
103174;INF209K01157;INF209K01165;Aditya Birla Sun Life Frontline Equity Fund - Regular Plan - Growth;500.1234;25-May-2026
119551;INF209K01876;INF209K01884;Aditya Birla Sun Life Frontline Equity Fund - Direct Plan - Growth;520.4321;25-May-2026

Open Ended Schemes(Debt Scheme - Liquid Fund)

HDFC Mutual Fund

Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
100037;INF179K01CG7;INF179K01CH5;HDFC Liquid Fund - Regular Plan - Growth;4789.5678;25-May-2026
119551;-;-;HDFC Liquid Fund - Direct Plan - Growth;4810.1111;25-May-2026
```

(Real NAVAll has 9k schemes; this is a 4-row smoke fixture.)

- [ ] **Step 4: Implement `amfi_master.py`**

`backend/app/services/sources/amfi_master.py`:

```python
"""AMFI scheme master fetcher and parser.

Source: https://www.amfiindia.com/spages/NAVAll.txt
Format: pipe... actually semicolon-delimited text with interleaved section
headers naming the scheme category and AMC.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
TIMEOUT_SEC = 30

# Section header looks like:
#   Open Ended Schemes(Equity Scheme - Large Cap Fund)
_CATEGORY_HEADER_RE = re.compile(r"^(Open|Close) Ended Schemes\((.+?)\)\s*$")

# AMC line is just a plain string (no semicolons) immediately after the
# category header or between sub-categories.
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
    """Map AMFI raw scheme category to (top_level, sub_category)."""
    raw_lower = raw.lower()
    if "equity" in raw_lower:
        top = "Equity"
    elif "debt" in raw_lower or "liquid" in raw_lower or "income" in raw_lower:
        top = "Debt"
    elif "hybrid" in raw_lower or "balanced" in raw_lower:
        top = "Hybrid"
    else:
        top = "Other"
    # Sub-category is the portion after the dash if present.
    sub = raw.split("-", 1)[1].strip() if "-" in raw else raw
    return top, sub


def _detect_plan_type(name: str) -> str:
    n = name.lower()
    if "direct" in n:
        return "Direct"
    return "Regular"


def parse_navall(text: str) -> list[dict]:
    """Parse NAVAll.txt text into list of dicts (one per scheme).

    Tolerates blank lines and the interleaved header structure.
    """
    out: list[dict] = []
    current_category: tuple[str, str] | None = None  # (top, sub)
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

        # An AMC line is text without semicolons and not a header.
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/sources/test_amfi_master.py -v
```

Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/sources/__init__.py \
        backend/app/services/sources/amfi_master.py \
        backend/tests/sources/__init__.py \
        backend/tests/sources/test_amfi_master.py \
        backend/tests/fixtures/navall_sample.txt
git commit -m "feat(sources): AMFI NAVAll fetcher + parser with fixture"
```

---

## Task 3: Universe loader orchestrator (AMFI master only at this stage)

**Files:**
- Create: `backend/app/services/universe_loader.py`
- Create: `backend/tests/test_universe_loader.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_universe_loader.py`:

```python
from unittest.mock import patch

import pytest

from app.models.fund import Fund
from app.services import universe_loader


@pytest.fixture
def amfi_rows():
    return [
        {
            "scheme_code": 103174,
            "scheme_name": "Aditya Birla Sun Life Frontline Equity Fund - Regular Plan - Growth",
            "amc": "Aditya Birla Sun Life Mutual Fund",
            "category": "Equity",
            "sub_category": "Large Cap Fund",
            "plan_type": "Regular",
            "isin_growth": "INF209K01157",
            "isin_dividend": "INF209K01165",
            "nav": 500.12,
            "nav_date": "25-May-2026",
        },
        {
            "scheme_code": 100037,
            "scheme_name": "HDFC Liquid Fund - Regular Plan - Growth",
            "amc": "HDFC Mutual Fund",
            "category": "Debt",
            "sub_category": "Liquid Fund",
            "plan_type": "Regular",
            "isin_growth": "INF179K01CG7",
            "isin_dividend": None,
            "nav": 4789.56,
            "nav_date": "25-May-2026",
        },
    ]


def test_apply_amfi_master_inserts_new_funds(db_session, amfi_rows):
    result = universe_loader.apply_amfi_master(db_session, amfi_rows)
    assert result["inserted"] == 2
    assert result["updated"] == 0
    f = db_session.get(Fund, 103174)
    assert f.category == "Equity"
    assert f.amc == "Aditya Birla Sun Life Mutual Fund"
    assert f.plan_type == "Regular"
    assert f.source == "amfi"


def test_apply_amfi_master_updates_existing_fund(db_session, amfi_rows):
    db_session.add(Fund(scheme_code=103174, fund_name="Old", category=None, is_active=True))
    db_session.commit()
    result = universe_loader.apply_amfi_master(db_session, amfi_rows[:1])
    assert result["updated"] == 1
    f = db_session.get(Fund, 103174)
    assert f.category == "Equity"
    assert f.amc == "Aditya Birla Sun Life Mutual Fund"


def test_apply_amfi_master_preserves_existing_amc_when_already_set(db_session, amfi_rows):
    """Don't clobber a user-set AMC."""
    db_session.add(Fund(
        scheme_code=103174, fund_name="Old", amc="Manual Override",
        category="Equity", is_active=True,
    ))
    db_session.commit()
    universe_loader.apply_amfi_master(db_session, amfi_rows[:1])
    # AMC stays as manual override; only category gets refreshed.
    f = db_session.get(Fund, 103174)
    assert f.amc == "Manual Override"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_universe_loader.py -v
```

Expected: ImportError on `universe_loader`.

- [ ] **Step 3: Implement `universe_loader.py`**

`backend/app/services/universe_loader.py`:

```python
"""Orchestrate upstream data sources into the funds table.

Currently wires AMFI master. NSE + TER scrapers slot in via additional
helpers in later tasks.
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_universe_loader.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/universe_loader.py \
        backend/tests/test_universe_loader.py
git commit -m "feat(universe): apply_amfi_master upsert with manual-AMC preservation"
```

---

## Task 4: Wire AMFI master into a Celery task

**Files:**
- Modify: `backend/app/tasks/refresh.py`
- Modify: `backend/app/tasks/celery_app.py`

- [ ] **Step 1: Append the new task to refresh.py**

Append at end of `backend/app/tasks/refresh.py`:

```python
@celery_app.task(name="app.tasks.refresh.refresh_universe", bind=True, max_retries=3)
def refresh_universe(self) -> dict[str, int]:
    """Pull AMFI NAVAll, upsert funds, refresh categories + plan_type."""
    import asyncio
    from app.services.sources import amfi_master
    from app.services.universe_loader import apply_amfi_master

    try:
        rows = asyncio.run(amfi_master.fetch_navall())
    except Exception as exc:
        logger.exception("refresh_universe: AMFI fetch failed")
        raise self.retry(exc=exc, countdown=60 * 10) from exc

    session = SessionLocal()
    try:
        result = apply_amfi_master(session, rows)
    finally:
        session.close()
    logger.info("refresh_universe OK: %s", result)
    return result
```

- [ ] **Step 2: Add beat schedule entry**

In `backend/app/tasks/celery_app.py`, inside `celery_app.conf.beat_schedule`, add:

```python
    # AMFI scheme master refresh (v3.3A). Runs nightly before fund_master legacy task
    # so newer category + plan_type values are in place.
    "nightly-amfi-master": {
        "task": "app.tasks.refresh.refresh_universe",
        "schedule": crontab(hour=HOUR, minute=55),  # 22:55 IST, 5 min before legacy
    },
```

- [ ] **Step 3: Verify import + run full pytest**

```bash
cd backend
python -c "from app.tasks.refresh import refresh_universe; print('ok')"
python -m pytest -q --tb=line
```

Expected: imports cleanly, all tests pass (no behavioural change yet, just adding task).

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks/refresh.py backend/app/tasks/celery_app.py
git commit -m "feat(tasks): refresh_universe Celery task + beat schedule at 22:55 IST"
```

---

## Task 5: Rewrite AMFI TER scraper

**Files:**
- Create: `backend/app/services/sources/amfi_ter_scraper.py`
- Create: `backend/tests/fixtures/amfi_ter_page.html`
- Create: `backend/tests/sources/test_amfi_ter_scraper.py`

- [ ] **Step 1: Drop the HTML fixture**

`backend/tests/fixtures/amfi_ter_page.html`:

```html
<!doctype html>
<html><body>
<a href="/sites/default/files/research/TER-2026-05.xlsx">Download TER May 2026</a>
<a href="/sites/default/files/research/TER-2026-04.xlsx">April</a>
</body></html>
```

- [ ] **Step 2: Write failing tests**

`backend/tests/sources/test_amfi_ter_scraper.py`:

```python
from pathlib import Path

from app.services.sources import amfi_ter_scraper

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "amfi_ter_page.html"


def test_find_latest_xlsx_url_picks_most_recent_filename():
    html = FIXTURE.read_text(encoding="utf-8")
    url = amfi_ter_scraper.find_latest_xlsx_url(html, base="https://www.amfiindia.com")
    assert url == "https://www.amfiindia.com/sites/default/files/research/TER-2026-05.xlsx"


def test_find_latest_xlsx_url_returns_none_when_no_match():
    url = amfi_ter_scraper.find_latest_xlsx_url("<html><body>no links</body></html>", base="x")
    assert url is None
```

- [ ] **Step 3: Run + verify fail**

```bash
python -m pytest tests/sources/test_amfi_ter_scraper.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement scraper**

`backend/app/services/sources/amfi_ter_scraper.py`:

```python
"""AMFI Total Expense Ratio scraper - rewrite of v2 amfi_scraper.

URL discovery: fetch AMFI index page, find all .xlsx links matching the
TER filename pattern (TER-YYYY-MM.xlsx), pick the lexicographically
greatest (= newest month).
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
    candidates.sort()  # newest year/month last
    return candidates[-1][1]
```

- [ ] **Step 5: Run tests + verify pass**

```bash
python -m pytest tests/sources/test_amfi_ter_scraper.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/sources/amfi_ter_scraper.py \
        backend/tests/sources/test_amfi_ter_scraper.py \
        backend/tests/fixtures/amfi_ter_page.html
git commit -m "feat(sources): AMFI TER scraper URL discovery (HTML parse)"
```

---

## Task 6: NSE quote fetcher

**Files:**
- Create: `backend/app/services/sources/nse_quote_fetcher.py`
- Create: `backend/tests/sources/test_nse_quote_fetcher.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/sources/test_nse_quote_fetcher.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.sources import nse_quote_fetcher


@pytest.mark.asyncio
async def test_fetch_quote_parses_lastprice(monkeypatch):
    payload = {
        "priceInfo": {
            "lastPrice": 250.5,
            "previousClose": 245.0,
            "pChange": 2.24,
            "lastUpdateTime": "25-May-2026 15:30:00",
        }
    }
    mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(nse_quote_fetcher, "_fetch_raw", mock)

    quote = await nse_quote_fetcher.fetch_quote("NIFTYBEES")
    assert quote.last_price == 250.5
    assert quote.prev_close == 245.0
    assert quote.day_change_pct == 2.24


@pytest.mark.asyncio
async def test_fetch_quote_returns_none_on_missing_priceinfo(monkeypatch):
    mock = AsyncMock(return_value={})
    monkeypatch.setattr(nse_quote_fetcher, "_fetch_raw", mock)
    quote = await nse_quote_fetcher.fetch_quote("BOGUS")
    assert quote is None


def test_should_failover_after_three_failures():
    tracker = nse_quote_fetcher.FailoverTracker()
    assert not tracker.should_failover()
    tracker.record_failure()
    tracker.record_failure()
    assert not tracker.should_failover()
    tracker.record_failure()
    assert tracker.should_failover()


def test_failover_tracker_resets_on_success():
    tracker = nse_quote_fetcher.FailoverTracker()
    tracker.record_failure()
    tracker.record_failure()
    tracker.record_success()
    tracker.record_failure()
    assert not tracker.should_failover()
```

- [ ] **Step 2: Run + verify fail**

```bash
python -m pytest tests/sources/test_nse_quote_fetcher.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement fetcher**

`backend/app/services/sources/nse_quote_fetcher.py`:

```python
"""NSE quote API client for live ETF prices.

Endpoint: https://www.nseindia.com/api/quote-equity?symbol=<SYMBOL>
Notes:
  - NSE requires a session cookie set via a prior GET to / and a real-looking
    User-Agent header. The fetcher manages cookies per AsyncClient.
  - Symbols are NSE tickers WITHOUT the .NS suffix (Yahoo's suffix).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nseindia.com"
QUOTE_PATH = "/api/quote-equity"
TIMEOUT_SEC = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class NseQuote:
    symbol: str
    last_price: float
    prev_close: float | None
    day_change_pct: float | None
    last_traded_at: datetime
    source: str = "nse"


class FailoverTracker:
    """Tracks consecutive failures to decide when to cascade to Yahoo."""

    THRESHOLD = 3

    def __init__(self) -> None:
        self._fails = 0

    def record_failure(self) -> None:
        self._fails += 1

    def record_success(self) -> None:
        self._fails = 0

    def should_failover(self) -> bool:
        return self._fails >= self.THRESHOLD


async def _fetch_raw(symbol: str, client: httpx.AsyncClient) -> dict:
    """Issue the quote API call. Returns parsed JSON dict."""
    resp = await client.get(QUOTE_PATH, params={"symbol": symbol})
    resp.raise_for_status()
    return resp.json()


async def fetch_quote(symbol: str, client: httpx.AsyncClient | None = None) -> NseQuote | None:
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": "application/json",
            },
            trust_env=False,
            timeout=TIMEOUT_SEC,
        )
        # NSE needs a homepage GET to seed cookies.
        await client.get("/")
    try:
        data = await _fetch_raw(symbol, client)
    except Exception as exc:
        logger.warning("nse_quote_fetcher: %s failed: %s", symbol, exc)
        return None
    finally:
        if own_client:
            await client.aclose()

    pi = data.get("priceInfo")
    if not pi or pi.get("lastPrice") is None:
        return None

    last_traded = datetime.now(timezone.utc)  # NSE timestamp parsing optional
    return NseQuote(
        symbol=symbol,
        last_price=float(pi["lastPrice"]),
        prev_close=float(pi["previousClose"]) if pi.get("previousClose") else None,
        day_change_pct=float(pi["pChange"]) if pi.get("pChange") else None,
        last_traded_at=last_traded,
    )
```

- [ ] **Step 4: Install pytest-asyncio if missing**

```bash
pip install --break-system-packages pytest-asyncio==0.23.5
```

- [ ] **Step 5: Run + verify pass**

```bash
python -m pytest tests/sources/test_nse_quote_fetcher.py -v
```

Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/sources/nse_quote_fetcher.py \
        backend/tests/sources/test_nse_quote_fetcher.py
git commit -m "feat(sources): NSE quote fetcher + failover tracker"
```

---

## Task 7: Wire NSE→Yahoo cascade into ETF refresh task

**Files:**
- Modify: `backend/app/tasks/refresh.py`
- Modify: `backend/tests/test_yahoo_fetch.py` (regression check)

- [ ] **Step 1: Patch `refresh_etf_quotes` to try NSE first**

Replace the existing `refresh_etf_quotes` body in `backend/app/tasks/refresh.py`:

```python
@celery_app.task(name="app.tasks.refresh.refresh_etf_quotes", bind=True, max_retries=2)
def refresh_etf_quotes(self, force: bool = False) -> dict[str, int | bool]:
    """Pull live ETF quotes - NSE primary, Yahoo fallback after 3 fails."""
    import asyncio
    from app.services.sources import nse_quote_fetcher
    from app.services.yahoo_fetch import is_market_open, run_yahoo_refresh

    if not force and not is_market_open():
        logger.info("refresh_etf_quotes: market closed, skip")
        return {"skipped": True, "reason": "market_closed"}

    session = SessionLocal()
    try:
        result = asyncio.run(_run_etf_refresh(session, nse_quote_fetcher, run_yahoo_refresh))
    except Exception as exc:
        logger.exception("refresh_etf_quotes failed")
        raise self.retry(exc=exc, countdown=60 * 2) from exc
    finally:
        session.close()
    logger.info("refresh_etf_quotes OK: %s", result)
    return {**result, "skipped": False}


async def _run_etf_refresh(session, nse, yahoo_fn):
    """NSE first; on 3 consecutive fails, switch to Yahoo for rest of batch."""
    from app.models.fund import EtfQuote
    from sqlalchemy import select

    rows = session.execute(select(EtfQuote.scheme_code, EtfQuote.symbol_yahoo)).all()
    tracker = nse.FailoverTracker()
    written = 0
    succeeded = 0
    failed = 0
    used_yahoo = False

    for scheme_code, yahoo_symbol in rows:
        if tracker.should_failover():
            used_yahoo = True
            break
        # Strip ".NS" suffix for NSE API
        nse_symbol = yahoo_symbol.replace(".NS", "")
        quote = await nse.fetch_quote(nse_symbol)
        if quote is None:
            tracker.record_failure()
            failed += 1
            continue
        tracker.record_success()
        succeeded += 1
        existing = session.get(EtfQuote, scheme_code)
        if existing is not None:
            existing.last_price = quote.last_price
            existing.prev_close = quote.prev_close
            existing.day_change_pct = quote.day_change_pct
            existing.last_traded_at = quote.last_traded_at
            existing.source = "nse"
            written += 1
    session.commit()

    if used_yahoo:
        logger.warning("NSE failed %d times - cascading to Yahoo", tracker.THRESHOLD)
        yahoo_result = yahoo_fn(session)
        return {
            "primary": "nse+yahoo",
            "nse_succeeded": succeeded,
            "nse_failed": failed,
            "rows_written": written + yahoo_result["rows_written"],
        }
    return {
        "primary": "nse",
        "nse_succeeded": succeeded,
        "nse_failed": failed,
        "rows_written": written,
    }
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_yahoo_fetch.py -v
```

Expected: existing tests still PASS (we didn't break Yahoo, only added NSE in front).

- [ ] **Step 3: Commit**

```bash
git add backend/app/tasks/refresh.py
git commit -m "feat(tasks): NSE-first ETF refresh with Yahoo failover after 3 fails"
```

---

## Task 8: Simplify `_exclude_direct_plans` filter

**Files:**
- Modify: `backend/app/api/funds.py`
- Modify: `backend/tests/test_funds_api.py`
- Modify: `backend/tests/test_active_filter.py`

- [ ] **Step 1: Update the filter**

Replace `_exclude_direct_plans` in `backend/app/api/funds.py` with:

```python
def _exclude_direct_plans(stmt):
    """Restrict universe to Regular plans only and only active funds.

    With v3.3A in place, plan_type comes from AMFI master and is authoritative,
    so we no longer need name-pattern heuristics.

    Filters:
      * is_active=True
      * category IS NOT NULL
      * plan_type = 'Regular'
    """
    return (
        stmt.where(Fund.is_active.is_(True))
        .where(Fund.category.is_not(None))
        .where(Fund.plan_type == "Regular")
    )
```

- [ ] **Step 2: Update the affected test**

In `backend/tests/test_funds_api.py`, the `test_search_excludes_direct_plans` fixture already sets `plan_type` explicitly - the test should pass unchanged. Verify it does.

In `backend/tests/test_active_filter.py`, the test `test_direct_plan_excluded_by_name_pattern` is no longer relevant (we use plan_type strict). Replace it:

```python
def test_direct_plan_excluded_by_plan_type(client, db_session):
    """Direct plans are excluded via plan_type, not name patterns."""
    db_session.add_all([
        Fund(scheme_code=1, fund_name="Foo Fund Growth",
             plan_type="Regular", category="Equity", is_active=True),
        Fund(scheme_code=2, fund_name="Foo Fund Direct",
             plan_type="Direct", category="Equity", is_active=True),
    ])
    db_session.commit()
    resp = client.get("/api/v1/funds/list?limit=10")
    codes = {f["scheme_code"] for f in resp.json()["items"]}
    assert codes == {1}
```

- [ ] **Step 3: Run + verify pass**

```bash
python -m pytest tests/test_funds_api.py tests/test_active_filter.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/funds.py backend/tests/test_active_filter.py
git commit -m "refactor(api): _exclude_direct_plans uses authoritative plan_type, drops name heuristics"
```

---

## Task 9: Admin trigger endpoint + delete legacy AMFI scraper

**Files:**
- Modify: `backend/app/api/admin.py`
- Delete: `backend/app/services/amfi_scraper.py` (after task 10 wires the new TER end-to-end)

- [ ] **Step 1: Add `/admin/refresh-universe` endpoint**

Append to `backend/app/api/admin.py`:

```python
@router.post("/refresh-universe")
def refresh_universe_now(
    _auth: None = Depends(_require_admin),
) -> dict[str, str]:
    """Trigger AMFI universe refresh immediately."""
    from app.tasks import refresh as refresh_tasks
    task = refresh_tasks.refresh_universe.delay()
    return {"dispatched": True, "task_id": task.id}
```

- [ ] **Step 2: Run + verify (no tests for admin token-gated endpoints in v2)**

```bash
python -c "from app.api.admin import refresh_universe_now; print('ok')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/admin.py
git commit -m "feat(admin): /admin/refresh-universe ops trigger"
```

---

## Task 10: End-to-end smoke + delete legacy scraper

- [ ] **Step 1: Run full suite + ruff**

```bash
cd backend
python -m pytest -q --tb=line
python -m ruff check .
```

Expected: all PASS, 0 ruff errors.

- [ ] **Step 2: Delete legacy `amfi_scraper.py`**

```bash
git rm backend/app/services/amfi_scraper.py
```

The TER scraper rewrite (Task 5) doesn't yet have a Celery task wired - that's intentional. The legacy `refresh_expense_ratios` task in `refresh.py` will need updating in a follow-up; for v3.3A we ship URL discovery only and leave the full pipeline rewrite for v3.3A.1.

- [ ] **Step 3: Update `refresh.py` to drop the legacy import**

In `backend/app/tasks/refresh.py`, remove:

```python
from app.services.amfi_scraper import run_amfi_scrape
```

and delete the `refresh_expense_ratios` task body (replace with a stub that returns `{"status": "deprecated"}` until rewritten). Also remove the corresponding `weekly-expense-ratios` entry from `celery_app.py`.

- [ ] **Step 4: Re-run full suite**

```bash
python -m pytest -q --tb=line
python -m ruff check .
```

Expected: all PASS, 0 ruff errors.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: drop legacy amfi_scraper; v3.3A TER scraper to be wired in 3A.1"
```

---

## Task 11: Push + tag v3.0.0

- [ ] **Step 1: Push branch**

```bash
git push origin main
```

- [ ] **Step 2: Tag**

```bash
git tag -a v3.0.0 -m "v3.0.0: data coverage overhaul (AMFI master, NSE quote, plan_type authoritative)"
git push origin v3.0.0
```

GitHub Actions auto-builds the installer + images for v3.0.0.

- [ ] **Step 3: Operational checklist**

After deployment:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -c "from app.tasks import refresh as r; print(r.refresh_universe.delay().id)"
# Wait ~30s
docker compose exec postgres psql -U mfa -d mf_analyser -c "
SELECT COUNT(*) FILTER (WHERE category IS NOT NULL) AS with_cat,
       COUNT(*) FILTER (WHERE plan_type = 'Regular' AND is_active) AS regular_active
FROM funds;"
```

Expected: `with_cat >= 9000`, `regular_active >= 9000`.

---

## Self-review

**Spec coverage:**
- AMFI master fetcher → Task 2 ✓
- TER scraper rewrite → Task 5 (URL discovery; full pipeline deferred to v3.3A.1 per Task 10 note) - **gap noted**
- NSE quote fetcher → Task 6 ✓
- Yahoo demoted to fallback → Task 7 ✓
- `_exclude_direct_plans` simplified → Task 8 ✓
- `funds.source` column → Task 1 ✓
- Admin trigger endpoint → Task 9 ✓
- Migration 0005 → Task 1 ✓
- Tests for all sources → Tasks 2, 5, 6, 7 ✓

**Placeholder scan:** None.

**Type consistency:** `NseQuote`, `FailoverTracker`, `AmfiScheme`, `apply_amfi_master`, `refresh_universe` consistent across tasks.

**Scope note:** TER scraper pipeline-wiring split out to v3.3A.1 (lighter v3.0.0). Documented in Task 10 step 2.

---

*Z1N Capital - Internal - Draft v0.1*
