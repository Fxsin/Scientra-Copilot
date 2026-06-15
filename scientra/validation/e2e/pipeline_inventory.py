"""Pipeline Inventory — scan Storage Layout v3 for P4/P5 outputs."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any


class PipelineInventory:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def scan(self) -> dict[str, Any]:
        return {
            "01_sources": self._count_dir("01_Sources/papers", True),
            "02_parse": {"text": self._count_dir("02_Parse/text", True),
                         "supplementary": self._count_dir("02_Parse/supplementary", True)},
            "03_assets": {
                "evidence": self._count_dir("03_Evidence", True),
                "figure_assets": self._count_files("03_Assets/figure_assets", "figures.json"),
                "table_assets": self._count_files("03_Assets/table_assets", "tables.json"),
                "supplementary_cards": self._count_files("03_Assets/supplementary_intelligence/cards", "*.json"),
                "supplementary_evidence": self._count_files("03_Assets/supplementary_intelligence/evidence", "*.json"),
                "dataset_cards": self._count_files("03_Assets/dataset_intelligence/dataset_cards", "*.json"),
                "ai_enrichment": {
                    "evidence_enrichment": self._count_files("03_Assets/ai/evidence_enrichment", "*.json"),
                    "gaps": self._count_files("03_Assets/ai/gaps", "*.json"),
                    "hypotheses": self._count_files("03_Assets/ai/hypotheses", "*.json"),
                    "summary_v2": self._count_files("03_Assets/ai/summary_v2", "*.json"),
                },
            },
            "05_knowledge": {
                "unified_graph_nodes": int((self.root / "05_Knowledge/unified_evidence_graph/graph_nodes.json").exists()),
                "unified_graph_edges": int((self.root / "05_Knowledge/unified_evidence_graph/graph_edges.json").exists()),
                "cross_paper_gaps": int((self.root / "05_Knowledge/cross_paper_gaps/gap_clusters.json").exists()),
                "cross_paper_hypotheses": int((self.root / "05_Knowledge/cross_paper_hypotheses/hypothesis_clusters.json").exists()),
                "dataset_entity_index": int((self.root / "05_Knowledge/dataset_intelligence/cross_paper_entity_index.json").exists()),
            },
            "06_index": {
                "lancedb_exists": int((self.root / "06_Index/vector/lancedb").exists()),
                "lancedb_tables": self._lancedb_tables(),
            },
            "07_agents": {
                "research_agent_traces": self._count_files("07_Agents/research_agent/traces", "*.json"),
            },
            "10_logs": self._count_files("10_System/logs", "*", True),
        }

    def _count_dir(self, rel: str, dirs: bool = False) -> int:
        p = self.root / rel
        if not p.exists(): return 0
        return sum(1 for _ in (p.iterdir() if not dirs else [d for d in p.iterdir() if d.is_dir()]))

    def _count_files(self, rel: str, pattern: str, dirs: bool = False) -> int:
        p = self.root / rel
        if not p.exists(): return 0
        if dirs: return sum(1 for d in p.iterdir() if d.is_dir())
        return len(list(p.glob(pattern)))

    def _lancedb_tables(self) -> list[str]:
        try:
            import lancedb
            db = lancedb.connect(str(self.root / "06_Index/vector/lancedb"))
            return db.table_names()
        except Exception:
            return []
