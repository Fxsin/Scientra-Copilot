# Third-Party Notices — Scientra Copilot

This document lists all third-party software components used in Scientra Copilot,
their licenses, and attribution requirements. It is organized by category:

1. **Bundled Source Code** — Projects whose full source is included in this repository
2. **Python Dependencies** — Packages installed via pip/poetry
3. **Node.js / npm Dependencies** — Packages installed via npm (frontend)
4. **Copied / Adapted Components** — Individual files or patterns adapted from third-party projects

---

## 1. Bundled Source Code (external/ directory)

These are complete third-party repositories cloned into `external/` for reference,
installation, or optional runtime use. They are NOT compiled or linked into the
core Scientra Copilot binary.

### 1.1 OpenDataLoader PDF

| Field | Value |
|-------|-------|
| **Project Name** | OpenDataLoader PDF |
| **GitHub** | https://github.com/opendataloader-project/opendataloader-pdf |
| **Author / Organization** | Hancom, Inc. |
| **License** | Apache License 2.0 (Apache-2.0) |
| **SPDX Identifier** | Apache-2.0 |
| **Has NOTICE File** | Yes (preserved at docs/licenses/opendataloader-pdf/NOTICE) |
| **Location in Repo** | `external/opendataloader-pdf/` |
| **Commit Reference** | `93663e5` |
| **Usage in Scientra** | Primary PDF parser — converts PDF to Markdown, layout JSON, and tables |
| **Source Copied** | Yes (full git clone) |
| **Source Modified** | No |
| **Modification Summary** | N/A |
| **How Invoked** | Runtime import via `scientra/parsers/opendataloader_adapter.py` |
| **Risk Level** | 🟢 Low — Apache-2.0 is permissive; NOTICE must be preserved |

**Attribution (required by Apache-2.0 §4d):**
```
This product includes OpenDataLoader PDF (https://github.com/opendataloader-project/opendataloader-pdf)
Copyright 2025–2026 Hancom, Inc. Licensed under Apache License 2.0.
```

### 1.2 Marker (Datalab)

| Field | Value |
|-------|-------|
| **Project Name** | Marker (Datalab) |
| **GitHub** | https://github.com/VikParuchuri/marker |
| **Author / Organization** | Vik Paruchuri / Endless Labs, Inc. |
| **License (Code)** | GNU General Public License v3.0 or later (GPL-3.0-or-later) |
| **License (Models)** | AI PUBS OPEN RAIL-M LICENSE (Modified) |
| **SPDX Identifier** | GPL-3.0-or-later (code), OpenRAIL-M (models) |
| **Location in Repo** | `external/marker/` |
| **Commit Reference** | `d3739db` |
| **Usage in Scientra** | Optional fallback PDF → Markdown parser (high-quality, not default) |
| **Source Copied** | Yes (full git clone) |
| **Source Modified** | No |
| **Modification Summary** | N/A |
| **How Invoked** | Runtime import via `scientra/parsers/marker_adapter.py` (only if installed) |
| **Risk Level** | 🔴 **HIGH** — GPL-3.0 is a strong copyleft license |

> ⚠️ **IMPORTANT — GPL-3.0 Risk Assessment:**
>
> Marker is licensed under GPL-3.0-or-later. The Scientra Copilot project
> maintains Marker as an **optional, pluggable** parser. The adapter
> (`scientra/parsers/marker_adapter.py`) gracefully degrades when Marker is
> not installed. Marker is:
> - NOT compiled or linked into the Scientra Copilot distribution
> - NOT a required dependency (commented out in requirements.txt)
> - Only invoked at runtime via `importlib` when explicitly enabled by the user
> - Listed as optional in pyproject.toml (commented out)
>
> **However**, if a user installs Marker alongside Scientra Copilot and the
> adapter imports it at runtime, the GPL-3.0 copyleft may apply to the
> combined work. **Users should seek legal advice** before distributing
> Scientra Copilot with Marker included.
>
> The model weights are separately licensed under OpenRAIL-M, which has
> additional use restrictions (see `docs/licenses/marker/MODEL_LICENSE`).

