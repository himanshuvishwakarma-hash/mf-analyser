# Z1N MF Analyser - Setup Guide

A short walkthrough for installing and running the Z1N Mutual Fund
Analyser on your own Windows machine. Should take about 20 minutes of
your active time. The first data download then runs in the background
for another 60-90 minutes.

If anything goes wrong, ping Himanshu (himanshu.vishwakarma@z1ncapital.com)
with a screenshot of the error.

---

## What you need before starting

1. A Windows 10 or 11 machine (64-bit). Mac is not currently supported.
2. About 5 GB of free disk space.
3. Admin rights on the machine (you will install Docker Desktop).
4. A stable internet connection (the first-time data sync downloads
   roughly 200 MB).

---

## Step 1 - Install Docker Desktop

The app runs inside Docker containers, so Docker Desktop is required.

1. Open https://www.docker.com/products/docker-desktop/ in your browser.
2. Click **Download for Windows - AMD64**.
3. Run the downloaded installer. Accept all defaults. Reboot when asked.
4. After reboot, open **Docker Desktop** from the Start menu.
5. Wait until the Docker whale icon in your system tray (bottom-right)
   stops animating - this means Docker is running. First launch takes
   1-2 minutes.

If Docker Desktop complains about WSL 2:
- Open PowerShell as Administrator
- Run `wsl --install` and reboot
- Re-launch Docker Desktop

---

## Step 2 - Download the Z1N installer

1. Open https://github.com/himanshuvishwakarma-hash/mf-analyser/releases
2. Find the latest release at the top (e.g., `v2.0.0`).
3. Under **Assets**, click `Z1NMFAnalyser-Setup-v2.0.0.exe` to download.

(If GitHub asks you to log in, contact Himanshu - he'll add you to the
private repo.)

---

## Step 3 - Run the installer

1. Double-click the downloaded `Z1NMFAnalyser-Setup-v2.0.0.exe`.
2. Windows SmartScreen will warn you: *"Windows protected your PC"*.
   This happens because we haven't bought a code-signing certificate
   yet. The installer is safe.
   - Click **More info** (small link on the warning).
   - Click **Run anyway**.
3. Inno Setup installer wizard opens. Click **Next** through:
   - Welcome page
   - Destination (leave default)
   - Additional shortcuts (recommended: tick **Create a desktop shortcut**
     AND **Start Z1N MF Analyser when Windows starts**)
   - Ready to install -> **Install**
4. When installation finishes, leave **Launch Z1N MF Analyser** ticked
   and click **Finish**.

---

## Step 4 - First launch

1. A small **Z** icon appears in your system tray (bottom-right corner
   of the screen).
2. A welcome wizard opens automatically. Click **Continue** through:
   - Welcome
   - Initial data sync (acknowledges the ~60 minute download)
   - All set -> **Finish**
3. Your default browser opens to `http://localhost:5173`.
4. A blue modal appears: *"Setting up your fund universe"*. Leave the
   tab open. You will see counts climb:
   - Fund master: ~37,000 funds
   - NAV history: ~1 million rows
   - Scores computed: ~9,800 funds

The modal disappears on its own once all three stages are done
(typically 60-90 minutes). The status dot in the top-right turns
green.

You can close the browser tab while data loads. Reopen anytime via the
tray icon -> **Open Dashboard**.

---

## Step 5 - Using the app

Four main screens, all reachable from the top navigation:

- **Discover** - Search and filter the full fund universe.
- **Fund Detail** - Click any fund to see its score, returns, risk,
  NAV chart, and live price (for ETFs).
- **Compare** - Add 2-5 funds for a side-by-side comparison.
- **Calculator** - Project SIP or Lumpsum returns using historical data
  and Monte Carlo simulation.

Two export buttons:

- **Export factsheet** on any Fund Detail page -> generates a Word or
  PDF report for the fund.
- **Export comparison** on the Compare page -> generates a Word or
  PDF side-by-side report.

Detailed user guide:
https://github.com/himanshuvishwakarma-hash/mf-analyser/blob/main/docs/USER_GUIDE.md

---

## Daily use

After the first sync, the app does the following automatically:

- Every night at 11:00 PM IST: refreshes the fund master + NAV history.
- 11:25 PM: backfills NAV for ETFs.
- 00:30 AM: recomputes risk metrics.
- 00:50 AM: recomputes composite scores.
- Sundays at 4:00 AM: refreshes expense ratios from AMFI.
- During market hours (Mon-Fri 9:15 AM - 3:30 PM IST): refreshes live
  ETF prices every 5 minutes.

You don't need to do anything. Just leave Docker Desktop running.

---

## Tray icon menu

Right-click the **Z** icon in your system tray for:

- **Open Dashboard** - opens the app in your browser.
- **View Logs** - opens the launcher log file (useful if you hit issues).
- **Restart Backend** - restarts the data service (use if dashboard
  stops loading).
- **Quit** - stops the backend and removes the icon. Re-launch from the
  Start menu or desktop shortcut.

---

## Common issues

**The dashboard shows a blank "All systems healthy" page with zero funds**
First-time data sync is still in progress. Leave the browser tab open
for 60-90 minutes after install. Check progress at
http://localhost:5173/admin

**The Z tray icon does not appear after install**
Docker Desktop might not be running. Check the whale icon in your
system tray. If missing, open Docker Desktop from the Start menu.
Then launch Z1N MF Analyser from the Start menu.

**"This site cannot be reached" at http://localhost:5173**
The backend container is still booting (typically 30-60 seconds after
launch). Wait a minute and refresh. If it persists, right-click the
tray icon -> Restart Backend.

**Status dot is red**
Something is wrong. Click the dot for a breakdown of which service is
down. Most common: Docker Desktop got paused or stopped. Restart
Docker Desktop, then right-click tray icon -> Restart Backend.

**PDF export gives a 503 error**
PDF generation needs LibreOffice inside the backend container. Should
be auto-installed; if missing, the .docx (Word) export always works
as a fallback.

**Did not get an email invite to the GitHub repo**
Ask Himanshu to add your GitHub username as a collaborator on the
private repo.

---

## Uninstall

If you ever want to remove the app:

1. Windows Settings -> Apps -> Installed apps
2. Find **Z1N MF Analyser** -> **Uninstall**
3. The uninstaller will ask: *"Also remove all downloaded fund data?"*
   - Choose **Yes** to free up disk space.
   - Choose **No** to keep the data for a future re-install.

Docker Desktop is left alone - uninstall it separately if needed.

---

## Need help?

- Bug or weird behaviour: email Himanshu with a screenshot.
- Feature request: same channel.
- Anything urgent affecting client work: WhatsApp.

*Z1N Capital - Internal - Confidential*
