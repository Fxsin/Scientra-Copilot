"""Secret Scanner — scan for API keys/tokens (local only, no upload)."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [r"sk-[A-Za-z0-9]{20,}", r"OPENAI_API_KEY[=:]\s*[A-Za-z0-9\-]+", r"ANTHROPIC_API_KEY[=:]\s*[A-Za-z0-9\-]+", r"DEEPSEEK_API_KEY[=:]\s*[A-Za-z0-9\-]+", r"api_key:\s*sk-", r"authorization.*bearer\s+[A-Za-z0-9\-_\.]{10,}", r'api_key\s*=\s*"[^"]{10,}"']

SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".next", "venv", ".venv", "dist", "06_Index", "10_System/logs"}
SKIP_EXTS = {".pyc", ".pkl", ".bin", ".parquet", ".lance"}


class SecretScanner:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def scan(self) -> list[dict]:
        hits: list[dict] = []
        # Only scan text-like files for performance
        scan_exts = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".ts", ".tsx", ".js", ".jsx", ".toml", ".cfg", ".ini", ".sh", ".bat", ".env", ""}
        for f in self.root.rglob("*"):
            if not f.is_file(): continue
            if any(d in f.parts for d in SKIP_DIRS): continue
            if f.suffix not in scan_exts and f.suffix: continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for pat in SECRET_PATTERNS:
                for m in re.finditer(pat, content, re.IGNORECASE):
                    # Skip if in docs/reports that mention "do not commit" context
                    ctx = content[max(0, m.start() - 30):m.end() + 30]
                    if "example" in ctx.lower() or "placeholder" in ctx.lower() or "NEVER commit" in ctx:
                        continue
                    hits.append({"priority": "P0", "title": f"Potential secret: {m.group()[:30]}...", "detail": f"Found in {f.relative_to(self.root)}", "file": str(f.relative_to(self.root))})
        return hits
