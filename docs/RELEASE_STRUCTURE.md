# Scientra Copilot v1.0 Beta — Release Structure

```
Scientra Copilot/
├── README.md                          # Project overview
├── RELEASE_STRUCTURE.md               # This file
├── workflow.py                        # Workflow CLI entry point
├── workflow_runner.py                 # Workflow orchestrator (root)
├── agent_sdk.py                       # Agent SDK
├── agent_query_interface.py           # Agent query interface
├── api_server.py                      # Query API server
├── chunker.py                         # Text chunker
├── embedding_engine.py                # BGE-M3 embedding engine
├── query_models.py                    # Query data models
├── query_service.py                   # Query service
├── summary_agent.py                   # Summary Agent Mode (default)
├── summary_engine.py                  # Summary Engine (legacy direct_api)
├── tag_engine.py                      # Tag engine
├── vector_store.py                    # LanceDB vector store
│
├── 00_Inbox/                          # 📥 PDF drop zone
│   ├── README.md
│   └── .gitkeep
│
├── 01_PDF/                            # 📄 Working PDF copies
│   ├── README.md
│   └── .gitkeep
│
├── 02_Metadata/                       # 📋 Metadata outputs
│   ├── README.md
│   ├── papers/                        # Parse JSON output
│   │   └── .gitkeep
│   ├── yaml/                          # Enriched metadata YAML
│   │   └── .gitkeep
│   └── tei/                           # GROBID TEI XML
│       └── .gitkeep
│
├── 03_Summary/                        # 📝 Summaries and text
│   ├── README.md
│   ├── raw_text/                      # Extracted plain text
│   │   └── .gitkeep
│   ├── cache/                         # Summary cache
│   │   └── .gitkeep
│   ├── summaries/                     # Summary markdown files
│   │   └── .gitkeep
│   ├── chunks/                        # Text chunks
│   │   └── .gitkeep
│   ├── failures/                      # Failure logs
│   │   └── .gitkeep
│   └── agent_prompts/                 # Agent mode prompts
│       └── .gitkeep
│
├── 04_VectorDB/                       # 🔍 Vector database
│   ├── README.md
│   └── lancedb/                       # LanceDB storage
│       └── .gitkeep
│
├── 05_Index/                          # 🏷️ Tags and index
│   ├── README.md
│   └── tags/                          # Tag assignments
│       └── .gitkeep
│
├── 06_API/                            # 🌐 Query API
│   ├── README.md
│   └── .gitkeep
│
├── 07_Workflows/                      # ⚙️ Workflow orchestration
│   ├── README.md
│   ├── workflow_config.yaml
│   ├── workflow_models.py
│   ├── workflow_runner.py
│   ├── workflow_state.py
│   ├── logs/                          # Run logs
│   │   └── .gitkeep
│   └── reports/                       # Workflow reports
│       └── .gitkeep
│
├── 08_Agent_Interface/                # 🤖 Agent SDK interface
│   ├── README.md
│   └── .gitkeep
│
├── Config/                            # 🔧 Configuration
│   ├── README.md
│   ├── workflow_config.yaml
│   ├── grobid.yaml
│   ├── embedding.yaml
│   ├── tag_ontology.yaml
│   └── tag_dictionary.yaml
│
├── Scripts/                           # 🛠️ Pipeline scripts
│   ├── README.md
│   ├── pdf_parser.py
│   ├── metadata_extractor.py
│   ├── retag.py
│   ├── build_embeddings.py
│   ├── search_test.py
│   ├── system_check.py
│   ├── ensure_grobid.py
│   ├── grobid_client.py
│   ├── grobid_diagnostic.py
│   ├── run_api_server.py
│   └── run_workflow.py
│
├── Tests/                             # 🧪 Test suite
│   ├── README.md
│   └── .gitkeep
│
├── docs/                              # 📚 Documentation
│   ├── README.md
│   ├── System_Requirements.md
│   └── Summary_Agent_Mode.md
│
├── examples/                          # 📖 Usage examples
│   ├── README.md
│   └── .gitkeep
│
├── templates/                         # 📄 Templates
│   ├── README.md
│   └── .gitkeep
│
└── tools/                             # 🔨 Utility tools
    ├── README.md
    └── .gitkeep
```

## Directory Legend

| Icon | Directory | Purpose |
|------|-----------|---------|
| 📥 | 00_Inbox | PDF input |
| 📄 | 01_PDF | Working PDF copies |
| 📋 | 02_Metadata | Metadata extraction |
| 📝 | 03_Summary | Summaries and text |
| 🔍 | 04_VectorDB | Vector embeddings |
| 🏷️ | 05_Index | Tags and index |
| 🌐 | 06_API | Query API |
| ⚙️ | 07_Workflows | Orchestration |
| 🤖 | 08_Agent_Interface | Agent SDK |
| 🔧 | Config | Configuration |
| 🛠️ | Scripts | Pipeline scripts |
| 🧪 | Tests | Test suite |
| 📚 | docs | Documentation |
| 📖 | examples | Usage examples |
| 📄 | templates | Project templates |
| 🔨 | tools | Utility tools |

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd Scientra Copilot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start GROBID
docker run -d --name scientra_grobid -p 18070:8070 lfoppiano/grobid:latest

# 4. Verify system
python Scripts/system_check.py

# 5. Add PDFs to 00_Inbox/

# 6. Run workflow
python workflow.py run --input-dir 00_Inbox
```
