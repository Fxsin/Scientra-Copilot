"""Generate comprehensive bilingual Word manual in project root."""
import datetime, sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
today = datetime.date.today().isoformat()

doc = Document()

# ── Helper functions ──

def h1(text):
    doc.add_heading(text, level=1)

def h2(text):
    doc.add_heading(text, level=2)

def h3(text):
    doc.add_heading(text, level=3)

def p(text, bold=False, italic=False, size=10):
    par = doc.add_paragraph()
    run = par.add_run(text)
    run.font.size = Pt(size)
    if bold: run.bold = True
    if italic: run.italic = True
    return par

def code(text):
    par = doc.add_paragraph()
    run = par.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    return par

def bullet(text):
    par = doc.add_paragraph(text, style="List Bullet")
    return par

def warn(text):
    par = doc.add_paragraph()
    run = par.add_run("⚠️  " + text)
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(180, 100, 0)
    return par

def table(headers, rows):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = h
    for ri, row in enumerate(rows):
        for ci, cell in enumerate(row):
            t.rows[ri+1].cells[ci].text = str(cell)
    doc.add_paragraph("")

# ── Title Page ──

title_p = doc.add_paragraph()
title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title_p.add_run("Scientra Copilot\nUser Manual v2.0")
run.font.size = Pt(26)
run.bold = True

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
run2 = sub.add_run(f"Bilingual Edition | Software v1.5 | Storage Layout v3 | {today}")
run2.font.size = Pt(11)
run2.font.color.rgb = RGBColor(100, 100, 100)

doc.add_page_break()

# ══════════════════════════════════════════════════════════
# PART I: ENGLISH
# ══════════════════════════════════════════════════════════

h1("Part I. English User Manual")

# ── 1. Introduction ──
h2("1. Introduction")

h3("1.1 What is Scientra Copilot?")
p("Scientra Copilot is a local-first, evidence-oriented research discovery platform. It transforms scientific literature (PDFs, supplementary Excel/CSV/TSV files, figures, tables) into structured, searchable, AI-queryable knowledge — all running locally on your machine.")
p("Unlike reference managers that treat papers as opaque files, Scientra Copilot reads and understands your literature. It extracts methods, results, claims, figures, tables, and entities, links supplementary data to parent papers, indexes genes and proteins from supplementary tables, and provides an AI chat interface that answers research questions grounded in your literature with traceable citations.")

h3("1.2 What It Does")
bullet("Processes PDFs into structured knowledge assets (sections, methods, results, claims, figures, tables, entities)")
bullet("Links supplementary files (Excel, CSV, TSV) to their parent papers via folder-explicit binding")
bullet("Extracts gene, protein, compound entities from supplementary tables with value context (FC, p-value, log2FC)")
bullet("Provides evidence-grounded AI chat with [Ref:N] citations traceable to source chunks")
bullet("Enables cross-paper entity comparison with direction detection (upregulated/downregulated)")
bullet("Maintains full provenance: SHA256 hashes, import sources, binding methods, confidence scores")

h3("1.3 What It Does NOT Do")
bullet("It is not a cloud service — all data stays on your machine. No internet required for core functionality.")
bullet("It does not replace human scientific judgment. Interpretation includes caution notes.")
bullet("It does not automatically write papers or grant proposals.")
bullet("It does not perform statistical meta-analysis across papers. Cross-paper values are not directly comparable without aligned conditions.")
bullet("It does not do OCR on supplementary PDFs or scanned documents in the current version.")

h3("1.4 Current Version and Development Status")
p(f"Version: v1.5. Status: active development. The core pipeline is stable: Chat, Query APIs, Storage Layout v3, Article Bundle Import, LanceDB v3, Supplementary Entity Index, and Cross-paper Comparison are all functional. Import Dashboard and Assets Viewer are planned for v1.6.")

# ── 2. Core Design Philosophy ──
h2("2. Core Design Philosophy")

h3("2.1 Local-first Scientific Workspace")
p("Scientra Copilot is designed to run entirely on your local machine. No cloud dependency means no data leaves your computer, no subscription fees, and no internet required for core functionality. LLM integration is optional and uses your own API keys.")

h3("2.2 Evidence-oriented Knowledge Extraction")
p("The core philosophy is: from PDF collection to evidence-based research memory. Every piece of extracted knowledge carries provenance — you can trace a claim or an entity value back to the exact table, row, file, and paper it came from.")

h3("2.3 Pipeline: Paper → Asset → Corpus → Knowledge → Index → Agent")
p("Scientra Copilot follows a layered pipeline design:")
bullet("Paper layer: raw PDFs and supplementary files imported via Article Bundle")
bullet("Asset layer: extracted structured data (sections, methods, results, figures, tables, entities, claims)")
bullet("Corpus layer: long-term aggregated corpora (expression patterns, reasoning, evidence, data)")
bullet("Knowledge layer: knowledge graph nodes, edges, research maps, scientific memory")
bullet("Index layer: LanceDB vector index, keyword, entity, citation, paper indexes")
bullet("Agent layer: Chat, writing, reviewer, reasoning, experimental design agents")

