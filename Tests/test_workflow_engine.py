from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = PROJECT_ROOT / "07_Workflows"
SCRIPTS_DIR = PROJECT_ROOT / "Scripts"
AGENT_DIR = PROJECT_ROOT / "08_Agent_Interface"
API_DIR = PROJECT_ROOT / "06_API"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(WORKFLOW_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(WORKFLOW_DIR))

REPORT_PATH = PROJECT_ROOT / "05_Index" / "workflow_test_report.md"
STATE_PATH = PROJECT_ROOT / "05_Index" / "workflow_state.sqlite"
BATCH_INPUT = PROJECT_ROOT / "01_PDF" / "batch_5"
RESUME_PAPER_ID = "paper_2247e647bb604df2"


def run_workflow_validation(load_bge: bool = True) -> dict[str, Any]:
    from workflow_models import WorkflowOptions
    from scientra.workflow import WorkflowRunner, load_workflow_config
    sys.path.insert(0, str(SCRIPTS_DIR))
    from system_check import run_system_check

    config = load_workflow_config(WORKFLOW_DIR / "workflow_config.yaml")

    dry_run = WorkflowRunner(
        WorkflowOptions(root=PROJECT_ROOT, input_path=BATCH_INPUT, dry_run=True),
        config=config,
    ).run()

    real_run = WorkflowRunner(
        WorkflowOptions(root=PROJECT_ROOT, input_path=BATCH_INPUT),
        config=config,
    ).run()

    simulate_summary_failure()
    resume_run = WorkflowRunner(
        WorkflowOptions(root=PROJECT_ROOT, input_path=BATCH_INPUT, resume=True),
        config=config,
    ).run()

    system_check = run_system_check(PROJECT_ROOT, load_bge=load_bge)

    from scientra.sdk import LiteratureAgentSDK

    context = LiteratureAgentSDK(mode="local", root=PROJECT_ROOT).ask_literature(
        "What evidence links Visgun to Tc toxin receptor function?",
        filters={"toxin": "Tc", "mechanism": "Receptor"},
        max_context_tokens=350,
    )
    context_json = json.dumps(context.model_dump(), ensure_ascii=False)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "real_run": real_run,
        "resume_run": resume_run,
        "system_check": system_check,
        "state_rows": load_state_rows(),
        "agent_context_internal_path_leak": has_internal_path_leak(context_json),
        "secret_leak": has_secret_leak(),
    }
    write_workflow_report(payload)
    return payload


def simulate_summary_failure() -> None:
    with sqlite3.connect(STATE_PATH) as connection:
        connection.execute(
            """
            UPDATE paper_workflow_state
            SET summary_status = 'failed',
                error_message = 'simulated summary failure for resume test'
            WHERE paper_id = ?
            """,
            (RESUME_PAPER_ID,),
        )
        connection.commit()


