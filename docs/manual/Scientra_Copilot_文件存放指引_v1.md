<!--
  Scientra Copilot File Placement Guide / 文件存放指引
  Version: v1
  Layout: Storage Layout v3
  Generated: 2026-06-13
  Generator: Scripts/generate_file_placement_guide.py
-->

### Scientra Copilot File Placement Guide / 文件存放指引

**适用于 Storage Layout v3 / Article Bundle Import**

生成日期 / Generated: 2026-06-13
版本 / Version: v1

# ENGLISH VERSION


## 1. What This Guide Solves

After downloading a paper PDF, supplementary tables, supplementary PDFs, source data, images, or project materials, you may wonder: **Where should I put each file?**

This guide tells you exactly how to organize your files so that Scientra Copilot can:

- Correctly identify the main paper PDF
- Reliably bind supplementary files to the right paper
- Parse and index supplementary tables for entity search
- Avoid re-parsing, mis-binding, or losing track of your data

Following this guide prevents the most common import problems.

## 2. The Most Important Rule

**Recommended approach: One folder per article.**

Example:

```text
00_Inbox/article_bundles/new/
└── Article_001/
    ├── main.pdf
    ├── Table_S1.xlsx
    ├── Source_Data.xlsx
    └── Supplementary_Information.pdf
```

**Why:** All files in the same article folder are treated as belonging to the same paper. This is called **folder_explicit binding**, and it is the most reliable way to link supplementary files to their paper.

Key facts about folder_explicit binding:

- Match confidence = **high** (no filename guessing needed)
- Supplementary files are automatically linked to the detected main PDF
- Supplementary entities (genes, proteins, compounds) enter the entity index automatically
- No manual confirmation required for files in the same folder

## 3. File Type Overview

| File Type | Examples | Recommended Location | How the Software Handles It | Recommended? |
|---|---|---|---|---|
| Main paper PDF | `paper.pdf`, `main.pdf` | `00_Inbox/article_bundles/new/<article_folder>/` | Parsed as the primary literature source | **Strongly recommended** |
| Supplementary Excel | `Table_S1.xlsx` | Same article folder as main PDF | Previewed as table; entities (gene, protein, compound) extracted | **Strongly recommended** |
| Supplementary CSV/TSV | `Source_Data.csv` | Same article folder as main PDF | Tabular data + entity indexing | **Strongly recommended** |
| Supplementary PDF | `Supplementary_Info.pdf` | Same article folder as main PDF | Linked as supplementary; structured table extraction not forced | **Recommended** |
| Image files | `figure.png`, `.tif` | Same article folder or project folder | Currently recorded as file references | Optional |
| ZIP archives | `source_data.zip` | Same article folder as main PDF | Currently recorded only; not auto-extracted | Use with caution |
| Standalone paper PDF | `paper.pdf` | `00_Inbox/single_papers/new/` | Parsed as a paper; no supplementary binding | Acceptable |
| Standalone supplementary file | `Table_S1.xlsx` | `00_Inbox/loose_supplementary/new/` | Requires manual confirmation; does NOT enter entity index automatically | **Not recommended as first choice** |
| Project materials | `proposal.docx`, `notes.md` | `08_Projects/<project_name>/` | Workspace files for your project | Optional |
| Export results | `report.xlsx`, `figures.zip` | `09_Exports/` | Software export outputs | Auto or manual |

## 4. Recommended: Article Bundle Import


## 4.1 How to Create an Article Folder

Create one folder per article under `00_Inbox/article_bundles/new/`:

```text
00_Inbox/article_bundles/new/
└── Zhang_2024_Nature/
    ├── main.pdf                         # Main paper PDF
    ├── Table_S1.xlsx                    # Supplementary table 1
    ├── Table_S2.xlsx                    # Supplementary table 2
    ├── Source_Data.xlsx                 # Source data file
    └── Supplementary_Information.pdf    # Supplementary information PDF
```

- `Zhang_2024_Nature` is the article folder you create
- `main.pdf` is the main paper PDF — named for easy detection
- All supplementary files go in the same folder
- The software binds everything as one article

## 4.2 Recommended Naming

**Main PDF recommended names** (detected with higher priority):

- `main.pdf`
- `paper.pdf`
- `article.pdf`
- `manuscript.pdf`
- `fulltext.pdf`

**Supplementary file naming:**

- `Table_S1.xlsx`, `Table_S2.csv` — keep original table numbers
- `Supplementary_Data_1.xlsx`
- `Source_Data.xlsx`
- `Supplementary_Information.pdf`

**Article folder naming** (use a pattern you can recognize):

- `Author_Year_Journal` — e.g., `Zhang_2024_Nature`
- `ShortTitle_Year` — e.g., `Vip3A_PM_Interaction_2025`
- `DOI_or_keyword` — e.g., `10_1038_s41586_2024_00123`

Use letters, numbers, and underscores. Avoid special characters.

## 4.3 Commands to Run

**Step 1 — Scan:** See what article folders exist.
```bash
python Scripts/process_article_bundles.py --scan
```

**Step 2 — Dry run:** Simulate processing without touching files.
```bash
python Scripts/process_article_bundles.py --process --dry-run
```
This shows which PDF will be detected as the main paper, and which files will be treated as supplementary.

**Step 3 — Process (copy mode, recommended):**
```bash
python Scripts/process_article_bundles.py --process --archive-mode copy
```
Files are copied to `01_Sources/`. Original files remain in `00_Inbox/`.

**Step 4 — Process (move mode, use with caution):**
```bash
python Scripts/process_article_bundles.py --process --archive-mode move
```
Files are moved (original deleted from inbox). Only use when you are certain.
Not recommended for regular users.

## 5. Main Paper PDF Placement

Three common situations:

## 5.1 You have a main PDF + supplementary files

Place everything in:
```text
00_Inbox/article_bundles/new/<article_folder>/
```