**Attribution:**
```
Marker PDF conversion engine (https://github.com/VikParuchuri/marker)
Copyright Vik Paruchuri. Licensed under GPL-3.0-or-later.
Models licensed under AI PUBS OPEN RAIL-M LICENSE (Modified).
```

---

## 2. Python Dependencies

These are runtime dependencies declared in `pyproject.toml` and/or `requirements.txt`.
They are installed from PyPI and are NOT bundled in this repository.

### 2.1 Core Dependencies (pyproject.toml `dependencies`)

| Package | Version | License | SPDX | Usage |
|---------|---------|---------|------|-------|
| fastapi | >=0.100 | MIT | MIT | REST API framework |
| uvicorn | >=0.23 | BSD-3-Clause | BSD-3-Clause | ASGI server |
| lancedb | >=0.4 | Apache-2.0 | Apache-2.0 | Vector database |
| pyyaml | >=6.0 | MIT | MIT | YAML config parsing |
| loguru | >=0.7 | MIT | MIT | Structured logging |
| sentence-transformers | >=2.2 | Apache-2.0 | Apache-2.0 | Text embeddings |
| torch | >=2.0 | BSD-3-Clause | BSD-3-Clause | Deep learning framework |
| pydantic | >=2.0 | MIT | MIT | Data validation |
| pyarrow | >=12.0 | Apache-2.0 | Apache-2.0 | Columnar data format |
| requests | >=2.28 | Apache-2.0 | Apache-2.0 | HTTP client |

### 2.2 Additional Dependencies (requirements.txt)

| Package | Version | License | SPDX | Usage |
|---------|---------|---------|------|-------|
| typer | >=0.9 | MIT | MIT | CLI framework |
| numpy | >=1.24 | BSD-3-Clause | BSD-3-Clause | Numerical computing |
| transformers | >=4.30 | Apache-2.0 | Apache-2.0 | Hugging Face models |
| huggingface-hub | >=0.16 | Apache-2.0 | Apache-2.0 | Model hub access |
| pymupdf | >=1.24 | AGPL-3.0 / Commercial | AGPL-3.0 | PDF scanning & figure extraction |
| opendataloader-pdf | >=2.4 | Apache-2.0 | Apache-2.0 | PDF markdown/layout/table extraction |

### 2.3 Optional / Development Dependencies

| Package | Version | License | SPDX | Usage |
|---------|---------|---------|------|-------|
| pytest | >=7.0 | MIT | MIT | Test framework |
| pytest-asyncio | >=0.21 | Apache-2.0 | Apache-2.0 | Async test support |
| ruff | >=0.1 | MIT | MIT | Linting |
| mypy | >=1.0 | MIT | MIT | Type checking |
| docker | >=6.0 | Apache-2.0 | Apache-2.0 | GROBID container management (optional) |

### ⚠️ High-Risk Python Dependencies

| Package | Risk | License | Issue |
|---------|------|---------|-------|
| **pymupdf** | 🔴 HIGH | AGPL-3.0 | Strong copyleft; AGPL applies to network use. Used in `scientra/parsers/pymupdf_adapter.py`. Consider replacing with a permissively-licensed alternative or obtaining a commercial license from Artifex. |
| **marker-pdf** | 🔴 HIGH | GPL-3.0 | Strong copyleft. Listed as optional (commented out in requirements.txt). Used only if user explicitly installs. |

---

## 3. Node.js / npm Dependencies (web/package.json)

### 3.1 Runtime Dependencies

| Package | Version | License | SPDX | Usage |
|---------|---------|---------|------|-------|
| @base-ui/react | ^1.5.0 | MIT | MIT | Headless UI primitives |
| @tanstack/react-query | ^5.101.0 | MIT | MIT | Server state management |
| class-variance-authority | ^0.7.1 | Apache-2.0 | Apache-2.0 | CSS variant helper |
| clsx | ^2.1.1 | MIT | MIT | CSS classname utility |
| lucide-react | ^1.17.0 | ISC | ISC | Icon library |
| next | 16.2.7 | MIT | MIT | React framework |
| react | 19.2.4 | MIT | MIT | UI library |
| react-dom | 19.2.4 | MIT | MIT | React DOM renderer |
| react-force-graph-2d | ^1.29.1 | MIT | MIT | 2D force-directed graph |
| react-markdown | ^10.1.0 | MIT | MIT | Markdown renderer |
| shadcn | ^4.11.0 | MIT | MIT | Component CLI tool |
| tailwind-merge | ^3.6.0 | MIT | MIT | Tailwind class merging |
| tw-animate-css | ^1.4.0 | MIT | MIT | CSS animation utilities |
| zustand | ^5.0.14 | MIT | MIT | State management |

