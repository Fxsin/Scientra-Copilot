from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


CHUNKER_VERSION = "0.1.0"


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    paper_id: str
    source: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    text_hash: str
    source_section: str | None = None


@dataclass(frozen=True)
class ChunkingConfig:
    chunk_size: int = 800
    chunk_overlap: int = 150
    min_chunk_size: int = 200

    @classmethod
    def from_mapping(cls, payload: dict[str, Any] | None) -> "ChunkingConfig":
        payload = payload or {}
        chunk_size = positive_int(payload.get("chunk_size"), 800)
        chunk_overlap = max(0, positive_int(payload.get("chunk_overlap"), 150))
        min_chunk_size = max(1, positive_int(payload.get("min_chunk_size"), 200))
        if chunk_overlap >= chunk_size:
            chunk_overlap = max(0, chunk_size // 5)
        return cls(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min(min_chunk_size, chunk_size),
        )


def chunk_text(
    text: str,
    paper_id: str,
    source: str = "raw_text",
    config: ChunkingConfig | None = None,
) -> list[TextChunk]:
    """Split text into deterministic overlapping chunks without writing files."""
    config = config or ChunkingConfig()
    normalized = normalize_text(text)
    if not normalized:
        return []

    spans = split_spans(
        normalized,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )
    spans = merge_small_tail(spans, min_chunk_size=config.min_chunk_size)

    chunks: list[TextChunk] = []
    for index, (start, end) in enumerate(spans, start=1):
        chunk_text_value = normalized[start:end].strip()
        if not chunk_text_value:
            continue
        text_hash = sha256_text(chunk_text_value)
        chunk_id = stable_chunk_id(
            paper_id=paper_id,
            source=source,
            chunk_index=index,
            text_hash=text_hash,
        )
        chunks.append(
            TextChunk(
                chunk_id=chunk_id,
                paper_id=paper_id,
                source=source,
                chunk_index=index,
                text=chunk_text_value,
                char_start=start,
                char_end=end,
                text_hash=text_hash,
                source_section=section_for_offset(normalized, start),
            )
        )
    return chunks


def split_spans(text: str, chunk_size: int, chunk_overlap: int) -> list[tuple[int, int]]:
    paragraphs = paragraph_spans(text)
    if not paragraphs:
        return []

    spans: list[tuple[int, int]] = []
    current_start: int | None = None
    current_end: int | None = None

    for para_start, para_end in paragraphs:
        para_len = para_end - para_start
        if para_len > chunk_size:
            if current_start is not None and current_end is not None:
                spans.append((current_start, current_end))
                current_start = None
                current_end = None
            spans.extend(window_spans(para_start, para_end, chunk_size, chunk_overlap))
            continue

        if current_start is None:
            current_start = para_start
            current_end = para_end
            continue

        assert current_end is not None
        if para_end - current_start <= chunk_size:
            current_end = para_end
            continue

        spans.append((current_start, current_end))
        overlap_start = max(current_start, current_end - chunk_overlap)
        current_start = min(overlap_start, para_start)
        current_end = para_end

    if current_start is not None and current_end is not None:
        spans.append((current_start, current_end))
    return normalize_spans(spans, len(text))


def paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, flags=re.DOTALL):
        spans.append((match.start(), match.end()))
    if spans:
        return spans
    stripped = text.strip()
    if not stripped:
        return []
    start = text.index(stripped)
    return [(start, start + len(stripped))]


def window_spans(start: int, end: int, chunk_size: int, chunk_overlap: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    step = max(1, chunk_size - chunk_overlap)
    cursor = start
    while cursor < end:
        window_end = min(end, cursor + chunk_size)
        spans.append((cursor, window_end))
        if window_end >= end:
            break
        cursor += step
    return spans


def merge_small_tail(
    spans: list[tuple[int, int]],
    min_chunk_size: int,
) -> list[tuple[int, int]]:
    if len(spans) <= 1:
        return spans
    last_start, last_end = spans[-1]
    if last_end - last_start >= min_chunk_size:
        return spans
    prev_start, _prev_end = spans[-2]
    return [*spans[:-2], (prev_start, last_end)]


def normalize_spans(spans: list[tuple[int, int]], text_len: int) -> list[tuple[int, int]]:
    normalized: list[tuple[int, int]] = []
    for start, end in spans:
        start = max(0, min(start, text_len))
        end = max(start, min(end, text_len))
        if end > start:
            normalized.append((start, end))
    return normalized


def stable_chunk_id(
    paper_id: str,
    source: str,
    chunk_index: int,
    text_hash: str,
) -> str:
    return f"{safe_id(paper_id)}:{safe_id(source)}:chunk_{chunk_index:04d}:{text_hash[:12]}"


def section_for_offset(text: str, offset: int) -> str | None:
    prefix = text[:offset]
    headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", prefix)
    if headings:
        return headings[-1].strip()
    return None


def normalize_text(text: str) -> str:
    text = (text or "").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._:-]+", "_", str(value)).strip("_")
    return safe or "unknown"


def positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
