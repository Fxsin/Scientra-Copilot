"""Demo Schema — P6.2 type definitions."""

from __future__ import annotations
from typing import Any


def make_demo_manifest() -> dict:
    return {"project": "demo_project", "paper_id": "demo_paper_001", "title": "Demo Plant Stress Response Study", "year": 2026, "synthetic": True, "warning": "ALL DATA IS SYNTHETIC — FOR FUNCTIONALITY TESTING ONLY"}


def make_demo_status(files_exist: bool = False, imported: bool = False, pipeline_run: bool = False, validated: bool = False) -> dict:
    return {"files_exist": files_exist, "imported": imported, "pipeline_run": pipeline_run, "validated": validated, "ready_for_demo": files_exist}
