"""
Asset Quality Checker — validates completeness of all assets per paper.

Checks:
  1. File existence (sections, methods, results, entities, claims_evidence, agent_chunks)
  2. Required fields per asset (asset_id, paper_id, asset_type, source_text, confidence, created_at)
  3. source_text non-empty
  4. confidence validity
  5. linked_evidence_id traceability

Output: 06_PDF_DataAssets/00_registry/quality_status.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_CONFIDENCES = {"high", "medium", "low", "unknown"}
REQUIRED_FIELDS = ["asset_id", "paper_id", "asset_type", "source_text", "confidence", "created_at"]
EXPECTED_FILES = [
    "sections.json",
    "methods.json",
    "results.json",
    "entities.json",
    "claims_evidence.json",
    "agent_chunks.jsonl",
]


class AssetQualityChecker:
    """Validates asset completeness and field-level quality."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.data_dir = self.root / "06_PDF_DataAssets"

    def check_paper(self, paper_id: str) -> dict[str, Any]:
        """Run all quality checks for a single paper. Returns check result dict."""
        result: dict[str, Any] = {
            "paper_id": paper_id,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "file_checks": {},
            "field_checks": {},
            "issues": [],
            "overall_score": 0.0,
            "overall_status": "unknown",
        }

        # ── File existence checks ──
        file_paths = {
            "sections": self.data_dir / "01_sections" / paper_id / "sections.json",
            "methods": self.data_dir / "04_methods" / paper_id / "methods.json",
            "results": self.data_dir / "05_results" / paper_id / "results.json",
            "entities": self.data_dir / "06_entities" / paper_id / "entities.json",
            "claims_evidence": self.data_dir / "07_claims_evidence" / paper_id / "claims_evidence.json",
            "agent_chunks": self.data_dir / "09_agent_chunks" / paper_id / "agent_chunks.jsonl",
        }

        for name, fpath in file_paths.items():
            exists = fpath.exists()
            size = fpath.stat().st_size if exists else 0
            result["file_checks"][name] = {"exists": exists, "size_bytes": size}
            if not exists:
                result["issues"].append(f"missing_file: {name}")

        # ── Field-level checks ──
        field_results: dict[str, Any] = {}

        # Sections
        sec_path = file_paths["sections"]
        if sec_path.exists():
            field_results["sections"] = self._check_asset_list(sec_path, "section", paper_id)

        # Methods
        meth_path = file_paths["methods"]
        if meth_path.exists():
            field_results["methods"] = self._check_asset_list(meth_path, "method", paper_id)

        # Results
        res_path = file_paths["results"]
        if res_path.exists():
            field_results["results"] = self._check_asset_list(res_path, "result", paper_id)

        # Entities
        ent_path = file_paths["entities"]
        if ent_path.exists():
            field_results["entities"] = self._check_asset_list(ent_path, "entity", paper_id)

        # Claims
        claim_path = file_paths["claims_evidence"]
        if claim_path.exists():
            try:
                claim_data = json.loads(claim_path.read_text(encoding="utf-8"))
                claims_list = claim_data.get("claims", [])
                field_results["claims"] = self._check_asset_list_raw(claims_list, "claim", paper_id)
            except Exception:
                field_results["claims"] = {"error": "parse_failed"}

        # Agent chunks (JSONL)
        chunk_path = file_paths["agent_chunks"]
        if chunk_path.exists():
            field_results["agent_chunks"] = self._check_jsonl(chunk_path, "agent_chunk", paper_id)

        result["field_checks"] = field_results

        # Collect field-level issues
        for asset_type, fr in field_results.items():
            if isinstance(fr, dict):
                for issue in fr.get("issues", []):
                    result["issues"].append(f"{asset_type}: {issue}")

        # ── Score calculation ──
        file_count = sum(1 for v in result["file_checks"].values() if v["exists"])
        file_score = (file_count / len(EXPECTED_FILES)) * 50  # 50% weight

        field_scores = []
        for atype in ["sections", "methods", "results", "entities", "claims", "agent_chunks"]:
            fr = field_results.get(atype, {})
            if isinstance(fr, dict) and "score" in fr:
                field_scores.append(fr["score"])
        field_score = (sum(field_scores) / max(len(field_scores), 1)) * 0.5 if field_scores else 0

        result["overall_score"] = round(file_score + field_score, 1)
        if result["overall_score"] >= 90:
            result["overall_status"] = "excellent"
        elif result["overall_score"] >= 70:
            result["overall_status"] = "good"
        elif result["overall_score"] >= 50:
            result["overall_status"] = "fair"
        else:
            result["overall_status"] = "poor"

        return result

    def _check_asset_list(self, path: Path, asset_type: str, paper_id: str) -> dict[str, Any]:
        """Check a JSON file containing a list of assets."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return self._check_asset_list_raw(data, asset_type, paper_id)
            # claims_evidence.json is a dict with "claims" key
            if isinstance(data, dict) and "claims" in data:
                return self._check_asset_list_raw(data["claims"], asset_type, paper_id)
            return {"error": "unexpected_format", "issues": ["unexpected_json_structure"]}
        except Exception as e:
            return {"error": str(e), "issues": ["parse_failed"]}

    def _check_asset_list_raw(self, items: list, asset_type: str, paper_id: str) -> dict[str, Any]:
        """Check a raw list of asset dicts. Chunk-aware for agent_chunks."""
        if not items:
            return {"count": 0, "score": 100, "issues": ["empty_list"]}

        total = len(items)
        missing_field_count = 0
        empty_source_text = 0
        bad_confidence = 0
        missing_evidence_id = 0
        specific_issues: list[str] = []

        # For agent_chunks, the text field is 'text' not 'source_text'
        text_field = "text" if asset_type == "agent_chunk" else "source_text"
        # For agent_chunks, different required fields (not PDFAssetBase subclass)
        is_chunk = asset_type == "agent_chunk"
        chunk_required = ["chunk_id", "paper_id", "chunk_type", "text"]
        fields_to_check = chunk_required if is_chunk else REQUIRED_FIELDS

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            # Required fields
            for rf in fields_to_check:
                if rf not in item or item[rf] is None:
                    missing_field_count += 1
                    if missing_field_count <= 5:
                        specific_issues.append(f"item[{i}] missing '{rf}'")

            # source_text / text non-empty
            st = item.get(text_field, "")
            if not st or (isinstance(st, str) and len(st.strip()) < 2):
                empty_source_text += 1

            # confidence valid
            conf = item.get("confidence", "")
            if conf not in VALID_CONFIDENCES:
                bad_confidence += 1

            # linked_evidence_id traceability
            if "linked_evidence_id" not in item:
                missing_evidence_id += 1

        # Score: 100 - penalties
        penalty = 0
        field_count = len(fields_to_check)
        if total > 0:
            penalty += min(20, (missing_field_count / (total * field_count)) * 20) if field_count > 0 else 0
            penalty += min(30, (empty_source_text / total) * 30)
            penalty += min(20, (bad_confidence / total) * 20)
            penalty += min(10, (missing_evidence_id / total) * 10)

        score = max(0, round(100 - penalty, 1))

        issues = specific_issues[:10]  # cap at 10
        if empty_source_text > 0:
            issues.append(f"{empty_source_text}/{total} items have empty source_text")
        if bad_confidence > 0:
            issues.append(f"{bad_confidence}/{total} items have invalid confidence")
        if missing_evidence_id > 0:
            issues.append(f"{missing_evidence_id}/{total} items missing linked_evidence_id")

        return {
            "count": total,
            "missing_fields": missing_field_count,
            "empty_source_text": empty_source_text,
            "bad_confidence": bad_confidence,
            "missing_evidence_id": missing_evidence_id,
            "score": score,
            "issues": issues,
        }

    def _check_jsonl(self, path: Path, asset_type: str, paper_id: str) -> dict[str, Any]:
        """Check a JSONL file with one JSON object per line."""
        items: list[dict] = []
        try:
            for line in path.read_text(encoding="utf-8").strip().splitlines():
                if line.strip():
                    items.append(json.loads(line))
        except Exception as e:
            return {"error": str(e), "issues": ["jsonl_parse_failed"]}

        return self._check_asset_list_raw(items, asset_type, paper_id)

    def check_all(self) -> dict[str, Any]:
        """Run quality checks for all papers with assets in the registry."""
        registry_path = self.data_dir / "00_registry" / "asset_registry.json"
        if not registry_path.exists():
            return {"error": "no_registry", "papers": {}}

        try:
            reg = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            return {"error": "registry_parse_failed", "papers": {}}

        entries = reg.get("entries", [])
        results: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_papers": len(entries),
            "papers": {},
            "summary": {
                "excellent": 0, "good": 0, "fair": 0, "poor": 0,
                "average_score": 0.0,
            },
        }

        scores = []
        for entry in entries:
            pid = entry.get("paper_id", "")
            if not pid:
                continue
            paper_result = self.check_paper(pid)
            results["papers"][pid] = paper_result
            status = paper_result.get("overall_status", "poor")
            results["summary"][status] = results["summary"].get(status, 0) + 1
            scores.append(paper_result.get("overall_score", 0))

        if scores:
            results["summary"]["average_score"] = round(sum(scores) / len(scores), 1)

        return results

    def save_quality_status(self) -> Path:
        """Run check_all and save to quality_status.json. Returns output path."""
        results = self.check_all()
        output_path = self.data_dir / "00_registry" / "quality_status.json"
        tmp = output_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(output_path)
        return output_path
