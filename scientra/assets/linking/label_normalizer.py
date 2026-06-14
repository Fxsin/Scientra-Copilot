"""Label Normalizer — standardize citation labels across varied writing styles.

Handles:
  Fig. 1      -> Figure 1
  Figure 1    -> Figure 1
  Fig. 1A     -> Figure 1A
  Figure S1   -> Figure S1
  Fig. S2     -> Figure S2
  Supplementary Fig. S3  -> Figure S3
  Table 1     -> Table 1
  Table S1    -> Table S1
  Supplementary Table 2  -> Table S2
  Dataset S1  -> Dataset S1
  Data S1     -> Dataset S1
  Appendix Figure S1     -> Figure S1
"""

from __future__ import annotations

import re
from typing import Any

# ── Patterns for recognizing different citation forms ──

# Matches: "Fig. 1", "Figure 2A", "Fig. S1", "Figure S3B"
_FIGURE_PATTERN = re.compile(
    r"(?:(?:Supplementary|Suppl\.?|Appendix|App\.?)\s+)?"
    r"(?:Fig\.?|Figs\.?|Figure|Figures|FIG\.?|FIGS\.?)\s+"
    r"(S?\d+(?:[A-Za-z])?(?:[–\-]\d+[A-Za-z]?)?(?:,\s*(?:and\s+)?\d+[A-Za-z]?)*)",
    re.IGNORECASE,
)

# Matches: "Table 1", "Table S1", "Supplementary Table 2"
_TABLE_PATTERN = re.compile(
    r"(?:(?:Supplementary|Suppl\.?|Appendix|App\.?)\s+)?"
    r"(?:Table|TAB\.?)\s+"
    r"(S?\d+(?:[A-Za-z])?(?:[–\-]\d+[A-Za-z]?)?(?:,\s*\d+[A-Za-z]?)*)",
    re.IGNORECASE,
)

# Matches: "Dataset S1", "Data S1", "Supplementary Data 1", "Supplementary Dataset S1"
_DATASET_PATTERN = re.compile(
    r"(?:(?:Supplementary|Suppl\.?|Appendix|App\.?)\s+)?"
    r"(?:Data|Dataset|DATASET)\s+"
    r"(S?\d+(?:[A-Za-z])?)",
    re.IGNORECASE,
)

# Matches: "Supplementary Material", "Supplementary Information", "SI Appendix"
_SUPPLEMENTARY_GENERAL = re.compile(
    r"(?:Supplementary\s+(?:Material|Information|Data|File|Note|Text|Methods|Results|Discussion))"
    r"|(?:SI\s+Appendix)"
    r"|(?:Supporting\s+Information)"
    r"|(?:Additional\s+[Ff]ile\s+\d+)"
    r"|(?:(?:Appendix|App\.?)\s+[A-Z]\d*)",
    re.IGNORECASE,
)


def normalize_label(citation_text: str) -> dict[str, Any]:
    """Normalize a citation text to a standard label.

    Args:
        citation_text: Raw citation text, e.g. "Supplementary Fig. S1A"

    Returns:
        dict with keys:
            normalized_label: str  — e.g. "Figure S1"
            asset_type: str        — "figure", "table", "dataset", "supplementary", "unknown"
            subpanel: str          — e.g. "A", "" if no subpanel
            original_text: str     — the input text
            is_supplementary: bool — True if label indicates supplementary material
    """
    text = citation_text.strip()

    result: dict[str, Any] = {
        "normalized_label": text,
        "asset_type": "unknown",
        "subpanel": "",
        "original_text": text,
        "is_supplementary": False,
    }

    # Detect supplementary prefix
    is_supp = bool(re.search(
        r"^(?:Supplementary|Suppl\.?|Appendix|App\.?)\s+",
        text, re.IGNORECASE,
    ))
    # Also detect S-prefixed numbers (S1, S2, etc.)
    has_s_prefix = bool(re.search(r"\bS\d+", text))

    result["is_supplementary"] = is_supp or has_s_prefix

    # Try figure pattern first
    fig_match = _FIGURE_PATTERN.search(text)
    if fig_match:
        number_part = fig_match.group(1).strip()
        label, subpanel = _parse_number_part(number_part, "Figure", result["is_supplementary"])
        result["normalized_label"] = label
        result["asset_type"] = "figure"
        result["subpanel"] = subpanel
        return result

    # Try table pattern
    tbl_match = _TABLE_PATTERN.search(text)
    if tbl_match:
        number_part = tbl_match.group(1).strip()
        label, subpanel = _parse_number_part(number_part, "Table", result["is_supplementary"])
        result["normalized_label"] = label
        result["asset_type"] = "table"
        result["subpanel"] = subpanel
        return result

    # Try dataset pattern
    ds_match = _DATASET_PATTERN.search(text)
    if ds_match:
        number_part = ds_match.group(1).strip()
        label, subpanel = _parse_number_part(number_part, "Dataset", result["is_supplementary"])
        result["normalized_label"] = label
        result["asset_type"] = "dataset"
        result["subpanel"] = subpanel
        return result

    # Try supplementary general
    supp_match = _SUPPLEMENTARY_GENERAL.search(text)
    if supp_match:
        result["normalized_label"] = supp_match.group(0).strip()
        result["asset_type"] = "supplementary"
        result["is_supplementary"] = True
        return result

    return result


