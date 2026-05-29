# v3.3A - Data Coverage Overhaul - Design Spec

**Author:** Z1N engineering
**Date:** 2026-05-21
**Status:** Approved, ready for implementation plan

## Goal

Replace v2's scattered upstream data sources (MFApi list + NSE NMF II XLS +
broken AMFI scraper + Yahoo Finance) with a small set of authoritative free
sources that fully populate `funds.category`, `funds.expense_ratio`,
`funds.plan_type` and `etf_quotes.last_price` without name-pattern guessing.

Single-pain-point root cause: v2 sources are incomplete or fragile. v3.3A
fixes that by switching to AMFI's official scheme master as primary, with
the NSE official quote API for ETFs.

## Success criteria

- 9,000+ funds have `category` populated (vs ~7,027 today)
- 5,000+ funds have `expense_ratio` populated (vs 0 today)
- ETF quote refresh succeeds 95%+ during NSE market hours
- Direct plans constitute <1% of UI-visible universe (today: leaks through
  name-pattern heuristic)
- All existing v2 features unchanged (scoring, calculator, exports, admin)
- All existing tests pass; new tests added for each source

## Architecture

New umbrella module:

```
app/services/sources/
    __init__.py
    amfi_master.py        - fetch + parse NAVAll.txt (~9k Regular plans)
    amfi_ter_scraper.py   - rewrite of amfi_scraper.py for current AMFI page
    nse_quote_fetcher.py  - live ETF quotes via NSE public API
app/services/universe_loader.py
    - thin orchestrator that wires the three sources into the funds table
```

Existing files modified:

- `app/tasks/refresh.py` - tasks delegate to `universe_loader`. Old inline
  ingestion logic removed.
- `app/services/yahoo_fetch.py` - kept but demoted to FALLBACK only.
  Called by `nse_quote_fetcher` when NSE fails 3 consecutive calls.
- `app/services/amfi_scraper.py` - DELETED. Replaced by
  `sources/amfi_ter_scraper.py` (rewrite, not refactor - URL discovery
  logic needs new approach).
- `app/api/funds.py` `_exclude_direct_plans` - simplified to
  `is_active AND category IS NOT NULL AND plan_type = 'Regular'`. Name
  patterns and Direct heuristics removed because plan_type is now
  authoritative from AMFI master.

## Data sources

### 1. AMFI scheme master (`NAVAll.txt`)

- **URL:** `https://www.amfiindia.com/spages/NAVAll.txt`
- **Format:** Pipe-delimited text, ~9,000 active Regular plans
- **Updated:** Daily (next-business-day NAV)
- **Fields parsed:**
  - `scheme_code` (AMFI code, integer)
  - `scheme_name`
  - `isin_growth`, `isin_dividend`
  - `nav`, `nav_date` (used as latest-NAV check)
- **Header lines** separate sections. Section headers carry:
  - AMC name (e.g. "Aditya Birla Sun Life Mutual Fund")
  - Scheme category (e.g. "Open Ended Schemes (Equity Scheme - Large Cap Fund)")
  - Plan type can be inferred from `scheme_name` ("Direct"/"Regular") OR
    accepted as Regular when not stated (per AMFI convention).

### 2. AMFI TER scraper

- **Index URL:** `https://www.amfiindia.com/research-information/other-data/total-expense-ratio-of-mutual-fund-schemes`
- Approach: BeautifulSoup scrape the page for a `.xlsx` link, download the
  latest Excel, parse with `openpyxl`.