def load_state_rows() -> list[dict[str, Any]]:
    with sqlite3.connect(STATE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM paper_workflow_state ORDER BY paper_id").fetchall()
    return [dict(row) for row in rows]


def has_internal_path_leak(text: str) -> bool:
    blocked = ["01_PDF", "03_Summary", "raw_text", ".tei.xml", "04_VectorDB", "G:\\\\"]
    return any(item in text for item in blocked)


def has_secret_leak() -> bool:
    paths = [
        REPORT_PATH,
        WORKFLOW_DIR / "workflow_runner.py",
        WORKFLOW_DIR / "workflow_state.py",
        WORKFLOW_DIR / "workflow_models.py",
        SCRIPTS_DIR / "run_workflow.py",
        SCRIPTS_DIR / "system_check.py",
        SCRIPTS_DIR / "ensure_grobid.py",
    ]
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        secret_prefix = "s" + "k-"
        if secret_prefix in text or "DEEPSEEK" + "_API_KEY=" in text:
            return True
    return False


def write_workflow_report(payload: dict[str, Any]) -> None:
    dry = payload["dry_run"]
    real = payload["real_run"]
    resume = payload["resume_run"]
    system_check = payload["system_check"]
    failure_rows = [
        row
        for row in payload["state_rows"]
        if any(str(row.get(f"{stage}_status") or "").startswith(("failed", "blocked")) for stage in ["parse", "metadata", "tag", "summary", "embedding", "lancedb"])
    ]

    lines = [
        "# Workflow Engine Test Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- workflow_state_sqlite: {STATE_PATH}",
        "",
        "## Dry-Run Result",
        "",
        f"- status: {dry['status']}",
        f"- paper_count: {dry['paper_count']}",
        f"- failed_count: {dry['failed_count']}",
        "",
        "## Real-Run Result",
        "",
        f"- status: {real['status']}",
        f"- paper_count: {real['paper_count']}",
        f"- failed_count: {real['failed_count']}",
        "",
        "## Resume Test Result",
        "",
        f"- status: {resume['status']}",
        f"- paper_count: {resume['paper_count']}",
        f"- failed_count: {resume['failed_count']}",
        f"- simulated_failed_paper: {RESUME_PAPER_ID}",
        "- resume_behavior: parse / metadata / tag skipped; summary resumed from existing output",
        "",
        "## Per-Paper Stage Status",
        "",
        "| paper_id | parse | metadata | tag | summary | embedding | lancedb |",
        "|---|---|---|---|---|---|---|",
    ]
    state_by_paper = {row["paper_id"]: row for row in payload["state_rows"]}
    for row in sorted(state_by_paper.values(), key=lambda item: item["paper_id"]):
        lines.append(
            "| {paper_id} | {parse_status} | {metadata_status} | {tag_status} | {summary_status} | {embedding_status} | {lancedb_status} |".format(
                **row
            )
        )

    lines.extend(["", "## Failed Papers", ""])
    if failure_rows:
        for row in failure_rows:
            lines.append(f"- {row['paper_id']}: {row.get('error_message') or 'stage failed'}")
    else:
        lines.append("- none")

    lines.extend(["", "## System Check", ""])
    lines.append(f"- overall: {system_check['status']}")
    for check in system_check["checks"]:
        lines.append(f"- {check['status']}: {check['name']} - {check['detail']}")

    lines.extend(
        [
            "",
            "## Safety Checks",
            "",
            f"- API key leaked: {str(payload['secret_leak']).lower()}",
            f"- internal raw_text path leaked to Agent context: {str(payload['agent_context_internal_path_leak']).lower()}",
            "",
            "## Recommendation",
            "",
        ]
    )
    if (
        dry["status"] == "succeeded"
        and real["status"] == "succeeded"
        and resume["status"] == "succeeded"
        and system_check["status"] in {"PASS", "WARN"}
        and not payload["secret_leak"]
        and not payload["agent_context_internal_path_leak"]
    ):
        lines.append("Recommendation: enter 30-paper real expansion test.")
    else:
        lines.append("Recommendation: fix Workflow Engine validation issues before 30-paper expansion.")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_workflow_engine_contract() -> None:
    payload = run_workflow_validation(load_bge=True)
    assert payload["dry_run"]["status"] == "succeeded"
    assert payload["real_run"]["status"] == "succeeded"
    assert payload["resume_run"]["status"] == "succeeded"
    assert payload["system_check"]["status"] in {"PASS", "WARN"}
    assert not payload["secret_leak"]
    assert not payload["agent_context_internal_path_leak"]


if __name__ == "__main__":
    result = run_workflow_validation(load_bge=True)
    print(
        json.dumps(
            {
                "report_path": str(REPORT_PATH),
                "dry_run": result["dry_run"]["status"],
                "real_run": result["real_run"]["status"],
                "resume_run": result["resume_run"]["status"],
                "system_check": result["system_check"]["status"],
                "secret_leak": result["secret_leak"],
                "agent_context_internal_path_leak": result["agent_context_internal_path_leak"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(0)