### 3.2 Dev Dependencies

| Package | Version | License | SPDX | Usage |
|---------|---------|---------|------|-------|
| @tailwindcss/postcss | ^4 | MIT | MIT | PostCSS plugin |
| @types/node | ^20 | MIT | MIT | Node.js type definitions |
| @types/react | ^19 | MIT | MIT | React type definitions |
| @types/react-dom | ^19 | MIT | MIT | React DOM type definitions |
| eslint | ^9 | MIT | MIT | JavaScript linter |
| eslint-config-next | 16.2.7 | MIT | MIT | Next.js ESLint config |
| tailwindcss | ^4 | MIT | MIT | CSS framework |
| typescript | ^5 | Apache-2.0 | Apache-2.0 | TypeScript compiler |

> **Note:** The `web/node_modules/` directory contains hundreds of transitive
> dependencies installed by npm. Their licenses are documented in their
> respective `package.json` files within `node_modules/`. For a complete
> audit of transitive npm dependencies, run:
> ```bash
> npx license-checker --summary --production
> ```

---

## 4. Copied / Adapted Components

### 4.1 shadcn/ui Components

| Field | Value |
|-------|-------|
| **Project Name** | shadcn/ui |
| **GitHub** | https://github.com/shadcn-ui/ui |
| **Author** | shadcn |
| **License** | MIT |
| **SPDX Identifier** | MIT |
| **Location in Repo** | `web/components/ui/button.tsx` |
| **Usage** | Button component following shadcn/ui patterns |
| **Source Copied** | Yes (pattern adapted) |
| **Source Modified** | Yes (customized variants and styling) |
| **Modification Summary** | Custom variant definitions, sizing, and integration with project's design tokens. Uses `@base-ui/react` as the underlying primitive instead of Radix. |
| **Risk Level** | 🟢 Low — MIT license, attribution included |

**Attribution (included in source file):**
```
// Based on shadcn/ui Button component (https://ui.shadcn.com/)
// SPDX-License-Identifier: MIT
// Copyright (c) 2023 shadcn
```

### 4.2 Other UI Patterns

The following files follow patterns from shadcn/ui but are substantially
rewritten for this project's needs:

- `web/components/ui/` — Additional shadcn-style components may be added via `npx shadcn add`
- Tailwind CSS class patterns follow shadcn/ui conventions with custom theme tokens

---

## 5. License Text Preservation

All original license texts from bundled third-party projects are preserved in
the `docs/licenses/` directory:

| Original License | Preserved At |
|-----------------|--------------|
| OpenDataLoader PDF — Apache 2.0 | `docs/licenses/opendataloader-pdf/LICENSE` |
| OpenDataLoader PDF — NOTICE | `docs/licenses/opendataloader-pdf/NOTICE` |
| Marker — GPL 3.0 | `docs/licenses/marker/LICENSE` |
| Marker — OpenRAIL-M Model License | `docs/licenses/marker/MODEL_LICENSE` |

---

## 6. Summary Risk Matrix

| Component | License | Risk | Action Required |
|-----------|---------|------|----------------|
| OpenDataLoader PDF | Apache-2.0 | 🟢 Low | Preserve NOTICE and attribution |
| Marker | GPL-3.0 | 🔴 High | Keep as optional; do NOT link statically |
| PyMuPDF | AGPL-3.0 | 🔴 High | Consider replacing or obtaining commercial license |
| shadcn/ui | MIT | 🟢 Low | Include attribution comment |
| All npm deps | MIT/ISC/Apache-2.0 | 🟢 Low | Standard permissive licenses |
| All core Python deps | MIT/BSD/Apache-2.0 | 🟢 Low | Standard permissive licenses |

---

*Last updated: 2026-06-14*
*This document should be reviewed and updated whenever dependencies change.*
