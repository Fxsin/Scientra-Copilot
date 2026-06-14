"""
Hybrid PDF Parser — Availability Detection.

Checks which parsers are available in the current environment.
Import failures are silenced — individual parsers simply report as unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scientra.parsers.types import ParserAvailability


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    """Load a YAML file safely, returning empty dict on any failure."""
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _resolve_root() -> Path:
    """Resolve project root — same logic as server._resolve_root()."""
    import os
    env_root = os.environ.get("SCIENTRA_ROOT")
    if env_root:
        return Path(env_root)
    candidate = Path(__file__).resolve().parent
    for _ in range(5):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parents[2]


def check_parser_availability(root: str | Path | None = None) -> ParserAvailability:
    """Check which parsers are available in the current environment.

    Returns a ParserAvailability dataclass. Import failures are caught
    silently — individual parsers simply report as unavailable.

    Also checks workflow_config.yaml for hybrid_parser.enabled flag.
    """
    project_root = Path(root) if root else _resolve_root()

    # ── PyMuPDF (fitz) ──
    pymupdf_available = False
    try:
        import fitz  # noqa: F401
        pymupdf_available = True
    except ImportError:
        pass

    # ── OpenDataLoader PDF (package: opendataloader_pdf) ──
    # Requires: Python 3.10+, Java 11+
    opendataloader_available = False
    try:
        import importlib
        spec = importlib.util.find_spec("opendataloader_pdf")
        if spec is not None:
            opendataloader_available = True
    except Exception:
        pass

    # ── Marker (package: marker, PyPI: marker-pdf) ──
    # Requires: Python 3.10+, PyTorch, surya-ocr
    marker_available = False
    try:
        import importlib
        spec = importlib.util.find_spec("marker")
        if spec is not None:
            # Verify key submodules exist to confirm it's properly installed
            marker_models_spec = importlib.util.find_spec("marker.models")
            marker_config_spec = importlib.util.find_spec("marker.config.parser")
            marker_output_spec = importlib.util.find_spec("marker.output")
            if marker_models_spec and marker_config_spec and marker_output_spec:
                marker_available = True
    except Exception:
        pass

    # ── GROBID ──
    grobid_available = False
    try:
        config_path = project_root / "Config" / "grobid.yaml"
        if config_path.exists():
            config = _load_yaml_safe(config_path)
            if config:
                grobid_available = True
    except Exception:
        pass

    # ── Hybrid parser enabled check ──
    hybrid_parser_enabled = False
    try:
        wf_config_path = project_root / "Config" / "workflow_config.yaml"
        if wf_config_path.exists():
            wf_config = _load_yaml_safe(wf_config_path)
            hybrid_cfg = wf_config.get("hybrid_parser", {})
            if isinstance(hybrid_cfg, dict):
                hybrid_parser_enabled = hybrid_cfg.get("enabled", False)
    except Exception:
        pass

    return ParserAvailability(
        grobid_available=grobid_available,
        opendataloader_available=opendataloader_available,
        marker_available=marker_available,
        pymupdf_available=pymupdf_available,
        hybrid_parser_enabled=hybrid_parser_enabled,
    )
