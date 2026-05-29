# Z1N MF Analyser - v3 Roadmap

Caveman draft. v3 builds on v2 (shipped May 2026). Four phases sequential.

## Goals (input from Himanshu)

| # | Goal | Why |
|---|------|-----|
| 1 | Better data coverage | Today: ~3k visible funds, NULL category on 25k+, no expense ratios, ETF prices flaky. Blocks everything else. |
| 2 | Portfolio-level analysis | Today is single-fund. v3: upload portfolio, see overlap, weighted score, rebalancing suggestions. |
| 3 | Login + users + watchlists | Multi-user. Advisor view + client view. SEBI overlay for client-facing mode. |
| 4 | Native desktop (Tauri) | Remove Docker Desktop dependency. Single ~100 MB binary. |

## Phase plan

| Phase | Scope | Calendar | Spec |
|-------|-------|----------|------|
| **3A. Data coverage** | AMFI scheme master, AMFI TER scraper rewrite, NSE quote API, removal of name-pattern fallbacks | 2 weeks | `specs/2026-05-21-3a-data-coverage-design.md` |
| **3B. Portfolio analysis** | CAS upload, holdings table, overlap matrix, weighted composite, what-if swap | 3 weeks | TBD after 3A |
| **3C. Login + multi-user** | FastAPI-Users auth, per-user portfolios + watchlists, role split (advisor/client), SEBI client overlay | 4 weeks | TBD after 3B |
| **3D. Native desktop** | Tauri rewrite of tray launcher. Embedded SQLite. Optional remote-sync. Parallel with 3C ok. | 4 weeks | TBD |

Total: 9-13 calendar weeks.

## Source of truth

- Free sources only (AMFI scheme master, NSE quote API, MFApi.in NAV)
- Paid feed (Morningstar / ValueResearch) parked for v3.1 if free coverage proves insufficient

## What stays from v2

- Composite score model (10-factor peer-percentile)
- Monte Carlo calculator
- Word/PDF factsheet (client + advisor toggle)
- Hidden /admin page
- Celery beat schedule (extended in 3A)
- Windows installer (replaced by Tauri in 3D)

## What's parked

- Code-signing certificate (cosmetic; SmartScreen warning remains until purchased)
- Mobile-first PWA
- Multi-tenant SaaS deployment
- True client-facing mode w/ SEBI compliance (touched in 3C but full audit parked)

---

*Z1N Capital - Internal - Draft v0.1*