Example:
```text
00_Inbox/article_bundles/new/MyPaper/
├── main.pdf
├── Table_S1.xlsx
└── Supplementary_Info.pdf
```

## 5.2 You have only a main PDF (no supplementary files)

Place it in:
```text
00_Inbox/single_papers/new/
```

Example:
```text
00_Inbox/single_papers/new/
└── paper.pdf
```

**Note:** This method parses the paper only. No supplementary files will be automatically bound. If you later obtain supplementary files, move the PDF and the supplementary files into an article bundle folder instead.

## 5.3 Multiple PDFs in the same article folder

The software uses these rules to pick the main PDF:

1. Filenames containing `main`, `paper`, `article`, `manuscript`, or `fulltext` get **priority**.
2. Filenames containing `supplementary`, `supporting`, or `appendix` get **demoted** (treated as supplementary PDFs).
3. If only one PDF exists in the folder, it is selected as the main paper.
4. If multiple PDFs exist and no keyword match is found, the **largest PDF by file size** is selected — and a **warning** is generated.
5. If no PDF is found, the bundle status is `failed_no_main_pdf`.

**Best practice:** Name your main PDF `main.pdf` to avoid ambiguity.

## 6. Supplementary File Placement


## 6.1 Best: Place with the main PDF

```text
00_Inbox/article_bundles/new/MyPaper/
├── main.pdf
├── Table_S1.xlsx
├── Table_S2.csv
├── Supplementary_Data_1.tsv
└── Supplementary_Information.pdf
```

The software knows with **high confidence** that all supplementary files belong to `main.pdf`. This enables automatic entity indexing and cross-paper comparison.

## 6.2 Excel / CSV / TSV Files

These are the **best supplementary formats** for structured parsing.

The software can:
- Read sheet names and column headers
- Show previews of the first few rows
- Extract entities: gene names, protein names, compound names, treatments, statistical values
- Index entities for cross-paper search and comparison

**Supported formats:** `.xlsx`, `.xls`, `.csv`, `.tsv`

**Note:** Complex multi-sheet workbooks with merged cells may have reduced extraction quality. Simple, flat tables produce the best results.

## 6.3 Supplementary PDFs

Supplementary PDFs can be placed in the same article folder.

Currently, supplementary PDFs are:
- Recorded as supplementary file references
- Linked to the parent paper
- **Not** force-processed for structured table extraction

**Why:** Supplementary PDFs often contain scanned tables, images, or complex layouts. Forcing structured extraction can produce unreliable results.

**Recommendation:** When the same data is available as Excel/CSV, prefer the Excel/CSV version for entity extraction. Keep the PDF as a reference.

## 6.4 ZIP Files

ZIP archives placed in the article folder are recorded as file entries.

**Current behavior:** ZIP files are recorded but not automatically extracted.

**Recommendation:** Extract the contents of the ZIP and place the individual files (Excel, CSV, etc.) directly in the article folder. Keep the ZIP as a backup if desired.

**Future:** Auto-extraction of ZIP files is under consideration but not yet implemented.

## 7. Why Loose Supplementary Is Not Recommended

If you place a file in:
```text
00_Inbox/loose_supplementary/new/Table_S1.xlsx
```

The software **cannot reliably determine** which paper it belongs to.

**Why this matters:** Many papers have a `Table_S1.xlsx`. Without folder context, the software has no way to know which paper this particular Table S1 is from.

Consequences of using loose supplementary:

- Match confidence is **not high** — the file is flagged as needing review
- The file does **not** automatically enter the entity index
- **Manual confirmation** is required to bind it to a specific paper
- It will not appear in cross-paper entity comparisons until confirmed

**Better approach:** Create the article bundle folder and move the file there.

## 8. Where Files Go After Processing

Here is what happens when you process an article bundle:

| Stage | Location | What happens |
|---|---|---|
| **Your input** | `00_Inbox/article_bundles/new/` | You place files here |
| **Archived originals** | `01_Sources/papers/<paper_id>/` | Main PDF copied/moved here with manifest |
| **Archived supplementary** | `01_Sources/supplementary/<bundle_id>/` | Supplementary files copied/moved here with manifest |
| **Parsed results** | `02_Parse/` | Parsed text, figures, tables |
| **Structured assets** | `03_Assets/` | Structured, searchable JSON assets |
| **Corpus & evidence** | `04_Corpus/` | Long-term corpora (claims, methods, evidence) |
| **Vector index** | `06_Index/vector/lancedb/` | LanceDB vector embeddings for search |
| **System records** | `10_System/registry/`, `10_System/migrations/`, `10_System/backups/` | Registries, migration records, backups |

**Important:** Users generally do not need to manually modify anything under `01_Sources/` or beyond. The software manages these directories.

## 9. Which Folders You Can Touch (and Which You Should Not)

| Directory | User Can Modify? | Notes |
|---|---|---|
| `00_Inbox/` | **Yes** | Place new files here for import |
| `01_Sources/` | **Not recommended** | Original file archive; avoid manual changes |
| `02_Parse/` | **Not recommended** | Parsed intermediate results |
| `03_Assets/` | **Not recommended** | Structured assets managed by the system |
| `04_Corpus/` | **Not recommended** | Corpus and evidence library |
| `05_Knowledge/` | **Not recommended** | Knowledge graph and memory |
| `06_Index/` | **Do NOT manually modify** | Vector database and indexes. Deleting this breaks Chat and retrieval. |
| `07_Agents/` | Developer use only | Agent configurations and workspaces |
| `08_Projects/` | **Yes** | Your project workspace |
| `09_Exports/` | **Yes** | Export results; safe to read, copy, or delete |
| `10_System/` | **Not recommended** | Logs, backups, migration records. Read but don't edit. |

## 10. Common Mistakes (and How to Fix Them)

**Mistake 1:** Placing `Table_S1.xlsx` alone in `loose_supplementary/`.
→ **Correct:** Place it in the same article folder as its main PDF.

