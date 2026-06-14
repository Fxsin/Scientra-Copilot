"""Tests for Gap & Hypothesis workflow integration.

Run: python -m pytest Tests/test_gap_hypothesis_workflow.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestStepRegistration:
    def test_gap_in_step_order(self):
        from scientra.workflow import STEP_ORDER
        assert "ai_gap_extraction" in STEP_ORDER

    def test_hypothesis_in_step_order(self):
        from scientra.workflow import STEP_ORDER
        assert "ai_hypothesis_generation" in STEP_ORDER

    def test_correct_order(self):
        from scientra.workflow import STEP_ORDER
        ee_idx = STEP_ORDER.index("ai_evidence_enrichment")
        gap_idx = STEP_ORDER.index("ai_gap_extraction")
        hyp_idx = STEP_ORDER.index("ai_hypothesis_generation")
        emb_idx = STEP_ORDER.index("embedding")
        assert ee_idx < gap_idx < hyp_idx < emb_idx


class TestConfigDefaults:
    def test_defaults_disabled(self):
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            ai = config.get("ai_enrichment", {})
            assert ai.get("gap_extraction") is False
            assert ai.get("hypothesis_generation") is False

    def test_has_config_keys(self):
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            ai = config.get("ai_enrichment", {})
            for key in ["gap_extraction", "hypothesis_generation", "max_gaps_per_paper", "max_hypotheses_per_paper"]:
                assert key in ai, f"Missing: {key}"

    def test_steps_optional(self):
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            steps = config.get("steps", {})
            assert steps.get("ai_gap_extraction", {}).get("optional") is True
            assert steps.get("ai_hypothesis_generation", {}).get("optional") is True


class TestBuiltinDispatch:
    def test_dispatches_gap(self):
        from scientra.workflow import WorkflowRunner, WorkflowOptions
        import yaml

        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if not config_path.exists():
            pytest.skip("config not found")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["ai_enrichment"] = {"enabled": False, "gap_extraction": False, "hypothesis_generation": False}
        options = WorkflowOptions(config_path=config_path, root=config_path.parent,
                                  file=None, input_dir=None, changed_only=False,
                                  resume=False, force=False, dry_run=False,
                                  from_step=None, to_step=None)
        runner = WorkflowRunner(config=config, options=options)

        with patch.object(runner, "_run_ai_gap_extraction_builtin") as m:
            m.return_value = MagicMock(step="ai_gap_extraction", status="skipped")
            runner.run_builtin_step("ai_gap_extraction", "ai_gap_extraction", "2026-01-01T00:00:00Z", 0.0)
            m.assert_called_once()

    def test_dispatches_hypothesis(self):
        from scientra.workflow import WorkflowRunner, WorkflowOptions
        import yaml

        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if not config_path.exists():
            pytest.skip("config not found")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["ai_enrichment"] = {"enabled": False, "gap_extraction": False, "hypothesis_generation": False}
        options = WorkflowOptions(config_path=config_path, root=config_path.parent,
                                  file=None, input_dir=None, changed_only=False,
                                  resume=False, force=False, dry_run=False,
                                  from_step=None, to_step=None)
        runner = WorkflowRunner(config=config, options=options)

        with patch.object(runner, "_run_ai_hypothesis_generation_builtin") as m:
            m.return_value = MagicMock(step="ai_hypothesis_generation", status="skipped")
            runner.run_builtin_step("ai_hypothesis_generation", "ai_hypothesis_generation", "2026-01-01T00:00:00Z", 0.0)
            m.assert_called_once()

    def test_gap_skips_when_disabled(self):
        from scientra.workflow import WorkflowRunner, WorkflowOptions
        import yaml

        config_path = Path(__file__).resolve().parent.parent / "Config" / "workflow_config.yaml"
        if not config_path.exists():
            pytest.skip("config not found")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["ai_enrichment"] = {"enabled": False, "gap_extraction": False, "hypothesis_generation": False}
        options = WorkflowOptions(config_path=config_path, root=config_path.parent,
                                  file=None, input_dir=None, changed_only=False,
                                  resume=False, force=False, dry_run=False,
                                  from_step=None, to_step=None)
        runner = WorkflowRunner(config=config, options=options)
        result = runner._run_ai_gap_extraction_builtin("2026-01-01T00:00:00Z", 0.0)
        assert result.status in ("skipped", "failed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
