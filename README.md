# vba_brain — VBA & Access Modernization Pipeline

[![Python](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/next.js-v15-black?logo=next.js)](https://nextjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![gRPC](https://img.shields.io/badge/gRPC-50051-244c5a?logo=grpc)](https://grpc.io/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-blueviolet)](https://github.com/langchain-ai/langgraph)
[![Avalonia](https://img.shields.io/badge/Avalonia-UI-.NET10-purple)](https://avaloniaui.net/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**vba_brain** is an enterprise-grade 5-layer AI pipeline to modernize the entire MS Access (`.accdb` / `.mdb`) + VBA codebase — from AST analysis, design document generation, modern database SQL migration, Excel specs export, to automated generation of build-ready C#/Avalonia source code.

---

## 📋 Table of Contents

- [Architecture Overview](#-architecture-overview)
- [Directory Structure](#-directory-structure)
- [Tech Stack](#-tech-stack)
- [Detailed Layers](#-detailed-layers)
- [MongoDB Collections](#-mongodb-collections)
- [gRPC API Gateway](#-grpc-api-gateway)
- [LLM Model Routing](#-llm-model-routing)
- [Installation & Setup](#-installation--setup)
- [Running the System](#-running-the-system)
- [Web Console Dashboard](#-web-console-dashboard)
- [Output & Artifacts](#-output--artifacts)
- [Environment Variables](#-environment-variables)
- [Security](#-security)

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         vba_brain — 5-Layer Pipeline                          │
└──────────────────────────────────────────────────────────────────────────────┘

  MS Access .accdb / VBA source files
          │
          ▼
  ╔═══════════════╗
  ║   LAYER  1   ║  AST Extraction & Parsing
  ║  (Python)    ║  frm_parser / query_parser / macro_parser / modules_parser
  ╚═══════════════╝
          │  JSON exports → MongoDB (collections: forms, reports, queries_v2,
          │                          modules, macros, tables, dependency_graph)
          ▼
  ╔═══════════════╗
  ║   LAYER  2   ║  AI Design Specification (LangGraph agents)
  ║  (Python)    ║  BDService (bd1→bd4)  +  DDService (dd1→dd4)
  ╚═══════════════╝
          │  BD/DD JSON → MongoDB (collections: bds, dds)
          │  Token cost report → layer2/output/token_reports/
          ▼
  ┌───────┴──────────────────────────────────┐
  │                                          │
  ▼                                          ▼
  ╔═══════════════╗                ╔═══════════════╗
  ║   LAYER  3   ║                ║   LAYER  4   ║
  ║  SQL Migration║                ║  Excel Export ║
  ║  → PostgreSQL ║                ║  → .xlsx docs ║
  ║  → Oracle     ║                ╚═══════════════╝
  ╚═══════════════╝                         │
                                            ▼
                                  ╔═══════════════╗
                                  ║   LAYER  5   ║
                                  ║  Code   Gen  ║
                                  ║  → C# / XAML ║
                                  ║  → Avalonia  ║
                                  ╚═══════════════╝

  ┌──────────────────────────────────────────────────────────┐
  │              Infrastructure & Tooling                     │
  │  Next.js 15 Web Console  ◄──► gRPC Gateway (port 50051) │
  │  MongoDB 7 + Qdrant + Oracle XE (Docker Compose)         │
  └──────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
workflow/
├── start.py                        # Launcher: FE (Next.js :3000) + BE (gRPC :50051)
├── start_wpf.py                    # Launcher: Avalonia WPF app (dotnet build + run)
├── config.json                     # ⚠ GITIGNORED — local secrets (API keys, passwords)
├── config.example.json             # ✅ Safe template to copy
│
├── src/
│   ├── backend/
│   │   ├── requirements.txt        # Python dependencies
│   │   ├── common/
│   │   │   └── config.py           # Singleton config: reads config.json + .env, exports constants
│   │   ├── protos/
│   │   │   └── workflow.proto      # Protobuf service + message definitions
│   │   ├── api_gateway/
│   │   │   ├── grpc_server.py      # Unified gRPC server — entry point port 50051
│   │   │   ├── workflow_pb2.py     # Auto-generated protobuf message stubs
│   │   │   └── workflow_pb2_grpc.py# Auto-generated gRPC service stubs
│   │   └── workflow/
│   │       ├── layer1/             # ── Layer 1: AST Extraction ──────────────────
│   │       │   ├── parser/
│   │       │   │   ├── frm_parser.py       # Forms & Reports: controls, events, VBA
│   │       │   │   ├── query_parser.py     # Access queries: SQL text, params, joins
│   │       │   │   ├── macro_parser.py     # Macro action sequences + conditions
│   │       │   │   ├── modules_parser.py   # VBA standard modules: procs, consts
│   │       │   │   └── table_parser.py     # Table schemas: columns, types, keys
│   │       │   ├── aggregator.py           # Cross-reference enrichment engine
│   │       │   │                           # (DoCmd, DLookup, form refs, CallSub, ...)
│   │       │   ├── seed_db.py              # Seed all parsed JSON → MongoDB
│   │       │   └── run_all.py              # CLI batch: Layer 1 parse→seed→L2→L3
│   │       │
│   │       ├── layer2/             # ── Layer 2: AI Design Generation ──────────
│   │       │   ├── agents/
│   │       │   │   ├── bd_agent/
│   │       │   │   │   ├── bd_service.py       # BDService: orchestrates BD flow
│   │       │   │   │   └── core/               # bd1_extract → bd2_map → bd3_logic → bd4_final
│   │       │   │   └── dd_agent/
│   │       │   │       ├── dd_service.py       # DDService: orchestrates DD flow
│   │       │   │       └── core/               # dd1_skeleton → dd2_sql → dd3_llm → dd4_final
│   │       │   ├── db/
│   │       │   │   └── layer1_repo.py      # MongoDB read: forms/reports/modules/queries
│   │       │   ├── utils/
│   │       │   │   ├── cost_tracker.py     # Token usage + USD cost per LLM call
│   │       │   │   ├── llm_client.py       # LLM API wrapper (Alibaba/OpenAI/Anthropic)
│   │       │   │   ├── model_router.py     # Stage→model resolution
│   │       │   │   └── vba_utils.py        # VBA parsing helpers
│   │       │   ├── runners/
│   │       │   │   ├── main.py             # CLI: --item / --all / --all-forms / --dry-run
│   │       │   │   ├── run_bd_agent.py     # Run BD only
│   │       │   │   ├── run_dd_agent.py     # Run DD only
│   │       │   │   └── push_to_mongo.py    # Push BD/DD output → MongoDB bds/dds collections
│   │       │   ├── schema/                 # JSON schemas + sample templates
│   │       │   ├── pipeline.py             # LangGraph graph: BD node → DD node → END
│   │       │   ├── state.py                # PipelineState TypedDict definition
│   │       │   └── config.py               # Layer2 config: stage, model routing, paths
│   │       │
│   │       ├── layer3/             # ── Layer 3: SQL Migration ──────────────────
│   │       │   └── sql_migration/
│   │       │       ├── router.py               # API: list/get/update/convert query + table
│   │       │       ├── table_converter.py      # Access DDL → PostgreSQL/Oracle DDL
│   │       │       ├── postgres_migrator.py    # LLM-assisted full migration runner
│   │       │       └── seed_queries_v2.py      # Seed Access queries (raw_sql) → MongoDB
│   │       │
│   │       ├── layer4/             # ── Layer 4: Excel Export ───────────────────
│   │       │   ├── server.py                   # Layer4 functions (gen_bd/gen_dd/download)
│   │       │   ├── scripts/
│   │       │   │   ├── excel_translator.py     # JP→EN cell value translation + sheet rename
│   │       │   │   ├── fill_bd_excel.py        # BD Screen template filler
│   │       │   │   ├── fill_bd_report_excel.py # BD Report template filler
│   │       │   │   ├── fill_dd_excel_frm.py    # DD Form template filler
│   │       │   │   ├── fill_dd_excel_macro.py  # DD Macro template filler
│   │       │   │   ├── fill_dd_excel_module.py # DD Module template filler
│   │       │   │   └── fill_dd_excel_report.py # DD Report template filler
│   │       │   └── template/                   # Excel .xlsx base templates
│   │       │       ├── BD_Screen/bd_template.xlsx
│   │       │       ├── BD_Report/bd_report_template.xlsx
│   │       │       └── DD_Screen/ + DD_Report/
│   │       │
│   │       └── layer5/             # ── Layer 5: Code Generation ────────────────
│   │           ├── agents/
│   │           │   ├── graphview/      # WPF mapping graph (Access→.NET name mapping)
│   │           │   ├── logic/          # Business logic analyzer from DD steps
│   │           │   ├── mapping/        # Access form → WPF View/ViewModel name mapper
│   │           │   ├── repo/           # Repository pattern code generator
│   │           │   ├── service/        # C# Service class generator
│   │           │   └── ui/             # XAML View + ViewModel generator
│   │           ├── codegen/
│   │           │   ├── jinja_engine.py     # Jinja2 template renderer
│   │           │   └── templates/          # C# / XAML Jinja2 templates
│   │           ├── core/
│   │           │   ├── config.py           # Layer5 config: model routing, paths, collections
│   │           │   └── models.py           # Domain models for codegen
│   │           └── pipeline/
│   │               ├── orchestrator.py     # Full gen pipeline: analyze→gen→deploy→verify
│   │               ├── deploy_to_source.py # Copy generated files → correct WPF project dirs
│   │               ├── build_verify.py     # dotnet build + AI auto-fix (max 3 iterations)
│   │               └── file_writer.py      # Safe file write with backup
│   │
│   ├── frontend/                   # Next.js 15 Web Console
│   │   └── src/
│   │       ├── app/
│   │       │   ├── api/
│   │       │   │   ├── graph/              # VBA dependency graph builder (graphBuilder.ts)
│   │       │   │   ├── graph-wpf/          # WPF graph: mapping, validation, source-review
│   │       │   │   └── v1/layer5/          # Layer5 run-agent / run-logic API endpoints
│   │       │   └── (pages)/                # Dashboard pages: layer1→5, graph, graph-wpf
│   │       └── components/
│   │           ├── GraphView.tsx           # React Flow canvas for dependency graph
│   │           ├── Header.tsx / Footer.tsx
│   │           └── nodes/                  # Custom React Flow node components
│   │
│   ├── vba/
│   │   └── vba_source/             # VBA source exports (Tables/AllColumns.csv, ...)
│   │
│   └── wpf/                        # Generated/target Avalonia WPF solution
│       ├── vba_brain.Application/
│       ├── vba_brain.Domain/
│       ├── vba_brain.Infrastructure/
│       └── vba_brain.UI.Avalonia/
│
├── data/                           # ⚠ GITIGNORED — raw Access exports & DB backups
│   ├── forms/ reports/ modules/ queries/ macros/ tables/ graphs/
│   └── reference_map.json          # Cross-reference mapping hints
│
├── infa/
│   ├── docker-compose.yml          # MongoDB 7 + Qdrant + Oracle XE (dev + test)
│   └── mongo-init/01_init_user.js  # MongoDB init script
│
└── docs/                           # Additional documentation
```

---

## 🛠️ Tech Stack

### Backend

| Component | Technology | Version |
|-----------|----------|---------|
| Language | Python | 3.9 – 3.13 |
| API Gateway | gRPC (`grpcio`) | ≥ 1.62 |
| AI Orchestration | LangGraph + LangChain | ≥ 0.2 |
| Database Client | PyMongo | ≥ 4.8 |
| PostgreSQL Driver | psycopg2-binary | ≥ 2.9 |
| Excel Processing | openpyxl | ≥ 3.1 |
| Template Engine | Jinja2 | ≥ 3.1 |
| HTTP / Async | FastAPI + uvicorn | ≥ 0.111 |
| Env Loader | python-dotenv | ≥ 1.0 |

### Frontend

| Component | Technology | Version |
|-----------|----------|---------|
| Framework | Next.js | 15 |
| Styling | TailwindCSS | 3.x |
| Graph Canvas | React Flow (`@xyflow/react`) | latest |
| Icons | Lucide React | latest |
| Animations | Framer Motion | latest |
| Package Manager | Yarn | 1.x |

### Infrastructure

| Service | Image | Port | Used for |
|---------|-------|------|---------|
| MongoDB | `mongo:7.0` | 27017 | Document store (L1/L2 state) |
| Mongo Express | `mongo-express:1.0.2` | 8082 | DB Web UI |
| Qdrant | `qdrant/qdrant:latest` | 6333 / 6334 | Vector embeddings |
| Oracle Dev | `gvenzl/oracle-free:23-slim` | 1522 | Target dev DB |
| Oracle Test | `gvenzl/oracle-free:23-slim` | 1523 | Target test DB |

### Target Platform

| Component | Technology |
|-----------|----------|
| Desktop App | Avalonia UI |
| Runtime | .NET 10 |
| ORM | Dapper (PostgreSQL) |
| Architecture | MVVM — Domain / Application / Infrastructure |

---

## 🔬 Detailed Layers

### Layer 1 — AST Extraction & Parsing

**Entry Point**: `src/backend/workflow/layer1/run_all.py`  
**Input**: JSON files exported from MS Access (placed in `data/`)  
**Output**: MongoDB collections (L1)

#### Parsers

| File | Input data | MongoDB collection | Main Content |
|------|-----------|-------------------|----------------|
| `frm_parser.py` | `data/forms/*.json` | `forms` | Controls, events, VBA procedures, form properties |
| `frm_parser.py` | `data/reports/*.json` | `reports` | Report sections, fields, embedded queries |
| `query_parser.py` | `data/queries/*.json` | `queries_v2` | SQL text, parameters, join type, raw_sql |
| `macro_parser.py` | `data/macros/*.json` | `macros` | Action sequences, conditions, arguments |
| `modules_parser.py` | `data/modules/*.json` | `modules` | Public subs/functions, constants, Declare |
| `table_parser.py` | `data/tables/*.json` | `tables` | Columns, data types, PK/FK, indexes |

#### Aggregator (`aggregator.py`)

After parsing, `aggregator.py` enriches each form/report with:
- **DoCmd references**: `OpenForm`, `OpenReport`, `OpenQuery`, `RunMacro`, `OutputTo`
- **DLookup/DCount/DSum**: resolve name of tables/queries referenced
- **Cross-form calls**: `Form_X.Proc()`, `[Forms]![FormName]`
- **Module procedure calls**: `Module.Procedure()` from standard modules
- **CallSub / Application.Run**: explicit sub calls

Results are written to `data/graphs/` and seeded into the `dependency_graph` collection.

---

## 🏗️ Layer 2 — AI Design Specification

**Entry Point**: `src/backend/workflow/layer2/runners/main.py`  
**Orchestration**: LangGraph `StateGraph` (BD node → DD node → END)  
**State**: `PipelineState` TypedDict

#### BD Flow (Business Design) — Forms & Reports only

```
bd1_extract  →  bd2_map  →  bd3_logic  →  bd4_final
   │              │             │            │
   ▼              ▼             ▼            ▼
 Extract       Map VBA      Analyze      Produce
 screens &    events &     business     BD JSON
 controls    UI elements    logic       (persist)
```

Result: `layer2/output/bd_flow/bd4_bd_final/<name>.json`  
*Completely skipped for type = `module` / `macro`*

#### DD Flow (Detailed Design) — All types

```
dd1_skeleton  →  dd2_sql_map  →  dd3_llm_enrich  →  dd4_final
    │               │                │                │
    ▼               ▼                ▼                ▼
 Build DD       Map SQL          LLM fills         Produce
 skeleton       queries →        steps, logic,     DD JSON
 from BD        sheet4/5         pseudo-code       (persist)
```

Result:
- `layer2/output/dd_flow/screen/dd4_dd_final/<name>.json`
- `layer2/output/dd_flow/macro/dd4_dd_final/<name>.json`
- `layer2/output/dd_flow/common/dd4_dd_final/<name>.json`

#### Cost Tracking

Each LLM call execution is recorded in the `CostTracker` singleton:

```python
# Token pricing (per 1M tokens, USD)
qwen-max:   $2.80 input / $8.40 output
qwen-plus:  $0.56 input / $1.68 output
gpt-4o:     $2.50 input / $10.0 output
```

The report is saved after each run:
- `layer2/output/token_reports/<name>_<timestamp>.json`
- `excel_outputs/<name>_cost.xlsx`

#### CLI Usage

```bash
cd src/backend/workflow/layer2/runners

# Process a specific item
python main.py --item F_Login --type form --stage dev

# Process all forms
python main.py --all-forms --stage dev

# Process all (forms + reports + modules)
python main.py --all --stage production

# Dry run — list items without running LLM
python main.py --all --dry-run
```

**Stage** determines which model is used:

| Stage | Model (default) | Used for |
|-------|-----------------|---------|
| `dev` | `qwen-max` | Development, quick testing |
| `pilot` | `qwen-max` | UAT, quality review |
| `production` | `qwen3-coder-480b` (critical/high) / `qwen-max` (medium) / `qwen3-coder-next` (low) | Generating full docs |

---

## ⚙️ Layer 3 — SQL Migration

**Input**: MongoDB collection `queries_v2` + `tables`  
**Output**: PostgreSQL DDL SQL

#### Modules

| File | Function |
|------|----------|
| `table_converter.py` | Convert Access data types → PostgreSQL DDL |
| `postgres_migrator.py` | LLM-assisted runner: read each table → generate CREATE TABLE → execute |
| `seed_queries_v2.py` | Seed queries (with both `raw_sql` and `sql` fields) into MongoDB |
| `router.py` | API endpoints: list/get/update/convert query, convert table schema, get stats |

#### Workflow

```
MongoDB (queries_v2 / tables)
         │
         ▼
  table_converter.py        → Access DDL → PostgreSQL DDL
  postgres_migrator.py      → Execute DDL on target PostgreSQL
  router.py::convert_query  → LLM translates Access SQL → target SQL dialect
```

---

## 📊 Layer 4 — Excel Specification Export

**Input**: BD/DD JSON (from `layer2/output/` or MongoDB `bds`/`dds`)  
**Output**: `.xlsx` files at `src/excel_outputs/`

#### Template Types

| Template | File | Used for |
|---------|------|---------|
| BD Screen | `BD_Screen/bd_template.xlsx` | Forms — Business Design |
| BD Report | `BD_Report/bd_report_template.xlsx` | Reports — Business Design |
| DD Screen | `DD_Screen/dd_template.xlsx` | Forms — Detailed Design |
| DD Report | `DD_Report/dd_report_template.xlsx` | Reports — Detailed Design |
| DD Macro | `DD_Screen/dd_template_macro.xlsx` | Macros — Detailed Design |
| DD Module | `DD_Screen/dd_template_module.xlsx` | Modules — Detailed Design |

#### Translation Engine (`excel_translator.py`)

When `config.json → localization.target_language = "en"`:
- Translate all cell values from Japanese → English using the `JP_EN_MAPPING` dictionary
- Translate sheet names (e.g. `変更履歴` → `Change History`)
- After export, Japanese sheet names can be restored using `restore_japanese_sheet_names()`

---

## 💻 Layer 5 — Automated Code Generation

**Input**: DD JSON + Access→WPF name mapping  
**Output**: C# source files (Avalonia/WPF architecture)

#### Generated File Types

| Agent | Output | Place into WPF project |
|-------|--------|---------------------|
| `ui` (View) | `Views/F_Login.axaml` | `vba_brain.UI.Avalonia/Views/` |
| `ui` (ViewModel) | `ViewModels/F_LoginViewModel.cs` | `vba_brain.UI.Avalonia/ViewModels/` |
| `service` | `Application/Services/LoginService.cs` | `vba_brain.Application/` |
| `repo` | `Infrastructure/Repositories/LoginRepository.cs` | `vba_brain.Infrastructure/` |
| `repo` (interface) | `Domain/Interfaces/ILoginRepository.cs` | `vba_brain.Domain/` |
| `entity` | `Domain/Entities/User.cs` | `vba_brain.Domain/` |

#### Model Routing (Layer 5)

```python
L5_ROUTING = {
    "service":    qwen3-coder-480b   # Complex business logic
    "viewmodel":  qwen-plus-2025     # MVVM commands, event flow
    "repository": qwen3-coder-480b   # SQL → Dapper code
    "view_xaml":  qwen-plus-2025     # BD layout → XAML
    "validator":  qwen-plus-2025     # Business rules → FluentValidation
    "entity":     qwen-plus-2025     # Data models
    "dto":        qwen-plus-2025     # DTOs
    "mapper":     qwen-plus-2025     # AutoMapper profiles
}
```

#### Build Verify Loop

`build_verify.py` performs:
1. `dotnet build` → parse compiler errors
2. If there are errors → send errors + source code → LLM → receive patch → apply
3. Loop up to 3 times (`MAX_RETRIES = 3`)

---

## 🗄️ MongoDB Collections

| Collection | Layer | Content |
|-----------|-------|---------|
| `forms` | L1 | Form metadata, controls, VBA procedures, references |
| `reports` | L1 | Report metadata, sections, fields |
| `queries_v2` | L1 | Access query definitions (SQL, params, raw_sql) |
| `modules` | L1 | VBA standard modules (procedures, functions) |
| `macros` | L1 | Macro action sequences |
| `tables` | L1 | Table schemas (columns, types, constraints) |
| `dependency_graph` | L1 | Cross-form reference graph |
| `bds` | L2 | Business Design JSON documents |
| `dds` | L2 | Detailed Design JSON documents |
| `agent_repo` | L5 | Generated code artifacts registry |
| `migration_queries` | L3 | SQL migration status (Access→target) |

---

## 🔌 gRPC API Gateway

**Port**: `50051` | **Entry**: `src/backend/api_gateway/grpc_server.py`

### Layer1Service

| Method | Request | Description |
|--------|---------|--------|
| `ListForms` | `EmptyRequest` | List of all forms from MongoDB |
| `ListQueries` | `EmptyRequest` | List of queries |
| `ListAllItems` | `EmptyRequest` | Forms + Reports + Modules + Macros |
| `GetDbQuery` | `screen_name, item_type, deep` | Get raw JSON for 1 item |

### Layer2Service

| Method | Request | Description |
|--------|---------|--------|
| `GetConfig` | `EmptyRequest` | LLM providers + available models |
| `GetModelsHealth` | `EmptyRequest` | Ping test all models (parallel) |
| `GetBdStatus` | `screen_name` | Check if BD/DD has been generated |
| `RunBdFlowFull` | `screen_name, model, force` | Run BD full flow (bd1→bd4) |
| `RunBdFlowExtract` | `screen_name` | Only run bd1_extract |
| `RunBdFlowAnalysis` | `screen_name, model, force` | Extract + Analysis phases |
| `RunDdFlowFull` | `screen_name, model, force` | Run DD full flow (dd1→dd4) |
| `GetTokenReport` | `EmptyRequest` | Get current token usage report |

### Layer3Service (Excel Gen)

| Method | Request | Description |
|--------|---------|--------|
| `ListItems` | `EmptyRequest` | All items that can generate Excel |
| `ListOutputs` | `EmptyRequest` | List of generated Excel files |
| `GenBd` | `screen_name, type` | Generate BD Excel |
| `GenDd` | `screen_name, type` | Generate DD Excel |
| `GenAll` | `screen_name, type` | Generate BD + DD Excel |
| `DownloadExcel` | `doc_kind, doc_type, filename` | Download file bytes |

### Layer4Service (SQL Migration)

| Method | Request | Description |
|--------|---------|--------|
| `ListMigrationQueries` | `EmptyRequest` | All Access queries that need migration |
| `GetMigrationQuery` | `name` | Details of 1 query (SQL + target_sql) |
| `UpdateMigrationQuery` | `name, target_sql, status, ...` | Save review result |
| `ConvertQuery` | `name, model` | LLM convert 1 query → target dialect |
| `SeedQueries` | `EmptyRequest` | Seed queries from MongoDB |
| `ListMigrationTables` | `EmptyRequest` | All tables that need migration |
| `ConvertTableSchema` | `table_name, target_db` | Convert DDL for 1 table |
| `GetStats` | `EmptyRequest` | Migration progress statistics |

---

## 🤖 LLM Model Routing

### Config Resolution Priority

```
1. Environment variable (e.g. ALIBABA_API_KEY)
         ↓
2. config.json → llm_providers.<provider>.api_key
         ↓
3. config.json → llm_settings.<layer>_model
         ↓
4. Hardcoded default (qwen-max)
```

### Model Override (Runtime)

```bash
# Override model for a specific layer
export MODEL_OVERRIDE_QWEN_MAX=qwen3-coder-480b-a35b-instruct

# Override model stage
export L2_STAGE=production
```

### Available Models

| Model ID | Provider | Context | Used for |
|----------|---------|---------|---------|
| `qwen3-max` | Alibaba | 262K | Best for complex tasks, most capable |
| `qwen3.5-plus` | Alibaba | 1M | Balanced performance, comparable to Qwen3-Max |
| `qwen-plus` | Alibaba | 1M | L5 ViewModel/XAML/Entity, medium tasks |
| `qwen-plus-latest` | Alibaba | 1M | L5 ViewModel/XAML/Entity (latest) |
| `qwen-plus-2025-12-01` | Alibaba | 1M | Stable snapshot |
| `qwen-plus-2025-07-28` | Alibaba | 1M | Legacy snapshot |
| `qwen3.5-flash` | Alibaba | 1M | Fast, cost-effective |
| `qwen-flash` | Alibaba | 1M | Simple tasks, fast |
| `qwen-turbo` | Alibaba | 1M | Fast inference, lower cost |
| `qwen-turbo-latest` | Alibaba | 1M | Fast inference (latest) |
| `qwen-max` | Alibaba | 128K | L2 dev/pilot, L3 migration |
| `qwen-max-latest` | Alibaba | 128K | L2 dev/pilot (latest) |
| `qwen-long-latest` | Alibaba | 10M | Long context documents |
| `qwq-plus` | Alibaba | 128K | Complex reasoning |
| `qwen3-coder-plus` | Alibaba | 1M | Code generation, Coding Agent |
| `qwen3-coder-flash` | Alibaba | 1M | Code generation, fast |
| `qwen3-coder-next` | Alibaba | 262K | L2 production complex (fallback) |
| `qwen3-coder-480b-a35b-instruct` | Alibaba | 262K | L5 Service/Repository, L2 production complex |
| `qwen3-coder-30b-a3b-instruct` | Alibaba | 262K | Code generation (30B) |
| `qwen3-235b-a22b` | Alibaba | 128K | L2 production medium |
| `qwen3-235b-a22b-thinking-2507` | Alibaba | 128K | Thinking mode only (July 2025) |
| `qwen3-235b-a22b-instruct-2507` | Alibaba | 128K | Non-thinking mode only (July 2025) |
| `qwen3-32b` | Alibaba | 128K | General purpose 32B |
| `qwen3-30b-a3b` | Alibaba | 128K | MoE 30B |
| `qwen3-14b` | Alibaba | 128K | General purpose 14B |
| `qwen3-8b` | Alibaba | 128K | General purpose 8B |
| `qwen3-4b` | Alibaba | 128K | Lightweight 4B |
| `qwen3-1.7b` | Alibaba | 32K | Ultra-lightweight 1.7B |
| `qwen3-0.6b` | Alibaba | 32K | Ultra-lightweight 0.6B |
| `qwen3-next-80b-a3b-thinking` | Alibaba | 128K | Thinking only (Sep 2025) |
| `qwen3-next-80b-a3b-instruct` | Alibaba | 128K | Non-thinking only (Sep 2025) |
| `qwen3-vl-plus` | Alibaba | 262K | Visual understanding (Plus) |
| `qwen3-vl-flash` | Alibaba | 262K | Visual understanding (Flash) |
| `qwen3-vl-235b-a22b-thinking` | Alibaba | 128K | Visual reasoning (235B thinking) |
| `qwen3-vl-235b-a22b-instruct` | Alibaba | 128K | Visual understanding (235B) |
| `qwen3-vl-32b-thinking` | Alibaba | 128K | Visual reasoning (32B) |
| `qwen3-vl-30b-a3b-thinking` | Alibaba | 128K | Visual reasoning (30B MoE) |
| `qwen3-vl-8b-thinking` | Alibaba | 128K | Visual reasoning (8B) |
| `qwen-vl-max` | Alibaba | 128K | Visual understanding (max) |
| `qwen-vl-plus` | Alibaba | 128K | Visual understanding (plus) |
| `qvq-max` | Alibaba | 128K | Visual reasoning |
| `qvq-plus` | Alibaba | 128K | Visual reasoning (plus) |
| `qwen-mt-plus` | Alibaba | 16K | Translation (92 languages) |
| `qwen-mt-flash` | Alibaba | 16K | Translation fast |
| `qwen-math-plus` | Alibaba | 4K | Mathematical reasoning |
| `qwen-math-turbo` | Alibaba | 4K | Math fast |
| `qwen2.5-72b-instruct` | Alibaba | 128K | Open-source 72B |
| `qwen2.5-32b-instruct` | Alibaba | 128K | Open-source 32B |
| `qwen2.5-14b-instruct` | Alibaba | 128K | Open-source 14B |
| `qwen2.5-7b-instruct` | Alibaba | 128K | Open-source 7B |
| `qwen2.5-vl-72b-instruct` | Alibaba | 128K | Open-source VL 72B |
| `qwen2.5-coder-32b-instruct` | Alibaba | 128K | Open-source coder 32B |
| `qwen2.5-coder-7b-instruct` | Alibaba | 128K | Open-source coder 7B |

### Handling Quota Exhaustion & Fallback Models

When a model's free tier quota is exhausted (HTTP 403 `AllocationQuota.FreeTierOnly`), Layer 2 automatically falls back to alternative models:

**Fallback Chain** (Layer 2):
```
qwen3-coder-480b-a35b-instruct → qwen-max → qwen-plus-2025-07-28
qwen3-235b-a22b-instruct-2507  → qwen-max → qwen-plus-2025-07-28
qwen-max                        → qwen-plus-2025-07-28 → qwen3-coder-480b
qwen-plus-2025-07-28            → qwen-max
```

**Usage**:
```python
from layer2.utils.llm_client import LLMClient
from layer2.config import DEV_MODEL

client = LLMClient()
# Automatically tries DEV_MODEL, then fallback models if quota exhausted
text, usage = client.call_with_fallback(DEV_MODEL, system_prompt, user_prompt)
```

**To resolve quota issues**:

1. **Upgrade Alibaba Account** (recommended for production):
   - Visit [Alibaba Cloud Console](https://dashscope.console.aliyun.com/)
   - Disable "Use free tier only" mode
   - Add payment method

2. **Use Alternative API Keys**:
   - Update `config.json → llm_providers.alibaba.api_key` with a new key
   - Or add OpenAI/Anthropic keys to `llm_providers`

3. **Wait for Free Tier Reset**:
   - Alibaba free tier typically resets monthly
   - Check console for reset date

4. **Monitor Token Usage**:
   - Layer 2 generates token reports: `layer2/output/token_reports/<name>_<timestamp>.json`
   - Check `excel_outputs/<name>_cost.xlsx` for cost breakdown

---

## ⚡ Installation & Setup

### Prerequisites

| Tool | Version | Notes |
|------|---------|---------|
| Python | ≥ 3.9 | Recommended 3.11+ |
| Node.js | ≥ 18 | Required for Frontend |
| Yarn | 1.x | `npm install -g yarn` |
| Docker Desktop | latest | For MongoDB + Qdrant + PostgreSQL |
| .NET SDK | 10 | Only required if using Layer 5 / WPF |

### Step 1: Clone & Dependencies

```bash
git clone <repo-url>
cd workflow

# Python backend
pip install -r src/backend/requirements.txt

# Node.js frontend
cd src/frontend
yarn install
cd ../..
```

### Step 2: Config

```bash
# Copy template
cp config.example.json config.json

# Open and fill in real values
nano config.json  # or your preferred editor
```

Required fields:
- `llm_providers.alibaba.api_key` — Alibaba Cloud API key
- `mongodb.uri` — MongoDB connection string
- `postgres_db.connection_string` — PostgreSQL connection string

> ⚠️ **NEVER commit `config.json`**. This file is already in `.gitignore`.

### Step 3: Start Infrastructure

```bash
cd infa

# Start MongoDB + Qdrant + PostgreSQL (background)
docker compose up -d

# Only start MongoDB (minimal)
docker compose up -d mongo

# Check
docker compose ps
```

| Service | URL | Credentials |
|---------|-----|------------|
| MongoDB | `localhost:27017` | `vba_brain` / `vba_brain2024` |
| Mongo Express UI | `http://localhost:8082` | `admin` / `admin123` |
| PostgreSQL | `localhost:5432` | `vba_brain` / `vba_brain2024` — DB: `vba_brain` |

---

## 🚀 Running the System

### Web Console (Frontend + Backend)

```bash
# Run both FE (port 3000) + BE gRPC (port 50051)
python start.py

# Frontend only
python start.py --fe-only

# Backend gRPC only
python start.py --be-only

# Clean Next.js cache (when encountering Turbopack/memory errors)
python start.py --clean
```

Access: **http://localhost:3000**

### Pipeline Batch CLI

```bash
cd src/backend/workflow/layer1

# Full pipeline: parse → seed → Layer 2 BD/DD → Layer 3 PostgreSQL migrate
python run_all.py
```

**Execution Order** (defined by `SCRIPTS` in `run_all.py`):

| # | Script | Description |
|---|--------|--------|
| 1 | `parser/frm_parser.py` | Parse Forms |
| 2 | `parser/frm_parser.py --reports` | Parse Reports |
| 3 | `parser/query_parser.py` | Parse Queries |
| 4 | `parser/macro_parser.py` | Parse Macros |
| 5 | `parser/modules_parser.py` | Parse Modules |
| 6 | `aggregator.py` | Aggregate cross-references |
| 7 | `seed_db.py` | Seed all data → MongoDB |
| 8 | `layer2/runners/main.py --all --stage dev` | Generate BD & DD |
| 9 | `layer3/sql_migration/postgres_migrator.py` | Migrate → PostgreSQL |

### Layer 2 Standalone

```bash
cd src/backend/workflow/layer2/runners

# 1 specific form
python main.py --item F_Login --type form --stage dev

# All forms with a stronger model
python main.py --all-forms --stage production

# Check which items will be processed (no LLM run)
python main.py --all --dry-run
```

### WPF Application

```bash
# Build Debug + Run
python start_wpf.py

# Build only (do not run)
python start_wpf.py --build-only

# Run using old build
python start_wpf.py --run-only

# Build Release mode
python start_wpf.py --release

# Clean + Build
python start_wpf.py --clean
```

---

## 📊 Web Console Dashboard

| Page | Path | Description |
|------|------|--------|
| Landing | `/` | Pipeline overview + animations |
| Layer 1 | `/layer1` | Browse parsed forms/reports/queries |
| Layer 2 | `/layer2` | Run BD/DD agents, view JSON output, token stats |
| Layer 3 | `/layer3` | Review & convert SQL queries (Access → PostgreSQL) |
| Layer 4 | `/layer4` | Generate & download Excel BD/DD specification files |
| Layer 5 | `/layer5` | Code gen: run agent, view generated files, WPF graph |
| VBA Graph | `/graph` | Interactive dependency graph (React Flow) |
| WPF Graph | `/graph-wpf` | Access→WPF mapping graph + source review |

---

## 📦 Output & Artifacts

| Artifact | Path | Format | Notes |
|---------|-----------|--------|---------|
| BD JSON | `layer2/output/bd_flow/bd4_bd_final/<name>.json` | JSON | Business Design |
| DD JSON | `layer2/output/dd_flow/{screen\|macro\|common}/dd4_dd_final/<name>.json` | JSON | Detailed Design |
| BD Excel | `src/excel_outputs/BD/<name>.xlsx` | XLSX | BD specification |
| DD Excel | `src/excel_outputs/DD/<name>.xlsx` | XLSX | DD specification |
| Token Report JSON | `layer2/output/token_reports/<name>_<ts>.json` | JSON | Cost per run |
| Token Report Excel | `src/excel_outputs/<name>_cost.xlsx` | XLSX | Cost per run |
| Generated C# | `layer5/output/` | `.cs` / `.axaml` | WPF source |
| Dependency Graph | `data/graphs/<name>.json` | JSON | Cross-reference graph |

---

## 🌐 Environment Variables

Variables that can be set in `.env` or shell environment, overriding config.json:

| Variable | Description | Default |
|----------|--------|---------|
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGO_DB` | MongoDB database name | `vba_brain_core` |
| `ALIBABA_API_KEY` | Alibaba Cloud API key | from `config.json` |
| `OPENAI_API_KEY` | OpenAI API key | from `config.json` |
| `ANTHROPIC_API_KEY` | Anthropic API key | from `config.json` |
| `GROQ_API_KEY` | Groq API key | from `config.json` |
| `L2_STAGE` | Layer 2 model stage | `dev` |
| `POSTGRES_CONN` | PostgreSQL ADO.NET connection string | from `config.json` |
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | PostgreSQL database name | `vba_brain` |
| `POSTGRES_USER` | PostgreSQL username | `vba_brain` |
| `POSTGRES_PASSWORD` | PostgreSQL password | from `config.json` |
| `LAYER5_SERVICE_MODEL` | Override L5 service model | from `config.json` |
| `LAYER5_REPOSITORY_MODEL` | Override L5 repo model | from `config.json` |
| `SOURCE_LANGUAGE` | Source language code | `ja` |
| `TARGET_LANGUAGE` | Target language code | `en` |
| `L2_HUMAN_REVIEW` | Enable interactive review | `0` |

---

## 🔒 Security

> **Important**: This project handles credentials and secrets. Strictly comply with the following rules:

- ✅ `config.example.json` — placeholder template file, **commit normally**
- ❌ `config.json` — contains real API keys, **NEVER commit** (already in `.gitignore`)
- ❌ `.env`, `.env.*` — **NEVER commit**
- ❌ `appsettings.json` — .NET configuration with DB password, **NEVER commit**

**If a key is leaked**:
1. Rotate the key immediately on Alibaba Cloud Console / OpenAI / Anthropic
2. Check git history: `git log --all -S "sk-"` to find the commit containing the key
3. If pushed to remote: use `git-filter-repo` to erase it from history

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file.
