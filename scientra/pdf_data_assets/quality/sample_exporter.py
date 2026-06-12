"""
Sample Exporter — generates human-reviewable sample files.

For each paper, exports random samples:
  - 5 method assets
  - 5 result assets
  - 20 entities
  - 5 claims
  - 10 agent chunks

Output:
  - 06_PDF_DataAssets/00_registry/samples/{paper_id}/sample_review.md
  - 06_PDF_DataAssets/00_registry/samples/{paper_id}/sample_review.json
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SampleExporter:
    """Exports random samples for human quality review."""

    SAMPLE_SIZES = {
        "methods": 5,
        "results": 5,
        "entities": 20,
        "claims": 5,
        "agent_chunks": 10,
    }

    def __init__(self, root: str | Path, seed: int = 42) -> None:
        self.root = Path(root).resolve()
        self.data_dir = self.root / "06_PDF_DataAssets"
        self.samples_dir = self.data_dir / "00_registry" / "samples"
        random.seed(seed)

    def export_paper(self, paper_id: str) -> dict[str, Any]:
        """Export samples for a single paper. Returns paths."""
        paper_samples_dir = self.samples_dir / paper_id
        paper_samples_dir.mkdir(parents=True, exist_ok=True)

        samples: dict[str, list[dict[str, Any]]] = {}

        # ── Load sources ──
        sources = {
            "methods": self.data_dir / "04_methods" / paper_id / "methods.json",
            "results": self.data_dir / "05_results" / paper_id / "results.json",
            "entities": self.data_dir / "06_entities" / paper_id / "entities.json",
            "claims": self.data_dir / "07_claims_evidence" / paper_id / "claims_evidence.json",
            "agent_chunks": self.data_dir / "09_agent_chunks" / paper_id / "agent_chunks.jsonl",
        }

        for asset_type, path in sources.items():
            if not path.exists():
                samples[asset_type] = []
                continue
            try:
                if asset_type == "agent_chunks":
                    items = []
                    for line in path.read_text(encoding="utf-8").strip().splitlines():
                        if line.strip():
                            items.append(json.loads(line))
                elif asset_type == "claims":
                    data = json.loads(path.read_text(encoding="utf-8"))
                    items = data.get("claims", [])
                else:
                    items = json.loads(path.read_text(encoding="utf-8"))

                if not isinstance(items, list):
                    items = []

                n = min(self.SAMPLE_SIZES.get(asset_type, 5), len(items))
                sampled = random.sample(items, n) if n > 0 else []
                samples[asset_type] = sampled
            except Exception:
                samples[asset_type] = []

        # ── Write JSON ──
        json_path = paper_samples_dir / "sample_review.json"
        export_data = {
            "paper_id": paper_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "sample_sizes": {k: len(v) for k, v in samples.items()},
            "samples": samples,
        }
        tmp = json_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(json_path)

        # ── Write Markdown ──
        md_path = paper_samples_dir / "sample_review.md"
        md_content = self._build_markdown(paper_id, samples)
        tmp_md = md_path.with_suffix(".tmp")
        tmp_md.write_text(md_content, encoding="utf-8")
        tmp_md.replace(md_path)

        return {
            "paper_id": paper_id,
            "json_path": str(json_path),
            "md_path": str(md_path),
            "sample_counts": {k: len(v) for k, v in samples.items()},
        }

    def _build_markdown(self, paper_id: str, samples: dict[str, list[dict[str, Any]]]) -> str:
        """Build a human-readable markdown review document."""
        lines: list[str] = []
        lines.append(f"# Sample Review — {paper_id}")
        lines.append(f"")
        lines.append(f"**Exported:** {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"**Purpose:** Manual quality spot-check for Phase 0 assetization")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

        for asset_type in ["methods", "results", "entities", "claims", "agent_chunks"]:
            items = samples.get(asset_type, [])
            lines.append(f"## {asset_type.upper()} ({len(items)} samples)")
            lines.append(f"")

            if not items:
                lines.append(f"> No {asset_type} samples available.")
                lines.append(f"")
                continue

            for i, item in enumerate(items):
                lines.append(f"### {asset_type[:-1].title()} {i + 1}")
                lines.append(f"")

                if asset_type == "methods":
                    lines.append(f"- **Method Name:** `{item.get('method_name', 'unknown')}`")
                    lines.append(f"- **Category:** {item.get('method_category', 'unknown')}")
                    lines.append(f"- **Evidence Type:** {item.get('evidence_type', 'unknown')}")
                    lines.append(f"- **Section:** {item.get('source_section', 'unknown')}")
                    lines.append(f"- **Confidence:** `{item.get('confidence', 'unknown')}`")
                    lines.append(f"- **Evidence ID:** `{item.get('linked_evidence_id', 'none')}`")
                    lines.append(f"- **Source Text:**")
                    lines.append(f"  > {item.get('source_text', '')[:300]}")
                    lines.append(f"- **Possible Issue:** {self._flag_issue(item)}")

                elif asset_type == "results":
                    lines.append(f"- **Result:** {item.get('result_text', '')[:200]}")
                    lines.append(f"- **Direction:** {item.get('direction', 'unknown')}")
                    lines.append(f"- **Section:** {item.get('source_section', 'unknown')}")
                    lines.append(f"- **Confidence:** `{item.get('confidence', 'unknown')}`")
                    lines.append(f"- **Evidence ID:** `{item.get('linked_evidence_id', 'none')}`")
                    lines.append(f"- **Linked Methods:** {item.get('linked_method_id', 'none')}")
                    lines.append(f"- **Source Text Preview:** {item.get('source_text', '')[:120]}")
                    lines.append(f"- **Possible Issue:** {self._flag_issue(item)}")

                elif asset_type == "entities":
                    lines.append(f"- **Entity:** `{item.get('entity_name', 'unknown')}`")
                    lines.append(f"- **Type:** {item.get('entity_type', 'unknown')}")
                    lines.append(f"- **Confidence:** `{item.get('confidence', 'unknown')}`")
                    lines.append(f"- **Context:** {item.get('entity_context', '')[:150]}")
                    lines.append(f"- **Status:** {item.get('entity_status', 'unchecked')}")
                    lines.append(f"- **Possible Issue:** {self._flag_issue(item)}")

                elif asset_type == "claims":
                    lines.append(f"- **Claim:** {item.get('claim_text', '')[:200]}")
                    lines.append(f"- **Type:** {item.get('claim_type', 'unknown')}")
                    lines.append(f"- **Section:** {item.get('source_section', 'unknown')}")
                    lines.append(f"- **Confidence:** `{item.get('confidence', 'unknown')}`")
                    lines.append(f"- **Evidence ID:** `{item.get('linked_evidence_id', 'none')}`")
                    lines.append(f"- **Evidence Links:** {len(item.get('supporting_evidence', []))} supporting")
                    lines.append(f"- **Quality Score:** {item.get('claim_quality_score', 'unchecked')}")
                    lines.append(f"- **Needs AI:** {item.get('needs_ai_interpretation', 'unchecked')}")
                    lines.append(f"- **Source Text Preview:** {str(item.get('source_text', ''))[:120]}")
                    lines.append(f"- **Possible Issue:** {self._flag_issue(item)}")

                elif asset_type == "agent_chunks":
                    lines.append(f"- **Chunk ID:** `{item.get('chunk_id', 'unknown')}`")
                    lines.append(f"- **Type:** {item.get('chunk_type', 'unknown')}")
                    lines.append(f"- **Section:** {item.get('source_section', 'unknown')}")
                    lines.append(f"- **Text:** {item.get('text', '')[:200]}")
                    lines.append(f"- **Source Assets:** {item.get('source_asset_ids', [])}")
                    lines.append(f"- **Evidence ID:** `{item.get('linked_evidence_id', 'none')}`")
                    lines.append(f"- **Evidence IDs:** {item.get('linked_evidence_ids', [])}")
                    lines.append(f"- **Vector Ready:** {item.get('vector_ready', 'unchecked')}")
                    lines.append(f"- **Quality Score:** {item.get('quality_score', 'unchecked')}")
                    lines.append(f"- **Entities ({len(item.get('entities', []))}):** {', '.join(str(e) for e in item.get('entities', [])[:10])}")
                    lines.append(f"- **Source Text Preview:** {str(item.get('text', ''))[:120]}")
                    lines.append(f"- **Possible Issue:** {self._flag_issue(item)}")

                lines.append(f"")

        lines.append(f"---")
        lines.append(f"*Generated by Scientra Copilot Phase 0.5 Sample Exporter*")
        return "\n".join(lines)

    def _flag_issue(self, item: dict[str, Any]) -> str:
        """Flag potential quality issues."""
        issues: list[str] = []

        source_text = str(item.get("source_text", ""))
        if not source_text or len(source_text.strip()) < 10:
            # For chunks, check 'text' field instead
            chunk_text = str(item.get("text", ""))
            if not chunk_text or len(chunk_text.strip()) < 10:
                issues.append("missing/empty source_text")

        confidence = str(item.get("confidence", ""))
        if confidence in ("low", "unknown"):
            issues.append(f"low confidence ({confidence})")

        if item.get("entity_status") in ("filtered_stopword", "filtered_generic_word"):
            issues.append(f"filtered: {item.get('entity_status')}")

        if item.get("needs_ai_interpretation"):
            issues.append("needs AI interpretation")

        if item.get("vector_ready") is False:
            issues.append("not vector-ready")

        # Traceability check (Phase 0.5B)
        chunk_type = str(item.get("chunk_type", ""))
        if chunk_type in ("method", "result", "claim"):
            has_ev = bool(item.get("linked_evidence_id")) or bool(item.get("linked_evidence_ids"))
            if not has_ev:
                issues.append("missing_linked_evidence_id")

        qs = item.get("quality_score")
        if isinstance(qs, (int, float)) and qs < 70:
            issues.append(f"quality_score={qs}")

        return ", ".join(issues) if issues else "none apparent"

    def export_all(self) -> dict[str, Any]:
        """Export samples for all papers in the registry."""
        registry_path = self.data_dir / "00_registry" / "asset_registry.json"
        if not registry_path.exists():
            return {"error": "no_registry"}

        reg = json.loads(registry_path.read_text(encoding="utf-8"))
        results: dict[str, Any] = {"exported_at": datetime.now(timezone.utc).isoformat(), "papers": {}}

        for entry in reg.get("entries", []):
            pid = entry.get("paper_id", "")
            if pid and entry.get("build_status") == "success":
                results["papers"][pid] = self.export_paper(pid)

        return results