**Mistake 2:** Placing supplementary files directly in `01_Sources/`.
→ **Correct:** New files should always go into `00_Inbox/` first. The system moves them to `01_Sources/` during processing.

**Mistake 3:** Manually deleting `06_Index/vector/lancedb/`.
→ **Consequence:** Chat and search retrieval may stop working. This directory contains all vector embeddings. Do not delete it unless you intend to rebuild the entire index from scratch.

**Mistake 4:** Putting PDFs and supplementary files from multiple unrelated papers into one article folder.
→ **Correct:** One article folder = one paper. Create separate folders for each paper.

**Mistake 5:** Renaming `Supplementary_Info.pdf` to `main.pdf`.
→ **Consequence:** It may be misidentified as the main paper. Name supplementary PDFs with `supplementary` or `supporting` in the filename.

**Mistake 6:** Using `--archive-mode move` without verifying the dry run.
→ **Correct:** Always run `--dry-run` first. Use `copy` mode by default.

## 11. File Naming Tips

- Use **English letters, numbers, and underscores** whenever possible
- **Avoid special characters** (`#`, `%`, `&`, `*`, `:`, `<`, `>`, `?`, `|`, spaces are OK but underscores are safer)
- **Keep filenames reasonably short** — long paths may cause issues on some systems
- **Do not name multiple files `Table_S1.xlsx`** in different folders — the software tracks files by path, but it helps you to use distinct names
- **Article folders:** Use `Author_Year_ShortTitle` (e.g., `Smith_2024_CRISPR`)
- **Main PDF:** Name it `main.pdf` for unambiguous detection
- **Supplementary tables:** Keep the original `Table_S1`, `Table_S2` numbering
- **Chinese characters in filenames are supported**, but English names are more portable across systems

## 12. Usage Scenarios (8 Examples)


### Scenario 1: One paper + two Excel supplementary tables

**Folder structure:**
```text
00_Inbox/article_bundles/new/Smith_2024_Cell/
├── main.pdf
├── Table_S1.xlsx
└── Table_S2.xlsx
```
**Commands:**
```bash
python Scripts/process_article_bundles.py --scan
python Scripts/process_article_bundles.py --process --dry-run
python Scripts/process_article_bundles.py --process --archive-mode copy
```
**Notes:** Both Excel files are auto-linked to `main.pdf` with high confidence. Gene/protein/compound entities will be indexed.

### Scenario 2: One paper + a supplementary PDF

**Folder structure:**
```text
00_Inbox/article_bundles/new/Jones_2024_Science/
├── main.pdf
└── Supplementary_Material.pdf
```
**Commands:** Same as above.
**Notes:** The supplementary PDF is recorded and linked. Structured table data is not forced from it. If the same data is available as Excel, add the Excel file too.

### Scenario 3: Just a paper PDF, no supplementary files

**Folder structure (option A — recommended):**
```text
00_Inbox/article_bundles/new/Lee_2024_PNAS/
└── main.pdf
```
**Folder structure (option B — also supported):**
```text
00_Inbox/single_papers/new/
└── paper.pdf
```
**Notes:** Option A makes it easy to add supplementary files later without reorganizing. Option B is simpler but supplementary files cannot be bound to it.

### Scenario 4: You downloaded supplementary files later

**If you used option A (article bundle):**
Simply add the new files to the existing article folder and re-run the process command.

**If you used option B (single paper):**
Create a new article bundle folder, move the PDF and the new supplementary files into it, then process.

**Commands:**
```bash
python Scripts/process_article_bundles.py --scan
python Scripts/process_article_bundles.py --process --archive-mode copy
```

### Scenario 5: Paper has RNA-seq source data

**Folder structure:**
```text
00_Inbox/article_bundles/new/Chen_2024_GenomeBio/
├── main.pdf
├── RNA_seq_counts.csv
├── DEG_analysis.xlsx
└── Sample_Metadata.tsv
```
**Notes:** Each data file is indexed separately. Gene symbols from RNA-seq counts and DEG results are extracted for entity search.

### Scenario 6: Multiple PDFs in one folder — unsure which is the main paper

**Folder structure:**
```text
00_Inbox/article_bundles/new/Park_2024/
├── document.pdf
├── appendix.pdf
└── Table_S1.xlsx
```
**What happens:** Since neither filename contains `main`/`paper`/`article` and neither contains `supplementary`/`supporting`, the software picks the largest PDF as the main paper and issues a warning.

**Better approach:** Rename the main paper to `main.pdf` and the appendix to `Appendix.pdf` or `Supplementary_Appendix.pdf`.

**Then re-run:**
```bash
python Scripts/process_article_bundles.py --scan
```

### Scenario 7: Supplementary file is a ZIP archive

**Folder structure:**
```text
00_Inbox/article_bundles/new/Wang_2024_eLife/
├── main.pdf
└── supplementary_data.zip
```
**Current behavior:** The ZIP is recorded as a file entry but not auto-extracted.

**Better approach:** Extract the ZIP contents and place the extracted files in the folder:
```text
00_Inbox/article_bundles/new/Wang_2024_eLife/
├── main.pdf
├── Table_S1.xlsx        (extracted)
├── Table_S2.csv          (extracted)
└── supplementary_data.zip (keep as backup)
```

### Scenario 8: Starting a project workspace

**Folder structure:**
```text
08_Projects/My_Research_Project/
├── proposal.docx
├── literature_notes.md
├── analysis_plan.md
└── figures/
    ├── overview.png
    └── workflow.png
```
**Notes:** `08_Projects/` is your free workspace. You can organize project materials however you like. The software does not process these files — they are for your own reference.

## 13. Frequently Asked Questions


**Q1: Can I put all PDFs in one folder?**

Not recommended. Use one folder per paper under `article_bundles/new/`. If you put multiple unrelated PDFs in one folder, the software will pick one as the main paper and treat the others as supplementary PDFs, which is wrong.

**Q2: Can I upload supplementary files separately?**

