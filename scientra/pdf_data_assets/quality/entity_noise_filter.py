"""
Entity Noise Filter — removes low-quality entities without deleting originals.

Rules:
  1. Remove entities with name length < 2
  2. Remove pure numeric entities
  3. Remove common English stopwords
  4. Remove overly generic scientific words
  5. Merge case-insensitive duplicates (keep first, record frequency)
  6. Merge identical entities (accumulate frequency)

Output: 06_PDF_DataAssets/06_entities/{paper_id}/filtered_entities.json
Original entities.json is NEVER modified.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Stopwords & generic words to filter ──

STOPWORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall", "this",
    "that", "these", "those", "it", "its", "they", "them", "their",
    "we", "us", "our", "you", "your", "he", "she", "his", "her",
    "not", "no", "nor", "so", "if", "then", "than", "too", "very",
    "just", "about", "above", "after", "again", "all", "also", "any",
    "because", "before", "between", "both", "but", "each", "few", "more",
    "most", "other", "some", "such", "only", "own", "same", "into",
    "over", "under", "up", "down", "out", "off", "now", "new", "here",
    "there", "when", "where", "which", "who", "whom", "whose", "how",
    "well", "one", "two", "three", "first", "second", "last", "next",
}

GENERIC_SCIENTIFIC_WORDS: set[str] = {
    "result", "results", "method", "methods", "figure", "fig", "table",
    "using", "used", "showed", "shows", "shown", "significant",
    "significantly", "data", "analysis", "study", "studies", "experiment",
    "experiments", "level", "levels", "effect", "effects", "activity",
    "activities", "role", "roles", "function", "functions", "process",
    "processes", "factor", "factors", "type", "types", "group", "groups",
    "control", "controls", "sample", "samples", "model", "models",
    "system", "systems", "cell", "cells", "based", "present", "observed",
    "found", "identified", "reported", "known", "similar", "different",
    "various", "several", "including", "additional", "important", "novel",
    "potential", "previous", "current", "total", "specific", "common",
    "natural", "produced", "produce", "produces", "production",
    "high", "higher", "low", "lower", "large", "larger", "small", "smaller",
    "increase", "increased", "decrease", "decreased",
    "form", "forms", "formation", "formed", "forming",
    "class", "classified", "classification",
    "order", "orders", "family", "families",
    "number", "numbers", "sequence", "sequences",
    "gene", "genes", "protein", "proteins",
    "species", "strains", "strain",
    "bacterium", "bacteria", "bacterial",
    "year", "years", "day", "days", "time", "times",
    "value", "values", "range", "ranges",
    "mode", "modes", "action", "actions",
    "location", "locations", "host", "hosts",
    "addition", "additional",
    "lack", "lacks", "lacking",
    "wide", "wider", "diverse", "diversity",
    "insect", "insects", "pest", "pests",
    "crystal", "crystals", "crystalline", "parasporal",
    "phase", "phases", "growth", "medium",
    "characterized", "characterize", "characterization",
    "synthesize", "synthesizes", "synthesized",
    "respectively",
    "degree", "degrees",
    "criterion", "criteria",
    "imply", "implies", "implied",
    "facilitate", "facilitates", "facilitated",
    "observation", "observations",
    "instance", "instances",
    "usefulness",
    "motivated", "motivates",
    "generating", "generated", "generates",
    "continuously", "continuous",
    "successfully", "successful",
    "depending", "depends", "depended",
    "pairwise",
    "identity", "identities",
    "named", "naming", "names",
    "previously", "previous",
    "ranks", "rank", "ranking",
    "assigned", "assigning",
    "displayed", "displays", "displaying",
    "displayed",
    "upon",
    "containing", "contains", "contained",
    "including", "includes", "included",
    "term", "termed", "terms",
    "secreted", "secretory", "secrete",
    "sprayable", "wherein", "ingredien",
    "cations", "icidal", "antibac",
    "xins", "insecticides", "bioinsecticides",
    "caterpillars", "beetles", "flies", "mosquitoes", "larvae",
    "blackflies", "nematodes", "phyla",
    "isolates", "isolated", "worldwide",
    "ecosystems", "soil", "water", "dead", "phylloplane",
    "ubiquitous", "rod", "shaped", "sporulating",
    "gram", "positive", "negative",
    "anaerobic", "genus", "clostridium", "archaeal",
    "against",
    "endotoxins", "onset", "sporulation", "stationary", "inclusions",
    "homopteran", "coleopteran", "lepidopteran",
    "mosquitocidal", "binary", "lysinibacillus", "sphaericus",
    "israelensis", "subspecies",
    "subsequently", "during",
    "commonly",
    "hold", "holds",
}


class EntityNoiseFilter:
    """Filters and deduplicates entities. Never modifies originals."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.entities_dir = self.root / "06_PDF_DataAssets" / "06_entities"
        self._seen_names: dict[str, str] = {}  # lowercase -> first original name

    def filter_paper(self, paper_id: str) -> dict[str, Any]:
        """Filter entities for a paper. Returns filtered result dict."""
        source_path = self.entities_dir / paper_id / "entities.json"
        if not source_path.exists():
            return {
                "paper_id": paper_id,
                "status": "no_source",
                "original_count": 0,
                "filtered_count": 0,
                "entities": [],
                "filter_stats": {},
                "error": "entities.json not found",
            }

        try:
            original = json.loads(source_path.read_text(encoding="utf-8"))
        except Exception as e:
            return {
                "paper_id": paper_id,
                "status": "parse_error",
                "original_count": 0,
                "filtered_count": 0,
                "entities": [],
                "filter_stats": {},
                "error": str(e),
            }

        if not isinstance(original, list):
            original = []

        original_count = len(original)
        filtered: list[dict[str, Any]] = []
        stats: dict[str, int] = {
            "kept": 0,
            "filtered_too_short": 0,
            "filtered_numeric": 0,
            "filtered_stopword": 0,
            "filtered_generic_word": 0,
            "merged_duplicate": 0,
        }

        # Frequency map for merging
        freq_map: dict[str, dict[str, Any]] = {}  # lower_name -> merged info

        for item in original:
            if not isinstance(item, dict):
                continue
            name = str(item.get("entity_name", "")).strip()
            entity_type = str(item.get("entity_type", "unknown"))

            # Rule 1: too short
            if len(name) < 2:
                stats["filtered_too_short"] += 1
                item["entity_status"] = "filtered_too_short"
                filtered.append(item)
                continue

            # Rule 2: pure numeric
            if re.match(r"^[\d.,]+$", name):
                stats["filtered_numeric"] += 1
                item["entity_status"] = "filtered_numeric"
                filtered.append(item)
                continue

            # Rule 3: stopword
            if name.lower() in STOPWORDS:
                stats["filtered_stopword"] += 1
                item["entity_status"] = "filtered_stopword"
                filtered.append(item)
                continue

            # Rule 4: generic scientific word
            if name.lower() in GENERIC_SCIENTIFIC_WORDS:
                stats["filtered_generic_word"] += 1
                item["entity_status"] = "filtered_generic_word"
                filtered.append(item)
                continue

            # Merge duplicates
            lower_name = name.lower()
            if lower_name in freq_map:
                stats["merged_duplicate"] += 1
                freq_map[lower_name]["frequency"] = freq_map[lower_name].get("frequency", 1) + 1
                # Keep the shorter or first name
                if len(name) < len(freq_map[lower_name]["entity_name"]):
                    freq_map[lower_name]["entity_name"] = name
                item["entity_status"] = "merged_duplicate"
                item["merged_into"] = freq_map[lower_name]["entity_name"]
                filtered.append(item)
                continue

            # Kept
            stats["kept"] += 1
            item["entity_status"] = "kept"
            item["frequency"] = 1
            freq_map[lower_name] = {
                "entity_name": name,
                "frequency": 1,
                "entity_type": entity_type,
            }
            filtered.append(item)

        # Update frequencies on kept items
        for item in filtered:
            if item.get("entity_status") == "kept" and item.get("entity_name", "").lower() in freq_map:
                item["frequency"] = freq_map[item["entity_name"].lower()]["frequency"]

        result = {
            "paper_id": paper_id,
            "status": "success",
            "filtered_at": datetime.now(timezone.utc).isoformat(),
            "original_count": original_count,
            "kept_count": stats["kept"],
            "filtered_count": original_count - stats["kept"],
            "filter_stats": stats,
            "entities": filtered,
        }

        # Save
        output_path = self.entities_dir / paper_id / "filtered_entities.json"
        tmp = output_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(output_path)

        return result

    def get_filter_stats(self, paper_id: str) -> dict[str, Any]:
        """Get cached filter stats, or compute and cache."""
        cache_path = self.entities_dir / paper_id / "filtered_entities.json"
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                return {
                    "paper_id": paper_id,
                    "original_count": data.get("original_count", 0),
                    "kept_count": data.get("kept_count", 0),
                    "filtered_count": data.get("filtered_count", 0),
                    "filter_stats": data.get("filter_stats", {}),
                }
            except Exception:
                pass
        return self.filter_paper(paper_id)
