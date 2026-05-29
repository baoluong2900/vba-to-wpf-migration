# vba_brain — VBA & Access Modernization Pipeline

[![Python](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/next.js-v15-black?logo=next.js)](https://nextjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![gRPC](https://img.shields.io/badge/gRPC-50051-244c5a?logo=grpc)](https://grpc.io/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-blueviolet)](https://github.com/langchain-ai/langgraph)
[![Avalonia](https://img.shields.io/badge/Avalonia-UI-.NET10-purple)](https://avaloniaui.net/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**vba_brain** là pipeline AI 5 lớp (layer) enterprise-grade để hiện đại hoá toàn bộ codebase MS Access (`.accdb` / `.mdb`) + VBA — từ việc phân tích AST, sinh tài liệu thiết kế, dịch SQL sang database hiện đại, xuất Excel specs, cho đến tự động sinh C#/Avalonia source code sẵn sàng build.

---

## 📋 Mục Lục

- [Kiến trúc tổng quan](#-kiến-trúc-tổng-quan)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Tech Stack](#-tech-stack)
- [Chi tiết từng Layer](#-chi-tiết-từng-layer)
- [MongoDB Collections](#-mongodb-collections)
- [gRPC API Gateway](#-grpc-api-gateway)
- [LLM Model Routing](#-llm-model-routing)
- [Cài đặt & Setup](#-cài-đặt--setup)
- [Chạy hệ thống](#-chạy-hệ-thống)
- [Web Console Dashboard](#-web-console-dashboard)
- [Output & Artifacts](#-output--artifacts)
- [Environment Variables](#-environment-variables)
- [Bảo mật](#-bảo-mật)

---

## 🏗️ Kiến Trúc Tổng Quan

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
  ║  (Python)    ║  BDService (s1→s4)  +  DDService (d1→d4)
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

## 📁 Cấu Trúc Thư Mục

```
workflow/
├── start.py                        # Launcher: FE (Next.js :3000) + BE (gRPC :50051)
├── start_wpf.py                    # Launcher: Avalonia WPF app (dotnet build + run)
├── config.json                     # ⚠ GITIGNORED — local secrets (API keys, passwords)
├── config.example.json             # ✅ Template an toàn để copy
│
├── src/
│   ├── backend/
│   │   ├── requirements.txt        # Python dependencies
│   │   ├── common/
│   │   │   └── config.py           # Singleton config: đọc config.json + .env, export constants
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
│   │       │   └── run_all.py              # CLI batch: Layer1 parse→seed→L2→L3
│   │       │
│   │       ├── layer2/             # ── Layer 2: AI Design Generation ──────────
│   │       │   ├── agents/
│   │       │   │   ├── bd_agent/
│   │       │   │   │   ├── bd_service.py       # BDService: orchestrates BD flow
│   │       │   │   │   └── core/               # s1_extract → s2_map → s3_logic → s4_final
│   │       │   │   └── dd_agent/
│   │       │   │       ├── dd_service.py       # DDService: orchestrates DD flow
│   │       │   │       └── core/               # d1_skeleton → d2_sql → d3_llm → d4_final
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

| Thành phần | Công nghệ | Version |
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

| Thành phần | Công nghệ | Version |
|-----------|----------|---------|
| Framework | Next.js | 15 |
| Styling | TailwindCSS | 3.x |
| Graph Canvas | React Flow (`@xyflow/react`) | latest |
| Icons | Lucide React | latest |
| Animations | Framer Motion | latest |
| Package Manager | Yarn | 1.x |

### Infrastructure

| Service | Image | Port | Dùng cho |
|---------|-------|------|---------|
| MongoDB | `mongo:7.0` | 27017 | Document store (L1/L2 state) |
| Mongo Express | `mongo-express:1.0.2` | 8082 | DB Web UI |
| Qdrant | `qdrant/qdrant:latest` | 6333 / 6334 | Vector embeddings |
| Oracle Dev | `gvenzl/oracle-free:23-slim` | 1522 | Target dev DB |
| Oracle Test | `gvenzl/oracle-free:23-slim` | 1523 | Target test DB |

### Target Platform

| Thành phần | Công nghệ |
|-----------|----------|
| Desktop App | Avalonia UI |
| Runtime | .NET 10 |
| ORM | Dapper (PostgreSQL) |
| Architecture | MVVM — Domain / Application / Infrastructure |

---

## 🔬 Chi Tiết Từng Layer

### Layer 1 — AST Extraction & Parsing

**Entry point**: `src/backend/workflow/layer1/run_all.py`  
**Input**: JSON files exported từ MS Access (đặt trong `data/`)  
**Output**: MongoDB collections (L1)

#### Parsers

| File | Input data | MongoDB collection | Nội dung chính |
|------|-----------|-------------------|----------------|
| `frm_parser.py` | `data/forms/*.json` | `forms` | Controls, events, VBA procedures, form properties |
| `frm_parser.py` | `data/reports/*.json` | `reports` | Report sections, fields, embedded queries |
| `query_parser.py` | `data/queries/*.json` | `queries_v2` | SQL text, parameters, join type, raw_sql |
| `macro_parser.py` | `data/macros/*.json` | `macros` | Action sequences, conditions, arguments |
| `modules_parser.py` | `data/modules/*.json` | `modules` | Public subs/functions, constants, Declare |
| `table_parser.py` | `data/tables/*.json` | `tables` | Columns, data types, PK/FK, indexes |

#### Aggregator (`aggregator.py`)

Sau khi parse, `aggregator.py` enrich mỗi form/report với:
- **DoCmd references**: `OpenForm`, `OpenReport`, `OpenQuery`, `RunMacro`, `OutputTo`
- **DLookup/DCount/DSum**: resolve tên bảng/query được tham chiếu
- **Cross-form calls**: `Form_X.Proc()`, `[Forms]![FormName]`
- **Module procedure calls**: `Module.Procedure()` từ standard modules
- **CallSub / Application.Run**: explicit sub calls

Kết quả được ghi vào `data/graphs/` và seeded vào collection `dependency_graph`.

---

## 🏗️ Layer 2 — AI Design Specification

**Entry point**: `src/backend/workflow/layer2/runners/main.py`  
**Orchestration**: LangGraph `StateGraph` (BD node → DD node → END)  
**State**: `PipelineState` TypedDict

#### BD Flow (Business Design) — Forms & Reports only

```
s1_extract  →  s2_map  →  s3_logic  →  s4_final
   │              │             │            │
   ▼              ▼             ▼            ▼
 Extract       Map VBA      Analyze      Produce
 screens &    events &     business     BD JSON
 controls    UI elements    logic       (persist)
```

Kết quả: `layer2/output/bd_flow/s4_bd_final/<name>.json`  
*Skip hoàn toàn cho type = `module` / `macro`*

#### DD Flow (Detailed Design) — All types

```
d1_skeleton  →  d2_sql_map  →  d3_llm_enrich  →  d4_final
    │               │                │                │
    ▼               ▼                ▼                ▼
 Build DD       Map SQL          LLM fills         Produce
 skeleton       queries →        steps, logic,     DD JSON
 from BD        sheet4/5         pseudo-code       (persist)
```

Kết quả:
- `layer2/output/dd_flow/screen/d4_dd_final/<name>.json`
- `layer2/output/dd_flow/macro/d4_dd_final/<name>.json`
- `layer2/output/dd_flow/common/d4_dd_final/<name>.json`

#### Cost Tracking

Mỗi lần chạy LLM call đều được ghi vào singleton `CostTracker`:

```python
# Token pricing (per 1M tokens, USD)
qwen-max:   $2.80 input / $8.40 output
qwen-plus:  $0.56 input / $1.68 output
gpt-4o:     $2.50 input / $10.0 output
```

Report được save sau mỗi run:
- `layer2/output/token_reports/<name>_<timestamp>.json`
- `excel_outputs/<name>_cost.xlsx`

#### CLI Usage

```bash
cd src/backend/workflow/layer2/runners

# Xử lý 1 item cụ thể
python main.py --item F_Login --type form --stage dev

# Xử lý tất cả forms
python main.py --all-forms --stage dev

# Xử lý tất cả (forms + reports + modules)
python main.py --all --stage production

# Dry run — liệt kê items không chạy LLM
python main.py --all --dry-run
```

**Stage** quyết định model nào được dùng:

| Stage | Model (mặc định) | Dùng khi |
|-------|-----------------|---------|
| `dev` | `qwen-max` | Development, test nhanh |
| `pilot` | `qwen-max` | UAT, review chất lượng |
| `production` | `qwen3-coder-480b` (critical/high) / `qwen-max` (medium) / `qwen3-coder-next` (low) | Sinh full docs |

---

## ⚙️ Layer 3 — SQL Migration

**Input**: MongoDB collection `queries_v2` + `tables`  
**Output**: PostgreSQL DDL SQL

#### Modules

| File | Chức năng |
|------|----------|
| `table_converter.py` | Chuyển Access data types → PostgreSQL DDL |
| `postgres_migrator.py` | LLM-assisted runner: đọc từng table → sinh CREATE TABLE → execute |
| `seed_queries_v2.py` | Seed queries (với cả `raw_sql` và `sql` field) vào MongoDB |
| `router.py` | API endpoints: list/get/update/convert query, convert table schema, get stats |

#### Workflow

```
MongoDB (queries_v2 / tables)
         │
         ▼
  table_converter.py        → Access DDL → PostgreSQL DDL
  postgres_migrator.py      → Execute DDL trên PostgreSQL target
  router.py::convert_query  → LLM dịch Access SQL → target SQL dialect
```

---

## 📊 Layer 4 — Excel Specification Export

**Input**: BD/DD JSON (từ `layer2/output/` hoặc MongoDB `bds`/`dds`)  
**Output**: `.xlsx` files tại `src/excel_outputs/`

#### Template Types

| Template | File | Dùng cho |
|---------|------|---------|
| BD Screen | `BD_Screen/bd_template.xlsx` | Forms — Business Design |
| BD Report | `BD_Report/bd_report_template.xlsx` | Reports — Business Design |
| DD Screen | `DD_Screen/dd_template.xlsx` | Forms — Detailed Design |
| DD Report | `DD_Report/dd_report_template.xlsx` | Reports — Detailed Design |
| DD Macro | `DD_Screen/dd_template_macro.xlsx` | Macros — Detailed Design |
| DD Module | `DD_Screen/dd_template_module.xlsx` | Modules — Detailed Design |

#### Translation Engine (`excel_translator.py`)

Khi `config.json → localization.target_language = "en"`:
- Dịch tất cả cell values từ Japanese → English theo dictionary `JP_EN_MAPPING`
- Dịch tên sheet (e.g. `変更履歴` → `Change History`)
- Sau export có thể khôi phục tên sheet JP bằng `restore_japanese_sheet_names()`

---

## 💻 Layer 5 — Automated Code Generation

**Input**: DD JSON + Access→WPF name mapping  
**Output**: C# source files (Avalonia/WPF architecture)

#### Generated File Types

| Agent | Output | Đặt vào WPF project |
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

`build_verify.py` thực hiện:
1. `dotnet build` → parse compiler errors
2. Nếu có error → gửi errors + source code → LLM → nhận patch → apply
3. Lặp tối đa **3 lần** (`MAX_RETRIES = 3`)

---

## 🗄️ MongoDB Collections

| Collection | Layer | Nội dung |
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

| Method | Request | Mô tả |
|--------|---------|--------|
| `ListForms` | `EmptyRequest` | Danh sách tất cả forms từ MongoDB |
| `ListQueries` | `EmptyRequest` | Danh sách queries |
| `ListAllItems` | `EmptyRequest` | Forms + Reports + Modules + Macros |
| `GetDbQuery` | `screen_name, item_type, deep` | Lấy raw JSON cho 1 item |

### Layer2Service

| Method | Request | Mô tả |
|--------|---------|--------|
| `GetConfig` | `EmptyRequest` | LLM providers + available models |
| `GetModelsHealth` | `EmptyRequest` | Ping test tất cả models (parallel) |
| `GetBdStatus` | `screen_name` | Kiểm tra BD/DD đã sinh chưa |
| `RunBdFlowFull` | `screen_name, model, force` | Chạy BD full flow (s1→s4) |
| `RunBdFlowExtract` | `screen_name` | Chỉ chạy s1_extract |
| `RunBdFlowAnalysis` | `screen_name, model, force` | Extract + Analysis phases |
| `RunDdFlowFull` | `screen_name, model, force` | Chạy DD full flow (d1→d4) |
| `GetTokenReport` | `EmptyRequest` | Lấy token usage report hiện tại |

### Layer3Service (Excel Gen)

| Method | Request | Mô tả |
|--------|---------|--------|
| `ListItems` | `EmptyRequest` | Tất cả items có thể generate Excel |
| `ListOutputs` | `EmptyRequest` | Danh sách file Excel đã generate |
| `GenBd` | `screen_name, type` | Generate BD Excel |
| `GenDd` | `screen_name, type` | Generate DD Excel |
| `GenAll` | `screen_name, type` | Generate BD + DD Excel |
| `DownloadExcel` | `doc_kind, doc_type, filename` | Download file bytes |

### Layer4Service (SQL Migration)

| Method | Request | Mô tả |
|--------|---------|--------|
| `ListMigrationQueries` | `EmptyRequest` | Tất cả Access queries cần migrate |
| `GetMigrationQuery` | `name` | Chi tiết 1 query (SQL + target_sql) |
| `UpdateMigrationQuery` | `name, target_sql, status, ...` | Lưu kết quả review |
| `ConvertQuery` | `name, model` | LLM convert 1 query → target dialect |
| `SeedQueries` | `EmptyRequest` | Seed queries từ MongoDB |
| `ListMigrationTables` | `EmptyRequest` | Tất cả tables cần migrate |
| `ConvertTableSchema` | `table_name, target_db` | Chuyển DDL cho 1 table |
| `GetStats` | `EmptyRequest` | Thống kê migration progress |

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
# Override model cho 1 layer cụ thể
export MODEL_OVERRIDE_QWEN_MAX=qwen3-coder-480b-a35b-instruct

# Override model stage
export L2_STAGE=production
```

### Available Models

| Model ID | Provider | Context | Dùng cho |
|----------|---------|---------|---------|
| `qwen3-coder-480b-a35b-instruct` | Alibaba | 262K | L5 Service/Repository, L2 production complex |
| `qwen3-235b-a22b-instruct-2507` | Alibaba | 262K | L2 production medium |
| `qwen-plus-2025-07-28` | Alibaba | 262K | L5 ViewModel/XAML/Entity |
| `qwen-max` | Alibaba | 128K | L2 dev/pilot, L3 migration |
| `qwen3-vl-235b-a22b-thinking` | Alibaba | 128K | Visual analysis |
| `qwen-vl-plus-latest` | Alibaba | - | Image understanding |
| `qvq-max-2025-03-25` | Alibaba | 128K | Complex reasoning |

---

## ⚡ Cài Đặt & Setup

### Prerequisites

| Tool | Version | Ghi chú |
|------|---------|---------|
| Python | ≥ 3.9 | Khuyến nghị 3.11+ |
| Node.js | ≥ 18 | Cần cho Frontend |
| Yarn | 1.x | `npm install -g yarn` |
| Docker Desktop | latest | Cho MongoDB + Qdrant + PostgreSQL |
| .NET SDK | 10 | Chỉ cần nếu dùng Layer 5 / WPF |

### Bước 1: Clone & Dependencies

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

### Bước 2: Config

```bash
# Copy template
cp config.example.json config.json

# Mở và điền thông tin thực
nano config.json  # hoặc editor của bạn
```

Các trường bắt buộc:
- `llm_providers.alibaba.api_key` — Alibaba Cloud API key
- `mongodb.uri` — MongoDB connection string
- `postgres_db.connection_string` — PostgreSQL connection string

> ⚠️ **KHÔNG bao giờ commit `config.json`**. File này đã trong `.gitignore`.

### Bước 3: Khởi động Infrastructure

```bash
cd infa

# Start MongoDB + Qdrant + PostgreSQL (background)
docker compose up -d

# Chỉ start MongoDB (tối thiểu)
docker compose up -d mongo

# Kiểm tra
docker compose ps
```

| Service | URL | Credentials |
|---------|-----|------------|
| MongoDB | `localhost:27017` | `vba_brain` / `vba_brain2024` |
| Mongo Express UI | `http://localhost:8082` | `admin` / `admin123` |
| PostgreSQL | `localhost:5432` | `vba_brain` / `vba_brain2024` — DB: `vba_brain` |

---

## 🚀 Chạy Hệ Thống

### Web Console (Frontend + Backend)

```bash
# Chạy cả FE (port 3000) + BE gRPC (port 50051)
python start.py

# Chỉ Frontend
python start.py --fe-only

# Chỉ Backend gRPC
python start.py --be-only

# Clean Next.js cache (khi gặp lỗi Turbopack/memory)
python start.py --clean
```

Truy cập: **http://localhost:3000**

### Pipeline Batch CLI

```bash
cd src/backend/workflow/layer1

# Full pipeline: parse → seed → Layer2 BD/DD → Layer3 PostgreSQL migrate
python run_all.py
```

**Thứ tự thực thi** (theo `SCRIPTS` trong `run_all.py`):

| # | Script | Mô tả |
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

# 1 form cụ thể
python main.py --item F_Login --type form --stage dev

# Tất cả forms với model mạnh hơn
python main.py --all-forms --stage production

# Xem sẽ xử lý những item nào (không chạy LLM)
python main.py --all --dry-run
```

### WPF Application

```bash
# Build Debug + Run
python start_wpf.py

# Chỉ Build (không run)
python start_wpf.py --build-only

# Run bằng build cũ
python start_wpf.py --run-only

# Build Release mode
python start_wpf.py --release

# Clean + Build
python start_wpf.py --clean
```

---

## 📊 Web Console Dashboard

| Page | Path | Mô tả |
|------|------|--------|
| Landing | `/` | Pipeline overview + animations |
| Layer 1 | `/layer1` | Browse forms/reports/queries đã parse |
| Layer 2 | `/layer2` | Run BD/DD agents, view JSON output, token stats |
| Layer 3 | `/layer3` | Review & convert SQL queries (Access → PostgreSQL) |
| Layer 4 | `/layer4` | Generate & download Excel BD/DD specification files |
| Layer 5 | `/layer5` | Code gen: run agent, view generated files, WPF graph |
| VBA Graph | `/graph` | Interactive dependency graph (React Flow) |
| WPF Graph | `/graph-wpf` | Access→WPF mapping graph + source review |

---

## 📦 Output & Artifacts

| Artifact | Đường dẫn | Format | Ghi chú |
|---------|-----------|--------|---------|
| BD JSON | `layer2/output/bd_flow/s4_bd_final/<name>.json` | JSON | Business Design |
| DD JSON | `layer2/output/dd_flow/{screen\|macro\|common}/d4_dd_final/<name>.json` | JSON | Detailed Design |
| BD Excel | `src/excel_outputs/BD/<name>.xlsx` | XLSX | BD specification |
| DD Excel | `src/excel_outputs/DD/<name>.xlsx` | XLSX | DD specification |
| Token Report JSON | `layer2/output/token_reports/<name>_<ts>.json` | JSON | Cost per run |
| Token Report Excel | `src/excel_outputs/<name>_cost.xlsx` | XLSX | Cost per run |
| Generated C# | `layer5/output/` | `.cs` / `.axaml` | WPF source |
| Dependency Graph | `data/graphs/<name>.json` | JSON | Cross-reference graph |

---

## 🌐 Environment Variables

Các biến có thể set trong `.env` hoặc shell environment, sẽ override `config.json`:

| Variable | Mô tả | Default |
|----------|--------|---------|
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGO_DB` | MongoDB database name | `vba_brain_core` |
| `ALIBABA_API_KEY` | Alibaba Cloud API key | từ `config.json` |
| `OPENAI_API_KEY` | OpenAI API key | từ `config.json` |
| `ANTHROPIC_API_KEY` | Anthropic API key | từ `config.json` |
| `GROQ_API_KEY` | Groq API key | từ `config.json` |
| `L2_STAGE` | Layer 2 model stage | `dev` |
| `POSTGRES_CONN` | PostgreSQL ADO.NET connection string | từ `config.json` |
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | PostgreSQL database name | `vba_brain` |
| `POSTGRES_USER` | PostgreSQL username | `vba_brain` |
| `POSTGRES_PASSWORD` | PostgreSQL password | từ `config.json` |
| `LAYER5_SERVICE_MODEL` | Override L5 service model | từ `config.json` |
| `LAYER5_REPOSITORY_MODEL` | Override L5 repo model | từ `config.json` |
| `SOURCE_LANGUAGE` | Source language code | `ja` |
| `TARGET_LANGUAGE` | Target language code | `en` |
| `L2_HUMAN_REVIEW` | Enable interactive review | `0` |

---

## 🔒 Bảo Mật

> **Quan trọng**: Project này xử lý credentials và secrets. Tuân thủ nghiêm ngặt các quy tắc sau:

- ✅ `config.example.json` — file template placeholder, **commit bình thường**
- ❌ `config.json` — chứa API keys thật, **KHÔNG BAO GIỜ commit** (đã trong `.gitignore`)
- ❌ `.env`, `.env.*` — **KHÔNG BAO GIỜ commit**
- ❌ `appsettings.json` — cấu hình .NET với DB password, **KHÔNG BAO GIỜ commit**

**Nếu key bị lộ**:
1. Rotate key ngay trên Alibaba Cloud Console / OpenAI / Anthropic
2. Kiểm tra git history: `git log --all -S "sk-"` để tìm commit có key
3. Nếu đã push lên remote: dùng `git-filter-repo` để xoá khỏi history

---

## 📄 License

MIT License — xem file [LICENSE](LICENSE).
