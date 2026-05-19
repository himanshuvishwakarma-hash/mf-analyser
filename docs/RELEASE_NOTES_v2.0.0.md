# Z1N MF Analyser v2.0.0 - Release Notes

**Released:** May 2026
**Audience:** Internal advisors at Z1N Capital

## What's new

v2 turns the analyser from a developer-mode demo into something an
advisor can install, open, and use day-to-day.

### Install once, double-click forever
A new Windows installer (`Z1NMFAnalyser-Setup-v2.0.0.exe`) bundles
everything you need. After install, a small Z1N icon lives in the
system tray. Right-click for Open Dashboard / View Logs / Restart /
Quit. No PowerShell, no `docker compose` commands.

### First-boot is friendly
On first launch the app downloads the full Indian fund universe and
~3 years of NAV history in the background. A progress modal shows
exactly what's happening; you can use the dashboard the moment data
starts arriving.

### Expense ratios are now filled in
A weekly job pulls the official AMFI Total Expense Ratio sheet and
back-fills every fund's annual cost. If AMFI is down or the sheet
shifts shape, you can upload a corrected CSV via the admin page.

### Live ETF prices
For Exchange-Traded Funds, the detail page now shows an intraday
price and today's percentage change (sourced from Yahoo Finance).
Updates every 5 minutes during NSE market hours.

### One-click exports
Every fund detail page has an Export button. Get a polished Z1N
Capital factsheet as Word or PDF in two clicks. Same for the Compare
page - exports a side-by-side comparison report.

### See it before you click it
A green / yellow / red status dot in the top-right confirms the
backend is alive and data is fresh. Hover for details.

### Hidden admin page
Visit `/admin` (type the URL) to see live health, seed status, and
trigger the nightly refresh on-demand. Requires the admin token
from your server `.env`.

## Upgrade notes

- Existing v1 installations: stop the v1 compose stack, run the new
  installer. Your Postgres volume (and therefore all historical NAV
  + scores) is preserved across upgrades.
- A migration runs automatically on first start; no manual SQL needed.
- Sentry, AMFI URL, and admin token are now configured via the
  bundled `.env` (under `%LOCALAPPDATA%\Z1NMFAnalyser\payload\`).

## Known limitations

- Docker Desktop is still required on the host.
- ~50 NSE ETFs ship with live-price support out of the box; add more
  by editing `etf_symbol_map.csv`.
- Code signing is not yet applied; expect a one-time SmartScreen
  warning on first install ("More info" -> "Run anyway").

## Feedback

Thumbs up / down inside the app, or email the engineering team.