h3("2.4 Why Supplementary Data Matters")
p("The most valuable structured data in scientific papers often lives in supplementary files — gene expression tables, bioassay results, primer lists, statistical models. Traditional tools ignore these files. Scientra Copilot treats them as first-class data sources: Excel/CSV/TSV files are linked to papers, previewed, and indexed by entity.")

h3("2.5 Why folder_explicit Binding Is Safer")
p("Filename-based matching (e.g., 'Table_S1.xlsx' matching any paper's 'Table S1' reference) is fragile and error-prone. Many papers have a Table S1. folder_explicit binding ensures that all files in the same folder as the main PDF are linked to that paper with high confidence. No guessing required.")
warn("loose supplementary files (files without a parent article folder) require manual confirmation and will NOT enter the entity index automatically.")

h3("2.6 Why Traceability Matters")
p("Every asset, entity, and chunk in Scientra Copilot carries provenance information: source file, import method, binding confidence, SHA256 hash. This means you can always verify where a piece of knowledge came from and how it was generated. No black boxes.")

# ── 3. System Architecture ──
h2("3. System Architecture")

h3("3.1 Backend")
bullet("Python 3.11+ with FastAPI server on port 8710")
bullet("GROBID (Docker-based) for PDF parsing on port 8070")
bullet("BGE-M3 embedding model (1024-dimensional vectors)")
bullet("LanceDB for vector storage at 06_Index/vector/lancedb/")
bullet("LLM integration: DeepSeek deepseek-chat or Anthropic Claude (API key in Config/llm_config.yaml)")

h3("3.2 Frontend")
bullet("Next.js 14 with React and Tailwind CSS on port 3000")
bullet("13 pages across Analysis and Data categories")
bullet("Client-side rendering with server-side API calls")

h3("3.3 Storage Layout v3")
p("10-group directory structure designed for long-term knowledge building. See Chapter 4 for details.")

h3("3.4 Data Flow")
code("PDF + Supplementary → GROBID → Metadata → Evidence → Assets → Corpus → Knowledge → Index → Agent → Web UI")

# ── 4. Storage Layout v3 ──
h2("4. Storage Layout v3 — Complete Directory Reference")

h3("4.1 00_Inbox/ — Import Staging")
p("Where you place files for import. Three subdirectories:")
bullet("article_bundles/{new,processing,processed,failed} — Recommended: one folder per paper")
bullet("single_papers/{new,processed,failed} — Legacy single-PDF import")
bullet("loose_supplementary/{new,review_needed,failed} — Files needing manual confirmation")
warn("Do NOT manually delete files from processing/ or processed/. Use the import commands.")

h3("4.2 01_Sources/ — Original Files")
bullet("papers/<paper_id>/ — Main PDF + source_manifest.json")
bullet("supplementary/<paper_id>/ — Supplementary files + supplementary_manifest.json")
bullet("datasets/<dataset_id>/ — External datasets")
warn("Do NOT manually edit files here. Manifests track SHA256 hashes.")

h3("4.3 02_Parse/ — Parsed Intermediates")
bullet("text/<paper_id>/ — raw_text.txt, sections.json, grobid.tei.xml, references.json")
bullet("figures/<paper_id>/ — Extracted figure images and captions")
bullet("tables/<paper_id>/ — Extracted table structures")
bullet("supplementary/<paper_id>/ — Parsed supplementary data")

h3("4.4 03_Assets/ — Structured Assets")
bullet("paper_assets/agent_chunks/ — Agent-ready knowledge chunks (JSONL)")
bullet("figure_assets/ — Figure records with captions and references")
bullet("table_assets/ — Table records with captions and structure status")
bullet("supplementary_assets/links/ — Supplementary link records with matching status")
bullet("entity_assets/ — Entity records (gene, protein, compound)")
bullet("asset_registry/ — Asset tracking and build status")

h3("4.5 04_Corpus/ — Long-term Corpora")
bullet("writing/ — Expression, introduction, discussion, citation, abstract, limitation, terminology")
bullet("reasoning/ — Claims, gaps, hypotheses, methods, evidence, contradictions")
bullet("data/ — Supplementary, datasets, gene_evidence, omics, cross_study")
bullet("review/ — Reviewer comments, author responses, review patterns")

h3("4.6 05_Knowledge/ — Knowledge Graph and Maps")
bullet("graph/ — Nodes, edges, snapshots, graph_schema.json")
bullet("maps/ — Research map, hotspots, research gaps, knowledge network")
bullet("memory/ — Field memory, project memory, topic memory")
bullet("reasoning_chains/ — Claim-method-evidence, hypothesis-experiment-result, contradiction sets")

h3("4.7 06_Index/ — Search Indexes")
p("Primary LanceDB path: 06_Index/vector/lancedb/")
bullet("vector/lancedb/ — LanceDB with 3 tables: evidence_chunks (1,267 rows), literature_vectors (319 rows), pdf_asset_chunks (2,648 rows)")
bullet("vector/embedding_reports/ — Embedding status and reports")
bullet("keyword/, entity/, citation/, paper/, asset/ — Other index types")

h3("4.8 07_Agents/ — Agent Workspaces")
bullet("chat/ — Chat agent configuration and prompts")
bullet("writing_agent/ — Academic writing agent (planned)")
bullet("reviewer_agent/ — AI reviewer agent (planned)")
bullet("reasoning_agent/ — Scientific reasoning agent (planned)")
bullet("evals/ — Evaluation cases and regression tests")

