"""Supplementary Intelligence Runner — orchestrator for the full pipeline.

Stages:
  1. Parse supplementary files (txt/md/docx/pdf/html)
  2. Detect sections
  3. Build contexts
  4. Extract evidence
  5. Create chunks
  6. Interpret (LLM or rule fallback)
  7. Check quality
  8. Build Supplementary Cards
  9. Write output files to 03_Assets/supplementary_intelligence/

Path principle: Uses Storage Layout v3 paths only. No DB/DB_v2.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Storage Layout v3 output root
V3_OUTPUT_ROOT = "03_Assets/supplementary_intelligence"
V3_PARSE_INTERMEDIATE = "02_Parse/supplementary"
V3_CORPUS = "04_Corpus/supplementary"
V3_LANCEDB = "06_Index/vector/lancedb"


class SupplementaryIntelligenceRunner:
    """Orchestrate the Supplementary Intelligence pipeline using Storage Layout v3."""

    def __init__(self, mode: str = "auto", root: str | Path | None = None,
                 max_chunk_size: int = 1200, chunk_overlap: int = 150,
                 embed: bool = False) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.mode = mode
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap
        self.embed = embed

    def run(self, paper_id: str, force: bool = False) -> dict[str, Any]:
        """Run the full Supplementary Intelligence pipeline."""
        out_dir = self._v3_path(V3_OUTPUT_ROOT)

        # Check existing output
        cards_path = out_dir / "cards" / f"{paper_id}.json"
        if not force and cards_path.exists():
            return self._load_existing_summary(paper_id, out_dir)

        # Step 1: Find supplementary assets
        from scientra.assets.asset_registry import load_registry, get_paper_dir
        registry = load_registry(paper_id)
        if not registry:
            return {"paper_id": paper_id, "success": False, "error": "No asset registry.", "supplementary_count": 0}

        assets = registry.assets if hasattr(registry, 'assets') else []
        supp_assets = [a for a in assets if a.get("asset_type") in ("supplementary_pdf", "attachment")]
        if not supp_assets:
            return {"paper_id": paper_id, "success": True, "supplementary_count": 0, "message": "No supplementary assets found."}

        paper_dir = get_paper_dir(paper_id)

        # Step 2: Parse each supplementary file
        from scientra.assets.supplementary_intelligence.supplementary_parser import parse_supplementary
        from scientra.assets.supplementary_intelligence.supplementary_sectioner import detect_sections
        from scientra.assets.supplementary_intelligence.supplementary_context_builder import SupplementaryContextBuilder
        from scientra.assets.supplementary_intelligence.supplementary_evidence_extractor import extract_evidence
        from scientra.assets.supplementary_intelligence.supplementary_chunker import chunk_supplementary
        from scientra.assets.supplementary_intelligence.supplementary_interpreter import SupplementaryInterpreter
        from scientra.assets.supplementary_intelligence.supplementary_quality_checker import SupplementaryQualityChecker
        from scientra.assets.supplementary_intelligence.supplementary_card_builder import SupplementaryCardBuilder

        parse_results: dict[str, dict] = {}
        all_sections: dict[str, list[dict]] = {}
        all_evidence: dict[str, list[dict]] = {}
        all_chunks: list[dict] = []

        ctx_builder = SupplementaryContextBuilder(self.root)
        contexts = ctx_builder.build_all(paper_id)
        ctx_map = {c.get("asset_id", ""): c for c in contexts}

        for a in supp_assets:
            asset_id = a.get("asset_id", "")
            rel_path = a.get("relative_path", "")
            file_path = str(paper_dir / rel_path) if rel_path else ""
            supp_id = f"supp_{asset_id}"

            # Parse
            pr = parse_supplementary(file_path, paper_id)
            pr["supplementary_id"] = supp_id
            pr["asset_id"] = asset_id
            pr["source_relative_path"] = rel_path
            parse_results[supp_id] = pr

            # Section
            sections = detect_sections(pr.get("raw_text", ""))
            for s in sections:
                s["paper_id"] = paper_id
                s["asset_id"] = asset_id
                s["section_id"] = f"{supp_id}_{s['section_id']}"
            all_sections[supp_id] = sections

            # Update context completeness
            ctx = ctx_map.get(asset_id, {})
            if ctx:
                ctx["context_completeness"]["has_sections"] = len(sections) > 0
                ctx["context_completeness"]["has_parseable_text"] = pr["parse_status"] == "parsed"

            # Evidence
            evidence = extract_evidence(sections, paper_id, asset_id)
            all_evidence[supp_id] = evidence

            if ctx:
                ctx["context_completeness"]["has_linked_evidence"] = len(evidence) > 0

            # Chunks
            chunks = chunk_supplementary(sections, evidence, paper_id, asset_id, rel_path,
                                         self.max_chunk_size, self.chunk_overlap)
            all_chunks.extend(chunks)

        # Interpret
        interpreter = SupplementaryInterpreter(mode=self.mode, root=self.root)
        interpretations = interpreter.interpret_all(list(ctx_map.values()), all_sections, all_evidence)
        effective_mode = interpretations[0].get("mode", "rule") if interpretations else "rule"

        # Quality
        checker = SupplementaryQualityChecker()
        q_reports = []
        for ctx in ctx_map.values():
            sid = ctx.get("supplementary_id", "")
            q_reports.append(checker.check(parse_results.get(sid, {}), all_sections.get(sid, []), {i.get("supplementary_id", ""): i for i in interpretations}.get(sid, {})))

        # Cards
        card_builder = SupplementaryCardBuilder()
        cards = []
        for ctx in ctx_map.values():
            sid = ctx.get("supplementary_id", "")
            im = {i.get("supplementary_id", ""): i for i in interpretations}
            qm = {q.get("supplementary_id", ""): q for q in q_reports}
            card = card_builder.build(ctx, parse_results.get(sid, {}), all_sections.get(sid, []), all_evidence.get(sid, []), im.get(sid, {}), qm.get(sid, {}))
            card["chunk_count"] = sum(1 for c in all_chunks if c.get("asset_id") == ctx.get("asset_id"))
            cards.append(card)

        # Write outputs to v3 paths
        self._write_v3_outputs(paper_id, out_dir, parse_results, all_sections, ctx_map, all_evidence, all_chunks, interpretations, cards, q_reports)

        # Optional embedding
        if self.embed:
            try:
                self._embed_chunks(all_chunks)
            except Exception as e:
                pass  # Embedding failure does not block main flow

        # Summary
        summary = {
            "paper_id": paper_id, "success": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "supplementary_count": len(supp_assets),
            "mode_used": effective_mode,
            "total_sections": sum(len(v) for v in all_sections.values()),
            "total_evidence": sum(len(v) for v in all_evidence.values()),
            "total_chunks": len(all_chunks),
            "embedded": self.embed,
        }
        self._write_summary_md(out_dir / "summaries" / f"{paper_id}.md", summary, cards)
        return summary

    # ── Read API ──

    def get_supplementaries(self, paper_id: str) -> dict[str, Any]:
        d = self._v3_path(V3_OUTPUT_ROOT)
        cp = d / "cards" / f"{paper_id}.json"
        if not cp.exists():
            return {"paper_id": paper_id, "available": False, "message": "Not yet built.", "supplementaries": []}
        try:
            cards = json.loads(cp.read_text(encoding="utf-8"))
            return {"paper_id": paper_id, "available": True, "supplementaries": cards, "summary": {"count": len(cards)}}
        except Exception:
            return {"paper_id": paper_id, "available": False, "message": "Error loading.", "supplementaries": []}

    def get_supplementary_card(self, paper_id: str, supp_id: str) -> dict[str, Any]:
        data = self.get_supplementaries(paper_id)
        if not data.get("available"):
            return {"available": False, "card": None}
        for c in data["supplementaries"]:
            if c.get("supplementary_id") == supp_id:
                return {"available": True, "card": c}
        return {"available": False, "card": None}

    def get_summary(self, paper_id: str) -> dict[str, Any]:
        d = self._v3_path(V3_OUTPUT_ROOT)
        cp = d / "cards" / f"{paper_id}.json"
        if not cp.exists():
            return {"paper_id": paper_id, "available": False, "count": 0}
        try:
            cards = json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            return {"paper_id": paper_id, "available": False, "count": 0}
        return {"paper_id": paper_id, "available": True, "count": len(cards), "parse_statuses": list(dict.fromkeys(c.get("parse_status", "?") for c in cards))}

    def get_evidence(self, paper_id: str) -> dict[str, Any]:
        d = self._v3_path(V3_OUTPUT_ROOT)
        ep = d / "evidence" / f"{paper_id}.json"
        if not ep.exists():
            return {"paper_id": paper_id, "available": False, "evidence": []}
        try:
            return {"paper_id": paper_id, "available": True, "evidence": json.loads(ep.read_text(encoding="utf-8"))}
        except Exception:
            return {"paper_id": paper_id, "available": False, "evidence": []}

    def get_chunks(self, paper_id: str) -> dict[str, Any]:
        d = self._v3_path(V3_OUTPUT_ROOT)
        cp = d / "chunks" / f"{paper_id}.json"
        if not cp.exists():
            return {"paper_id": paper_id, "available": False, "chunks": []}
        try:
            return {"paper_id": paper_id, "available": True, "chunks": json.loads(cp.read_text(encoding="utf-8"))}
        except Exception:
            return {"paper_id": paper_id, "available": False, "chunks": []}

    # ── Internal ──

    def _v3_path(self, rel: str) -> Path:
        return self.root / rel

    def _load_existing_summary(self, paper_id: str, d: Path) -> dict[str, Any]:
        s = self.get_summary(paper_id)
        return {"paper_id": paper_id, "success": True, "supplementary_count": s.get("count", 0), "mode_used": "cached"}

    def _write_v3_outputs(self, paper_id, out_dir, parse_results, all_sections, ctx_map, all_evidence, all_chunks, interpretations, cards, q_reports):
        for sub in ["parse_results", "sections", "contexts", "evidence", "chunks", "interpretations", "cards", "quality"]:
            (out_dir / sub).mkdir(parents=True, exist_ok=True)
        self._wj(out_dir / "parse_results" / f"{paper_id}.json", list(parse_results.values()))
        self._wj(out_dir / "sections" / f"{paper_id}.json", {k: v for k, v in all_sections.items()})
        self._wj(out_dir / "contexts" / f"{paper_id}.json", list(ctx_map.values()))
        self._wj(out_dir / "evidence" / f"{paper_id}.json", {k: v for k, v in all_evidence.items()})
        self._wj(out_dir / "chunks" / f"{paper_id}.json", all_chunks)
        self._wj(out_dir / "interpretations" / f"{paper_id}.json", interpretations)
        self._wj(out_dir / "cards" / f"{paper_id}.json", cards)
        self._wj(out_dir / "quality" / f"{paper_id}.json", q_reports)

    @staticmethod
    def _wj(p: Path, d: Any) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    def _embed_chunks(self, chunks: list[dict]) -> None:
        """Write chunks to LanceDB for vector search."""
        try:
            import lancedb
            db_path = self._v3_path(V3_LANCEDB)
            db = lancedb.connect(str(db_path))

            data = [{
                "chunk_id": c.get("chunk_id", ""),
                "paper_id": c.get("paper_id", ""),
                "asset_id": c.get("asset_id", ""),
                "section_id": c.get("section_id", ""),
                "evidence_id": c.get("evidence_id", ""),
                "chunk_type": c.get("chunk_type", ""),
                "text": c.get("text", ""),
                "source_file": c.get("source_file", ""),
                "source_relative_path": c.get("source_relative_path", ""),
                "vector": _compute_embedding(c.get("text", "")),
            } for c in chunks if c.get("text")]

            if not data:
                return

            try:
                table = db.open_table("supplementary_chunks")
                table.add(data)
            except Exception:
                db.create_table("supplementary_chunks", data)
        except Exception:
            pass  # Embedding failure does not block

    @staticmethod
    def _write_summary_md(path: Path, summary: dict, cards: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Supplementary Intelligence Summary — {summary['paper_id']}",
            f"Generated: {summary.get('generated_at', 'N/A')}",
            f"Mode: {summary.get('mode_used', 'unknown')}",
            f"Supplementary files: {summary.get('supplementary_count', 0)}",
            f"Total sections: {summary.get('total_sections', 0)}",
            f"Total evidence: {summary.get('total_evidence', 0)}",
            f"Total chunks: {summary.get('total_chunks', 0)}",
            f"Embedded: {summary.get('embedded', False)}",
            "", "## Cards", "",
            "| Label | File Type | Parse | Sections | Evidence | Quality |",
            "|-------|-----------|-------|----------|----------|---------|",
        ]
        for c in cards:
            lines.append(f"| {c.get('label', '?')} | {c.get('file_type', '?')} | {c.get('parse_status', '?')} | {c.get('section_count', 0)} | {c.get('evidence_count', 0)} | {c.get('quality_score', 0):.2f} |")
        path.write_text("\n".join(lines), encoding="utf-8")


def _compute_embedding(text: str) -> list[float] | None:
    """Compute BGE-M3 embedding. Returns None if unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3")
        return model.encode(text[:8192]).tolist()
    except Exception:
        return None
