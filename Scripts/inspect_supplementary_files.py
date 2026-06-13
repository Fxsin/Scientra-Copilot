"""Survey TRUE supplementary files in project — Phase 2C-B Quality Guard.

Strictly distinguishes:
  1. true_supplementary_files (xlsx, csv, tsv, labeled supplementary txt/zip/pdf)
  2. parsed_text_sources (03_Summary/raw_text/*.txt)
  3. original_pdfs (01_PDF/*.pdf)
  4. generated_assets (06_PDF_DataAssets/*.json)
  5. ignored_files (everything else)
"""
import json, os, re
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent.parent
os.chdir(str(root))

# ── Classification rules ──

TRUE_SUPP_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.tsv'}
TRUE_SUPP_KEYWORDS = {
    'supplementary', 'supplement', 'suppl', 'supporting',
    'additional', 'dataset', 'data', 'table', 'source data',
    'source_data', 'si_table', 'si_fig',
}
CANDIDATE_SUPP_EXTENSIONS = {'.zip', '.docx'}
SUPP_PDF_KEYWORDS = {'supplementary', 'supplement', 'suppl', 'supporting', 'si_', 'si '}

EXCLUDE_DIRS = {'node_modules', '.git', '__pycache__', 'web', 'logs', '.claude',
                '06_PDF_DataAssets', '02_Metadata', '03_Evidence', '04_VectorDB',
                '05_Index', '07_Workflows', 'Config', 'reports', 'scientra', 'Tests',
                'Scripts', 'docs', '.vscode', '00_Inbox', '03_Summary', '01_PDF'}

# 00_Supplementary/inbox/ is the high-priority manual import source
INBOX_DIR = '00_Supplementary[\\/]inbox'

EXCLUDE_PATH_PATTERNS = [
    r'03_Summary[\\/]raw_text', r'01_PDF[\\/]', r'evidence\.json',
    r'figures\.json', r'tables\.json', r'agent_chunks\.jsonl',
    r'asset_registry\.json', r'\.quality\.jsonl', r'\.tmp$',
    r'supplementary_links\.json',
    # Do NOT exclude 00_Supplementary/ — it IS a true supplementary source
]


def is_true_supplementary_file(file_path: str, file_name: str, ext: str) -> bool:
    """Check if a file is a TRUE supplementary data file."""
    path_lower = file_path.lower()
    name_lower = file_name.lower()

    # Reject excluded paths immediately
    for pat in EXCLUDE_PATH_PATTERNS:
        if re.search(pat, path_lower):
            return False

    # Check for 01_PDF — only allow if filename indicates supplement
    if '01_pdf' in path_lower or 'paper' in path_lower and ext == '.pdf':
        return any(kw in name_lower for kw in SUPP_PDF_KEYWORDS)

    # True tabular supplementary files
    if ext in TRUE_SUPP_EXTENSIONS:
        return True

    # txt files: only if path/name contains supplementary keywords
    if ext == '.txt':
        return any(kw in name_lower for kw in TRUE_SUPP_KEYWORDS)

    # zip/docx: candidate only
    if ext in CANDIDATE_SUPP_EXTENSIONS:
        return any(kw in name_lower for kw in TRUE_SUPP_KEYWORDS)

    # PDF: only if filename has supplementary keywords
    if ext == '.pdf':
        return any(kw in name_lower for kw in SUPP_PDF_KEYWORDS)

    return False


def classify_file(f: Path) -> str:
    """Classify a file into one of five categories."""
    rp = str(f.relative_to(root))
    rp_lower = rp.lower()

    if '00_supplementary' in rp_lower:
        return 'manual_import'
    if '03_summary' in rp_lower and 'raw_text' in rp_lower:
        return 'parsed_text_source'
    if '01_pdf' in rp_lower:
        return 'original_pdf'
    if '06_pdf_dataassets' in rp_lower or 'asset_registry' in rp_lower:
        return 'generated_asset'
    if '02_metadata' in rp_lower:
        return 'generated_asset'
    if '03_evidence' in rp_lower:
        return 'generated_asset'
    return 'unknown'


# ── Main inventory ──

