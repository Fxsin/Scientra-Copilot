"""Table Context Builder — build comprehensive context for each table asset.

Reuses the FigureContextBuilder pattern adapted for table assets.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scientra.assets.asset_registry import load_registry, get_paper_dir
from scientra.assets.linking import AssetGraphBuilder


class TableContextBuilder:
    """Build comprehensive context for each table asset."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            candidate = Path(__file__).resolve().parent.parent.parent.parent
            self.root = candidate
        else:
            self.root = Path(root).resolve()

    def build_all(self, paper_id: str) -> list[dict[str, Any]]:
        builder = AssetGraphBuilder(self.root)
        links_data = builder.get_asset_links(paper_id)
        if not links_data.get("available"):
            return []

        registry = load_registry(paper_id)
        evidence = self._load_evidence(paper_id)

        asset_by_id = {a.get("asset_id", ""): a for a in (registry.assets if registry and hasattr(registry, 'assets') else [])}
        links_by_asset = self._group_by(links_data.get("asset_links", []), "asset_id")
        mentions_by_id = {m.get("mention_id", ""): m for m in links_data.get("citation_mentions", [])}
        evidence_by_id = self._build_ev_lookup(evidence)
        ev_links_by_asset = self._group_by(links_data.get("evidence_asset_links", []), "asset_id")
        tables_by_label = self._tables_by_label(evidence.get("tables", []))

        contexts: list[dict[str, Any]] = []
        for asset_id, asset_info in asset_by_id.items():
            atype = asset_info.get("asset_type", "")
            if atype not in ("supplementary_table", "dataset"):
                continue

            asset_links = links_by_asset.get(asset_id, [])
            norm_label = next((l.get("normalized_label", "") for l in asset_links if l.get("normalized_label")), "")
            if not norm_label:
                norm_label = self._label_from_filename(asset_info.get("filename", ""))

            body_mentions = []
            for link in asset_links:
                mid = link.get("citation_mention_id", "")
                m = mentions_by_id.get(mid)
                if m:
                    body_mentions.append({
                        "mention_id": m.get("mention_id", ""),
                        "sentence": m.get("sentence", ""),
                        "section": m.get("section", ""),
                        "source_type": m.get("source_type", ""),
                        "citation_text": m.get("citation_text", ""),
                    })

            ev_ids = set()
            for link in asset_links:
                for eid in link.get("linked_evidence_ids", []):
                    ev_ids.add(eid)
            for evl in ev_links_by_asset.get(asset_id, []):
                ev_ids.add(evl.get("evidence_id", ""))

            linked_evidence = [evidence_by_id[eid] for eid in ev_ids if eid in evidence_by_id]
            caption = tables_by_label.get(norm_label, {}).get("caption", "")

            related_claims = list(dict.fromkeys(
                str(e.get("claim", e.get("finding", "")))[:300]
                for e in linked_evidence if e.get("claim") or e.get("finding")
            ))
            related_methods = list(dict.fromkeys(
                str(e.get("method", ""))[:200]
                for e in linked_evidence if e.get("method")
            ))

            paper_dir = get_paper_dir(paper_id)
            asset_path = str(paper_dir / asset_info.get("relative_path", ""))
            has_readable = Path(asset_path).suffix.lower() in (".xlsx", ".xls", ".csv", ".tsv", ".txt") if asset_path else False

            completeness = {
                "has_caption": len(caption) > 0,
                "has_body_mention": len(body_mentions) > 0,
                "has_linked_evidence": len(linked_evidence) > 0,
                "has_readable_table": has_readable,
            }

            table_id = f"tbl_{asset_id}"
            contexts.append({
                "table_id": table_id,
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
                "context_completeness": completeness,
                "warnings": self._gen_warnings(completeness, caption),
            })

        return contexts

    @staticmethod
    def _load_evidence(paper_id: str) -> dict[str, Any]:
        root = Path(__file__).resolve().parent.parent.parent.parent
        ev_path = root / "03_Evidence"
        for d in ev_path.glob(f"*{paper_id.replace('paper_', '')}*"):
            fpath = d / "evidence.json"
            if fpath.exists():
                try:
                    return json.loads(fpath.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return {}

    @staticmethod
    def _group_by(items: list[dict], key: str) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for item in items:
            k = item.get(key, "")
            result.setdefault(k, []).append(item)
        return result

    @staticmethod
    def _build_ev_lookup(evidence: dict) -> dict[str, dict]:
        lookup: dict[str, dict] = {}
        for field in ["key_results", "core_findings", "discussion_points", "methods"]:
            items = evidence.get(field, [])
            if not isinstance(items, list):
                continue
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                eid = f"{evidence.get('paper_id', '')}:evidence:{field}:{i}"
                lookup[eid] = {
                    "evidence_id": eid, "field": field,
                    "text": str(item.get("result", item.get("finding", item.get("name", "")))),
                    "claim": str(item.get("result", item.get("finding", ""))),
                    "finding": str(item.get("result", item.get("finding", ""))),
                    "method": str(item.get("method", item.get("quote", ""))),
                }
        return lookup

    @staticmethod
    def _tables_by_label(tables: list) -> dict[str, dict]:
        return {t.get("table_label", t.get("label", "")): t for t in tables if t.get("table_label") or t.get("label")}

    @staticmethod
    def _label_from_filename(filename: str) -> str:
        m = re.search(r"(?:Table|Tab)[._\s-]*(S?\d+)", filename, re.IGNORECASE)
        return f"Table {m.group(1)}" if m else ""

    @staticmethod
    def _gen_warnings(completeness: dict, caption: str) -> list[str]:
        w = []
        if not completeness["has_caption"]:
            w.append("No caption found.")
        if not completeness["has_body_mention"]:
            w.append("No body text citation found.")
        if not completeness["has_linked_evidence"]:
            w.append("No linked evidence chunks.")
        if not completeness["has_readable_table"]:
            w.append("Table file not readable — structure cannot be parsed.")
        if caption and len(caption) < 30:
            w.append("Caption is very short.")
        return w
