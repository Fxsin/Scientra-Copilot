"""
Web Import Center — Drag-and-drop import with staging, plan, and confirm flow.

Core principles:
1. Uploaded files go to staging, NEVER directly to 01_Sources/ or 03_Assets/
2. Default copy-only, never move
3. Never delete user files
4. All paths are relative
5. No absolute paths exposed
6. Every import generates an import plan requiring user confirmation
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from scientra.io.storage_layout import StorageLayout

# ── Constants ──

MAIN_PDF_KEYWORDS = ["main", "paper", "article", "manuscript", "fulltext", "full_text"]
SUPP_PDF_KEYWORDS = [
    "supplementary", "supplement", "supporting", "appendix",
    "supplemental", "source_data", "si_", "si ", "suppl", "table",
]
ALLOWED_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".tsv", ".docx", ".zip",
}
TABULAR_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv"}
SUPPLEMENTARY_EXTENSIONS = {".pdf", ".docx", ".zip"}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB per file
MAX_SESSION_FILES = 200


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_filename(filename: str) -> str:
    """Sanitize filename: replace path separators and dangerous chars."""
    # Strip null bytes immediately
    name = filename.replace("\x00", "")
    # Replace all path separators with underscore FIRST
    name = name.replace("\\", "_").replace("/", "_")
    # Now extract the last component (in case there were path parts)
    # os.path.basename handles both / and \ on all platforms
    name = os.path.basename(name)
    # Handle parent directory references that may remain
    while name.startswith(".."):
        name = "_" + name[2:] if len(name) > 2 else "_"
    # Strip leading dots (hidden files are OK, but not ".")
    if name in (".", ".."):
        name = "unnamed_file"
    # Remove any remaining unsafe chars
    name = name.strip()
    if not name:
        name = "unnamed_file"
    return name


def _validate_relative_path(relative_path: str) -> str:
    """Validate and sanitize a relative path. Raises ValueError on path traversal."""
    # Normalize path separators
    path = relative_path.replace("\\", "/")
    # Reject absolute paths
    if os.path.isabs(path) or path.startswith("/"):
        raise ValueError(f"Absolute path not allowed: {relative_path}")
    # Reject path traversal
    parts = path.split("/")
    cleaned: list[str] = []
    for p in parts:
        if p == "..":
            raise ValueError(f"Path traversal not allowed: {relative_path}")
        if p in ("", "."):
            continue
        cleaned.append(p)
    if not cleaned:
        raise ValueError(f"Empty path after sanitization: {relative_path}")
    return "/".join(cleaned)


def _staging_path(sl: StorageLayout, session_id: str) -> Path:
    """Get the staging directory for a session."""
    base = sl.get_path("inbox.web_uploads_staging")
    return base / session_id


def _planned_path(sl: StorageLayout, session_id: str) -> Path:
    """Get the planned directory for a session."""
    base = sl.get_path("inbox.web_uploads_planned")
    return base / session_id


def _imported_path(sl: StorageLayout, session_id: str) -> Path:
    """Get the imported directory for a session."""
    base = sl.get_path("inbox.web_uploads_imported")
    return base / session_id


def _failed_path(sl: StorageLayout, session_id: str) -> Path:
    """Get the failed directory for a session."""
    base = sl.get_path("inbox.web_uploads_failed")
    return base / session_id


# ── Main PDF detection ──

def _score_pdf(filename: str, size: int) -> tuple[int, str]:
    """Score a PDF for main-paper likelihood. Returns (score, reason)."""
    name_lower = filename.lower()
    score = 0
    reasons: list[str] = []

    # Keyword bonus
    for kw in MAIN_PDF_KEYWORDS:
        if kw in name_lower:
            score += 3
            reasons.append(f"main_keyword:{kw}")

    # Supplementary penalty
    for kw in SUPP_PDF_KEYWORDS:
        if kw in name_lower:
            score -= 5
            reasons.append(f"supp_keyword:{kw}")

    # Size heuristic: very small PDFs (< 50KB) are unlikely to be main
    if size < 50 * 1024:
        score -= 2
        reasons.append("very_small_pdf")

    # Large PDFs get a small bonus
    if size > 500 * 1024:
        score += 1
        reasons.append("large_pdf")

    reason = ";".join(reasons) if reasons else "default"
    return score, reason


def _detect_main_pdf(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Detect main PDF from uploaded files list. Returns detection result or None."""
    pdfs = [f for f in files if f["extension"] == ".pdf"]
    if not pdfs:
        return None

    if len(pdfs) == 1:
        return {
            "filename": pdfs[0]["filename"],
            "relative_path": pdfs[0]["relative_path"],
            "detection_reason": "single_pdf_only",
            "confidence": "high",
        }

    # Score each PDF
    scored: list[tuple[int, dict[str, Any], int]] = []
    for p in pdfs:
        score, reason = _score_pdf(p["filename"], p["size"])
        scored.append((score, p, p["size"]))

    # Sort: highest score, then largest file
    scored.sort(key=lambda x: (-x[0], -x[2]))
    best_score, best_pdf, best_size = scored[0]

    if best_score > 0:
        return {
            "filename": best_pdf["filename"],
            "relative_path": best_pdf["relative_path"],
            "detection_reason": "filename_keyword_match",
            "confidence": "high" if best_score >= 3 else "medium",
        }

    # Fallback: largest PDF
    return {
        "filename": best_pdf["filename"],
        "relative_path": best_pdf["relative_path"],
        "detection_reason": "largest_pdf_fallback",
        "confidence": "low",
    }


