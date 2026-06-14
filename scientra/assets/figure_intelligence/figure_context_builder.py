"""Figure Context Builder — build comprehensive context for each figure from asset graph.

Gathers all available information about a figure from:
  - Asset registry (file path, metadata)
  - Asset links (citation mentions)
  - Evidence chunks (linked findings, claims, methods)
  - Caption (from evidence.json figures array)
  - Body citation sentences
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scientra.assets.asset_registry import load_registry, get_paper_dir
from scientra.assets.linking import AssetGraphBuilder


class FigureContextBuilder:
    """Build comprehensive context for each figure asset."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            candidate = Path(__file__).resolve().parent.parent.parent.parent
            self.root = candidate
        else:
            self.root = Path(root).resolve()

    def build_all(self, paper_id: str) -> list[dict[str, Any]]:
        """Build figure contexts for all figure assets in a paper.

        Returns list of figure context dicts.
        """
        # Load asset graph data
        builder = AssetGraphBuilder(self.root)
        links_data = builder.get_asset_links(paper_id)

        if not links_data.get("available"):
            return []

        # Load registry for asset file paths
        registry = load_registry(paper_id)

        # Load evidence.json for captions and detailed evidence
        evidence = self._load_evidence(paper_id)

        # Build lookup structures
        asset_by_id = self._build_asset_lookup(registry)
        links_by_asset = self._build_links_by_asset(links_data.get("asset_links", []))
        mentions_by_id = self._build_mentions_by_id(links_data.get("citation_mentions", []))
        evidence_by_id = self._build_evidence_lookup(evidence)
        evidence_links_by_asset = self._build_ev_links_by_asset(
            links_data.get("evidence_asset_links", [])
        )

        # Get figures from evidence.json (has captions)
        figures_data = evidence.get("figures", []) if isinstance(evidence, dict) else []
        figures_by_label = self._build_figures_by_label(figures_data)

        # Filter to figure-type assets only
        contexts: list[dict[str, Any]] = []

        for asset_id, asset_info in asset_by_id.items():
            asset_type = asset_info.get("asset_type", "")
            # Include figure_image and supplementary_pdf (which may contain figures)
            if asset_type not in ("figure_image",):
                continue

            # Get normalized label from links
            asset_links = links_by_asset.get(asset_id, [])
            norm_label = ""
            for link in asset_links:
                if link.get("normalized_label"):
                    norm_label = link["normalized_label"]
                    break

            # If no label from links, try to derive from filename
            if not norm_label:
                norm_label = self._label_from_filename(asset_info.get("filename", ""))

            # Build body mentions
            body_mentions: list[dict[str, Any]] = []
            for link in asset_links:
                mid = link.get("citation_mention_id", "")
                mention = mentions_by_id.get(mid)
                if mention:
                    body_mentions.append({
                        "mention_id": mention.get("mention_id", ""),
                        "sentence": mention.get("sentence", ""),
                        "section": mention.get("section", ""),
                        "source_type": mention.get("source_type", ""),
                        "citation_text": mention.get("citation_text", ""),
                        "context_before": mention.get("context_before", ""),
                        "context_after": mention.get("context_after", ""),
                    })

            # Get linked evidence
            ev_link_ids = set()
            for link in asset_links:
                for ev_id in link.get("linked_evidence_ids", []):
                    ev_link_ids.add(ev_id)

            # Also get from evidence_asset_links
            ev_asset_links = evidence_links_by_asset.get(asset_id, [])
            for evl in ev_asset_links:
                ev_link_ids.add(evl.get("evidence_id", ""))

            linked_evidence: list[dict[str, Any]] = []
            for ev_id in ev_link_ids:
                ev_data = evidence_by_id.get(ev_id) or self._resolve_evidence_ref(ev_id, evidence)
                if ev_data:
                    linked_evidence.append(ev_data)

            # Get caption from evidence.json figures
            caption = ""
            figure_meta = figures_by_label.get(norm_label) or {}
            caption = figure_meta.get("caption", "")
            if not caption:
                # Try partial match
                for lbl, fig in figures_by_label.items():
                    if norm_label and (norm_label in lbl or lbl in norm_label):
                        caption = fig.get("caption", "")
                        break

            # Build related claims and methods
            related_claims: list[str] = []
            related_methods: list[str] = []
            for ev in linked_evidence:
                claim = ev.get("claim", ev.get("finding", ev.get("result", "")))
                if claim and claim not in related_claims:
                    related_claims.append(str(claim)[:300])
                method = ev.get("method", "")
                if method and method not in related_methods:
                    related_methods.append(str(method)[:200])

            # Determine context completeness
            context_completeness = {
                "has_caption": len(caption) > 0,
                "has_body_mention": len(body_mentions) > 0,
                "has_linked_evidence": len(linked_evidence) > 0,
            }

            # Build figure ID
            figure_id = f"fig_{asset_id}"

            # Get asset file path
            paper_dir = get_paper_dir(paper_id)
            asset_path = str(paper_dir / asset_info.get("relative_path", ""))

            context = {
                "figure_id": figure_id,
                "paper_id": paper_id,
                "asset_id": asset_id,
                "normalized_label": norm_label,
                "asset_path": asset_path,
                "asset_filename": asset_info.get("filename", ""),
                "caption": caption,
                "body_mentions": body_mentions,
                "linked_evidence": linked_evidence,
                "related_claims": related_claims,
                "related_methods": related_methods,
                "context_completeness": context_completeness,
                "warnings": self._generate_warnings(context_completeness, body_mentions, caption),
            }

            contexts.append(context)

        return contexts

    # ── Helpers ──

    @staticmethod
    def _load_evidence(paper_id: str) -> dict[str, Any]:
        """Load evidence.json for a paper."""
        root = Path(__file__).resolve().parent.parent.parent.parent
        ev_path = root / "03_Evidence"
        # Search for the paper's evidence directory
        for d in ev_path.glob(f"*{paper_id.replace('paper_', '')}*"):
            fpath = d / "evidence.json"
            if fpath.exists():
                try:
                    return json.loads(fpath.read_text(encoding="utf-8"))
                except Exception:
                    pass
        # Also try direct path
        direct = ev_path / paper_id / "evidence.json"
        if direct.exists():
            try:
                return json.loads(direct.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    @staticmethod
    def _build_asset_lookup(registry: Any) -> dict[str, dict[str, Any]]:
        """Build asset_id -> asset info dict."""
        lookup: dict[str, dict[str, Any]] = {}
        if registry is None:
            return lookup
        assets = registry.assets if hasattr(registry, 'assets') else []
        for a in assets:
            lookup[a.get("asset_id", "")] = a
        return lookup

    @staticmethod
    def _build_links_by_asset(links: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Build asset_id -> list of links."""
        by_asset: dict[str, list[dict[str, Any]]] = {}
        for link in links:
            aid = link.get("asset_id", "")
            if aid not in by_asset:
                by_asset[aid] = []
            by_asset[aid].append(link)
        return by_asset

    @staticmethod
    def _build_mentions_by_id(mentions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Build mention_id -> mention dict."""
        by_id: dict[str, dict[str, Any]] = {}
        for m in mentions:
            by_id[m.get("mention_id", "")] = m
        return by_id

    @staticmethod
    def _build_evidence_lookup(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Build evidence_id -> evidence item dict."""
        lookup: dict[str, dict[str, Any]] = {}
        fields = ["key_results", "core_findings", "discussion_points", "methods"]
        for field in fields:
            items = evidence.get(field, [])
            if not isinstance(items, list):
                continue
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                ev_id = f"{evidence.get('paper_id', '')}:evidence:{field}:{i}"
                lookup[ev_id] = {
                    "evidence_id": ev_id,
                    "field": field,
                    "index": i,
                    "text": str(item.get("result", item.get("finding", item.get("name", "")))),
                    "claim": str(item.get("result", item.get("finding", ""))),
                    "finding": str(item.get("result", item.get("finding", ""))),
                    "method": str(item.get("method", item.get("quote", ""))),
                    "section": str(item.get("section", "")),
                    "confidence": str(item.get("confidence", "")),
                }
        return lookup

    @staticmethod
    def _build_ev_links_by_asset(ev_links: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Build asset_id -> list of evidence-asset links."""
        by_asset: dict[str, list[dict[str, Any]]] = {}
        for evl in ev_links:
            aid = evl.get("asset_id", "")
            if aid not in by_asset:
                by_asset[aid] = []
            by_asset[aid].append(evl)
        return by_asset

    @staticmethod
    def _build_figures_by_label(figures: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Build normalized label -> figure data dict."""
        by_label: dict[str, dict[str, Any]] = {}
        for fig in figures:
            label = fig.get("figure_label", fig.get("label", ""))
            if label:
                by_label[label] = fig
        return by_label

    @staticmethod
    def _label_from_filename(filename: str) -> str:
        """Derive a normalized label from filename."""
        import re
        # Try to extract Figure_X or Fig_X pattern
        match = re.search(r"(?:Figure|Fig)[._\s-]*(S?\d+)", filename, re.IGNORECASE)
        if match:
            return f"Figure {match.group(1)}"
        return ""

    @staticmethod
    def _resolve_evidence_ref(ev_id: str, evidence: dict[str, Any]) -> dict[str, Any] | None:
        """Resolve an evidence reference that might not be in the main lookup."""
        # Parse the ev_id format: paper_id:evidence:field:index
        parts = ev_id.split(":")
        if len(parts) < 4:
            return None
        field = parts[2]
        try:
            idx = int(parts[3])
        except ValueError:
            return None

        items = evidence.get(field, [])
        if isinstance(items, list) and 0 <= idx < len(items):
            item = items[idx]
            if isinstance(item, dict):
                return {
                    "evidence_id": ev_id,
                    "field": field,
                    "index": idx,
                    "text": str(item.get("result", item.get("finding", item.get("name", "")))),
                    "claim": str(item.get("result", item.get("finding", ""))),
                    "finding": str(item.get("result", item.get("finding", ""))),
                    "method": str(item.get("method", item.get("quote", ""))),
                    "section": str(item.get("section", "")),
                    "confidence": str(item.get("confidence", "")),
                }
        return None

    @staticmethod
    def _generate_warnings(
        completeness: dict[str, bool],
        body_mentions: list[dict[str, Any]],
        caption: str,
    ) -> list[str]:
        """Generate warnings based on context completeness."""
        warnings: list[str] = []
        if not completeness["has_caption"]:
            warnings.append("No caption found in evidence.json — figure interpretation may be limited.")
        if not completeness["has_body_mention"]:
            warnings.append("No body text citation found — figure may not be discussed in main text.")
        if not completeness["has_linked_evidence"]:
            warnings.append("No linked evidence chunks — interpretation relies on caption only.")
        if body_mentions and len(body_mentions) < 2:
            warnings.append("Only one body mention — limited context for interpretation.")
        if caption and len(caption) < 30:
            warnings.append("Caption is very short — may lack detail for reliable interpretation.")
        return warnings
