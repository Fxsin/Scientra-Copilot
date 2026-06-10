#!/usr/bin/env python3
"""
Scientra Copilot — Real Data Verification Script

Checks that the API returns real literature data, not demo/empty data.
Run after starting the API server:

    python Scripts/verify_real_data.py
    python Scripts/verify_real_data.py --api-url http://localhost:8720
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_API_URL = "http://127.0.0.1:8710"


def check(label: str, ok: bool, detail: str = "") -> str:
    icon = "PASS" if ok else "FAIL"
    return f"[{icon}] {label}{' — ' + detail if detail else ''}"


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Verify Scientra Copilot real data")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"API base URL (default: {DEFAULT_API_URL})")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    all_ok = True
    paper_count = 0

    print("=" * 50)
    print("  REAL DATA CHECK")
    print("=" * 50)

    # 1. /health
    try:
        with urllib.request.urlopen(f"{api_url}/health", timeout=5) as resp:
            health = json.loads(resp.read())
        lancedb_ok = health.get("lancedb_status") == "ok"
        counts = health.get("table_counts", {})
        total_vecs = sum(counts.values())
        print(check("API /health", lancedb_ok,
                    f"lancedb={health.get('lancedb_status')}, vectors={total_vecs}"))
        if not lancedb_ok:
            all_ok = False
    except Exception as exc:
        print(check("API /health", False, f"{type(exc).__name__}: {exc}"))
        all_ok = False

    # 2. /stats
    try:
        with urllib.request.urlopen(f"{api_url}/stats", timeout=5) as resp:
            stats = json.loads(resp.read())
        paper_count = stats.get("paper_count", 0)
        has_papers = paper_count > 0
        print(check("API /stats", has_papers, f"{paper_count} papers"))
        if not has_papers:
            print("  → No papers found. Run `python workflow.py run` first.")
            all_ok = False
    except Exception as exc:
        print(check("API /stats", False, f"{type(exc).__name__}: {exc}"))
        all_ok = False

    # 3. /query
    try:
        body = json.dumps({"query": "Vip3A", "top_k": 5, "mode": "keyword", "level": "all"}).encode()
        req = urllib.request.Request(f"{api_url}/query", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        total = result.get("total", 0)
        has_results = total > 0
        print(check("API /query", has_results, f"{total} results for 'Vip3A'"))
        if not has_results:
            all_ok = False
    except Exception as exc:
        print(check("API /query", False, f"{type(exc).__name__}: {exc}"))
        all_ok = False

    # 4. CORS check
    try:
        req = urllib.request.Request(f"{api_url}/stats",
                                     headers={"Origin": "http://localhost:3000"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            acao = resp.headers.get("Access-Control-Allow-Origin", "")
        print(check("CORS", bool(acao),
                    f"Access-Control-Allow-Origin: {acao}" if acao else "CORS header missing — browser requests will fail!"))
        if not acao:
            all_ok = False
    except Exception as exc:
        print(check("CORS", False, f"{type(exc).__name__}: {exc}"))
        all_ok = False

    # 5. Web reachability
    from urllib.request import urlopen
    web_url = "http://localhost:3000"
    try:
        with urlopen(web_url, timeout=3) as resp:
            pass
        print(check("Web", True, f"{web_url} reachable"))
    except Exception:
        print(check("Web", False, f"{web_url} not reachable — start with: python Scripts/start_all.py"))

    # 5. Frontend API URL check
    frontend_api = DEFAULT_API_URL
    try:
        env_path = Path(__file__).resolve().parents[1] / "web" / ".env.local"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("NEXT_PUBLIC_SCIENTRA_API_URL="):
                    frontend_api = line.split("=", 1)[1].strip()
        print(check("Frontend API URL", frontend_api == api_url or not env_path.exists(),
                    f"{frontend_api}"))
    except Exception:
        pass

    print("=" * 50)
    if all_ok and paper_count > 0:
        print(f"RESULT: All checks passed — {paper_count} real papers available.")
        return 0
    elif paper_count == 0:
        print("RESULT: API is running but no papers found. Run the workflow first.")
        return 1
    else:
        print("RESULT: Some checks failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
