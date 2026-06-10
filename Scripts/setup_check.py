#!/usr/bin/env python3
"""
Scientra Copilot — First-Run Environment Check

Comprehensive environment validation for first-time users.
Checks everything needed to run the pipeline, with clear fix suggestions.

Usage:
  python Scripts/setup_check.py           # Full check (interactive)
  python Scripts/setup_check.py --quick   # Skip BGE-M3 download check
  python Scripts/setup_check.py --json    # Machine-readable output
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

CHECK_ICONS = {"PASS": "OK", "FAIL": "FAIL", "WARN": "WARN", "INFO": " – "}

# ── Helpers ──


def port_in_use(port: int) -> bool:
    """Check if a TCP port is already bound."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def run_cmd(cmd: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def check(name: str, status: str, detail: str, fix: str = "") -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "fix": fix}


# ── Individual Checks ──


def check_python() -> dict[str, Any]:
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 11
    return check(
        "Python 3.11+",
        "PASS" if ok else "FAIL",
        f"Python {v.major}.{v.minor}.{v.micro} — {sys.executable}",
        "Install Python 3.11+ from https://www.python.org/downloads/" if not ok else "",
    )


def check_pip_deps() -> dict[str, Any]:
    missing: list[str] = []
    for mod, pkg in [
        ("yaml", "pyyaml"),
        ("fastapi", "fastapi"),
        ("lancedb", "lancedb"),
        ("loguru", "loguru"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return check("Core dependencies", "PASS", "All core packages installed")
    return check(
        "Core dependencies",
        "FAIL",
        f"Missing: {', '.join(missing)}",
        f"Run: pip install {' '.join(missing)}",
    )


def check_disk_space() -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(PROJECT_ROOT)
        free_gb = usage.free / (1024**3)
        if free_gb >= 10:
            return check("Disk space", "PASS", f"{free_gb:.1f} GB free")
        elif free_gb >= 2:
            return check(
                "Disk space", "WARN",
                f"Only {free_gb:.1f} GB free. BGE-M3 model needs ~2 GB.",
                "Free up space or use an external drive.",
            )
        else:
            return check(
                "Disk space", "FAIL",
                f"Only {free_gb:.1f} GB free. Need at least 2 GB for the embedding model.",
                "Free up disk space before continuing.",
            )
    except Exception:
        return check("Disk space", "WARN", "Could not check disk space")


def check_docker() -> dict[str, Any]:
    # Check CLI
    docker_path = shutil.which("docker")
    if not docker_path:
        return check(
            "Docker installed",
            "FAIL",
            "Docker CLI not found in PATH.",
            "Install Docker Desktop: https://docs.docker.com/desktop/",
        )
    # Check daemon
    result = run_cmd(["docker", "version", "--format", "{{.Server.Version}}"], timeout=10)
    if result.returncode != 0:
        return check(
            "Docker running",
            "FAIL",
            f"Docker installed but daemon not responding.",
            "Start Docker Desktop and wait for it to finish starting.",
        )
    return check("Docker", "PASS", f"Docker {result.stdout.strip()} — {docker_path}")


def check_grobid() -> dict[str, Any]:
    health_url = "http://localhost:18070/api/isalive"
    if http_ok(health_url):
        return check("GROBID service", "PASS", health_url)
    # Check if container exists
    result = run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}"], timeout=10)
    if "scientra_grobid" in result.stdout:
        return check(
            "GROBID service",
            "WARN",
            "Container exists but GROBID is not responding.",
            "Run: docker start scientra_grobid\nThen wait 30-60s for GROBID to load its models.",
        )
    return check(
        "GROBID service",
        "WARN",
        "GROBID container not found.",
        "Run: python Scripts/setup_grobid.py",
    )


def check_ports() -> dict[str, Any]:
    conflicts: list[int] = []
    for port in [18070, 8710]:
        if port_in_use(port):
            conflicts.append(port)
    if not conflicts:
        return check("Port availability", "PASS", "Ports 18070 (GROBID) and 8710 (API) available")
    return check(
        "Port availability",
        "WARN",
        f"Ports in use: {', '.join(map(str, conflicts))}",
        "Change ports in Config/grobid.yaml (GROBID) or Scripts/run_api_server.py --port (API).",
    )


def check_api_key() -> dict[str, Any]:
    keys_found: list[str] = []
    for var in ["ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "LITERATURE_OS_API_KEY"]:
        if os.environ.get(var):
            keys_found.append(var)
    if keys_found:
        return check("LLM API key", "PASS", f"Found: {', '.join(keys_found)}")
    return check(
        "LLM API key",
        "INFO",
        "No API key set. Summaries will use prompt-file mode.",
        "Set ANTHROPIC_API_KEY or DEEPSEEK_API_KEY env var for automatic summary generation.\n"
        "Without a key, summary prompts are written to 03_Summary/agent_prompts/ for manual resolution.",
    )


def check_bge_model_accessible() -> dict[str, Any]:
    """Light check — just verify sentence-transformers can find the model name. No download."""
    try:
        from sentence_transformers import SentenceTransformer
        return check("BGE-M3 model", "PASS", "sentence-transformers available (model downloads on first use)")
    except ImportError:
        return check(
            "BGE-M3 model",
            "WARN",
            "sentence-transformers not installed.",
            "Run: pip install sentence-transformers\n"
            "First embedding run will download BAAI/bge-m3 (~2 GB). This is a one-time download.",
        )
    except Exception as exc:
        return check("BGE-M3 model", "WARN", f"{type(exc).__name__}: {exc}")


def check_directory_structure() -> dict[str, Any]:
    required = [
        "00_Inbox", "01_PDF", "02_Metadata", "03_Summary",
        "04_VectorDB", "05_Index", "06_API", "07_Workflows",
        "Config", "Scripts",
    ]
    missing = [d for d in required if not (PROJECT_ROOT / d).is_dir()]
    if not missing:
        return check("Directory structure", "PASS", "All required directories present")
    return check(
        "Directory structure",
        "WARN",
        f"Missing: {', '.join(missing)}",
        "The workflow will auto-create needed directories on first run.",
    )


def check_pdf_count() -> dict[str, Any]:
    inbox = list((PROJECT_ROOT / "00_Inbox").glob("*.pdf"))
    pdf_dir = list((PROJECT_ROOT / "01_PDF").glob("*.pdf"))
    total = len(inbox) + len(pdf_dir)
    if total > 0:
        return check("PDFs found", "PASS", f"{total} PDF(s) — {len(inbox)} in Inbox, {len(pdf_dir)} in 01_PDF")
    return check(
        "PDFs found",
        "INFO",
        "No PDFs found. Ready to process — just add PDFs to 00_Inbox/ or 01_PDF/ and run the workflow.",
    )


# ── Main ──


def run_all_checks(quick: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        check_python(),
        check_pip_deps(),
        check_disk_space(),
        check_docker(),
        check_grobid(),
        check_ports(),
        check_api_key(),
        check_directory_structure(),
        check_pdf_count(),
    ]
    if not quick:
        checks.insert(5, check_bge_model_accessible())

    has_fail = any(c["status"] == "FAIL" for c in checks)
    has_warn = any(c["status"] == "WARN" for c in checks)

    return {
        "status": "FAIL" if has_fail else ("WARN" if has_warn else "READY"),
        "checks": checks,
    }


def print_checks(result: dict[str, Any], verbose: bool = True) -> None:
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║   Scientra Copilot — Environment Check       ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()

    for c in result["checks"]:
        icon = CHECK_ICONS.get(c["status"], " ? ")
        print(f"  [{icon}] {c['name']}")
        print(f"       {c['detail']}")
        if c["fix"] and verbose:
            for line in c["fix"].split("\n"):
                print(f"       → {line}")
        print()

    # Summary
    status = result["status"]
    if status == "READY":
        print("  ╔══════════════════════════════════════════════╗")
        print("  ║  All checks passed! System is ready.        ║")
        print("  ║  Run: python workflow.py --all              ║")
        print("  ╚══════════════════════════════════════════════╝")
    elif status == "WARN":
        print("  ╔══════════════════════════════════════════════╗")
        print("  ║  Warnings found but system is usable.       ║")
        print("  ║  Review the items marked [WARN] above.      ║")
        print("  ╚══════════════════════════════════════════════╝")
    else:
        print("  ╔══════════════════════════════════════════════╗")
        print("  ║  FAILURES detected. Fix items marked [FAIL]  ║")
        print("  ║  before running the workflow.               ║")
        print("  ╚══════════════════════════════════════════════╝")

    print(f"\n  Overall status: {status}")
    print(f"  For details: python Scripts/system_check.py")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scientra Copilot — First-Run Environment Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--quick", action="store_true", help="Skip BGE-M3 check")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--quiet", action="store_true", help="Only print summary")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = run_all_checks(quick=args.quick)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.quiet:
        print(result["status"])
    else:
        print_checks(result)

    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
