# Z1N Capital - Mutual Fund Analyser

Internal web application for scoring, comparing, and projecting mutual funds across the full AMFI universe.

See `../Z1N Capital MF Analyser Build Plan.docx` and `../Build_Kickoff_Plan.md` for full architecture and roadmap.

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI 0.110+, Python 3.11 |
| Data | Pandas, NumPy, SciPy, numpy-financial |
| DB | PostgreSQL 15 (SQLAlchemy 2 + Alembic) |
| Cache / Broker | Redis 7 |
| Tasks | Celery + Celery Beat |
| Frontend | React 18, Vite, Tailwind, Recharts, Zustand |
| Container | Docker Compose |

## Quickstart (local dev)

Prereqs: Docker + Docker Compose v2, ~4 GB RAM free.

```bash
cd mf-analyser
cp .env.example .env       # or "copy" on Windows cmd
docker compose up --build
```

Then in a second terminal:

```bash
docker compose exec backend alembic upgrade head
```

Endpoints:
- Backend API:    http://localhost:8000
- Swagger docs:   http://localhost:8000/docs
- Health probe:   http://localhost:8000/api/v1/health
- Frontend:       http://localhost:5173

## Phase Status

- [x] Sprint 0 - Scaffolding
- [x] Phase 1 - Data Pipeline + Backend API
  - [x] Week 2 - MFApi.in ingestion + live endpoints
  - [x] Week 3 - Metrics computation (CAGR/Sharpe/drawdown/momentum)
  - [x] Week 4 - Category benchmarks + Redis cache
- [x] Phase 2 - Composite scoring engine
- [x] Phase 3 - Frontend (Search, Detail, Compare, Calculator) - friendly UI
- [x] Phase 4 - Monte Carlo + NAV chart + Compare overlay
- [x] Phase 5 - QA, perf baseline, user guide, ops runbook
  - Full Playwright E2E suite deferred to post-launch

## Docs

- User-facing: `docs/USER_GUIDE.md`
- Ops runbook: `docs/OPS_RUNBOOK.md`

## First-run data cascade

After `docker compose up` and `alembic upgrade head`, run these in order. Each is idempotent and resumable.

### 1. Fund master (~10 seconds)
Loads ~37,000 scheme names from AMFI.
```bash
docker compose exec backend python -c "from app.tasks.refresh import refresh_fund_master; print(refresh_fund_master(populate_meta=False))"
```

### 2. NAV history + metadata (~1 hour, Regular plans only)
Fetches per-scheme NAV history + backfills AMC/category. Regular plans only (~18k schemes) per spec section 9.2.
```bash
# Smoke test with 5 schemes first
docker compose exec backend python -c "from app.tasks.refresh import refresh_nav_history; print(refresh_nav_history(limit=5))"

# Full backfill
docker compose exec backend python -c "from app.tasks.refresh import refresh_nav_history; print(refresh_nav_history())"
```

### 3. Compute metrics (~2 min)
Reads NAV history, computes CAGR 1Y/3Y/5Y/10Y, Sharpe, std dev, drawdown, momentum.
```bash
docker compose exec backend python -c "from app.tasks.refresh import compute_metrics; print(compute_metrics())"
```

### 4. Category benchmarks (~1 sec)
p25/p50/p75 per (category, metric).
```bash
docker compose exec backend python -c "from app.tasks.refresh import compute_benchmarks; print(compute_benchmarks())"
```

### 5. Composite scoring (~10 sec)
Peer-percentile ranking + weighted composite + momentum overlay + exit-load penalty.
```bash
docker compose exec backend python -c "from app.tasks.refresh import compute_scores; print(compute_scores())"
```

After all five steps, refresh http://localhost:5173 - score gauges and metrics populate.

## Nightly schedule

Celery beat handles the cascade automatically at 23:00 IST each night:
- 23:00 fund master refresh
- 23:10 NAV history incremental
- 00:30 metrics
- 00:45 benchmarks
- 00:50 scoring

## Running tests
```bash
docker compose exec backend pytest -q
```

## Migrations
```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

---

*Z1N Capital - Internal - Confidential*

## v2 Roadmap progress

- [x] Phase A - Production hygiene + deep health probe + freshness widget
- [x] Phase B - AMFI weekly expense-ratio scraper + admin CSV upload
- [x] Phase C - Yahoo Finance live ETF quotes (intraday last_price, day_change_pct, stale flag)
- [x] Phase D - Word + PDF export (per-fund factsheet + comparison report, docx + pdf via LibreOffice)
- [x] Phase E - Windows installer (.exe) + tray launcher (PyInstaller + Inno Setup + GitHub Actions)
- [x] Phase F - First-boot auto-seed + progress modal + admin page + extended health checks
- [x] Phase G - QA + release (Playwright e2e, CHANGELOG, USER_GUIDE refresh, QA checklist)

See `../Z1N_MF_Analyser_v2_Plan.md` for the full v2 spec.
