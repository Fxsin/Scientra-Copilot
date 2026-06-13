"""Convert single/loose PDFs into article bundle folders.

Creates one article-bundle folder per PDF so supplementary files can be
added later and correctly linked via folder_explicit binding.

Usage:
  python Scripts/convert_single_to_bundle.py --scan
  python Scripts/convert_single_to_bundle.py --convert
  python Scripts/convert_single_to_bundle.py --convert --source sources --mode copy

Sources:
  inbox     PDFs from single_papers/new/ + loose PDFs in article_bundles/new/
  sources   PDFs already archived in 01_Sources/papers/
  all       Both (default)

Modes:
  move   Move PDF into new bundle folder (default for inbox — fast, no duplicates)
  copy   Copy PDF into new bundle folder (default for sources — safe, preserves original)

No absolute paths. No file deletion beyond intentional move. Generates manifest.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

# ── Constants ──
MANIFEST_PATH = "10_System/registry/single_to_bundle_conversion_manifest.json"
INBOX_SINGLE = "00_Inbox/single_papers/new"
INBOX_BUNDLES_NEW = "00_Inbox/article_bundles/new"
SOURCES_PAPERS = "01_Sources/papers"

# Files to skip (not PDFs)
SKIP_NAMES = {".gitkeep", "README.md", "Thumbs.db", ".DS_Store", "desktop.ini"}

# Characters to replace in folder names
_FOLDER_SAFE_RE = re.compile(r"[^a-zA-Z0-9一-鿿 _\-,.()\[\]\+&=]+")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_folder_name(name: str, max_len: int = 80) -> str:
    """Sanitize a PDF filename into a safe folder name."""
    # Strip .pdf extension
    if name.lower().endswith(".pdf"):
        name = name[:-4]

    # Replace unsafe chars with underscore
    safe = _FOLDER_SAFE_RE.sub("_", name)

    # Collapse multiple underscores/spaces
    safe = re.sub(r"[_\s]{2,}", "_", safe)

    # Strip leading/trailing dots, spaces, underscores
    safe = safe.strip(" ._-")

    # Truncate
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip(" ._-")

    # Ensure non-empty
    if not safe:
        safe = "Unnamed_Article"

    return safe


def _sha256_file(path: Path) -> str:
    """SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest() -> dict[str, Any]:
    """Load conversion manifest."""
    mp = root / MANIFEST_PATH
    if mp.exists():
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": "1.0", "conversions": [], "created_at": _utc_now()}


def _save_manifest(manifest: dict[str, Any]) -> None:
    """Save conversion manifest."""
    mp = root / MANIFEST_PATH
    mp.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = _utc_now()
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _find_pdfs(directories: list[Path], skip_converted: set[str]) -> list[dict[str, Any]]:
    """Find PDF files in given directories. Returns list of info dicts."""
    results: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for directory in directories:
        if not directory.exists():
            continue

        for entry in sorted(directory.iterdir()):
            if entry.is_file():
                name = entry.name
                if name in SKIP_NAMES:
                    continue
                if not name.lower().endswith(".pdf"):
                    continue

                abs_path = str(entry.resolve())
                if abs_path in seen_paths:
                    continue
                seen_paths.add(abs_path)

                folder_name = _sanitize_folder_name(name)
                sha = _sha256_file(entry)

                # Check if already converted
                already = sha in skip_converted or abs_path in skip_converted

                results.append({
                    "pdf_path": str(entry.relative_to(root)),
                    "pdf_name": name,
                    "pdf_size": entry.stat().st_size,
                    "pdf_sha256": sha,
                    "proposed_folder": folder_name,
                    "source": "inbox" if "Inbox" in str(entry) or "00_Inbox" in str(entry) else "sources",
                    "already_converted": already,
                })

    return results