Yes, via `00_Inbox/loose_supplementary/new/`, but they will require manual confirmation and will not auto-enter the entity index. It is always better to put them in the article folder with the main PDF.

**Q3: What is the difference between Excel and PDF supplementary files?**

Excel/CSV/TSV files are parsed for structured data and entity extraction. PDF supplementary files are linked as references but structured table data is not forced from them. When both are available, use the Excel version for entity indexing.

**Q4: Will my files in 00_Inbox be deleted after processing?**

Not with the default `--archive-mode copy`. Your original files remain in `00_Inbox/` after processing. Only `--archive-mode move` removes them — and we do not recommend this for regular use.

**Q5: Why doesn't the software automatically guess which paper a Table S1 belongs to?**

Because many papers have a `Table_S1.xlsx`. Without folder context, the software cannot reliably match a standalone file to a specific paper. Filename-based guessing would produce many false matches. Folder-explicit binding is the safe, correct approach.

**Q6: Can I delete `10_System/legacy_archive/`?**

Yes — but only after you have confirmed that all systems are working correctly with the new Storage Layout v3. The legacy archive contains old data from previous versions and is preserved for safety. It is safe to delete, but do so deliberately, not accidentally.

**Q7: What is `06_Index/vector/lancedb/`?**

This is the LanceDB vector database. It stores all vector embeddings used for semantic search, Chat retrieval, and entity queries. Do not delete or modify it manually.

**Q8: Why can't I find a recently imported file in Chat?**

After importing, the file goes through parsing, assetization, and embedding before it becomes searchable. This pipeline runs during processing. If you ran `--scan` but not `--process`, the file has not been processed yet. Run the full process command to complete the pipeline.

**Q9: Why wasn't a table extracted from my supplementary PDF?**

Supplementary PDFs are linked as references but structured table extraction is not forced on them. Supplementary PDFs often contain scanned or image-based tables that cannot be reliably parsed. If the data is available as Excel/CSV, add that file for entity extraction.

**Q10: Why wasn't a gene in my Excel file found by search?**

Check: (1) Was the file processed as part of an article bundle (not loose supplementary)? (2) Is the gene name in a format the entity extractor recognizes? (3) Did the processing step complete successfully? Run `--scan` to check the bundle status.

**Q11: Can filenames contain Chinese characters?**

Yes, Chinese filenames are supported. However, English names with letters, numbers, and underscores are more portable across different operating systems and tools. For article folders, you can use pinyin or English abbreviations of the Chinese title.

**Q12: Can one article folder have multiple Excel files?**

Yes, and this is encouraged. All Excel/CSV/TSV files in the article folder are treated as supplementary tables for that paper. Each file is processed independently and entities from all files are indexed.

**Q13: Can one article folder have multiple PDFs?**

It can, but one will be treated as the main paper and the rest as supplementary PDFs. The software auto-detects the main PDF by filename keywords. If you have multiple PDFs, name the main one `main.pdf` to avoid ambiguity.

**Q14: Where can I check if a file failed to process?**

Check `00_Inbox/article_bundles/failed/`. Failed bundles are moved there in move mode. You can also check `10_System/registry/article_bundle_registry.json` for the status of each bundle.

**Q15: Which folders should I back up?**

At minimum: `01_Sources/` (original files), `08_Projects/` (your work), `06_Index/vector/lancedb/` (vector index — large but critical for search), `10_System/registry/` (system records). You can also back up the entire project directory excluding `logs/` and `node_modules/`.

**Q16: What if I accidentally put the wrong PDF as main?**

Rename the files so that the intended main PDF has a priority name (`main.pdf`, `paper.pdf`), and the unintended one has a demoted name (`supplementary_*.pdf`). Then re-run `--scan` and `--process`.

**Q17: Will the software process subfolders inside my article folder?**

The current implementation scans the immediate article folder for files. For best results, place all files directly in the article folder without creating nested subfolders. Deeply nested structures may not be fully processed.

## 14. Recommended Workflow (Step by Step)

1. **Download** the main paper PDF and all supplementary files to your computer.
2. **Create an article folder** under `00_Inbox/article_bundles/new/`. Use a recognizable name like `Author_Year_Journal`.
3. **Rename** the main paper PDF to `main.pdf`.
4. **Place** all supplementary tables (Excel, CSV, TSV) and supplementary PDFs in the same folder.
5. **Run scan** to verify the bundle is recognized:
   ```bash
   python Scripts/process_article_bundles.py --scan
   ```
6. **Run dry-run** to see what the software will do:
   ```bash
   python Scripts/process_article_bundles.py --process --dry-run
   ```
7. **Confirm** that the detected main PDF is correct and all supplementary files are listed.
8. **Process** with copy mode (recommended):
   ```bash
   python Scripts/process_article_bundles.py --process --archive-mode copy
   ```
9. **Search** using Chat (`/chat`), Library (`/library`), or Evidence (`/evidence`) in the web interface.
10. **Review** imported papers and supplementary data. The Import Dashboard (`/import`) and Assets Viewer (`/assets`) pages are currently **planned** for a future release and are not yet available.

# 中文版本


## 1. 这份指引解决什么问题

当你下载了正文 PDF、补充表格、补充 PDF、源数据、图片、项目资料后，可能会困惑：**这些文件应该放哪里？**

本指引告诉你如何正确存放文件，确保 Scientra Copilot 能够：

- 正确识别正文 PDF
- 可靠地将补充文件绑定到正确的文章
- 解析并索引补充表格，支持实体搜索
- 避免重复解析、错误匹配或数据丢失

遵循本指引可以避免最常见的导入问题。

## 2. 最重要的一句话

**推荐方式：一篇文章一个文件夹。**

示例：

```text
00_Inbox/article_bundles/new/
└── Article_001/
    ├── main.pdf
    ├── Table_S1.xlsx
    ├── Source_Data.xlsx
    └── Supplementary_Information.pdf
```

