"""P4.1 Figure Intelligence.

Core modules:
  - figure_context_builder: Build comprehensive context for each figure from asset graph
  - figure_evidence_classifier: Classify figure evidence type from captions/context
  - figure_interpreter: Generate interpretations (LLM mode or rule fallback)
  - figure_quality_checker: Evaluate interpretation quality and overclaim risk
  - figure_card_builder: Merge all outputs into unified Figure Cards
  - figure_intelligence_runner: Orchestrate full pipeline
"""

from scientra.assets.figure_intelligence.figure_evidence_classifier import classify_evidence_type
from scientra.assets.figure_intelligence.figure_context_builder import FigureContextBuilder
from scientra.assets.figure_intelligence.figure_interpreter import FigureInterpreter
from scientra.assets.figure_intelligence.figure_quality_checker import FigureQualityChecker
from scientra.assets.figure_intelligence.figure_card_builder import FigureCardBuilder
from scientra.assets.figure_intelligence.figure_intelligence_runner import FigureIntelligenceRunner

__all__ = [
    "classify_evidence_type",
    "FigureContextBuilder",
    "FigureInterpreter",
    "FigureQualityChecker",
    "FigureCardBuilder",
    "FigureIntelligenceRunner",
]
