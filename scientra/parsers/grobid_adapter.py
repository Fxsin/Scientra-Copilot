"""
Hybrid PDF Parser — GROBID Adapter.

Wraps the existing GROBID Docker-based metadata extraction.
This adapter does NOT replace the current GROBID flow — it provides a
programmatic wrapper that returns ParserOutput for the hybrid pipeline.

The existing GROBID process (Docker container + Scripts/pdf_parser.py)
continues to run as the primary metadata source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

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


def _load_grobid_config(root: Path) -> dict[str, Any]:
    """Load GROBID Docker config from Config/grobid.yaml."""
    config_path = root / "Config" / "grobid.yaml"
    if not config_path.exists():
        return {}
    try:
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _check_grobid_health(base_url: str) -> bool:
    """Check if GROBID Docker container is running."""
    try:
        import urllib.request
        url = f"{base_url}/api/isalive"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def locate_existing_grobid_outputs(
    paper_id: str,
    output_root: str | Path | None = None,
) -> dict[str, Path | None]:
    """Locate existing GROBID output files for a paper without calling GROBID.

    This function ONLY reads existing files — it does NOT trigger a new
    GROBID API call. It is safe to call at any time.

    Returns a dict with keys:
        - tei_xml: Path to TEI XML file, or None
        - metadata_json: Path to metadata JSON file, or None
        - text: Path to raw text file, or None
    """
    root = Path(output_root) if output_root else _resolve_root()

    result: dict[str, Path | None] = {
        "tei_xml": None,
        "metadata_json": None,
        "text": None,
    }

    # Check for TEI XML (saved by legacy GROBID flow or hybrid parser)
    tei_path = root / "02_Parse" / "text" / "grobid" / f"{paper_id}.tei.xml"
    if tei_path.exists():
        result["tei_xml"] = tei_path

    # Check for metadata JSON (saved by hybrid parser)
    meta_path = root / "02_Parse" / "reports" / "grobid" / f"{paper_id}_metadata.json"
    if meta_path.exists():
        result["metadata_json"] = meta_path

    # Check for raw text (legacy path)
    text_path = root / "02_Parse" / "text" / f"{paper_id}.txt"
    if text_path.exists():
        result["text"] = text_path

    # Also check legacy GROBID output in 02_Parse/text/ directly
    legacy_tei = root / "02_Parse" / "text" / f"{paper_id}.tei.xml"
    if legacy_tei.exists() and result["tei_xml"] is None:
        result["tei_xml"] = legacy_tei

    return result


def read_grobid_metadata_if_available(
    paper_id: str,
    output_root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Read GROBID metadata from existing outputs without calling GROBID.

    Looks for:
    1. 02_Parse/reports/grobid/{paper_id}_metadata.json (hybrid parser output)
    2. 02_Parse/text/grobid/{paper_id}.tei.xml (legacy GROBID output — parsed on the fly)

    Returns the metadata dict if found, None otherwise.
    Never throws — all errors are caught and result in None.
    """
    root = Path(output_root) if output_root else _resolve_root()

    # Try JSON metadata first (fast path)
    meta_json_path = root / "02_Parse" / "reports" / "grobid" / f"{paper_id}_metadata.json"
    if meta_json_path.exists():
        try:
            return json.loads(meta_json_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Try TEI XML (legacy path — parse on the fly)
    tei_path = root / "02_Parse" / "text" / "grobid" / f"{paper_id}.tei.xml"
    if not tei_path.exists():
        tei_path = root / "02_Parse" / "text" / f"{paper_id}.tei.xml"

    if tei_path.exists():
        try:
            xml_data = tei_path.read_text(encoding="utf-8")
            metadata = _parse_tei_metadata(xml_data)
            if metadata:
                return metadata
        except Exception:
            pass

    return None


def run_grobid_metadata(
    pdf_path: str | Path,
    paper_id: str,
    output_root: str | Path | None = None,
) -> ParserOutput:
    """Extract metadata using GROBID Docker service.

    This function performs a live GROBID API call. It is intended for use
    within the hybrid parser pipeline, NOT as a replacement for the existing
    batch GROBID process.

    Returns ParserOutput with status="skipped" if GROBID is not reachable.
    """
    pdf_path = Path(pdf_path)
    root = Path(output_root) if output_root else _resolve_root()

    config = _load_grobid_config(root)
    base_url = config.get("grobid_base_url", "http://localhost:18070")

    if not _check_grobid_health(base_url):
        return ParserOutput(
            parser_name="grobid",
            status=ParserStatus.SKIPPED,
            output_type=OutputType.METADATA,
            warnings=[f"GROBID is not reachable at {base_url}. Ensure the Docker container is running."],
        )

    if not pdf_path.exists():
        return ParserOutput(
            parser_name="grobid",
            status=ParserStatus.FAILED,
            output_type=OutputType.METADATA,
            errors=[f"PDF file not found: {pdf_path}"],
        )

    try:
        import urllib.request
        import urllib.error

        process_url = f"{base_url}/api/processFulltextDocument"
        consolidate_header = config.get("request", {}).get("consolidateHeader", 0)
        consolidate_citations = config.get("request", {}).get("consolidateCitations", 0)

        # Prepare form data with parameters
        from urllib.parse import urlencode

        params = urlencode({
            "consolidateHeader": str(consolidate_header),
            "consolidateCitations": str(consolidate_citations),
            "includeRawCitations": "0",
            "includeRawAffiliations": "0",
        })

        boundary = "----FormBoundary" + "7MA4YWxkTrZu0gW"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="input"; filename="paper.pdf"\r\n'
            f"Content-Type: application/pdf\r\n\r\n"
        )

        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        body_bytes = body.encode("utf-8") + pdf_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            f"{process_url}?{params}",
            data=body_bytes,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/xml",
            },
            method="POST",
        )

        timeout = config.get("grobid_timeout_seconds", 120)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_data = resp.read().decode("utf-8", errors="replace")

        # Parse TEI XML for metadata
        metadata = _parse_tei_metadata(xml_data)

        # Save GROBID output
        output_paths: list[str] = []

        # Save raw TEI XML
        tei_dir = _ensure_dir(root / "02_Parse" / "text" / "grobid")
        tei_path = tei_dir / f"{paper_id}.tei.xml"
        tei_path.write_text(xml_data, encoding="utf-8")

        # Save extracted metadata JSON
        meta_dir = _ensure_dir(root / "02_Parse" / "reports" / "grobid")
        meta_path = meta_dir / f"{paper_id}_metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        output_paths.extend([str(tei_path), str(meta_path)])

        quality_score = _score_metadata_quality(metadata)

        return ParserOutput(
            parser_name="grobid",
            status=ParserStatus.SUCCESS if metadata else ParserStatus.FALLBACK,
            output_type=OutputType.METADATA,
            output_paths=output_paths,
            quality_score=quality_score,
        )

    except urllib.error.URLError as e:
        return ParserOutput(
            parser_name="grobid",
            status=ParserStatus.FAILED,
            output_type=OutputType.METADATA,
            errors=[f"GROBID connection failed: {e}"],
        )
    except Exception as exc:
        return ParserOutput(
            parser_name="grobid",
            status=ParserStatus.FAILED,
            output_type=OutputType.METADATA,
            errors=[f"GROBID parsing failed: {type(exc).__name__}: {exc}"],
        )


