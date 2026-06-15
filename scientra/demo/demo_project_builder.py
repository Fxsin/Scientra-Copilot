"""Demo Project Builder — create synthetic demo files."""

from __future__ import annotations
import shutil
from pathlib import Path
from typing import Any


class DemoProjectBuilder:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def create(self, force: bool = False) -> dict[str, Any]:
        src = self.root / "examples/demo_project/article_bundle/Demo_Paper_001"
        dest = self.root / "00_Inbox/article_bundles/demo/Demo_Paper_001"

        if not src.exists():
            return {"success": False, "error": f"Demo source not found: {src}"}

        if dest.exists():
            if force:
                shutil.rmtree(dest)
            else:
                return {"success": True, "message": "Demo already exists. Use --force to recreate.", "demo_dir": str(dest.relative_to(self.root))}

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)

        files = [f.name for f in dest.iterdir()]
        return {"success": True, "message": f"Demo project created with {len(files)} files.", "demo_dir": str(dest.relative_to(self.root)), "files": files}
