"""P4.0.4 Asset Linking Engine.

Core modules:
  - citation_parser: Extract Figure/Table/Dataset/Supplementary citations from text
  - label_normalizer: Normalize varied citation forms to standard labels
  - asset_matcher: Match citations to registered assets
  - evidence_asset_linker: Link evidence chunks to matched assets
  - asset_graph_builder: Orchestrate full pipeline, produce output files
"""

from scientra.assets.linking.label_normalizer import normalize_label, make_search_variants
from scientra.assets.linking.citation_parser import CitationParser
from scientra.assets.linking.asset_matcher import AssetMatcher
from scientra.assets.linking.evidence_asset_linker import EvidenceAssetLinker
from scientra.assets.linking.asset_graph_builder import AssetGraphBuilder

__all__ = [
    "normalize_label",
    "make_search_variants",
    "CitationParser",
    "AssetMatcher",
    "EvidenceAssetLinker",
    "AssetGraphBuilder",
]
