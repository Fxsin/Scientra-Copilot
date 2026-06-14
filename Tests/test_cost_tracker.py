"""Tests for the Cost Tracker — usage logging and summary.

Run:
    python -m pytest Tests/test_cost_tracker.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestLogUsage:
    """Test the log_usage function."""

    def test_log_writes_record(self, tmp_path):
        """log_usage writes a JSONL record to the log file."""
        from scientra.ai.cost_tracker import log_usage, USAGE_LOG_DIR

        # Override the log directory for testing
        with patch("scientra.ai.cost_tracker.USAGE_LOG_DIR", tmp_path / "ai_usage"):
            log_usage(
                timestamp="2026-06-14T10:00:00Z",
                provider="deepseek",
                model="deepseek-chat",
                task_name="summary",
                paper_id="paper123",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_estimate=0.000082,
                success=True,
            )

            # Verify the file was created
            log_files = list((tmp_path / "ai_usage").glob("usage_*.jsonl"))
            assert len(log_files) == 1

            # Verify content
            content = log_files[0].read_text().strip().split("\n")
            assert len(content) == 1
            record = json.loads(content[0])
            assert record["provider"] == "deepseek"
            assert record["model"] == "deepseek-chat"
            assert record["task_name"] == "summary"
            assert record["paper_id"] == "paper123"
            assert record["input_tokens"] == 100
            assert record["output_tokens"] == 50
            assert record["total_tokens"] == 150
            assert record["cost_estimate"] == 0.000082
            assert record["success"] is True

    def test_log_appends_multiple_records(self, tmp_path):
        """Multiple log_usage calls append to the same file."""
        from scientra.ai.cost_tracker import log_usage

        with patch("scientra.ai.cost_tracker.USAGE_LOG_DIR", tmp_path / "ai_usage"):
            for i in range(5):
                log_usage(
                    timestamp=f"2026-06-14T10:00:0{i}Z",
                    provider="openai",
                    model="gpt-4o",
                    task_name="agent_chat",
                    paper_id=f"paper_{i}",
                    input_tokens=10 * i,
                    output_tokens=5 * i,
                    total_tokens=15 * i,
                    cost_estimate=0.0001 * i,
                    success=True,
                )

            log_files = list((tmp_path / "ai_usage").glob("usage_*.jsonl"))
            assert len(log_files) == 1
            content = log_files[0].read_text().strip().split("\n")
            assert len(content) == 5

    def test_log_failure_record(self, tmp_path):
        """Failed calls are also logged."""
        from scientra.ai.cost_tracker import log_usage

        with patch("scientra.ai.cost_tracker.USAGE_LOG_DIR", tmp_path / "ai_usage"):
            log_usage(
                timestamp="2026-06-14T10:00:00Z",
                provider="anthropic",
                model="claude-sonnet-4-6",
                task_name="summary",
                paper_id="paper_fail",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_estimate=0.0,
                success=False,
                error="Rate limit exceeded",
            )

            log_files = list((tmp_path / "ai_usage").glob("usage_*.jsonl"))
            content = log_files[0].read_text().strip()
            record = json.loads(content)
            assert record["success"] is False
            assert record["error"] == "Rate limit exceeded"
            assert record["cost_estimate"] == 0.0

    def test_log_never_raises_on_disk_full(self, tmp_path):
        """log_usage silently handles write errors."""
        from scientra.ai.cost_tracker import log_usage

        # Create a directory where we can't write a file (path is a directory)
        bad_dir = tmp_path / "ai_usage"
        bad_dir.mkdir(parents=True)
        # Create a file with the same name as what the log would use, but make it a directory
        log_path = bad_dir / f"usage_{datetime.now(timezone.utc).strftime('%Y-%m')}.jsonl"
        log_path.mkdir()  # Make it a directory so open() fails

        with patch("scientra.ai.cost_tracker.USAGE_LOG_DIR", bad_dir):
            # Should not raise
            log_usage(
                timestamp="2026-06-14T10:00:00Z",
                provider="deepseek",
                model="deepseek-chat",
                task_name="test",
                paper_id="",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_estimate=0.0,
                success=True,
            )


class TestGetUsageSummary:
    """Test the get_usage_summary function."""

    def test_empty_summary(self, tmp_path):
        """Empty log directory returns zeroed summary."""
        from scientra.ai.cost_tracker import get_usage_summary

        empty_dir = tmp_path / "empty_usage"
        empty_dir.mkdir(parents=True)

        with patch("scientra.ai.cost_tracker.USAGE_LOG_DIR", empty_dir):
            summary = get_usage_summary()
            assert summary["total_calls"] == 0
            assert summary["total_cost"] == 0.0
            assert summary["by_provider"] == {}
            assert summary["by_task"] == {}
            assert summary["daily"] == {}

    def test_summary_aggregates_correctly(self, tmp_path):
        """Summary correctly aggregates multiple records."""
        from scientra.ai.cost_tracker import log_usage, get_usage_summary, USAGE_LOG_DIR

        with patch("scientra.ai.cost_tracker.USAGE_LOG_DIR", tmp_path / "ai_usage"):
            # Log two successful calls
            for i in range(2):
                log_usage(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    provider="deepseek",
                    model="deepseek-chat",
                    task_name="summary",
                    paper_id=f"p{i}",
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                    cost_estimate=0.0001,
                    success=True,
                )

            # Log one failed call
            log_usage(
                timestamp=datetime.now(timezone.utc).isoformat(),
                provider="openai",
                model="gpt-4o",
                task_name="agent_chat",
                paper_id="p3",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_estimate=0.0,
                success=False,
                error="timeout",
            )

            summary = get_usage_summary()
            assert summary["total_calls"] == 3
            assert summary["total_success"] == 2
            assert summary["total_failure"] == 1
            assert summary["total_cost"] == pytest.approx(0.0002, abs=0.00001)
            assert summary["total_input_tokens"] == 200
            assert summary["total_output_tokens"] == 100

            # By provider
            assert "deepseek" in summary["by_provider"]
            assert summary["by_provider"]["deepseek"]["calls"] == 2
            assert "openai" in summary["by_provider"]

            # By task
            assert "summary" in summary["by_task"]
            assert summary["by_task"]["summary"]["calls"] == 2
            assert "agent_chat" in summary["by_task"]


class TestMonthlyFileNaming:
    """Test that logs are organized by YYYY-MM."""

    def test_file_naming_by_month(self, tmp_path):
        """Logs for the same month go to the same file."""
        from scientra.ai.cost_tracker import log_usage

        with patch("scientra.ai.cost_tracker.USAGE_LOG_DIR", tmp_path / "ai_usage"):
            # Log two records in the same month
            log_usage(
                timestamp="2026-06-14T10:00:00Z",
                provider="deepseek",
                model="deepseek-chat",
                task_name="summary",
                paper_id="p1",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cost_estimate=0.00001,
                success=True,
            )
            log_usage(
                timestamp="2026-06-15T10:00:00Z",
                provider="deepseek",
                model="deepseek-chat",
                task_name="summary",
                paper_id="p2",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cost_estimate=0.00001,
                success=True,
            )

            log_files = list((tmp_path / "ai_usage").glob("usage_*.jsonl"))
            assert len(log_files) == 1
            assert "usage_2026-06.jsonl" in str(log_files[0])

            content = log_files[0].read_text().strip().split("\n")
            assert len(content) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
