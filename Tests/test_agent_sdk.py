from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "06_API"
AGENT_DIR = PROJECT_ROOT / "08_Agent_Interface"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(AGENT_DIR))

REPORT_PATH = PROJECT_ROOT / "05_Index" / "agent_sdk_test_report.md"
API_BASE_URL = "http://127.0.0.1:8765"
TC_PAPER_ID = "paper_2247e647bb604df2"


def start_api_server_if_needed() -> tuple[Any | None, threading.Thread | None]:
    if endpoint_is_ready(f"{API_BASE_URL}/health"):
        return None, None

    import uvicorn
    from scientra.server import create_app

    config = uvicorn.Config(create_app(PROJECT_ROOT), host="127.0.0.1", port=8765, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 60
    while time.time() < deadline:
        if endpoint_is_ready(f"{API_BASE_URL}/health"):
            return server, thread
        time.sleep(0.5)
    server.should_exit = True
    raise RuntimeError("API server did not become ready on 127.0.0.1:8765")


def endpoint_is_ready(url: str) -> bool:
    try:
        response = httpx.get(url, timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def run_sdk_checks() -> dict[str, Any]:
    from scientra.sdk import LiteratureAgentSDK

    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str, payload: Any | None = None) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail, "payload": payload})

    local_sdk = LiteratureAgentSDK(mode="local", root=PROJECT_ROOT)
    local_search = local_sdk.search("Visgun receptor Tc toxin Drosophila cells", top_k=5)
    record("Local Mode search", local_search.total > 0, f"results={local_search.total}", local_search.model_dump())

    server, thread = start_api_server_if_needed()
    try:
        api_sdk = LiteratureAgentSDK(mode="api", root=PROJECT_ROOT, api_base_url=API_BASE_URL)
        api_search = api_sdk.search("CRISPR Cas9 abdominal-A knockout fall armyworm", mode="keyword", top_k=5)
        record("API Mode search", api_search.total > 0, f"results={api_search.total}", api_search.model_dump())
    finally:
        if server is not None:
            server.should_exit = True
            if thread is not None:
                thread.join(timeout=10)

    summary = local_sdk.get_summary(TC_PAPER_ID)
    record(
        "get_summary",
        bool(summary.summary) and bool(summary.citation_anchors),
        f"summary_chars={len(summary.summary or '')}, anchors={len(summary.citation_anchors)}",
        summary.model_dump(),
    )

    metadata = local_sdk.get_metadata(TC_PAPER_ID)
    metadata_json = json.dumps(metadata.model_dump(), ensure_ascii=False)
    record(
        "get_metadata",
        bool((metadata.metadata or {}).get("title")) and no_internal_path_leak(metadata_json),
        f"title={(metadata.metadata or {}).get('title')}",
        metadata.model_dump(),
    )

    tags = local_sdk.get_tags(TC_PAPER_ID)
    assigned_tags = (tags.tags or {}).get("assigned_tags") or {}
    record(
        "get_tags",
        bool(assigned_tags),
        f"assigned_categories={len(assigned_tags)}",
        tags.model_dump(),
    )

    evidence = local_sdk.get_evidence(
        "Visgun receptor Tc toxin Drosophila cells",
        filters={"toxin": "Tc", "mechanism": "Receptor"},
        top_k=5,
    )
    record(
        "get_evidence",
        bool(evidence.supporting_chunks) and bool(evidence.citation_anchors),
        f"chunks={len(evidence.supporting_chunks)}, confidence={evidence.confidence}",
        evidence.model_dump(),
    )

    context = local_sdk.ask_literature(
        "What evidence links Visgun to Tc toxin receptor function?",
        filters={"toxin": "Tc", "mechanism": "Receptor"},
        max_context_tokens=350,
    )
    context_payload = context.model_dump()
    record(
        "ask_literature",
        bool(context.selected_papers) and (bool(context.selected_summaries) or bool(context.selected_evidence_chunks)),
        f"papers={len(context.selected_papers)}, chunks={len(context.selected_evidence_chunks)}, tokens={context.context_token_estimate}",
        context_payload,
    )

    selected_context_json = json.dumps(
        {
            "selected_papers": context_payload.get("selected_papers"),
            "selected_summaries": context_payload.get("selected_summaries"),
            "selected_evidence_chunks": context_payload.get("selected_evidence_chunks"),
        },
        ensure_ascii=False,
    )
    record(
        "candidate_tags default excluded",
        "candidate_tags" not in selected_context_json,
        f"excluded_candidate_categories={len(context.excluded_candidate_tags)}",
        context_payload.get("excluded_candidate_tags"),
    )

    record(
        "max_context_tokens",
        context.context_token_estimate <= 350,
        f"context_token_estimate={context.context_token_estimate}",
        {"context_token_estimate": context.context_token_estimate},
    )

    full_context_json = json.dumps(context_payload, ensure_ascii=False)
    record(
        "raw_text not leaked",
        no_internal_path_leak(full_context_json),
        "no PDF/source-text/TEI/vector path exposed",
        {"checked_chars": len(full_context_json)},
    )

    record(
        "SDK does not call LLM",
        sdk_code_has_no_llm_call(),
        "no LLM provider imports or API key references in SDK code",
        {},
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
        "context_pack_sample": shrink_context_pack(context_payload),
    }


