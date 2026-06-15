# Troubleshooting

## GROBID Not Started

**Symptom:** PDF parsing fails, "GROBID connection refused"
**Fix:** `python Scripts/ensure_grobid.py`

## LanceDB Missing / Empty

**Symptom:** Vector search returns no results
**Fix:** Run the import pipeline to populate evidence chunks, or `python Scripts/build_unified_evidence_graph.py --embed-nodes`

## No API Key

**Symptom:** LLM features fail
**Fix:** Configure in `Config/llm_config.yaml` or `python Scripts/setup_llm.py`. All rule-based features work without API key.

## No Validation Results

**Symptom:** `/quality-dashboard` shows "Not yet run"
**Fix:** `python Scripts/run_e2e_validation.py --all --verbose`

## No Demo Data

**Symptom:** `/demo` shows empty
**Fix:** `python Scripts/create_demo_project.py --create-only`

## No Graph Results

**Symptom:** Graph queries return empty
**Fix:** `python Scripts/build_unified_evidence_graph.py --verbose --validate`

## No Dataset Intelligence

**Symptom:** `/datasets` shows empty
**Fix:** `python Scripts/build_dataset_intelligence.py --all --sample-rows 50`

## Frontend Can't Connect to Backend

**Symptom:** Web UI shows network error
**Fix:** Ensure FastAPI server is running on port 8710: `python Scripts/dev_restart.py`

## Parser Missing

**Symptom:** Parsing errors
**Fix:** Install parser dependencies: `pip install pymupdf marker-pdf pdfplumber python-docx openpyxl`

## Java Version / Docker

**Symptom:** GROBID fails to start
**Fix:** Ensure Java 11+ is installed, or use Docker: `docker run -p 8070:8070 lfoppiano/grobid:0.8.1`
