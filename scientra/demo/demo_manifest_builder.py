"""Demo Manifest Builder — generate demo_manifest.json."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any


class DemoManifestBuilder:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def build(self) -> dict:
        p = self.root / "examples/demo_project/demo_manifest.json"
        if p.exists():
            try: return json.loads(p.read_text(encoding="utf-8"))
            except: pass
        return {"project": "demo_project", "paper_id": "demo_paper_001", "synthetic": True}