- Column finder unchanged from v2 (fuzzy match on "scheme code" + "expense
  ratio") - but the URL discovery is rewritten to handle current page
  layout.
- Fallback: admin CSV upload endpoint (already exists in v2).

### 3. NSE quote fetcher

- **Base URL:** `https://www.nseindia.com/api/quote-equity?symbol=NIFTYBEES`
- **Auth:** None, but NSE requires a session cookie set via a first GET to
  `/` and proper User-Agent + Accept-Language headers. The fetcher manages
  cookies via a single `httpx.AsyncClient` per refresh batch.
- **Batch policy:** sequential, 200ms delay between symbols, to stay
  polite. ~50 ETFs in symbol map = ~10s per refresh cycle.
- **Returned fields:** `lastPrice`, `previousClose`, `pChange`,
  `lastUpdateTime`.

## Data flow

```
Nightly 23:00 IST (beat schedule):
    universe_loader.refresh_universe()
      |- amfi_master.fetch_navall()
      |    upsert funds (scheme_code, scheme_name, amc, category,
      |                  sub_category, plan_type)
      |- mark schemes missing from NAVAll for 3 consecutive days
      |    as is_active = False
      |- cache.invalidate("funds:")

23:10 IST: refresh_nav_history (unchanged from v2)
00:30 IST: compute_metrics (unchanged)
00:45 IST: compute_benchmarks
00:50 IST: compute_scores
00:55 IST: deactivate_stale_funds (already bidirectional from H.4)

Sunday 04:00 IST:
    amfi_ter_scraper.run() -> funds.expense_ratio

Every 5 min, Mon-Fri 09:15-15:30 IST:
    nse_quote_fetcher.fetch_all()
      |- For each etf_quotes row -> NSE API call
      |- On 3 consecutive failures -> fall back to yahoo_fetch
      |- Upsert etf_quotes (sets source = 'nse' or 'yahoo')
```

## Schema changes

Single migration `0005_funds_source.py`:

```sql
ALTER TABLE funds ADD COLUMN source VARCHAR(32) NULL;
-- Backfill existing rows to 'mfapi' (their original origin):
UPDATE funds SET source = 'mfapi' WHERE source IS NULL;
```

`source` is informational (debug aid for the admin page), not used by
filters. Possible values: `amfi`, `nse_master`, `mfapi`, `manual_upload`.

## API changes

None to existing endpoints. One new admin endpoint for ops:

- `POST /api/v1/admin/refresh-universe` - manual trigger, gated by
  `X-Admin-Token`. Returns dispatched Celery task IDs (same pattern as
  existing `/admin/run-cascade`).

## Error handling

| Source | Failure | Behaviour |
|--------|---------|-----------|
| `amfi_master` | HTTP 5xx, parse error, empty payload | Keep previous run's `funds` rows. Retry hourly. Health probe drops to `warn`. |
| `amfi_master` | A scheme disappears for 1-2 days | NO action. Transient outages are common. |
| `amfi_master` | A scheme disappears for >= 3 consecutive days | `is_active = False`. Bidirectional - reactivates on reappearance. |
| `amfi_ter_scraper` | URL changed, parser broke | `status=error` in task result. Existing `expense_ratio` values untouched. Admin notified. |
| `nse_quote_fetcher` | Single symbol fails | Move to next; record per-symbol failure count. |
| `nse_quote_fetcher` | 3 consecutive symbols fail | Switch over to `yahoo_fetch` for remainder of batch. Log a single warning. Reset on next batch. |
| Both NSE + Yahoo fail | All ETF rows stay flagged stale via `is_stale()` check (already in v2). |

## Testing

New test files:

- `tests/sources/test_amfi_master.py` - mocked NAVAll fixture (text file in
  `tests/fixtures/navall_sample.txt`), assert parsed dict shape, header
  section parsing, AMC carryover across rows.
- `tests/sources/test_amfi_ter_scraper.py` - mocked AMFI index page (HTML
  fixture), assert URL discovery + Excel parse handle layout drift.
- `tests/sources/test_nse_quote_fetcher.py` - monkeypatched `httpx`
  response, assert fail-counter logic + Yahoo cascade.
- `tests/test_universe_loader.py` - integration: feeds all three sources
  through the orchestrator, verifies `funds`/`etf_quotes` end state.
- `tests/test_funds_api.py` - update `test_search_excludes_direct_plans` to
  reflect the simpler filter (`plan_type='Regular'` strict, no name
  patterns).

Acceptance gates:

- All existing tests still pass after `_exclude_direct_plans` simplification.
- New tests achieve >=85% coverage on the new modules.
- One smoke-test fixture (`navall_sample.txt`) covers 20 representative
  schemes spanning Equity / Debt / Hybrid / Other categories and both
  Regular / Direct plans.

## Migration plan / rollout

1. Land new sources behind feature flag `USE_AMFI_MASTER` (env var,
   default `false` in v2.x).
2. Run shadow load: nightly fetch NAVAll, write to a new
   `funds_amfi_shadow` table. Compare counts against existing `funds`
   for one week.
3. Flip the flag to `true`. Switch task wiring. Drop shadow table.
4. Tag `v3.0.0`. Bake images, publish installer.

Time estimate: 10 working days. Two for shadow validation week.

## What's not in 3A

- Portfolio upload (3B)
- Login / users (3C)
- Tauri desktop (3D)
- Paid feed integration
- AMFI scheme master full schema (only the columns we use today)
- Internationalisation / non-English fund names

## Acceptance checklist

- [ ] AMFI NAVAll fetch succeeds + upserts >= 8,500 funds
- [ ] `funds.category` non-null on >= 9,000 active funds
- [ ] `funds.expense_ratio` non-null on >= 5,000 active funds
- [ ] NSE quote fetcher returns `lastPrice` for >= 8/10 sample ETFs
- [ ] `_exclude_direct_plans` simplified; v2 name-pattern code deleted
- [ ] All v2 endpoints return identical shapes
- [ ] 0 ruff errors, 0 mypy errors
- [ ] All v2 tests + new tests pass

---

*Z1N Capital - Internal - Draft v0.1*
