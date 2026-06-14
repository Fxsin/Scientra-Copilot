"""P4.3 Supplementary Intelligence.

Core modules:
  - supplementary_parser: Parse .txt/.md/.docx/.pdf/.html files
  - supplementary_sectioner: Detect sections in supplementary text
  - supplementary_context_builder: Build context from asset graph + P4.1/P4.2 cards
  - supplementary_evidence_extractor: Extract evidence from sections
  - supplementary_chunker: Create retrievable chunks
  - supplementary_interpreter: Generate interpretations (LLM + rule fallback)
  - supplementary_quality_checker: Evaluate quality and overclaim risk
  - supplementary_card_builder: Merge into unified Supplementary Cards
  - supplementary_intelligence_runner: Orchestrate full pipeline (Storage Layout v3)
"""

from scientra.assets.supplementary_intelligence.supplementary_parser import parse_supplementary
from scientra.assets.supplementary_intelligence.supplementary_sectioner import detect_sections
from scientra.assets.supplementary_intelligence.supplementary_context_builder import SupplementaryContextBuilder
from scientra.assets.supplementary_intelligence.supplementary_evidence_extractor import extract_evidence
from scientra.assets.supplementary_intelligence.supplementary_chunker import chunk_supplementary
from scientra.assets.supplementary_intelligence.supplementary_interpreter import SupplementaryInterpreter
from scientra.assets.supplementary_intelligence.supplementary_quality_checker import SupplementaryQualityChecker
from scientra.assets.supplementary_intelligence.supplementary_card_builder import SupplementaryCardBuilder
from scientra.assets.supplementary_intelligence.supplementary_intelligence_runner import SupplementaryIntelligenceRunner

__all__ = [
    "parse_supplementary",
    "detect_sections",
    "SupplementaryContextBuilder",
    "extract_evidence",
    "chunk_supplementary",
    "SupplementaryInterpreter",
    "SupplementaryQualityChecker",
    "SupplementaryCardBuilder",
    "SupplementaryIntelligenceRunner",
]
