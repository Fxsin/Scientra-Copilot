"""Vector Retriever — semantic search via LanceDB/BGE-M3."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class VectorRetriever:
    """Semantic search using LanceDB vector index."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.warnings: list[str] = []
        self._available = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                import lancedb
                db_path = self.root / "06_Index/vector/lancedb"
                if db_path.exists():
                    db = lancedb.connect(str(db_path))
                    tables = db.table_names()
                    self._available = len(tables) > 0
                else:
                    self._available = False
            except Exception:
                self._available = False
        return self._available

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """Semantic search across LanceDB tables.

        Returns list of scored hit dicts.
        """
        if not self.is_available():
            self.warnings.append("LanceDB not available — vector search skipped.")
            return []

        try:
            vector = self._embed(query)
            if vector is None:
                self.warnings.append("Embedding failed — vector search skipped.")
                return []
        except Exception:
            self.warnings.append("Embedding model unavailable.")
            return []

        hits: list[dict] = []
        try:
            import lancedb
            db = lancedb.connect(str(self.root / "06_Index/vector/lancedb"))

            for table_name in ["evidence_chunks", "pdf_asset_chunks"]:
                try:
                    table = db.open_table(table_name)
                    results = table.search(vector).limit(top_k).to_list()
                    for r in results:
                        hits.append({
                            "hit_id": f"vec_{table_name}_{r.get('chunk_id', '')[:20]}",
                            "asset_type": "evidence",
                            "paper_id": r.get("paper_id", ""),
                            "asset_id": r.get("chunk_id", ""),
                            "title": str(r.get("text", ""))[:100],
                            "text": str(r.get("text", ""))[:500],
                            "matched_fields": ["vector_semantic"],
                            "source_module": "vector_retriever",
                            "source_relative_path": f"06_Index/vector/lancedb/{table_name}",
                            "score": round(float(r.get("_distance", 1.0)), 3),
                            "score_breakdown": {"vector_score": round(float(r.get("_distance", 1.0)), 3)},
                            "confidence": float(r.get("confidence", 0.5)) if isinstance(r.get("confidence"), (int, float)) else 0.5,
                            "provenance": {"source_module": "vector_retriever", "created_by": "embedding"},
                        })
                except Exception:
                    pass
        except Exception as e:
            self.warnings.append(f"Vector search error: {e}")

        return hits[:top_k]

    def _embed(self, text: str) -> list[float] | None:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("BAAI/bge-m3")
            return model.encode(text[:8192]).tolist()
        except Exception:
            return None
