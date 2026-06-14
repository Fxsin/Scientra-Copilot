"""P4.2 Table Intelligence.

Core modules:
  - table_context_builder: Build context for each table from asset graph
  - table_structure_parser: Parse xlsx/csv/tsv/txt files
  - table_schema_inferer: Classify table type from headers
  - table_stat_detector: Detect statistical fields
  - table_interpreter: Generate interpretations (LLM + rule fallback)
  - table_quality_checker: Evaluate quality and overclaim risk
  - table_card_builder: Merge into unified Table Cards
  - table_intelligence_runner: Orchestrate full pipeline
"""

from scientra.assets.table_intelligence.table_context_builder import TableContextBuilder
from scientra.assets.table_intelligence.table_structure_parser import parse_table_structure
from scientra.assets.table_intelligence.table_schema_inferer import infer_table_schema
from scientra.assets.table_intelligence.table_stat_detector import detect_statistical_fields
from scientra.assets.table_intelligence.table_interpreter import TableInterpreter
from scientra.assets.table_intelligence.table_quality_checker import TableQualityChecker
from scientra.assets.table_intelligence.table_card_builder import TableCardBuilder
from scientra.assets.table_intelligence.table_intelligence_runner import TableIntelligenceRunner

__all__ = [
    "TableContextBuilder",
    "parse_table_structure",
    "infer_table_schema",
    "detect_statistical_fields",
    "TableInterpreter",
    "TableQualityChecker",
    "TableCardBuilder",
    "TableIntelligenceRunner",
]
