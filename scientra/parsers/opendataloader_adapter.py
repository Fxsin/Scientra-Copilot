"""
Hybrid PDF Parser — OpenDataLoader PDF Adapter.

Encapsulates opendataloader-pdf (GitHub: opendataloader-project/opendataloader-pdf)
for markdown, layout/bbox JSON, and table extraction.

Third-Party Notice:
  OpenDataLoader PDF — Copyright 2025–2026 Hancom, Inc.
  Licensed under Apache License 2.0 (SPDX: Apache-2.0)
  Original license: docs/licenses/opendataloader-pdf/LICENSE
  Original NOTICE:  docs/licenses/opendataloader-pdf/NOTICE

Real API (from source):
    import opendataloader_pdf
    opendataloader_pdf.convert(input_path="file.pdf", output_dir="out/", format="markdown,json")

Returns ParserOutput with status="skipped" if the dependency is missing.
No uncaught exceptions propagate.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from scientra.parsers.types import OutputType, ParserOutput, ParserStatus


def _resolve_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(5):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parents[2]


def _ensure_dir(target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    return target


# Known Java 11+ installation paths on Windows
_KNOWN_JAVA11_PATHS = [
    r"C:\Program Files\ojdkbuild\java-11-openjdk-11.0.15-1",
    r"C:\Program Files\ojdkbuild\java-11-openjdk-11.0.15.9-1",
    r"C:\Program Files\Eclipse Adoptium\jdk-11",
    r"C:\Program Files\Microsoft\jdk-11",
    r"C:\Program Files\Java\jdk-11",
]


def _find_java11_home() -> str | None:
    """Find a Java 11+ installation directory.

    Checks known paths first, then tries JAVA_HOME env var,
    then attempts to run 'java -version' to check.
    """
    import os as _os

    # 1. Check known paths
    for p in _KNOWN_JAVA11_PATHS:
        java_exe = Path(p) / "bin" / "java.exe"
        if java_exe.exists():
            return p

    # 2. Check JAVA_HOME env var
    env_home = _os.environ.get("JAVA_HOME", "")
    if env_home:
        java_exe = Path(env_home) / "bin" / "java.exe"
        if java_exe.exists():
            # Verify it's Java 11+
            try:
                import subprocess
                result = subprocess.run(
                    [str(java_exe), "-version"],
                    capture_output=True, text=True,
                    timeout=10,
                )
                version_output = result.stderr or result.stdout or ""
                if "11." in version_output or "17." in version_output or "21." in version_output:
                    return env_home
            except Exception:
                pass

    # 3. Try 'java' on PATH and check version
    try:
        import subprocess
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True, text=True,
            timeout=10,
        )
        version_output = result.stderr or result.stdout or ""
        if "11." in version_output or "17." in version_output or "21." in version_output:
            return _os.environ.get("JAVA_HOME", "") or None
    except Exception:
        pass

    return None


def _is_opendataloader_available() -> bool:
    """Check if opendataloader_pdf can be imported."""
    try:
        import importlib
        spec = importlib.util.find_spec("opendataloader_pdf")
        return spec is not None
    except Exception:
        return False


def run_opendataloader(
    pdf_path: str | Path,
    paper_id: str,
    output_root: str | Path | None = None,
) -> ParserOutput:
    """Run OpenDataLoader PDF to extract markdown, layout JSON, and tables.

    Uses the real opendataloader_pdf.convert() API which invokes a Java JAR.
    Requires Java 11+ at runtime.

    Saves:
    - 02_Parse/markdown/opendataloader/{paper_id}.md
    - 02_Parse/layout/opendataloader/{paper_id}.json
    - 02_Parse/tables/opendataloader/{paper_id}.json

    Returns ParserOutput with status="skipped" if OpenDataLoader is not available.
    """
    pdf_path = Path(pdf_path)
    root = Path(output_root) if output_root else _resolve_root()

    if not _is_opendataloader_available():
        return ParserOutput(
            parser_name="opendataloader",
            status=ParserStatus.SKIPPED,
            output_type=OutputType.MARKDOWN,
            warnings=["opendataloader_pdf is not installed. Clone from github.com/opendataloader-project/opendataloader-pdf and install the Python wrapper."],
        )

    if not pdf_path.exists():
        return ParserOutput(
            parser_name="opendataloader",
            status=ParserStatus.FAILED,
            output_type=OutputType.MARKDOWN,
            errors=[f"PDF file not found: {pdf_path}"],
        )

    try:
        import opendataloader_pdf
    except ImportError:
        return ParserOutput(
            parser_name="opendataloader",
            status=ParserStatus.SKIPPED,
            output_type=OutputType.MARKDOWN,
            warnings=["opendataloader_pdf module not found. Install Python wrapper from external/opendataloader-pdf/python/opendataloader-pdf/"],
        )

    # ── Ensure Java 11+ is on PATH ──
    # OpenDataLoader PDF requires Java 11+. The installed JAR (v2.4.7) was
    # compiled with class file version 55.0 (Java 11). If the system default
    # Java is older, we explicitly set JAVA_HOME to the Java 11 installation.
    _java11_home = _find_java11_home()
    if _java11_home:
        import os as _os
        _os.environ.setdefault("JAVA_HOME", _java11_home)
        # Also prepend to PATH so the 'java' command picks it up
        _java_bin = str(Path(_java11_home) / "bin")
        if _java_bin not in _os.environ.get("PATH", ""):
            _os.environ["PATH"] = _java_bin + _os.pathsep + _os.environ.get("PATH", "")

    output_paths: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    # Use a temporary directory for raw OpenDataLoader output
    with tempfile.TemporaryDirectory(prefix="odl_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        try:
            # Real API: opendataloader_pdf.convert(input_path, output_dir, format)
            opendataloader_pdf.convert(
                input_path=str(pdf_path),
                output_dir=str(tmp_path),
                format="markdown,json",
            )
        except Exception as e:
            error_msg = str(e)
            if "Java" in error_msg or "java" in error_msg:
                return ParserOutput(
                    parser_name="opendataloader",
                    status=ParserStatus.SKIPPED,
                    output_type=OutputType.MARKDOWN,
                    warnings=[f"OpenDataLoader PDF requires Java 11+. Current Java not compatible: {error_msg}"],
                )
            return ParserOutput(
                parser_name="opendataloader",
                status=ParserStatus.FAILED,
                output_type=OutputType.MARKDOWN,
                errors=[f"OpenDataLoader convert() failed: {type(e).__name__}: {error_msg}"],
            )

        # OpenDataLoader names output files by input basename: {stem}.md, {stem}.json
        stem = pdf_path.stem

        # ── Copy markdown ──
        md_src = tmp_path / f"{stem}.md"
        if md_src.exists():
            md_dir = _ensure_dir(root / "02_Parse" / "markdown" / "opendataloader")
            md_dst = md_dir / f"{paper_id}.md"
            shutil.copy2(md_src, md_dst)
            output_paths.append(str(md_dst))
        else:
            warnings.append("No markdown output produced by OpenDataLoader PDF.")

        # ── Copy layout JSON ──
        json_src = tmp_path / f"{stem}.json"
        if json_src.exists():
            layout_dir = _ensure_dir(root / "02_Parse" / "layout" / "opendataloader")
            layout_dst = layout_dir / f"{paper_id}.json"
            shutil.copy2(json_src, layout_dst)
            output_paths.append(str(layout_dst))

            # ── Extract tables from JSON if present ──
            try:
                data = json.loads(json_src.read_text(encoding="utf-8"))
                tables = _extract_tables_from_odl_json(data)
                if tables:
                    tables_dir = _ensure_dir(root / "02_Parse" / "tables" / "opendataloader")
                    tables_dst = tables_dir / f"{paper_id}.json"
                    tables_dst.write_text(json.dumps(tables, indent=2, ensure_ascii=False), encoding="utf-8")
                    output_paths.append(str(tables_dst))
            except Exception as e:
                warnings.append(f"Table extraction from layout JSON skipped: {e}")
        else:
            warnings.append("No layout JSON output produced by OpenDataLoader PDF.")

    status = ParserStatus.SUCCESS if output_paths else ParserStatus.FALLBACK
    return ParserOutput(
        parser_name="opendataloader",
        status=status,
        output_type=OutputType.MARKDOWN,
        output_paths=output_paths,
        quality_score=0.8 if len(output_paths) >= 2 else 0.5,
        warnings=warnings,
        errors=errors,
    )


def _extract_tables_from_odl_json(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract table data from OpenDataLoader JSON output.

    OpenDataLoader JSON structure includes:
    - "elements" or "blocks" array with type/bbox/text fields
    - Tables are elements with type == "table"
    """
    tables: list[dict[str, Any]] = []

    # Try common structures
    elements = data.get("elements") or data.get("blocks") or data.get("content") or []

    if isinstance(elements, list):
        for el in elements:
            if isinstance(el, dict):
                el_type = el.get("type", el.get("category", "")).lower()
                if el_type in ("table", "table_block", "tabular"):
                    tables.append({
                        "type": el_type,
                        "bbox": el.get("bbox", el.get("bounding_box", [])),
                        "page": el.get("page", el.get("page_num")),
                        "text": el.get("text", el.get("content", "")),
                        "rows": el.get("rows", el.get("table_rows", [])),
                    })

    # If no explicit tables found but there are pages with tables
    if not tables:
        pages = data.get("pages", [])
        if isinstance(pages, list):
            for page in pages:
                if isinstance(page, dict):
                    page_elements = page.get("elements", page.get("blocks", []))
                    for el in page_elements:
                        if isinstance(el, dict) and el.get("type", "").lower() in ("table", "table_block"):
                            tables.append({
                                "type": "table",
                                "bbox": el.get("bbox", []),
                                "page": page.get("page", page.get("number")),
                                "text": el.get("text", ""),
                                "rows": el.get("rows", []),
                            })

    return tables
