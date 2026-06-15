#!/usr/bin/env python3
"""P6.6.1 Scientra Copilot Startup Manager. Usage:
    python Scripts/start_scientra.py
    python Scripts/start_scientra.py --check-only
    python Scripts/start_scientra.py --api-only
    python Scripts/start_scientra.py --no-browser
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

API_DEFAULT_PORT = 8710
WEB_DEFAULT_PORT = 3000


def is_port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 100 <= resp.status < 400
    except Exception:
        return False


def wait_for_url(url: str, label: str, timeout: float = 30.0) -> bool:
    print(f"  Waiting for {label} at {url} ...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if http_ok(url):
            print(f"  ✅ {label} is ready")
            return True
        time.sleep(0.8)
    print(f"  ❌ {label} did not respond within {timeout:.0f}s")
    return False


def main() -> int:
    p = argparse.ArgumentParser(description="Scientra Copilot Startup Manager (P6.6.1)")
    p.add_argument("--check-only", action="store_true", help="Run environment check only, don't start services")
    p.add_argument("--api-only", action="store_true", help="Start API only, skip web frontend")
    p.add_argument("--no-browser", action="store_true", help="Don't open browser after startup")
    p.add_argument("--api-port", type=int, default=API_DEFAULT_PORT, help=f"API port (default: {API_DEFAULT_PORT})")
    p.add_argument("--root", type=Path, default=None, help="Project root path")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    args = p.parse_args()

    root = args.root or PROJECT_ROOT

    # ── Phase 1: Environment Check ──
    print(f"\n{'='*60}")
    print(f"  Scientra Copilot — Startup Manager (P6.6.1)")
    print(f"  {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print(f"{'='*60}")

    print(f"\n  📋 Phase 1: Environment Check\n")

    from scientra.environment.diagnostics import run_diagnostics
    from scientra.environment.repair import generate_repair_suggestions
    from scientra.environment.report_builder import build_all_health_reports

    diag = run_diagnostics(root)
    repair = generate_repair_suggestions(root)

    score = diag["health_score"]
    status = diag["status"]
    icon = "🟢" if status == "healthy" else ("🟡" if status == "degraded" else "🔴")

    print(f"  {icon} Health Score: {score}/100 — {status.upper()}")
    print(f"  ✅ {diag['passed']} passed  ⚠️  {diag['warnings']} warnings  ❌ {diag['failed']} failed")

    # Show failed items
    failed = [c for c in diag["checks"] if c["status"] == "FAIL"]
    if failed:
        print(f"\n  ❌ Critical Issues:")
        for c in failed:
            print(f"     • {c['name']}: {c.get('detail', '')[:100]}")
            if c.get("fix"):
                print(f"       Fix: {c['fix']}")

    # Show repair suggestions
    if repair:
        print(f"\n  🔧 Repair Suggestions ({len(repair)}):")
        for s in repair[:5]:
            sev = "🔴" if s["severity"] == "FAIL" else "🟡"
            print(f"     {sev} {s['problem']}: {s['fix'][:100]}")

    # Generate health reports
    reports = build_all_health_reports(root)
    print(f"\n  📄 Reports:")
    for name, path in reports.items():
        print(f"     {path}")

    if args.json:
        import json
        print(json.dumps({
            "health_score": score,
            "status": status,
            "diagnostics": diag,
            "repair_suggestions": repair,
        }, ensure_ascii=False, indent=2))

    if args.check_only:
        print(f"\n  Check complete. Not starting services (--check-only).\n")
        return 1 if diag["failed"] > 0 else 0

    # ── Phase 2: Start Services ──
    print(f"\n  🚀 Phase 2: Starting Services\n")

    api_port = args.api_port

    # Check if API is already running
    api_health_url = f"http://127.0.0.1:{api_port}/health"
    if http_ok(api_health_url):
        print(f"  ✅ API already running at http://127.0.0.1:{api_port}")
        print(f"     Health: {api_health_url}")
    else:
        if is_port_in_use(api_port):
            print(f"  ⚠️  Port {api_port} is occupied by another process.")
            print(f"     Try a different port: python Scripts/start_scientra.py --api-port {api_port + 1}")
            if not args.json:
                return 1

        # Start API
        print(f"  Starting API server on port {api_port}...")
        script = root / "Scripts" / "run_api_server.py"
        if not script.exists():
            print(f"  ❌ API script not found: {script}")
            return 1

        proc = subprocess.Popen(
            [sys.executable, str(script), "--port", str(api_port), "--host", "0.0.0.0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        time.sleep(2)
        if proc.poll() is not None:
            print(f"  ❌ API process exited (code {proc.returncode}). Check logs.")
            print(f"     Try: python Scripts/run_api_server.py --port {api_port}")
            return 1

        if not wait_for_url(api_health_url, "API /health", timeout=20.0):
            print(f"  ❌ API did not start. Try manually: python Scripts/run_api_server.py --port {api_port}")
            return 1

    # ── Phase 3: Web URL (informational) ──
    if not args.api_only:
        web_port = WEB_DEFAULT_PORT
        web_url = f"http://localhost:{web_port}"

        print(f"\n  🌐 Frontend URL: {web_url}")
        print(f"  📡 API Base URL: http://127.0.0.1:{api_port}")
        print(f"  💚 Health URL:  http://127.0.0.1:{api_port}/health")

        # Check if web is running
        if http_ok(web_url):
            print(f"  ✅ Web frontend detected at {web_url}")
        else:
            print(f"  ℹ️  Web frontend not running at {web_url}")
            print(f"     Start it manually: cd web && npm run dev")

        if not args.no_browser:
            if http_ok(web_url):
                print(f"\n  🌍 Opening {web_url} ...")
                webbrowser.open_new_tab(web_url)
            else:
                print(f"\n  ℹ️  Skipping browser — web frontend not running.")

    print(f"\n{'='*60}")
    print(f"  ✅ Scientra Copilot is ready!")
    print(f"  API:  http://127.0.0.1:{api_port}/health")
    print(f"  Docs: http://127.0.0.1:{api_port}/docs")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
