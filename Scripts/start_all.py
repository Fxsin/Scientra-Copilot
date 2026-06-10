#!/usr/bin/env python3
"""
Scientra Copilot — One-Click Launcher (Production Version)

Orchestrates startup of:
  1. GROBID Docker container
  2. Scientra Copilot Query API
  3. Scientra Copilot Web frontend
  4. Opens browser to the actual Web URL

Ports are configurable via environment variables:
  SCIENTRA_WEB_PORT    (default 3000)
  SCIENTRA_API_PORT    (default 8710)
  SCIENTRA_GROBID_PORT (default 18070)

Usage:
  python Scripts/start_all.py
  python Scripts/start_all.py --no-browser
  python Scripts/start_all.py --api-only
"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "startup.log"
DIAG_REPORT = REPORTS_DIR / "startup_diagnostics_report.md"

# ── Ports from environment variables ──
GROBID_CONTAINER = os.environ.get("SCIENTRA_GROBID_CONTAINER", "scientra_grobid")
GROBID_PORT = int(os.environ.get("SCIENTRA_GROBID_PORT", "18070"))
API_PORT = int(os.environ.get("SCIENTRA_API_PORT", "8710"))
WEB_PORT_START = int(os.environ.get("SCIENTRA_WEB_PORT", "3000"))

# These will be updated at runtime if ports change
actual_grobid_port: int = GROBID_PORT
actual_api_port: int = API_PORT
actual_web_port: int = WEB_PORT_START

GROBID_HEALTH_PATH = "/api/isalive"
API_HEALTH_PATH = "/health"

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

# ── Diagnostics collector ──

_diag: dict[str, Any] = {
    "started_at": datetime.now().isoformat(timespec="seconds"),
    "os": platform.system(),
    "os_version": platform.version(),
    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    "services": {},
}


def log_separator(title: str) -> None:
    log.info("=" * 60)
    log.info(f"  {title}")
    log.info("=" * 60)


# ── Port / process utilities ──

def is_port_in_use(port: int) -> bool:
    """Check if a TCP port is currently listening on localhost."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(("127.0.0.1", port))
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def get_process_on_port(port: int) -> str | None:
    """Return the process name/PID using a given port (Windows only for now)."""
    if sys.platform != "win32":
        try:
            result = subprocess.run(
                ["lsof", "-i", f"tcp:{port}", "-t"],
                capture_output=True, text=True, timeout=5,
            )
            return f"PID {result.stdout.strip()}" if result.stdout.strip() else None
        except Exception:
            return None

    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                try:
                    task = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, timeout=5,
                    )
                    proc_name = task.stdout.strip().split(",")[0].strip('"') if task.stdout else "unknown"
                    return f"{proc_name} (PID {pid})"
                except Exception:
                    return f"PID {pid}"
        return None
    except Exception:
        return None


