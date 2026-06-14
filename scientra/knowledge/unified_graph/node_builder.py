"""Node Builder — construct unified graph nodes from all available data sources."""

from __future__ import annotations

import uuid
from typing import Any

from scientra.knowledge.unified_graph.graph_schema import make_node, prov


class NodeBuilder:
    """Build all node types for the unified evidence graph."""

    def __init__(self, warnings: list[str] | None = None) -> None:
        self.warnings = warnings or []
        self._id_counter: dict[str, int] = {}

    def _next_id(self, prefix: str) -> str:
        self._id_counter[prefix] = self._id_counter.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counter[prefix]:05d}"

    def build_all(self, paper_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Build all nodes for a paper."""
        nodes: list[dict[str, Any]] = []
        pid = paper_data.get("paper_id", "")
        meta = paper_data.get("paper_meta", {})

        # Paper node
        title = meta.get("title", paper_data.get("paper_meta", {}).get("title", pid))
        nodes.append(make_node(
            self._next_id("paper"), "paper", pid, title=title,
            text=title, source_paths=[f"01_Sources/papers/{meta.get('display_name', '')}"],
            confidence=1.0, provenance=prov("graph_construction", created_by="parser"),
            metadata={"year": meta.get("year", ""), "doi": meta.get("doi", "")},
        ))

        # Evidence nodes
        ev = paper_data.get("evidence", {})
        if isinstance(ev, dict):
            for field in ["key_results", "core_findings", "discussion_points", "methods"]:
                items = ev.get(field, [])
                if isinstance(items, list):
                    for i, item in enumerate(items):
                        if not isinstance(item, dict):
                            continue
                        txt = str(item.get("result", item.get("finding", item.get("name", item.get("quote", "")))))
                        if not txt or len(txt) < 20:
                            continue
                        ntype = "method" if field == "methods" else "evidence"
                        nodes.append(make_node(
                            self._next_id("ev"), ntype, pid, title=txt[:100], text=txt[:500],
                            source_paths=[f"03_Evidence/{pid}/evidence.json"],
                            confidence=0.7 if item.get("confidence") == "high" else 0.5,
                            provenance=prov("evidence_extraction", "evidence.json", created_by="parser"),
                            metadata={"field": field, "index": i},
                        ))

        # Evidence enrichment
        enrichment = paper_data.get("evidence_enrichment", {})
        if isinstance(enrichment, dict):
            claims = enrichment.get("claims", enrichment.get("enriched_claims", []))
            for c in (claims if isinstance(claims, list) else []):
                if isinstance(c, dict) and c.get("text"):
                    nodes.append(make_node(
                        self._next_id("claim"), "claim", pid, title=str(c.get("text", ""))[:100],
                        text=str(c.get("text", ""))[:500],
                        source_paths=[f"03_Assets/ai/evidence_enrichment/{pid}.json"],
                        confidence=float(c.get("confidence", 0.6)),
                        provenance=prov("ai_enrichment", created_by="llm"),
                    ))
            methods = enrichment.get("methods", [])
            for m in (methods if isinstance(methods, list) else []):
                if isinstance(m, dict) and m.get("name"):
                    nodes.append(make_node(
                        self._next_id("method"), "method", pid, title=str(m.get("name", ""))[:100],
                        text=str(m.get("description", m.get("name", "")))[:500],
                        source_paths=[f"03_Assets/ai/evidence_enrichment/{pid}.json"],
                        confidence=0.7, provenance=prov("ai_enrichment", created_by="llm"),
                    ))

        # Figures
        figs = paper_data.get("figures", [])
        for f in (figs if isinstance(figs, list) else []):
            fid = f.get("figure_id", f.get("asset_id", ""))
            label = f.get("figure_label", f.get("label", ""))
            caption = f.get("caption", "")
            nodes.append(make_node(
                self._next_id("fig"), "figure", pid, title=f"{label}: {caption[:80]}" if caption else label,
                text=caption[:500], source_ids=[fid],
                source_paths=[f"03_Assets/figure_assets/..."],
                confidence=float(f.get("confidence", 0.5)) if isinstance(f.get("confidence"), (int, float)) else 0.5,
                provenance=prov("figure_intelligence", created_by="parser"),
                metadata={"label": label, "evidence_type": f.get("evidence_type", ""),
                          "quality_score": f.get("quality_score", 0)},
            ))

        # Tables
        tbls = paper_data.get("tables", [])
        for t in (tbls if isinstance(tbls, list) else []):
            tid = t.get("table_id", t.get("asset_id", ""))
            label = t.get("table_label", t.get("label", ""))
            caption = t.get("caption", "")
            nodes.append(make_node(
                self._next_id("tbl"), "table", pid, title=f"{label}: {caption[:80]}" if caption else label,
                text=caption[:500], source_ids=[tid],
                source_paths=[f"03_Assets/table_assets/..."],
                confidence=0.5, provenance=prov("table_intelligence", created_by="parser"),
                metadata={"label": label, "table_type": t.get("table_type", ""), "n_rows": t.get("n_rows", 0)},
            ))

        # Supplementary
        supps = paper_data.get("supplementary_cards", [])
        if isinstance(supps, list):
            for s in supps:
                nodes.append(make_node(
                    self._next_id("supp"), "supplementary", pid, title=s.get("title", s.get("label", "")),
                    text=s.get("supplementary_summary", "")[:500],
                    source_ids=[s.get("asset_id", "")],
                    source_paths=[f"03_Assets/supplementary_intelligence/..."],
                    confidence=s.get("confidence", 0.5),
                    provenance=prov("supplementary_intelligence", created_by=s.get("mode", "rule")),
                    metadata={"file_type": s.get("file_type", ""), "section_count": s.get("section_count", 0)},
                ))

        # Gaps
        gaps = paper_data.get("gaps", {})
        gap_list = gaps.get("gaps", gaps.get("knowledge_gaps", [])) if isinstance(gaps, dict) else []
        for g in (gap_list if isinstance(gap_list, list) else []):
            if isinstance(g, dict):
                nodes.append(make_node(
                    self._next_id("gap"), "gap", pid, title=str(g.get("gap", ""))[:100],
                    text=str(g.get("gap", g.get("description", "")))[:500],
                    source_paths=[f"03_Assets/ai/gaps/{pid}.json"],
                    confidence=float(g.get("confidence", 0.5)) if isinstance(g.get("confidence"), (int, float)) else 0.5,
                    provenance=prov("ai_enrichment", created_by="llm"),
                ))

        # Hypotheses
        hyps = paper_data.get("hypotheses", {})
        hyp_list = hyps.get("hypotheses", []) if isinstance(hyps, dict) else []
        for h in (hyp_list if isinstance(hyp_list, list) else []):
            if isinstance(h, dict):
                nodes.append(make_node(
                    self._next_id("hyp"), "hypothesis", pid, title=str(h.get("hypothesis", ""))[:100],
                    text=str(h.get("hypothesis", h.get("description", "")))[:500],
                    source_paths=[f"03_Assets/ai/hypotheses/{pid}.json"],
                    confidence=float(h.get("confidence", 0.5)) if isinstance(h.get("confidence"), (int, float)) else 0.5,
                    provenance=prov("ai_enrichment", created_by="llm"),
                ))

        # Entities from enrichment
        entities = enrichment.get("entities", enrichment.get("key_entities", []))
        for e in (entities if isinstance(entities, list) else []):
            name = e if isinstance(e, str) else (e.get("name", e.get("entity", "")) if isinstance(e, dict) else "")
            if name:
                nodes.append(make_node(
                    self._next_id("ent"), "entity", pid, title=str(name)[:100],
                    text=str(name), source_paths=[f"03_Assets/ai/evidence_enrichment/{pid}.json"],
                    confidence=0.6, provenance=prov("ai_enrichment", created_by="llm"),
                ))

        return nodes
