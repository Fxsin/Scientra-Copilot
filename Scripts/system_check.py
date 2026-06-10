from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def run_system_check(root: str | Path = PROJECT_ROOT, load_bge: bool = True, summary_mode: str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    if summary_mode is None:
        summary_mode = _detect_summary_mode(root)
    checks = [
        check_python_version(),
        check_docker(),
        check_grobid(),
        check_summary_api_key(summary_mode),
        check_bge_m3(load_bge=load_bge),
        check_lancedb(root),
        check_query_api(root),
        check_agent_sdk(root),
    ]
    status = "PASS"
    if any(check["status"] == "FAIL" for check in checks):
        status = "FAIL"
    elif any(check["status"] == "WARN" for check in checks):
        status = "WARN"
    return {"status": status, "checks": checks, "summary_mode": summary_mode}


def check_python_version() -> dict[str, str]:
    version = sys.version_info
    ok = version.major == 3 and version.minor >= 11
    return result("Python version", "PASS" if ok else "FAIL", f"{version.major}.{version.minor}.{version.micro}")


def check_docker() -> dict[str, str]:
    try:
        completed = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"], text=True, capture_output=True, timeout=10)
        if completed.returncode == 0:
            return result("Docker", "PASS", completed.stdout.strip() or "available")
        return result("Docker", "WARN", "docker command returned non-zero; GROBID may already be running")
    except Exception as exc:
        return result("Docker", "WARN", f"{type(exc).__name__}: {exc}")


def check_grobid() -> dict[str, str]:
    url = "http://localhost:18070/api/isalive"
    try:
        with urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace").strip().lower()
        return result("GROBID", "PASS" if "true" in body else "WARN", url)
    except Exception as exc:
        return result("GROBID", "WARN", f"{url} unavailable: {type(exc).__name__}")


def _detect_summary_mode(root: Path) -> str:
    """Detect summary mode from workflow_config.yaml, defaulting to 'agent'."""
    config_path = root / "Config" / "workflow_config.yaml"
    try:
        import yaml
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return str(config.get("steps", {}).get("summary", {}).get("mode", "agent"))
    except Exception:
        return "agent"


def check_summary_api_key(summary_mode: str = "agent") -> dict[str, str]:
    """Check API key based on summary mode.

    - agent mode:      ANTHROPIC_API_KEY preferred, DEEPSEEK_API_KEY not required
    - direct_api mode: DEEPSEEK_API_KEY required
    """
    if summary_mode == "agent":
        anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        deepseek_key = bool(os.environ.get("DEEPSEEK_API_KEY"))
        if anthropic_key:
            return result("Summary API key (agent mode)", "PASS", "ANTHROPIC_API_KEY present")
        elif deepseek_key:
            return result("Summary API key (agent mode)", "PASS", "DEEPSEEK_API_KEY present (fallback)")
        else:
            return result(
                "Summary API key (agent mode)",
                "PASS",
                "No API key set — summaries will be written as prompt files for Claude Code Agent resolution. "
                "Set ANTHROPIC_API_KEY or DEEPSEEK_API_KEY for automatic generation.",
            )
    else:
        exists = bool(os.environ.get("DEEPSEEK_API_KEY"))
        return result(
            "Summary API key (direct_api mode)",
            "PASS" if exists else "FAIL",
            "present" if exists else "missing; DEEPSEEK_API_KEY required for direct_api mode",
        )


def check_bge_m3(load_bge: bool = True) -> dict[str, str]:
    try:
        from scientra.embedding import BgeM3Embedder

        if load_bge:
            embedder = BgeM3Embedder(model_name="BAAI/bge-m3", device="auto")
            embedder.load()
        return result("BGE-M3", "PASS", "loadable")
    except Exception as exc:
        return result("BGE-M3", "WARN", f"{type(exc).__name__}: {exc}")


def check_lancedb(root: Path) -> dict[str, str]:
    try:
        import lancedb

        lancedb_dir = root / "04_VectorDB" / "lancedb"
        if not lancedb_dir.exists() or not any(lancedb_dir.iterdir()):
            return result("LanceDB", "WARN", "No data yet — tables created on first workflow run")

        db = lancedb.connect(str(lancedb_dir))
        if hasattr(db, "list_tables"):
            payload = db.list_tables()
            names = set(payload.tables if hasattr(payload, "tables") else payload)
        else:
            names = set(db.table_names())
        # Accept both the legacy per-level table names and the unified table name
        expected_legacy = {"metadata_embeddings", "summary_embeddings", "chunk_embeddings"}
        expected_unified = {"literature_vectors"}
        if names & expected_unified:
            # Unified table present — count it
            table_name = (names & expected_unified).pop()
            counts = {table_name: len(db.open_table(table_name).to_arrow())}
            return result("LanceDB", "PASS", json.dumps(counts, ensure_ascii=False))
        missing = expected_legacy - names
        if missing:
            return result("LanceDB", "WARN", f"Tables not yet created: {sorted(missing)}. Run workflow first.")
        counts = {name: len(db.open_table(name).to_arrow()) for name in sorted(expected_legacy)}
        return result("LanceDB", "PASS", json.dumps(counts, ensure_ascii=False))
    except Exception as exc:
        return result("LanceDB", "WARN", f"{type(exc).__name__}: {exc}. Tables created on first workflow run.")


def check_query_api(root: Path) -> dict[str, str]:
    try:
        from scientra.query import LiteratureQueryService
        from scientra.models import LiteratureQueryRequest

        service = LiteratureQueryService(root)
        # Test with a simple keyword search
        req = LiteratureQueryRequest(query="test", query_type="search_by_keyword", top_k=1)
        response = service.query(req)
        return result("Query API", "PASS" if response.total >= 0 else "FAIL", f"total_results={response.total}")
    except Exception as exc:
        return result("Query API", "FAIL", f"{type(exc).__name__}: {exc}")


def check_agent_sdk(root: Path) -> dict[str, str]:
    try:
        from scientra.agent import AgentQueryInterface
        from scientra.sdk import LiteratureAgentSDK

        interface = AgentQueryInterface()
        sdk = LiteratureAgentSDK(interface=interface)
        response = sdk.search("Tc toxin receptor", query_type="search_by_keyword", top_k=1)
        if response.total > 0:
            return result("Agent SDK", "PASS", f"results={response.total}")
        # Empty results may mean no data yet — that's OK for fresh install
        return result("Agent SDK", "WARN", "SDK works but 0 results (no literature processed yet)")
    except Exception as exc:
        return result("Agent SDK", "FAIL", f"{type(exc).__name__}: {exc}")


def result(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Scientra Copilot runtime requirements.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--no-bge-load", action="store_true", help="Skip actual BGE-M3 model loading.")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    payload = run_system_check(args.root, load_bge=not args.no_bge_load)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for check in payload["checks"]:
            print(f"{check['status']}: {check['name']} - {check['detail']}")
        print(f"overall: {payload['status']}")
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