def _parse_number_part(number_str: str, prefix: str, is_supp: bool) -> tuple[str, str]:
    """Parse a number part like 'S1A' or '3B' into (label, subpanel).

    Args:
        number_str: The number part of the citation (e.g. "S1A", "3", "2B")
        prefix: The asset type prefix ("Figure", "Table", "Dataset")
        is_supp: Whether this is a supplementary reference

    Returns:
        (normalized_label, subpanel)
    """
    # Extract trailing letter (subpanel)
    subpanel = ""
    match = re.match(r"^(S?\d+)([A-Za-z])$", number_str)
    if match:
        number_str = match.group(1)
        subpanel = match.group(2).upper()

    # Ensure S prefix is preserved for supplementary labels
    num = number_str.strip()
    if is_supp and not num.startswith("S"):
        num = "S" + num

    label = f"{prefix} {num}"
    return label, subpanel


def make_search_variants(normalized_label: str, asset_type: str) -> list[str]:
    """Generate search variants for fuzzy matching against filenames/notes.

    Args:
        normalized_label: e.g. "Figure S1"
        asset_type: e.g. "figure"

    Returns:
        List of variant strings to try when matching against asset metadata.
    """
    variants = [normalized_label]

    # Split into prefix and number
    parts = normalized_label.rsplit(" ", 1)
    if len(parts) != 2:
        return variants

    prefix, num = parts

    # Variants with different separators
    variants.append(f"{prefix}_{num}")       # Figure_S1
    variants.append(f"{prefix}-{num}")       # Figure-S1
    variants.append(f"{prefix}{num}")        # FigureS1
    variants.append(f"{prefix.lower()}_{num}")  # figure_S1
    variants.append(f"{prefix.lower()}-{num}")  # figure-S1
    variants.append(f"{prefix.lower()}{num}")   # figureS1

    # Abbreviated forms
    abbr_map = {"Figure": "Fig", "Table": "Tab", "Dataset": "Data"}
    abbr = abbr_map.get(prefix, prefix)
    variants.append(f"{abbr}_{num}")         # Fig_S1
    variants.append(f"{abbr}-{num}")         # Fig-S1
    variants.append(f"{abbr}{num}")          # FigS1
    variants.append(f"{abbr}._{num}")        # Fig._S1
    variants.append(f"{abbr}.{num}")         # Fig.S1
    variants.append(f"{abbr} {num}")         # Fig S1

    # Just the number part (for filenames like S1.png)
    variants.append(num)

    # Number without S prefix for supplementary items
    if num.startswith("S"):
        bare_num = num[1:]
        variants.append(f"{prefix}_{bare_num}")
        variants.append(f"{prefix}-{bare_num}")
        variants.append(f"{prefix} {bare_num}")
        variants.append(f"{abbr}_{bare_num}")
        variants.append(f"{abbr}.{bare_num}")
        variants.append(bare_num)

    return variants
