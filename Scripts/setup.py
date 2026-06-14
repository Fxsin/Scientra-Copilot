#!/usr/bin/env python3
"""
Scientra Copilot — Master One-Click Setup & Diagnostics
========================================================
Single entry point for ALL dependency installation and troubleshooting.

Usage:
  python Scripts/setup.py                    # Full check (interactive)
  python Scripts/setup.py --check            # Check only, no install
  python Scripts/setup.py --install          # Auto-install everything
  python Scripts/setup.py --install --yes    # Skip all prompts
  python Scripts/setup.py --json             # Machine-readable output
  python Scripts/setup.py --filter parsers   # Only parser-related checks

What this covers:
  [Core]       Python · pip deps · disk space · directory structure
  [Services]   Docker · GROBID · ports
  [Parsers]    PyMuPDF · OpenDataLoader · Marker · GROBID metadata
  [LLM]        API keys · summary mode · agent SDK
  [Data]       LanceDB · BGE-M3 embeddings · PDF count
  [API]        Query API · agent endpoint

How to add a new dependency in the future:
  Add an entry to the MODULES list below with check() and optional install().
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ── Constants ──

ICONS = {"PASS": "OK", "FAIL": "FAIL", "WARN": "WARN", "INFO": " --"}
GROBID_PORT = 18070
API_PORT = 8710


# ── Helpers ──

def check(name: str, status: str, detail: str, fix: str = "") -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def run_cmd(cmd: list[str], timeout: int = 30, env: dict | None = None) -> subprocess.CompletedProcess:
    merged = {**os.environ, **(env or {})}
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=merged)


def http_ok(url: str, timeout: float = 3.0) -> bool:
    from urllib.request import urlopen
    try:
        with urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def find_java11() -> str | None:
    """Find Java 11+ installation."""
    known = []
    if sys.platform == "win32":
        known = [
            r"C:\Program Files\ojdkbuild\java-11-openjdk-11.0.15-1",
            r"C:\Program Files\ojdkbuild\java-11-openjdk-11.0.15.9-1",
            r"C:\Program Files\Eclipse Adoptium\jdk-11",
            r"C:\Program Files\Microsoft\jdk-11",
            r"C:\Program Files\Java\jdk-11",
        ]
    else:
        known = [
            "/usr/lib/jvm/java-11-openjdk",
            "/usr/lib/jvm/java-11-openjdk-amd64",
            "/usr/lib/jvm/java-17-openjdk",
            "/opt/homebrew/opt/openjdk@11",
        ]
    for p in known:
        exe = "java.exe" if sys.platform == "win32" else "java"
        if (Path(p) / "bin" / exe).exists():
            return p
    env_home = os.environ.get("JAVA_HOME", "")
    if env_home:
        exe = "java.exe" if sys.platform == "win32" else "java"
        if (Path(env_home) / "bin" / exe).exists():
            return env_home
    return None


def java_version_str(java_home: str) -> str:
    exe = "java.exe" if sys.platform == "win32" else "java"
    java = Path(java_home) / "bin" / exe
    if not java.exists():
        return "unknown"
    try:
        result = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=10)
        out = result.stderr or result.stdout or ""
        return out.strip().split("\n")[0] if out else "unknown"
    except Exception:
        return "unknown"


def pip_install(packages: list[str]) -> tuple[bool, str]:
    if not packages:
        return True, ""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + packages,
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if l and "Successfully" in l]
            return True, lines[-1] if lines else "Installed"
        last = (result.stderr or result.stdout or "").strip().split("\n")[-1]
        return False, last[:200]
    except Exception as e:
        return False, str(e)[:200]


def try_import(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


# ── Module Registry ──
#
# Each entry: {
#   key, category, label,
#   check: fn() -> {"name","status","detail","fix"},
#   install: fn() -> {"name","status","detail","fix"} | None,
# }
#
# To add a new dependency, add a new dict to MODULES.

MODULES: list[dict[str, Any]] = []

# ──────────────────────────────────────────────
# Category: Core
# ──────────────────────────────────────────────

def _check_python():
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 11
    return check("Python 3.11+", "PASS" if ok else "FAIL",
                 f"Python {v.major}.{v.minor}.{v.micro}",
                 "Install Python 3.11+ from https://python.org" if not ok else "")

MODULES.append({"key": "python", "cat": "Core", "label": "Python 3.11+",
                "check": _check_python, "install": None})

def _check_pip_deps():
    required = {"yaml": "pyyaml", "fastapi": "fastapi", "lancedb": "lancedb",
                "loguru": "loguru", "uvicorn": "uvicorn"}
    missing = [pkg for mod, pkg in required.items() if not try_import(mod)]
    if not missing:
        return check("Core pip packages", "PASS", "All present")
    return check("Core pip packages", "FAIL",
                 f"Missing: {', '.join(missing)}",
                 f"pip install {' '.join(missing)}")

MODULES.append({"key": "core_deps", "cat": "Core", "label": "Core pip packages",
                "check": _check_pip_deps, "install": None})

def _check_disk():
    try:
        usage = shutil.disk_usage(PROJECT_ROOT)
        free_gb = usage.free / (1024**3)
        if free_gb >= 10:
            return check("Disk space", "PASS", f"{free_gb:.1f} GB free")
        elif free_gb >= 3:
            return check("Disk space", "WARN", f"{free_gb:.1f} GB free — models may need more",
                         "Free up space or use external drive")
        return check("Disk space", "FAIL", f"Only {free_gb:.1f} GB free — models need 5+ GB",
                     "Free up disk space")
    except Exception as e:
        return check("Disk space", "WARN", f"Could not check: {e}")

MODULES.append({"key": "disk", "cat": "Core", "label": "Disk space",
                "check": _check_disk, "install": None})

def _check_dirs():
    required = ["00_Inbox", "01_Sources", "02_Parse", "03_Assets", "Config", "Scripts"]
    missing = [d for d in required if not (PROJECT_ROOT / d).is_dir()]
    if not missing:
        return check("Directory structure", "PASS", "All required directories present")
    return check("Directory structure", "WARN",
                 f"Missing: {', '.join(missing)}",
                 "Workflow will auto-create needed directories")

MODULES.append({"key": "dirs", "cat": "Core", "label": "Directory structure",
                "check": _check_dirs, "install": None})

# ──────────────────────────────────────────────
# Category: Services
# ──────────────────────────────────────────────

def _check_docker():
    docker = shutil.which("docker")
    if not docker:
        return check("Docker", "WARN", "Not installed — GROBID needs Docker",
                     "Install Docker Desktop: https://docs.docker.com/desktop/")
    result = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                            capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return check("Docker", "PASS", f"v{result.stdout.strip()}")
    return check("Docker", "WARN", "Installed but daemon not running",
                 "Start Docker Desktop")

MODULES.append({"key": "docker", "cat": "Services", "label": "Docker",
                "check": _check_docker, "install": None})

def _check_ports():
    conflicts = [p for p in [GROBID_PORT, API_PORT] if port_in_use(p)]
    if not conflicts:
        return check("Ports", "PASS", f"{GROBID_PORT} (GROBID) + {API_PORT} (API) free")
    return check("Ports", "WARN",
                 f"Ports in use: {', '.join(map(str, conflicts))}",
                 "Change ports in Config/grobid.yaml or run_api_server.py --port")

MODULES.append({"key": "ports", "cat": "Services", "label": "Port availability",
                "check": _check_ports, "install": None})

# ──────────────────────────────────────────────
# Category: GROBID
# ──────────────────────────────────────────────

def _check_grobid_config():
    cfg = PROJECT_ROOT / "Config" / "grobid.yaml"
    if cfg.exists():
        return check("GROBID config", "PASS", "Config/grobid.yaml present")
    return check("GROBID config", "FAIL", "Config/grobid.yaml missing",
                 "Run: python Scripts/setup_grobid.py")

MODULES.append({"key": "grobid_cfg", "cat": "GROBID", "label": "GROBID config",
                "check": _check_grobid_config, "install": None})

def _check_grobid_service():
    if http_ok("http://localhost:18070/api/isalive"):
        return check("GROBID service", "PASS", "Running on :18070")
    result = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"],
                            capture_output=True, text=True, timeout=10)
    if "scientra_grobid" in result.stdout:
        return check("GROBID service", "WARN", "Container exists but not responding",
                     "docker start scientra_grobid && sleep 30")
    return check("GROBID service", "WARN", "Container not created",
                 "Run: python Scripts/setup_grobid.py")

def _install_grobid():
    setup_script = PROJECT_ROOT / "Scripts" / "setup_grobid.py"
    if not setup_script.exists():
        return check("GROBID", "FAIL", "setup_grobid.py not found")
    try:
        subprocess.run([sys.executable, str(setup_script)],
                       capture_output=True, text=True, timeout=300)
        return check("GROBID", "PASS", "Setup completed — container may be starting")
    except Exception as e:
        return check("GROBID", "WARN", str(e)[:200])

MODULES.append({"key": "grobid_svc", "cat": "GROBID", "label": "GROBID service",
                "check": _check_grobid_service, "install": _install_grobid})

# ──────────────────────────────────────────────
# Category: Parsers
# ──────────────────────────────────────────────

def _check_pymupdf():
    try:
        import fitz
        return check("PyMuPDF (fitz)", "PASS", f"v{fitz.version[0]} — PDF scan + figures")
    except ImportError:
        return check("PyMuPDF (fitz)", "FAIL", "Not installed",
                     "pip install pymupdf")

def _install_pymupdf():
    ok, msg = pip_install(["pymupdf"])
    return check("PyMuPDF (fitz)", "PASS" if ok else "FAIL",
                 msg, "pip install pymupdf" if not ok else "")

MODULES.append({"key": "pymupdf", "cat": "Parsers", "label": "PyMuPDF (fitz)",
                "check": _check_pymupdf, "install": _install_pymupdf})

def _check_opendataloader():
    if not try_import("opendataloader_pdf"):
        return check("OpenDataLoader PDF", "FAIL", "Python wrapper not installed",
                     "pip install opendataloader-pdf\nRequires Java 11+")
    try:
        import opendataloader_pdf
        jar = Path(opendataloader_pdf.__file__).parent / "jar" / "opendataloader-pdf-cli.jar"
        if not jar.exists():
            return check("OpenDataLoader PDF", "FAIL", "JAR missing",
                         "pip install --force-reinstall opendataloader-pdf")
        jar_mb = jar.stat().st_size / (1024**2)
    except Exception:
        jar_mb = 0

    java = find_java11()
    if not java:
        return check("OpenDataLoader PDF", "FAIL",
                     f"Wrapper + JAR ({jar_mb:.0f}MB) but Java 11+ missing",
                     "winget install ojdkbuild.openjdk.11.jdk  (Windows)\n"
                     "sudo apt install openjdk-11-jdk         (Linux)\n"
                     "brew install openjdk@11                 (macOS)")
    jv = java_version_str(java)
    return check("OpenDataLoader PDF", "PASS",
                 f"Wrapper + JAR {jar_mb:.0f}MB + {jv} — markdown/layout/tables")

def _install_opendataloader():
    details = []
    # Install Python wrapper
    ok, msg = pip_install(["opendataloader-pdf"])
    details.append(f"pip: {msg}")
    # Check Java
    java = find_java11()
    if not java and sys.platform == "win32":
        details.append("Installing Java 11 via winget...")
        try:
            subprocess.run(["winget", "install", "--id", "ojdkbuild.openjdk.11.jdk",
                           "--accept-source-agreements", "--accept-package-agreements"],
                          capture_output=True, text=True, timeout=300)
            java = find_java11()
            details.append("Java 11 installed" if java else "Java install may need reboot")
        except Exception:
            details.append("winget not available — install Java 11 manually")
    elif not java:
        details.append("Install Java 11: sudo apt install openjdk-11-jdk")

    status = "PASS" if ok else "FAIL"
    return check("OpenDataLoader PDF", status, " | ".join(details),
                 "" if ok else "Manual: pip install opendataloader-pdf + Java 11+")

MODULES.append({"key": "opendataloader", "cat": "Parsers", "label": "OpenDataLoader PDF",
                "check": _check_opendataloader, "install": _install_opendataloader})

def _check_marker():
    if not try_import("marker"):
        return check("Marker", "WARN", "Not installed (optional)",
                     "pip install marker-pdf  — disabled by default")
    # Check if actually functional
    try:
        importlib.import_module("marker.models")
        importlib.import_module("marker.output")
        return check("Marker", "PASS", "Package + models OK (models download on first use)")
    except ImportError as e:
        return check("Marker", "WARN",
                     f"Package installed but deps incomplete: {e}",
                     "Marker is disabled by default. Works best on Python 3.10/3.11.")
    except Exception as e:
        return check("Marker", "WARN", f"Installed with issues: {e}")

def _install_marker():
    marker_src = PROJECT_ROOT / "external" / "marker"
    if marker_src.exists() and (marker_src / "marker").is_dir():
        ok, msg = pip_install(["-e", str(marker_src)])
        if not ok:
            ok, msg = pip_install(["marker-pdf"])
    else:
        ok, msg = pip_install(["marker-pdf"])
    # Best-effort deps
    for dep in ["surya-ocr", "pdftext", "ftfy", "rapidfuzz", "markdownify"]:
        if not try_import(dep.replace("-", "_")):
            pip_install([dep])
    return check("Marker", "PASS" if ok else "WARN", msg,
                 "Optional — disabled by default" if not ok else "")

MODULES.append({"key": "marker", "cat": "Parsers", "label": "Marker",
                "check": _check_marker, "install": _install_marker})

# ──────────────────────────────────────────────
# Category: LLM
# ──────────────────────────────────────────────

def _check_llm_key():
    keys = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        keys.append("ANTHROPIC_API_KEY")
    if os.environ.get("DEEPSEEK_API_KEY"):
        keys.append("DEEPSEEK_API_KEY")
    if os.environ.get("SCIENTRA_API_KEY"):
        keys.append("SCIENTRA_API_KEY")
    if keys:
        return check("LLM API keys", "PASS", f"Found: {', '.join(keys)}")
    return check("LLM API keys", "INFO",
                 "No API keys in environment — Chat uses prompt-file mode",
                 "Set ANTHROPIC_API_KEY or DEEPSEEK_API_KEY\n"
                 "Or run: python Scripts/setup_llm.py")

MODULES.append({"key": "llm_key", "cat": "LLM", "label": "LLM API keys",
                "check": _check_llm_key, "install": None})

def _check_llm_config():
    cfg = PROJECT_ROOT / "Config" / "llm_config.yaml"
    if cfg.exists():
        return check("LLM config", "PASS", "Config/llm_config.yaml present")
    return check("LLM config", "INFO", "Not configured (Chat feature)",
                 "Run: python Scripts/setup_llm.py")

MODULES.append({"key": "llm_cfg", "cat": "LLM", "label": "LLM config",
                "check": _check_llm_config, "install": None})

# ──────────────────────────────────────────────
# Category: Data & Embeddings
# ──────────────────────────────────────────────

def _check_bge():
    if not try_import("sentence_transformers"):
        return check("BGE-M3 embedding", "WARN", "sentence-transformers not installed",
                     "pip install sentence-transformers\n"
                     "First embedding run downloads BAAI/bge-m3 (~2GB, one-time)")
    return check("BGE-M3 embedding", "PASS", "sentence-transformers ready")

MODULES.append({"key": "bge", "cat": "Data", "label": "BGE-M3 embeddings",
                "check": _check_bge, "install": None})

def _check_lancedb():
    if not try_import("lancedb"):
        return check("LanceDB", "WARN", "lancedb not installed",
                     "pip install lancedb pyarrow")
    try:
        import lancedb
        db_dir = PROJECT_ROOT / "06_Index" / "vector" / "lancedb"
        if db_dir.exists() and any(db_dir.iterdir()):
            db = lancedb.connect(str(db_dir))
            try:
                tables = db.table_names()
            except AttributeError:
                tables = db.list_tables()
            if tables:
                return check("LanceDB", "PASS", f"{len(tables)} table(s) at 06_Index/vector/lancedb")
            return check("LanceDB", "INFO", "Connected but no tables yet",
                         "Run: python Scripts/build_embeddings.py")
        return check("LanceDB", "INFO", "Package ready — generate embeddings to create tables")
    except Exception as e:
        return check("LanceDB", "WARN", str(e)[:100])

MODULES.append({"key": "lancedb", "cat": "Data", "label": "LanceDB vector store",
                "check": _check_lancedb, "install": None})

def _check_pdf_count():
    inbox = list((PROJECT_ROOT / "00_Inbox").glob("**/*.pdf"))
    sources = list((PROJECT_ROOT / "01_Sources").glob("**/*.pdf"))
    total = len(inbox) + len(sources)
    if total:
        return check("PDFs found", "PASS", f"{total} ({len(inbox)} inbox, {len(sources)} sources)")
    return check("PDFs found", "INFO", "No PDFs — add to 00_Inbox/ or import to begin")

MODULES.append({"key": "pdfs", "cat": "Data", "label": "PDFs in project",
                "check": _check_pdf_count, "install": None})

# ──────────────────────────────────────────────
# Category: API
# ──────────────────────────────────────────────

def _check_api_endpoint():
    if http_ok(f"http://localhost:{API_PORT}/health", timeout=3):
        return check("API server", "PASS", f"Running on :{API_PORT}")
    return check("API server", "INFO", "Not running",
                 "Run: python Scripts/run_api_server.py")

MODULES.append({"key": "api", "cat": "API", "label": "API server",
                "check": _check_api_endpoint, "install": None})

# ──────────────────────────────────────────────
# Category: Hybrid Parser Status
# ──────────────────────────────────────────────

def _check_hybrid_config():
    try:
        from scientra.parsers.availability import check_parser_availability
        avail = check_parser_availability(PROJECT_ROOT)
        d = avail.to_dict()
        ready = [k.replace("_available", "").title() for k, v in d.items()
                 if v and k != "hybrid_parser_enabled"]
        enabled = d.get("hybrid_parser_enabled", False)
        status = "PASS" if ready and enabled else ("INFO" if ready else "WARN")
        msg = f"Parsers: {', '.join(ready) or 'none'} | Hybrid mode: {'ON' if enabled else 'OFF'}"
        if not enabled and ready:
            return check("Hybrid parser", status, msg,
                         "Set hybrid_parser.enabled: true in Config/workflow_config.yaml")
        return check("Hybrid parser", status, msg)
    except Exception as e:
        return check("Hybrid parser", "WARN", str(e)[:100])

MODULES.append({"key": "hybrid", "cat": "API", "label": "Hybrid parser",
                "check": _check_hybrid_config, "install": None})


# ── Orchestration ──

def _match_filter(m: dict, filters: list[str] | None) -> bool:
    """Check if a module matches the filter list (case-insensitive)."""
    if not filters:
        return True
    key_lower = m["key"].lower()
    cat_lower = m["cat"].lower()
    label_lower = m["label"].lower()
    for f in filters:
        f_lower = f.lower().strip()
        if f_lower in (key_lower, cat_lower, label_lower):
            return True
        # Allow partial matches
        if f_lower in key_lower or f_lower in cat_lower or f_lower in label_lower:
            return True
    return False


def run_all_checks(filters: list[str] | None = None) -> dict[str, Any]:
    """Run all module checks. Returns {status, checks_by_category, overall_status}."""
    cats: dict[str, list[dict]] = {}
    for m in MODULES:
        if not _match_filter(m, filters):
            continue
        cat = m["cat"]
        if cat not in cats:
            cats[cat] = []
        result = m["check"]()
        cats[cat].append(result)

    all_results = [r for items in cats.values() for r in items]
    has_fail = any(r["status"] == "FAIL" for r in all_results)
    has_warn = any(r["status"] == "WARN" for r in all_results)
    return {
        "overall_status": "FAIL" if has_fail else ("WARN" if has_warn else "READY"),
        "categories": cats,
        "total_checks": len(all_results),
        "pass_count": sum(1 for r in all_results if r["status"] == "PASS"),
        "warn_count": sum(1 for r in all_results if r["status"] == "WARN"),
        "fail_count": sum(1 for r in all_results if r["status"] == "FAIL"),
    }


def run_all_installs(filters: list[str] | None = None, yes: bool = False) -> dict[str, Any]:
    """Run install for all modules that have an installer and aren't PASS."""
    results: dict[str, list[dict]] = {}
    for m in MODULES:
        if not _match_filter(m, filters):
            continue
        cat = m["cat"]
        if cat not in results:
            results[cat] = []

        current = m["check"]()
        if current["status"] == "PASS" or m.get("install") is None:
            results[cat].append(current)
            continue

        if not yes:
            answer = input(f"  Install {m['label']}? [{current['detail']}] [Y/n]: ").strip().lower()
            if answer and answer not in ("y", "yes"):
                results[cat].append(current)
                continue

        installed = m["install"]()
        results[cat].append(installed)

    all_results = [r for items in results.values() for r in items]
    has_fail = any(r["status"] == "FAIL" for r in all_results)
    has_warn = any(r["status"] == "WARN" for r in all_results)
    return {
        "overall_status": "FAIL" if has_fail else ("WARN" if has_warn else "READY"),
        "categories": results,
        "total_checks": len(all_results),
        "pass_count": sum(1 for r in all_results if r["status"] == "PASS"),
        "warn_count": sum(1 for r in all_results if r["status"] == "WARN"),
        "fail_count": sum(1 for r in all_results if r["status"] == "FAIL"),
    }