def http_ok(url: str, timeout: float = 3.0) -> bool:
    """Return True if URL returns HTTP 2xx/3xx."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 100 <= resp.status < 400
    except Exception:
        return False


def wait_for_url(url: str, label: str, timeout: float = 30.0) -> bool:
    """Poll a URL until it responds or timeout."""
    log.info(f"  Waiting for {label} at {url} ...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if http_ok(url):
            log.info(f"  [OK] {label} is ready ({url})")
            return True
        time.sleep(0.8)
    log.error(f"  [FAIL] {label} did not become ready within {timeout:.0f}s")
    return False


def run_detached(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.Popen:
    """Start a subprocess and return the Popen handle without waiting."""
    log.info(f"  Starting: {' '.join(str(c) for c in cmd)}")
    return subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env or dict(os.environ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


# ── Preflight checks ──

def check_python() -> bool:
    """Verify Python version meets requirements."""
    ver = sys.version_info
    log.info(f"  Python {ver.major}.{ver.minor}.{ver.micro} — {sys.executable}")
    if ver < (3, 11):
        log.error("  Python 3.11+ is required. You are running Python %s.%s.", ver.major, ver.minor)
        _diag["python_ok"] = False
        return False
    _diag["python_ok"] = True
    return True


def check_node_npm() -> bool:
    """Verify Node.js and npm are available."""
    ok = True
    # Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        ver = result.stdout.strip()
        log.info(f"  Node.js {ver}")
        _diag["node_version"] = ver
    except Exception:
        log.error("  Node.js not found. Please install Node.js from https://nodejs.org")
        _diag["node_version"] = None
        ok = False

    # npm
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    try:
        result = subprocess.run([npm, "--version"], capture_output=True, text=True, timeout=5)
        ver = result.stdout.strip()
        log.info(f"  npm {ver}")
        _diag["npm_version"] = ver
    except Exception:
        log.error("  npm not found.")
        _diag["npm_version"] = None
        ok = False

    # pnpm (optional)
    pnpm = "pnpm.cmd" if sys.platform == "win32" else "pnpm"
    try:
        result = subprocess.run([pnpm, "--version"], capture_output=True, text=True, timeout=5)
        log.info(f"  pnpm {result.stdout.strip()}")
        _diag["pnpm_version"] = result.stdout.strip()
    except Exception:
        _diag["pnpm_version"] = None

    return ok


def check_docker() -> tuple[bool, str]:
    """Check Docker availability. Returns (ok, message)."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        log.info(f"  Docker CLI: {result.stdout.strip()}")
        _diag["docker_cli"] = result.stdout.strip()
    except FileNotFoundError:
        msg = "Docker CLI not found. Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
        log.error(f"  {msg}")
        return False, msg
    except Exception as exc:
        msg = f"Docker check failed: {exc}"
        log.error(f"  {msg}")
        return False, msg

    # Check Docker daemon
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            log.info(f"  Docker daemon: v{result.stdout.strip()}")
            _diag["docker_daemon"] = result.stdout.strip()
            return True, ""
        else:
            msg = (
                "Docker Desktop is installed but the Docker daemon is not running.\n"
                "  Please open Docker Desktop and wait for it to fully start, then re-run:\n"
                "    python Scripts/start_all.py"
            )
            log.error(f"  {msg}")
            return False, msg
    except Exception:
        msg = (
            "Cannot connect to Docker daemon.\n"
            "  Please ensure Docker Desktop is running, then re-run:\n"
            "    python Scripts/start_all.py"
        )
        log.error(f"  {msg}")
        return False, msg


def check_config_files() -> list[str]:
    """Check critical config files exist. Returns list of missing files."""
    required = [
        PROJECT_ROOT / "Config" / "grobid.yaml",
        PROJECT_ROOT / "web" / "package.json",
        PROJECT_ROOT / "Config" / "workflow_config.yaml",
    ]
    missing = []
    for f in required:
        if f.exists():
            log.info(f"  [OK] {f.relative_to(PROJECT_ROOT)}")
        else:
            log.error(f"  [MISSING] {f.relative_to(PROJECT_ROOT)}")
            missing.append(str(f.relative_to(PROJECT_ROOT)))
    return missing


def check_node_modules() -> bool:
    """Check web/node_modules exists."""
    nm = PROJECT_ROOT / "web" / "node_modules"
    if nm.exists():
        log.info("  [OK] web/node_modules found")
        return True
    log.warning("  web/node_modules not found — will install dependencies on first run")
    return False


def run_preflight() -> bool:
    """Run all preflight checks. Returns True if all pass."""
    log_separator("Preflight Checks")

    all_ok = True

    # 1. Python
    if not check_python():
        all_ok = False

    # 2. Node + npm
    if not check_node_npm():
        all_ok = False

    # 3. Docker
    docker_ok, _ = check_docker()
    if not docker_ok:
        all_ok = False

    # 4. Config files
    missing_configs = check_config_files()
    if missing_configs:
        log.error(f"  Missing config files: {', '.join(missing_configs)}")
        all_ok = False

    # 5. node_modules
    check_node_modules()

    # 6. Port pre-check
    log.info("  Port pre-check:")
    for label, port in [("Web", WEB_PORT_START), ("API", API_PORT), ("GROBID", GROBID_PORT)]:
        used = is_port_in_use(port)
        proc = get_process_on_port(port) if used else None
        _diag.setdefault("port_check", {})[label] = {"port": port, "in_use": used, "process": proc}
        if used:
            log.info(f"    {label} port {port}: IN USE by {proc}")
        else:
            log.info(f"    {label} port {port}: free")

    return all_ok


# ── GROBID ──