h3("4.9 08_Projects/ through 10_System/")
p("08_Projects/ — User project workspaces with project profiles and working memory.")
p("09_Exports/ — Export outputs for papers, reports, tables, figures.")
p("10_System/ — System files: config, logs, cache, temp, migrations, backups, registry, legacy_archive.")
warn("10_System/legacy_archive/ contains old directories from the pre-v3 layout. Safe to delete after verifying all systems work.")

# ── 5. Installation and Startup ──
h2("5. Installation and Startup")

h3("5.1 Requirements")
bullet("Python 3.11 or higher")
bullet("Node.js 18 or higher")
bullet("Docker (for GROBID PDF parsing)")
bullet("Git (optional, for version control)")

h3("5.2 Quick Start")
code("python Scripts/dev_restart.py")
p("This single command starts both the backend API (port 8710) and the Web frontend (port 3000).")

h3("5.3 Manual Start")
code("python -m scientra.server          # API on http://127.0.0.1:8710")
code("cd web && npm run dev              # Web on http://127.0.0.1:3000")

h3("5.4 LLM Setup")
code("python Scripts/setup_llm.py")
p("Interactive setup for DeepSeek or Anthropic. Your API key is stored in Config/llm_config.yaml (gitignored, never committed).")
p("Without an LLM key, the Chat works in Evidence-only mode — it shows retrieved evidence but does not call any external API.")

h3("5.5 Port Configuration")
p("Default ports: API=8710, Web=3000, GROBID=8070. To change, edit the respective configuration files.")

# ── 6. Importing Papers ──
h2("6. Importing Papers — Complete Guide")

h3("6.1 Recommended: Article Bundle Import")
p("Place each paper in its own folder under 00_Inbox/article_bundles/new/:")
code("00_Inbox/article_bundles/new/")
code("└── Example_Paper_2024/")
code("    ├── main.pdf")
code("    ├── Table_S1.xlsx")
code("    ├── Table_S2.csv")
code("    └── Supplementary_Information.pdf")

h3("6.2 Commands")
code("python Scripts/process_article_bundles.py --scan       # Scan inbox")
code("python Scripts/process_article_bundles.py --process --archive-mode copy  # Process (safe)")
code("python Scripts/process_article_bundles.py --process --dry-run  # Plan only")

h3("6.3 Main PDF Detection Logic")
p("The system uses a scoring algorithm to identify the main paper PDF:")
bullet("Step 1: Filename keyword scoring. 'main', 'paper', 'article', 'manuscript', 'fulltext' → +2 points each")
bullet("Step 2: Supplementary keywords demote. 'supplementary', 'supporting', 'appendix', 'suppl' → -5 points each")
bullet("Step 3: If only one PDF, auto-select it regardless of name")
bullet("Step 4: If multiple PDFs and no clear winner, select the largest file and add a warning")
bullet("Step 5: If no PDF at all, mark as failed_no_main_pdf")

h3("6.4 Archive Modes")
bullet("copy (default, safe): Copies files to 01_Sources/. Original files preserved in inbox.")
bullet("move: Moves files. Use only when you are certain.")
bullet("none: No archiving. Files stay in inbox.")
bullet("dry-run: Generates a plan only. No file operations.")

h3("6.5 What Happens After Import")
bullet("Main PDF → copied to 01_Sources/papers/<paper_id>/main.pdf")
bullet("Supplementary files → copied to 01_Sources/supplementary/<paper_id>/")
bullet("source_manifest.json generated with SHA256, import source, binding method")
bullet("supplementary_manifest.json generated with file details and entity index status")
bullet("Bundle archived to 00_Inbox/article_bundles/processed/ or failed/")

h3("6.6 Common Mistakes")
bullet("Putting multiple papers in one folder — each folder should contain exactly one paper")
bullet("Naming supplementary PDFs as 'main.pdf' — use descriptive names")
bullet("Including scanned PDFs expecting OCR — not supported in current version")
bullet("Using move mode without verifying the copy was successful")

# ── 7. Supplementary Files ──
h2("7. Supplementary Files — Complete Management Guide")

h3("7.1 Supported Types")
table(
    ["Type", "Extensions", "Can Preview?", "Can Enter Entity Index?"],
    [["Tabular", ".xlsx, .xls, .csv, .tsv", "Yes (first 20 rows)", "Yes (high confidence only)"],
     ["Supplementary PDF", ".pdf (not main)", "No (file link only)", "No"],
     ["Document", ".docx", "No (file link only)", "No"],
     ["Archive", ".zip", "No (file link only)", "No"]]
)

h3("7.2 folder_explicit Binding")
p("All files in the same folder as the main PDF are automatically linked to that paper with high confidence. This is the safest binding method.")
bullet("import_source = article_bundle")
bullet("binding_method = folder_explicit")
bullet("match_confidence = high")
bullet("Can enter entity index: Yes")

h3("7.3 loose supplementary")
p("Files placed in 00_Inbox/loose_supplementary/new/ or found outside article bundles:")
bullet("require manual confirmation")
bullet("will NOT be automatically matched to any paper")
bullet("will NOT enter the entity index")
bullet("marked as review_needed or candidate_only")