def no_internal_path_leak(text: str) -> bool:
    blocked = ["01_PDF", "03_Summary", "raw_text", ".tei.xml", "04_VectorDB", "G:\\\\"]
    return not any(item in text for item in blocked)


def sdk_code_has_no_llm_call() -> bool:
    code_paths = [
        AGENT_DIR / "agent_sdk.py",
        AGENT_DIR / "agent_query_interface.py",
        AGENT_DIR / "agent_response_models.py",
    ]
    blocked = ["DEEPSEEK" + "_API_KEY", "deepseek", "openai", "chat.completions", "responses.create"]
    for path in code_paths:
        text = path.read_text(encoding="utf-8", errors="ignore").casefold()
        if any(item.casefold() in text for item in blocked):
            return False
    return True


def shrink_context_pack(context: dict[str, Any]) -> dict[str, Any]:
    sample = dict(context)
    sample["selected_papers"] = sample.get("selected_papers", [])[:2]
    sample["selected_summaries"] = sample.get("selected_summaries", [])[:1]
    sample["selected_evidence_chunks"] = sample.get("selected_evidence_chunks", [])[:2]
    return sample


def write_report(payload: dict[str, Any], path: Path = REPORT_PATH) -> None:
    lines = [
        "# Agent SDK Test Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        "- sdk_scope: read-only",
        "- local_mode: supported",
        "- api_mode: supported",
        "- default_api_base_url: http://localhost:8765",
        "",
        "## Local Mode Test Results",
        "",
    ]
    for check in payload["checks"]:
        if check["name"].startswith("Local") or check["name"] in {
            "get_summary",
            "get_metadata",
            "get_tags",
            "get_evidence",
            "ask_literature",
        }:
            lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'} ({check['detail']})")

    lines.extend(["", "## API Mode Test Results", ""])
    for check in payload["checks"]:
        if check["name"].startswith("API"):
            lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'} ({check['detail']})")

    lines.extend(["", "## Safety Test Results", ""])
    for check in payload["checks"]:
        if check["name"] in {
            "candidate_tags default excluded",
            "max_context_tokens",
            "raw_text not leaked",
            "SDK does not call LLM",
        }:
            lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'} ({check['detail']})")

    context = payload["context_pack_sample"]
    lines.extend(
        [
            "",
            "## Context Pack Example",
            "",
            f"- question: {context.get('question')}",
            f"- retrieval_mode: {context.get('retrieval_mode')}",
            f"- context_token_estimate: {context.get('context_token_estimate')}",
            f"- selected_papers: {len(context.get('selected_papers') or [])}",
            f"- selected_summaries: {len(context.get('selected_summaries') or [])}",
            f"- selected_evidence_chunks: {len(context.get('selected_evidence_chunks') or [])}",
            f"- citation_anchors: {', '.join((context.get('citation_anchors') or [])[:8])}",
            f"- excluded_candidate_tags: {json.dumps(context.get('excluded_candidate_tags') or {}, ensure_ascii=False)}",
            "",
            "```json",
            json.dumps(context, ensure_ascii=False, indent=2)[:5000],
            "```",
            "",
            "## Summary",
            "",
            f"- passed: {payload['passed']}",
            f"- failed: {payload['failed']}",
            "- raw_text leakage check: PASS" if any(c["name"] == "raw_text not leaked" and c["passed"] for c in payload["checks"]) else "- raw_text leakage check: FAIL",
            "- LLM call check: PASS" if any(c["name"] == "SDK does not call LLM" and c["passed"] for c in payload["checks"]) else "- LLM call check: FAIL",
            "",
            "## Recommendation",
            "",
        ]
    )
    if payload["failed"] == 0:
        lines.append("Recommendation: enter P9 Workflow Engine.")
    else:
        lines.append("Recommendation: fix Agent SDK checks before P9 Workflow Engine.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_agent_sdk_contract() -> None:
    payload = run_sdk_checks()
    write_report(payload)
    failed = [check for check in payload["checks"] if not check["passed"]]
    assert not failed, failed


if __name__ == "__main__":
    result = run_sdk_checks()
    write_report(result)
    print(json.dumps({"report_path": str(REPORT_PATH), "passed": result["passed"], "failed": result["failed"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["failed"] == 0 else 1)
