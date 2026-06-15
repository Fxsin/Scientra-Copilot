"""User Workflow Doc Builder — generate docs/USER_WORKFLOW.md."""

from __future__ import annotations
from pathlib import Path

CONTENT = """# User Workflow

## 1. Install & Setup
```bash
git clone <repo> && cd "Scientra Copilot"
pip install -r requirements.txt
python Scripts/setup.py
```

## 2. Quick Demo (2 min)
```bash
python Scripts/create_demo_project.py --create-only
python Scripts/run_demo_queries.py --use-cross-asset --use-dataset --verbose
```

## 3. Import Literature
Place article bundles in `00_Inbox/article_bundles/`. See [IMPORT_WORKFLOW.md](docs/IMPORT_WORKFLOW.md).

## 4. Run Asset Intelligence
```bash
python Scripts/build_asset_links.py --all
python Scripts/build_figure_intelligence.py --all --mode rule
python Scripts/build_table_intelligence.py --all --mode rule
python Scripts/build_supplementary_intelligence.py --all --mode rule
python Scripts/build_dataset_intelligence.py --all
```

## 5. Build Knowledge Graph
```bash
python Scripts/build_unified_evidence_graph.py --verbose
```

## 6. Validate
```bash
python Scripts/run_e2e_validation.py --all --verbose
```

## 7. Explore
- Web UI: /quality-dashboard, /demo, paper detail pages
- Search: `python Scripts/query_cross_assets.py --query "topic"`
- Agent: `python Scripts/ask_research_agent.py --query "question"`
"""


class UserWorkflowDocBuilder:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def build(self, output_path: str = "docs/USER_WORKFLOW.md") -> str:
        dest = self.root / output_path
        dest.write_text(CONTENT, encoding="utf-8")
        return str(dest)