h3("7.4 Entity Indexing Rules")
p("Only supplementary files meeting ALL of these conditions are indexed:")
bullet("content_status = simple_preview_extracted")
bullet("match_confidence = high or medium")
bullet("binding_method = folder_explicit (or manual_confirmed)")
bullet("file type = xlsx, xls, csv, or tsv")
p("candidate_only and file_missing files are EXPLICITLY excluded from entity indexing.")

# ── 8. Web Interface Guide ──
h2("8. Web Interface — Complete Page Guide")

pages_en = [
    ("/chat", "AI Literature Chat", "Ask research questions. 7 query types auto-detected. Three answer modes. Citations with [Ref:N] references. Token usage display.", "Available"),
    ("/library", "Paper Library", "Paginated list of all imported papers. Search by title, author, year, DOI. Filter by tags.", "Available"),
    ("/paper/{id}", "Paper Detail", "Metadata, AI summary, structured evidence, figures, tables. 'Ask this paper' card for paper-specific chat.", "Available"),
    ("/evidence", "Evidence Search", "Search evidence chunks by keyword. Filter by type (method, result, claim, etc.).", "Available"),
    ("/research-map", "Research Topic Map", "Facet-first hierarchical topic explorer. Topic evolution with evidence-rich phase cards.", "Available"),
    ("/hotspots", "Trending Topics", "Trending topics, hot papers, emerging facets. Evidence coverage indicators.", "Available"),
    ("/research-gaps", "Research Gaps", "Auto-detected evidence gaps from facet distribution. Confidence and impact scores.", "Available"),
    ("/knowledge-network", "Knowledge Network", "Paper-facet-method-finding network graph. 123 nodes × 330 edges.", "Available"),
    ("/report", "Library Report", "Auto-generated library intelligence report with executive summary.", "Available"),
    ("/topic-explorer", "Topic Explorer", "Browse topics by research facet with paper lists and evidence coverage.", "Available"),
    ("/import", "Import Dashboard", "View article bundles, main PDF detection, supplementary status, loose files needing review.", "Planned (v1.6)"),
    ("/assets", "Assets Viewer", "Browse figures, tables, supplementary assets, gene evidence, entity comparisons.", "Planned (v1.6)"),
    ("/settings", "Settings", "Application configuration.", "Available"),
]
for pg, desc, detail, status in pages_en:
    h3(f"8.{pages_en.index((pg,desc,detail,status))+1} {pg} — {desc}")
    p(f"Status: {status}")
    p(detail)

# ── 9. Literature Chat ──
h2("9. Literature Chat — Complete Usage Guide")

h3("9.1 Query Types")
p("The system automatically detects your query intent:")
table(
    ["Intent", "Example", "Output Style"],
    [["claim_query", "Which claims need stronger evidence?", "Claim → Evidence → Missing → Sources"],
     ["research_gap_query", "What research gaps can be inferred?", "Evidence-based + Inferred gaps"],
     ["method_query", "What bioassay methods are commonly used?", "Grouped by category (5 groups)"],
     ["result_query", "Which results are frequently reported?", "Result + evidence strength"],
     ["supplementary_entity_query", "Is MAP2K4 in supplementary tables?", "Entity values + source + caution"],
     ["supplementary_entity_comparison_query", "Compare MAP2K4 across papers.", "Aggregated records + direction summary"],
     ["hybrid_search", "General literature questions", "Mixed retrieval + LLM synthesis"]]
)

h3("9.2 Answer Modes")
bullet("Auto (recommended): Uses LLM if API key configured, otherwise evidence-only fallback")
bullet("LLM synthesis: Forces LLM call with academic citation format")
bullet("Evidence-only: Deterministic, no API call, <100ms response time")

h3("9.3 How to Ask Good Questions")
bullet("Be specific: 'Is MAP2K4 present in supplementary tables?' instead of 'Tell me about MAP2K4'")
bullet("For comparison: 'Compare MAP2K4 across supplementary data.'")
bullet("For methods: 'What bioassay methods are commonly used for Spodoptera?'")
bullet("Include context: mention entity type if known (gene, protein, compound)")

h3("9.4 Citations and Traceability")
p("All LLM answers include [Ref:N] citations. Each citation links to a specific chunk in LanceDB with a unique chunk_id. You can verify the source by checking the chunk's paper_id, source_section, and linked_evidence_ids.")

h3("9.5 Token Usage and Cost")
p("The Chat interface shows an inline token usage panel with: provider, model, prompt_tokens, completion_tokens, total_tokens, and estimated cost in USD. Evidence-only mode uses 0 tokens.")

h3("9.6 Limitations")
bullet("Answers are based only on your imported literature — not the entire internet")
bullet("LLM may occasionally misinterpret context. Always verify citations.")
bullet("Single-row supplementary data cannot prove causality. Interpretation includes 'What this does not prove' section.")
bullet("source_link_count means the same data row is linked to multiple references — NOT independent evidence.")

# ── 10. Query APIs and SDK ──
h2("10. Query APIs and SDK")

