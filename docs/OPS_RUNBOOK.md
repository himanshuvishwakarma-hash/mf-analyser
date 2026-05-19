# Z1N MF Analyser - Ops runbook

## Daily nightly cascade
Runs automatically via Celery beat at 23:00 IST. Sequence:

| Time | Task | Expected duration |
|------|------|-------------------|
| 23:00 | refresh_fund_master | 30s (no metadata) / 30 min (with metadata) |
| 23:10 | refresh_nav_history (Regular plans only, ~9,900 schemes) | 30-60 min |
| 00:30 | compute_metrics | 2 min |
| 00:45 | compute_benchmarks | <1s |
| 00:50 | compute_scores | 10s |

## Manual cascade
```bash
docker compose exec backend python -c "from app.tasks.refresh import refresh_fund_master, refresh_nav_history, compute_metrics, compute_benchmarks, compute_scores; \
    refresh_fund_master(); refresh_nav_history(); compute_metrics(); compute_benchmarks(); compute_scores()"
```

## Common operations

| Need | Command |
|------|---------|
| Re-score after weight tuning | `docker compose exec backend python -c "from app.tasks.refresh import compute_scores; print(compute_scores())"` |
| Top fund by score | `docker compose exec postgres psql -U mfa -d mf_analyser -c "SELECT scheme_code, composite_score FROM fund_scores ORDER BY composite_score DESC LIMIT 10;"` |
| Cache flush | `docker compose exec redis redis-cli FLUSHALL` |
| Recreate schema | `docker compose exec backend alembic downgrade base && docker compose exec backend alembic upgrade head` |
| Tail backend logs | `docker compose logs -f backend` |
| Tail beat schedule | `docker compose logs -f celery_beat` |

## Monitoring checks

Sanity probes that should pass any time the stack is healthy:

```bash
curl -s http://localhost:8000/api/v1/health | jq
# {"status": "ok", "db": "ok"}

curl -s "http://localhost:8000/api/v1/funds/search?q=axis&limit=3" | jq '.total'
# > 0

curl -s "http://localhost:8000/api/v1/categories" | jq '.categories | length'
# >= 4
```

## Alarms (manual until Sentry wired)

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/api/v1/funds/{code}/score` returns 404 for funds in DB | scoring not run yet | Run `compute_scores` task |
| Empty cards on Discover page | DB empty | Run the full cascade |
| Postgres FATAL `database mfa does not exist` in logs | healthcheck pre-DB-init, harmless | Wait for compose readiness |
| MFApi.in timeouts | upstream outage | Retry; tenacity already retries 4x |

## Performance baselines (Phase 5 measurement)

Measured on the dev stack with 50 funds populated:

| Endpoint | p50 | p95 |
|----------|-----|-----|
| GET /api/v1/funds/search?q=axis | 30 ms | 80 ms |
| GET /api/v1/funds/list | 25 ms | 60 ms |
| GET /api/v1/funds/{code} | 40 ms | 110 ms |
| GET /api/v1/funds/{code}/nav | 25 ms | 90 ms |
| POST /api/v1/funds/compare (5 funds) | 60 ms | 150 ms |
| POST /api/v1/calculator/sip (10k sims, 10y) | 220 ms | 450 ms |
| POST /api/v1/calculator/lumpsum (10k sims, 25y) | 380 ms | 700 ms |

Numbers degrade roughly linearly with the fund universe; expect p95 < 500 ms (spec target) once full ~18k regular schemes are scored, assuming Redis cache stays hot.

## Accessibility checklist (Phase 5 quick pass)

- [x] Keyboard nav: tab moves through search input, category chips, fund cards, sticky compare bar
- [x] All `?` tooltip icons have `title` attribute screen readers can read
- [x] Charts have legends and axis labels (Recharts default)
- [ ] Colour-only signals: green/red highlighting in compare matrix needs a textual hint (TODO)
- [ ] Live region for "Compare list now has 3 funds" announcements (TODO)
- [ ] ARIA on score gauge (currently SVG without role) (TODO)

## Future enhancements (out of scope for v1)

- Word/PDF export of a fund report
- Authentication + advisor profiles + saved watchlists
- Portfolio overlap analysis
- Alert system (score change, NAV drop)
- Client-facing mode w/ SEBI compliance disclaimers

## Sentry error tracking (v2 Phase A.3)

Code path already wired in `app/main.py` and reads `SENTRY_DSN` from env. To enable:

1. Create a Z1N Sentry org + project at https://sentry.io (free tier is fine for v2)
2. Copy the DSN (looks like `https://xxx@oNNN.ingest.sentry.io/PPP`)
3. Add to `.env`:
   ```
   SENTRY_DSN=https://xxx@oNNN.ingest.sentry.io/PPP
   ENVIRONMENT=production
   ```
4. Restart backend: `docker compose restart backend celery_worker celery_beat`

Errors auto-flow to Sentry. To verify, trigger any 5xx and check the Sentry dashboard within a minute.

