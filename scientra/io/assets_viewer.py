"""Assets Viewer — read-only asset summary and search."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scientra.io.storage_layout import StorageLayout


class AssetsViewer:
    """Read-only access to generated assets across the v3 layout."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.storage = StorageLayout(root)
        self.storage.load()
        self.root = self.storage.root

    def get_summary(self) -> dict[str, Any]:
        """Return asset summary counts."""
        summary = {
            "papers_count": self._count_dir("01_Sources/papers"),
            "supplementary_files_count": self._count_files("01_Sources/supplementary"),
            "figure_assets_count": self._count_json_items("03_Assets/figure_assets"),
            "table_assets_count": self._count_json_items("03_Assets/table_assets"),
            "supplementary_assets_count": self._count_json_items("03_Assets/supplementary_assets/links"),
            "gene_evidence_count": self._count_json_items("04_Corpus/data/gene_evidence"),
            "entity_comparison_count": self._count_files("04_Corpus/data/cross_study"),
            "vector_tables": {},
            "vector_rows": 0,
            "lancedb_status": "unknown",
            "last_updated": None,
        }
        # LanceDB
        try:
            import lancedb
            ldb_path = self.root / "06_Index" / "vector" / "lancedb"
            if not ldb_path.exists():
                ldb_path = self.root / "04_VectorDB"
            db = lancedb.connect(str(ldb_path))
            tables = db.table_names()
            total_rows = 0
            tbl_info = {}
            for t in tables:
                try:
                    rc = len(db.open_table(t).to_pandas())
                    tbl_info[t] = rc
                    total_rows += rc
                except Exception:
                    tbl_info[t] = -1
            summary["vector_tables"] = tbl_info
            summary["vector_rows"] = total_rows
            summary["lancedb_status"] = "ok"
        except Exception:
            summary["lancedb_status"] = "unavailable"

        return summary

    def get_by_paper(self, paper_id: str) -> dict[str, Any]:
        """Return assets for a specific paper."""
        result = {
            "paper_id": paper_id,
            "source_manifest": self._load_json(f"01_Sources/papers/{paper_id}/source_manifest.json"),
            "supplementary_manifest": self._load_json(f"01_Sources/supplementary/{paper_id}/supplementary_manifest.json"),
            "figures": self._find_json(f"03_Assets/figure_assets/{paper_id}/figures.json"),
            "tables": self._find_json(f"03_Assets/table_assets/{paper_id}/tables.json"),
            "supplementary_files": self._find_json(f"03_Assets/supplementary_assets/links/{paper_id}/supplementary_links.json"),
            "gene_evidence_records": self._find_json(f"04_Corpus/data/gene_evidence/{paper_id}/supplementary_entities.json"),
            "entity_comparisons": [],
            "evidence_count": 0,
            "asset_chunk_count": 0,
        }
        return result

    def search(self, query: str = "", asset_type: str = "", paper_id: str = "", limit: int = 20) -> dict[str, Any]:
        """Search assets. Delegates to existing query endpoints where possible."""
        results: list[dict] = []
        if asset_type in ("gene_evidence", "supplementary_entity"):
            try:
                from scientra.pdf_data_assets.supplementary_entity_indexer import SupplementaryEntityIndexer
                idx = SupplementaryEntityIndexer(self.root)
                matches = idx.search_entities(query, top_k=limit)
                for m in matches:
                    m["asset_type"] = "gene_evidence"
                    results.append(m)
            except Exception:
                pass
        elif asset_type in ("entity_comparison",):
            try:
                from scientra.pdf_data_assets.supplementary_entity_comparator import SupplementaryEntityComparator
                comp = SupplementaryEntityComparator(self.root)
                r = comp.compare(query, top_k=limit)
                for rec in r.get("records", []):
                    rec["asset_type"] = "entity_comparison"
                    results.append(rec)
            except Exception:
                pass
        elif asset_type in ("table", "figure", "method", "result", "claim"):
            try:
                from scientra.sdk import query_assets
                r = query_assets(query, top_k=limit, chunk_types=[asset_type] if asset_type else None,
                                 paper_id=paper_id or None)
                for c in r.get("results", []):
                    c["asset_type"] = c.get("chunk_type", asset_type)
                    results.append(c)
            except Exception:
                pass
        elif query:
            try:
                from scientra.sdk import query_assets
                r = query_assets(query, top_k=limit, paper_id=paper_id or None)
                for c in r.get("results", []):
                    c["asset_type"] = c.get("chunk_type", "unknown")
                    results.append(c)
            except Exception:
                pass

        return {"query": query, "results": results[:limit], "total": len(results)}

    def _count_dir(self, rel: str) -> int:
        d = self.root / rel
        if not d.exists():
            return 0
        return len([x for x in d.iterdir() if x.is_dir()])

    def _count_files(self, rel: str) -> int:
        d = self.root / rel
        if not d.exists():
            return 0
        return len([x for x in d.rglob("*") if x.is_file()])

    def _count_json_items(self, rel: str) -> int:
        d = self.root / rel
        if not d.exists():
            return 0
        count = 0
        for f in d.rglob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    count += len(data)
                elif isinstance(data, dict) and "records" in data:
                    count += len(data["records"])
                elif isinstance(data, dict):
                    count += 1
            except Exception:
                pass
        return count

    def _load_json(self, rel: str) -> dict | list | None:
        p = self.root / rel
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _find_json(self, rel: str) -> list | None:
        p = self.root / rel
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
