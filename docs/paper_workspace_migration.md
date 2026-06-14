# Paper Workspace Migration (Phase 4.0.1)

## What Changed

Before:
```
01_Sources/papers/
├── paper_d0cf4389f4ef6e06/
├── paper_39cce317b667c3db/
└── paper_b9f151757dca8463/
```

After:
```
01_Sources/papers/
├── 2018_Autophagy_Induced_By_Vip3Aa_Has_A_Pro_Survival_Role/
├── 1996_Bacillus_Thuringiensis_Vegetative_Insecticidal_Protein_Family/
└── 2023_Transgenic_Cotton_Coexpressing_Vip3A_And_Cry1Ac/
```

**paper_id is still the primary key everywhere.** The change is purely cosmetic for human readability.

## Why

Users shouldn't need to remember opaque hash IDs like `paper_d0cf4389f4ef6e06`. Year + title naming makes it immediately obvious which paper is which when browsing the filesystem or adding supplementary assets.

## What Was NOT Changed

- `01_PDF/` — main PDF files stay in place
- `02_Metadata/` — YAML metadata untouched
- `03_Evidence/`, `03_Assets/`, `03_Summary/` — all evidence/summary untouched
- `04_VectorDB/` — LanceDB embeddings untouched
- `05_Knowledge/` — gap/hypothesis/opportunity outputs untouched
- `paper_id` — remains the primary key in ALL databases and APIs

## How to Migrate

### Step 1: Dry Run

```bash
python Scripts/migrate_paper_workspaces.py --dry-run
```

This builds the global paper registry and shows the migration plan.

### Step 2: Review the Report

Check `10_System/reports/paper_workspace_migration_report.json`

### Step 3: Apply

```bash
python Scripts/migrate_paper_workspaces.py --apply
```

### Step 4: Verify

```bash
ls 01_Sources/papers/
# Should show human-friendly directory names
```

## How to Rollback

The migration report at `10_System/reports/paper_workspace_migration_report.json` contains the mapping:

```json
{
  "paper_id": "paper_d0cf4389f4ef6e06",
  "old_dir": "01_Sources/papers/paper_d0cf4389f4ef6e06",
  "new_dir": "01_Sources/papers/2018_Autophagy_Induced_..."
}
```

To rollback manually:
```bash
mv "01_Sources/papers/2018_Autophagy_Induced_..." "01_Sources/papers/paper_d0cf4389f4ef6e06"
```

Then rebuild the registry:
```bash
python Scripts/migrate_paper_workspaces.py --dry-run
```

## Adding Assets After Migration

Use human-friendly lookup:

```bash
# By title keyword
python Scripts/add_paper_asset.py --title "Vip3Aa resistance" --file "supplementary.pdf"

# By DOI
python Scripts/add_paper_asset.py --doi "10.1038/srep24311" --file "Table_S1.xlsx"

# By search query
python Scripts/add_paper_asset.py --query "Bt cotton Vip3A" --file "data.csv"

# Still works: by paper_id
python Scripts/add_paper_asset.py --paper-id paper_d0cf4389f4ef6e06 --file "figure.png"
```

## Global Paper Registry

Located at `05_Knowledge/paper_registry.json`. Contains:
- paper_id → display_name mapping
- Title and DOI indices for fast lookup
- Legacy path for rollback

## FAQ

**Q: Can I still use paper_id?**
A: Yes. All APIs work with paper_id. The display name is for human convenience only.

**Q: What if two papers have the same title?**
A: A short hash suffix is appended: `2023_Title_x7a9c`

**Q: Does this break the main PDF pipeline?**
A: No. The pipeline uses paper_id, not directory names.

**Q: Can I add more papers after migration?**
A: Yes. New papers will use display names automatically.