def ensure_grobid() -> bool:
    """Start or verify GROBID Docker container."""
    global actual_grobid_port
    log_separator("GROBID (Docker)")

    grobid_url = f"http://localhost:{actual_grobid_port}{GROBID_HEALTH_PATH}"

    # Already running?
    if http_ok(grobid_url):
        log.info(f"  [OK] GROBID already running at {grobid_url}")
        _diag["services"]["grobid"] = {"status": "reused", "port": actual_grobid_port, "url": grobid_url}
        return True

    # Port occupied by something else?
    if is_port_in_use(actual_grobid_port):
        proc = get_process_on_port(actual_grobid_port)
        log.error(
            f"  GROBID port {actual_grobid_port} is occupied by {proc}, but it is not a GROBID service.\n"
            f"  Solutions:\n"
            f"    1. Close the program using port {actual_grobid_port}.\n"
            f"    2. Use a different port:\n"
            f'       $env:SCIENTRA_GROBID_PORT="{actual_grobid_port + 1}"\n'
            f"       python Scripts/start_all.py"
        )
        _diag["services"]["grobid"] = {"status": "failed", "reason": f"Port {actual_grobid_port} occupied by {proc}"}
        return False

    # Try docker start on existing container
    log.info(f"  Starting GROBID container '{GROBID_CONTAINER}' ...")
    try:
        result = subprocess.run(
            ["docker", "start", GROBID_CONTAINER],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "No such container" in stderr:
                log.error(
                    f"  GROBID container '{GROBID_CONTAINER}' not found.\n"
                    f"  Create it first:\n"
                    f"    docker run -d --name {GROBID_CONTAINER} "
                    f"-p {actual_grobid_port}:8070 -p {actual_grobid_port + 1}:8071 "
                    f"lfoppiano/grobid:0.8.1"
                )
                _diag["services"]["grobid"] = {"status": "failed", "reason": "Container not found"}
                return False
            log.warning(f"  docker start: {stderr}")
    except Exception as exc:
        log.error(f"  Failed to start GROBID container: {exc}")
        _diag["services"]["grobid"] = {"status": "failed", "reason": str(exc)}
        return False

    if wait_for_url(grobid_url, "GROBID", timeout=60.0):
        _diag["services"]["grobid"] = {"status": "started", "port": actual_grobid_port, "url": grobid_url}
        return True

    _diag["services"]["grobid"] = {"status": "failed", "reason": "Timeout waiting for GROBID"}
    return False


# ── Query API ──

def is_scientra_api(port: int) -> bool:
    """Check if a service on the given port looks like Scientra API."""
    try:
        url = f"http://localhost:{port}{API_HEALTH_PATH}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if 100 <= resp.status < 400:
                return True
    except Exception:
        pass
    return False


def start_api() -> bool:
    """Start Scientra Copilot Query API with full health verification."""
    global actual_api_port
    log_separator("Scientra Copilot Query API")

    # Use 127.0.0.1 for reliability (avoids IPv6 localhost resolution issues)
    api_url = f"http://127.0.0.1:{actual_api_port}"
    api_health = f"{api_url}{API_HEALTH_PATH}"
    api_stats = f"{api_url}/stats"

    # Already running?
    if is_scientra_api(actual_api_port):
        log.info(f"  [OK] Scientra API already running at {api_health}")
        # Verify /stats works too
        if http_ok(api_stats):
            log.info(f"  [OK] API /stats verified: {api_stats}")
            _diag["services"]["api"] = {"status": "reused", "port": actual_api_port, "url": api_url}
            return True
        else:
            log.warning(f"  API /health is reachable but /stats is not responding. Restarting API...")
            # Kill the broken API and restart
            proc = get_process_on_port(actual_api_port)
            if proc and sys.platform == "win32":
                pid = proc.split("PID ")[-1].rstrip(")") if "PID" in proc else ""
                if pid:
                    subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, timeout=5)
            time.sleep(2)

    # Port occupied by non-Scientra process?
    if is_port_in_use(actual_api_port):
        proc = get_process_on_port(actual_api_port)
        log.error(
            f"  API port {actual_api_port} is occupied by {proc}, which is not a Scientra API service.\n"
            f"  Solutions:\n"
            f"    1. Close the program using port {actual_api_port}.\n"
            f"    2. Use a different port:\n"
            f'       $env:SCIENTRA_API_PORT="{actual_api_port + 1}"\n'
            f"       python Scripts/start_all.py"
        )
        _diag["services"]["api"] = {"status": "failed", "reason": f"Port {actual_api_port} occupied by {proc}"}
        return False

    script = PROJECT_ROOT / "Scripts" / "run_api_server.py"
    if not script.exists():
        log.error(f"  API script not found: {script}")
        _diag["services"]["api"] = {"status": "failed", "reason": "run_api_server.py not found"}
        return False

    log.info(f"  Starting API on port {actual_api_port}...")
    proc = run_detached(
        [sys.executable, str(script), "--port", str(actual_api_port), "--host", "0.0.0.0"],
    )

    # Give the process a moment to start
    time.sleep(1.5)

    # Check if process died immediately
    if proc.poll() is not None:
        log.error(
            f"  API process exited immediately (code {proc.returncode}).\n"
            f"  Script: {script}\n"
            f"  Port: {actual_api_port}\n"
            f"  Try running manually to see errors:\n"
            f"    python Scripts/run_api_server.py --port {actual_api_port}\n"
            f"  Check Python dependencies: pip install fastapi uvicorn"
        )
        _diag["services"]["api"] = {"status": "failed", "reason": f"Process exited with code {proc.returncode}"}
        return False

    # Wait for /health
    if not wait_for_url(api_health, "API /health", timeout=15.0):
        log.error(
            f"  API /health not reachable within 15s.\n"
            f"  The process may have crashed. Check manually:\n"
            f"    curl {api_health}\n"
            f"  Or start manually:\n"
            f"    python Scripts/run_api_server.py --port {actual_api_port}"
        )
        _diag["services"]["api"] = {"status": "failed", "reason": "Timeout waiting for /health"}
        return False

    log.info(f"  [OK] API /health verified: {api_health}")

    # Wait for /stats (data endpoint)
    if not wait_for_url(api_stats, "API /stats", timeout=10.0):
        log.error(
            f"  API /health is reachable but /stats failed.\n"
            f"  The API may have started but data loading failed.\n"
            f"  Check: curl {api_stats}"
        )
        _diag["services"]["api"] = {"status": "failed", "reason": "Timeout waiting for /stats"}
        return False

    log.info(f"  [OK] API /stats verified: {api_stats}")
    _diag["services"]["api"] = {"status": "started", "port": actual_api_port, "url": api_url}
    return True


