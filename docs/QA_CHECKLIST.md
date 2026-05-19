# Z1N MF Analyser v2.0.0 - QA Checklist

Manual checks against a fresh Windows install on three machines
(min: Win 10 22H2, Win 11 23H2, one corporate-managed device). Tick
each box per machine.

---

## 0. Pre-flight

- [ ] Test machine has Docker Desktop 4.x installed and running
- [ ] No prior version of Z1N MF Analyser installed (or fully
      uninstalled including volumes)
- [ ] Network can reach: `api.mfapi.in`, `query1.finance.yahoo.com`,
      `amfiindia.com`
- [ ] `Z1NMFAnalyser-Setup-v2.0.0.exe` downloaded locally

## 1. Installer

- [ ] Installer launches via double-click (no admin elevation needed)
- [ ] If Docker missing: prompt opens Docker Desktop download page
- [ ] Default install path = `%LOCALAPPDATA%\Z1NMFAnalyser`
- [ ] Desktop shortcut created (Tasks page)
- [ ] Start menu folder "Z1N MF Analyser" created
- [ ] Startup-on-login registered (Tasks page)
- [ ] Post-install: tray launcher starts automatically

## 2. First boot

- [ ] Tray icon (teal "Z") visible in system tray
- [ ] Right-click menu shows: Open Dashboard, View Logs, Restart, v2.0.0, Quit
- [ ] First-run wizard opens (3 steps): Welcome -> Sync -> Done
- [ ] Clicking "Finish" launches browser at `http://localhost:5173`
- [ ] First-boot modal shows on dashboard ("Setting up your fund universe")
- [ ] Modal updates as fund_count / nav_count / score_count progress
- [ ] Modal dismisses automatically once `seeded:true`
- [ ] Total time to seeded: 60-90 minutes on a 50 Mbps line

## 3. Discover (search + list)

- [ ] Typing "HDFC" in search returns >= 5 funds within 1s
- [ ] Each row shows: name, AMC, category, score, 1y/3y/5y CAGR, cost
- [ ] Category filter dropdown narrows results
- [ ] Pagination loads next page without flicker
- [ ] Direct plans are NOT shown (confirm via name + plan badge)

## 4. Fund Detail

- [ ] Composite score gauge displays in 0-100 range
- [ ] Snapshot card values match underlying DB
- [ ] Returns table renders 1y/3y/5y/10y (dashes for missing)
- [ ] Risk profile section: Sharpe, drawdown, recovery
- [ ] Momentum section: 3m + 6m
- [ ] NAV history chart renders; range selector (1M/3M/6M/1Y/3Y/5Y/Max) works
- [ ] "Add to compare" button toggles state
- [ ] Calculator link navigates with scheme pre-selected
- [ ] Export factsheet button shows Word + PDF options

## 5. ETF live prices

- [ ] Open an ETF fund (e.g., NIFTYBEES)
- [ ] Live-price block appears below header
- [ ] Current price + day_change_pct visible (during market hours)
- [ ] Outside market hours: shows last-known value, no errors
- [ ] Stale > 15 min: amber banner appears
- [ ] Polling: price refreshes within 60s during market hours

## 6. Compare

- [ ] Add 2 funds -> Compare page shows side-by-side table
- [ ] Overlaid NAV chart (rebased to 100) renders
- [ ] Best value in each row is green; worst is red
- [ ] Add 5 funds: layout doesn't break
- [ ] Try 6th fund: blocked with friendly error
- [ ] Export comparison: Word file downloads with all funds

## 7. Calculator

- [ ] Pick a fund, enter 10,000 SIP / 10 years -> Calculate
- [ ] "Calculated return" and "Projected return" both display
- [ ] No Pessimistic / Optimistic numbers in the result card (only 2 numbers)
- [ ] Chart/Table toggle works for the Monte Carlo breakdown
- [ ] Table shows P10/P50/P90 + implied CAGR per year
- [ ] Switch to Lumpsum: same flow works

## 8. Exports

### Per-fund factsheet (Word)
- [ ] Filename: `factsheet_<scheme>.docx`
- [ ] Opens in MS Word without warnings
- [ ] Contains: Z1N header, snapshot table, returns, risk, score breakdown, NAV chart
- [ ] Footer has disclaimer + generation timestamp

### Per-fund factsheet (PDF)
- [ ] Generated within ~5s
- [ ] PDF opens in browser / Acrobat
- [ ] No 503 errors (confirms LibreOffice in backend image)

### Comparison report (Word + PDF)
- [ ] All selected funds appear in matrix
- [ ] Normalised overlay chart embedded
- [ ] Page does not split mid-table

## 9. Admin page

- [ ] Visit `/admin` directly in URL bar
- [ ] System health card lists: db, redis, celery, data, etf_quotes
- [ ] Data seed card shows accurate counts
- [ ] Without token: cascade trigger returns "Invalid admin token"
- [ ] With wrong token: 401 message
- [ ] With correct token from `.env`: cascade dispatches, success banner
- [ ] No `ADMIN_TOKEN` set on server: returns 503 with explanation

## 10. Tray launcher

- [ ] "Open Dashboard" opens default browser at correct URL
- [ ] "View Logs" opens launcher log in default editor
- [ ] "Restart Backend" cleanly down/ups the stack (~30s)
- [ ] "Quit" stops the stack and removes the tray icon
- [ ] Launcher log file under `%LOCALAPPDATA%\Z1NMFAnalyser\launcher.log`

## 11. Nightly refresh (next day)

- [ ] Logs show: refresh_fund_master at 23:00 IST
- [ ] Logs show: refresh_nav_history at 23:10 IST
- [ ] Logs show: compute_metrics + compute_benchmarks + compute_scores
- [ ] Health dot turns green by 01:00 IST
- [ ] Sunday only: refresh_expense_ratios runs at 04:00 IST

## 12. Uninstall

- [ ] Programs and Features -> Z1N MF Analyser -> Uninstall
- [ ] Prompt asks: "Also remove all downloaded fund data?"
- [ ] Choose No: docker volume preserved
- [ ] Choose Yes: docker volume dropped
- [ ] App folder removed from `%LOCALAPPDATA%`
- [ ] Tray icon disappears
- [ ] Startup entry removed

## 13. Re-install (volume preserved path)

- [ ] Run installer again with old data preserved
- [ ] First-boot modal does NOT appear (`seeded:true` from existing volume)
- [ ] All previous funds + scores still present

---

## Acceptance summary

A release is GO when:

- All Win 10 22H2 boxes ticked
- All Win 11 23H2 boxes ticked
- Corporate-managed device: all boxes except #2 (startup may be policy-blocked)
- No P0 / P1 bugs filed
- Sentry shows < 1 error per 100 requests during the QA window