**原因：** 同一个文件夹里的所有文件，会被软件认为属于同一篇文章。这称为 **folder_explicit binding（文件夹显式绑定）**，是最可靠的绑定方式。

folder_explicit binding 的关键事实：

- 匹配置信度 = **high（高）**（不需要猜测文件名）
- 补充文件自动关联到检测到的正文 PDF
- 补充文件中的实体（基因、蛋白质、化合物）自动进入实体索引
- 同一文件夹内的文件不需要人工确认

## 3. 用户最常见的文件类型总览

| 文件类型 | 示例 | 推荐存放位置 | 软件处理方式 | 是否推荐 |
|---|---|---|---|---|
| 正文 PDF | `paper.pdf`、`main.pdf` | `00_Inbox/article_bundles/new/<文章文件夹>/` | 作为主文献解析 | **强烈推荐** |
| 补充 Excel | `Table_S1.xlsx` | 同一文章文件夹 | 作为补充表格，可预览和提取实体（基因、蛋白质、化合物） | **强烈推荐** |
| 补充 CSV/TSV | `Source_Data.csv` | 同一文章文件夹 | 可做表格和实体索引 | **强烈推荐** |
| 补充 PDF | `Supplementary_Info.pdf` | 同一文章文件夹 | 作为补充文件链接，暂不强制提取结构化表格 | **推荐** |
| 图片文件 | `figure.png`、`.tif` | 同一文章文件夹或项目文件夹 | 目前主要作为文件记录 | 可选 |
| ZIP 压缩包 | `source_data.zip` | 同一文章文件夹 | 当前仅记录文件，不自动解压 | 谨慎使用 |
| 单独正文 PDF | `paper.pdf` | `00_Inbox/single_papers/new/` | 只解析正文，不绑定补充文件 | 可用 |
| 单独补充文件 | `Table_S1.xlsx` | `00_Inbox/loose_supplementary/new/` | 需要人工确认，不自动进入实体索引 | **不推荐作为首选** |
| 项目资料 | `proposal.docx`、`notes.md` | `08_Projects/<项目名>/` | 项目工作区资料 | 可选 |
| 导出结果 | `report.xlsx`、`figures.zip` | `09_Exports/` | 软件导出结果 | 自动或手动 |

## 4. 推荐方式：Article Bundle Import


## 4.1 文件夹怎么建

在 `00_Inbox/article_bundles/new/` 下为每篇文章创建一个文件夹：

```text
00_Inbox/article_bundles/new/
└── Zhang_2024_Nature/
    ├── main.pdf                         # 正文 PDF
    ├── Table_S1.xlsx                    # 补充表格 1
    ├── Table_S2.xlsx                    # 补充表格 2
    ├── Source_Data.xlsx                 # 源数据
    └── Supplementary_Information.pdf    # 补充说明 PDF
```

- `Zhang_2024_Nature` 是你自己创建的文章文件夹
- `main.pdf` 是正文 PDF——命名便于软件识别
- 所有补充文件放入同一文件夹
- 软件会将它们绑定为同一篇文章

## 4.2 推荐命名

**正文 PDF 推荐命名**（会获得更高的识别优先级）：

- `main.pdf`
- `paper.pdf`
- `article.pdf`
- `manuscript.pdf`
- `fulltext.pdf`

**补充文件推荐命名：**

- `Table_S1.xlsx`、`Table_S2.csv`——保留原始表格编号
- `Supplementary_Data_1.xlsx`
- `Source_Data.xlsx`
- `Supplementary_Information.pdf`

**文章文件夹推荐命名**（使用你能识别的模式）：

- `Author_Year_Journal`——例如 `Zhang_2024_Nature`
- `ShortTitle_Year`——例如 `Vip3A_PM_Interaction_2025`
- `DOI_or_keyword`——例如 `10_1038_s41586_2024_00123`

使用英文字母、数字和下划线。避免特殊符号。

## 4.3 运行命令

**第一步——扫描：** 查看有哪些文章文件夹。
```bash
python Scripts/process_article_bundles.py --scan
```

**第二步——模拟：** 模拟处理流程，不实际操作文件。
```bash
python Scripts/process_article_bundles.py --process --dry-run
```
这会显示软件将识别哪个 PDF 为正文、哪些为补充文件。

**第三步——正式处理（copy 模式，推荐）：**
```bash
python Scripts/process_article_bundles.py --process --archive-mode copy
```
文件被复制到 `01_Sources/`。原始文件保留在 `00_Inbox/` 中。

**第四步——正式处理（move 模式，谨慎使用）：**
```bash
python Scripts/process_article_bundles.py --process --archive-mode move
```
文件被移动（原始文件从 inbox 中删除）。只在非常确定时使用。普通用户不建议使用 move 模式。

## 5. 正文 PDF 应该怎么放

三种常见情况：

## 5.1 有正文 PDF + 补充文件

全部放入：
```text
00_Inbox/article_bundles/new/<文章文件夹>/
```

示例：
```text
00_Inbox/article_bundles/new/MyPaper/
├── main.pdf
├── Table_S1.xlsx
└── Supplementary_Info.pdf
```

## 5.2 只有正文 PDF，没有补充文件

放入：
```text
00_Inbox/single_papers/new/
```

示例：
```text
00_Inbox/single_papers/new/
└── paper.pdf
```

**注意：** 这种方式只解析正文，不会自动绑定补充文件。如果之后获得了补充文件，建议将 PDF 和补充文件一起放入 article bundle 文件夹。

## 5.3 多个 PDF 在同一个文章文件夹里

软件使用以下规则选择正文 PDF：

1. 文件名包含 `main`、`paper`、`article`、`manuscript`、`fulltext` → **优先识别为正文**。
2. 文件名包含 `supplementary`、`supporting`、`appendix` → **降低优先级**（视为补充 PDF）。
3. 如果文件夹中只有一个 PDF → 自动选为正文。
4. 如果有多个 PDF 且无法通过关键词判断 → 选择**文件大小最大的 PDF**，并生成 **warning**。
5. 如果没有 PDF → 状态为 `failed_no_main_pdf`。

