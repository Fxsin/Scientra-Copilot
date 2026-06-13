"""
Article Bundle Importer — folder-explicit article + supplementary import.

Scans 00_Inbox/article_bundles/new/ for one-folder-per-article bundles.
Main PDF detection, supplementary classification, manifest generation.
No absolute paths. Copy-only by default. No file deletion.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.io.bundle_models import ArticleBundleRecord
from scientra.io.storage_layout import StorageLayout


MAIN_PDF_KEYWORDS = ["main", "paper", "article", "manuscript", "fulltext", "full_text"]
SUPP_PDF_KEYWORDS = ["supplementary", "supplement", "supporting", "appendix",
                     "supplemental", "source_data", "si_", "si ", "suppl"]
TABULAR_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv"}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_bundle_id(bundle_name: str) -> str:
    h = hashlib.sha256(bundle_name.encode()).hexdigest()[:12]
    safe = "".join(c for c in bundle_name if c.isalnum() or c in "_-")[:40]
    return f"bundle_{safe}_{h}"


class ArticleBundleImporter:
    """Scans, classifies, and processes article bundles."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.storage = StorageLayout(root) if root else StorageLayout()
        self.storage.load()
        self.root = self.storage.root

    def scan(self) -> list[ArticleBundleRecord]:
        """Scan inbox for article bundles."""
        inbox = self.storage.get_path("inbox.article_bundles_new")
        records: list[ArticleBundleRecord] = []
        if not inbox.exists():
            return records

        for entry in sorted(inbox.iterdir()):
            if not entry.is_dir():
                continue
            bundle = self._scan_bundle(entry)
            records.append(bundle)

        return records

    def _scan_bundle(self, bundle_dir: Path) -> ArticleBundleRecord:
        bundle_name = bundle_dir.name
        bundle_id = _make_bundle_id(bundle_name)
        rel = str(bundle_dir.relative_to(self.root))

        record = ArticleBundleRecord(
            bundle_id=bundle_id, bundle_name=bundle_name,
            bundle_relative_path=rel,
        )

        all_files = sorted(bundle_dir.iterdir())
        if not all_files:
            record.processing_status = "failed_empty"
            record.error_message = "Bundle directory is empty"
            return record

        # Find PDFs
        pdfs = [f for f in all_files if f.suffix.lower() == ".pdf"]
        if not pdfs:
            record.processing_status = "failed_no_main_pdf"
            record.error_message = "No PDF found in bundle"
            return record

        main_pdf = self._detect_main_pdf(pdfs)
        record.detected_main_pdf = str(main_pdf.relative_to(self.root))

        # Classify remaining files
        for f in all_files:
            if f == main_pdf:
                continue
            rel_f = str(f.relative_to(self.root))
            ext = f.suffix.lower()
            if ext in TABULAR_EXTENSIONS:
                record.tabular_supplementary_files.append(rel_f)
            elif ext == ".pdf":
                record.supplementary_pdfs.append(rel_f)
            else:
                record.other_files.append(rel_f)

        record.supplementary_files = (
            record.tabular_supplementary_files + record.supplementary_pdfs + record.other_files
        )
        record.processing_status = "scanned"
        return record

    def _detect_main_pdf(self, pdfs: list[Path]) -> Path:
        """Detect main PDF from a list of PDF paths."""
        if len(pdfs) == 1:
            return pdfs[0]

        # Score each PDF
        scored: list[tuple[int, int, Path]] = []
        for p in pdfs:
            name_lower = p.name.lower()
            score = 0
            # Keyword bonus
            for kw in MAIN_PDF_KEYWORDS:
                if kw in name_lower:
                    score += 2
            # Supplementary penalty
            for kw in SUPP_PDF_KEYWORDS:
                if kw in name_lower:
                    score -= 5
            size = p.stat().st_size
            scored.append((score, size, p))

        # Sort: highest score, then largest file
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return scored[0][2]

    def process(
        self, archive_mode: str = "copy", dry_run: bool = False
    ) -> dict[str, Any]:
        """Process all scanned bundles.

        archive_mode: copy | move | none
        dry_run: if True, only generate plan, no file operations.
        """
        records = self.scan()
        sources_papers = self.storage.get_path("sources.papers")
        sources_suppl = self.storage.get_path("sources.supplementary")
        processed_dir = self.storage.get_path("inbox.article_bundles_processed")
        failed_dir = self.storage.get_path("inbox.article_bundles_failed")

        results: list[dict] = []
        timestamp = datetime.now(timezone.utc).isoformat()

        for rec in records:
            entry: dict[str, Any] = {
                "bundle_id": rec.bundle_id, "bundle_name": rec.bundle_name,
                "status": rec.processing_status, "action": archive_mode,
            }

            if rec.processing_status.startswith("failed"):
                entry["status"] = "skipped_failed"
                if not dry_run:
                    self._archive_bundle(rec, failed_dir, archive_mode)
                results.append(entry)
                continue

            paper_id = rec.paper_id or rec.bundle_id
            target_paper = sources_papers / paper_id
            target_suppl = sources_suppl / paper_id

            entry["paper_id"] = paper_id

            if dry_run:
                entry["would_copy_main"] = str(target_paper / Path(rec.detected_main_pdf or "").name)
                entry["would_copy_suppl_count"] = len(rec.tabular_supplementary_files) + len(rec.supplementary_pdfs)
                entry["status"] = "dry_run_planned"
                results.append(entry)
                continue

            # Copy main PDF
            try:
                main_src = self.root / rec.detected_main_pdf if rec.detected_main_pdf else None
                if main_src and main_src.exists():
                    target_paper.mkdir(parents=True, exist_ok=True)
                    target_main = target_paper / "main.pdf"
                    shutil.copy2(main_src, target_main)
                    # Manifest
                    manifest = {
                        "paper_id": paper_id, "bundle_id": rec.bundle_id,
                        "original_main_pdf_name": main_src.name,
                        "archived_main_pdf_relative_path": str(target_main.relative_to(self.root)),
                        "sha256": _sha256_file(main_src),
                        "size_bytes": main_src.stat().st_size,
                        "import_source": "article_bundle",
                        "binding_method": "folder_explicit",
                        "created_at": timestamp,
                        "paper_ingest_status": "pending",
                        "warnings": rec.warnings,
                    }
                    (target_paper / "source_manifest.json").write_text(
                        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                entry["error"] = str(e)

            # Copy supplementary files
            suppl_entries = []
            try:
                all_suppl = rec.tabular_supplementary_files + rec.supplementary_pdfs + rec.other_files
                for f_rel in all_suppl:
                    f_src = self.root / f_rel
                    if not f_src.exists():
                        continue
                    target_suppl.mkdir(parents=True, exist_ok=True)
                    f_dst = target_suppl / f_src.name
                    shutil.copy2(f_src, f_dst)
                    suppl_entries.append({
                        "file_name": f_src.name,
                        "relative_path": str(f_dst.relative_to(self.root)),
                        "file_type": f_src.suffix.lstrip("."),
                        "sha256": _sha256_file(f_src),
                        "size_bytes": f_src.stat().st_size,
                        "import_source": "article_bundle",
                        "binding_method": "folder_explicit",
                        "match_confidence": "high",
                        "content_status": "file_found",
                        "preview_status": "none",
                        "entity_index_status": "pending",
                    })

                if suppl_entries:
                    suppl_manifest = {
                        "paper_id": paper_id, "bundle_id": rec.bundle_id,
                        "supplementary_files": suppl_entries,
                        "created_at": timestamp,
                        "import_source": "article_bundle",
                    }
                    (target_suppl / "supplementary_manifest.json").write_text(
                        json.dumps(suppl_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                entry["suppl_error"] = str(e)[:200]

            entry["status"] = "processed"
            entry["main_copied"] = True
            entry["suppl_copied"] = len(suppl_entries)
            rec.processed_at = timestamp
            rec.processing_status = "processed"

            # Archive bundle
            self._archive_bundle(rec, processed_dir, archive_mode)
            results.append(entry)

        # Save registry
        registry = {
            "generated_at": timestamp,
            "total_bundles": len(records),
            "processed": len([r for r in results if r.get("status") == "processed"]),
            "failed": len([r for r in results if r.get("status", "").startswith("skipped_failed")]),
            "bundles": [r.to_dict() for r in records],
            "results": results,
        }
        reg_path = self.root / "10_System" / "registry" / "article_bundle_registry.json"
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

        return registry

    def _archive_bundle(self, rec: ArticleBundleRecord, target_dir: Path, mode: str) -> None:
        if mode == "none":
            return
        bundle_src = self.root / rec.bundle_relative_path
        if not bundle_src.exists():
            return
        target_dir.mkdir(parents=True, exist_ok=True)
        bundle_dst = target_dir / rec.bundle_name
        if mode == "copy":
            if not bundle_dst.exists():
                shutil.copytree(bundle_src, bundle_dst)
        elif mode == "move":
            shutil.move(str(bundle_src), str(bundle_dst))
        rec.archive_status = mode
