"""Tests for P6.5 agent_benchmark_runner."""

import tempfile
from pathlib import Path

from scientra.benchmark.agent_benchmark_runner import run_agent_benchmark, AGENT_QUERIES


class TestAgentBenchmarkRunner:
    def test_run_no_crash(self):
        """Agent benchmark should not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_agent_benchmark(root)
            assert result.category == "agent"
            assert len(result.runtime_metrics) == len(AGENT_QUERIES)

    def test_evidence_only_default(self):
        """Default mode should be evidence_only (no LLM calls)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_agent_benchmark(root)
            for m in result.runtime_metrics:
                assert m.metadata.get("mode") == "evidence_only"

    def test_agent_metrics_have_phases(self):
        """Each metric should have intent, planning, execution, assembly, answer phases."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_agent_benchmark(root)
            for m in result.runtime_metrics:
                assert "intent" in m.metadata
                assert "intent_ms" in m.metadata
                assert "planning_ms" in m.metadata
                assert "tool_execution_ms" in m.metadata
                assert "assembly_ms" in m.metadata
                assert "answer_build_ms" in m.metadata
                assert "total_ms" in m.metadata

    def test_all_queries_benchmarked(self):
        """All 4 agent queries should be benchmarked."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_agent_benchmark(root)
            assert len(result.runtime_metrics) == 4

    def test_no_llm_by_default(self):
        """include_llm=False means no LLM usage."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_agent_benchmark(root, include_llm=False)
            for m in result.runtime_metrics:
                # evidence_only mode should be used
                assert m.metadata.get("mode") == "evidence_only"
