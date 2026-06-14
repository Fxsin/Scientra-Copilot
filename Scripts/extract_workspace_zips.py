#!/usr/bin/env python
"""Extract ZIP files in paper workspaces and register contents with notes matching."""
import json, re, shutil, tempfile, zipfile, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.papers.paper_registry import get_paper_entry
from scientra.assets.asset_registry import compute_sha256, _safe_filename


def parse_plos_notes(text: str) -> dict[str, dict]:
    """Parse PLOS-style supplementary notes into a map of s-number -> note info."""
    notes_map = {}
    blocks = re.split(r'\n\n+', text.strip())
    current = None
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        first = lines[0].strip()
        m = re.match(r'^(S\d+\s+(Table|Fig|Data|Text|Raw\s+Images?)\.?)\s*(.*)', first, re.IGNORECASE)
        if m:
            current = {'id': m.group(1), 'description': m.group(3)[:200] if m.group(3) else ''}
        elif current:
            doi_m = re.search(r'(https?://doi\.org/\S+)', first)
            if doi_m:
                current['doi'] = doi_m.group(1)
                snum = re.search(r'(s\d+)$', doi_m.group(1))
                if snum:
                    notes_map[snum.group(1)] = dict(current)
            type_m = re.match(r'^\(([^)]+)\)$', first)
            if type_m:
                current['file_type'] = type_m.group(1).upper()
    return notes_map


def extract_and_register(paper_id: str, zip_rel: str, notes_text: str = ""):
    entry = get_paper_entry(paper_id)
    if not entry:
        print(f'  No entry for {paper_id}')
        return 0

    ws = Path(entry['source_dir'])
    if not ws.is_absolute():
        ws = Path.cwd() / ws

    zip_path = ws / zip_rel
    if not zip_path.exists():
        print(f'  ZIP not found: {zip_path}')
        return 0

    notes_map = parse_plos_notes(notes_text) if notes_text else {}
    print(f'  Parsed {len(notes_map)} notes from notes file')

    reg_file = ws / 'paper_assets.json'
    reg = json.loads(reg_file.read_text(encoding='utf-8'))

    extract_dir = Path(tempfile.mkdtemp(prefix='scx_'))
    registered = 0
    matched = 0

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            members = zf.namelist()
            print(f'  ZIP contains {len(members)} files')

            for member in members:
                try:
                    zf.extract(member, extract_dir)
                except Exception as e:
                    print(f'    Failed to extract {member}: {e}')
                    continue

                extracted = extract_dir / member
                # Handle nested paths
                if not extracted.is_file():
                    for ef in extract_dir.rglob(Path(member).name):
                        if ef.is_file():
                            extracted = ef
                            break
                if not extracted.is_file():
                    continue

                name = Path(member).name.lower()
                ext = Path(member).suffix.lower()

                # Classify
                if ext in ('.xlsx', '.xls'):
                    atype = 'supplementary_table'
                elif ext == '.pdf':
                    atype = 'supplementary_pdf'
                elif ext in ('.csv', '.tsv'):
                    atype = 'dataset'
                elif ext in ('.png', '.jpg', '.jpeg', '.tif', '.tiff'):
                    atype = 'figure_image'
                elif ext in ('.docx', '.doc'):
                    atype = 'supplementary_table' if 'table' in name else 'attachment'
                else:
                    atype = 'attachment'

                # Match note by DOI suffix
                matched_note = None
                for snum, note in notes_map.items():
                    if snum in member:
                        matched_note = note
                        matched += 1
                        break

                # SHA256 dedup
                sha = compute_sha256(str(extracted))
                dup = any(a.get('sha256') == sha for a in reg.get('assets', []))
                if dup:
                    continue

                # Target
                dirs = {'supplementary_pdf': 'assets/supplementary',
                        'supplementary_table': 'assets/tables',
                        'dataset': 'assets/datasets',
                        'figure_image': 'assets/images',
                        'attachment': 'assets/attachments'}
                sub = dirs.get(atype, 'assets/attachments')
                td = ws / sub
                td.mkdir(parents=True, exist_ok=True)

                safe = _safe_filename(Path(member).name)
                target = td / safe
                c = 1
                while target.exists():
                    target = td / f'{Path(safe).stem}_{c}{Path(safe).suffix}'
                    c += 1

                shutil.copy2(str(extracted), str(target))

                idx = len(reg.get('assets', []))
                short = paper_id.replace('paper_', '')[:8]
                aid = f'asset_{short}_{idx:04d}'
                now = datetime.now(timezone.utc).isoformat()

                reg.setdefault('assets', []).append({
                    'asset_id': aid, 'paper_id': paper_id, 'asset_type': atype,
                    'filename': safe, 'original_filename': Path(member).name,
                    'relative_path': str(target.relative_to(ws)), 'sha256': sha,
                    'size_bytes': target.stat().st_size,
                    'mime_type': 'application/octet-stream', 'extension': ext,
                    'source': 'zip_extraction', 'status': 'registered',
                    'created_at': now, 'updated_at': now,
                    'notes': f'Extracted from {zip_path.name}',
                    'warnings': [], 'errors': [],
                    'asset_title': matched_note.get('id', '') if matched_note else '',
                    'asset_description': matched_note.get('description', '') if matched_note else '',
                    'source_reference': matched_note.get('doi', '') if matched_note else '',
                    'metadata_source': 'user_notes' if matched_note else 'auto',
                })
                reg.setdefault('asset_counts', {})
                reg['asset_counts'][atype] = reg['asset_counts'].get(atype, 0) + 1
                registered += 1

                note_label = f' [{matched_note["id"]}]' if matched_note else ''
                print(f'    {Path(member).name} -> {atype}{note_label}')
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)

    reg['last_updated'] = datetime.now(timezone.utc).isoformat()
    reg_file.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  Result: {registered} registered, {matched} matched to notes')
    return registered


if __name__ == '__main__':
    print("=" * 60)
    print("  ZIP Extraction & Notes Matching")
    print("=" * 60)

    # Retrotransposon
    print("\n--- 2024 Retrotransposon ---")
    notes_file = Path('01_Sources/papers/2024_Retrotransposon_Mediated_Disruption_Of_A_Chitin_Synthase_Gene/10_1371_journal_pbio_3002704.txt')
    notes = notes_file.read_text(encoding='utf-8') if notes_file.exists() else ''
    extract_and_register('paper_1bc3ea965f7db3fe', '10_1371_journal_pbio_3002704.zip', notes)

    # HaVipR1
    print("\n--- 2025 HaVipR1 ---")
    notes_file = Path('01_Sources/papers/2025_Disruption_Of_HaVipR1_Confers_Vip3Aa_Resistance_In_The_Moth_C/10_1371_journal_pbio_3003165.txt')
    notes = notes_file.read_text(encoding='utf-8') if notes_file.exists() else ''
    extract_and_register('paper_272c3256e0e93572', '10_1371_journal_pbio_3003165.zip', notes)

    print("\nDone!")