h3("10.1 API Endpoints")
table(
    ["Endpoint", "Method", "Description"],
    [["/v1/agent/ask", "POST", "Literature Agent — AI-powered Q&A with citations"],
     ["/query/assets", "POST", "Search asset chunks (11 types, filterable by chunk_type and paper_id)"],
     ["/query/evidence", "POST", "Search evidence chunks"],
     ["/query/supplementary-entities", "POST", "Search indexed supplementary entities by gene/protein/compound name"],
     ["/query/supplementary-entity-comparison", "POST", "Cross-paper entity comparison with direction summary"],
     ["/health", "GET", "API and LanceDB status"]]
)

h3("10.2 SDK Examples")
code("from scientra.sdk import query_assets, query_supplementary_entities")
code("")
code("# Search for method chunks about protein expression")
code('r = query_assets("protein expression", top_k=10, chunk_types=["method"])')
code("")
code("# Search supplementary entities for a gene")
code('r = query_supplementary_entities("MAP2K4", entity_type="gene")')
code('for m in r["matches"]:')
code('    print(m["entity_text"], m["value_columns"])')
code("")
code("# Cross-paper comparison")
code('from scientra.sdk import query_supplementary_entity_comparison')
code('r = query_supplementary_entity_comparison("MAP2K4")')
code('print(r["total_matches"], r["direction_summary"])')

# ── 11. Maintenance ──
h2("11. Database Maintenance and Upgrade Guide")

h3("11.1 Adding New Papers")
code("1. Place article folder in 00_Inbox/article_bundles/new/")
code("2. python Scripts/process_article_bundles.py --scan")
code("3. python Scripts/process_article_bundles.py --process --archive-mode copy")
code("4. python -m scientra.pdf_data_assets.build_assets --supplementary --all --force")
code("5. python -m scientra.pdf_data_assets.build_assets --supplementary-entities --all --force")
code("6. python -m scientra.pdf_data_assets.build_assets --quality-check")
code("7. python -m scientra.pdf_data_assets.asset_embedding --all --force")

h3("11.2 Rebuilding Assets")
p("Use --force only when source data has changed significantly:")
code("python -m scientra.pdf_data_assets.build_assets --tables --all --force")
code("python -m scientra.pdf_data_assets.build_assets --figures --all --force")

h3("11.3 LanceDB Maintenance")
bullet("Primary path: 06_Index/vector/lancedb/")
bullet("Backup before rebuild: copy 06_Index/vector/lancedb/ to 10_System/backups/")
bullet("Check status: python -m scientra.pdf_data_assets.asset_embedding --status")
bullet("Legacy archive: 10_System/legacy_archive/ contains the pre-v3 LanceDB. Safe to keep as backup.")
p("Do NOT manually edit LanceDB files. Always use the provided tools.")

h3("11.4 When to Use --force")
bullet("After changing source data (new papers, updated supplementary files)")
bullet("After fixing bugs in extraction logic")
bullet("When regenerating assets from scratch")
h3("11.5 When NOT to Rebuild")
bullet("Adding only a few new papers — use incremental processing")
bullet("Routine checks — use --quality-check instead")
bullet("When the system is working correctly — don't fix what isn't broken")

# ── 12. Troubleshooting ──
h2("12. Error Troubleshooting")

troubleshooting = [
    ("Backend cannot start", "Port 8710 is already in use", "Check: netstat -ano | findstr 8710. Kill the process or change port.", "python -m scientra.server"),
    ("Frontend cannot start", "Port 3000 in use or node_modules missing", "Check port. Run: cd web && npm install && npm run dev", "cd web && npm run dev"),
    ("GROBID not responding", "Docker not running or port 8070 conflict", "Check: docker ps. Start Docker. Check GROBID logs.", "docker start grobid"),
    ("API key missing", "DEEPSEEK_API_KEY or ANTHROPIC_API_KEY not set", "Run: python Scripts/setup_llm.py. Or set environment variable.", "python Scripts/setup_llm.py"),
    ("LanceDB cannot open", "Path missing or corrupt", "Check 06_Index/vector/lancedb/ exists. Try legacy archive fallback.", "python Scripts/promote_lancedb_to_v3.py --verify"),
    ("Query returns no results", "Data not imported or not embedded", "Check: python -m scientra.pdf_data_assets.asset_embedding --status", "Re-embed: python -m scientra.pdf_data_assets.asset_embedding --all --force"),
    ("Supplementary entity not found", "File is candidate_only or file_missing", "Check match_confidence. Only high/medium + simple_preview_extracted files are indexed.", "Rename file to include paper_id in filename"),
    ("Excel not parsed", "openpyxl not installed", "Run: pip install openpyxl", "pip install openpyxl"),
    ("Chat returns empty answer", "LLM API error or no evidence found", "Try Evidence-only mode. Check API key. Check network.", "Switch to Evidence-only mode in Chat"),
    ("npm build error", "Dependencies missing or version conflict", "Run: cd web && npm install && npm run build", "cd web && npm install"),
    ("Table structure unavailable", "GROBID text doesn't preserve table layout", "This is expected for complex tables. Try supplementary Excel files instead.", "Import supplementary tables as Excel/CSV"),
    ("Legacy archive fallback issue", "04_VectorDB auto-created empty directory", "Delete the empty auto-created directory. System will use archive.", "Check context_builder log for fallback path"),
]
for symptom, cause, check, fix in troubleshooting:
    h3(f"12.{troubleshooting.index((symptom,cause,check,fix))+1} {symptom}")
    p(f"Symptom: {symptom}", bold=True)
    p(f"Likely cause: {cause}")
    p(f"How to check: {check}")
    p(f"Fix: {fix}")

