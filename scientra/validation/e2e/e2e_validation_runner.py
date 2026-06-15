"""E2E Validation Runner — P6.0 orchestrator."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from scientra.validation.e2e.pipeline_inventory import PipelineInventory
from scientra.validation.e2e.paper_status_auditor import PaperStatusAuditor
from scientra.validation.e2e.storage_layout_validator import StorageLayoutValidator
from scientra.validation.e2e.module_health_checker import ModuleHealthChecker
from scientra.validation.e2e.query_eval_runner import QueryEvalRunner
from scientra.validation.e2e.agent_eval_runner import AgentEvalRunner
from scientra.validation.e2e.quality_report_builder import QualityReportBuilder
from scientra.validation.e2e.hardening_recommendation_builder import HardeningRecommendationBuilder

OUTPUT_DIR = "10_System/validation/e2e"


class E2EValidationRunner:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.out = self.root / OUTPUT_DIR

    def run(self, skip_agent: bool = False, skip_query: bool = False,
            check_storage: bool = True, check_db: bool = True) -> dict[str, Any]:
        self.out.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []

        # 1. Pipeline Inventory
        inv = PipelineInventory(self.root).scan()
        self._wj("pipeline_inventory.json", inv)

        # 2. Paper Status
        auditor = PaperStatusAuditor(self.root)
        paper_status = auditor.audit_all()
        self._wj("paper_status_details.json", paper_status)

        # 3. Storage Layout
        storage = {}
        if check_storage or check_db:
            storage = StorageLayoutValidator(self.root).validate()
            self._wj("storage_layout_report.json", storage)

        # 4. Module Health
        mh = ModuleHealthChecker(self.root).check()
        self._wj("module_health.json", mh)

        # 5. Query Eval
        qe: dict = {}
        if not skip_query:
            qe = QueryEvalRunner(self.root).run()
            self._wj("query_eval_results.json", qe)
        else:
            qe = {"available": False, "skipped": True}

        # 6. Agent Eval
        ae: dict = {}
        if not skip_agent:
            ae = AgentEvalRunner(self.root).run()
            self._wj("agent_eval_results.json", ae)
        else:
            ae = {"available": False, "skipped": True}

        # 7. Recommendations
        recs = HardeningRecommendationBuilder().build(inv, paper_status, storage, mh, qe, ae)
        self._wj("hardening_recommendations.json", recs)

        # 8. Reports
        builder = QualityReportBuilder(self.out)
        builder.build_all(inv, paper_status, storage, mh, qe, ae, recs)

        return {
            "papers": len(paper_status),
            "papers_complete": sum(1 for p in paper_status if p.get("completion_score", 0) >= 0.5),
            "storage_v3": storage.get("v3_compliant", False),
            "db_v2_clean": storage.get("db_v2_clean", True),
            "modules_ok": mh.get("all_modules_ok", False),
            "query_passed": qe.get("passed", 0),
            "agent_passed": ae.get("passed", 0),
            "p0_count": len(recs.get("P0", [])),
            "p1_count": len(recs.get("P1", [])),
            "output_dir": str(self.out.relative_to(self.root)),
        }

    def get_summary(self) -> dict[str, Any]:
        p = self.out / "e2e_validation_summary.json"
        if not p.exists(): return {"available": False, "message": "Not yet run. Use: python Scripts/run_e2e_validation.py --all"}
        try:
            return {"available": True, **json.loads(p.read_text(encoding="utf-8"))}
        except Exception:
            return {"available": False}

    def _wj(self, name: str, data: Any) -> None:
        (self.out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
