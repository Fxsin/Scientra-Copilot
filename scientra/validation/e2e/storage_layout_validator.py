"""Storage Layout Validator — check v3 compliance and DB/DB_v2 residue."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any

V3_DIRS = ["00_Inbox", "01_Sources", "02_Parse", "03_Assets", "04_Corpus",
           "05_Knowledge", "06_Index", "07_Agents", "08_Projects", "09_Exports", "10_System"]


class StorageLayoutValidator:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def validate(self) -> dict[str, Any]:
        issues, warnings = [], []

        # Check v3 dirs exist
        for d in V3_DIRS:
            if not (self.root / d).exists():
                issues.append(f"Missing v3 directory: {d}")

        # Check DB/DB_v2 residue
        db_v2_hits = self._scan_for_db_v2()
        for hit in db_v2_hits:
            warnings.append(f"DB/DB_v2 reference in: {hit}")

        # Check 03_Assets structure
        if not (self.root / "03_Assets/ai").exists():
            warnings.append("03_Assets/ai/ missing — AI enrichment outputs may not exist")

        # Check 05_Knowledge structure
        if not (self.root / "05_Knowledge/unified_evidence_graph").exists():
            warnings.append("Unified evidence graph directory missing")

        # Check 06_Index lancedb
        ldb = self.root / "06_Index/vector/lancedb"
        if not ldb.exists():
            warnings.append("06_Index/vector/lancedb missing — vector search unavailable")

        # Check 10_System writability
        log_dir = self.root / "10_System/logs"
        if log_dir.exists():
            try:
                (log_dir / ".write_test").touch()
                (log_dir / ".write_test").unlink()
            except Exception:
                issues.append("10_System/logs not writable")

        return {
            "v3_compliant": len(issues) == 0,
            "directories_checked": len(V3_DIRS),
            "issues": issues,
            "warnings": warnings,
            "db_v2_hits": db_v2_hits,
            "db_v2_clean": len(db_v2_hits) == 0,
        }

    def _scan_for_db_v2(self) -> list[str]:
        hits: list[str] = []
        # Scan Python source files
        for py_file in self.root.glob("scientra/**/*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                if "DB/DB_v2" in content:
                    hits.append(str(py_file.relative_to(self.root)))
            except Exception:
                pass
        # Scan Scripts
        for script in self.root.glob("Scripts/*.py"):
            try:
                content = script.read_text(encoding="utf-8", errors="replace")
                if "DB/DB_v2" in content:
                    hits.append(str(script.relative_to(self.root)))
            except Exception:
                pass
        # Scan reports
        for report in self.root.glob("reports/*.md"):
            try:
                content = report.read_text(encoding="utf-8", errors="replace")
                if "DB/DB_v2" in content:
                    hits.append(str(report.relative_to(self.root)))
            except Exception:
                pass
        return hits