# ── 13. Development Guide ──
h2("13. Development and Extension Guide")

h3("13.1 Adding a New Corpus")
code("1. Create directory under 04_Corpus/<category>/")
code("2. Build extraction logic in scientra/pdf_data_assets/")
code("3. Add chunk type to schemas.py, agent_chunk_builder.py, quality checker")
code("4. Add to build_assets.py with a new --flag")
code("5. Add to asset_embedding.py for LanceDB storage")
code("6. Write tests following existing patterns")

h3("13.2 Adding a New Asset Type")
code("1. Add schema class to scientra/pdf_data_assets/schemas.py")
code("2. Create builder module: scientra/pdf_data_assets/<type>_builder.py")
code("3. Add chunk generation in agent_chunk_builder.py")
code("4. Add to VALID_CHUNK_TYPES in server.py")
code("5. Add to quality checker rules")
code("6. Update frontend types in web/lib/types.ts if needed")

h3("13.3 Safety Rules for Developers")
bullet("Never commit API keys, PDFs, LanceDB, or user data")
bullet("Never use absolute paths in reports or API responses")
bullet("Never delete user files — use copy mode as default")
bullet("Always write tests before changing production code paths")
bullet("Respect the legacy archive — it's the user's safety net")

# ── 14. Data Safety ──
h2("14. Data Safety and Git Rules")

h3("14.1 What Should Never Be Committed")
bullet("PDF files (*.pdf)")
bullet("Excel/CSV/TSV files (*.xlsx, *.xls, *.csv, *.tsv)")
bullet("LanceDB directory (06_Index/vector/lancedb/)")
bullet("API keys (Config/llm_config.yaml — already gitignored)")
bullet("Raw text files (02_Parse/text/)")
bullet("Generated data: 03_Assets/, 04_Corpus/, 05_Knowledge/")

h3("14.2 .gitignore Recommendations")
code("00_Inbox/")
code("01_Sources/")
code("02_Parse/")
code("03_Assets/")
code("04_Corpus/")
code("05_Knowledge/")
code("06_Index/")
code("07_Agents/")
code("08_Projects/")
code("09_Exports/")
code("10_System/")
code("*.pdf")
code("*.xlsx")
code("*.csv")
code("lancedb/")

h3("14.3 Backup Strategy")
bullet("Before major migrations: backup 10_System/backups/")
bullet("Before LanceDB rebuild: backup 06_Index/vector/lancedb/")
bullet("Legacy archive at 10_System/legacy_archive/ is your safety net")
bullet("All backups use sha256 verification")

# ── 15. FAQ ──
h2("15. Frequently Asked Questions")

faq_en = [
    ("Is cloud required?", "No. All data stays local. LLM integration uses your own API keys and is optional."),
    ("Can I delete the legacy archive?", "Yes, after confirming all systems work correctly from the new paths."),
    ("What LLM providers are supported?", "DeepSeek (deepseek-chat) and Anthropic Claude (claude-sonnet-4-6)."),
    ("Does it work without an LLM?", "Yes. Use Evidence-only mode in Chat. All APIs work without LLM."),
    ("Can I add supplementary files later?", "Yes. Put them in the article bundle folder and re-process."),
    ("Why is my file marked candidate_only?", "It matched a supplementary label (e.g., 'Table S1') but not a specific paper. Rename to include paper_id."),
    ("How to get high confidence matching?", "Use folder_explicit binding: place the file in the same folder as the main PDF."),
    ("Does it support Chinese papers?", "GROBID supports multiple languages. Chat works in Chinese and English."),
    ("How large can the database grow?", "LanceDB scales to millions of vectors. Performance depends on your hardware."),
    ("Why are table structures not extracted from PDF?", "GROBID text loses table grid structure. Use supplementary Excel/CSV for structured table data."),
]
for q, a in faq_en:
    h3(f"Q: {q}")
    p(f"A: {a}")

# ── 16. Roadmap ──
h2("16. Roadmap")

table(
    ["Phase", "Version", "Features"],
    [["Near-term", "v1.6", "Import Dashboard, Assets Viewer, Manual Binding UI for loose supplementary"],
     ["Mid-term", "v1.7–1.8", "Corpus builders (expression, intro, discussion, method, claim, gap), Gene Evidence expansion, Cross-study comparison"],
     ["Long-term", "v2.0+", "Knowledge Graph, Scientific Memory, Reasoning Engine, Experimental Design Agent, AI Reviewer Agent"]]
)

doc.add_page_break()

# ══════════════════════════════════════════════════════════
# PART II: CHINESE
# ══════════════════════════════════════════════════════════

h1("Part II. 中文使用说明书")

h2("1. 软件简介")
p("Scientra Copilot 是一个本地优先、证据导向的科研文献发现平台。它将科学论文（PDF）、补充文件（Excel/CSV/TSV）、图表和表格转化为结构化、可检索、可供 AI 查询的知识——全部在你的本地机器上运行。")
p("不同于把论文当成不透明文件的文献管理工具，Scientra Copilot 真正阅读并理解你的文献。它能提取方法、结果、论断、图表、表格和实体，将补充数据与母论文关联，从补充表格中索引基因和蛋白质，并提供基于文献的 AI 对话界面——所有回答都带可追溯引用。")
warn("Scientra Copilot 不是云服务。所有数据在你的电脑上。LLM 集成是可选的，使用你自己的 API key。")

