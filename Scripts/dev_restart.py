#!/usr/bin/env python3
"""
Scientra Copilot — Development Restart Script

One-command development environment startup with automatic:
  - Port conflict detection & resolution
  - Old API detection & graceful fallback
  - .env.local synchronization
  - Next.js cache cleanup
  - Schema validation

Usage:
  python Scripts/dev_restart.py
  python Scripts/dev_restart.py --api-port 8710 --web-port 3000
  python Scripts/dev_restart.py --kill-old
  python Scripts/dev_restart.py --no-web
  python Scripts/dev_restart.py --open
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Project root ──
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ── Default ports ──
DEFAULT_API_PORTS = [8710, 8711, 8712, 8713, 8720]
DEFAULT_WEB_PORTS = [3000, 3001, 3002]

# ── Health & schema paths ──
API_HEALTH_PATH = "/health"
API_RESEARCH_MAP_PATH = "/research-map"
API_VERSION_PATH = "/version"

# ── Ensure UTF-8 output on Windows ──
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Colours for terminal output ──
class Colour:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

# ASCII-safe fallback symbols
OK = "[OK]"
WARN = "[WARN]"
ERR = "[ERR]"

def green(s: str) -> str: return f"{Colour.GREEN}{s}{Colour.RESET}"
def yellow(s: str) -> str: return f"{Colour.YELLOW}{s}{Colour.RESET}"
def red(s: str) -> str: return f"{Colour.RED}{s}{Colour.RESET}"
def cyan(s: str) -> str: return f"{Colour.CYAN}{s}{Colour.RESET}"
def bold(s: str) -> str: return f"{Colour.BOLD}{s}{Colour.RESET}"


# =============================================================================================================================================================================================
# Step 1: Validate project root
# =============================================================================================================================================================================================

def validate_root() -> bool:
    """Ensure we are in the Scientra Copilot project root."""
    checks = [
        PROJECT_ROOT / "scientra" / "server.py",
        PROJECT_ROOT / "web" / "package.json",
        PROJECT_ROOT / "Scripts" / "run_api_server.py",
    ]
    all_ok = True
    for path in checks:
        if not path.exists():
            print(f"  {red(ERR)} Missing: {path.relative_to(PROJECT_ROOT)}")
            all_ok = False
    if not all_ok:
        print(f"\n{red('ERROR:')} Not in Scientra Copilot project root.")
        print(f"  Expected root: {PROJECT_ROOT}")
        sys.exit(1)
    return True


# =============================================================================================================================================================================================
# Networking helpers
# =============================================================================================================================================================================================

def is_port_in_use(port: int) -> bool:
    """Check if a TCP port is listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(("127.0.0.1", port))
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def http_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    """HTTP GET returning (status_code, body_text)."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace") if e.fp else ""
    except Exception as e:
        return 0, str(e)


def http_ok(url: str, timeout: float = 3.0) -> bool:
    """Return True if URL returns 2xx/3xx."""
    code, _ = http_get(url, timeout)
    return 100 <= code < 400


def get_process_on_port(port: int) -> tuple[str | None, str | None]:
    """Return (process_name, pid) for the process listening on port, or (None, None)."""
    if sys.platform != "win32":
        try:
            result = subprocess.run(
                ["lsof", "-i", f"tcp:{port}", "-t"],
                capture_output=True, text=True, timeout=5,
            )
            pid = result.stdout.strip()
            return ("process", pid) if pid else (None, None)
        except Exception:
            return (None, None)

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
                    return (proc_name, pid)
                except Exception:
                    return ("unknown", pid)
        return (None, None)
    except Exception:
        return (None, None)


def kill_process_on_port(port: int) -> bool:
    """Try to kill the process on a port. Returns True if successful."""
    proc_name, pid = get_process_on_port(port)
    if not pid:
        return False
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", pid, "/F"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                print(f"  {green('OK')} Killed {proc_name} (PID {pid}) on port {port}")
                time.sleep(1.5)
                return True
            else:
                print(f"  {yellow('WARN')} Could not kill PID {pid}: {result.stderr.strip()[:200]}")
                return False
        except Exception as e:
            print(f"  {yellow('WARN')} taskkill failed: {e}")
            return False
    else:
        try:
            subprocess.run(["kill", "-9", pid], capture_output=True, timeout=5)
            return True
        except Exception:
            return False


# =============================================================================================================================================================================================
# Step 2: Detect API port
# =============================================================================================================================================================================================

def is_scientra_api(port: int) -> tuple[bool, str]:
    """Check if port hosts a Scientra API. Returns (is_api, schema_version)."""
    code, body = http_get(f"http://127.0.0.1:{port}{API_HEALTH_PATH}", timeout=3.0)
    if code < 200 or code >= 400:
        return False, ""

    # Try /version endpoint for explicit version check
    ver_code, ver_body = http_get(f"http://127.0.0.1:{port}{API_VERSION_PATH}", timeout=2.0)
    if ver_code == 200:
        try:
            ver_data = json.loads(ver_body)
            return True, ver_data.get("research_map_schema", "unknown")
        except json.JSONDecodeError:
            pass

    # Fallback: check research-map schema
    rm_code, rm_body = http_get(f"http://127.0.0.1:{port}{API_RESEARCH_MAP_PATH}", timeout=3.0)
    if rm_code == 200:
        try:
            rm_data = json.loads(rm_body)
            if "clusters" in rm_data or "mature_topics" in rm_data:
                return True, "v2"
            if "topics" in rm_data and "papers" in rm_data:
                return True, "v1"
        except json.JSONDecodeError:
            pass

    # It's serving HTTP but not Scientra
    return False, ""


def find_api_port(requested: int | None, kill_old: bool) -> int:
    """Find a suitable API port. Tries requested, then defaults."""
    ports_to_try = [requested] if requested else DEFAULT_API_PORTS
    ports_to_try = [p for p in ports_to_try if p is not None]

    for port in ports_to_try:
        if not is_port_in_use(port):
            print(f"  {green('OK')} Port {port} is free — will use for API")
            return port

        # Port is in use — check if it's a Scientra API
        is_api, schema_ver = is_scientra_api(port)
        if is_api:
            if schema_ver == "v2":
                print(f"  {green('OK')} Port {port}: Scientra API v2 already running — reusing")
                return port
            else:
                print(f"  {yellow('WARN')} Port {port}: OLD Scientra API (schema {schema_ver or 'v1'})")
                proc_name, pid = get_process_on_port(port)
                if proc_name and pid:
                    print(f"      Process: {proc_name} (PID {pid})")
                if kill_old:
                    print(f"      Attempting to stop old API on port {port}...")
                    if kill_process_on_port(port):
                        time.sleep(1)
                        if not is_port_in_use(port):
                            print(f"  {green('OK')} Port {port} freed — will use for API")
                            return port
                    print(f"  {yellow('WARN')} Could not kill old API — trying next port")
                else:
                    print(f"      Use --kill-old to attempt automatic stop.")
                    print(f"      Or manually: taskkill /PID {pid} /F  (requires admin)")
                continue
        else:
            proc_name, pid = get_process_on_port(port)
            print(f"  {yellow('WARN')} Port {port} occupied by non-Scientra process: {proc_name or 'unknown'}")
            if pid:
                print(f"      PID: {pid}")
            continue

    # All ports are occupied by non-Scientra processes
    # Try additional fallback ports
    for fallback in range(8721, 8730):
        if not is_port_in_use(fallback):
            print(f"  {green('OK')} Using fallback port {fallback} for API")
            return fallback

    print(f"\n{red('ERROR:')} No API ports available (tried {ports_to_try} and fallbacks).")
    print("  Please free a port manually and re-run.")
    sys.exit(1)


# =============================================================================================================================================================================================
# Step 4: Start API server
# =============================================================================================================================================================================================

def start_api(port: int) -> subprocess.Popen | None:
    """Start the API server. Returns Popen handle or None on failure."""
    script = PROJECT_ROOT / "Scripts" / "run_api_server.py"
    print(f"\n{cyan('=========')} Starting API server on port {port} {cyan('=========')}")
    print(f"  Command: python Scripts/run_api_server.py --port {port}")

    try:
        proc = subprocess.Popen(
            [sys.executable, str(script), "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception as e:
        print(f"  {red('ERR')} Failed to start API process: {e}")
        return None

    # Wait for health endpoint
    print(f"  Waiting for API health check...", end="", flush=True)
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(f"\n  {red('ERR')} API process exited with code {proc.returncode}")
            return None
        if http_ok(f"http://127.0.0.1:{port}{API_HEALTH_PATH}", timeout=1.0):
            print(f" {green('OK')}")
            return proc
        print(".", end="", flush=True)
        time.sleep(0.8)

    print(f"\n  {red('ERR')} API did not start within 30 seconds")
    return None


# =============================================================================================================================================================================================
# Step 5: Write .env.local
# =============================================================================================================================================================================================

def write_env_local(api_port: int) -> None:
    """Write or update web/.env.local with the correct API URL."""
    env_path = PROJECT_ROOT / "web" / ".env.local"
    api_url = f"http://127.0.0.1:{api_port}"

    # Read existing
    existing_lines: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                existing_lines[key.strip()] = val.strip()

    # Backup
    if env_path.exists():
        bak_path = env_path.with_suffix(".local.bak")
        shutil.copy2(env_path, bak_path)
        print(f"  Backed up existing .env.local → .env.local.bak")

    # Update/add the two API variables
    existing_lines["NEXT_PUBLIC_SCIENTRA_API_URL"] = api_url
    existing_lines["NEXT_PUBLIC_SCIENTRA_API_PORT"] = str(api_port)

    # Write
    lines = [f"{k}={v}" for k, v in existing_lines.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {green('OK')} web/.env.local → {api_url}")


# =============================================================================================================================================================================================
# Step 6: Clean Next.js cache
# =============================================================================================================================================================================================

def clean_next_cache() -> None:
    """Remove web/.next directory."""
    next_dir = PROJECT_ROOT / "web" / ".next"
    if not next_dir.exists():
        print(f"  No .next cache to clean")
        return
    try:
        shutil.rmtree(next_dir)
        print(f"  {green('OK')} Cleaned web/.next cache")
    except PermissionError:
        print(f"  {yellow('WARN')} Cannot delete web/.next — permission denied")
        print(f"      Files may be locked by a running dev server. Close it and re-run.")
    except Exception as e:
        print(f"  {yellow('WARN')} Could not clean .next: {e}")


# =============================================================================================================================================================================================
# Step 7: Start Web frontend
# =============================================================================================================================================================================================

def find_web_port(requested: int | None) -> int:
    """Find a suitable web port."""
    ports_to_try = [requested] if requested else DEFAULT_WEB_PORTS
    for port in ports_to_try:
        if not is_port_in_use(port):
            return port
        # Check if it's already a Next.js dev server (acceptable reuse)
        if http_ok(f"http://localhost:{port}", timeout=1.0):
            print(f"  {green('OK')} Web already running on port {port} — reusing")
            return port
    # Fallback
    for fallback in range(3003, 3010):
        if not is_port_in_use(fallback):
            return fallback
    return 3000  # last resort


def start_web(web_port: int) -> subprocess.Popen | None:
    """Start the Next.js dev server."""
    web_dir = PROJECT_ROOT / "web"
    npm = "npm.cmd" if sys.platform == "win32" else "npm"

    print(f"\n{cyan('=========')} Starting Web frontend on port {web_port} {cyan('=========')}")

    try:
        proc = subprocess.Popen(
            [npm, "run", "dev", "--", "-p", str(web_port)],
            cwd=str(web_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception as e:
        print(f"  {red('ERR')} Failed to start web process: {e}")
        return None

    print(f"  Next.js is compiling (Turbopack). First run may take 1-2 minutes...")
    print(f"  Waiting for web server...", end="", flush=True)

    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(f"\n  {red('ERR')} Web process exited with code {proc.returncode}")
            return None
        if http_ok(f"http://localhost:{web_port}", timeout=1.0):
            print(f" {green('OK')}")
            return proc
        print(".", end="", flush=True)
        time.sleep(1.5)

    print(f"\n  {yellow('WARN')} Web did not respond within 120s — may still be compiling")
    print(f"      Visit http://localhost:{web_port} manually in a moment.")
    return proc


# =============================================================================================================================================================================================
# Step 8: Schema validation
# =============================================================================================================================================================================================

def validate_schema(api_port: int, strict: bool = False) -> bool:
    """Validate that the API returns the expected Research Map schema."""
    print(f"\n{cyan('=========')} Schema Validation {cyan('=========')}")

    api_base = f"http://127.0.0.1:{api_port}"
    issues: list[str] = []

    # /health
    if http_ok(f"{api_base}{API_HEALTH_PATH}"):
        print(f"  {green('OK')} /health OK")
    else:
        issues.append("/health failed")
        print(f"  {red('ERR')} /health failed")

    # /research-map
    code, body = http_get(f"{api_base}{API_RESEARCH_MAP_PATH}", timeout=5.0)
    if code == 200:
        try:
            data = json.loads(body)
            top_keys = list(data.keys())
            print(f"  /research-map top-level keys: {top_keys}")

            # Check for new schema
            has_clusters = "clusters" in data and len(data.get("clusters", [])) > 0
            has_mature = "mature_topics" in data
            has_rels = "topic_relationships" in data

            # Check for old schema
            is_old_schema = set(top_keys) == {"topics", "papers"} and len(data.get("topics", [])) == 0

            if is_old_schema:
                issues.append("Old schema detected: {topics:[], papers:[]}")
                print(f"  {red('ERR')} OLD SCHEMA: {{topics:[], papers:[]}} — this is a stale API")
                print(f"      The frontend expects {{clusters, mature_topics, topic_relationships}}")
                return False

            if has_clusters or has_mature:
                clusters = data.get("clusters", [])
                mature = data.get("mature_topics", [])
                growing = data.get("growing_topics", [])
                gap = data.get("gap_topics", [])

                all_topics = clusters + mature + growing + gap
                seen_ids = set()
                unique_topics = []
                for t in all_topics:
                    tid = t.get("cluster_id") or t.get("id")
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        unique_topics.append(t)

                print(f"  {green('OK')} Topics: {len(unique_topics)} unique")

                # Check for papers
                topics_with_papers = sum(1 for t in unique_topics if t.get("papers") and len(t.get("papers", [])) > 0)
                topics_with_kw = sum(1 for t in unique_topics if t.get("keywords") and len(t.get("keywords", [])) > 0)
                print(f"  Topics with papers: {topics_with_papers}/{len(unique_topics)}")
                print(f"  Topics with keywords: {topics_with_kw}/{len(unique_topics)}")

                if topics_with_papers == 0:
                    issues.append("No topics have papers")
                if topics_with_kw == 0:
                    issues.append("No topics have keywords")

                # Check relationships
                rels = data.get("topic_relationships", [])
                print(f"  {green('OK') if len(rels) >= 0 else ''} Relationships: {len(rels)}")

                # Verify a topic detail
                if unique_topics:
                    sample_id = unique_topics[0].get("cluster_id") or unique_topics[0].get("id")
                    tc, tb = http_get(f"{api_base}/research-map/topic/{sample_id}", timeout=5.0)
                    if tc == 200:
                        td = json.loads(tb)
                        t = td.get("topic", td)
                        has_yd = "year_distribution" in t
                        has_ev = "evolution_phases" in t
                        has_rt = "related_topics" in t
                        print(f"  Topic detail: year_distribution={has_yd} evolution_phases={has_ev} related_topics={has_rt}")
                        if not has_ev:
                            issues.append("Topic detail missing evolution_phases")
                        if not has_rt:
                            issues.append("Topic detail missing related_topics (field should exist, even if empty)")
                    else:
                        issues.append(f"Topic detail returned HTTP {tc}")
            else:
                issues.append("Unknown /research-map schema")
                print(f"  {red('ERR')} Unknown schema — raw keys: {top_keys}")
        except json.JSONDecodeError:
            issues.append("/research-map returned invalid JSON")
            print(f"  {red('ERR')} Invalid JSON from /research-map")

    else:
        issues.append(f"/research-map returned HTTP {code}")
        print(f"  {red('ERR')} /research-map: HTTP {code}")

    # Summary
    if issues:
        print(f"\n  {red('Schema issues found:')}")
        for i in issues:
            print(f"    - {i}")
        if strict:
            print(f"\n{red('ERROR:')} Schema validation failed (--strict mode). Exiting.")
            sys.exit(1)
        else:
            print(f"\n  {yellow('WARN')} Schema validation had warnings (non-fatal).")
        return False
    else:
        print(f"\n  {green('OK')} Schema validation passed")
        return True


# =============================================================================================================================================================================================
# Step 9: Print access URLs
# =============================================================================================================================================================================================

def print_urls(api_port: int, web_port: int | None) -> None:
    """Print final access URLs."""
    print(f"\n{cyan('=========')} Access URLs {cyan('=========')}")
    print(f"  API Health:         http://127.0.0.1:{api_port}/health")
    print(f"  API Stats:          http://127.0.0.1:{api_port}/stats")
    print(f"  Research Map API:   http://127.0.0.1:{api_port}/research-map")
    print(f"  Evidence Query API: http://127.0.0.1:{api_port}/query/evidence")
    if web_port:
        print(f"  Web Research Map:   http://localhost:{web_port}/research-map")
        print(f"  Web Topic Detail:   http://localhost:{web_port}/research-map/topic/topic_001")


# =============================================================================================================================================================================================
# Main
# =============================================================================================================================================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scientra Copilot — Development Restart Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Scripts/dev_restart.py                    # Auto-detect ports
  python Scripts/dev_restart.py --api-port 8710    # Force API port
  python Scripts/dev_restart.py --kill-old         # Kill old API if needed
  python Scripts/dev_restart.py --no-web           # API only
  python Scripts/dev_restart.py --open             # Auto-open browser
  python Scripts/dev_restart.py --strict           # Fail on schema issues
        """,
    )
    parser.add_argument("--api-port", type=int, default=None, help="Preferred API port (default: auto-detect from 8710,8711,8712,8713,8720)")
    parser.add_argument("--web-port", type=int, default=None, help="Preferred Web port (default: auto-detect from 3000,3001,3002)")
    parser.add_argument("--kill-old", action="store_true", help="Attempt to kill old API processes on occupied ports")
    parser.add_argument("--no-web", action="store_true", help="Only start API, skip web frontend")
    parser.add_argument("--no-cache-clean", action="store_true", help="Skip .next cache cleanup")
    parser.add_argument("--open", action="store_true", help="Open browser to Research Map after startup")
    parser.add_argument("--strict", action="store_true", help="Exit with error if schema validation fails")
    args = parser.parse_args()

    print(f"\n{bold('Scientra Copilot — Dev Restart')}")
    print(f"  {datetime.now().isoformat(timespec='seconds')}")
    print(f"  Project: {PROJECT_ROOT}")
    print(f"  Platform: {platform.system()}")

    # ── Step 1: Validate root ──
    print(f"\n{cyan('=========')} Step 1: Project Root {cyan('=========')}")
    validate_root()
    print(f"  {green('OK')} Project root OK")

    # ── Step 2-3: Find API port ──
    print(f"\n{cyan('=========')} Step 2: API Port Detection {cyan('=========')}")
    api_port = find_api_port(args.api_port, args.kill_old)
    print(f"\n  → Selected API port: {green(str(api_port))}")

    # ── Step 4: Start API ──
    print(f"\n{cyan('=========')} Step 3: API Server {cyan('=========')}")
    api_proc = start_api(api_port)
    if api_proc is None:
        print(f"\n{red('FATAL:')} API server failed to start.")
        sys.exit(1)

    # ── Step 5: Write .env.local ──
    print(f"\n{cyan('=========')} Step 4: Frontend API Config {cyan('=========')}")
    write_env_local(api_port)

    # ── Step 6: Clean cache ──
    if not args.no_cache_clean:
        print(f"\n{cyan('=========')} Step 5: Next.js Cache {cyan('=========')}")
        clean_next_cache()

    # ── Step 7: Start Web ──
    web_port: int | None = None
    if not args.no_web:
        print(f"\n{cyan('=========')} Step 6: Web Port Detection {cyan('=========')}")
        web_port = find_web_port(args.web_port)
        print(f"  → Selected Web port: {green(str(web_port))}")

        print(f"\n{cyan('=========')} Step 7: Web Frontend {cyan('=========')}")
        web_proc = start_web(web_port)
        if web_proc is None:
            print(f"\n{yellow('WARN')} Web frontend failed to start — API is still available.")
            web_port = None

    # ── Step 8: Schema validation ──
    print(f"\n{cyan('=========')} Step 8: Schema Validation {cyan('=========')}")
    validate_schema(api_port, strict=args.strict)

    # ── Step 9: URLs ──
    print_urls(api_port, web_port)

    # ── Browser ──
    if args.open and web_port:
        import webbrowser
        url = f"http://localhost:{web_port}/research-map"
        print(f"\n  Opening {url} ...")
        webbrowser.open_new_tab(url)

    print(f"\n{bold(green('OK Ready!'))} API on port {api_port}" + (f", Web on port {web_port}" if web_port else " (API only)") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
