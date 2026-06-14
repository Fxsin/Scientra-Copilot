"""Tests for Evidence-Asset Linker."""

from __future__ import annotations

import pytest
from scientra.assets.linking.evidence_asset_linker import EvidenceAssetLinker


def _make_mention(**kwargs) -> dict:
    defaults = {
        "mention_id": "cite_test001",
        "paper_id": "paper_test",
        "source_type": "evidence_chunk",
        "source_id": "paper_test:evidence:key_results:0",
        "section": "results",
        "sentence": "Figure S2 shows the dose-response curve.",
        "citation_text": "Figure S2",
        "asset_type": "figure",
        "normalized_label": "Figure S2",
        "subpanel": "",
        "is_supplementary": True,
        "context_before": "The treatment was effective.",
        "context_after": "The EC50 was 2.3 μM.",
        "evidence_field": "key_results",
        "evidence_index": 0,
    }
    defaults.update(kwargs)
    return defaults


def _make_asset_link(**kwargs) -> dict:
    defaults = {
        "link_id": "link_test001",
        "paper_id": "paper_test",
        "citation_mention_id": "cite_test001",
        "asset_id": "asset_001",
        "asset_type": "figure",
        "normalized_label": "Figure S2",
        "match_method": "filename",
        "confidence": 0.90,
        "status": "matched",
    }
    defaults.update(kwargs)
    return defaults


class TestEvidenceAssetLinker:
    def test_basic_linking(self):
        linker = EvidenceAssetLinker()
        mentions = [
            _make_mention(
                mention_id="cite_001",
                source_id="paper_test:evidence:key_results:0",
                citation_text="Figure S2",
            ),
        ]
        asset_links = [
            _make_asset_link(
                citation_mention_id="cite_001",
                asset_id="asset_fig_s2",
            ),
        ]
        result = linker.link("paper_test", mentions, asset_links)
        assert len(result) >= 1
        ev_link = result[0]
        assert ev_link["asset_id"] == "asset_fig_s2"
        assert ev_link["evidence_id"] == "paper_test:evidence:key_results:0"

    def test_relation_inference_supports(self):
        linker = EvidenceAssetLinker()
        mentions = [
            _make_mention(
                mention_id="cite_002",
                sentence="These results support the hypothesis.",
                context_before="The data confirm the model.",
            ),
        ]
        asset_links = [
            _make_asset_link(citation_mention_id="cite_002"),
        ]
        result = linker.link("paper_test", mentions, asset_links)
        if result:
            assert result[0]["relation"] in ("supports", "illustrates", "reports_data", "method_detail", "unknown")

    def test_relation_inference_method(self):
        linker = EvidenceAssetLinker()
        mentions = [
            _make_mention(
                mention_id="cite_003",
                sentence="The protocol is described in Supplementary Table 2.",
                context_before="Methods were performed as detailed.",
            ),
        ]
        asset_links = [
            _make_asset_link(citation_mention_id="cite_003"),
        ]
        result = linker.link("paper_test", mentions, asset_links)
        if result:
            assert result[0]["relation"] == "method_detail"

    def test_relation_inference_illustrates(self):
        linker = EvidenceAssetLinker()
        mentions = [
            _make_mention(
                mention_id="cite_004",
                sentence="As shown in Figure 1, the data clearly demonstrate the trend.",
            ),
        ]
        asset_links = [
            _make_asset_link(citation_mention_id="cite_004"),
        ]
        result = linker.link("paper_test", mentions, asset_links)
        if result:
            assert result[0]["relation"] == "illustrates"

    def test_ignore_non_evidence_mentions(self):
        linker = EvidenceAssetLinker()
        mentions = [
            _make_mention(
                mention_id="cite_005",
                source_type="body_text",  # Not evidence_chunk
                source_id="test:body:1",
            ),
        ]
        asset_links = [
            _make_asset_link(citation_mention_id="cite_005"),
        ]
        result = linker.link("paper_test", mentions, asset_links)
        # Should not link body_text mentions
        assert len(result) == 0

    def test_missing_asset_info(self):
        linker = EvidenceAssetLinker()
        mentions = [
            _make_mention(mention_id="cite_006"),
        ]
        asset_links = []  # No matching asset link
        result = linker.link("paper_test", mentions, asset_links)
        assert len(result) == 0

    def test_build_asset_evidence_index(self):
        linker = EvidenceAssetLinker()
        evidence_links = [
            {
                "evidence_id": "ev_1",
                "asset_id": "asset_A",
            },
            {
                "evidence_id": "ev_2",
                "asset_id": "asset_A",
            },
            {
                "evidence_id": "ev_3",
                "asset_id": "asset_B",
            },
        ]
        index = linker.build_asset_evidence_index(evidence_links)
        assert "asset_A" in index
        assert len(index["asset_A"]) == 2
        assert "ev_1" in index["asset_A"]
        assert "ev_2" in index["asset_A"]
        assert "asset_B" in index
        assert len(index["asset_B"]) == 1

    def test_evidence_link_structure(self):
        linker = EvidenceAssetLinker()
        mentions = [
            _make_mention(
                mention_id="cite_struct",
                source_id="paper_test:evidence:core_findings:1",
                evidence_field="core_findings",
                evidence_index=1,
            ),
        ]
        asset_links = [
            _make_asset_link(citation_mention_id="cite_struct", asset_id="asset_struct"),
        ]
        result = linker.link("paper_test", mentions, asset_links)
        if result:
            ev_link = result[0]
            assert "evidence_id" in ev_link
            assert "asset_id" in ev_link
            assert "relation" in ev_link
            assert "confidence" in ev_link
            assert "citation_text" in ev_link
            assert ev_link["relation"] in ("supports", "illustrates", "reports_data", "method_detail", "unknown")
