# SPDX-License-Identifier: MIT
# Copyright (c) 2024–2026 Scientra Copilot Contributors
"""Scientra Copilot — Your Literature, Structured.

LLM-Powered Literature Knowledge OS for Researchers.
"""

import sys
from pathlib import Path

# Ensure project root is on path for runtime imports
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scientra.version import __version__, VERSION, VERSION_TUPLE

# Public API — what agents should use
from scientra.sdk import (
    LiteratureAgentSDK,
    get_agent_sdk,
    get_evidence,
    get_summary,
    retrieve,
    search,
)

# The canonical query entry point
from scientra.query import literature_query

__all__ = [
    'LiteratureAgentSDK',
    'get_agent_sdk',
    'get_evidence',
    'get_summary',
    'literature_query',
    'retrieve',
    'search',
    '__version__',
]
