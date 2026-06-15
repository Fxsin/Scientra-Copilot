"""P5.3 Dataset Intelligence."""

from scientra.datasets.intelligence.dataset_manifest_builder import DatasetManifestBuilder
from scientra.datasets.intelligence.dataset_loader import load_dataset
from scientra.datasets.intelligence.dataset_schema_inferer import infer_schema
from scientra.datasets.intelligence.dataset_entity_extractor import extract_entities
from scientra.datasets.intelligence.dataset_numeric_profiler import profile_numerics
from scientra.datasets.intelligence.dataset_evidence_extractor import extract_evidence
from scientra.datasets.intelligence.dataset_card_builder import build_card, build_cards
from scientra.datasets.intelligence.dataset_quality_checker import check_quality
from scientra.datasets.intelligence.cross_paper_dataset_indexer import CrossPaperDatasetIndexer
from scientra.datasets.intelligence.dataset_comparison_engine import DatasetComparisonEngine
from scientra.datasets.intelligence.dataset_intelligence_runner import DatasetIntelligenceRunner

__all__ = [
    "DatasetManifestBuilder", "load_dataset", "infer_schema",
    "extract_entities", "profile_numerics", "extract_evidence",
    "build_card", "build_cards", "check_quality",
    "CrossPaperDatasetIndexer", "DatasetComparisonEngine",
    "DatasetIntelligenceRunner",
]
