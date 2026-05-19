# Changelog

All notable changes to the Z1N MF Analyser are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to semantic versioning.

---

## [2.0.0] - 2026-05-18

The v2 release ships six themed phases on top of the v1 codebase:
production hardening, expense-ratio scraping, live ETF data, Word/PDF
exports, a Windows installer, and a friendlier first-boot experience.

### Added

- **Phase A - Production hygiene**
  - `/api/v1/health/deep` rolls up DB + Redis + Celery + data-freshness checks.
  - Sentry wiring documented (`SENTRY_DSN` env).
  - Test coverage raised to 70%+ in `core/`.
- **Phase B - AMFI expense-ratio scraper**
  - Weekly Celery job (`Sun 04:00 IST`) parses AMFI TER Excel.
  - Admin endpoint `POST /admin/expense-upload` accepts CSV fallback.
  - New column `funds.expense_ratio_as_of`.
- **Phase C - Live ETF quotes**
  - New table `etf_quotes`, seeded from `data/etf_symbol_map.csv` (~50 NSE ETFs).
  - Yahoo Finance fetcher via `yfinance`, every 5 min during NSE hours.
  - `FundDetail` shows live price + day change + stale flag for ETFs.
- **Phase D - Word + PDF exports**
  - `/funds/{code}/report?format=docx|pdf` per-fund factsheet.
  - `POST /funds/compare/report` side-by-side comparison report.
  - Server-side matplotlib charts embedded as PNG.
  - PDF via LibreOffice headless; graceful 503 if missing.
- **Phase E - Windows installer**
  - PyInstaller tray launcher (`Z1NLauncher.exe`) with system-tray icon.
  - First-run Tk wizard.
  - Inno Setup script bundles compose stack + env template.
  - GitHub Actions builds the installer on every `v*.*.*` tag.
- **Phase F - First-boot UX**
  - Backend auto-dispatches seed cascade on empty `funds` table.
  - `FirstBootModal` polls `/admin/seed-status` and shows progress.
  - Hidden `/admin` page surfaces system health + manual cascade trigger.
  - `/health/deep` now includes ETF quote freshness.

### Changed

- All admin endpoints require `X-Admin-Token` header (set `ADMIN_TOKEN`
  in `.env`). Returns 503 if token unset.
- Bundled `docker-compose.yml` (installer payload) uses named volumes
  exclusively, no host bind mounts.

### Removed

- Nothing user-facing.

### Fixed

- Postgres parameter-limit overflow on large fund-master inserts
  (chunked at 1000 rows now).
- Sandbox/proxy env leak on httpx clients (`trust_env=False`).
- Direct-plan exclusion fallback when `plan_type` is `NULL`.

### Known limitations

- Installer still requires Docker Desktop on the host (true zero-Docker
  is parked for v3 / Tauri evaluation).
- ETF symbol map ships ~50 NSE ETFs; full BSE coverage is opt-in via
  the CSV.
- Yahoo Finance is unofficial - rate limits can throttle quotes during
  spikes; cached values + stale flag soften this.

---

## [1.0.0] - 2026-04-30

Initial release: Phases 0-5.

- FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery backend.
- React + Vite + Tailwind + Recharts frontend.
- 4 screens: Search, Fund Detail, Compare, Calculator.
- Nightly cascade: fund master, NAV history, metrics, scores.
- Peer-percentile composite scoring (10-factor).
- Monte Carlo SIP / lumpsum projections (P10/P50/P90).
- Docker Compose orchestration.