def _parse_tei_metadata(xml_data: str) -> dict[str, Any]:
    """Extract metadata from GROBID TEI XML output.

    Uses a lightweight XML parser to avoid external dependencies.
    """
    try:
        from xml.etree import ElementTree as ET
    except ImportError:
        return {}

    try:
        # Strip namespaces for easier parsing
        root = ET.fromstring(xml_data)

        ns = {"tei": "http://www.tei-c.org/ns/1.0"}
        # Also try without namespace
        if root.tag.startswith("{"):
            # Has namespace
            actual_ns = root.tag.split("}")[0].strip("{")
            ns = {"tei": actual_ns}
        else:
            ns = {"tei": ""}

        def _find(el, tag):
            """Find element with or without namespace."""
            result = el.find(f"{{{ns['tei']}}}{tag}")
            if result is None and ns["tei"]:
                result = el.find(tag)
            return result

        def _findall(el, tag):
            result = el.findall(f"{{{ns['tei']}}}{tag}")
            if not result and ns["tei"]:
                result = el.findall(tag)
            return result

        def _text(el, tag):
            found = _find(el, tag)
            return found.text.strip() if found is not None and found.text else ""

        # Title
        title_stmt = _find(root, "titleStmt")
        title = ""
        if title_stmt is not None:
            title = _text(title_stmt, "title")

        # Authors
        authors: list[str] = []
        source_desc = _find(root, "sourceDesc")
        if source_desc is not None:
            bibl = _find(source_desc, "biblStruct")
            if bibl is None:
                bibl = source_desc
            for analytic in _findall(bibl if bibl is not None else source_desc, "analytic"):
                if analytic is None:
                    continue
                for author_el in _findall(analytic, "author"):
                    pers_name = _find(author_el, "persName")
                    if pers_name is not None:
                        forename = _text(pers_name, "forename")
                        surname = _text(pers_name, "surname")
                        if forename and surname:
                            authors.append(f"{forename} {surname}")
                        elif surname:
                            authors.append(surname)

        # If no authors found from analytic, try author elements in titleStmt
        if not authors and title_stmt is not None:
            for author_el in _findall(title_stmt, "author"):
                pers_name = _find(author_el, "persName")
                if pers_name is not None:
                    forename = _text(pers_name, "forename")
                    surname = _text(pers_name, "surname")
                    if forename and surname:
                        authors.append(f"{forename} {surname}")
                    elif surname:
                        authors.append(surname)

        # Abstract
        abstract = ""
        profile_desc = _find(root, "profileDesc")
        if profile_desc is not None:
            abstract_el = _find(profile_desc, "abstract")
            if abstract_el is not None:
                parts = []
                for p in _findall(abstract_el, "p"):
                    if p.text:
                        parts.append(p.text.strip())
                abstract = " ".join(parts)

        # DOI
        doi = ""
        if source_desc is not None:
            bibl = _find(source_desc, "biblStruct")
            if bibl is not None:
                for idno in _findall(bibl, "idno"):
                    if idno.get("type") == "DOI":
                        doi = (idno.text or "").strip()

        # Journal
        journal = ""
        if source_desc is not None:
            bibl = _find(source_desc, "biblStruct")
            if bibl is not None:
                monogr = _find(bibl, "monogr")
                if monogr is not None:
                    journal = _text(monogr, "title")

        # Year
        year = ""
        if source_desc is not None:
            bibl = _find(source_desc, "biblStruct")
            if bibl is not None:
                monogr = _find(bibl, "monogr")
                if monogr is not None:
                    imprint = _find(monogr, "imprint")
                    if imprint is not None:
                        date_el = _find(imprint, "date")
                        if date_el is not None:
                            year = (date_el.get("when") or date_el.text or "").strip()

        # References
        references: list[dict[str, Any]] = []
        text_div = _find(root, "text")
        if text_div is not None:
            back = _find(text_div, "back")
            if back is not None:
                for ref_div in _findall(back, "div"):
                    if ref_div.get("type") == "references":
                        for bibl_ref in _findall(ref_div, "biblStruct"):
                            ref_title = ""
                            ref_authors: list[str] = []
                            ref_year = ""
                            for analytic in _findall(bibl_ref, "analytic"):
                                ref_title = _text(analytic, "title") or ref_title
                                for author_el in _findall(analytic, "author"):
                                    pers_name = _find(author_el, "persName")
                                    if pers_name is not None:
                                        surname = _text(pers_name, "surname")
                                        if surname:
                                            ref_authors.append(surname)
                            monogr = _find(bibl_ref, "monogr")
                            if monogr is not None:
                                imprint = _find(monogr, "imprint")
                                if imprint is not None:
                                    date_el = _find(imprint, "date")
                                    if date_el is not None:
                                        ref_year = (date_el.get("when") or date_el.text or "").strip()
                            if ref_title or ref_authors:
                                references.append({
                                    "title": ref_title,
                                    "authors": ref_authors,
                                    "year": ref_year,
                                })

        return {
            "title": title,
            "authors": authors,
            "abstract": abstract[:1000] if abstract else "",
            "doi": doi,
            "journal": journal,
            "year": year,
            "references": references,
        }

    except Exception:
        return {}


def _score_metadata_quality(metadata: dict[str, Any]) -> float:
    """Quick quality score for GROBID-extracted metadata."""
    score = 0.0
    if metadata.get("title"):
        score += 0.3
    if metadata.get("abstract"):
        score += 0.2
    if metadata.get("doi"):
        score += 0.15
    if metadata.get("authors"):
        score += 0.15
    if metadata.get("year"):
        score += 0.1
    if metadata.get("references") and len(metadata["references"]) > 0:
        score += 0.1
    return min(score, 1.0)


def check_grobid_health(base_url: str | None = None) -> bool:
    """Public health check for GROBID."""
    if base_url is None:
        root = _resolve_root()
        config = _load_grobid_config(root)
        base_url = config.get("grobid_base_url", "http://localhost:18070")
    return _check_grobid_health(base_url)
