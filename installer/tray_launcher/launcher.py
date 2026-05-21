"""Z1N MF Analyser - Windows tray launcher.

Single .exe (via PyInstaller) that:
- Manages the Docker Compose stack lifecycle (up / down / restart).
- Hosts a system-tray icon with menu: Open Dashboard, View Logs, Restart, Quit.
- On first run, launches the wizard before bringing the stack up.
- Polls a release feed weekly and surfaces an "Update available" notification.

Designed to run hidden (--windowed). All user feedback goes through tray
notifications or popup windows (no console).

Dependencies (installed by PyInstaller-time pip): pystray, pillow, requests.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - guarded for non-Windows test machines
    raise SystemExit(
        "pystray + Pillow required. Install via `pip install pystray Pillow requests`"
    ) from exc

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

APP_NAME = "Z1N MF Analyser"
APP_VERSION = "2.0.0"
DASHBOARD_URL = "http://localhost:5173"
UPDATE_FEED_URL = "https://releases.z1ncapital.in/version.json"
UPDATE_CHECK_INTERVAL_SEC = 7 * 24 * 60 * 60  # weekly

APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".z1n"))) / "Z1NMFAnalyser"
APP_DATA.mkdir(parents=True, exist_ok=True)
STATE_FILE = APP_DATA / "state.json"
LOG_FILE = APP_DATA / "launcher.log"
# Resolve the bundled compose dir. When frozen by PyInstaller, __file__ points
# inside the temp extraction dir, NOT the install location. Use sys.executable.
if getattr(sys, "frozen", False):
    # Running from PyInstaller .exe -> Z1NLauncher.exe lives in {app}, payload at {app}/payload
    COMPOSE_DIR = Path(sys.executable).resolve().parent / "payload"
else:
    # Dev mode: launcher.py is at installer/tray_launcher/launcher.py, payload at installer/payload
    COMPOSE_DIR = Path(__file__).resolve().parent.parent / "payload"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("z1n_launcher")


# ---- state ---------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("state.json unreadable, resetting")
    return {}


def save_state(s: dict) -> None:
    STATE_FILE.write_text(json.dumps(s, indent=2), encoding="utf-8")


# ---- docker management --------------------------------------------------

def _run_compose(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-f", str(COMPOSE_DIR / "docker-compose.yml"), *args]
    logger.info("compose: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def stack_up() -> bool:
    r = _run_compose(["up", "-d"], timeout=300)
    if r.returncode != 0:
        logger.error("compose up failed: %s", r.stderr.strip())
        return False
    return True


def stack_down() -> None:
    _run_compose(["down"], timeout=120)


def stack_logs(n: int = 200) -> str:
    r = _run_compose(["logs", "--tail", str(n), "backend"], timeout=30)
    return r.stdout or r.stderr


# ---- update check -------------------------------------------------------

def _semver_newer(remote: str, local: str) -> bool:
    """Trivial dotted compare. Returns True if remote > local."""
    def parts(v):
        return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())
    try:
        return parts(remote) > parts(local)
    except (ValueError, AttributeError):
        return False


def check_for_update() -> str | None:
    if requests is None:
        return None
    try:
        r = requests.get(UPDATE_FEED_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        latest = str(data.get("version", "")).strip()
        if latest and _semver_newer(latest, APP_VERSION):
            return latest
    except Exception as exc:  # noqa: BLE001
        logger.info("update check failed (non-fatal): %s", exc)
    return None


def update_loop(icon):
    state = load_state()
    while True:
        last = state.get("last_update_check_utc")
        due = True
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                due = (datetime.now(timezone.utc) - last_dt) > timedelta(
                    seconds=UPDATE_CHECK_INTERVAL_SEC
                )
            except ValueError:
                due = True
        if due:
            latest = check_for_update()
            state["last_update_check_utc"] = datetime.now(timezone.utc).isoformat()
            if latest:
                state["update_available"] = latest
                icon.notify(
                    f"{APP_NAME} v{latest} is available. Visit releases.z1ncapital.in.",
                    "Update available",
                )
            save_state(state)
        time.sleep(60 * 60)  # re-evaluate hourly; gated by interval above


# ---- icon ----------------------------------------------------------------

def make_icon_image() -> Image.Image:
    """Generate a simple Z1N-teal square with 'Z' glyph. Replaces brand asset."""
    size = 64
    img = Image.new("RGB", (size, size), "#0F766E")
    d = ImageDraw.Draw(img)
    d.rectangle([6, 6, size - 6, size - 6], outline="white", width=2)
    d.text((22, 16), "Z", fill="white")
    return img


# ---- menu actions --------------------------------------------------------

def on_open_dashboard(icon, item):
    webbrowser.open(DASHBOARD_URL)


def on_view_logs(icon, item):
    """Open the launcher log file in the default editor."""
    try:
        os.startfile(str(LOG_FILE))  # type: ignore[attr-defined]
    except AttributeError:
        # Non-Windows fallback (dev).
        subprocess.Popen(["xdg-open", str(LOG_FILE)])


def on_restart(icon, item):
    icon.notify("Restarting backend...", APP_NAME)
    stack_down()
    if stack_up():
        icon.notify("Backend restarted.", APP_NAME)
    else:
        icon.notify("Restart failed. See logs.", APP_NAME)


def on_quit(icon, item):
    icon.notify("Stopping backend and exiting...", APP_NAME)
    stack_down()
    icon.stop()


def build_menu():
    return pystray.Menu(
        pystray.MenuItem("Open Dashboard", on_open_dashboard, default=True),
        pystray.MenuItem("View Logs", on_view_logs),
        pystray.MenuItem("Restart Backend", on_restart),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"v{APP_VERSION}", None, enabled=False),
        pystray.MenuItem("Quit", on_quit),
    )


# ---- first-run gate ------------------------------------------------------

def maybe_run_wizard() -> bool:
    """Returns True if user completed wizard or wizard not needed; False to abort."""
    state = load_state()
    if state.get("first_run_complete"):
        return True
    # Import here so tests can run without tkinter in some envs.
    try:
        from wizard import run_wizard  # type: ignore
    except ImportError:
        from . import wizard  # type: ignore
        run_wizard = wizard.run_wizard
    ok = run_wizard()
    if ok:
        state["first_run_complete"] = True
        state["first_run_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
    return ok


# ---- main ----------------------------------------------------------------

def main() -> int:
    logger.info("=== %s v%s launcher starting ===", APP_NAME, APP_VERSION)

    if not docker_available():
        logger.error("Docker Desktop not running")
        # Show a simple message via tk and exit; user can install / start Docker.
        try:
            import tkinter.messagebox as mb
            mb.showerror(
                APP_NAME,
                "Docker Desktop is not running. Please start it and re-launch "
                f"{APP_NAME}.",
            )
        except Exception:
            pass
        return 2

    if not maybe_run_wizard():
        logger.info("user cancelled wizard, exiting")
        return 1

    if not stack_up():
        try:
            import tkinter.messagebox as mb
            mb.showerror(
                APP_NAME,
                "Could not start the backend stack. See launcher.log in "
                f"{APP_DATA}.",
            )
        except Exception:
            pass
        return 3

    icon = pystray.Icon(
        "z1n_mf",
        icon=make_icon_image(),
        title=f"{APP_NAME} v{APP_VERSION}",
        menu=build_menu(),
    )

    threading.Thread(target=update_loop, args=(icon,), daemon=True).start()
    icon.notify(f"{APP_NAME} is running. Right-click for menu.", APP_NAME)
    icon.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