def _resolve_folder_name(desired: str, target_dir: Path, pdf_path: Path) -> str:
    """Resolve folder name, appending suffix if already exists and is for a different PDF."""
    candidate = desired
    if not (target_dir / candidate).exists():
        return candidate

    # Folder exists — check if it contains the same PDF (SHA256)
    existing_pdfs = list((target_dir / candidate).glob("*.pdf"))
    if existing_pdfs:
        existing_sha = _sha256_file(existing_pdfs[0])
        new_sha = _sha256_file(pdf_path)
        if existing_sha == new_sha:
            return candidate  # Same PDF, reuse folder
        # Different PDF — append suffix
        for i in range(2, 100):
            candidate = f"{desired}_{i}"
            if not (target_dir / candidate).exists():
                return candidate
    return candidate


def scan(args: argparse.Namespace) -> dict[str, Any]:
    """Scan for single PDFs and propose conversions."""
    source = args.source or "all"
    dirs: list[Path] = []

    if source in ("inbox", "all"):
        dirs.append(root / INBOX_SINGLE)
        dirs.append(root / INBOX_BUNDLES_NEW)
    if source in ("sources", "all"):
        dirs.append(root / SOURCES_PAPERS)

    manifest = _load_manifest()
    skip_set: set[str] = set()
    for conv in manifest.get("conversions", []):
        skip_set.add(conv.get("pdf_sha256", ""))
        skip_set.add(str(root / conv.get("original_pdf_path", "")))

    pdfs = _find_pdfs(dirs, skip_set)

    # Filter already_converted for display
    new_pdfs = [p for p in pdfs if not p["already_converted"]]
    converted_pdfs = [p for p in pdfs if p["already_converted"]]

    result = {
        "total_pdfs_found": len(pdfs),
        "new_pdfs": len(new_pdfs),
        "already_converted": len(converted_pdfs),
        "pdfs": pdfs,
    }

    # ── Print scan report ──
    print("=" * 70)
    print("  Single PDF → Article Bundle Conversion — SCAN")
    print("=" * 70)
    print(f"  Source: {source}")
    print(f"  Total PDFs found: {len(pdfs)}")
    print(f"  Ready to convert: {len(new_pdfs)}")
    print(f"  Already converted (skipped): {len(converted_pdfs)}")
    print()

    if converted_pdfs:
        print("  Already converted (will skip):")
        for p in converted_pdfs:
            print(f"    ⊘ {p['pdf_name']}")
        print()

    if new_pdfs:
        print("  Ready to convert:")
        for p in new_pdfs:
            tag = "[INBOX]" if p["source"] == "inbox" else "[SOURCES]"
            size_kb = p["pdf_size"] / 1024
            print(f"    → {p['pdf_name']}")
            print(f"      {tag}  Folder: {p['proposed_folder']}/  ({size_kb:.0f} KB)")
        print()

    if not new_pdfs and not converted_pdfs:
        print("  No PDFs found. Nothing to convert.")
        print()
        print("  Checked directories:")
        for d in dirs:
            print(f"    {d.relative_to(root) if d.exists() else '(missing) ' + str(d.relative_to(root))}")
        print()

    print(f"  Manifest: {MANIFEST_PATH}")
    print(f"  Previous conversions: {len(manifest.get('conversions', []))}")
    print()

    return result


