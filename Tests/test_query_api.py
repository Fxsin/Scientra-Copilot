from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "06_API"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(API_DIR))

REPORT_PATH = PROJECT_ROOT / "05_Index" / "query_api_test_report.md"
TC_PAPER_ID = "paper_2247e647bb604df2"


def get_client():
    from fastapi.testclient import TestClient

    from scientra.server import create_app

    return TestClient(create_app(PROJECT_ROOT))


def run_endpoint_checks() -> dict[str, Any]:
    client = get_client()
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str, payload: dict[str, Any] | None = None) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail, "payload": payload or {}})

    health = client.get("/health")
    health_payload = health.json()
    record(
        "/health",
        health.status_code == 200 and health_payload.get("lancedb_status") == "ok",
        f"status={health.status_code}, lancedb_status={health_payload.get('lancedb_status')}",
        health_payload,
    )

    stats = client.get("/stats")
    stats_payload = stats.json()
    record(
        "/stats",
        stats.status_code == 200 and int(stats_payload.get("paper_count") or 0) >= 30,
        f"status={stats.status_code}, paper_count={stats_payload.get('paper_count')}",
        stats_payload,
    )

    query_cases = [
        (
            "hybrid query",
            {
                "query": "Visgun receptor Tc toxin Drosophila cells",
                "mode": "hybrid",
                "top_k": 10,
                "level": "all",
            },
        ),
        (
            "vector query",
            {
                "query": "Vip3Aa binding Spodoptera frugiperda midgut BBMV",
                "mode": "vector",
                "top_k": 10,
                "level": "all",
            },
        ),
        (
            "keyword query",
            {
                "query": "CRISPR Cas9 abdominal-A knockout fall armyworm",
                "mode": "keyword",
                "top_k": 10,
                "level": "all",
            },
        ),
        (
            "tag filter",
            {
                "query": "binding midgut",
                "mode": "hybrid",
                "top_k": 10,
                "level": "all",
                "toxin": "Vip3",
            },
        ),
        (
            "candidate excluded by default",
            {
                "query": "",
                "mode": "keyword",
                "top_k": 10,
                "level": "all",
                "mechanism": "Microbiota",
            },
        ),
        (
            "candidate included weak recall",
            {
                "query": "",
                "mode": "keyword",
                "top_k": 10,
                "level": "all",
                "mechanism": "Microbiota",
                "include_candidate_tags": True,
            },
        ),
    ]

    for name, payload in query_cases:
        response = client.post("/query", json=payload)
        data = response.json()
        results = data.get("results") or []
        if name == "candidate excluded by default":
            passed = response.status_code == 200 and len(results) == 0
        elif name == "candidate included weak recall":
            passed = response.status_code == 200 and len(results) > 0
        elif name == "tag filter":
            passed = response.status_code == 200 and all(
                "Vip3" in item.get("assigned_tags", {}).get("TOXIN", [])
                for item in results
            )
        else:
            passed = response.status_code == 200 and len(results) > 0
        record(name, passed, f"status={response.status_code}, results={len(results)}", data)

    summary = client.get(f"/paper/{TC_PAPER_ID}/summary")
    summary_payload = summary.json()
    record(
        "/paper/{paper_id}/summary",
        summary.status_code == 200 and bool(summary_payload.get("citation_anchors")),
        f"status={summary.status_code}, anchors={len(summary_payload.get('citation_anchors') or [])}",
        summary_payload,
    )

    metadata = client.get(f"/paper/{TC_PAPER_ID}/metadata")
    metadata_payload = metadata.json()
    metadata_json = json.dumps(metadata_payload, ensure_ascii=False)
    record(
        "/paper/{paper_id}/metadata",
        metadata.status_code == 200
        and bool(metadata_payload.get("metadata", {}).get("title"))
        and "01_PDF" not in metadata_json
        and "raw_text" not in metadata_json,
        f"status={metadata.status_code}, title={metadata_payload.get('metadata', {}).get('title')}",
        metadata_payload,
    )

    tags = client.get(f"/paper/{TC_PAPER_ID}/tags")
    tags_payload = tags.json()
    record(
        "/paper/{paper_id}/tags",
        tags.status_code == 200 and bool(tags_payload.get("assigned_tags")),
        f"status={tags.status_code}, assigned_categories={len(tags_payload.get('assigned_tags') or {})}",
        tags_payload,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
        "health": health_payload,
        "stats": stats_payload,
    }