def _classify_files(files: list[dict[str, Any]], main_pdf: dict[str, Any] | None) -> dict[str, Any]:
    """Classify files as supplementary, unsupported, etc."""
    suppl: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    main_path = main_pdf.get("relative_path", "") if main_pdf else ""

    for f in files:
        if f["relative_path"] == main_path:
            continue  # Skip main PDF

        ext = f["extension"]
        if ext in TABULAR_EXTENSIONS:
            suppl.append({
                "filename": f["filename"],
                "relative_path": f["relative_path"],
                "file_type": "spreadsheet",
                "binding_method": "session_explicit",
                "match_confidence": "high",
                "entity_index_eligible": True,
            })
        elif ext == ".pdf":
            score, reason = _score_pdf(f["filename"], f["size"])
            suppl.append({
                "filename": f["filename"],
                "relative_path": f["relative_path"],
                "file_type": "supplementary_pdf",
                "binding_method": "session_explicit",
                "match_confidence": "medium" if score >= 0 else "low",
                "entity_index_eligible": False,
            })
        elif ext in (".docx",):
            suppl.append({
                "filename": f["filename"],
                "relative_path": f["relative_path"],
                "file_type": "document",
                "binding_method": "session_explicit",
                "match_confidence": "medium",
                "entity_index_eligible": False,
            })
        elif ext == ".zip":
            suppl.append({
                "filename": f["filename"],
                "relative_path": f["relative_path"],
                "file_type": "archive",
                "binding_method": "session_explicit",
                "match_confidence": "low",
                "entity_index_eligible": False,
                "note": "ZIP files are recorded but not automatically extracted.",
            })
        else:
            unsupported.append({
                "filename": f["filename"],
                "relative_path": f["relative_path"],
                "extension": ext,
                "reason": f"Unsupported file type: {ext}",
            })

    return {"supplementary": suppl, "unsupported": unsupported}