h2("2. 设计逻辑")
p("核心理念：从 PDF 收集到基于证据的研究记忆。每一块提取的知识都携带溯源——你可以追溯一个论断或实体值到它来源的表格、行、文件和论文。")
p("流水线：论文 → 资产 → 语料 → 知识 → 索引 → 智能体。每一步保留溯源信息（来源文件、导入方式、匹配置信度、SHA256）。")
p("为什么补充数据重要：科学论文中最有价值的结构化数据往往在补充文件中——基因表达表格、生测结果、引物列表、统计模型。传统工具忽略这些文件。Scientra Copilot 将它们视为一等数据源。")
p("folder_explicit 绑定：同一文件夹内的所有文件和正文 PDF 通过文件夹明确关联，置信度 high。不靠文件名猜测。loose supplementary（散装补充文件）需要人工确认，不会自动进入实体索引。")

h2("3. 整体架构")
bullet("后端：Python 3.11+，FastAPI，端口 8710。GROBID（Docker）解析 PDF。BGE-M3 嵌入（1024 维）。LanceDB 向量存储。")
bullet("前端：Next.js 14，React，Tailwind CSS，端口 3000。")
bullet("LLM：DeepSeek deepseek-chat 或 Anthropic Claude。API key 保存在 Config/llm_config.yaml（已 gitignore）。")
bullet("存储：Storage Layout v3，10 组目录结构（详见第 4 章）。")

h2("4. Storage Layout v3 详细参考")
p("10 组目录，每组有明确用途。不要手动修改系统管理的目录。")
table(
    ["目录", "用途", "可否手动修改"],
    [["00_Inbox/", "导入入口", "✅ 放入文件"],
     ["01_Sources/", "原始文件 + manifest", "❌ 系统管理"],
     ["02_Parse/", "解析中间产物", "❌ 系统管理"],
     ["03_Assets/", "结构化资产（JSON）", "❌ 系统管理"],
     ["04_Corpus/", "长期语料库", "❌ 系统管理"],
     ["05_Knowledge/", "知识图谱和地图", "❌ 系统管理"],
     ["06_Index/", "检索索引（LanceDB）", "❌ 系统管理"],
     ["07_Agents/", "智能体工作区", "🔧 开发者"],
     ["08_Projects/", "用户项目", "✅ 用户工作区"],
     ["09_Exports/", "导出", "✅ 可读"],
     ["10_System/", "配置/日志/备份/归档", "⚠️ 只读"]]
)
p("LanceDB 主路径：06_Index/vector/lancedb/（3 张表，4,234 行）。旧版数据归档在 10_System/legacy_archive/。")

h2("5. 安装与启动")
bullet("环境要求：Python 3.11+、Node.js 18+、Docker")
code("python Scripts/dev_restart.py  # 一键启动")
code("python Scripts/setup_llm.py   # 配置 LLM（可选）")
bullet("API：http://127.0.0.1:8710 | Web：http://127.0.0.1:3000")

h2("6. 导入文献")
p("推荐：Article Bundle Import。一篇文章一个文件夹。")
code("00_Inbox/article_bundles/new/论文文件夹/")
code("├── main.pdf      ← 正文（自动识别）")
code("├── Table_S1.xlsx ← 补充表格")
code("└── Source_Data.csv")
code("")
code("python Scripts/process_article_bundles.py --scan")
code("python Scripts/process_article_bundles.py --process --archive-mode copy")
p("正文 PDF 识别：含 main/paper/article 文件名优先；含 supplementary/supporting 文件名降低优先级。仅一个 PDF 则自动选。无 PDF 则失败。")
p("归档模式：copy（安全默认）、move（谨慎使用）、none、dry-run（仅计划）。")

h2("7. 补充文件管理")
table(
    ["类型", "扩展名", "可预览？", "可进入实体索引？"],
    [["表格", ".xlsx .xls .csv .tsv", "是（前 20 行）", "是（高置信）"],
     ["补充 PDF", ".pdf（非正文）", "否", "否"],
     ["文档", ".docx", "否", "否"],
     ["压缩包", ".zip", "否", "否"]]
)
p("folder_explicit 绑定：同一文件夹内的文件自动关联，置信度 high。")
warn("loose supplementary（散装补充文件）需要人工确认，不会自动进入实体索引。")

h2("8. Web 页面解读")
pages_cn = [
    ("/chat", "AI 文献对话", "7 种查询类型，3 种回答模式，带引用", "可用"),
    ("/library", "论文库", "分页浏览，搜索筛选", "可用"),
    ("/paper/{id}", "论文详情", "元数据、摘要、证据、本文提问", "可用"),
    ("/evidence", "证据搜索", "关键词搜索，类型筛选", "可用"),
    ("/research-map", "研究地图", "分层主题浏览", "可用"),
    ("/hotspots", "热点", "热门话题、热点论文", "可用"),
    ("/research-gaps", "研究空白", "自动检测", "可用"),
    ("/knowledge-network", "知识网络", "关系图谱", "可用"),
    ("/report", "文献库报告", "自动生成", "可用"),
    ("/topic-explorer", "维度浏览", "按研究维度浏览话题", "可用"),
    ("/import", "导入仪表盘", "查看导入状态", "规划中"),
    ("/assets", "资产查看器", "浏览资产", "规划中"),
]
for pg, desc, detail, status in pages_cn:
    h3(f"{pg} — {desc}（{status}）")
    p(detail)

