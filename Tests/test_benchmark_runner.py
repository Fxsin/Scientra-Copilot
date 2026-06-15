"""Tests for P6.5 benchmark_runner orchestrator."""

import tempfile
from pathlib import Path

from scientra.benchmark.benchmark_runner import BenchmarkRunner


class TestBenchmarkRunner:
    def test_run_all_no_crash(self):
        """Full benchmark run should not crash with empty dir."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = BenchmarkRunner(root)
            run = runner.run_all(
                skip_graph=False,
                skip_datasets=False,
                skip_agent=False,
                skip_large_file=False,
                max_synthetic_rows=1000,
                keep_synthetic_files=False,
            )
            assert run is not None
            assert run.run_id  # has ID
            assert run.total_duration_ms >= 0

    def test_skip_flags(self):
        """Skip flags should skip categories."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = BenchmarkRunner(root)
            run = runner.run_all(
                skip_modules=True,
                skip_queries=True,
                skip_graph=True,
                skip_datasets=True,
                skip_agent=True,
                skip_large_file=True,
            )
            assert run is not None
            assert len(run.results) == 0

    def test_partial_result_on_error(self):
        """Runner should produce partial result even if one category fails."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = BenchmarkRunner(root)
            run = runner.run_all()
            # Should complete even if some categories have no data
            assert run is not None
            assert run.total_tasks >= 0

    def test_generate_reports(self):
        """Reports should be generated after run."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = BenchmarkRunner(root)
            runner.run_all(
                skip_graph=True,
                skip_datasets=True,
                skip_agent=True,
                skip_large_file=True,
            )
            reports = runner.generate_reports()
            assert len(reports) > 0

    def test_cache_recommendations_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = BenchmarkRunner(root)
            run = runner.run_all(
                skip_graph=True,
                skip_datasets=True,
                skip_agent=True,
                skip_large_file=True,
            )
            assert isinstance(run.cache_recommendations, list)
            assert isinstance(run.incremental_update_recommendations, list)

    def test_slowest_tracking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = BenchmarkRunner(root)
            run = runner.run_all(
                skip_graph=True,
                skip_datasets=True,
                skip_agent=True,
                skip_large_file=True,
            )
            assert isinstance(run.slowest_module, str)
            assert isinstance(run.slowest_query, str)