# ── Web Frontend ──

def is_scientra_web(port: int) -> bool:
    """Check if a service on the given port looks like Scientra Web (Next.js)."""
    try:
        url = f"http://localhost:{port}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            # Next.js returns 200 or 307; any valid HTTP response is a good sign
            return 100 <= resp.status < 500
    except Exception:
        return False


def find_available_web_port() -> int | None:
    """Try ports starting from WEB_PORT_START, up to WEB_PORT_START+4."""
    for offset in range(5):
        port = WEB_PORT_START + offset
        if is_scientra_web(port):
            # Already running Scientra Web
            log.info(f"  Found existing Scientra Web on port {port}")
            return port
        if not is_port_in_use(port):
            # Port is free
            return port
    return None


def start_web() -> bool:
    """Start Scientra Copilot Web frontend."""
    global actual_web_port
    log_separator("Scientra Copilot Web Frontend")

    web_dir = PROJECT_ROOT / "web"
    if not (web_dir / "package.json").exists():
        log.warning("  web/package.json not found. Skipping web frontend.")
        _diag["services"]["web"] = {"status": "skipped", "reason": "package.json not found"}
        return True

    npm = "npm.cmd" if sys.platform == "win32" else "npm"

    # Install dependencies if needed
    if not (web_dir / "node_modules").exists():
        log.info("  Installing web dependencies (npm install, may take a few minutes)...")
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
                _diag["services"]["web"] = {"status": "failed", "reason": "npm install failed"}
                return False
            log.info("  [OK] npm install complete.")
        except subprocess.TimeoutExpired:
            log.error("  npm install timed out (>10 min).")
            _diag["services"]["web"] = {"status": "failed", "reason": "npm install timeout"}
            return False
        except Exception as exc:
            log.error(f"  npm install failed: {exc}")
            _diag["services"]["web"] = {"status": "failed", "reason": str(exc)}
            return False

    # Find available port
    port = find_available_web_port()
    if port is None:
        log.error(
            f"  All Web ports {WEB_PORT_START}-{WEB_PORT_START + 4} are occupied.\n"
            f"  Solutions:\n"
            f"    1. Close programs using these ports.\n"
            f"    2. Use a different starting port:\n"
            f'       $env:SCIENTRA_WEB_PORT="{WEB_PORT_START + 10}"\n'
            f"       python Scripts/start_all.py"
        )
        _diag["services"]["web"] = {"status": "failed", "reason": "All ports occupied"}
        return False

    actual_web_port = port
    web_url = f"http://localhost:{actual_web_port}"

    # Check if already running
    if is_scientra_web(actual_web_port):
        log.info(f"  [OK] Scientra Web already running at {web_url}")
        _diag["services"]["web"] = {"status": "reused", "port": actual_web_port, "url": web_url}
        return True

    # If port shifted from default, inform user
    if actual_web_port != WEB_PORT_START:
        log.warning(
            f"  Port {WEB_PORT_START} is occupied. Using port {actual_web_port} instead.\n"
            f"  To change the default, set $env:SCIENTRA_WEB_PORT before running."
        )

    # Start Next.js with the correct API URL injected
    api_base_url = f"http://127.0.0.1:{actual_api_port}"
    web_env = dict(os.environ)
    web_env["NEXT_PUBLIC_SCIENTRA_API_URL"] = api_base_url
    web_env["NEXT_PUBLIC_SCIENTRA_API_PORT"] = str(actual_api_port)
    log.info(f"  Web API Base URL: {api_base_url}")

    run_detached([npm, "run", "dev", "--", "-p", str(actual_web_port)], cwd=web_dir, env=web_env)

    log.info("  Web frontend is compiling (Next.js/Turbopack). This may take 1-2 minutes on first run...")
    log.info("  Subsequent starts will be much faster.")

    if wait_for_url(web_url, "Web Frontend", timeout=120.0):
        _diag["services"]["web"] = {"status": "started", "port": actual_web_port, "url": web_url}
        if actual_web_port != WEB_PORT_START:
            _diag["services"]["web"]["note"] = f"Port shifted from {WEB_PORT_START} to {actual_web_port}"
        return True

    # Check if Next.js started but on a different port than we expected
    for offset in range(1, 5):
        alt_port = actual_web_port + offset
        alt_url = f"http://localhost:{alt_port}"
        if is_scientra_web(alt_port):
            log.warning(f"  Web started on {alt_url} instead of {web_url}")
            actual_web_port = alt_port
            _diag["services"]["web"] = {"status": "started", "port": actual_web_port, "url": alt_url,
                                         "note": "Next.js auto-selected different port"}
            return True

    log.error(
        f"  Web frontend did not respond within 120 seconds.\n"
        f"  The dev server may still be compiling, or may have crashed.\n"
        f"  Check Next.js output or visit {web_url} manually after a moment."
    )
    _diag["services"]["web"] = {"status": "failed", "reason": "Timeout (120s)"}
    return False


