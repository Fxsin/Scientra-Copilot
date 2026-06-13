"""
Table Structure Extractor — simple text-based table structure parsing.

Phase 2B: Extracts simple table structures from raw text sources.
No OCR. No LLM. No PDF layout parsing.
Only handles whitespace-aligned, tab-delimited, and markdown-like tables.

Complex tables (multi-level headers, merged cells, irregular columns) are
marked as complex_structure_skipped rather than forced.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


# ── Complexity classification thresholds ──

MAX_TABLE_ROWS = 100          # More rows than this → complex
MAX_CELL_CHARS = 200          # Longer cell text → likely not a table cell
MAX_COLUMN_COUNT = 30         # More columns → likely not a simple table
MIN_CONSISTENT_LINES = 2      # Need at least this many lines with same col count
MIN_COLUMNS = 2               # Minimum columns for a table
HEADER_KEYWORD_RATIO = 0.3    # Ratio of header-like words needed to confirm header row


class TableStructureExtractor:
    """Extracts simple table structures from raw text."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.raw_text_dir = self.root / "03_Summary" / "raw_text"

    # ── Public API ──

    def extract_structure(
        self, paper_id: str, table_number: str, caption: str
    ) -> dict[str, Any]:
        """Attempt to extract simple table structure for a given table.

        Returns dict with:
            structure_status, structured_columns, structured_rows,
            raw_table_text, structure_confidence, structure_extraction_method,
            structure_notes
        """
        text = self._load_raw_text(paper_id)
        if not text:
            return self._unavailable_result("no_raw_text")

        # Locate the table body near the caption
        table_body = self._find_table_body(text, table_number, caption)
        if table_body is None:
            return self._unavailable_result("no_table_body_found")

        # Classify complexity
        complexity = self.classify_complexity(table_body)
        if complexity == "unavailable":
            return self._unavailable_result("table_body_empty_or_minimal")
        if complexity == "complex":
            return self._complex_result(
                "table_structure_too_complex",
                ["Structure classified as complex: irregular or multi-level patterns"]
            )

        # Try parsing strategies in order
        result = self._try_parse(table_body)
        if result:
            return result

        return self._complex_result(
            "parse_failed",
            ["All parsing strategies failed to produce viable results"]
        )

    def classify_complexity(self, table_body: str) -> str:
        """Classify a raw text block as simple, complex, or unavailable.

        Returns: 'simple' | 'complex' | 'unavailable'
        """
        # Clean input
        body = table_body.strip()
        if not body or len(body) < 20:
            return "unavailable"

        lines = [l.strip() for l in body.splitlines() if l.strip()]
        if len(lines) < MIN_CONSISTENT_LINES:
            return "unavailable"

        # Check for markdown-like table (| col | col |)
        md_pipe_lines = sum(1 for l in lines if l.startswith("|") and "|" in l[1:])
        if md_pipe_lines >= 2:
            return "simple"

        # Analyze whitespace patterns
        col_counts = []
        for line in lines:
            # Try splitting by 2+ spaces (whitespace-aligned)
            cols = re.split(r'\s{2,}', line)
            cols = [c.strip() for c in cols if c.strip()]
            if len(cols) >= MIN_COLUMNS:
                col_counts.append(len(cols))

        if len(col_counts) >= MIN_CONSISTENT_LINES:
            # Check consistency of column counts
            counter = Counter(col_counts)
            most_common_count, most_common_freq = counter.most_common(1)[0]
            consistency = most_common_freq / len(col_counts)

            if consistency >= 0.6 and most_common_count >= MIN_COLUMNS:
                if most_common_count > MAX_COLUMN_COUNT:
                    return "complex"
                if len(lines) > MAX_TABLE_ROWS:
                    return "complex"
                return "simple"

        # Check for tab-delimited
        tab_lines = [l for l in lines if '\t' in l]
        if len(tab_lines) >= MIN_CONSISTENT_LINES:
            tab_counts = [len(l.split('\t')) for l in tab_lines]
            tc = Counter(tab_counts)
            most_common_tc, _ = tc.most_common(1)[0]
            if most_common_tc >= MIN_COLUMNS:
                return "simple"

        # Check for numeric/data-heavy lines (likely table data but poorly delimited)
        numeric_ratio = self._numeric_line_ratio(lines)
        if numeric_ratio > 0.3 and len(lines) >= 3:
            return "complex"  # data-heavy but can't parse cleanly

        return "complex"

    # ── Parsing strategies ──

    def _try_parse(self, table_body: str) -> dict[str, Any] | None:
        """Try parsing strategies in order. Returns first successful result."""
        strategies = [
            ("markdown_like", self._parse_markdown_like),
            ("tab_delimited", self._parse_tab_delimited),
            ("whitespace_aligned", self._parse_whitespace_aligned),
            ("whitespace_flat", self._parse_whitespace_flat),
        ]

        for method_name, parser in strategies:
            try:
                result = parser(table_body)
                if result and result.get("columns") and result.get("rows"):
                    cols = result["columns"]
                    rows = result["rows"]
                    if len(cols) >= MIN_COLUMNS and len(rows) >= 1:
                        conf = self._assess_confidence(cols, rows, method_name)
                        return {
                            "structure_status": "simple_structure_extracted",
                            "structured_columns": cols,
                            "structured_rows": rows,
                            "raw_table_text": table_body[:5000],
                            "structure_confidence": conf,
                            "structure_extraction_method": method_name,
                            "structure_notes": [
                                f"Parsed as {method_name}",
                                f"columns={len(cols)}, rows={len(rows)}"
                            ],
                        }
            except Exception:
                continue

        return None

    def _parse_markdown_like(self, body: str) -> dict[str, Any] | None:
        """Parse markdown-like pipe tables: | col1 | col2 | ... |"""
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        pipe_lines = [l for l in lines if l.startswith("|") and "|" in l[1:]]
        if len(pipe_lines) < 2:
            return None

        # Separate header from data, skip separator lines like |---|---|
        data_lines = []
        header_line = None
        for l in pipe_lines:
            cells = [c.strip() for c in l.split("|")[1:-1]]
            # Skip separator rows (|---|---|)
            if all(re.match(r'^[-:]+$', c) for c in cells if c):
                continue
            if header_line is None:
                header_line = cells
            else:
                data_lines.append(cells)

        if not header_line or not data_lines:
            return None

        # Build structured rows
        all_rows = []
        for cells in data_lines:
            if len(cells) == 0:
                continue
            row: dict[str, str] = {}
            for i, cell in enumerate(cells):
                col_name = header_line[i] if i < len(header_line) else f"col_{i}"
                row[col_name] = cell
            all_rows.append(row)

        return {"columns": header_line, "rows": all_rows}

    def _parse_tab_delimited(self, body: str) -> dict[str, Any] | None:
        """Parse tab-delimited table data."""
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        tab_lines = [l for l in lines if '\t' in l]
        if len(tab_lines) < 2:
            return None

        # Use first line as header, rest as data
        header = [c.strip() for c in tab_lines[0].split('\t')]
        if len(header) < MIN_COLUMNS:
            return None

        rows = []
        for line in tab_lines[1:]:
            cells = [c.strip() for c in line.split('\t')]
            row: dict[str, str] = {}
            for i, cell in enumerate(cells):
                col_name = header[i] if i < len(header) else f"col_{i}"
                row[col_name] = cell
            rows.append(row)

        return {"columns": header, "rows": rows}

    def _parse_whitespace_aligned(self, body: str) -> dict[str, Any] | None:
        """Parse whitespace-aligned table (columns separated by 2+ spaces)."""
        lines = [l for l in body.splitlines() if l.strip()]
        if len(lines) < 2:
            return None

        # Split each line by 2+ whitespace
        split_lines = []
        for line in lines:
            cols = re.split(r'\s{2,}', line.strip())
            cols = [c.strip() for c in cols if c.strip()]
            if len(cols) >= MIN_COLUMNS:
                split_lines.append(cols)

        if len(split_lines) < 2:
            return None

        # Find most common column count
        col_counts = Counter(len(c) for c in split_lines)
        common_count, _ = col_counts.most_common(1)[0]

        # Keep only lines with the common column count
        consistent_lines = [l for l in split_lines if len(l) == common_count]
        if len(consistent_lines) < 2:
            return None

        # Detect header: first line that has a high ratio of alphabetical content
        header_idx = self._detect_header_row(consistent_lines)
        if header_idx is None:
            header_idx = 0  # Use first line as header by default

        # Build header from the header row
        header = consistent_lines[header_idx]

        # Build data rows
        all_rows = []
        for i, cells in enumerate(consistent_lines):
            if i == header_idx:
                continue
            row: dict[str, str] = {}
            for j, cell in enumerate(cells):
                col_name = header[j] if j < len(header) else f"col_{j}"
                row[col_name] = cell
            all_rows.append(row)

        return {"columns": header, "rows": all_rows}

    def _parse_whitespace_flat(self, body: str) -> dict[str, Any] | None:
        """Parse inline/flattened table data (GROBID common case).

        In GROBID output, multi-row tables often appear as one or a few
        very long lines where columns are separated by consistent 2+ space
        gaps but rows are concatenated (no newline between rows).

        Strategy: detect repeating column patterns within lines, then
        chunk items into N-column rows.
        """
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        if not lines:
            return None

        all_cells: list[str] = []
        gap_sizes: list[int] = []

        # Split each line by 2+ whitespace and collect cells + gap sizes
        for line in lines:
            # Find all whitespace gaps
            gaps = [(m.start(), m.end()) for m in re.finditer(r'\s{2,}', line)]
            if len(gaps) < 2:
                continue

            cells = re.split(r'\s{2,}', line)
            cells = [c.strip() for c in cells if c.strip()]
            if len(cells) < 3:
                continue
            all_cells.extend(cells)

            for g in gaps:
                gap_sizes.append(g[1] - g[0])

        if len(all_cells) < 6:  # Need at least header + 1 row with 3 cols
            return None

        # Try to detect column count by looking for repeating patterns
        # Count the frequency of different column splits
        best_cols = 0
        best_score = 0.0

        for n_cols in range(2, min(15, len(all_cells) // 2 + 1)):
            if len(all_cells) % n_cols != 0 and len(all_cells) % n_cols < n_cols - 2:
                continue  # Must divide reasonably evenly

            # Check if first row (header) in first n_cols items looks header-like
            header_cells = all_cells[:n_cols]
            alpha_count = sum(1 for c in header_cells if re.search(r'[A-Za-z]', c))
            header_score = alpha_count / n_cols

            # Check if subsequent "rows" follow similar patterns
            rows = len(all_cells) // n_cols - 1  # minus header
            if rows < 1:
                continue

            # Score: prefer reasonable column count with good header
            if 3 <= n_cols <= 12 and header_score >= 0.3 and rows >= 1:
                score = header_score + min(rows * 0.1, 0.5)
                if score > best_score:
                    best_score = score
                    best_cols = n_cols

        if best_cols < 2:
            return None

        # Build header and rows
        n_cols = best_cols
        header = all_cells[:n_cols]
        data_cells = all_cells[n_cols:]

        # Truncate to complete rows
        full_rows = len(data_cells) // n_cols
        if full_rows < 1:
            return None

        all_rows_data = []
        for r in range(full_rows):
            row_cells = data_cells[r * n_cols:(r + 1) * n_cols]
            row: dict[str, str] = {}
            for j, cell in enumerate(row_cells):
                col_name = header[j] if j < len(header) else f"col_{j}"
                row[col_name] = cell
            all_rows_data.append(row)

        # Cap rows
        all_rows_data = all_rows_data[:MAX_TABLE_ROWS]

        return {"columns": header, "rows": all_rows_data}

    # ── Helpers ──

    def _find_table_body(
        self, text: str, table_number: str, caption: str
    ) -> str | None:
        """Locate the table body text after a table caption in raw text.

        Strategy: find the caption location, then scan ahead for the first
        contiguous block of lines with consistent delimiter structure (the
        actual table data), skipping intervening natural language paragraphs.
        """
        # Build search patterns for the table label
        patterns = [
            rf'(?:Supplementary\s+)?Table\s+{re.escape(table_number)}\s*[.:]',
            rf'(?:Supplementary\s+)?TABLE\s+{re.escape(table_number)}\s*[.:]',
        ]

        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if not m:
                continue

            # Extract a large chunk after the caption to search for table data
            search_start = m.end()
            search_end = min(len(text), search_start + 8000)

            # Define end markers to bound our search
            end_markers_compact = [
                r'\n\s*\n\s*(?:REFERENCES|ACKNOWLEDGMENTS)\b',
                r'\n\s*(?:Table\s+\d+|TABLE\s+\d+|Figure\s+\d+|Fig\.?\s+\d+)\.',
            ]
            for marker in end_markers_compact:
                em = re.search(marker, text[search_start:search_end], re.IGNORECASE)
                if em:
                    search_end = min(search_end, search_start + em.start())

            chunk = text[search_start:search_end]

            # Try to find the contiguous table data block within the chunk
            table_block = self._extract_table_block(chunk, caption)
            if table_block and len(table_block) >= 30:
                return table_block[:10000]

            # Fallback: return the cleaned chunk (removing caption prefix)
            fallback = self._remove_caption_prefix(chunk, caption)
            if fallback and len(fallback) >= 30:
                return fallback[:8000]

            break

        return None

    def _extract_table_block(self, chunk: str, caption: str) -> str | None:
        """Extract the contiguous table data block from a mixed text chunk.

        Scans lines for the first block of 3+ consecutive lines with
        consistent delimiter patterns (whitespace, tabs, or pipes).
        """
        lines = chunk.splitlines()
        if len(lines) < 3:
            return None

        # Score each line for "table-likeness"
        scored_lines: list[tuple[int, float]] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                scored_lines.append((i, -1.0))
                continue
            score = self._table_line_score(stripped)
            scored_lines.append((i, score))

        # Find the longest consecutive block with score >= threshold
        best_start = -1
        best_len = 0
        current_start = -1
        current_len = 0
        threshold = 0.3

        for i, (idx, score) in enumerate(scored_lines):
            if score >= threshold:
                if current_start < 0:
                    current_start = i
                current_len += 1
            else:
                if current_len >= 3 and current_len > best_len:
                    best_start = current_start
                    best_len = current_len
                current_start = -1
                current_len = 0

        # Check last block
        if current_len >= 3 and current_len > best_len:
            best_start = current_start
            best_len = current_len

        if best_start >= 0 and best_len >= 3:
            block_lines = lines[best_start:best_start + best_len]
            return "\n".join(block_lines)

        return None

    def _table_line_score(self, line: str) -> float:
        """Score a line for table-likeness (0.0 to 1.0).

        High scores for: consistent whitespace gaps, numeric content,
        pipe delimiters, tab delimiters, multiple distinct columns.
        """
        score = 0.0

        # Pipe delimiter
        if line.startswith("|") and "|" in line[1:]:
            return 0.9

        # Tab delimiter
        if '\t' in line:
            cols = line.split('\t')
            if len(cols) >= 2:
                return 0.8

        # Whitespace gap analysis
        gaps = [len(g) for g in re.findall(r'\s{2,}', line)]
        if len(gaps) >= 2:
            # Consistent gap sizes → high score
            if len(set(gaps)) <= len(gaps) * 0.5:
                score += 0.4
            else:
                score += 0.2
            score += min(len(gaps) * 0.1, 0.3)

        # Split by 2+ spaces and check column count
        cols = re.split(r'\s{2,}', line.strip())
        cols = [c for c in cols if c.strip()]
        if len(cols) >= 3:
            score += 0.3
        elif len(cols) >= 2:
            score += 0.2

        # Numeric content ratio
        clean = re.sub(r'\s', '', line)
        if clean:
            digits = sum(1 for c in clean if c.isdigit() or c in '.-+±()')
            ratio = digits / len(clean)
            if ratio > 0.3:
                score += 0.2
            if ratio > 0.5:
                score += 0.1

        # Check if it looks like natural language (long runs of alpha chars)
        alpha_runs = re.findall(r'[A-Za-z]{8,}', line)
        if len(alpha_runs) > 3:
            score -= 0.3  # Likely natural language

        # Check for table keywords in header position
        header_indicators = [
            r'\b(table|supplementary|appendix|mean|sd|se|n\b|p\b|value|total)\b',
        ]
        for hi in header_indicators:
            if re.search(hi, line, re.IGNORECASE):
                score += 0.1
                break

        return max(0.0, min(1.0, score))

    def _remove_caption_prefix(self, body: str, caption: str) -> str:
        """Remove the caption text prefix from table body if present."""
        if not caption:
            return body
        # The body might start with the caption text (no newline separation)
        caption_clean = re.sub(r'\s+', ' ', caption.strip()).lower()
        body_start = re.sub(r'\s+', ' ', body[:len(caption) + 50].strip()).lower()
        if body_start.startswith(caption_clean):
            return body[len(caption_clean):].strip()
        return body

    def _detect_header_row(self, lines: list[list[str]]) -> int | None:
        """Detect which row is most likely the header (alphabetical content)."""
        best_idx = None
        best_score = -1
        for i, cells in enumerate(lines):
            alpha_count = sum(
                1 for c in cells if re.search(r'[A-Za-z]', c)
            )
            score = alpha_count / max(len(cells), 1)
            if score > best_score and score >= HEADER_KEYWORD_RATIO:
                best_score = score
                best_idx = i
        return best_idx

    def _numeric_line_ratio(self, lines: list[str]) -> float:
        """Calculate the ratio of numeric-heavy lines."""
        if not lines:
            return 0.0
        numeric_count = 0
        for line in lines:
            chars = re.sub(r'\s', '', line)
            if not chars:
                continue
            digits = sum(1 for c in chars if c.isdigit() or c in '.-+±()')
            if digits / max(len(chars), 1) > 0.3:
                numeric_count += 1
        return numeric_count / max(len(lines), 1)

    def _assess_confidence(
        self, columns: list[str], rows: list[dict[str, str]], method: str
    ) -> str:
        """Assess structure extraction confidence."""
        score = 0
        # Column name quality
        alpha_cols = sum(1 for c in columns if re.search(r'[A-Za-z]', c))
        if alpha_cols >= len(columns) * 0.5:
            score += 2

        # Consistency
        col_counts = Counter(len(r) for r in rows)
        most_common = col_counts.most_common(1)[0][1]
        if most_common == len(rows):
            score += 2
        elif most_common >= len(rows) * 0.8:
            score += 1

        # Row count
        if len(rows) >= 10:
            score += 1
        if len(rows) >= 5:
            score += 0

        # Method quality
        if method == "markdown_like":
            score += 1
        elif method == "tab_delimited":
            score += 1

        if score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        else:
            return "low"

    def _load_raw_text(self, paper_id: str) -> str:
        if not self.raw_text_dir.exists():
            return ""
        pid_hash = paper_id[-12:] if len(paper_id) >= 12 else paper_id
        for f in self.raw_text_dir.glob("*.txt"):
            if pid_hash in f.name:
                try:
                    return f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
        return ""

    def _unavailable_result(self, reason: str) -> dict[str, Any]:
        return {
            "structure_status": "structure_pending",
            "structured_columns": [],
            "structured_rows": [],
            "raw_table_text": None,
            "structure_confidence": "none",
            "structure_extraction_method": "unavailable",
            "structure_notes": [f"No table body available: {reason}"],
        }

    def _complex_result(self, reason: str, notes: list[str]) -> dict[str, Any]:
        return {
            "structure_status": "complex_structure_skipped",
            "structured_columns": [],
            "structured_rows": [],
            "raw_table_text": None,
            "structure_confidence": "none",
            "structure_extraction_method": "skipped_complex",
            "structure_notes": [reason] + notes,
        }