**最佳实践：** 将正文 PDF 命名为 `main.pdf` 以避免歧义。

## 6. 补充文件应该怎么放


## 6.1 最推荐：和正文 PDF 放一起

```text
00_Inbox/article_bundles/new/MyPaper/
├── main.pdf
├── Table_S1.xlsx
├── Table_S2.csv
├── Supplementary_Data_1.tsv
└── Supplementary_Information.pdf
```

软件以**高置信度**知道这些补充文件属于 `main.pdf`。这会启用自动实体索引和跨论文比较功能。

## 6.2 Excel / CSV / TSV 文件

这些是**最适合结构化解析**的补充文件格式。

软件可以：
- 读取 sheet 名称和列标题
- 显示前几行预览
- 提取实体：基因名、蛋白质名、化合物名、处理方法、统计值
- 为跨论文搜索和比较建立实体索引

**支持的格式：** `.xlsx`、`.xls`、`.csv`、`.tsv`

**注意：** 包含合并单元格的复杂多 sheet 工作簿可能会降低提取质量。简单、扁平的表格效果最好。

## 6.3 补充 PDF

补充 PDF 可以放入同一文章文件夹。

目前补充 PDF 会：
- 记录为补充文件引用
- 与母论文关联
- **不会**强制提取结构化表格数据

**原因：** 补充 PDF 常包含扫描表格、图片或复杂排版。强制结构化提取可能产生不可靠的结果。

**建议：** 如果相同数据有 Excel/CSV 版本，优先使用 Excel/CSV 版本进行实体提取。PDF 保留作为参考。

## 6.4 ZIP 文件

放在文章文件夹中的 ZIP 压缩包会被记录为文件条目。

**当前行为：** ZIP 文件仅记录，不会自动解压。

**建议：** 解压 ZIP 内容，将解压出的文件（Excel、CSV 等）直接放入文章文件夹。如需要，可保留 ZIP 作为备份。

**未来：** ZIP 自动解压功能在考虑中，但尚未实现。

## 7. loose supplementary 为什么不推荐

如果你把文件放在：
```text
00_Inbox/loose_supplementary/new/Table_S1.xlsx
```

软件**无法可靠确定**它属于哪篇文章。

**为什么这是问题：** 很多文章都有 `Table_S1.xlsx`。没有文件夹上下文，软件无法知道这个 Table S1 具体属于哪篇论文。

使用 loose supplementary 的后果：

- 匹配置信度**不高**——文件被标记为需要审核
- 文件**不会**自动进入实体索引
- 需要**人工确认**才能绑定到具体文章
- 确认之前不会出现在跨论文实体比较中

**更好的做法：** 创建 article bundle 文件夹，将文件移入其中。

## 8. 软件处理完以后文件会去哪里

以下是处理 article bundle 时发生的情况：

| 阶段 | 位置 | 发生了什么 |
|---|---|---|
| **你的输入** | `00_Inbox/article_bundles/new/` | 你将文件放在这里 |
| **归档原始文件** | `01_Sources/papers/<paper_id>/` | 正文 PDF 复制/移动到此，带清单文件 |
| **归档补充文件** | `01_Sources/supplementary/<bundle_id>/` | 补充文件复制/移动到此，带清单文件 |
| **解析结果** | `02_Parse/` | 解析后的文本、图表、表格 |
| **结构化资产** | `03_Assets/` | 结构化、可搜索的 JSON 资产 |
| **语料和证据** | `04_Corpus/` | 长期语料库（论断、方法、证据） |
| **向量索引** | `06_Index/vector/lancedb/` | 用于搜索的 LanceDB 向量嵌入 |
| **系统记录** | `10_System/registry/`、`10_System/migrations/`、`10_System/backups/` | 注册表、迁移记录、备份 |

**重要：** 用户一般不需要手动修改 `01_Sources/` 及之后的内容。这些目录由软件管理。

## 9. 哪些文件夹用户可以手动操作，哪些不要动

| 目录 | 用户是否可以手动操作 | 说明 |
|---|---|---|
| `00_Inbox/` | **可以** | 放新文件用于导入 |
| `01_Sources/` | **不建议** | 原始文件归档，尽量不要手动改 |
| `02_Parse/` | **不建议** | 解析中间结果 |
| `03_Assets/` | **不建议** | 系统管理的结构化资产 |
| `04_Corpus/` | **不建议** | 语料和证据库 |
| `05_Knowledge/` | **不建议** | 知识图谱和记忆 |
| `06_Index/` | **不要手动改** | 向量库和索引。删除此目录会导致 Chat 和检索失效。 |
| `07_Agents/` | 开发者可改 | Agent 配置和工作空间 |
| `08_Projects/` | **可以** | 项目工作区 |
| `09_Exports/` | **可以** | 导出结果，可安全读取、复制或删除 |
| `10_System/` | **不建议** | 日志、备份、迁移记录。可读但不要编辑。 |

## 10. 常见错误放法（及如何纠正）

**错误 1：** 把 `Table_S1.xlsx` 单独放到 `loose_supplementary/`。
→ **正确：** 放到对应文章的 article bundle 文件夹。

**错误 2：** 把补充文件直接放入 `01_Sources/`。
→ **正确：** 新文件应该先放 `00_Inbox/`。系统在处理过程中将它们移至 `01_Sources/`。

**错误 3：** 手动删除 `06_Index/vector/lancedb/`。
→ **后果：** Chat 和搜索检索可能停止工作。该目录包含所有向量嵌入。除非你打算从头重建整个索引，否则不要删除它。

**错误 4：** 把多篇不相关论文的 PDF 和补充文件放进同一个文章文件夹。
→ **正确：** 一个文章文件夹 = 一篇论文。每篇论文创建独立的文件夹。