def _propose_article_folder(files: list[dict[str, Any]], main_pdf: dict[str, Any] | None) -> str:
    """Propose an article folder name based on uploaded files."""
    if main_pdf:
        # Use main PDF name minus extension
        base = main_pdf["filename"]
        # Remove extension
        for ext in [".pdf", ".PDF"]:
            if base.endswith(ext):
                base = base[:-len(ext)]
                break
        # Clean up common separators
        base = base.strip().replace(" ", "_")
        # Remove special chars but keep alphanum, underscore, dash
        clean = "".join(c for c in base if c.isalnum() or c in "_-")
        if clean:
            return clean[:80]

    # Fallback: use first file's folder name if available
    for f in files:
        rp = f.get("relative_path", "")
        if "/" in rp:
            folder = rp.split("/")[0]
            clean = "".join(c for c in folder if c.isalnum() or c in "_-")
            if clean:
                return clean[:80]

    # Last resort
    return f"import_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


class WebImportSession:
    """Manages a single web upload session from staging to confirm."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.sl = StorageLayout(root)
        self.sl.load()
        self.root = self.sl.root

    # ── Session management ──

    def create_session(self) -> dict[str, Any]:
        """Create a new upload session."""
        session_id = f"web_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        staging_dir = _staging_path(self.sl, session_id)
        staging_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "upload_session_id": session_id,
            "created_at": _utc_now(),
            "status": "created",
            "files": [],
        }
        (staging_dir / "upload_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "upload_session_id": session_id,
            "staging_path": str(staging_dir.relative_to(self.root)),
            "created_at": manifest["created_at"],
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Get session info."""
        staging_dir = _staging_path(self.sl, session_id)
        if not staging_dir.exists():
            return {"error": "Session not found", "upload_session_id": session_id}

        manifest_path = staging_dir / "upload_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"upload_session_id": session_id, "files": [], "status": "unknown"}

        # Enrich with computed fields
        files = manifest.get("files", [])
        pdfs = [f for f in files if f["extension"] == ".pdf"]
        tables = [f for f in files if f["extension"] in TABULAR_EXTENSIONS]
        suppl_pdfs = [f for f in files if f["extension"] == ".pdf"]
        unsupported = [f for f in files if f.get("status") == "unsupported"]

        return {
            "upload_session_id": session_id,
            "staging_path": str(staging_dir.relative_to(self.root)),
            "status": manifest.get("status", "unknown"),
            "created_at": manifest.get("created_at"),
            "file_count": len(files),
            "total_size": sum(f.get("size", 0) for f in files),
            "detected_pdfs": len(pdfs),
            "detected_tables": len(tables),
            "detected_supplementary_pdfs": len(suppl_pdfs),
            "unsupported_files": len(unsupported),
            "files": files,
        }

    # ── File upload ──

    def add_files(self, session_id: str, file_items: list[tuple[str, bytes, str]]) -> dict[str, Any]:
        """Add files to a session.

        Args:
            session_id: Session ID.
            file_items: List of (original_filename, content_bytes, relative_path) tuples.
                        relative_path may be just the filename or a sub-path from folder upload.

        Returns:
            Dict with upload results.
        """
        staging_dir = _staging_path(self.sl, session_id)
        if not staging_dir.exists():
            return {"error": "Session not found", "upload_session_id": session_id}

        # Load existing manifest
        manifest_path = staging_dir / "upload_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"upload_session_id": session_id, "created_at": _utc_now(), "status": "created", "files": []}

        existing_files = manifest.get("files", [])
        if len(existing_files) + len(file_items) > MAX_SESSION_FILES:
            return {
                "error": f"Too many files. Maximum {MAX_SESSION_FILES} per session.",
                "upload_session_id": session_id,
            }

        uploaded: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for orig_name, content, rel_path in file_items:
            safe_name = _safe_filename(orig_name)

            # Validate relative path
            try:
                clean_rel = _validate_relative_path(rel_path)
            except ValueError as e:
                rejected.append({"filename": safe_name, "relative_path": rel_path, "reason": str(e)})
                continue

            # Size check
            if len(content) > MAX_FILE_SIZE:
                rejected.append({
                    "filename": safe_name, "relative_path": clean_rel,
                    "reason": f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})",
                })
                continue

            # Extension check
            ext = Path(safe_name).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                rejected.append({
                    "filename": safe_name, "relative_path": clean_rel,
                    "reason": f"Unsupported file type: {ext}",
                    "status": "unsupported",
                })
                # Still record unsupported files in manifest
                file_record = {
                    "filename": safe_name,
                    "relative_path": clean_rel,
                    "size": len(content),
                    "extension": ext,
                    "sha256": _sha256_bytes(content),
                    "status": "unsupported",
                }
                existing_files.append(file_record)
                continue

            # Write file to staging
            # If the relative path has subdirectories, preserve structure
            dest = staging_dir / clean_rel
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Handle duplicate filenames
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                counter = 1
                while dest.exists():
                    dest = dest.parent / f"{stem}_{counter}{suffix}"
                    counter += 1

            dest.write_bytes(content)

            file_record = {
                "filename": safe_name,
                "relative_path": str(dest.relative_to(staging_dir)).replace("\\", "/"),
                "size": len(content),
                "extension": ext,
                "sha256": _sha256_bytes(content),
                "status": "uploaded",
            }
            uploaded.append(file_record)
            existing_files.append(file_record)

        # Update manifest
        manifest["files"] = existing_files
        manifest["status"] = "uploading"
        manifest["updated_at"] = _utc_now()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "upload_session_id": session_id,
            "uploaded": len(uploaded),
            "rejected": len(rejected),
            "uploaded_files": uploaded,
            "rejected_files": rejected,
            "total_files": len(existing_files),
        }

    # ── Import plan generation ──

    def generate_plan(self, session_id: str) -> dict[str, Any]:
        """Generate an import plan for the session."""
        staging_dir = _staging_path(self.sl, session_id)
        if not staging_dir.exists():
            return {"error": "Session not found", "upload_session_id": session_id}

        manifest_path = staging_dir / "upload_manifest.json"
        if not manifest_path.exists():
            return {"error": "No files uploaded", "upload_session_id": session_id}

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest.get("files", [])
        uploaded_files = [f for f in files if f.get("status") == "uploaded"]

        if not uploaded_files:
            return {
                "upload_session_id": session_id,
                "detected_import_type": "unsupported",
                "errors": ["No valid files to import."],
                "requires_manual_review": True,
            }

        # Detect main PDF
        main_pdf = _detect_main_pdf(uploaded_files)
        classifications = _classify_files(uploaded_files, main_pdf)
        proposed_folder = _propose_article_folder(uploaded_files, main_pdf)

        # Determine import type
        warnings: list[str] = []
        errors: list[str] = []
        requires_review = False
        main_pdf_candidates: list[dict[str, Any]] = []

        if main_pdf is None:
            # No PDF at all
            has_tabular = any(f["extension"] in TABULAR_EXTENSIONS for f in uploaded_files)
            if has_tabular:
                plan = {
                    "upload_session_id": session_id,
                    "detected_import_type": "loose_supplementary",
                    "proposed_article_folder": None,
                    "main_pdf": None,
                    "supplementary_files": classifications["supplementary"],
                    "unsupported_files": classifications["unsupported"],
                    "warnings": ["No PDF detected. These files cannot enter the entity index until manually bound to a parent paper."],
                    "errors": [],
                    "requires_manual_review": True,
                    "suggested_next_action": "manual_binding_required",
                    "message": "This looks like loose supplementary data. It cannot enter the entity index until manually bound to a parent paper.",
                }
            else:
                plan = {
                    "upload_session_id": session_id,
                    "detected_import_type": "unsupported",
                    "proposed_article_folder": None,
                    "main_pdf": None,
                    "supplementary_files": [],
                    "unsupported_files": classifications["unsupported"],
                    "warnings": [],
                    "errors": ["No PDF or tabular data files detected."],
                    "requires_manual_review": True,
                    "suggested_next_action": "cannot_import",
                }
            # Save plan even for loose/unsupported
            _save_plan(self.sl, session_id, plan)
            manifest["status"] = "planned"
            manifest["updated_at"] = _utc_now()
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return plan

        # Check if we have multiple PDFs
        pdfs_in_session = [f for f in uploaded_files if f["extension"] == ".pdf"]
        if len(pdfs_in_session) > 1:
            # Score all PDFs and check if there's ambiguity
            scored_pdfs = []
            for p in pdfs_in_session:
                score, reason = _score_pdf(p["filename"], p["size"])
                scored_pdfs.append({
                    "filename": p["filename"],
                    "relative_path": p["relative_path"],
                    "score": score,
                    "reason": reason,
                })
            scored_pdfs.sort(key=lambda x: -x["score"])

            # If top two are close or confidence is low, require manual review
            top_score = scored_pdfs[0]["score"] if scored_pdfs else 0
            if main_pdf["confidence"] == "low":
                requires_review = True
                warnings.append("Multiple PDFs detected with similar likelihood. Please select the main paper PDF.")
                main_pdf_candidates = scored_pdfs

            # If there are multiple PDFs and any has supplementary keywords, warn
            suppl_pdfs = [p for p in scored_pdfs if p["score"] <= 0]
            if suppl_pdfs:
                warnings.append(f"{len(suppl_pdfs)} PDF(s) identified as likely supplementary (demoted by keywords).")

        # Check for unsupported files
        if classifications["unsupported"]:
            unsupported_names = [u["filename"] for u in classifications["unsupported"]]
            warnings.append(f"Unsupported files will be skipped: {', '.join(unsupported_names)}")

        # Build plan
        plan = {
            "upload_session_id": session_id,
            "detected_import_type": "article_bundle" if main_pdf else "loose_supplementary",
            "proposed_article_folder": proposed_folder,
            "main_pdf": main_pdf,
            "supplementary_files": classifications["supplementary"],
            "unsupported_files": classifications["unsupported"],
            "warnings": warnings,
            "errors": errors,
            "requires_manual_review": requires_review,
            "suggested_next_action": "needs_review" if requires_review else "confirm_import",
        }

        if main_pdf_candidates:
            plan["main_pdf_candidates"] = main_pdf_candidates

        # Save plan to planned/
        _save_plan(self.sl, session_id, plan)

        # Update manifest status
        manifest["status"] = "planned"
        manifest["updated_at"] = _utc_now()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return plan

    # ── Plan update (manual override) ──

    def update_plan(self, session_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update import plan with manual selections."""
        planned_dir = _planned_path(self.sl, session_id)
        plan_path = planned_dir / "import_plan.json"

        if not plan_path.exists():
            return {"error": "No plan exists. Generate a plan first.", "upload_session_id": session_id}

        plan = json.loads(plan_path.read_text(encoding="utf-8"))

        # Update main PDF selection
        if "main_pdf_relative_path" in updates:
            staging_dir = _staging_path(self.sl, session_id)
            new_main_path = updates["main_pdf_relative_path"]
            # Verify this file exists in staging
            full_path = staging_dir / new_main_path
            if not full_path.exists():
                return {"error": f"File not found in staging: {new_main_path}"}

            plan["main_pdf"] = {
                "filename": Path(new_main_path).name,
                "relative_path": new_main_path,
                "detection_reason": "manual_selection",
                "confidence": "high",
            }
            plan["requires_manual_review"] = False
            plan["warnings"] = [w for w in plan.get("warnings", []) if "Multiple PDFs" not in w]

        # Update article folder name
        if "article_folder_name" in updates:
            safe = "".join(c for c in updates["article_folder_name"] if c.isalnum() or c in "_-")[:80]
            if safe:
                plan["proposed_article_folder"] = safe

        # Update import type
        if "import_type" in updates:
            allowed = {"article_bundle", "single_paper", "loose_supplementary"}
            if updates["import_type"] in allowed:
                plan["detected_import_type"] = updates["import_type"]

        # Update supplementary files selection
        if "supplementary_relative_paths" in updates:
            selected = set(updates["supplementary_relative_paths"])
            plan["supplementary_files"] = [
                s for s in plan.get("supplementary_files", [])
                if s["relative_path"] in selected
            ]

        plan["updated_at"] = _utc_now()
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        return {**plan, "status": "plan_updated"}

    # ── Confirm import ──

    def confirm_import(self, session_id: str) -> dict[str, Any]:
        """Execute the import plan: copy files from staging to inbox."""
        planned_dir = _planned_path(self.sl, session_id)
        plan_path = planned_dir / "import_plan.json"

        if not plan_path.exists():
            return {"error": "No plan exists. Generate and review a plan first.", "upload_session_id": session_id}

        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        staging_dir = _staging_path(self.sl, session_id)

        import_type = plan.get("detected_import_type", "unsupported")
        main_pdf = plan.get("main_pdf")
        suppl_files = plan.get("supplementary_files", [])
        folder_name = plan.get("proposed_article_folder", f"import_{session_id}")

        warnings: list[str] = []
        files_copied = 0
        failed_files: list[dict[str, Any]] = []

        if import_type == "unsupported":
            return {
                "status": "error",
                "upload_session_id": session_id,
                "error": "Cannot import unsupported content.",
            }

        if import_type == "loose_supplementary":
            # Copy to loose supplementary inbox
            target_dir = self.sl.get_path("inbox.loose_supplementary_new")
            target_dir.mkdir(parents=True, exist_ok=True)

            for sf in suppl_files:
                src = staging_dir / sf["relative_path"]
                if not src.exists():
                    failed_files.append({"filename": sf["filename"], "error": "Source file not found in staging"})
                    continue
                try:
                    dst = target_dir / sf["filename"]
                    # Handle duplicates
                    if dst.exists():
                        stem, suffix = dst.stem, dst.suffix
                        counter = 1
                        while dst.exists():
                            dst = target_dir / f"{stem}_{counter}{suffix}"
                            counter += 1
                    shutil.copy2(src, dst)
                    files_copied += 1
                except Exception as e:
                    failed_files.append({"filename": sf["filename"], "error": str(e)[:200]})

            _archive_session(self.sl, session_id, "imported")

            return {
                "status": "imported",
                "import_type": "loose_supplementary",
                "target_path": str(target_dir.relative_to(self.root)),
                "files_copied": files_copied,
                "failed_files": failed_files,
                "warnings": warnings,
                "next_steps": [
                    "These files are loose supplementary and require manual binding to enter the entity index.",
                    "Check /import for review needed items.",
                ],
            }

        # article_bundle or single_paper: copy to article_bundles/new/
        target_dir = self.sl.get_path("inbox.article_bundles_new") / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy main PDF
        if main_pdf:
            src = staging_dir / main_pdf["relative_path"]
            if src.exists():
                try:
                    dst = target_dir / main_pdf["filename"]
                    # Always use main.pdf as canonical name
                    canonical = target_dir / "main.pdf"
                    shutil.copy2(src, canonical)
                    files_copied += 1
                except Exception as e:
                    failed_files.append({"filename": main_pdf["filename"], "error": str(e)[:200]})
            else:
                failed_files.append({"filename": main_pdf["filename"], "error": "Source file not found in staging"})

        # Copy supplementary files
        for sf in suppl_files:
            src = staging_dir / sf["relative_path"]
            if not src.exists():
                failed_files.append({"filename": sf["filename"], "error": "Source file not found in staging"})
                continue
            try:
                dst = target_dir / sf["filename"]
                if dst.exists():
                    stem, suffix = dst.stem, dst.suffix
                    counter = 1
                    while dst.exists():
                        dst = target_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                shutil.copy2(src, dst)
                files_copied += 1
            except Exception as e:
                failed_files.append({"filename": sf["filename"], "error": str(e)[:200]})

        # Generate bundle manifest in the target directory
        manifest_target = {
            "import_source": "web_import",
            "upload_session_id": session_id,
            "imported_at": _utc_now(),
            "import_type": import_type,
            "main_pdf": {"filename": main_pdf["filename"]} if main_pdf else None,
            "supplementary_count": len(suppl_files),
            "files_copied": files_copied,
            "failed_files": failed_files,
        }
        (target_dir / "web_import_manifest.json").write_text(
            json.dumps(manifest_target, ensure_ascii=False, indent=2), encoding="utf-8")

        # Archive session
        _archive_session(self.sl, session_id, "imported")

        return {
            "status": "imported",
            "import_type": import_type,
            "article_bundle_path": str(target_dir.relative_to(self.root)),
            "files_copied": files_copied,
            "failed_files": failed_files,
            "processing_started": True,
            "processing_result": {
                "main_pdf": main_pdf["filename"] if main_pdf else None,
                "supplementary_count": len(suppl_files),
                "warnings": warnings,
            },
            "next_steps": [
                "Check /library after processing",
                "Check /assets for extracted figures, tables, entities",
                "Use /chat after embeddings are updated",
                "Run: python Scripts/process_article_bundles.py --process",
            ],
        }


def _save_plan(sl: StorageLayout, session_id: str, plan: dict[str, Any]) -> None:
    """Save import plan to planned/ directory."""
    planned_dir = _planned_path(sl, session_id)
    planned_dir.mkdir(parents=True, exist_ok=True)
    plan_path = planned_dir / "import_plan.json"
    plan_with_meta = {**plan, "generated_at": _utc_now(), "plan_version": "1.0"}
    plan_path.write_text(json.dumps(plan_with_meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _archive_session(sl: StorageLayout, session_id: str, status: str) -> None:
    """Move session manifest to imported/ or failed/ directory."""
    staging_dir = _staging_path(sl, session_id)
    if status == "imported":
        archive_base = sl.get_path("inbox.web_uploads_imported")
    else:
        archive_base = sl.get_path("inbox.web_uploads_failed")

    archive_dir = archive_base / session_id
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Copy manifest if it exists
    manifest_path = staging_dir / "upload_manifest.json"
    if manifest_path.exists():
        shutil.copy2(manifest_path, archive_dir / "upload_manifest.json")

    # Also copy plan if it exists
    planned_dir = _planned_path(sl, session_id)
    plan_path = planned_dir / "import_plan.json"
    if plan_path.exists():
        shutil.copy2(plan_path, archive_dir / "import_plan.json")


def _sha256_bytes(content: bytes) -> str:
    h = hashlib.sha256()
    h.update(content)
    return h.hexdigest()


# ── Module-level convenience ──

def create_session(root: str | Path | None = None) -> dict[str, Any]:
    return WebImportSession(root).create_session()


def list_sessions(root: str | Path | None = None) -> list[dict[str, Any]]:
    """List all web upload sessions (from staging only)."""
    sl = StorageLayout(root)
    sl.load()
    staging_base = sl.get_path("inbox.web_uploads_staging")
    sessions: list[dict[str, Any]] = []
    if staging_base.exists():
        for d in sorted(staging_base.iterdir()):
            if d.is_dir():
                mf = d / "upload_manifest.json"
                if mf.exists():
                    try:
                        m = json.loads(mf.read_text(encoding="utf-8"))
                        sessions.append({
                            "upload_session_id": m.get("upload_session_id", d.name),
                            "status": m.get("status", "unknown"),
                            "file_count": len(m.get("files", [])),
                            "created_at": m.get("created_at"),
                        })
                    except Exception:
                        pass
    return sessions
