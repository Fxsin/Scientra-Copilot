from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = PROJECT_ROOT / "07_Workflows"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(WORKFLOW_DIR))

from scientra.workflow import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