# ── Browser ──

def open_browser() -> None:
    """Open the actual Web URL in the default browser."""
    log_separator("Browser")
    web_url = f"http://localhost:{actual_web_port}"
    log.info(f"  Opening {web_url} ...")
    webbrowser.open_new_tab(web_url)


# ── Diagnostics Report ──

def write_diagnostics_report() -> None:
    """Generate startup_diagnostics_report.md."""
    lines: list[str] = []
    lines.append("# Scientra Copilot — Startup Diagnostics Report\n")
    lines.append(f"**Started at:** {_diag['started_at']}  ")
    lines.append(f"**OS:** {_diag['os']} {_diag.get('os_version', '')}  ")
    lines.append(f"**Python:** {_diag.get('python_version', '?')}  ")
    lines.append(f"**Node.js:** {_diag.get('node_version', 'not found')}  ")
    lines.append(f"**npm:** {_diag.get('npm_version', 'not found')}  ")
    if _diag.get("pnpm_version"):
        lines.append(f"**pnpm:** {_diag['pnpm_version']}  ")
    lines.append(f"**Docker:** {_diag.get('docker_daemon', 'not available')}  ")
    lines.append("")

    # Port check
    if "port_check" in _diag:
        lines.append("## Port Detection\n")
        lines.append("| Service | Port | Status | Process |")
        lines.append("|---------|------|--------|---------|")
        for svc, info in _diag["port_check"].items():
            status = "IN USE" if info["in_use"] else "free"
            proc = info.get("process") or "-"
            lines.append(f"| {svc} | {info['port']} | {status} | {proc} |")
        lines.append("")

    # Service status
    lines.append("## Service Status\n")
    lines.append("| Service | Status | Port | URL |")
    lines.append("|---------|--------|------|-----|")
    for svc_name, info in _diag.get("services", {}).items():
        status = info.get("status", "?")
        port = info.get("port", "-")
        url = info.get("url", "-")
        lines.append(f"| {svc_name} | {status} | {port} | {url} |")
    lines.append("")

    # Recommendations
    failures = [
        (name, info) for name, info in _diag.get("services", {}).items()
        if info.get("status") == "failed"
    ]
    if failures:
        lines.append("## Failures & Recommendations\n")
        for name, info in failures:
            lines.append(f"### {name}\n")
            lines.append(f"**Reason:** {info.get('reason', 'unknown')}  ")
            lines.append("**Suggestions:** Check the log above for detailed solutions.\n")
        lines.append("")

    lines.append(f"\n*Report generated at {datetime.now().isoformat(timespec='seconds')}*")
    DIAG_REPORT.write_text("\n".join(lines), encoding="utf-8")