def main():
    print("=" * 60)
    print("Supplementary File Inventory — Phase 2C-B Quality Guard")
    print("=" * 60)

    all_extensions = {'.xlsx', '.xls', '.csv', '.tsv', '.txt', '.docx', '.pdf', '.zip'}
    true_supp_files: list[dict] = []
    parsed_text_sources: list[dict] = []
    original_pdfs: list[dict] = []
    generated_assets: list[dict] = []
    ignored_files: list[dict] = []

    for ext in all_extensions:
        for f in root.rglob(f"*{ext}"):
            skip = False
            for part in f.parts:
                if part in EXCLUDE_DIRS:
                    skip = True
                    break
            if skip:
                continue
            if f.name.startswith("Scientra_"):
                continue

            rp = str(f.relative_to(root))
            entry = {"path": rp, "name": f.name, "ext": f.suffix.lower(), "size": f.stat().st_size}

            if is_true_supplementary_file(rp, f.name, ext):
                true_supp_files.append(entry)
            else:
                cat = classify_file(f)
                if cat == 'parsed_text_source':
                    parsed_text_sources.append(entry)
                elif cat == 'original_pdf':
                    original_pdfs.append(entry)
                elif cat == 'generated_asset':
                    generated_assets.append(entry)
                elif cat == 'manual_import':
                    # Files in 00_Supplementary but not matched by extension rules
                    true_supp_files.append(entry)
                else:
                    ignored_files.append(entry)

    xlsx_csv_count = sum(1 for f in true_supp_files if f['ext'] in {'.xlsx','.xls','.csv','.tsv'})
    inbox_count = sum(1 for f in true_supp_files if '00_supplementary' in f['path'].lower())
    print(f"\nTRUE supplementary data files:   {len(true_supp_files)}")
    print(f"  xlsx/csv/tsv:                   {xlsx_csv_count}")
    print(f"  from 00_Supplementary/inbox/:   {inbox_count}")
    print(f"Parsed text sources (excluded):   {len(parsed_text_sources)}")
    print(f"Original PDFs (excluded):         {len(original_pdfs)}")
    print(f"Generated assets (excluded):      {len(generated_assets)}")
    print(f"Other ignored:                    {len(ignored_files)}")

    if len(true_supp_files) == 0:
        print(f"\n*** No local tabular supplementary data files found. ***")

    # Write report
    report_path = root / "06_PDF_DataAssets" / "00_registry" / "supplementary_file_inventory.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    true_ext_dist = Counter(f["ext"] for f in true_supp_files)

    lines = [
        "# Supplementary File Inventory — Phase 2C-B (Quality Guard)", "",
        "## Summary", "",
        f"- **True supplementary data files**: {len(true_supp_files)}",
        f"- **xlsx/csv/tsv (tabular)**: {xlsx_csv_count}",
        f"- **Parsed text sources (excluded)**: {len(parsed_text_sources)}",
        f"- **Original PDFs (excluded)**: {len(original_pdfs)}",
        f"- **Generated assets (excluded)**: {len(generated_assets)}",
        "", "## True Supplementary Files", "",
    ]
    if true_supp_files:
        for f in true_supp_files:
            lines.append(f"- `{f['path']}` ({f['size']} bytes)")
    else:
        lines.append("- **(none)**")
        lines.extend([
            "", "> No local tabular supplementary data files found.",
            "> All supplementary table data resides on publisher websites.",
            "> SupplementaryTableLinks use `content_status='file_missing'`.",
        ])

    lines.extend(["", "## Excluded: Parsed Text Sources", "",
        f"- {len(parsed_text_sources)} raw_text files excluded from matching"])
    for f in parsed_text_sources[:5]:
        lines.append(f"  - `{f['path']}`")

    lines.extend(["", "## Quality Guard Notes", "",
        "- Raw text files (03_Summary/raw_text/) are NEVER matched as supplementary data",
        "- Original PDFs are NEVER matched unless filename contains 'supplement'",
        "- Generated assets (06_PDF_DataAssets/) are NEVER matched",
        "- Only true .xlsx/.csv/.tsv and keyword-labeled files are candidates",
    ])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {report_path}")
    print("Done.")


if __name__ == "__main__":
    main()
