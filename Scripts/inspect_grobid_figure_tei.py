"""Diagnose figure-related structure in available text sources."""
import re, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent

# Check all sources
raw_dir = root / "03_Summary" / "raw_text"
ev_dir = root / "03_Evidence"

print("=" * 60)
print("Figure Structure Diagnostic Report")
print("=" * 60)

# Source 1: Raw text files
if raw_dir.exists():
    txt_files = sorted(raw_dir.glob("*.txt"))
    print(f"\n[1] Raw text files: {len(txt_files)}")
    total_fig_mentions = 0
    papers_with_figs = 0
    for tf in txt_files:
        text = tf.read_text(encoding="utf-8", errors="replace")
        mentions = len(re.findall(r'(?:Figure|Fig\.?)\s+\d+', text, re.IGNORECASE))
        if mentions > 0:
            papers_with_figs += 1
            total_fig_mentions += mentions
    print(f"    Papers with figure mentions: {papers_with_figs}/{len(txt_files)}")
    print(f"    Total figure mentions: {total_fig_mentions}")

    # Find captions: "Figure N. Caption text" pattern
    caption_count = 0
    for tf in txt_files[:5]:
        text = tf.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'(?:Figure|Fig\.?)\s+(\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)\s*\.\s*(.{30,600}?)(?=\s*(?:Figure|Fig\.?)\s+\d+[\.\s]|\n\s*\n\s*(?:[A-Z][a-z]+|Table|REFERENCES|ACKNOWLEDG)|$)', text, re.IGNORECASE | re.DOTALL):
            caption_count += 1
            if caption_count <= 3:
                num = m.group(1)
                cap = m.group(2).strip()[:200]
                print(f"\n    Figure {num}: {cap}...")
    print(f"\n    Captions found (sample): {caption_count}")

else:
    print("\n[1] Raw text: NOT FOUND")

# Source 2: Evidence text
if ev_dir.exists():
    ev_dirs = [d for d in ev_dir.iterdir() if d.is_dir()]
    print(f"\n[2] Evidence dirs: {len(ev_dirs)}")
else:
    print("\n[2] Evidence: NOT FOUND")

print(f"\nKey finding: Use raw_text files (03_Summary/raw_text/) as primary caption source.")
print("Pattern: 'Figure N. Caption text...' embedded in paragraphs.")