# ── Main ──

def main() -> int:
    parser = argparse.ArgumentParser(description="Scientra Copilot one-click launcher")
    parser.add_argument("--no-browser", action="store_true", help="Skip opening browser")
    parser.add_argument("--api-only", action="store_true", help="Only start GROBID and API, skip web")
    parser.add_argument("--web-only", action="store_true", help="Only start web frontend")
    args = parser.parse_args()

    log.info(f"Scientra Copilot Startup — {datetime.now().isoformat(timespec='seconds')}")
    log.info(f"Log file: {LOG_FILE}")
    log.info(f"Diagnostics: {DIAG_REPORT}")

    errors: list[tuple[str, str]] = []  # (service, reason)

    # ── Preflight ──
    preflight_ok = run_preflight()

    if not preflight_ok and not args.web_only:
        log_separator("PREFLIGHT WARNING")
        log.warning("  Some preflight checks failed (see above). Starting services anyway...")

    # ── Start services ──
    if not args.web_only:
        if not ensure_grobid():
            errors.append(("GROBID", "Docker/GROBID unavailable"))
        if not start_api():
            errors.append(("API", "Query API failed to start — Web will NOT be started"))

    # Only start Web if API is available (Web depends on API for data)
    if not args.api_only:
        if not errors:
            if not start_web():
                errors.append(("Web", "Web frontend failed to start"))
        else:
            log.warning("  Skipping Web start because API is not available.")
            errors.append(("Web", "Skipped — API must be running first"))

    # ── Diagnostics report ──
    try:
        write_diagnostics_report()
    except Exception as exc:
        log.warning(f"  Could not write diagnostics report: {exc}")

    # ── Results ──
    if errors:
        log_separator("STARTUP ISSUES DETECTED")
        for svc, reason in errors:
            log.error(f"  {svc}: {reason}")
        log.info("")
        log.info("  For detailed diagnostics, see:")
        log.info(f"    {DIAG_REPORT}")
        log.info(f"  Log file: {LOG_FILE}")
        return 1

    # ── Success ──
    if not args.no_browser and not args.api_only and actual_web_port:
        open_browser()

    log_separator("ALL SERVICES READY")
    grobid_url = f"http://localhost:{actual_grobid_port}{GROBID_HEALTH_PATH}"
    api_base = f"http://127.0.0.1:{actual_api_port}"
    web_url = f"http://localhost:{actual_web_port}"
    log.info(f"  GROBID:        {grobid_url} ✅")
    log.info(f"  API Health:    {api_base}/health ✅")
    log.info(f"  API Stats:     {api_base}/stats ✅")
    log.info(f"  Web:           {web_url} ✅")
    log.info(f"  Web API URL:   {api_base}")
    if actual_web_port != WEB_PORT_START:
        log.info(f"  Note: Web port {WEB_PORT_START} was occupied; using port {actual_web_port} instead.")
    log.info(f"  Log:           {LOG_FILE}")
    log.info(f"  Diag:          {DIAG_REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
