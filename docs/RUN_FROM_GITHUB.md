# Z1N MF Analyser — Run From GitHub (Full Setup)

A complete, step-by-step guide to running the Z1N Mutual Fund Analyser on your own Windows or macOS machine by cloning the source from GitHub.

This is the **developer / power-user route**. If you only want a one-click install, use the Windows installer described in [`COLLEAGUE_SETUP.md`](./COLLEAGUE_SETUP.md) instead.

Expect about 30 minutes of active work. The first data download then runs in the background for another 60-90 minutes.

If you hit any issue, ping Himanshu (himanshu.vishwakarma@z1ncapital.com) with a screenshot of the error and the step number.

---

## Table of contents

1. [What you need before starting](#what-you-need)
2. [Install prerequisites](#install-prerequisites)
3. [Get the source code from GitHub](#clone-the-repo)
4. [Configure environment variables](#configure-env)
5. [Build and start the stack](#start-stack)
6. [First-time data sync](#first-data-sync)
7. [Open the app](#open-app)
8. [Daily use](#daily-use)
9. [Stopping and starting](#stop-start)
10. [Updating to the latest version](#updating)
11. [Common issues](#common-issues)
12. [Optional: developer extras](#dev-extras)

---

## 1. What you need before starting <a name="what-you-need"></a>

| Item | Why | Minimum version |
|---|---|---|
| Windows 10/11 (64-bit) **or** macOS 12+ | Operating system | — |
| 8 GB RAM | Docker containers + Postgres + Redis + frontend | 8 GB |
| 10 GB free disk | Docker images + Postgres data + NAV history | 10 GB |
| Admin rights on your machine | To install Docker Desktop and Git | — |
| Stable internet (broadband) | First-time data sync downloads ~200 MB; nightly refresh ~50 MB | — |

You do **not** need to install Python, Node.js, or PostgreSQL separately. Docker bundles all of them.

---

## 2. Install prerequisites <a name="install-prerequisites"></a>

### 2a. Install Git

Git is needed to download the source code.

**Windows:**
1. Go to https://git-scm.com/download/win
2. Download and run the 64-bit Git for Windows Setup installer.
3. Accept all defaults. Make sure **Git Bash** is included.
4. Verify by opening PowerShell and running:
   ```powershell
   git --version
   ```
   You should see `git version 2.x.x` or similar.

**macOS:**
1. Open Terminal and run:
   ```bash
   xcode-select --install
   ```
2. Click Install when prompted. This installs Git along with Apple's developer tools.
3. Verify:
   ```bash
   git --version
   ```

### 2b. Install Docker Desktop

Docker runs the database, backend, and frontend containers.

**Windows:**
1. Go to https://www.docker.com/products/docker-desktop/
2. Click **Download for Windows - AMD64**.
3. Run the installer. Accept all defaults. Reboot when asked.
4. After reboot, launch **Docker Desktop** from the Start menu.
5. Wait for the whale icon in your system tray to stop animating. First boot takes 1-2 minutes.
6. If Docker Desktop complains about WSL 2:
   - Open PowerShell as Administrator.
   - Run `wsl --install` and reboot.
   - Re-launch Docker Desktop.

**macOS:**
1. Go to https://www.docker.com/products/docker-desktop/
2. Click **Download for Mac - Apple Silicon** (M1/M2/M3) or **Intel chip** as appropriate.
3. Open the downloaded `.dmg` and drag Docker to Applications.
4. Launch Docker from Applications. Grant the permissions it asks for.
5. Wait until the whale icon in the menu bar stops animating.

### 2c. Verify Docker is running

Open a terminal (PowerShell on Windows, Terminal on macOS) and run:
```bash
docker --version
docker compose version
```
You should see versions for both. If either says "command not found", Docker Desktop is not running or not installed.

### 2d. (Optional) Install a code editor

If you plan to look at logs or edit settings, install VS Code from https://code.visualstudio.com/. Not required to just run the app.

---

## 3. Get the source code from GitHub <a name="clone-the-repo"></a>

### 3a. Get repo access

The repository is private. You need to be added as a collaborator first.
- Email Himanshu your **GitHub username** (not email). He will send you an invite.
- Open the invite link in the email and click **Accept invitation**.

### 3b. Create a Personal Access Token (PAT)

GitHub no longer allows password-based git push/pull. You need a PAT.

1. Open https://github.com/settings/tokens
2. Click **Generate new token (classic)**.
3. Note: name it `mf-analyser-local`.
4. Expiration: 90 days (or longer if you prefer).
5. Scopes: check **repo** (gives full repo access).
6. Click **Generate token**.
7. **Copy the token immediately** — you will not see it again. Paste it into a secure note.

### 3c. Clone the repository

Open a terminal in the folder where you want the code (e.g. `Desktop`):

**Windows (PowerShell):**
```powershell
cd $HOME\Desktop
git clone https://github.com/himanshuvishwakarma-hash/mf-analyser.git
```
When prompted:
- Username: your GitHub username
- Password: **paste the PAT** (not your GitHub password)

**macOS (Terminal):**
```bash
cd ~/Desktop
git clone https://github.com/himanshuvishwakarma-hash/mf-analyser.git
```
Same credential prompt.

You should now have a folder `mf-analyser` on your Desktop.

### 3d. Enter the project folder

```bash
cd mf-analyser
```

All remaining commands assume you are inside this folder.

---

## 4. Configure environment variables <a name="configure-env"></a>

The stack reads its configuration from a `.env` file at the project root. A template is provided.

### 4a. Copy the template

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS:**
```bash
cp .env.example .env
```

### 4b. Edit the .env file (optional)

Open `.env` in a text editor. For most local setups, the defaults are fine. Things you might want to change:

| Variable | Default | What it does |
|---|---|---|
| `POSTGRES_PASSWORD` | `mfa_local_pwd` | Postgres password. Change for production. |
| `ADMIN_TOKEN` | `change-me-please` | Token to call admin endpoints. Change to something only you know. |
| `CELERY_SCHEDULE_HOUR` | `23` | Hour (IST) for nightly refresh. 23 = 11 PM. |

Save and close.

> Never commit your `.env` file. It's already in `.gitignore`.

---

## 5. Build and start the stack <a name="start-stack"></a>

This builds Docker images for the backend (Python + FastAPI), frontend (Node + Vite + React), and starts Postgres + Redis + Celery worker.

From the project root:

```bash
docker compose up -d --build
```

First run takes 5-10 minutes (downloads base images, builds Python + Node dependencies). Subsequent runs are seconds.

When the command finishes, verify all containers are healthy:

```bash
docker compose ps
```

You should see:
```
NAME                IMAGE                              STATUS
mfa_backend         mf-analyser-backend                Up (healthy)
mfa_celery_worker   mf-analyser-celery_worker          Up
mfa_frontend        mf-analyser-frontend               Up
mfa_postgres        postgres:15                        Up (healthy)
mfa_redis           redis:7                            Up (healthy)
```

If any container shows `Restarting` or `Exited`, run `docker compose logs <service>` (e.g. `docker compose logs backend`) and send the last 50 lines to Himanshu.

### 5a. Run database migrations

The backend auto-creates tables on first boot, but if you want to be explicit (or after pulling new code), run:

```bash
docker compose exec backend alembic upgrade head
```

You should see lines ending in `INFO  [alembic.runtime.migration] Running upgrade ...` and then a clean prompt.

---

## 6. First-time data sync <a name="first-data-sync"></a>

The fresh database has no funds in it. Trigger the initial load:

```bash
docker compose exec backend python -c "from app.tasks import refresh as r; r.refresh_universe.delay(); r.refresh_fund_master.delay()"
```

Then in a separate terminal (keep this running so you can watch progress):

```bash
docker compose logs -f celery_worker
```

You should see lines like:
```
[INFO] refresh_universe OK: {'inserted': 14000, 'updated': 0, 'total': 14000}
[INFO] refresh_fund_master OK: scheme_codes_added=23000
```

Once those finish (typically 3-5 minutes), kick off the NAV backfill:

```bash
docker compose exec backend python -c "from app.tasks import refresh as r; r.refresh_nav_history.delay()"
```

This is the long one. NAV history downloads ~1 million rows from MFAPI and takes **60-90 minutes**. You can close the terminal — Celery runs in the background.

After NAV is done, scoring kicks in automatically (or run it manually):

```bash
docker compose exec backend python -c "from app.tasks import refresh as r; r.compute_metrics.delay(); r.compute_scores.delay()"
```

Scoring takes another 5-10 minutes.

> **TL;DR**: just trigger `refresh_universe` + `refresh_fund_master` + `refresh_nav_history` once after install, then walk away for ~90 minutes. The nightly Celery beat will keep things fresh automatically from then on.

---

## 7. Open the app <a name="open-app"></a>

Open your browser to:

```
http://localhost:5173
```

You should see the Z1N MF Analyser dashboard.

While the first sync is running, you may see "Setting up your fund universe" or partial counts. That's normal. The status dot in the top-right shows live freshness — green when everything is up to date.

The four main screens:
- **Discover** — search and filter the universe.
- **Fund Detail** — click any fund for its score, returns, risk, NAV chart, live price (ETFs).
- **Compare** — pick 2-5 funds, see them side by side.
- **Calculator** — SIP / Lumpsum projections with Monte Carlo simulation.

Export buttons on Fund Detail and Compare give you a Word or PDF factsheet.

Full user guide: [`docs/USER_GUIDE.md`](./USER_GUIDE.md).

---

## 8. Daily use <a name="daily-use"></a>

You don't need to do anything daily. Once Docker Desktop is running, the stack auto-runs:

| Time (IST) | What happens |
|---|---|
| 22:55 | AMFI scheme master refresh (new funds, plan types, ISINs) |
| 23:00 | Fund master sync (MFAPI) |
| 23:10 | NAV history incremental refresh (~5-10 min) |
| 23:25 | ETF NAV backfill |
| 00:30 | Metrics recompute (Sharpe, drawdown, CAGR) |
| 00:45 | Category benchmarks |
| 00:50 | Composite scoring |
| 00:55 | Deactivate funds with no NAV in 60+ days |
| Sunday 04:00 | Expense ratio refresh from AMFI |
| Mon-Fri 09:15-15:30, every 5 min | ETF live quotes (NSE) |

Just leave Docker Desktop running. The frontend tab can be closed and reopened any time.

---

## 9. Stopping and starting <a name="stop-start"></a>

**Stop everything** (preserves your data):
```bash
docker compose stop
```

**Start again** after a stop:
```bash
docker compose start
```

**Restart a single service** (e.g. after editing config):
```bash
docker compose restart backend
```

**Tear down completely** (still preserves data in the `pgdata` volume):
```bash
docker compose down
```

**Tear down AND delete all data** (start from scratch):
```bash
docker compose down -v
```

---

## 10. Updating to the latest version <a name="updating"></a>

When new code is pushed to GitHub:

```bash
cd path\to\mf-analyser
git pull
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

The `--build` flag rebuilds containers with the new code. The `alembic upgrade head` applies any new database migrations.

To verify the version you're on:
```bash
git log -1 --oneline
```

---

## 11. Common issues <a name="common-issues"></a>

**`docker: command not found`**
Docker Desktop is not running or not installed. Open Docker Desktop from your Start menu / Applications, wait for the whale icon to settle, then retry.

**`port 5432 already in use`**
You have a local Postgres already running. Either stop it (Windows: Services → Postgres → Stop; macOS: `brew services stop postgresql`) or change the published port in `docker-compose.yml`:
```yaml
services:
  postgres:
    ports:
      - "5433:5432"   # changed from 5432:5432
```

**`port 5173 already in use`**
Same fix as above, but for the frontend container.

**Browser shows "This site can't be reached" at http://localhost:5173**
The frontend container is still booting. Wait 30 seconds and refresh. If it persists:
```bash
docker compose logs frontend
```
and send the last 30 lines to Himanshu.

**Status dot in app is red**
Click it for a per-service breakdown. Most common cause: Docker paused or stopped. Restart Docker Desktop, then:
```bash
docker compose restart backend celery_worker
```

**`fatal: Authentication failed` when running `git pull`**
Your PAT expired. Regenerate at https://github.com/settings/tokens and either:
- Re-clone the repo with the new token, OR
- Update the stored credential in Windows Credential Manager / macOS Keychain.

**ETF live prices stuck / `Etf_quotes WARN` on weekends**
Expected. NSE is closed Saturday and Sunday. The freshness widget uses a 96-hour threshold on weekends to suppress this warning. Mon morning after 09:15 IST it returns to normal.

**`Could not start backend stack` from the tray installer**
That's the Windows installer route, not the GitHub clone route. See [`COLLEAGUE_SETUP.md`](./COLLEAGUE_SETUP.md) section *Common issues*.

**A specific Celery task is failing**
Read its tail:
```bash
docker compose logs --tail 100 celery_worker | findstr ERROR
```
(Linux/macOS: replace `findstr` with `grep`.)

---

## 12. Optional: developer extras <a name="dev-extras"></a>

Only relevant if you want to make code changes.

### Run tests

```bash
docker compose exec backend pytest -q
```

### Open the API docs

The FastAPI app auto-generates Swagger docs at:
```
http://localhost:8000/docs
```

### Connect to the database directly

```bash
docker compose exec postgres psql -U mfa -d mf_analyser
```

Useful queries:
```sql
-- Fund counts by source
SELECT source, COUNT(*) FROM funds GROUP BY source;

-- Last successful score run
SELECT MAX(computed_at) FROM fund_scores;

-- Inspect a single fund
SELECT scheme_code, fund_name, category, plan_type, expense_ratio
FROM funds WHERE scheme_code = 120505;
```

Exit psql with `\q`.

### Tail backend logs live

```bash
docker compose logs -f backend
```

`Ctrl+C` to detach (does not stop the container).

### Trigger a refresh manually

```bash
# Universe (AMFI scheme master)
docker compose exec backend python -c "from app.tasks import refresh as r; print(r.refresh_universe.delay().id)"

# NAV
docker compose exec backend python -c "from app.tasks import refresh as r; print(r.refresh_nav_history.delay().id)"

# Scores
docker compose exec backend python -c "from app.tasks import refresh as r; print(r.compute_metrics.delay().id, r.compute_scores.delay().id)"
```

### Admin endpoints

The admin router (mounted at `/api/v1/admin`) needs the `ADMIN_TOKEN` you set in `.env`. Example:
```bash
curl -X POST http://localhost:8000/api/v1/admin/refresh-universe \
  -H "X-Admin-Token: change-me-please"
```

---

## Need help?

- Bug, error message, or weird behaviour: email Himanshu with a screenshot and the step number you were on.
- Feature request: same channel.
- Anything urgent affecting client work: WhatsApp.

*Z1N Capital — Internal — Confidential*
