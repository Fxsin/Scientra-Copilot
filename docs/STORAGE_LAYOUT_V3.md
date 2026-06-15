# Storage Layout v3

Scientra Copilot uses a 10-00 numbered directory structure. **DB/DB_v2 paths are NOT used.**

```
00_Inbox/      Import staging — place files here for processing
01_Sources/    Original files — papers, supplementary, datasets
02_Parse/      Parsed intermediates — text, figures, tables
03_Assets/     Structured searchable assets — evidence, AI outputs
04_Corpus/     Long-term corpora — writing, reasoning, data
05_Knowledge/  Knowledge graph, research maps, memory
06_Index/      Search indexes — LanceDB at vector/lancedb/
07_Agents/     Agent workspaces and evaluations
08_Projects/   User project workspaces
09_Exports/    Export outputs
10_System/     Config, logs, migrations, backups
```

## User-Editable Directories

- `00_Inbox/` — Place import files here
- `01_Sources/` — Place original PDFs/supplementary here
- `07_Agents/` — Agent workspaces
- `08_Projects/` — User projects
- `09_Exports/` — Export destination

## System-Managed Directories

Do not manually modify:
- `02_Parse/` — Auto-generated parsing intermediates
- `03_Assets/` — Auto-generated structured assets
- `04_Corpus/` — Auto-generated corpora
- `05_Knowledge/` — Auto-generated knowledge graph
- `06_Index/` — Auto-managed search indexes
- `10_System/` — System config and logs

## Key Subdirectories

| Path | Content |
|------|---------|
| `03_Assets/ai/` | AI enrichment outputs |
| `03_Assets/figure_intelligence/` | Figure cards |
| `03_Assets/table_intelligence/` | Table cards |
| `03_Assets/supplementary_intelligence/` | Supplementary intelligence |
| `03_Assets/dataset_intelligence/` | Dataset cards + entities |
| `05_Knowledge/unified_evidence_graph/` | Evidence graph |
| `05_Knowledge/dataset_intelligence/` | Cross-paper dataset index |
| `06_Index/vector/lancedb/` | Vector search indexes |
| `10_System/validation/e2e/` | E2E validation results |
