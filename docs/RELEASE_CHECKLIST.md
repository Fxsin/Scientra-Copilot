# Release Checklist

## Before Release

- [ ] `python -m pytest Tests -q` — all tests passing
- [ ] `python Scripts/update_docs.py --check-storage-paths --check-consistency`
- [ ] `python Scripts/release_check.py --all --fail-on-p0`
- [ ] `python Scripts/create_demo_project.py --create-only`
- [ ] `python Scripts/run_demo_queries.py --use-cross-asset --use-dataset`
- [ ] `python Scripts/run_e2e_validation.py --all --verbose`
- [ ] `python Scripts/export_quality_dashboard.py --markdown`

## Data Safety

- [ ] No user PDFs in repository
- [ ] No supplementary raw data files
- [ ] No API keys (`sk-`, `OPENAI_API_KEY`, etc.)
- [ ] No LanceDB index files committed
- [ ] No logs, backups, or validation outputs committed
- [ ] `Config/llm_config.yaml` not committed

## Storage Layout

- [ ] No `DB/DB_v2` references in code or docs
- [ ] No absolute paths in code or docs
- [ ] Storage Layout v3 directories properly gitignored

## Version

- [ ] README version badge updated
- [ ] CHANGELOG updated
- [ ] Docs reviewed for accuracy

## GitHub

- [ ] CI passing (`.github/workflows/ci.yml`)
- [ ] No large files (>20MB) in repository
- [ ] No secrets detected by `release_check.py --secrets`
- [ ] Release tag created