h2("9. Chat 使用方法")
p("系统自动识别 7 种查询类型。3 种回答模式：Auto（推荐）、LLM synthesis、Evidence-only。")
p("如何提问：尽量具体。例如 'Is MAP2K4 in supplementary tables?'、'Compare MAP2K4 across supplementary data.'")
p("回答中的 [Ref:N] 引用可追溯到 LanceDB 中的源片段。Token 用量面板显示消耗。")
warn("单行补充数据不能证明因果关系。LLM 解释包含严格的限制声明。source_link_count 不是独立证据数量。")

h2("10. 检索 API 与 SDK")
code("from scientra.sdk import query_assets, query_supplementary_entities")
code('r = query_assets("protein expression", chunk_types=["method"])')
code('r = query_supplementary_entities("MAP2K4", entity_type="gene")')

h2("11. 数据库维护与升级")
p("添加新论文流程：")
code("1. 放入 00_Inbox/article_bundles/new/")
code("2. process_article_bundles --scan && --process")
code("3. build_assets --supplementary --all --force")
code("4. build_assets --supplementary-entities --all --force")
code("5. build_assets --quality-check")
code("6. asset_embedding --all --force")
p("使用 --force 的情况：源数据有重大变更。日常添加少量论文：增量处理即可。")
p("备份：重大操作前备份 06_Index/vector/lancedb/ 到 10_System/backups/。")

h2("12. 常见报错与维修")
errors_cn = [
    ("后端无法启动", "端口 8710 被占用", "netstat -ano | findstr 8710", "python -m scientra.server"),
    ("前端无法启动", "端口 3000 被占用或依赖缺失", "cd web && npm install", "cd web && npm run dev"),
    ("GROBID 无响应", "Docker 未运行", "docker ps", "docker start grobid"),
    ("API key 缺失", "环境变量未设置", "python Scripts/setup_llm.py", "设置 DEEPSEEK_API_KEY"),
    ("LanceDB 无法打开", "路径丢失", "检查 06_Index/vector/lancedb/", "python Scripts/promote_lancedb_to_v3.py --verify"),
    ("查询无结果", "数据未导入或未嵌入", "python -m scientra.pdf_data_assets.asset_embedding --status", "重新嵌入"),
    ("补充实体找不到", "文件是 candidate_only 或 file_missing", "检查 match_confidence", "改名包含 paper_id"),
    ("Excel 无法解析", "缺少 openpyxl", "pip install openpyxl", "pip install openpyxl"),
    ("表格结构不可用", "GROBID 文本丢失表格结构", "正常现象", "使用 Excel/CSV 补充文件"),
]
for symptom, cause, check, fix in errors_cn:
    h3(f"{symptom}")
    p(f"原因：{cause}")
    p(f"排查：{check}")
    p(f"修复：{fix}")

h2("13. 开发扩展指南")
p("添加新语料：在 04_Corpus/ 下创建目录，构建提取逻辑。添加新资产类型：添加 schema、builder、chunk type、embedder。安全规则：不提交 API key、PDF、LanceDB 或用户数据。不使用绝对路径。不删除用户文件。")

h2("14. 数据安全")
p("绝不提交到 git：PDF、Excel/CSV/TSV、LanceDB、API key、原始文本、生成数据。")
p("Config/llm_config.yaml 已 gitignore。所有报告和清单仅使用相对路径。")

h2("15. 常见问题")
faq_cn = [
    ("需要云端吗？", "不需要。所有数据在本地。LLM 用你自己的 API key。"),
    ("能删除 legacy_archive 吗？", "确认系统正常后可手动删除。"),
    ("支持哪些 LLM？", "DeepSeek 和 Anthropic Claude。"),
    ("没有 LLM 能用吗？", "能。使用 Evidence-only 模式。"),
    ("能后加补充文件吗？", "能。放入 article bundle 文件夹重新处理。"),
    ("为什么是 candidate_only？", "文件名缺少 paper_id。改名或放入 article bundle。"),
    ("支持中文论文吗？", "GROBID 支持多语言。Chat 支持中文。"),
    ("数据库能多大？", "LanceDB 支持百万级向量。"),
]
for q, a in faq_cn:
    h3(f"问：{q}")
    p(f"答：{a}")

h2("16. 未来路线图")
table(
    ["阶段", "版本", "功能"],
    [["近期", "v1.6", "导入仪表盘、资产查看器、手动绑定界面"],
     ["中期", "v1.7–1.8", "语料构建器、基因证据扩展、跨研究比较"],
     ["远期", "v2.0+", "知识图谱、科学记忆、推理引擎、实验设计助手、AI 审稿助手"]]
)

# ── Save ──
out = root / "Scientra_Copilot_User_Manual_v2_bilingual.docx"
doc.save(str(out))
print(f"Generated: {out.name} ({out.stat().st_size:,} bytes)")
