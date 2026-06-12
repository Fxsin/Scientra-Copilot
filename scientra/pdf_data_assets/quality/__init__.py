"""
Quality verification, noise filtering, and Agent-readiness checks for Phase 0 assets.

Modules:
    - asset_quality_checker: Completeness validation per paper
    - entity_noise_filter: Entity dedup, stopword removal, merge
    - chunk_quality_checker: Agent chunk validation + vector_ready scoring
    - claim_quality_checker: Claim-evidence quality assessment
    - sample_exporter: Human-review sample export (.md + .json)
    - quality_report_builder: Full-library quality report generation
"""

from __future__ import annotations
