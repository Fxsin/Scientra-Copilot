#!/usr/bin/env python3
"""
Scientra Copilot — One-Click Launcher

Orchestrates startup of:
  1. GROBID Docker container
  2. Scientra Copilot Query API (port 8710)
  3. Scientra Copilot Web frontend (port 3000)
  4. Opens browser to http://localhost:3000

Usage:
  python Scripts/start_all.py
  python Scripts/start_all.py --no-browser
  python Scripts/start_all.py --api-only
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "startup.log"
GROBID_CONTAINER = "scientra_grobid"
GROBID_HEALTH_URL = "http://localhost:18070/api/isalive"
API_URL = "http://localhost:8710"
API_HEALTH_URL = f"{API_URL}/health"
WEB_URL = "http://localhost:3000"

# ── Logging ──

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("startup")


def log_separator(title: str) -> None:
    log.info("=" * 60)
    log.info(f"  {title}")
    log.info("=" * 60)


# ── Health check helpers ──

def http_ok(url: str, timeout: float = 3.0) -> bool:
    """Return True if URL returns HTTP 2xx."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 100 <= resp.status < 400
    except Exception:
        return False


def wait_for_url(url: str, label: str, timeout: float = 30.0) -> bool:
    """Poll a URL until it responds or timeout."""
    log.info(f"Waiting for {label} at {url} ...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if http_ok(url):
            log.info(f"[OK] {label} is ready ({url})")
            return True
        time.sleep(0.8)
    log.error(f"[FAIL] {label} did not become ready within {timeout:.0f}s")
    return False


# ── Subprocess helpers ──

def run_detached(cmd: list[str], cwd: Path | None = None) -> subprocess.Popen:
    """Start a subprocess and return the Popen handle without waiting."""
    log.info(f"  Starting: {' '.join(str(c) for c in cmd)}")
    return subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


# ── 1. Python check ──

def check_python() -> bool:
    log_separator("1. Python Environment")
    ver = sys.version_info
    log.info(f"  Python {ver.major}.{ver.minor}.{ver.micro} — {sys.executable}")
    if ver < (3, 11):
        log.error("  Python 3.11+ is required.")
        return False
    return True


# ── 2. Docker / GROBID ──

def ensure_grobid() -> bool:
    log_separator("2. GROBID (Docker)")

    # Check if Docker is available
    try:
        subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            timeout=5,
        )
    except FileNotFoundError:
        log.error("  Docker CLI not found. Is Docker Desktop installed?")
        return False
    except Exception as exc:
        log.error(f"  Docker check failed: {exc}")
        return False

    # Check if GROBID is already healthy
    if http_ok(GROBID_HEALTH_URL):
        log.info(f"  [OK] GROBID already running ({GROBID_HEALTH_URL})")
        return True

    # Try docker start on existing container
    log.info(f"  GROBID not responding. Starting container '{GROBID_CONTAINER}' ...")
    try:
        result = subprocess.run(
            ["docker", "start", GROBID_CONTAINER],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "No such container" in stderr:
                log.error(
                    f"  Container '{GROBID_CONTAINER}' not found.\n"
                    f"  Create it first:\n"
                    f"    docker run -d --name {GROBID_CONTAINER} -p 18070:8070 -p 18071:8071 lfoppiano/grobid:0.8.1"
                )
                return False
            log.warning(f"  docker start warning: {stderr}")
    except Exception as exc:
        log.error(f"  Failed to start GROBID: {exc}")
        return False

    return wait_for_url(GROBID_HEALTH_URL, "GROBID", timeout=60.0)


# ── 3. Query API ──

def start_api() -> bool:
    log_separator("3. Scientra Copilot Query API")

    if http_ok(API_HEALTH_URL):
        log.info(f"  [OK] API already running ({API_HEALTH_URL})")
        return True

    script = PROJECT_ROOT / "Scripts" / "run_api_server.py"
    if not script.exists():
        log.error(f"  Script not found: {script}")
        return False

    run_detached([sys.executable, str(script), "--port", "8710"])
    return wait_for_url(API_HEALTH_URL, "Query API", timeout=15.0)


# ── 4. Web Frontend ──

def start_web() -> bool:
    log_separator("4. Scientra Copilot Web Frontend")

    if http_ok(WEB_URL):
        log.info(f"  [OK] Web already running ({WEB_URL})")
        return True

    web_dir = PROJECT_ROOT / "web"
    if not (web_dir / "package.json").exists():
        log.warning("  web/package.json not found. Skipping web frontend.")
        return True  # Not an error — web UI is optional

    npm = "npm.cmd" if sys.platform == "win32" else "npm"

    # Auto-install npm dependencies if node_modules is missing
    if not (web_dir / "node_modules").exists():
        log.info("  Installing web dependencies (npm install)...")
        try:
            result = subprocess.run(
                [npm, "install"],
                cwd=str(web_dir),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                log.error(f"  npm install failed:\n{result.stderr[-500:]}")
                return False
            log.info("  [OK] npm install complete.")
        except subprocess.TimeoutExpired:
            log.error("  npm install timed out (>10 min).")
            return False
        except Exception as exc:
            log.error(f"  npm install failed: {exc}")
            return False
    else:
        log.info("  [OK] node_modules found. Skipping npm install.")

    run_detached([npm, "run", "dev"], cwd=web_dir)
    return wait_for_url(WEB_URL, "Web Frontend", timeout=30.0)


# ── 5. Browser ──

def open_browser() -> None:
    log_separator("5. Browser")
    log.info(f"  Opening {WEB_URL} ...")
    webbrowser.open_new_tab(WEB_URL)


# ── Main ──

def main() -> int:
    parser = argparse.ArgumentParser(description="Scientra Copilot one-click launcher")
    parser.add_argument("--no-browser", action="store_true", help="Skip opening browser")
    parser.add_argument("--api-only", action="store_true", help="Only start API, skip web")
    parser.add_argument("--web-only", action="store_true", help="Only start web, skip API/GROBID")
    args = parser.parse_args()

    log.info(f"Scientra Copilot Startup — {datetime.now().isoformat(timespec='seconds')}")
    log.info(f"Log file: {LOG_FILE}")

    errors: list[str] = []

    if not args.web_only:
        if not check_python():
            errors.append("Python check failed")
        if not ensure_grobid():
            errors.append("GROBID unavailable")
        if not start_api():
            errors.append("Query API failed to start")

    if not args.api_only:
        if not start_web():
            errors.append("Web frontend failed to start")

    if errors:
        log_separator("STARTUP FAILED")
        for err in errors:
            log.error(f"  [FAIL] {err}")
        log.info(f"  Log: {LOG_FILE}")
        return 1

    if not args.no_browser and not args.api_only:
        open_browser()

    log_separator("ALL SERVICES READY")
    log.info(f"  GROBID:   {GROBID_HEALTH_URL}")
    log.info(f"  API:      {API_URL}")
    log.info(f"  Web:      {WEB_URL}")
    log.info(f"  Log:      {LOG_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
