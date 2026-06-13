"""Path Usage Audit — scan for hardcoded old path references."""
import json, re, sys
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

OLD_DIRS = [
    "00_Inbox", "00_Supplementary", "01_PDF", "02_Metadata",
    "03_Evidence", "03_Summary", "04_VectorDB", "05_Index",
    "06_PDF_DataAssets",
]

SCAN_DIRS = ["scientra", "Scripts", "web/lib", "web/components", "web/app", "Config"]
SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".yaml", ".yml"}
SKIP_PATTERNS = ["node_modules", "__pycache__", ".pyc", ".git", "10_System",
                 "storage_layout", "storage_migration", "storage_layout_v3",
                 "migrate_storage_layout", "path_usage_audit", "audit_path"]

# Also look for specific path builders like / "03_Evidence" / paper_id
PATH_JOIN_PATTERN = re.compile(
    r'["\'](0[0-6]_[A-Za-z_]+(?:/[^"\']*)?)["\']'
)

results = []
seen_files = set()

for scan_dir in SCAN_DIRS:
    full_dir = root / scan_dir
    if not full_dir.exists():
        continue
    for f in full_dir.rglob("*"):
        if f.suffix not in SCAN_SUFFIXES:
            continue
        skip = False
        for pat in SKIP_PATTERNS:
            if pat in str(f):
                skip = True
                break
        if skip:
            continue
        if f in seen_files:
            continue
        seen_files.add(f)

        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for line_no, line in enumerate(content.splitlines(), 1):
            for old_dir in OLD_DIRS:
                if old_dir in line:
                    # Determine usage type
                    usage = "unknown"
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("--"):
                        usage = "doc"
                    elif "test" in str(f).lower() or "test_" in f.name:
                        usage = "test"
                    elif any(w in stripped.lower() for w in ["write", "save", "dump", "mkdir", "output", "open("]):
                        usage = "write"
                    elif any(w in stripped.lower() for w in ["read", "load", "exists", "open(", "path"]):
                        usage = "read"
                    elif any(w in stripped.lower() for w in ["config", "yaml", "yml"]):
                        usage = "config"

                    # Determine risk
                    risk = "low"
                    if usage in ("read", "write") and not f.name.startswith("test"):
                        risk = "high"
                    elif usage == "config":
                        risk = "medium"
                    elif "legacy" in line.lower() or "fallback" in line.lower():
                        risk = "low"

                    results.append({
                        "file": str(f.relative_to(root)),
                        "line": line_no,
                        "old_path": old_dir,
                        "snippet": stripped[:120],
                        "usage_type": usage,
                        "risk_level": risk,
                    })

# Write audit reports
report_dir = root / "10_System" / "migrations"
report_dir.mkdir(parents=True, exist_ok=True)

# JSON
json_path = report_dir / "path_usage_audit.json"
json_path.write_text(json.dumps({
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "total_references": len(results),
    "by_risk": {
        "high": len([r for r in results if r["risk_level"] == "high"]),
        "medium": len([r for r in results if r["risk_level"] == "medium"]),
        "low": len([r for r in results if r["risk_level"] == "low"]),
    },
    "by_dir": {d: len([r for r in results if r["old_path"] == d]) for d in OLD_DIRS},
    "by_type": {d: len([r for r in results if r["usage_type"] == d])
                for d in sorted(set(r["usage_type"] for r in results))},
    "references": results,
}, ensure_ascii=False, indent=2), encoding="utf-8")

# Markdown
lines = [
    "# Path Usage Audit Report — Storage Layout v3", "",
    f"Generated: {datetime.now(timezone.utc).isoformat()}",
    f"Total references found: {len(results)}", "",
    "## Risk Summary", "",
    "| Risk | Count |",
    "|------|-------|",
]
for risk in ["high", "medium", "low"]:
    cnt = len([r for r in results if r["risk_level"] == risk])
    lines.append(f"| {risk} | {cnt} |")

lines.extend(["", "## By Directory", ""])
for d in OLD_DIRS:
    cnt = len([r for r in results if r["old_path"] == d])
    if cnt:
        lines.append(f"- **{d}**: {cnt} references")

lines.extend(["", "## High-Risk References (read/write in non-test code)", ""])
high = [r for r in results if r["risk_level"] == "high"]
if high:
    for r in high[:50]:
        lines.append(f"- `{r['file']}:{r['line']}` — {r['old_path']} ({r['usage_type']})")
        lines.append(f"  ```")
        lines.append(f"  {r['snippet']}")
        lines.append(f"  ```")
else:
    lines.append("- No high-risk references found.")

lines.extend(["", "## Medium-Risk References (config)", ""])
medium = [r for r in results if r["risk_level"] == "medium"]
for r in medium[:20]:
    lines.append(f"- `{r['file']}:{r['line']}` — {r['old_path']}")

lines.extend(["", "## Notes", "",
    "- All paths above are relative to project root.",
    "- No absolute paths are included in this report.",
    "- Legacy paths should be migrated to Storage Layout v3 resolver.",
])
lines.append("")
md_path = report_dir / "path_usage_audit_report.md"
md_path.write_text("\n".join(lines), encoding="utf-8")

print(f"Total references: {len(results)}")
print(f"High risk: {len(high)}")
print(f"Medium risk: {len(medium)}")
print(f"Low risk: {len(results) - len(high) - len(medium)}")
print(f"\nBy directory:")
for d in OLD_DIRS:
    cnt = len([r for r in results if r["old_path"] == d])
    if cnt:
        print(f"  {d}: {cnt}")
print(f"\nReports saved to 10_System/migrations/")