**错误 5：** 把 `Supplementary_Info.pdf` 重命名为 `main.pdf`。
→ **后果：** 可能被误识别为正文。补充 PDF 的文件名中应包含 `supplementary` 或 `supporting`。

**错误 6：** 未验证 dry run 结果就直接使用 `--archive-mode move`。
→ **正确：** 始终先运行 `--dry-run`。默认使用 `copy` 模式。

## 11. 文件命名建议

- 尽量使用**英文字母、数字和下划线**
- **避免特殊符号**（`#`、`%`、`&`、`*`、`:`、`<`、`>`、`?`、`|`，空格可以但下划线更安全）
- **文件名不宜过长**——过长的路径在某些系统上可能出问题
- **不要在多个文件夹中使用相同的文件名** `Table_S1.xlsx`——软件按路径跟踪文件，但不同的文件名有助于你自己区分
- **文章文件夹：** 使用 `Author_Year_ShortTitle`（例如 `Smith_2024_CRISPR`）
- **正文 PDF：** 命名 `main.pdf` 以确保被明确识别
- **补充表格：** 保留原始 `Table_S1`、`Table_S2` 编号
- **中文文件名可以使用**，但英文文件名在不同系统间更具可移植性

## 12. 用户上传场景示例（8 个场景）


### 场景 1：一篇论文 + 两个 Excel 补充表

**文件夹结构：**
```text
00_Inbox/article_bundles/new/Smith_2024_Cell/
├── main.pdf
├── Table_S1.xlsx
└── Table_S2.xlsx
```
**命令：**
```bash
python Scripts/process_article_bundles.py --scan
python Scripts/process_article_bundles.py --process --dry-run
python Scripts/process_article_bundles.py --process --archive-mode copy
```
**注意事项：** 两个 Excel 文件自动以高置信度关联到 `main.pdf`。基因/蛋白质/化合物实体会被索引。

### 场景 2：一篇论文 + 补充 PDF

**文件夹结构：**
```text
00_Inbox/article_bundles/new/Jones_2024_Science/
├── main.pdf
└── Supplementary_Material.pdf
```
**命令：** 同上。
**注意事项：** 补充 PDF 被记录并关联。不会强制从中提取结构化表格数据。如果相同数据有 Excel 版本，建议也加入。

### 场景 3：只有正文 PDF

**文件夹结构（方案 A——推荐）：**
```text
00_Inbox/article_bundles/new/Lee_2024_PNAS/
└── main.pdf
```
**文件夹结构（方案 B——也支持）：**
```text
00_Inbox/single_papers/new/
└── paper.pdf
```
**注意事项：** 方案 A 便于以后添加补充文件而无需重新整理。方案 B 更简单，但无法绑定补充文件。

### 场景 4：后来才下载到补充文件

**如果使用了方案 A（article bundle）：**
直接将新文件添加到已有的文章文件夹，然后重新运行 process 命令。

**如果使用了方案 B（single paper）：**
创建新的 article bundle 文件夹，将 PDF 和新补充文件一起移入，然后处理。

**命令：**
```bash
python Scripts/process_article_bundles.py --scan
python Scripts/process_article_bundles.py --process --archive-mode copy
```

### 场景 5：有 RNA-seq 源数据

**文件夹结构：**
```text
00_Inbox/article_bundles/new/Chen_2024_GenomeBio/
├── main.pdf
├── RNA_seq_counts.csv
├── DEG_analysis.xlsx
└── Sample_Metadata.tsv
```
**注意事项：** 每个数据文件独立索引。RNA-seq counts 和 DEG 结果中的基因符号会被提取用于实体搜索。

### 场景 6：有多个 PDF，不知道哪个是正文

**文件夹结构：**
```text
00_Inbox/article_bundles/new/Park_2024/
├── document.pdf
├── appendix.pdf
└── Table_S1.xlsx
```
**会发生什么：** 因为两个文件名都既不包含 `main`/`paper`/`article` 也不包含 `supplementary`/`supporting`，软件会选择文件大小最大的 PDF 作为正文，并产生 warning。

**更好的做法：** 将正文重命名为 `main.pdf`，将附录重命名为 `Appendix.pdf` 或 `Supplementary_Appendix.pdf`。

**然后重新运行：**
```bash
python Scripts/process_article_bundles.py --scan
```

### 场景 7：补充文件是 ZIP 压缩包

**文件夹结构：**
```text
00_Inbox/article_bundles/new/Wang_2024_eLife/
├── main.pdf
└── supplementary_data.zip
```
**当前行为：** ZIP 被记录为文件条目，但不会自动解压。

**更好的做法：** 解压 ZIP 内容，将解压出的文件放入文件夹：
```text
00_Inbox/article_bundles/new/Wang_2024_eLife/
├── main.pdf
├── Table_S1.xlsx        （解压出的）
├── Table_S2.csv          （解压出的）
└── supplementary_data.zip （保留为备份）
```

### 场景 8：想建立一个项目文件夹

**文件夹结构：**
```text
08_Projects/My_Research_Project/
├── proposal.docx
├── literature_notes.md
├── analysis_plan.md
└── figures/
    ├── overview.png
    └── workflow.png
```
**注意事项：** `08_Projects/` 是你的自由工作区。可以按自己的方式组织项目资料。软件不会处理这些文件——它们仅供你自己参考。

## 13. 常见问题（FAQ）


**Q1：我可以把所有 PDF 都放一个文件夹吗？**

不推荐。每篇论文在 `article_bundles/new/` 下使用独立的文件夹。如果把多篇无关的 PDF 放在同一文件夹中，软件会选一篇作为正文，其余的视为补充 PDF，这是错误的。

**Q2：补充文件能不能单独上传？**

可以，通过 `00_Inbox/loose_supplementary/new/`，但需要人工确认，且不会自动进入实体索引。始终建议将补充文件与正文 PDF 放在同一个文章文件夹中。

**Q3：Excel 和 PDF 补充文件有什么区别？**

