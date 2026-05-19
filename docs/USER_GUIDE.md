# Z1N MF Analyser - User Guide (v2)

A friendly walkthrough for Z1N Capital advisors. Written for v2.0.0.

---

## What is this?

The MF Analyser is an internal research tool covering ~9,000 Indian
mutual funds plus ~50 NSE-listed ETFs. It ingests official AMFI data
daily, computes risk-adjusted scores against peers in the same
category, and lets you compare funds, project SIP / lumpsum returns,
and export polished factsheets.

It is **research, not advice**. Past performance does not predict
future returns.

---

## First-time setup

The first time you open the app, a "Setting up your fund universe"
modal appears. It downloads the AMFI fund master, ~3 years of NAV
history, and computes risk-adjusted scores. This usually takes 60-90
minutes and runs in the background. You can leave the tab open or
come back later; new funds and scores appear as the cascade
progresses.

A small status dot in the top-right shows current data freshness:

- Green: data refreshed in the last 12 hours
- Yellow: data is 12-48 hours old (still usable)
- Red: data is more than 48 hours old or a service is down

Click the dot for a detailed breakdown across DB, Redis, Celery,
nightly refresh, and ETF live quotes.

---

## The 4 screens

### 1. Discover (search + browse)

Type any fund name, AMC, or category. The list shows the composite
score (0-100), 1y / 3y / 5y CAGR, annual cost, and AUM. Filter by
category via the dropdown.

### 2. Fund Detail

Click any fund to open its dedicated page:

- Header with composite score gauge and quick-action buttons
  (Add to Compare, Calculator, Export factsheet).
- Snapshot card (NAV, cost, exit fee, AUM, plan type).
- Returns table (1y / 3y / 5y / 10y, annualised).
- Risk profile (Sharpe ratio, worst drawdown, recovery time).
- Recent momentum (3m / 6m point-to-point).
- Full NAV history chart with range selector.

For ETFs, an extra live-price ticker appears below the header,
showing current price + today's change.

### 3. Compare

Pick 2-5 funds (use the "Add to Compare" button on any fund detail
page). The Compare page shows:

- An overlaid normalised performance chart (rebased to 100).
- Score gauges and key metrics in a side-by-side matrix.
- Best number in each row is highlighted green; worst is red.

Click "Export comparison" to download as Word or PDF.

### 4. Calculator

Pick a fund, enter SIP amount + tenure (or lumpsum amount + tenure),
and the page returns two numbers:

- **Calculated return** - deterministic projection using historical CAGR.
- **Projected return** - median (P50) of a 2,000-path Monte Carlo
  simulation based on the fund's historical volatility.

Below the result card, a year-by-year breakdown shows pessimistic
(P10), median (P50), and optimistic (P90) outcomes, plus the
implied CAGR for each percentile.

---

## ETF live prices

For Exchange-Traded Funds, the Fund Detail page shows a live
intraday price ticker in addition to NAV. Source: Yahoo Finance.

- Updates every 5 minutes during NSE market hours (Mon-Fri 09:15-15:30 IST).
- Browser polls every 60 seconds while page is open.
- Green up-arrow or red down-arrow shows today's percentage change.
- Amber "Live data is stale" banner appears if Yahoo has not refreshed
  in the last 15 minutes. NAV (end-of-day) is still shown as the
  primary value.

To add or update ETFs in the universe, edit
`backend/data/etf_symbol_map.csv` (columns: scheme_code, symbol_yahoo,
name) and re-run `python -m app.scripts.load_etf_map`.

---

## Exporting reports

Two report types are available:

- **Per-fund factsheet** - on any Fund Detail page, click "Export
  factsheet" and choose Word (.docx) or PDF. Includes snapshot,
  returns table, risk profile, score breakdown, and the NAV history
  chart.
- **Comparison report** - on the Compare page (after picking 2-5 funds),
  click "Export comparison" and choose Word or PDF. Includes a
  side-by-side metrics matrix and a normalised overlay chart of the
  funds.

PDF generation requires LibreOffice on the server (bundled in the
Docker image). If it's missing, the API returns 503 and the UI falls
back to a "Try Word format" message - .docx will always work.

All reports include a Z1N Capital header, a "not investment advice"
disclaimer in the footer, and a UTC generation timestamp.

---

## Admin page

The hidden `/admin` route (open by typing `/admin` in the URL) shows
system health and lets an authorised user trigger the nightly refresh
cascade manually. Requires the `ADMIN_TOKEN` value from the server's
`.env` file. Use this after an outage or to force a re-score.

---

## How the score works

Composite score (0-100) is a weighted blend of 10 sub-scores, each
computed as the fund's percentile against peers in the same Sub-
Category. Weights (sum to 100):

| Factor                  | Weight |
|-------------------------|--------|
| Risk-adjusted return (Sharpe) | 25 |
| 5-year CAGR             | 15 |
| 3-year CAGR             | 12 |
| 1-year CAGR             | 8  |
| Consistency (rolling-return stability) | 10 |
| Max drawdown            | 8  |
| Expense ratio (lower better) | 7  |
| Recent momentum (3-6m)  | 5  |
| AUM stability           | 5  |
| Exit-load penalty       | 5  |

A score of 80+ means the fund is in the top quintile of its peer set
across these dimensions. A score below 40 is a warning - the fund
under-performs peers on multiple axes.

---

## Caveats

- Mutual fund returns are not guaranteed; the analyser is a research
  tool, not a recommendation engine.
- The Monte Carlo simulation assumes log-normal returns calibrated to
  the fund's own history; black-swan events are not modelled.
- Live ETF prices come from Yahoo Finance (unofficial API); rate
  limits or upstream outages will trigger the stale-data banner.
- Direct plans are excluded by default to keep the universe consistent
  for advisory use cases.

---

## Troubleshooting

**The first-boot modal sits at "0 funds" for a long time**
Check that Docker Desktop is running and that the backend container
is healthy. From the tray icon: View Logs. If the launcher log shows
repeated MFApi timeouts, your network may be blocking
`api.mfapi.in`.

**Live ETF price won't update**
Yahoo's unofficial endpoint occasionally rate-limits. The amber
"stale" banner means the cached value is older than 15 minutes -
just wait, or click "Run cascade now" on the admin page.

**PDF export fails with a 503 message**
LibreOffice (`soffice`) isn't on PATH on the backend host. The
Docker image already includes it; for non-Docker installs see
`docs/OPS_RUNBOOK.md`.

**Composite scores look stuck**
Open `/admin` and check the "Scores computed" count. If it's lower
than expected, trigger the cascade and wait ~2 minutes for the
scoring task to finish.

**"Invalid admin token" on the admin page**
Read the `ADMIN_TOKEN` value from your server `.env` file (under
`%LOCALAPPDATA%\Z1NMFAnalyser\payload\` on Windows). Tokens are
session-scoped in the browser.
