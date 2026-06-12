"""
Chunk Quality Checker — validates agent_chunks.jsonl and scores readiness.

Phase 0.5B update:
  - linked_evidence_id is no longer a hard error; only deducts for method/result/claim chunks.
  - vector_ready logic: text non-empty + paper_id + chunk_type + source_asset_ids non-empty
    + source_text/text traceable. Missing linked_evidence_id is acceptable.
  - Adds quality note "missing_linked_evidence_id" when applicable.

Checks:
  1. chunk has non-empty text
  2. text length is reasonable (30-2000 chars)
  3. has source_asset_ids
  4. has paper_id
  5. has chunk_type
  6. citation_ready flag
  7. entity noise level
  8. linked_evidence_id traceability (soft check)
  9. vector_ready determination

Adds fields: vector_ready, quality_score (0-100), quality_notes

Output: 06_PDF_DataAssets/09_agent_chunks/{paper_id}/agent_chunks.quality.jsonl
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Common stopwords for entity noise detection ──
ENTITY_STOPWORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall", "this",
    "that", "these", "those", "it", "its", "they", "them", "their",
    "we", "us", "our", "you", "your", "he", "she", "his", "her",
    "not", "no", "nor", "so", "if", "then", "than", "too", "very",
    "also", "only", "now", "here", "there", "when", "where", "which",
    "who", "how", "well", "one", "two", "three", "first", "last",
    "using", "used", "against", "into", "other", "some", "such", "each",
    "more", "most", "all", "any", "both", "few", "same",
    "does", "even", "less", "much", "still", "since", "without",
    "within", "along", "among", "between",
    "have", "had", "been", "were", "being",
    "produced", "produce", "shown", "showed", "found",
    "based", "known", "reported", "identified",
    "including", "respectively", "addition",
    "lack", "wide", "diverse",
    "insect", "insects", "protein", "proteins", "gene", "genes",
    "activity", "cell", "cells", "species",
    "crystal", "form", "formation", "class",
    "order", "number", "sequence", "family",
    "similar", "different", "various",
    "high", "low", "large", "small",
    "natural", "location", "locations",
    "mode", "action", "host", "range",
    "phase", "growth", "medium",
    "bacterium", "bacterial", "gram", "positive",
}

# Chunk types that should have evidence traceability
EVIDENCE_TRACEABLE_TYPES = {"method", "result", "claim"}


class ChunkQualityChecker:
    """Validates agent chunks and assigns vector_ready + quality_score."""

    MIN_TEXT_LENGTH = 30
    MAX_TEXT_LENGTH = 2000

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.chunks_dir = self.root / "06_PDF_DataAssets" / "09_agent_chunks"

    def check_paper(self, paper_id: str) -> dict[str, Any]:
        """Check all chunks for a paper. Returns summary + writes .quality.jsonl."""
        source_path = self.chunks_dir / paper_id / "agent_chunks.jsonl"
        if not source_path.exists():
            return {"paper_id": paper_id, "status": "no_source", "total": 0, "vector_ready": 0, "scores": []}

        chunks: list[dict[str, Any]] = []
        try:
            for line in source_path.read_text(encoding="utf-8").strip().splitlines():
                if line.strip():
                    chunks.append(json.loads(line))
        except Exception as e:
            return {"paper_id": paper_id, "status": "parse_error", "error": str(e), "total": 0, "vector_ready": 0}

        total = len(chunks)
        checked: list[dict[str, Any]] = []
        vector_ready_count = 0
        scores: list[int] = []
        all_notes: list[str] = []

        for chunk in chunks:
            score = 100
            notes: list[str] = []

            ctype = str(chunk.get("chunk_type", ""))

            # Check 1: text non-empty
            text = str(chunk.get("text", "")).strip()
            if not text:
                score -= 30
                notes.append("empty_text")

            # Check 2: text length
            text_len = len(text)
            if text_len < self.MIN_TEXT_LENGTH:
                score -= 20
                notes.append(f"text_too_short ({text_len} chars)")
            elif text_len > self.MAX_TEXT_LENGTH:
                notes.append(f"text_long ({text_len} chars)")

            # Check 3: source_asset_ids
            src_ids = chunk.get("source_asset_ids", [])
            if not src_ids or len(src_ids) == 0:
                score -= 15
                notes.append("missing_source_asset_ids")

            # Check 4: paper_id
            if not chunk.get("paper_id"):
                score -= 20
                notes.append("missing_paper_id")

            # Check 5: chunk_type
            if not ctype or ctype == "unknown":
                score -= 10
                notes.append("unknown_chunk_type")

            # Check 6: citation_ready
            if not chunk.get("citation_ready", False):
                score -= 10
                notes.append("not_citation_ready")

            # Check 7: entity noise
            entities = chunk.get("entities", [])
            if isinstance(entities, list):
                noise_count = sum(1 for e in entities if str(e).lower() in ENTITY_STOPWORDS)
                if noise_count > len(entities) * 0.5:
                    score -= 15
                    notes.append(f"high_entity_noise ({noise_count}/{len(entities)} stopwords)")

            # Check 8: source_section traceability
            source_section = chunk.get("source_section", "unknown")
            if source_section == "unknown":
                score -= 5
                notes.append("unknown_source_section")

            # Check 9: linked_evidence_id (soft check — Phase 0.5B)
            linked_ev_id = chunk.get("linked_evidence_id")
            linked_ev_ids = chunk.get("linked_evidence_ids", [])
            has_ev_trace = bool(linked_ev_id) or (isinstance(linked_ev_ids, list) and len(linked_ev_ids) > 0)

            if not has_ev_trace:
                if ctype in EVIDENCE_TRACEABLE_TYPES:
                    # Soft penalty: deduct points but don't block vector_ready
                    score -= 10
                notes.append("missing_linked_evidence_id")

            # ── Vector-ready determination (Phase 0.5B updated) ──
            has_text = text_len >= self.MIN_TEXT_LENGTH
            has_paper_id = bool(chunk.get("paper_id"))
            has_type = bool(ctype and ctype != "unknown")
            has_source = bool(src_ids and len(src_ids) > 0)
            has_source_text = bool(chunk.get("source_section", "unknown") != "unknown" or text_len >= self.MIN_TEXT_LENGTH)

            vector_ready = all([has_text, has_paper_id, has_type, has_source, has_source_text])

            if vector_ready:
                vector_ready_count += 1
            else:
                missing = []
                if not has_text:
                    missing.append("text")
                if not has_paper_id:
                    missing.append("paper_id")
                if not has_type:
                    missing.append("chunk_type")
                if not has_source:
                    missing.append("source_asset_ids")
                if not has_source_text:
                    missing.append("source_traceability")
                notes.append(f"not_vector_ready: missing [{', '.join(missing)}]")

            chunk["quality_score"] = max(0, score)
            chunk["vector_ready"] = vector_ready
            chunk["quality_notes"] = notes
            chunk["quality_checked_at"] = datetime.now(timezone.utc).isoformat()

            checked.append(chunk)
            scores.append(max(0, score))
            all_notes.extend(notes)

        # Write quality output
        output_path = self.chunks_dir / paper_id / "agent_chunks.quality.jsonl"
        tmp = output_path.with_suffix(".tmp")
        lines = [json.dumps(c, ensure_ascii=False) for c in checked]
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(output_path)

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        # Note frequency
        from collections import Counter
        note_counts = dict(Counter(all_notes).most_common(10))

        return {
            "paper_id": paper_id,
            "status": "success",
            "total": total,
            "vector_ready": vector_ready_count,
            "vector_ready_pct": round(vector_ready_count / total * 100, 1) if total > 0 else 0,
            "average_quality_score": avg_score,
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "top_quality_notes": note_counts,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_summary(self, paper_id: str) -> dict[str, Any]:
        """Get quality summary, computing if needed."""
        quality_path = self.chunks_dir / paper_id / "agent_chunks.quality.jsonl"
        if quality_path.exists():
            try:
                chunks: list[dict] = []
                for line in quality_path.read_text(encoding="utf-8").strip().splitlines():
                    if line.strip():
                        chunks.append(json.loads(line))
                total = len(chunks)
                vr = sum(1 for c in chunks if c.get("vector_ready", False))
                scores = [c.get("quality_score", 0) for c in chunks]
                return {
                    "paper_id": paper_id,
                    "total": total,
                    "vector_ready": vr,
                    "vector_ready_pct": round(vr / total * 100, 1) if total > 0 else 0,
                    "average_quality_score": round(sum(scores) / len(scores), 1) if scores else 0,
                }
            except Exception:
                pass
        return self.check_paper(paper_id)
