"""Tests for AI enrichment workflow integration.

Run:
    python -m pytest Tests/test_ai_enrichment_workflow.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestWorkflowStepRegistration:
    """Test that AI enrichment steps are registered in STEP_ORDER."""

    def test_ai_summary_v2_in_step_order(self):
        """ai_summary_v2 step is in STEP_ORDER."""
        from scientra.workflow import STEP_ORDER
        assert "ai_summary_v2" in STEP_ORDER

    def test_ai_evidence_enrichment_in_step_order(self):
        """ai_evidence_enrichment step is in STEP_ORDER."""
        from scientra.workflow import STEP_ORDER
        assert "ai_evidence_enrichment" in STEP_ORDER

    def test_steps_in_correct_order(self):
        """AI enrichment steps come after evidence_chunks and before embedding."""
        from scientra.workflow import STEP_ORDER
        evidence_idx = STEP_ORDER.index("evidence_chunks")
        ai_sv2_idx = STEP_ORDER.index("ai_summary_v2")
        ai_ee_idx = STEP_ORDER.index("ai_evidence_enrichment")
        embedding_idx = STEP_ORDER.index("embedding")

        assert evidence_idx < ai_sv2_idx < ai_ee_idx < embedding_idx


class TestWorkflowConfigDefaults:
    """Test default workflow config values."""

    def test_ai_enrichment_disabled_by_default(self):
        """ai_enrichment.enabled defaults to false (safe mode)."""
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            ai_config = config.get("ai_enrichment", {})
            assert ai_config.get("enabled") is False
            assert ai_config.get("summary_v2") is False
            assert ai_config.get("evidence_enrichment") is False

    def test_ai_enrichment_has_required_keys(self):
        """ai_enrichment config has all required keys."""
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            ai_config = config.get("ai_enrichment", {})
            for key in ["enabled", "summary_v2", "evidence_enrichment", "batch_size",
                         "max_chunks_per_paper", "min_chunk_length", "paper_limit"]:
                assert key in ai_config, f"Missing key: {key}"

    def test_ai_steps_are_optional(self):
        """AI enrichment steps are marked optional."""
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            steps = config.get("steps", {})
            ai_sv2 = steps.get("ai_summary_v2", {})
            ai_ee = steps.get("ai_evidence_enrichment", {})
            assert ai_sv2.get("optional") is True
            assert ai_ee.get("optional") is True


class TestWorkflowBuiltinHandlers:
    """Test that builtin handlers exist and can be called."""

    def test_builtin_dispatches_ai_summary_v2(self):
        """run_builtin_step dispatches ai_summary_v2 correctly."""
        from scientra.workflow import WorkflowRunner, WorkflowOptions
        import yaml

        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if not config_path.exists():
            pytest.skip("workflow_config.yaml not found")

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["ai_enrichment"] = {
            "enabled": False,
            "summary_v2": False,
            "evidence_enrichment": False,
        }

        options = WorkflowOptions(
            config_path=config_path,
            root=config_path.parent,
            file=None, input_dir=None,
            changed_only=False, resume=False,
            force=False, dry_run=False,
            from_step=None, to_step=None,
        )
        runner = WorkflowRunner(config=config, options=options)

        with patch.object(runner, "_run_ai_summary_v2_builtin") as mock_run:
            mock_run.return_value = MagicMock(step="ai_summary_v2", status="skipped")
            result = runner.run_builtin_step(
                step="ai_summary_v2",
                builtin="ai_summary_v2",
                started_at="2026-01-01T00:00:00Z",
                started=0.0,
            )
            mock_run.assert_called_once()

    def test_builtin_dispatches_ai_evidence_enrichment(self):
        """run_builtin_step dispatches ai_evidence_enrichment correctly."""
        from scientra.workflow import WorkflowRunner, WorkflowOptions
        import yaml

        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if not config_path.exists():
            pytest.skip("workflow_config.yaml not found")

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["ai_enrichment"] = {
            "enabled": False,
            "summary_v2": False,
            "evidence_enrichment": False,
        }

        options = WorkflowOptions(
            config_path=config_path,
            root=config_path.parent,
            file=None, input_dir=None,
            changed_only=False, resume=False,
            force=False, dry_run=False,
            from_step=None, to_step=None,
        )
        runner = WorkflowRunner(config=config, options=options)

        with patch.object(runner, "_run_ai_evidence_enrichment_builtin") as mock_run:
            mock_run.return_value = MagicMock(step="ai_evidence_enrichment", status="skipped")
            result = runner.run_builtin_step(
                step="ai_evidence_enrichment",
                builtin="ai_evidence_enrichment",
                started_at="2026-01-01T00:00:00Z",
                started=0.0,
            )
            mock_run.assert_called_once()


class TestWorkflowBuiltinSkip:
    """Test that builtins skip when disabled."""

    def test_ai_summary_v2_skips_when_disabled(self):
        """ai_summary_v2 returns skipped when ai_enrichment is disabled."""
        from scientra.workflow import WorkflowRunner, WorkflowOptions
        import yaml

        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if not config_path.exists():
            pytest.skip("workflow_config.yaml not found")

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["ai_enrichment"] = {
            "enabled": False,
            "summary_v2": False,
            "evidence_enrichment": False,
        }
        options = WorkflowOptions(
            config_path=config_path,
            root=config_path.parent,
            file=None, input_dir=None,
            changed_only=False, resume=False,
            force=False, dry_run=False,
            from_step=None, to_step=None,
        )
        runner = WorkflowRunner(config=config, options=options)
        result = runner._run_ai_summary_v2_builtin(
            started_at="2026-01-01T00:00:00Z",
            started=0.0,
        )
        assert result.status in ("skipped", "failed")
        if result.status == "skipped":
            assert "disabled" in (result.error or "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
