"""
Hybrid PDF Parser — Marker Adapter.

Encapsulates Marker (GitHub: VikParuchuri/marker) as a high-quality backup
markdown parser. Marker is NOT enabled by default — it serves as a fallback
or quality enhancement when OpenDataLoader markdown quality is insufficient.

Third-Party Notice:
  Marker (Datalab) — Copyright Vik Paruchuri / Endless Labs, Inc.
  Code licensed under GPL-3.0-or-later (SPDX: GPL-3.0-or-later)
  Model weights licensed under AI PUBS OPEN RAIL-M LICENSE (Modified)
  Original license: docs/licenses/marker/LICENSE
  Original model license: docs/licenses/marker/MODEL_LICENSE

  WARNING: Marker is GPL-3.0 licensed. It is an OPTIONAL dependency.
  Do NOT statically link or distribute Marker with Scientra Copilot.
  The adapter gracefully degrades when Marker is not installed.

Real API (from source):
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    from marker.output import save_output

    models = create_model_dict()
    config_parser = ConfigParser({})
    converter_cls = config_parser.get_converter_cls()
    converter = converter_cls(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    rendered = converter(pdf_path)
    save_output(rendered, output_dir, base_name)

Returns ParserOutput with status="skipped" if Marker is not installed.
No uncaught exceptions propagate.
"""

from __future__ import annotations

from pathlib import Path

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


def _is_marker_available() -> bool:
    """Check if Marker can be imported."""
    try:
        import importlib
        spec = importlib.util.find_spec("marker")
        if spec is None:
            return False
        # Verify key submodules exist
        for sub in ("marker.models", "marker.config.parser", "marker.output"):
            if importlib.util.find_spec(sub) is None:
                return False
        return True
    except Exception:
        return False


def run_marker(
    pdf_path: str | Path,
    paper_id: str,
    output_root: str | Path | None = None,
) -> ParserOutput:
    """Run Marker to produce high-quality markdown from a PDF.

    Marker (by VikParuchuri) uses a deep-learning pipeline:
    text extraction → layout detection → reading order → cleaning → markdown.

    This is used as a FALLBACK or quality enhancement only.
    Default is NOT enabled.

    Saves:
    - 02_Parse/markdown/marker/{paper_id}.md

    Returns ParserOutput with status="skipped" if Marker is not available.
    """
    pdf_path = Path(pdf_path)
    root = Path(output_root) if output_root else _resolve_root()

    if not _is_marker_available():
        return ParserOutput(
            parser_name="marker",
            status=ParserStatus.SKIPPED,
            output_type=OutputType.MARKDOWN,
            warnings=["Marker is not installed. Clone from github.com/VikParuchuri/marker and pip install -e ."],
        )

    if not pdf_path.exists():
        return ParserOutput(
            parser_name="marker",
            status=ParserStatus.FAILED,
            output_type=OutputType.MARKDOWN,
            errors=[f"PDF file not found: {pdf_path}"],
        )

    try:
        from marker.models import create_model_dict
        from marker.config.parser import ConfigParser
        from marker.output import save_output

        # Create model artifacts (downloads models on first run)
        # This may take time and GPU memory on first invocation
        models = create_model_dict()

        # Parse config from defaults (empty kwargs = use defaults)
        config_parser = ConfigParser({})

        # Get the converter class and instantiate
        converter_cls = config_parser.get_converter_cls()
        converter = converter_cls(
            config=config_parser.generate_config_dict(),
            artifact_dict=models,
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service(),
        )

        # Convert the PDF — returns a Document with .markdown property
        rendered = converter(str(pdf_path))

        # Save output to our 02_Parse directory
        output_dir = _ensure_dir(root / "02_Parse" / "markdown" / "marker")
        base_name = paper_id  # Marker will create {base_name}.md

        save_output(rendered, str(output_dir), base_name)

        expected_path = output_dir / f"{paper_id}.md"
        if expected_path.exists():
            return ParserOutput(
                parser_name="marker",
                status=ParserStatus.SUCCESS,
                output_type=OutputType.MARKDOWN,
                output_paths=[str(expected_path)],
                quality_score=0.85,
            )
        else:
            # save_output may have used a different naming convention
            # Try to find any .md file in the output dir
            md_files = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if md_files:
                latest = md_files[0]
                # Rename to paper_id.md
                expected_path.unlink(missing_ok=True)
                latest.rename(expected_path)
                return ParserOutput(
                    parser_name="marker",
                    status=ParserStatus.SUCCESS,
                    output_type=OutputType.MARKDOWN,
                    output_paths=[str(expected_path)],
                    quality_score=0.85,
                )

            return ParserOutput(
                parser_name="marker",
                status=ParserStatus.FAILED,
                output_type=OutputType.MARKDOWN,
                errors=["Marker completed but no markdown file was saved."],
            )

    except FileNotFoundError as fe:
        return ParserOutput(
            parser_name="marker",
            status=ParserStatus.FAILED,
            output_type=OutputType.MARKDOWN,
            errors=[f"Marker model files not found. Models are downloaded on first run. {fe}"],
        )
    except ImportError as ie:
        return ParserOutput(
            parser_name="marker",
            status=ParserStatus.SKIPPED,
            output_type=OutputType.MARKDOWN,
            warnings=[f"Marker dependency missing: {ie}"],
        )
    except Exception as exc:
        return ParserOutput(
            parser_name="marker",
            status=ParserStatus.FAILED,
            output_type=OutputType.MARKDOWN,
            errors=[f"Marker parsing failed: {type(exc).__name__}: {exc}"],
        )