def write_report(payload: dict[str, Any], path: Path = REPORT_PATH) -> None:
    lines = [
        "# Query API Test Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        "- api_scope: read-only",
        "- api_developed: true",
        "- pdf_access: forbidden",
        "- raw_text_full_return: forbidden",
        "- lancedb_direct_agent_access: forbidden",
        "",
        "## API Startup Status",
        "",
        f"- health_status: {payload['health'].get('api_status')}",
        f"- lancedb_status: {payload['health'].get('lancedb_status')}",
        f"- embedding_model: {payload['health'].get('embedding_model')}",
        "",
        "## Table Count",
        "",
    ]
    for table, count in (payload["health"].get("table_counts") or {}).items():
        lines.append(f"- {table}: {count}")
    lines.extend(["", "## Endpoint Test Results", "", "| Test | Status | Detail |", "|---|---:|---|"])
    for check in payload["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"| {check['name']} | {status} | {check['detail']} |")

    lines.extend(["", "## Query Test Results", ""])
    for check in payload["checks"]:
        if "query" not in check["name"] and "filter" not in check["name"] and "candidate" not in check["name"]:
            continue
        results = check["payload"].get("results") or []
        top = results[0] if results else {}
        lines.append(f"### {check['name']}")
        lines.append(f"- status: {'PASS' if check['passed'] else 'FAIL'}")
        lines.append(f"- result_count: {len(results)}")
        if top:
            lines.append(f"- top_paper_id: {top.get('paper_id')}")
            lines.append(f"- top_level: {top.get('level')}")
            lines.append(f"- top_score: {top.get('score')}")
            lines.append(f"- top_matched_tags: {', '.join(top.get('matched_tags') or [])}")
        lines.append("")

    stats = payload["stats"]
    lines.extend(
        [
            "## Tag Filter Test Results",
            "",
            "- assigned_tags_default_filter: PASS" if any(c["name"] == "tag filter" and c["passed"] for c in payload["checks"]) else "- assigned_tags_default_filter: FAIL",
            "- candidate_tags_default_excluded: PASS" if any(c["name"] == "candidate excluded by default" and c["passed"] for c in payload["checks"]) else "- candidate_tags_default_excluded: FAIL",
            "- candidate_tags_include_true_extends_recall: PASS" if any(c["name"] == "candidate included weak recall" and c["passed"] for c in payload["checks"]) else "- candidate_tags_include_true_extends_recall: FAIL",
            "",
            "## Stats Snapshot",
            "",
            f"- paper_count: {stats.get('paper_count')}",
            f"- metadata_embedding_count: {stats.get('metadata_embedding_count')}",
            f"- summary_embedding_count: {stats.get('summary_embedding_count')}",
            f"- chunk_embedding_count: {stats.get('chunk_embedding_count')}",
            "",
            "## Recommendation",
            "",
        ]
    )
    if payload["failed"] == 0:
        lines.append("Recommendation: enter P8 Agent SDK.")
    else:
        lines.append("Recommendation: fix failing Query API checks before P8 Agent SDK.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_query_api_contract() -> None:
    payload = run_endpoint_checks()
    write_report(payload)
    failed = [check for check in payload["checks"] if not check["passed"]]
    assert not failed, failed


if __name__ == "__main__":
    result = run_endpoint_checks()
    write_report(result)
    print(json.dumps({"report_path": str(REPORT_PATH), "passed": result["passed"], "failed": result["failed"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["failed"] == 0 else 1)
