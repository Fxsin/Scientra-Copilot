"""Environment checks for P6.6.1.

Each check returns: {name, status: PASS|WARN|FAIL|INFO, detail, fix}
Never crashes — missing tools produce WARN or FAIL with fix suggestions.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any


def _resolve_root() -> Path:
    """Resolve project root."""
    candidate = Path(__file__).resolve().parent.parent.parent
    if (candidate / "Config" / "workflow_config.yaml").exists():
        return candidate
    return candidate


def mask_key(key: str) -> str:
    """Mask an API key for safe display: sk-first6...last4."""
    if not key or len(key) < 12:
        return "***" if key else "(empty)"
    return f"{key[:6]}...{key[-4:]}"


def check_python_version() -> dict[str, Any]:
    """Check Python >= 3.11."""
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 11
    return {
        "name": "Python",
        "status": "PASS" if ok else "FAIL",
        "detail": f"{v.major}.{v.minor}.{v.micro}",
        "fix": "" if ok else "Install Python 3.11+ from https://python.org",
    }


def check_node() -> dict[str, Any]:
    """Check Node.js and npm availability."""
    node_ver = None
    npm_ver = None

    # Node
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        node_ver = r.stdout.strip()
    except Exception:
        pass

    # npm
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    try:
        r = subprocess.run([npm, "--version"], capture_output=True, text=True, timeout=5)
        npm_ver = r.stdout.strip()
    except Exception:
        pass

    if node_ver and npm_ver:
        return {"name": "Node.js", "status": "PASS", "detail": f"Node {node_ver}, npm {npm_ver}", "fix": ""}
    elif node_ver:
        return {"name": "Node.js", "status": "WARN", "detail": f"Node {node_ver}, npm missing", "fix": "Install npm: https://nodejs.org"}
    else:
        return {"name": "Node.js", "status": "WARN", "detail": "Node.js not found", "fix": "Install Node.js 18+ from https://nodejs.org (needed for web frontend)"}


def check_git() -> dict[str, Any]:
    """Check Git availability."""
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        ver = r.stdout.strip()
        return {"name": "Git", "status": "PASS", "detail": ver, "fix": ""}
    except Exception:
        return {"name": "Git", "status": "WARN", "detail": "Git not found", "fix": "Install Git from https://git-scm.com"}


def check_disk_space(root: Path | None = None, min_gb: int = 10) -> dict[str, Any]:
    """Check available disk space."""
    if root is None:
        root = _resolve_root()
    try:
        usage = shutil.disk_usage(root)
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        if free_gb >= min_gb:
            return {"name": "Disk Space", "status": "PASS", "detail": f"{free_gb:.1f} GB free / {total_gb:.1f} GB total", "fix": ""}
        else:
            return {"name": "Disk Space", "status": "WARN", "detail": f"Only {free_gb:.1f} GB free (recommend ≥{min_gb} GB)", "fix": f"Free up disk space. Recommend at least {min_gb} GB for data and models."}
    except Exception as exc:
        return {"name": "Disk Space", "status": "WARN", "detail": f"Cannot check: {exc}", "fix": ""}


def check_ram(min_gb: int = 8) -> dict[str, Any]:
    """Check total system RAM."""
    try:
        import psutil
        total_gb = psutil.virtual_memory().total / (1024 ** 3)
        if total_gb >= 16:
            return {"name": "RAM", "status": "PASS", "detail": f"{total_gb:.1f} GB", "fix": ""}
        elif total_gb >= min_gb:
            return {"name": "RAM", "status": "WARN", "detail": f"{total_gb:.1f} GB (recommend ≥16 GB)", "fix": "More RAM recommended for large dataset processing."}
        else:
            return {"name": "RAM", "status": "FAIL", "detail": f"{total_gb:.1f} GB (minimum {min_gb} GB)", "fix": f"At least {min_gb} GB RAM required."}
    except ImportError:
        return {"name": "RAM", "status": "INFO", "detail": "psutil not available — cannot check", "fix": "Install psutil: pip install psutil"}
    except Exception as exc:
        return {"name": "RAM", "status": "WARN", "detail": f"Check failed: {exc}", "fix": ""}


def check_cpu() -> dict[str, Any]:
    """Check CPU core count."""
    try:
        cores = os.cpu_count() or 1
        if cores >= 4:
            return {"name": "CPU", "status": "PASS", "detail": f"{cores} logical cores", "fix": ""}
        else:
            return {"name": "CPU", "status": "WARN", "detail": f"Only {cores} logical cores", "fix": "Performance may be limited with fewer cores."}
    except Exception:
        return {"name": "CPU", "status": "INFO", "detail": "Cannot detect", "fix": ""}


def check_gpu() -> dict[str, Any]:
    """Check GPU / CUDA availability."""
    # Check torch.cuda
    try:
        import torch
        if torch.cuda.is_available():
            count = torch.cuda.device_count()
            name = torch.cuda.get_device_name(0) if count > 0 else "unknown"
            return {"name": "GPU", "status": "PASS", "detail": f"CUDA available: {name} (x{count})", "fix": ""}
        else:
            return {"name": "GPU", "status": "WARN", "detail": "torch.cuda not available", "fix": "GPU not required. CPU-only mode works for all features."}
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: check nvidia-smi
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                          capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return {"name": "GPU", "status": "PASS", "detail": r.stdout.strip().split("\n")[0], "fix": ""}
    except Exception:
        pass

    return {"name": "GPU", "status": "WARN", "detail": "No GPU detected", "fix": "GPU not required. CPU-only mode works for all features."}


def check_dependencies() -> dict[str, Any]:
    """Check critical Python package dependencies."""
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "lancedb": "lancedb",
        "sentence_transformers": "sentence-transformers",
        "pydantic": "pydantic",
        "numpy": "numpy",
        "pandas": "pandas",
        "yaml": "pyyaml",
    }
    installed: dict[str, str] = {}
    missing: list[str] = []

    for import_name, pkg_name in required.items():
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", "installed")
            installed[pkg_name] = str(ver)
        except ImportError:
            missing.append(pkg_name)

    if not missing:
        return {"name": "Dependencies", "status": "PASS", "detail": f"All {len(installed)} packages installed", "fix": ""}
    else:
        return {
            "name": "Dependencies",
            "status": "FAIL" if len(missing) > 2 else "WARN",
            "detail": f"Missing: {', '.join(missing)}. Installed: {len(installed)}",
            "fix": f"Run: pip install {' '.join(missing)}",
        }


def check_lancedb(root: Path | None = None) -> dict[str, Any]:
    """Check LanceDB database health."""
    if root is None:
        root = _resolve_root()

    try:
        import lancedb
    except ImportError:
        return {"name": "LanceDB", "status": "WARN", "detail": "lancedb package not installed", "fix": "pip install lancedb"}

    # Find LanceDB directory (check new layout first, then legacy)
    db_dirs = [
        root / "06_Index" / "vector" / "lancedb",
        root / "06_Index/vector/lancedb/lancedb",
        root / "04_VectorDB" / "lancedb",
    ]
    db_dir = None
    for d in db_dirs:
        if d.exists() and any(d.iterdir()):
            db_dir = d
            break

    if db_dir is None:
        return {"name": "LanceDB", "status": "WARN", "detail": "No LanceDB data yet — created on first import", "fix": "Import papers first: python Scripts/run_workflow.py"}

    try:
        db = lancedb.connect(str(db_dir))
        if hasattr(db, "list_tables"):
            names = [t.name for t in db.list_tables()]
        else:
            names = list(db.table_names())

        if not names:
            return {"name": "LanceDB", "status": "WARN", "detail": "Database exists but has no tables", "fix": "Run workflow to create tables."}

        counts: dict[str, int] = {}
        for t in names:
            try:
                counts[t] = len(db.open_table(t).to_arrow())
            except Exception:
                counts[t] = -1

        total = sum(v for v in counts.values() if v > 0)
        corrupted = [t for t, c in counts.items() if c < 0]
        if corrupted:
            return {"name": "LanceDB", "status": "WARN", "detail": f"{len(names)} tables, {total} records, {len(corrupted)} corrupted", "fix": "Rebuild corrupted tables."}
        return {"name": "LanceDB", "status": "PASS", "detail": f"{len(names)} table(s), {total} records", "fix": ""}
    except Exception as exc:
        return {"name": "LanceDB", "status": "FAIL", "detail": f"Error: {type(exc).__name__}: {exc}", "fix": "Check LanceDB directory integrity."}


def check_bge_m3() -> dict[str, Any]:
    """Check BGE-M3 embedding model availability."""
    try:
        from sentence_transformers import SentenceTransformer
        # Check if model is cached locally
        import os as _os
        cache_dir = _os.path.join(str(Path.home()), ".cache", "torch", "sentence_transformers", "BAAI_bge-m3")
        if Path(cache_dir).exists():
            return {"name": "BGE-M3 Model", "status": "PASS", "detail": "Model cached locally", "fix": ""}
        # Try loading (will download on first use)
        try:
            model = SentenceTransformer("BAAI/bge-m3")
            del model
            return {"name": "BGE-M3 Model", "status": "PASS", "detail": "Model loadable", "fix": ""}
        except Exception:
            return {"name": "BGE-M3 Model", "status": "WARN", "detail": "Not yet downloaded (downloaded on first use, ~2.2 GB)", "fix": "Run workflow to auto-download BGE-M3."}
    except ImportError:
        return {"name": "BGE-M3 Model", "status": "WARN", "detail": "sentence-transformers not installed", "fix": "pip install sentence-transformers"}
    except Exception as exc:
        return {"name": "BGE-M3 Model", "status": "WARN", "detail": f"Check failed: {exc}", "fix": ""}


def check_api_keys(root: Path | None = None) -> dict[str, Any]:
    """Check API key configuration from llm_config.yaml.

    Masks keys: sk-first6...last4.
    """
    if root is None:
        root = _resolve_root()

    config_path = root / "Config" / "llm_config.yaml"
    if not config_path.exists():
        return {"name": "API Keys", "status": "WARN", "detail": "llm_config.yaml not found", "fix": "Create Config/llm_config.yaml from template."}

    try:
        import yaml
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {"name": "API Keys", "status": "FAIL", "detail": f"Cannot parse config: {exc}", "fix": "Check Config/llm_config.yaml format."}

    provider = config.get("provider", "unknown")
    api_key = config.get("api_key", "") or ""
    model = config.get("model", "unknown")
    enabled = config.get("enabled", False)

    if not enabled:
        return {"name": "API Keys", "status": "WARN", "detail": f"Provider '{provider}' disabled in config", "fix": "Enable in Settings → AI Provider."}

    if not api_key:
        return {"name": "API Keys", "status": "FAIL", "detail": f"Provider '{provider}' has no API key", "fix": f"Set API key in Config/llm_config.yaml or Settings → AI Provider."}

    # Validate key format
    if provider == "deepseek" and not api_key.startswith("sk-"):
        return {"name": "API Keys", "status": "FAIL", "detail": f"DeepSeek key format invalid: {mask_key(api_key)}", "fix": "DeepSeek API keys should start with 'sk-'."}
    if provider == "openai" and not api_key.startswith("sk-"):
        return {"name": "API Keys", "status": "WARN", "detail": f"OpenAI key format unusual: {mask_key(api_key)}", "fix": "Check your OpenAI API key."}
    if provider == "anthropic" and not api_key.startswith("sk-ant-"):
        return {"name": "API Keys", "status": "WARN", "detail": f"Anthropic key format unusual: {mask_key(api_key)}", "fix": "Check your Anthropic API key."}

    return {"name": "API Keys", "status": "PASS", "detail": f"{provider} ({model}): {mask_key(api_key)}", "fix": ""}


def check_port(port: int) -> tuple[bool, str | None]:
    """Check if a port is in use. Returns (in_use, process_info)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                # Port is in use — try to identify the process
                if sys.platform == "win32":
                    try:
                        r = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=5)
                        for line in r.stdout.splitlines():
                            if f":{port}" in line and "LISTENING" in line:
                                pid = line.strip().split()[-1]
                                try:
                                    t = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                                      capture_output=True, text=True, timeout=5)
                                    proc = t.stdout.strip().split(",")[0].strip('"') if t.stdout else "unknown"
                                    return True, f"{proc} (PID {pid})"
                                except Exception:
                                    return True, f"PID {pid}"
                    except Exception:
                        pass
                return True, None
    except Exception:
        pass
    return False, None


def check_ports() -> dict[str, Any]:
    """Check key ports (8000 for API, 3000 for web)."""
    ports_to_check = [8000, 3000, 8710]
    statuses: list[str] = []
    all_free = True

    for port in ports_to_check:
        in_use, proc = check_port(port)
        if in_use:
            detail = f"Port {port}: occupied by {proc or 'unknown'}"
            statuses.append(detail)
            all_free = False

    if all_free:
        return {"name": "Ports", "status": "PASS", "detail": "8000, 3000, 8710 all available", "fix": ""}
    else:
        return {"name": "Ports", "status": "WARN", "detail": "; ".join(statuses), "fix": "Close programs using these ports, or configure different ports."}


def run_all_checks(root: Path | None = None) -> list[dict[str, Any]]:
    """Run all environment checks. Returns list of check result dicts."""
    if root is None:
        root = _resolve_root()

    checks = [
        check_python_version(),
        check_node(),
        check_git(),
        check_disk_space(root),
        check_ram(),
        check_cpu(),
        check_gpu(),
        check_dependencies(),
        check_lancedb(root),
        check_bge_m3(),
        check_api_keys(root),
        check_ports(),
    ]
    return checks
