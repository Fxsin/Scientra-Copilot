#!/usr/bin/env python
"""Batch import supplementary assets from Inbox and existing workspaces (Phase 4.0.1).

Scans:
  1. 01_Sources/papers/ — registers unregistered files already in workspaces
  2. 00_Inbox/article_bundles/new/ — processes paper bundles (PDF + ZIP + notes)
  3. 00_Inbox/loose_supplementary/new/ — matches loose files to papers

Usage:
    python Scripts/import_supplementary_assets.py --dry-run
    python Scripts/import_supplementary_assets.py --apply
    python Scripts/import_supplementary_assets.py --apply --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Helpers ──


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    # Use \\?\ prefix for long paths on Windows
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
    except (OSError, FileNotFoundError):
        # Try with extended-length path prefix
        long_path = "\\\\?\\" + str(filepath.resolve())
        with open(long_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
    return sha.hexdigest()


def _safe_name(name: str, max_len: int = 100) -> str:
    unsafe = '<>:"/\\|?*'
    for ch in unsafe:
        name = name.replace(ch, "_")
    if len(name) > max_len:
        stem = Path(name).stem[:max_len - 10]
        suffix = Path(name).suffix
        name = stem + suffix
    return name


def _classify(path: str | Path) -> str:
    """Classify a file into asset_type."""
    name = Path(path).name.lower()
    ext = Path(path).suffix.lower()

    if ext == ".pdf":
        for kw in ["supplementary", "supporting", "suppl", "si_", "appendix", "mmc",
                   "-s0", ".s0", "sapp", "-sup", "_sup"]:
            if kw in name:
                return "supplementary_pdf"
        # If filename starts with a pattern like "ppat.1007347.s" or "pbio.", it's supplementary
        if re.match(r'^[a-z]+\.[\d]+\.[a-z]\d', name):
            return "supplementary_pdf"
        return "main_pdf"
    if ext in (".xlsx", ".xls"):
        return "supplementary_table"
    if ext in (".csv", ".tsv"):
        return "dataset"
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"):
        if "table" in name or "tab_" in name:
            return "table_image"
        return "figure_image"
    if ext in (".zip", ".rar", ".7z", ".tar", ".gz"):
        return "archive"
    if ext in (".doc", ".docx"):
        if "table" in name:
            return "supplementary_table"
        return "attachment"
    if ext in (".txt", ".md"):
        return "attachment"
    return "unknown"


def _parse_supplementary_notes(text: str) -> list[dict[str, Any]]:
    """Parse a supplementary item description file into structured notes.

    Format (PLOS-style):
        S1 Table. Description text.
        https://doi.org/...
        (DOCX)

        S2 Fig. Description text.
        https://doi.org/...
        (DOCX)

    Returns list of {id, title, description, doi, file_type, raw_lines}
    """
    notes: list[dict[str, Any]] = []
    blocks = re.split(r'\n\n+', text.strip())
    current: dict[str, Any] | None = None

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split("\n")
        first_line = lines[0].strip()

        # Detect if this is a new item header (e.g., "S1 Table.", "S1 Fig.", "S1 Data.")
        header_match = re.match(r'^(S\d+\s+(Table|Fig|Data|Text|Raw\s+Images?)\.?)\s*(.*)', first_line, re.IGNORECASE)
        if header_match:
            if current:
                notes.append(current)
            current = {
                "id": header_match.group(1).strip(),
                "title": header_match.group(0)[:120],
                "description": header_match.group(3) if header_match.group(3) else "",
                "doi": "",
                "file_type": "",
                "raw_lines": lines,
            }
        elif current is not None:
            # Check for DOI line
            doi_match = re.search(r'(https?://doi\.org/\S+)', first_line)
            if doi_match:
                current["doi"] = doi_match.group(1)
            # Check for file type hint
            type_match = re.match(r'^\(([^)]+)\)$', first_line)
            if type_match:
                current["file_type"] = type_match.group(1).upper()

            # Append description if it's a non-DOI, non-type line
            if not doi_match and not type_match and first_line:
                if current["description"]:
                    current["description"] += " " + first_line
                else:
                    current["description"] = first_line

    if current:
        notes.append(current)

    return notes


def _load_registry(paper_id: str) -> dict | None:
    """Find and load paper_assets.json for a paper_id."""
    # Try registry lookup
    try:
        from scientra.papers.paper_registry import get_paper_entry
        entry = get_paper_entry(paper_id)
        if entry:
            src = entry.get("source_dir", "")
            if src:
                path = PROJECT_ROOT / src / "paper_assets.json"
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _save_registry(paper_id: str, reg: dict) -> None:
    """Save paper_assets.json."""
    try:
        from scientra.papers.paper_registry import get_paper_entry
        entry = get_paper_entry(paper_id)
        if entry:
            src = entry.get("source_dir", "")
            if src:
                path = PROJECT_ROOT / src / "paper_assets.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
                return
    except Exception:
        pass


def _get_workspace_dir(paper_id: str) -> Path | None:
    """Get the workspace directory for a paper."""
    try:
        from scientra.papers.paper_workspace import resolve_workspace_dir
        return resolve_workspace_dir(paper_id)
    except Exception:
        return None


def _find_asset_by_sha(reg: dict, sha: str) -> dict | None:
    """Find existing asset with same SHA-256."""
    mp = reg.get("main_pdf")
    if mp and isinstance(mp, dict) and mp.get("sha256") == sha:
        return mp
    for a in reg.get("assets", []):
        if a.get("sha256") == sha:
            return a
    return None


def _register_file(
    paper_id: str,
    file_path: Path,
    reg: dict,
    asset_type: str = "",
    notes: dict | None = None,
    source: str = "manual_upload",
    copy_mode: str = "copy",
) -> dict[str, Any]:
    """Register a single file to a paper workspace. Returns result dict."""
    result = {
        "file": file_path.name,
        "status": "unknown",
        "asset_id": "",
        "asset_type": "",
        "error": "",
    }

    # Get workspace
    ws = _get_workspace_dir(paper_id)
    if not ws:
        result["error"] = "No workspace dir"
        return result

    # Check SHA-256 dedup
    sha = _sha256(file_path)
    existing = _find_asset_by_sha(reg, sha)
    if existing:
        result["status"] = "skipped"
        result["asset_id"] = existing.get("asset_id", "duplicate")
        result["asset_type"] = existing.get("asset_type", "")
        result["error"] = "Duplicate SHA-256"
        return result

    # Classify
    if not asset_type:
        asset_type = _classify(file_path)

    # Determine target subdir
    type_dir_map = {
        "supplementary_pdf": "assets/supplementary",
        "supplementary_table": "assets/tables",
        "dataset": "assets/datasets",
        "figure_image": "assets/images",
        "table_image": "assets/images",
        "archive": "assets/archives",
        "attachment": "assets/attachments",
        "unknown": "assets/attachments",
        "main_pdf": "",  # don't store in assets/
    }
    subdir = type_dir_map.get(asset_type, "assets/attachments")

    if subdir:
        target_dir = ws / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        target_dir = ws
        target_dir.mkdir(parents=True, exist_ok=True)

    # Safe filename
    safe = _safe_name(file_path.name)
    target = target_dir / safe
    counter = 1
    while target.exists():
        stem = Path(safe).stem
        suffix = Path(safe).suffix
        target = target_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    # Copy
    try:
        if copy_mode == "move":
            shutil.move(str(file_path), str(target))
        else:
            shutil.copy2(str(file_path), str(target))
        if not target.exists():
            raise RuntimeError("Copy succeeded but target file not found")
    except Exception as e:
        # Try with extended-length path
        try:
            long_src = "\\\\?\\" + str(Path(file_path).resolve())
            long_dst = "\\\\?\\" + str(target.resolve())
            subprocess.run(["cmd", "/c", "copy", "/y", long_src, long_dst], capture_output=True, check=True)
        except Exception as e2:
            result["error"] = f"Copy failed: {e} / {e2}"
            return result

    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"

    # Generate asset ID
    asset_index = len(reg.get("assets", []))
    short_pid = paper_id.replace("paper_", "")[:8] if paper_id.startswith("paper_") else paper_id[:8]
    asset_id = f"asset_{short_pid}_{asset_index:04d}"

    now = datetime.now(timezone.utc).isoformat()

    rel_path = str(target.relative_to(ws))

    asset_entry = {
        "asset_id": asset_id,
        "paper_id": paper_id,
        "asset_type": asset_type,
        "filename": safe,
        "original_filename": file_path.name,
        "relative_path": rel_path,
        "sha256": sha,
        "size_bytes": target.stat().st_size,
        "mime_type": mime,
        "extension": file_path.suffix.lower(),
        "source": source,
        "status": "registered",
        "processing_stage": "",
        "created_at": now,
        "updated_at": now,
        "notes": f"Classified as {asset_type}",
        "warnings": [],
        "errors": [],
        # New metadata fields
        "asset_title": notes.get("title", "") if notes else "",
        "asset_description": notes.get("description", "") if notes else "",
        "source_reference": notes.get("doi", "") if notes else "",
        "metadata_source": "user_notes" if notes else "auto",
    }

    reg.setdefault("assets", []).append(asset_entry)
    atype = asset_entry["asset_type"]
    reg.setdefault("asset_counts", {})
    reg["asset_counts"][atype] = reg["asset_counts"].get(atype, 0) + 1
    reg["last_updated"] = now

    result["status"] = "registered"
    result["asset_id"] = asset_id
    result["asset_type"] = asset_type
    return result


# ── Phase 1: Scan existing workspaces ──


def scan_existing_workspaces(dry_run: bool = True) -> dict[str, Any]:
    """Scan 01_Sources/papers/ for unregistered files."""
    print("\n" + "=" * 60)
    print("  Phase 1: Scanning existing workspaces")
    print("=" * 60)

    papers_dir = PROJECT_ROOT / "01_Sources" / "papers"
    results: list[dict] = []
    total_registered = 0
    total_skipped = 0

    for paper_dir in sorted(papers_dir.iterdir()):
        if not paper_dir.is_dir() or paper_dir.name == "README.md":
            continue

        # Load registry
        reg_file = paper_dir / "paper_assets.json"
        if not reg_file.exists():
            continue
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        paper_id = reg.get("paper_id", "")
        if not paper_id:
            continue

        # Find all files in workspace (excluding paper_assets.json and assets/ subdirs)
        existing_paths = set()
        if reg.get("main_pdf"):
            existing_paths.add(reg["main_pdf"].get("relative_path", ""))
        for a in reg.get("assets", []):
            existing_paths.add(a.get("relative_path", ""))

        paper_registered = 0
        paper_skipped = 0

        for f in sorted(paper_dir.rglob("*")):
            if not f.is_file():
                continue
            if f.name == "paper_assets.json":
                continue
            rel = str(f.relative_to(paper_dir))
            if rel in existing_paths:
                continue

            if dry_run:
                atype = _classify(f)
                print(f"  [DRY] Would register: {f.name} ({atype}) -> {paper_dir.name}")
                paper_registered += 1
            else:
                result = _register_file(paper_id, f, reg, source="folder_scan")
                results.append({**result, "paper_id": paper_id, "workspace": paper_dir.name})
                if result["status"] == "registered":
                    paper_registered += 1
                else:
                    paper_skipped += 1

        if paper_registered > 0 or paper_skipped > 0:
            print(f"  {paper_dir.name}: +{paper_registered} registered, {paper_skipped} skipped")
            if not dry_run:
                _save_registry(paper_id, reg)

        total_registered += paper_registered
        total_skipped += paper_skipped

    print(f"\n  Workspace scan: {total_registered} to register, {total_skipped} skipped")
    return {"registered": total_registered, "skipped": total_skipped, "details": results}


# ── Phase 2: Process article bundles ──


def process_article_bundles(dry_run: bool = True) -> dict[str, Any]:
    """Process article bundles from 00_Inbox/article_bundles/new/."""
    print("\n" + "=" * 60)
    print("  Phase 2: Processing article bundles")
    print("=" * 60)

    bundles_dir = PROJECT_ROOT / "00_Inbox" / "article_bundles" / "new"
    processed_dir = PROJECT_ROOT / "00_Inbox" / "article_bundles" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    from scientra.papers.paper_lookup import search_papers

    results: list[dict] = []
    paper_reports: list[dict] = []

    for bundle_dir in sorted(bundles_dir.iterdir()):
        if not bundle_dir.is_dir():
            continue

        bundle_name = bundle_dir.name
        print(f"\n  --- Bundle: {bundle_name[:70]} ---")

        # Match to paper by directory name as query
        papers = search_papers(bundle_name, limit=5)
        if not papers:
            print(f"  ERROR: No paper match for '{bundle_name[:60]}'")
            continue

        if len(papers) > 1:
            print(f"  WARNING: Multiple matches ({len(papers)}). Using best match.")
            for i, p in enumerate(papers[:3], 1):
                print(f"    {i}. {p.get('title','')[:60]} ({p.get('year','')}) [{p.get('paper_id','')}]")

        paper = papers[0]
        paper_id = paper["paper_id"]
        print(f"  Matched: {paper.get('title','')[:70]}")
        print(f"  paper_id: {paper_id}")

        # Load registry
        reg = _load_registry(paper_id)
        if reg is None:
            print(f"  ERROR: No registry for {paper_id}")
            continue

        paper_stats = {
            "paper_title": paper.get("title", ""),
            "paper_id": paper_id,
            "workspace": paper.get("display_name", ""),
            "registered": 0,
            "supplementary_pdf": 0,
            "table": 0,
            "dataset": 0,
            "image": 0,
            "archive": 0,
            "matched_notes": 0,
            "unmatched_notes": [],
            "skipped": 0,
        }

        # Find notes file (TXT)
        notes_data: list[dict] = []
        for txt_file in sorted(bundle_dir.glob("*.txt")):
            text = txt_file.read_text(encoding="utf-8", errors="replace")
            notes_data = _parse_supplementary_notes(text)
            print(f"  Parsed notes: {len(notes_data)} items from {txt_file.name}")
            break  # Only first notes file

        # Check if main PDF is already registered by Phase 4
        if not reg.get("main_pdf"):
            print(f"  NOTE: main_pdf not yet linked (handled by Phase 4 from 01_PDF/)")

        # Process supplementary PDFs
        for spdf in sorted(bundle_dir.glob("*.pdf")):
            if _classify(spdf) != "supplementary_pdf":
                continue
            # Try to match with notes
            matched_note = _match_note(spdf.name, notes_data)
            if matched_note:
                paper_stats["matched_notes"] += 1
            else:
                paper_stats["unmatched_notes"].append(spdf.name)

            if dry_run:
                print(f"  [DRY] Would register: {spdf.name} (supplementary_pdf)")
            else:
                try:
                    r = _register_file(paper_id, spdf, reg, notes=matched_note, source="article_bundle")
                except (OSError, FileNotFoundError) as e:
                    print(f"  SKIP (path too long): {spdf.name} - {e}")
                    paper_stats["skipped"] += 1
                    continue
                results.append({**r, "paper_id": paper_id, "workspace": paper.get("display_name", "")})
                if r["status"] == "registered":
                    paper_stats["registered"] += 1
                    paper_stats["supplementary_pdf"] += 1
                else:
                    paper_stats["skipped"] += 1

        # Process ZIP files
        for zip_file in sorted(bundle_dir.glob("*.zip")):
            print(f"  Extracting ZIP: {zip_file.name}")
            # Use short temp dir to avoid path-too-long errors
            extract_dir = Path(tempfile.mkdtemp(prefix="scx_"))

            try:
                with zipfile.ZipFile(zip_file, "r") as zf:
                    # Use short internal names to avoid path length issues
                    for member in zf.namelist():
                        # Extract to flat temp dir with safe names
                        safe_member = _safe_name(Path(member).name)
                        target = extract_dir / safe_member
                        counter = 1
                        while target.exists():
                            stem = Path(safe_member).stem
                            suffix = Path(safe_member).suffix
                            target = extract_dir / f"{stem}_{counter}{suffix}"
                            counter += 1
                        try:
                            with zf.open(member) as src:
                                target.write_bytes(src.read())
                        except Exception as e:
                            print(f"    WARNING: Could not extract {member}: {e}")
            except Exception as e:
                print(f"  ERROR extracting ZIP: {e}")
                shutil.rmtree(extract_dir, ignore_errors=True)
                continue

            # Register ZIP itself
            if dry_run:
                print(f"  [DRY] Would register: {zip_file.name} (archive)")
            else:
                r = _register_file(paper_id, zip_file, reg, asset_type="archive", source="article_bundle")
                results.append({**r, "paper_id": paper_id, "workspace": paper.get("display_name", "")})
                if r["status"] == "registered":
                    paper_stats["registered"] += 1
                    paper_stats["archive"] += 1
                else:
                    paper_stats["skipped"] += 1

            # Register extracted files
            for ext_file in sorted(extract_dir.rglob("*")):
                if not ext_file.is_file():
                    continue
                atype = _classify(ext_file)
                matched_note = _match_note(ext_file.name, notes_data)

                if matched_note:
                    paper_stats["matched_notes"] += 1
                else:
                    paper_stats["unmatched_notes"].append(ext_file.name)

                if dry_run:
                    print(f"  [DRY] Would register: {ext_file.name} ({atype})")
                else:
                    r = _register_file(paper_id, ext_file, reg, notes=matched_note, source="article_bundle")
                    results.append({**r, "paper_id": paper_id, "workspace": paper.get("display_name", "")})
                    if r["status"] == "registered":
                        paper_stats["registered"] += 1
                        _increment_stat(paper_stats, atype)
                    else:
                        paper_stats["skipped"] += 1

        if not dry_run:
            _save_registry(paper_id, reg)

        paper_reports.append(paper_stats)
        _print_paper_report(paper_stats)

        # Move processed dir
        if not dry_run:
            target = processed_dir / bundle_dir.name
            if target.exists():
                target = processed_dir / f"{bundle_dir.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            shutil.move(str(bundle_dir), str(target))

    return {"paper_reports": paper_reports, "details": results}


def _match_note(filename: str, notes: list[dict]) -> dict | None:
    """Try to match a filename to a note entry."""
    name_lower = filename.lower()
    for n in notes:
        nid = n.get("id", "").lower()
        ndoi = n.get("doi", "").lower()
        # Match by DOI suffix (e.g., ".s001" matches "pbio.3002704.s001.docx")
        doi_suffix = re.search(r'(s\d+)', ndoi)
        if doi_suffix and doi_suffix.group(1) in name_lower:
            return n
        # Match by item ID in filename
        nid_short = re.sub(r'[^a-z0-9]', '', nid)
        if nid_short and nid_short in re.sub(r'[^a-z0-9]', '', name_lower):
            return n
    return None


def _increment_stat(stats: dict, atype: str) -> None:
    """Increment the appropriate stat counter."""
    if atype == "supplementary_pdf":
        stats["supplementary_pdf"] += 1
    elif atype in ("supplementary_table",):
        stats["table"] += 1
    elif atype == "dataset":
        stats["dataset"] += 1
    elif atype in ("figure_image", "table_image"):
        stats["image"] += 1
    elif atype == "archive":
        stats["archive"] += 1


def _print_paper_report(stats: dict) -> None:
    """Print per-paper summary."""
    print(f"\n  {'─'*50}")
    print(f"  Paper: {stats['paper_title'][:65]}")
    print(f"  ID:    {stats['paper_id']}")
    print(f"  WS:    {stats['workspace'][:55]}")
    print(f"  Registered:    {stats['registered']}")
    print(f"  Supp PDF:      {stats['supplementary_pdf']}")
    print(f"  Tables:        {stats['table']}")
    print(f"  Datasets:      {stats['dataset']}")
    print(f"  Images:        {stats['image']}")
    print(f"  Archives:      {stats['archive']}")
    print(f"  Matched notes: {stats['matched_notes']}")
    if stats["unmatched_notes"]:
        print(f"  Unmatched:     {len(stats['unmatched_notes'])} files")
        for u in stats["unmatched_notes"][:5]:
            print(f"    - {u}")
    print(f"  Skipped:       {stats['skipped']}")


# ── Phase 3: Loose supplementary files ──


def process_loose_supplementary(dry_run: bool = True) -> dict[str, Any]:
    """Process loose supplementary files from 00_Inbox/loose_supplementary/new/."""
    print("\n" + "=" * 60)
    print("  Phase 3: Processing loose supplementary files")
    print("=" * 60)

    loose_dir = PROJECT_ROOT / "00_Inbox" / "loose_supplementary" / "new"
    processed_dir = PROJECT_ROOT / "00_Inbox" / "loose_supplementary" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    from scientra.papers.paper_lookup import search_papers

    results: list[dict] = []
    registered = 0
    skipped = 0

    for f in sorted(loose_dir.iterdir()):
        if not f.is_file():
            continue

        # Try to match by filename keywords
        match_query = f.stem.replace("_", " ").replace("__", " ")[:80]
        papers = search_papers(match_query, limit=5)

        if not papers:
            print(f"  NO MATCH: {f.name} — query '{match_query[:50]}'")
            continue

        if len(papers) > 1:
            print(f"  MULTIPLE ({len(papers)}) matches for {f.name}:")
            for i, p in enumerate(papers[:3], 1):
                print(f"    {i}. {p['title'][:50]} ({p['year']}) [{p['paper_id']}]")
            print(f"  Skipping — needs manual resolution.")
            continue

        paper = papers[0]
        paper_id = paper["paper_id"]
        print(f"  {f.name} -> {paper['title'][:50]} [{paper_id}]")

        reg = _load_registry(paper_id)
        if reg is None:
            print(f"    ERROR: No registry")
            continue

        atype = _classify(f)
        if dry_run:
            print(f"    [DRY] Would register as {atype}")
            registered += 1
        else:
            r = _register_file(paper_id, f, reg, source="loose_supplementary")
            results.append({**r, "paper_id": paper_id})
            if r["status"] == "registered":
                registered += 1
            else:
                skipped += 1
            _save_registry(paper_id, reg)

        # Move processed file
        if not dry_run:
            dest = processed_dir / f.name
            if dest.exists():
                dest = processed_dir / f"{f.stem}_{datetime.now().strftime('%H%M%S')}{f.suffix}"
            shutil.move(str(f), str(dest))

    print(f"\n  Loose files: {registered} registered, {skipped} skipped")
    return {"registered": registered, "skipped": skipped, "details": results}


# ── Phase 4: Fix main_pdf linking ──


def fix_main_pdf_links(dry_run: bool = True) -> dict[str, Any]:
    """Fix main_pdf links in paper_assets.json by matching 01_PDF to workspaces."""
    print("\n" + "=" * 60)
    print("  Phase 4: Fixing main_pdf links")
    print("=" * 60)

    from scientra.papers.paper_registry import load_paper_registry

    reg = load_paper_registry()
    if not reg:
        print("  No registry found.")
        return {"fixed": 0, "already_ok": 0, "not_found": 0}

    pdf_dir = PROJECT_ROOT / "01_PDF"
    fixed = 0
    already_ok = 0
    not_found = 0

    for paper_id, entry in reg.get("papers", {}).items():
        src = entry.get("source_dir", "")
        if not src:
            continue

        assets_file = PROJECT_ROOT / src / "paper_assets.json"
        if not assets_file.exists():
            continue

        assets_reg = json.loads(assets_file.read_text(encoding="utf-8"))

        # Skip if main_pdf already set
        if assets_reg.get("main_pdf"):
            already_ok += 1
            continue

        # Try to find matching PDF in 01_PDF
        key = entry.get("metadata_path", "").replace("02_Metadata/yaml/", "").replace(".metadata.yaml", "")
        found = False

        # Try exact key match
        candidate = pdf_dir / f"{key}.pdf"
        if not candidate.exists():
            # Try fuzzy: match by DOI or title substring
            for pdf_file in pdf_dir.glob("*.pdf"):
                norm_pdf = re.sub(r'[^a-z0-9]', '', pdf_file.stem.lower())
                norm_key = re.sub(r'[^a-z0-9]', '', key.lower())
                if norm_key[:40] in norm_pdf or norm_pdf[:40] in norm_key:
                    candidate = pdf_file
                    break

        if not candidate.exists():
            not_found += 1
            continue

        if dry_run:
            print(f"  [DRY] {paper_id[:20]}... -> {candidate.name[:60]}")
            fixed += 1
            continue

        sha = _sha256(candidate)
        assets_reg["main_pdf"] = {
            "asset_id": "main_pdf",
            "paper_id": paper_id,
            "asset_type": "main_pdf",
            "filename": candidate.name,
            "original_filename": candidate.name,
            "relative_path": "",
            "source_path": str(candidate.resolve()),
            "sha256": sha,
            "size_bytes": candidate.stat().st_size,
            "mime_type": "application/pdf",
            "extension": ".pdf",
            "source": "fixup_script",
            "status": "registered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Main PDF — linked from 01_PDF by Phase 4.0.1 fixup",
            "warnings": [],
            "errors": [],
            "asset_title": "",
            "asset_description": "",
            "source_reference": "",
            "metadata_source": "auto",
        }
        assets_reg["last_updated"] = datetime.now(timezone.utc).isoformat()
        assets_file.write_text(json.dumps(assets_reg, ensure_ascii=False, indent=2), encoding="utf-8")
        fixed += 1

    print(f"  Fixed: {fixed}, Already OK: {already_ok}, Not found: {not_found}")
    return {"fixed": fixed, "already_ok": already_ok, "not_found": not_found}


# ── Main ──


def main() -> int:
    p = argparse.ArgumentParser(description="Batch import supplementary assets")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--skip-fix-main-pdf", action="store_true")
    args = p.parse_args()

    dry_run = not args.apply

    all_results: dict[str, Any] = {
        "phases": {},
        "total_registered": 0,
        "total_skipped": 0,
        "total_matched_notes": 0,
        "total_unmatched_notes": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    # Phase 1: Scan existing workspaces
    r1 = scan_existing_workspaces(dry_run=dry_run)
    all_results["phases"]["workspace_scan"] = r1

    # Phase 2: Process article bundles
    r2 = process_article_bundles(dry_run=dry_run)
    all_results["phases"]["article_bundles"] = r2

    # Phase 3: Loose supplementary
    r3 = process_loose_supplementary(dry_run=dry_run)
    all_results["phases"]["loose_supplementary"] = r3

    # Phase 4: Fix main_pdf links
    if not args.skip_fix_main_pdf:
        r4 = fix_main_pdf_links(dry_run=dry_run)
        all_results["phases"]["fix_main_pdf"] = r4

    # ── Aggregate ──
    for phase_name, phase_result in all_results["phases"].items():
        if isinstance(phase_result, dict):
            all_results["total_registered"] += phase_result.get("registered", 0)
            all_results["total_skipped"] += phase_result.get("skipped", 0)

    # Count notes from paper reports
    bundle_reports = r2.get("paper_reports", [])
    for pr in bundle_reports:
        all_results["total_matched_notes"] += pr.get("matched_notes", 0)
        all_results["total_unmatched_notes"] += len(pr.get("unmatched_notes", []))

    if args.json:
        print(json.dumps(all_results, ensure_ascii=False, indent=2, default=str))
        return 0

    # ── Final Report ──
    mode = "DRY RUN" if dry_run else "APPLY"
    print("\n" + "=" * 60)
    print(f"  SUPPLEMENTARY ASSET IMPORT — {mode}")
    print("=" * 60)
    print(f"  Total registered:   {all_results['total_registered']}")
    print(f"  Total skipped:      {all_results['total_skipped']}")
    print(f"  Matched notes:      {all_results['total_matched_notes']}")
    print(f"  Unmatched notes:    {all_results['total_unmatched_notes']}")
    print(f"  Errors:             {all_results['errors']}")

    if bundle_reports:
        print(f"\n  Per-Paper Summary:")
        for pr in bundle_reports:
            print(f"    {pr['paper_title'][:55]}")
            print(f"      ID: {pr['paper_id']}  WS: {pr['workspace'][:40]}")
            print(f"      +{pr['registered']} assets ({pr['supplementary_pdf']} supp, {pr['table']} tables, "
                  f"{pr['dataset']} datasets, {pr['image']} images, {pr['archive']} archives)")
            print(f"      Notes: {pr['matched_notes']} matched, {len(pr['unmatched_notes'])} unmatched")

    if dry_run:
        print(f"\n  To apply: python Scripts/import_supplementary_assets.py --apply")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
