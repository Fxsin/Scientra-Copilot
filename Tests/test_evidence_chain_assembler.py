import pytest
from scientra.agents.research_agent.evidence_chain_assembler import EvidenceChainAssembler

class TestAssembler:
    def test_empty(self):
        chains = EvidenceChainAssembler().assemble([])
        assert chains == []
    def test_assemble(self):
        results = [{"tool_name": "test", "data": [{"asset_type": "claim", "asset_id": "c1", "title": "C", "metadata": {"node_type": "claim"}},
                                                    {"asset_type": "evidence", "asset_id": "e1", "title": "E"}]}]
        chains = EvidenceChainAssembler().assemble(results)
        assert len(chains) >= 1