def print_report(report: dict[str, Any]) -> None:
    """Print a formatted report."""
    print()
    print("  ================================================")
    print("    Scientra Copilot — System Setup & Diagnostics")
    print("  ================================================")
    print()

    for cat, items in report["categories"].items():
        print(f"  [{cat}]")
        for r in items:
            icon = ICONS.get(r["status"], " ? ")
            print(f"    [{icon}] {r['name']}")
            print(f"         {r['detail']}")
            if r.get("fix"):
                for line in r["fix"].split("\n"):
                    print(f"         -> {line}")
        print()

    # Summary
    print(f"  Results: {report['pass_count']} OK, {report['warn_count']} warnings, {report['fail_count']} failures")
    print(f"  Overall: {report['overall_status']}")
    print()
    if report["overall_status"] == "READY":
        print("  All checks passed. System is ready.")
        print("  Run: python workflow.py --all")
    elif report["fail_count"] == 0:
        print("  Warnings found but system is usable.")
        print("  Review items marked [WARN] above.")
    else:
        print("  Failures detected. Fix items marked [FAIL] above.")
        print("  Run with --install to auto-install missing components.")
    print()


# ── CLI ──

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scientra Copilot — Master One-Click Setup & Diagnostics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Scripts/setup.py                     Full check (interactive)
  python Scripts/setup.py --check             Check only
  python Scripts/setup.py --install           Auto-install everything
  python Scripts/setup.py --install --yes     Skip all prompts
  python Scripts/setup.py --filter parsers    Only parser-related checks
  python Scripts/setup.py --json              Machine-readable output
        """,
    )
    p.add_argument("--check", action="store_true", help="Check only (no install)")
    p.add_argument("--install", action="store_true", help="Auto-install missing components")
    p.add_argument("--yes", "-y", action="store_true", help="Skip all prompts (with --install)")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p.add_argument("--filter", "-f", type=str, help="Only run checks for category or key (e.g. 'parsers', 'grobid')")
    return p


def main() -> int:
    args = build_parser().parse_args()
    filters = [f.strip().lower() for f in args.filter.split(",")] if args.filter else None

    if args.json:
        report = run_all_checks(filters=filters)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.install:
        report = run_all_installs(filters=filters, yes=args.yes)
        print_report(report)
        return 0 if report["fail_count"] == 0 else 1

    # Default: check only
    report = run_all_checks(filters=filters)
    print_report(report)
    print("  Run with --install to auto-install missing components.")
    print("  Run with --filter <category> to focus on a subsystem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
