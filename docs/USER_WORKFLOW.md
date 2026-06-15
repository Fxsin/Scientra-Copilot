# User Workflow — Scientra Copilot

Complete workflow from install to AI-powered research queries.

## 1. Install & Setup

```bash
git clone <repo>
cd Scientra\ Copilot
pip install -r requirements.txt
python Scripts/setup.py
```

## 2. Quick Demo (2 minutes)

```bash
python Scripts/create_demo_project.py --create-only
python Scripts/run_demo_queries.py --use-cross-asset --use-dataset --verbose
```

> ⚠️ Demo data is synthetic — for functionality testing only.

## 3. Import Your Literature

```bash
# Place article bundles in 00_Inbox/article_bundles/
# Then run the import pipeline:
python Scripts/setup.py  # or use the web Import page
```

## 4. Run Asset Intelligence

```bash
python Scripts/build_asset_links.py --all
python Scripts/build_figure_intelligence.py --all --mode rule
python Scripts/build_table_intelligence.py --all --mode rule
python Scripts/build_supplementary_intelligence.py --all --mode rule
python Scripts/build_dataset_intelligence.py --all --sample-rows 50
```

## 5. Build Knowledge Graph

```bash
python Scripts/build_unified_evidence_graph.py --verbose --validate
```

## 6. Run Validation

```bash
python Scripts/run_e2e_validation.py --all --verbose
```

## 7. Explore Results

- **Web UI**: Start the server and browse `/quality-dashboard`, `/demo`, paper detail pages
- **Cross-Asset Search**: `python Scripts/query_cross_assets.py --query "your topic"`
- **Dataset Search**: `python Scripts/query_datasets.py --entity "GENE_NAME"`
- **Research Agent**: `python Scripts/ask_research_agent.py --query "your question"`

## 8. API Access

All endpoints at `http://127.0.0.1:8710`. See [API_REFERENCE.md](API_REFERENCE.md).