If `SENTRY_DSN` is empty (default), the SDK is not initialised and the app runs unchanged.

## Deep health probe (v2 Phase A.2)

`GET /api/v1/health/deep` returns:

```json
{
  "status": "ok|warn|down",
  "checks": {
    "db":     {"status": "ok"},
    "redis":  {"status": "ok"},
    "celery": {"status": "ok", "workers": ["celery@..."]},
    "data":   {
      "status": "ok",
      "funds_total": 37597,
      "funds_scored": 9901,
      "category_benchmarks": 28,
      "latest_nav_date": "2026-05-15",
      "latest_score_computed_at": "2026-05-16T00:50:12",
      "score_age_hours": 8.5
    }
  }
}
```

Frontend header shows a green/yellow/red dot pulling this every 30s.

Status rollup logic:
- `down` if DB or Redis unreachable (any one is enough)
- `warn` if scores are >36h stale or Celery workers don't respond
- `ok` otherwise

## Expense ratio refresh (v2 Phase B)

`expense_ratio` is **not** in MFApi.in. v2 sources it from AMFI's monthly TER disclosure.

### Automatic (preferred)
Celery beat runs `refresh_expense_ratios` every Sunday at 04:00 IST. It:
1. Scrapes https://www.amfiindia.com/research-information/other-data/total-expense-ratio-of-mutual-fund-schemes for the latest .xlsx
2. Downloads + parses with pandas
3. Updates `funds.expense_ratio` + `funds.expense_ratio_as_of`

### Manual trigger
```bash
docker compose exec backend python -c "from app.tasks.refresh import refresh_expense_ratios; print(refresh_expense_ratios())"
```

### Manual CSV upload (when AMFI scraper fails)
Set `ADMIN_TOKEN=somethingsecret` in `.env`, restart backend, then:
```bash
curl -X POST http://localhost:8000/api/v1/admin/expense-upload \
  -H "X-Admin-Token: somethingsecret" \
  -F "file=@my_expense_data.csv"
```
CSV format: `scheme_code,expense_ratio` (one row per fund, header required).

### Admin: trigger AMFI scrape now
```bash
curl -X POST http://localhost:8000/api/v1/admin/expense-scrape \
  -H "X-Admin-Token: somethingsecret"
```

### Apply schema migration first
```bash
docker compose exec backend alembic upgrade head
```
Adds `expense_ratio_as_of` Date column to funds.

## Report exports (Phase D)

PDF generation depends on LibreOffice headless (`soffice`). It is installed
in the backend Docker image via apt. For non-Docker runs:

    sudo apt-get install -y libreoffice  # Debian/Ubuntu
    brew install --cask libreoffice      # macOS

The `/funds/{code}/report?format=pdf` endpoint returns HTTP 503 with a
clear message if `soffice` is missing. The .docx path always works (pure
python-docx).

Charts are rendered server-side via matplotlib (Agg backend, no display
required). Per-fund chart cache is opt-in via `REPORTS_CACHE_DIR` env var;
default is no caching (re-renders are ~50ms).

## Windows installer build + code signing (Phase E)

### Build steps (local Windows machine)

1. Build the React frontend Docker image (if image-bundled compose path):
   `docker build -t ghcr.io/z1ncapital/mf-analyser-frontend:2.0.0 frontend/`
2. Build the backend image:
   `docker build -t ghcr.io/z1ncapital/mf-analyser-backend:2.0.0 backend/`
3. Build the tray launcher exe:
   `installer\build_exe.ps1`
4. Compile the installer (Inno Setup 6.x required on PATH):
   `ISCC.exe installer\setup.iss`
5. Output: `installer\Output\Z1NMFAnalyser-Setup-v2.0.0.exe`

### Code signing

Without code signing, Windows SmartScreen will warn end-users on first
launch ("Windows protected your PC"). To remove the warning:

1. Purchase an OV (Organisation Validation) code-signing certificate.
   Vendors: DigiCert, Sectigo, GlobalSign. Indian price: Rs 18,000-30,000/yr.
   Lead time: 1-2 weeks (legal-entity verification).
2. Install the certificate on the build machine (USB token or HSM).
3. Sign the launcher exe before packaging into the installer:

   ```powershell
   signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 ^
     /a installer\tray_launcher\dist\Z1NLauncher.exe
   ```

4. Sign the final installer .exe after Inno Setup builds it:

   ```powershell
   signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 ^
     /a installer\Output\Z1NMFAnalyser-Setup-v2.0.0.exe
   ```

5. (Optional) Enable Inno Setup integrated signing by uncommenting
   `SignTool=signtool` in `setup.iss` and configuring the global
   SignTool definition in Inno Setup IDE preferences.

EV certificates (Extended Validation) skip SmartScreen reputation
build-up entirely - costlier (~Rs 50k+/yr) and require a hardware token.
For internal advisor use the OV cert is sufficient.
