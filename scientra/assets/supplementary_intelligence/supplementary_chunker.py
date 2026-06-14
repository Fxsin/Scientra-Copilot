"""Supplementary Chunker — cut supplementary sections/evidence into retrievable chunks.

Chunk types: supplementary_section_chunk, supplementary_evidence_chunk,
supplementary_method_chunk, supplementary_result_chunk, supplementary_dataset_chunk
"""

from __future__ import annotations

import uuid
from typing import Any


def chunk_supplementary(
    sections: list[dict[str, Any]],
    evidence_list: list[dict[str, Any]],
    paper_id: str = "",
    asset_id: str = "",
    source_relative_path: str = "",
    max_chunk_size: int = 1200,
    chunk_overlap: int = 150,
) -> list[dict[str, Any]]:
    """Create chunks from supplementary sections and evidence.

    Args:
        sections: Section dicts.
        evidence_list: Evidence dicts.
        paper_id: Paper ID.
        asset_id: Asset ID.
        source_relative_path: Relative path to source file.
        max_chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of chunk dicts.
    """
    chunks: list[dict[str, Any]] = []
    ev_by_section: dict[str, list[dict]] = {}
    for ev in evidence_list:
        sid = ev.get("section_id", "")
        ev_by_section.setdefault(sid, []).append(ev)

    for section in sections:
        section_id = section.get("section_id", "")
        section_type = section.get("section_type", "unknown")
        text = section.get("text", "")
        section_evidence = ev_by_section.get(section_id, [])

        # Chunk the section text
        if text:
            section_chunks = _sliding_window(text, max_chunk_size, chunk_overlap)
            for i, chunk_text in enumerate(section_chunks):
                cid = f"chk_{uuid.uuid4().hex[:10]}"
                chunks.append({
                    "chunk_id": cid,
                    "paper_id": paper_id,
                    "asset_id": asset_id,
                    "section_id": section_id,
                    "evidence_id": None,
                    "chunk_type": f"supplementary_{section_type}_chunk",
                    "text": chunk_text,
                    "source_file": source_relative_path,
                    "source_relative_path": source_relative_path,
                    "metadata": {
                        "section_type": section_type,
                        "chunk_index": i,
                        "total_section_chunks": len(section_chunks),
                    },
                })

        # Create one chunk per evidence item (if large enough)
        for ev in section_evidence:
            ev_text = ev.get("text", "")
            if len(ev_text) < 50:
                continue
            ev_type = ev.get("evidence_type", "unknown")

            # Map to chunk type
            chunk_type_map = {
                "method_detail": "supplementary_method_chunk",
                "result_detail": "supplementary_result_chunk",
                "dataset_description": "supplementary_dataset_chunk",
                "protocol_detail": "supplementary_method_chunk",
            }
            chunk_type = chunk_type_map.get(ev_type, "supplementary_evidence_chunk")

            cid = f"chk_{uuid.uuid4().hex[:10]}"
            chunks.append({
                "chunk_id": cid,
                "paper_id": paper_id,
                "asset_id": asset_id,
                "section_id": section_id,
                "evidence_id": ev.get("evidence_id", ""),
                "chunk_type": chunk_type,
                "text": ev_text[:max_chunk_size * 2],
                "source_file": source_relative_path,
                "source_relative_path": source_relative_path,
                "metadata": {
                    "evidence_type": ev_type,
                    "section_type": section_type,
                },
            })

    return chunks


def _sliding_window(text: str, max_size: int, overlap: int) -> list[str]:
    """Split text using sliding window with overlap."""
    if len(text) <= max_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_size, len(text))
        chunks.append(text[start:end])
        start += max_size - overlap

    return chunks