Excel/CSV/TSV 文件会被解析以提取结构化数据和实体。PDF 补充文件会作为引用关联，但不会强制提取结构化表格数据。当两者都可用时，优先使用 Excel 版本进行实体索引。

**Q4：处理完以后 00_Inbox 里的文件还在吗？**

使用默认的 `--archive-mode copy` 时，原始文件保留在 `00_Inbox/` 中。只有 `--archive-mode move` 会删除原始文件——我们不建议日常使用 move 模式。

**Q5：为什么不自动猜 Table S1 属于哪篇文章？**

因为很多文章都有 `Table_S1.xlsx`。没有文件夹上下文，软件无法可靠地将一个独立的文件匹配到特定文章。基于文件名的猜测会产生大量错误匹配。文件夹显式绑定是安全、正确的做法。

**Q6：我能不能删除 `10_System/legacy_archive/`？**

可以——但前提是你已确认所有系统在新 Storage Layout v3 下正常工作。legacy archive 包含旧版本的数据，出于安全考虑而保留。删除是安全的，但请有意识地执行，而非误删。

**Q7：`06_Index/vector/lancedb/` 是什么？**

这是 LanceDB 向量数据库。存储了所有用于语义搜索、Chat 检索和实体查询的向量嵌入。请勿手动删除或修改。

**Q8：为什么 Chat 查不到刚上传的文件？**

导入后，文件需要经过解析、资产化、嵌入等步骤才能被搜索到。这些步骤在处理过程中完成。如果你只运行了 `--scan` 而未运行 `--process`，文件尚未被处理。请运行完整的 process 命令。

**Q9：为什么补充 PDF 没有提取出表格？**

补充 PDF 被关联为引用，但不会强制提取结构化表格。补充 PDF 通常包含扫描版或图片型表格，无法可靠解析。如果相同数据有 Excel/CSV 版本，请添加该文件以进行实体提取。

**Q10：为什么 Excel 里的基因没有被搜到？**

请检查：(1) 文件是否作为 article bundle 的一部分处理（而非 loose supplementary）？(2) 基因名称格式是否被实体提取器识别？(3) 处理步骤是否成功完成？运行 `--scan` 检查 bundle 状态。

**Q11：文件名可以是中文吗？**

可以，中文文件名是支持的。但使用英文字母、数字和下划线在不同操作系统和工具之间更具可移植性。对于文章文件夹名，可以使用拼音或中文标题的英文缩写。

**Q12：一个文章文件夹里可以有多个 Excel 吗？**

可以，而且推荐这样做。文章文件夹中的所有 Excel/CSV/TSV 文件都被视为该论文的补充表格。每个文件独立处理，所有文件中的实体都会被索引。

**Q13：一个文章文件夹里可以有多个 PDF 吗？**

可以有，但其中一个会被视为正文，其余视为补充 PDF。软件通过文件名关键词自动检测正文。如果有多个 PDF，请将正文命名为 `main.pdf` 以避免歧义。

**Q14：处理失败的文件在哪里看？**

查看 `00_Inbox/article_bundles/failed/`。在 move 模式下，失败的 bundle 会被移至此处。你也可以在 `10_System/registry/article_bundle_registry.json` 中查看每个 bundle 的状态。

**Q15：我应该备份哪些文件夹？**

至少备份：`01_Sources/`（原始文件）、`08_Projects/`（你的工作成果）、`06_Index/vector/lancedb/`（向量索引——较大但对搜索至关重要）、`10_System/registry/`（系统记录）。也可以备份整个项目目录，排除 `logs/` 和 `node_modules/`。

**Q16：如果放错了正文 PDF 怎么办？**

重命名文件，使正确的正文 PDF 具有优先级名称（`main.pdf`、`paper.pdf`），不正确的使用降级名称（`supplementary_*.pdf`）。然后重新运行 `--scan` 和 `--process`。

**Q17：软件会处理文章文件夹中的子文件夹吗？**

当前实现扫描文章文件夹的直接文件。为获得最佳效果，请将所有文件直接放在文章文件夹中，不要创建嵌套子文件夹。深层嵌套结构可能无法完全处理。

## 14. 最后的推荐工作流（逐步操作）

1. **下载** 正文 PDF 和所有补充文件到你的电脑。
2. **创建文章文件夹** 在 `00_Inbox/article_bundles/new/` 下。使用可识别的名称，如 `Author_Year_Journal`。
3. **重命名** 正文 PDF 为 `main.pdf`。
4. **放入** 所有补充表格（Excel、CSV、TSV）和补充 PDF 到同一文件夹。
5. **运行 scan** 验证 bundle 是否被识别：
   ```bash
   python Scripts/process_article_bundles.py --scan
   ```
6. **运行 dry-run** 查看软件将执行什么操作：
   ```bash
   python Scripts/process_article_bundles.py --process --dry-run
   ```
7. **确认** 检测到的正文 PDF 正确，所有补充文件均已列出。
8. **正式处理** 使用 copy 模式（推荐）：
   ```bash
   python Scripts/process_article_bundles.py --process --archive-mode copy
   ```
9. **查询** 使用 Web 界面的 Chat（`/chat`）、Library（`/library`）或 Evidence（`/evidence`）进行搜索。
10. **查看** 导入的论文和补充数据。Import Dashboard（`/import`）和 Assets Viewer（`/assets`）页面目前处于**规划中**阶段，尚未完成。

## 15. 文档生成方式 / Document Generation

本指引由脚本 `Scripts/generate_file_placement_guide.py` 自动生成。
生成日期：2026-06-13
版本：v1

输出文件：
- Markdown: `docs/manual/Scientra_Copilot_文件存放指引_v1.md`
- DOCX: `docs/manual/Scientra_Copilot_文件存放指引_v1.docx`

不覆盖已有文件。如存在同名文件，自动添加时间戳。
不暴露本地绝对路径。所有路径均为相对于项目根目录的相对路径。
