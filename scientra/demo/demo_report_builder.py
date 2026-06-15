"""Demo Report Builder — generate demo project report."""

from __future__ import annotations
from pathlib import Path
from typing import Any


class DemoReportBuilder:
    def build(self, status: dict) -> str:
        lines = ["# Demo Project Report", "", "⚠️ ALL DATA IS SYNTHETIC — FOR FUNCTIONALITY TESTING ONLY", "",
                  "## Status", f"- Source files: {'✅' if status.get('src_files_exist') else '❌'}",
                  f"- Imported: {'✅' if status.get('imported') else '❌'}",
                  f"- Queries run: {'✅' if status.get('queries_run') else '❌'}",
                  f"- Validated: {'✅' if status.get('validated') else '❌'}",
                  "", "## Setup Instructions"]
        for instr in status.get("setup_instructions", []): lines.append(f"- `{instr}`")
        return "\n".join(lines)