def convert(args: argparse.Namespace) -> dict[str, Any]:
    """Create article bundle folders for single PDFs."""
    source = args.source or "all"
    mode = args.mode or "move"

    dirs: list[Path] = []
    if source in ("inbox", "all"):
        dirs.append(root / INBOX_SINGLE)
        dirs.append(root / INBOX_BUNDLES_NEW)
    if source in ("sources", "all"):
        dirs.append(root / SOURCES_PAPERS)

    manifest = _load_manifest()
    skip_set: set[str] = set()
    for conv in manifest.get("conversions", []):
        skip_set.add(conv.get("pdf_sha256", ""))
        skip_set.add(str(root / conv.get("original_pdf_path", "")))

    pdfs = _find_pdfs(dirs, skip_set)
    new_pdfs = [p for p in pdfs if not p["already_converted"]]

    if not new_pdfs:
        print("No new PDFs to convert. Run --scan first.")
        return {"converted": 0, "skipped": len(pdfs), "errors": 0, "details": []}

    # Force copy mode for sources
    target_dir = root / INBOX_BUNDLES_NEW
    target_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  Single PDF → Article Bundle Conversion — CONVERT")
    print("=" * 70)
    print(f"  Source: {source}  |  Mode: {mode}")
    print(f"  Target: {target_dir.relative_to(root)}/")
    print()

    converted = 0
    skipped = 0
    errors = 0
    details: list[dict[str, Any]] = []

    for pdf in new_pdfs:
        pdf_path = root / pdf["pdf_path"]
        folder_name = _resolve_folder_name(pdf["proposed_folder"], target_dir, pdf_path)
        bundle_dir = target_dir / folder_name

        # Only use copy for sources; move is fine for inbox
        effective_mode = "copy" if pdf["source"] == "sources" else mode

        if effective_mode == "move":
            action = "MOVE"
        else:
            action = "COPY"

        try:
            print(f"  [{action}] {pdf['pdf_name']}")
            print(f"          → {bundle_dir.relative_to(root)}/main.pdf")

            bundle_dir.mkdir(parents=True, exist_ok=True)
            dest = bundle_dir / "main.pdf"

            # If main.pdf already exists in bundle, check SHA
            if dest.exists():
                existing_sha = _sha256_file(dest)
                if existing_sha == pdf["pdf_sha256"]:
                    print(f"          ⊘ Already in bundle (same SHA256), skipped")
                    skipped += 1
                    continue
                else:
                    # Different content — use alternate name
                    dest = bundle_dir / pdf["pdf_name"]
                    print(f"          ⚠ main.pdf exists with different content, using original name")

            if effective_mode == "move":
                shutil.move(str(pdf_path), str(dest))
            else:
                shutil.copy2(str(pdf_path), str(dest))

            # Record in manifest
            entry = {
                "original_pdf_path": str(pdf_path.relative_to(root)),
                "original_pdf_sha256": pdf["pdf_sha256"],
                "bundle_folder": str(bundle_dir.relative_to(root)),
                "converted_pdf_path": str(dest.relative_to(root)),
                "source": pdf["source"],
                "mode": effective_mode,
                "converted_at": _utc_now(),
            }
            manifest["conversions"].append(entry)
            details.append(entry)
            converted += 1

        except OSError as e:
            print(f"          ✖ Error: {e}")
            errors += 1
            details.append({
                "original_pdf_path": pdf["pdf_path"],
                "error": str(e),
                "status": "failed",
            })

    # Save manifest
    _save_manifest(manifest)

    print()
    print(f"  Results: {converted} converted, {skipped} skipped, {errors} errors")
    print(f"  Manifest updated: {MANIFEST_PATH}")
    print()

    if converted > 0:
        print("  Next steps:")
        print(f"    1. Add supplementary files into each article folder")
        print(f"    2. python Scripts/process_article_bundles.py --scan")
        print(f"    3. python Scripts/process_article_bundles.py --process --dry-run")
        print(f"    4. python Scripts/process_article_bundles.py --process --archive-mode copy")
        print()

    return {
        "converted": converted,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert single/loose PDFs into article bundle folders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Scripts/convert_single_to_bundle.py --scan
  python Scripts/convert_single_to_bundle.py --scan --source inbox
  python Scripts/convert_single_to_bundle.py --convert
  python Scripts/convert_single_to_bundle.py --convert --source sources --mode copy
        """,
    )
    parser.add_argument(
        "--scan", action="store_true",
        help="Scan for single PDFs and show proposed conversions"
    )
    parser.add_argument(
        "--convert", action="store_true",
        help="Create article bundle folders and move/copy PDFs"
    )
    parser.add_argument(
        "--source", choices=["inbox", "sources", "all"], default="all",
        help="Which directories to scan (default: all)"
    )
    parser.add_argument(
        "--mode", choices=["move", "copy"], default=None,
        help="move=transfer PDF into bundle; copy=keep original (default: move for inbox, copy for sources)"
    )

    args = parser.parse_args()

    if not args.scan and not args.convert:
        parser.print_help()
        print("\n  Tip: Run --scan first to preview what will be converted.")
        return 0

    if args.scan:
        scan(args)

    if args.convert:
        convert(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
