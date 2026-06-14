"""Asset Graph Builder — orchestrator for the full asset linking pipeline.

Runs: CitationParser → LabelNormalizer → AssetMatcher → EvidenceAssetLinker
Outputs: JSON files to {paper_dir}/links/ and a summary markdown.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.assets.asset_registry import load_registry, get_paper_dir
from scientra.assets.linking.citation_parser import CitationParser
from scientra.assets.linking.asset_matcher import AssetMatcher
from scientra.assets.linking.evidence_asset_linker import EvidenceAssetLinker


class AssetGraphBuilder:
    """Orchestrate the asset linking pipeline for a paper."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            candidate = Path(__file__).resolve().parent.parent.parent.parent
            self.root = candidate
        else:
            self.root = Path(root).resolve()

    def build(self, paper_id: str, force: bool = False) -> dict[str, Any]:
        """Run the full asset linking pipeline.

        Args:
            paper_id: The paper ID.
            force: If True, overwrite existing output files.

        Returns:
            Summary dict with counts and status.
        """
        # Check if outputs already exist
        links_dir = self._get_links_dir(paper_id)
        output_exists = all(
            (links_dir / f).exists()
            for f in [
                "citation_mentions.json",
                "asset_links.json",
                "evidence_asset_links.json",
            ]
        )
        if output_exists and not force:
            # Load existing results and return summary
            return self._load_existing_summary(paper_id, links_dir)

        # Step 1: Load registry
        registry = load_registry(paper_id)
        if registry is None:
            return {
                "paper_id": paper_id,
                "success": False,
                "error": "Asset registry not found. Run Scripts/init_paper_assets.py first.",
                "citation_count": 0,
                "link_count": 0,
                "evidence_link_count": 0,
                "unmatched_asset_count": 0,
                "unmatched_mention_count": 0,
                "low_confidence_count": 0,
            }

        # Step 2: Parse citations
        parser = CitationParser(self.root)
        mentions = parser.parse_all_sources(paper_id)

        # Step 3: Match citations to assets
        matcher = AssetMatcher(self.root)
        match_result = matcher.match_all(paper_id, mentions, registry)

        links = match_result["links"]
        unmatched_mentions = match_result["unmatched_mentions"]
        unmatched_assets = match_result["unmatched_assets"]
        low_confidence = match_result["low_confidence"]

        # Step 4: Link evidence to assets
        evidence_linker = EvidenceAssetLinker(self.root)
        evidence_links = evidence_linker.link(paper_id, mentions, links)
        asset_evidence_index = evidence_linker.build_asset_evidence_index(evidence_links)

        # Step 5: Enrich links with evidence back-references
        for link in links:
            asset_id = link.get("asset_id", "")
            link["linked_evidence_ids"] = asset_evidence_index.get(asset_id, [])

        # Step 6: Write output files
        links_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(links_dir / "citation_mentions.json", mentions)
        self._write_json(links_dir / "asset_links.json", links)
        self._write_json(links_dir / "evidence_asset_links.json", evidence_links)
        self._write_json(links_dir / "unmatched_assets.json", unmatched_assets)
        self._write_json(links_dir / "low_confidence_links.json", low_confidence)

        # Step 7: Build unmatched mentions output (only those not linked)
        unmatched_mention_data = [
            {
                "mention_id": m.get("mention_id", ""),
                "citation_text": m.get("citation_text", ""),
                "normalized_label": m.get("normalized_label", ""),
                "asset_type": m.get("asset_type", ""),
                "source_type": m.get("source_type", ""),
                "section": m.get("section", ""),
                "sentence": m.get("sentence", ""),
            }
            for m in unmatched_mentions
        ]
        self._write_json(links_dir / "unmatched_mentions.json", unmatched_mention_data)

        # Step 8: Write summary
        summary = {
            "paper_id": paper_id,
            "success": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "citation_count": len(mentions),
            "link_count": len(links),
            "evidence_link_count": len(evidence_links),
            "unmatched_asset_count": len(unmatched_assets),
            "unmatched_mention_count": len(unmatched_mentions),
            "low_confidence_count": len(low_confidence),
            "match_methods": self._count_methods(links),
            "relation_types": self._count_relations(evidence_links),
        }

        self._write_summary_md(links_dir / "asset_graph_summary.md", summary, mentions,
                               links, evidence_links, unmatched_assets, unmatched_mentions,
                               low_confidence)

        return summary

    def _get_links_dir(self, paper_id: str) -> Path:
        """Get the links output directory for a paper."""
        paper_dir = get_paper_dir(paper_id)
        return paper_dir / "links"

    def get_asset_links(self, paper_id: str) -> dict[str, Any]:
        """Get existing asset links for a paper (read-only)."""
        links_dir = self._get_links_dir(paper_id)
        result: dict[str, Any] = {
            "paper_id": paper_id,
            "available": False,
            "citation_mentions": [],
            "asset_links": [],
            "evidence_asset_links": [],
            "unmatched_assets": [],
            "low_confidence_links": [],
            "summary": {},
        }

        files_map = {
            "citation_mentions": "citation_mentions.json",
            "asset_links": "asset_links.json",
            "evidence_asset_links": "evidence_asset_links.json",
            "unmatched_assets": "unmatched_assets.json",
            "low_confidence_links": "low_confidence_links.json",
        }

        available = False
        for key, filename in files_map.items():
            fpath = links_dir / filename
            if fpath.exists():
                try:
                    result[key] = json.loads(fpath.read_text(encoding="utf-8"))
                    available = True
                except Exception:
                    pass

        result["available"] = available
        if available:
            result["summary"] = {
                "citation_count": len(result["citation_mentions"]),
                "link_count": len(result["asset_links"]),
                "evidence_link_count": len(result["evidence_asset_links"]),
                "unmatched_asset_count": len(result["unmatched_assets"]),
                "low_confidence_count": len(result["low_confidence_links"]),
            }

        return result

    def get_unmatched_assets(self, paper_id: str) -> dict[str, Any]:
        """Get unmatched assets for a paper."""
        links_dir = self._get_links_dir(paper_id)
        fpath = links_dir / "unmatched_assets.json"

        if not fpath.exists():
            return {"paper_id": paper_id, "available": False, "unmatched_assets": []}

        try:
            unmatched = json.loads(fpath.read_text(encoding="utf-8"))
            return {"paper_id": paper_id, "available": True, "unmatched_assets": unmatched}
        except Exception:
            return {"paper_id": paper_id, "available": False, "unmatched_assets": []}

    def _load_existing_summary(self, paper_id: str, links_dir: Path) -> dict[str, Any]:
        """Load summary from existing output files."""
        result = self.get_asset_links(paper_id)
        summary = result.get("summary", {})
        return {
            "paper_id": paper_id,
            "success": True,
            "generated_at": "",
            "citation_count": summary.get("citation_count", 0),
            "link_count": summary.get("link_count", 0),
            "evidence_link_count": summary.get("evidence_link_count", 0),
            "unmatched_asset_count": summary.get("unmatched_asset_count", 0),
            "unmatched_mention_count": 0,
            "low_confidence_count": summary.get("low_confidence_count", 0),
            "match_methods": {},
            "relation_types": {},
        }

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        """Write JSON data to file."""
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _count_methods(links: list[dict[str, Any]]) -> dict[str, int]:
        """Count links by match method."""
        counts: dict[str, int] = {}
        for link in links:
            method = link.get("match_method", "unknown")
            counts[method] = counts.get(method, 0) + 1
        return counts

    @staticmethod
    def _count_relations(evidence_links: list[dict[str, Any]]) -> dict[str, int]:
        """Count evidence links by relation type."""
        counts: dict[str, int] = {}
        for link in evidence_links:
            rel = link.get("relation", "unknown")
            counts[rel] = counts.get(rel, 0) + 1
        return counts

    @staticmethod
    def _write_summary_md(
        path: Path,
        summary: dict[str, Any],
        mentions: list[dict[str, Any]],
        links: list[dict[str, Any]],
        evidence_links: list[dict[str, Any]],
        unmatched_assets: list[dict[str, Any]],
        unmatched_mentions: list[dict[str, Any]],
        low_confidence: list[dict[str, Any]],
    ) -> None:
        """Write human-readable summary markdown."""
        lines = [
            f"# Asset Graph Summary — {summary['paper_id']}",
            "",
            f"Generated: {summary.get('generated_at', 'N/A')}",
            "",
            "## Statistics",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Total citation mentions | {summary['citation_count']} |",
            f"| Matched asset links | {summary['link_count']} |",
            f"| Evidence-asset links | {summary['evidence_link_count']} |",
            f"| Unmatched assets | {summary['unmatched_asset_count']} |",
            f"| Unmatched mentions | {summary['unmatched_mention_count']} |",
            f"| Low confidence matches | {summary['low_confidence_count']} |",
            "",
        ]

        # Match methods breakdown
        methods = summary.get("match_methods", {})
        if methods:
            lines.append("## Match Methods")
            lines.append("")
            lines.append("| Method | Count |")
            lines.append("|--------|-------|")
            for method, count in sorted(methods.items()):
                lines.append(f"| {method} | {count} |")
            lines.append("")

        # Relation types breakdown
        relations = summary.get("relation_types", {})
        if relations:
            lines.append("## Evidence-Asset Relations")
            lines.append("")
            lines.append("| Relation | Count |")
            lines.append("|----------|-------|")
            for rel, count in sorted(relations.items()):
                lines.append(f"| {rel} | {count} |")
            lines.append("")

        # Linked assets table
        if links:
            lines.append("## Linked Assets")
            lines.append("")
            lines.append("| Asset ID | Label | Method | Confidence | Evidence IDs |")
            lines.append("|----------|-------|--------|------------|--------------|")
            for link in links[:50]:  # Limit to 50
                aid = link.get("asset_id", "")[:20]
                label = link.get("normalized_label", "")
                method = link.get("match_method", "")
                conf = link.get("confidence", 0)
                ev_ids = ", ".join(link.get("linked_evidence_ids", [])[:3])
                lines.append(f"| {aid} | {label} | {method} | {conf:.2f} | {ev_ids} |")
            if len(links) > 50:
                lines.append(f"| ... | +{len(links) - 50} more | | | |")
            lines.append("")

        # Unmatched assets
        if unmatched_assets:
            lines.append("## ⚠️ Unmatched Assets")
            lines.append("")
            for a in unmatched_assets[:20]:
                lines.append(f"- **{a.get('filename', '?')}** ({a.get('asset_type', '?')})")
            if len(unmatched_assets) > 20:
                lines.append(f"- ... and {len(unmatched_assets) - 20} more")
            lines.append("")

        # Low confidence
        if low_confidence:
            lines.append("## ⚠️ Low Confidence Matches")
            lines.append("")
            for lc in low_confidence[:10]:
                lines.append(
                    f"- **{lc.get('normalized_label', '?')}** → "
                    f"{lc.get('asset_id', '?')} "
                    f"(confidence: {lc.get('confidence', 0):.2f}, method: {lc.get('match_method', '?')})"
                )
            if len(low_confidence) > 10:
                lines.append(f"- ... and {len(low_confidence) - 10} more")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
