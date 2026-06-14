"""Asset Matcher — match citation mentions to registered assets in the registry.

Uses multiple matching methods:
  1. notes_match — match against asset_notes.txt title lines
  2. filename_match — match normalized label against asset filename
  3. caption_match — match against any caption metadata
  4. fuzzy_match — fuzzy string matching as fallback
  5. manual — user-provided mapping

Output: matched / unmatched / low_confidence links.
"""

from __future__ import annotations

import json
import re
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from scientra.assets.linking.label_normalizer import make_search_variants


class AssetMatcher:
    """Match citation mentions to registered assets."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            candidate = Path(__file__).resolve().parent.parent.parent.parent
            self.root = candidate
        else:
            self.root = Path(root).resolve()

    def match_all(
        self,
        paper_id: str,
        mentions: list[dict[str, Any]],
        registry: Any,  # PaperAssetRegistry
    ) -> dict[str, Any]:
        """Match all citation mentions against registered assets.

        Args:
            paper_id: The paper ID.
            mentions: List of citation mention dicts from CitationParser.
            registry: PaperAssetRegistry instance.

        Returns:
            dict with keys:
                links: list of asset link dicts
                unmatched_mentions: list of mentions with no match
                unmatched_assets: list of assets with no citation
                low_confidence: list of links with low confidence
        """
        links: list[dict[str, Any]] = []
        unmatched_mentions: list[dict[str, Any]] = []
        low_confidence: list[dict[str, Any]] = []

        # Build asset lookup structures
        assets_list = registry.assets if hasattr(registry, 'assets') else registry.get("assets", [])
        asset_by_id = {a.get("asset_id", ""): a for a in assets_list}

        # Load asset_notes for this paper
        notes_map = self._load_asset_notes(paper_id)

        # Track which assets get matched
        matched_asset_ids: set[str] = set()

        for mention in mentions:
            norm_label = mention.get("normalized_label", "")
            asset_type = mention.get("asset_type", "unknown")

            if not norm_label:
                unmatched_mentions.append(mention)
                continue

            # Try each matching method in priority order
            best_match = None
            best_method = ""
            best_score = 0.0

            # Method 1: notes matching
            result = self._match_by_notes(norm_label, asset_type, notes_map, asset_by_id)
            if result and result[1] > best_score:
                best_match, best_score = result
                best_method = "notes"

            # Method 2: filename matching
            result = self._match_by_filename(norm_label, asset_type, assets_list, asset_by_id)
            if result and result[1] > best_score:
                best_match, best_score = result
                best_method = "filename"

            # Method 3: caption matching
            result = self._match_by_caption(norm_label, asset_type, assets_list, asset_by_id)
            if result and result[1] > best_score:
                best_match, best_score = result
                best_method = "caption"

            # Method 4: fuzzy matching (only if no good match yet)
            if best_score < 0.7:
                result = self._match_by_fuzzy(norm_label, asset_type, assets_list, asset_by_id)
                if result and result[1] > best_score:
                    best_match, best_score = result
                    best_method = "fuzzy"

            # Build link
            link_id = f"link_{uuid.uuid4().hex[:12]}"

            if best_match and best_score >= 0.5:
                matched_asset = best_match
                asset_id = matched_asset.get("asset_id", "")

                link = {
                    "link_id": link_id,
                    "paper_id": paper_id,
                    "citation_mention_id": mention.get("mention_id", ""),
                    "asset_id": asset_id,
                    "asset_type": asset_type,
                    "normalized_label": norm_label,
                    "match_method": best_method,
                    "confidence": round(best_score, 2),
                    "status": "matched" if best_score >= 0.7 else "low_confidence",
                }

                if best_score >= 0.7:
                    links.append(link)
                    matched_asset_ids.add(asset_id)
                else:
                    low_confidence.append(link)
            else:
                # No match found
                link = {
                    "link_id": link_id,
                    "paper_id": paper_id,
                    "citation_mention_id": mention.get("mention_id", ""),
                    "asset_id": "",
                    "asset_type": asset_type,
                    "normalized_label": norm_label,
                    "match_method": "none",
                    "confidence": 0.0,
                    "status": "unmatched",
                }
                unmatched_mentions.append(mention)

        # Find assets with no citations
        unmatched_assets = [
            a for a in assets_list
            if a.get("asset_id") not in matched_asset_ids
            and a.get("asset_type") not in ("main_pdf", "unknown", "archive", "attachment")
        ]

        return {
            "links": links,
            "unmatched_mentions": unmatched_mentions,
            "unmatched_assets": unmatched_assets,
            "low_confidence": low_confidence,
        }

    def _load_asset_notes(self, paper_id: str) -> dict[str, str]:
        """Load asset_notes.txt and parse title lines.

        Format: "## Title: Figure S1 — Description"
        Returns dict mapping normalized label -> title line.
        """
        notes_map: dict[str, str] = {}

        # Look for asset_notes.txt in paper directory
        from scientra.assets.asset_registry import get_paper_dir
        paper_dir = get_paper_dir(paper_id)
        notes_path = paper_dir / "asset_notes.txt"

        if not notes_path.exists():
            # Also check assets/ subdirectory
            notes_path = paper_dir / "assets" / "asset_notes.txt"

        if not notes_path.exists():
            return notes_map

        try:
            content = notes_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return notes_map

        # Parse title lines: "## Title: Figure S1 ..." or "### Figure S1"
        title_pattern = re.compile(
            r"^(?:#{1,3}\s*(?:Title:\s*)?)?"
            r"(Figure\s+S?\d+[A-Za-z]?|Table\s+S?\d+[A-Za-z]?|Dataset\s+S?\d+[A-Za-z]?)",
            re.IGNORECASE | re.MULTILINE,
        )

        for match in title_pattern.finditer(content):
            label = match.group(1).strip()
            # Get the rest of the line
            line_start = match.start()
            line_end = content.find("\n", match.end())
            if line_end == -1:
                line_end = len(content)
            full_line = content[line_start:line_end].strip()
            notes_map[label] = full_line

        return notes_map

    def _match_by_notes(
        self,
        norm_label: str,
        asset_type: str,
        notes_map: dict[str, str],
        asset_by_id: dict[str, Any],
    ) -> tuple[dict[str, Any], float] | None:
        """Match by asset_notes.txt title."""
        # Direct match
        if norm_label in notes_map:
            # Find the asset associated with this note
            note_line = notes_map[norm_label]
            for asset_id, asset in asset_by_id.items():
                asset_filename = asset.get("filename", "")
                asset_orig = asset.get("original_filename", "")
                # Check if note line mentions this asset's filename
                if self._text_contains_any(note_line, [asset_filename, asset_orig]):
                    return (asset, 0.95)
            # If we can't find specific asset, return first match of same type
            for asset_id, asset in asset_by_id.items():
                if asset.get("asset_type", "") == self._asset_type_to_registry_type(asset_type):
                    return (asset, 0.85)

        # Fuzzy match in notes
        best_score = 0.0
        best_asset = None
        variants = make_search_variants(norm_label, asset_type)
        for variant in variants:
            for note_label, note_line in notes_map.items():
                score = SequenceMatcher(None, variant.lower(), note_label.lower()).ratio()
                if score > best_score and score >= 0.6:
                    best_score = score
                    # Find matching asset
                    for asset_id, asset in asset_by_id.items():
                        if asset.get("asset_type", "") == self._asset_type_to_registry_type(asset_type):
                            best_asset = asset
                            break

        if best_asset and best_score >= 0.6:
            return (best_asset, min(best_score, 0.75))  # Cap notes fuzzy at 0.75

        return None

    def _match_by_filename(
        self,
        norm_label: str,
        asset_type: str,
        assets_list: list[dict[str, Any]],
        asset_by_id: dict[str, Any],
    ) -> tuple[dict[str, Any], float] | None:
        """Match by filename similarity."""
        variants = make_search_variants(norm_label, asset_type)
        best_score = 0.0
        best_asset = None

        target_registry_type = self._asset_type_to_registry_type(asset_type)

        for asset in assets_list:
            # Skip if wrong type
            asset_reg_type = asset.get("asset_type", "")
            if target_registry_type and asset_reg_type != target_registry_type:
                # Allow cross-type for supplementary
                if not (target_registry_type == "supplementary_pdf" and "supplementary" in asset_reg_type):
                    continue

            filename = asset.get("filename", "")
            orig_filename = asset.get("original_filename", "")
            search_texts = [filename, orig_filename]

            for variant in variants:
                for st in search_texts:
                    if not st:
                        continue
                    # Direct substring match (high confidence)
                    if variant.lower() in st.lower():
                        score = 0.90
                        return (asset, score)
                    # Token-level match
                    score = self._token_match_score(variant, st)
                    if score > best_score:
                        best_score = score
                        best_asset = asset

        if best_asset and best_score >= 0.5:
            return (best_asset, min(best_score, 0.85))  # Cap filename fuzzy at 0.85

        return None

    def _match_by_caption(
        self,
        norm_label: str,
        asset_type: str,
        assets_list: list[dict[str, Any]],
        asset_by_id: dict[str, Any],
    ) -> tuple[dict[str, Any], float] | None:
        """Match by caption metadata if available."""
        target_registry_type = self._asset_type_to_registry_type(asset_type)

        for asset in assets_list:
            asset_reg_type = asset.get("asset_type", "")
            if target_registry_type and asset_reg_type != target_registry_type:
                continue

            # Check notes field for caption-like content
            notes = asset.get("notes", "")
            if notes and norm_label.lower() in notes.lower():
                return (asset, 0.80)

        return None

    def _match_by_fuzzy(
        self,
        norm_label: str,
        asset_type: str,
        assets_list: list[dict[str, Any]],
        asset_by_id: dict[str, Any],
    ) -> tuple[dict[str, Any], float] | None:
        """Fuzzy string matching fallback."""
        variants = make_search_variants(norm_label, asset_type)
        best_score = 0.0
        best_asset = None

        target_registry_type = self._asset_type_to_registry_type(asset_type)

        for asset in assets_list:
            asset_reg_type = asset.get("asset_type", "")
            if target_registry_type and asset_reg_type != target_registry_type:
                if not (target_registry_type == "supplementary_pdf" and "supplementary" in asset_reg_type):
                    continue

            filename = asset.get("filename", "")
            orig_filename = asset.get("original_filename", "")
            search_texts = [filename, orig_filename, asset.get("notes", "")]

            for variant in variants:
                for st in search_texts:
                    if not st:
                        continue
                    score = SequenceMatcher(None, variant.lower(), st.lower()).ratio()
                    if score > best_score:
                        best_score = score
                        best_asset = asset

        if best_asset and best_score >= 0.45:
            return (best_asset, min(best_score, 0.65))  # Cap fuzzy at 0.65

        return None

    @staticmethod
    def _token_match_score(query: str, target: str) -> float:
        """Score based on token overlap."""
        query_tokens = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
        target_tokens = set(re.findall(r"[a-zA-Z0-9]+", target.lower()))

        if not query_tokens:
            return 0.0

        overlap = query_tokens & target_tokens
        return len(overlap) / len(query_tokens)

    @staticmethod
    def _text_contains_any(text: str, candidates: list[str]) -> bool:
        """Check if text contains any of the candidate strings (case-insensitive)."""
        text_lower = text.lower()
        return any(c.lower() in text_lower for c in candidates if c)

    @staticmethod
    def _asset_type_to_registry_type(asset_type: str) -> str:
        """Map normalized asset_type to registry asset_type."""
        mapping = {
            "figure": "figure_image",
            "table": "supplementary_table",
            "dataset": "dataset",
            "supplementary": "supplementary_pdf",
        }
        return mapping.get(asset_type, "")
