# vba_brain — VBA & Access Modernization Pipeline

[![Python](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue?logo=python)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/next.js-v15-black?logo=next.js)](https://nextjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green?logo=mongodb)](https://www.mongodb.com/)
[![gRPC](https://img.shields.io/badge/gRPC-API%20Gateway-orange?logo=grpc)](https://grpc.io/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agents-purple)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue)](https://opensource.org/licenses/MIT)

**vba_brain** là một pipeline AI 5 lớp (layer) dạng enterprise, được thiết kế để phân tích toàn bộ codebase MS Access (`.accdb` / `.mdb`) và VBA — sau đó tự động sinh ra:

- 📄 **Tài liệu thiết kế** BD (Business Design) & DD (Detailed Design) bằng tiếng Anh
- 🗄️ **Schema SQL** cho PostgreSQL / Oracle từ Access queries & tables
- 📊 **Excel Specification Sheets** (BD + DD) đã được dịch và format đẹp
- 💻 **Source code hiện đại** (Avalonia/WPF C# hoặc React/TypeScript)

---

## 🏗️ Kiến trúc Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     vba_brain 5-Layer Pipeline                           │
└─────────────────────────────────────────────────────────────────────────┘

  Legacy MS Access DB (.accdb)
          │
          ▼
  ┌───────────────┐   AST parse forms/reports/modules/queries/macros
  │   Layer 1     │──────────────────────────────────────────────────▶ MongoDB (L1)
  │  Extraction   │   frm_parser, query_parser, macro_parser, ...
  └───────────────┘
          │
          ▼
  ┌───────────────┐   LangGraph agents: BDService + DDService (parallel)
  │   Layer 2     │──────────────────────────────────────────────────▶ MongoDB (L2)
  │  AI Design    │   BD (Business Design) → DD (Detailed Design)
  └───────────────┘
          │
    ┌─────┴──────────────────────┐
    ▼                            ▼
  ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
  │   Layer 3     │     │   Layer 4     │     │   Layer 5     │
  │  SQL Migration│     │  Excel Export │     │  Code  Gen    │
  │  → PostgreSQL │     │  → .xlsx docs │     │  → C# / React │
  │  → Oracle     │     │               │     │               │
  └───────────────┘     └───────────────┘     └───────────────┘
```

---

## 📁 Cấu trúc thư mục

```
workflow/
├── src/
│   ├── backend/
│   │   ├── api_gateway/                   # Unified gRPC API Gateway
│   │   │   ├── grpc_server.py             # Entry point — gRPC server port 50051
│   │   │   ├── workflow_pb2.py            # Generated protobuf stubs
│   │   │   └── workflow_pb2_grpc.py       # Generated gRPC stubs
│   │   ├── common/
│   │   │   └── config.py                  # Shared config — đọc config.json & .env
│   │   ├── protos/
│   │   │   └── workflow.proto             # Protobuf service definitions
│   │   ├── requirements.txt               # Python dependencies
│   │   └── workflow/
│   │       ├── layer1/                    # Parser & Extractor
│   │       │   ├── parser/
│   │       │   │   ├── frm_parser.py      # Form / Report parser
│   │       │   │   ├── query_parser.py    # Query & SQL parser
│   │       │   │   ├── macro_parser.py    # Macro parser
│   │       │   │   ├── modules_parser.py  # VBA module parser
│   │       │   │   └── table_parser.py    # Table structure parser
│   │       │   ├── aggregator.py          # Reference enrichment (cross-form, DLookup, ...)
│   │       │   ├── seed_db.py             # Seed parsed data → MongoDB
│   │       │   └── run_all.py             # Full pipeline runner (Layer 1 → 3)
│   │       ├── layer2/                    # AI Design Specification Generator
│   │       │   ├── agents/
│   │       │   │   ├── bd_agent/          # Business Design agent
│   │       │   │   │   ├── bd_service.py  # BDService — orchestrates BD flow
│   │       │   │   │   └── core/          # s1→s4 stage processors
│   │       │   │   └── dd_agent/          # Detailed Design agent
│   │       │   │       ├── dd_service.py  # DDService — orchestrates DD flow
│   │       │   │       └── core/          # d1→d4 stage processors
│   │       │   ├── db/                    # MongoDB read/write helpers (Layer1Repo)
│   │       │   ├── utils/                 # LLM client, cost tracker, helpers
│   │       │   ├── schema/                # JSON schemas & templates
│   │       │   ├── runners/               # CLI runners (main.py --all)
│   │       │   ├── pipeline.py            # LangGraph BD→DD pipeline builder
│   │       │   └── state.py               # PipelineState definition
│   │       ├── layer3/                    # SQL & Database Migration
│   │       │   └── sql_migration/
│   │       │       ├── router.py          # Layer 3 API router (list/get/convert/update)
│   │       │       ├── table_converter.py # Access → target SQL DDL converter
│   │       │       ├── postgres_migrator.py # LLM-assisted PostgreSQL migration runner
│   │       │       └── seed_queries_v2.py # Seed Access queries → MongoDB
│   │       ├── layer4/                    # Excel Specification Exporter
│   │       │   ├── scripts/
│   │       │   │   ├── excel_translator.py        # JP → EN translation engine
│   │       │   │   ├── fill_bd_excel.py            # Fill BD Screen Excel template
│   │       │   │   ├── fill_bd_report_excel.py     # Fill BD Report Excel template
│   │       │   │   ├── fill_dd_excel_frm.py        # Fill DD Form template
│   │       │   │   ├── fill_dd_excel_macro.py      # Fill DD Macro template
│   │       │   │   ├── fill_dd_excel_module.py     # Fill DD Module template
│   │       │   │   └── fill_dd_excel_report.py     # Fill DD Report template
│   │       │   ├── template/                       # Excel .xlsx templates (BD/DD)
│   │       │   ├── inputs/                         # Input JSON data for generation
│   │       │   └── outputs/                        # Generated .xlsx output
│   │       └── layer5/                    # Automated Code Generation
│   │           ├── agents/
│   │           │   ├── graphview/         # WPF/Access graph mapping agent
│   │           │   ├── logic/             # Business logic analyzer
│   │           │   ├── mapping/           # Access→WPF name mapper
│   │           │   ├── repo/              # Repository pattern generator
│   │           │   ├── report/            # Report generator
│   │           │   ├── service/           # Service layer generator
│   │           │   └── ui/                # UI (View/ViewModel) generator
│   │           ├── codegen/
│   │           │   ├── jinja_engine.py    # Jinja2 template engine
│   │           │   └── templates/         # C# / XAML code templates
│   │           ├── core/
│   │           │   └── llm/               # LLM client wrappers
│   │           └── pipeline/
│   │               ├── orchestrator.py    # Full generation pipeline
│   │               ├── deploy_to_source.py# Copy generated files → WPF solution
│   │               └── build_verify.py    # dotnet build + AI fix loop
│   ├── frontend/                          # Next.js 15 Web Console
│   │   └── src/
│   │       ├── app/
│   │       │   ├── api/                   # API routes (proxy → gRPC backend)
│   │       │   │   ├── graph/             # VBA dependency graph builder
│   │       │   │   ├── graph-wpf/         # WPF mapping graph & validation
│   │       │   │   └── v1/layer5/         # Layer 5 run-agent / run-logic endpoints
│   │       │   └── (pages)/               # Layer 1–5 dashboard pages
│   │       └── components/                # Shared UI components (Header, Footer, GraphView, ...)
│   ├── vba/
│   │   └── vba_source/                    # Exported VBA source files & table schemas
│   └── wpf/                               # Generated/target WPF (Avalonia) solution
│       ├── vba_brain.Application/
│       ├── vba_brain.Domain/
│       ├── vba_brain.Infrastructure/
│       └── vba_brain.UI.Avalonia/
├── data/                                  # (gitignored) Raw Access exports & DB backups
├── infa/
│   ├── docker-compose.yml                 # MongoDB + Qdrant + Oracle containers
│   └── mongo-init/                        # MongoDB init scripts
├── docs/                                  # Additional documentation
├── start.py                               # 🚀 Web Console launcher (FE + BE)
├── start_wpf.py                           # 🖥️  WPF app launcher (dotnet build + run)
├── config.json                            # ⚙️  Config (gitignored — do NOT commit)
└── config.example.json                    # ⚙️  Config template (commit-safe)
```

---

## ⚙️ Layer Chi Tiết

### Layer 1 — AST Extraction & Parsing

Parse toàn bộ dữ liệu từ MS Access export files:

| Parser | Đầu vào | Đầu ra (MongoDB) |
|--------|---------|-----------------|
| `frm_parser.py` | Form/Report JSON export | Controls, events, VBA procedures |
| `query_parser.py` | Query definitions | SQL text, parameters, joins |
| `macro_parser.py` | Macro action sequences | Action list, conditions |
| `modules_parser.py` | VBA standard modules | Procedures, functions, constants |
| `table_parser.py` | Table schema | Columns, data types, constraints |
| `aggregator.py` | All above | Cross-reference enrichment (DoCmd calls, DLookup, form references) |

### Layer 2 — AI Business & Detailed Design

Sử dụng **LangGraph** để chạy song song hai agent:

- **BDService** (4 stages: s1 extraction → s2 mapping → s3 logic → s4 BD final)
  - Skip cho `module` và `macro` (chỉ có DD)
- **DDService** (4 stages: d1 skeleton → d2 SQL mapping → d3 LLM enrich → d4 DD final)
  - Áp dụng cho tất cả: form, report, module, macro

Output JSON được persist vào MongoDB và file system (`output/bd_flow/`, `output/dd_flow/`).

> **Cost tracking**: Mỗi lần chạy đều ghi lại token usage và chi phí USD vào report Excel/JSON.

### Layer 3 — SQL Migration

Chuyển đổi Access queries và table schemas sang SQL hiện đại:

- **`table_converter.py`** — DDL conversion (Access → PostgreSQL/Oracle data types)
- **`postgres_migrator.py`** — LLM-assisted migration runner, tích hợp với `run_all`
- **`seed_queries_v2.py`** — Seed Access queries (với `raw_sql`) vào MongoDB để review
- **`router.py`** — API: list/get/update/convert queries, per-table schema conversion

### Layer 4 — Excel Specification Export

Đọc BD/DD JSON → ghi vào template `.xlsx` bằng `openpyxl`:

- Hỗ trợ **dịch tự động JP → EN** (qua `excel_translator.py`)
- Tự động phục hồi tên sheet tiếng Nhật sau khi export (nếu yêu cầu)
- Template riêng cho: BD Screen, BD Report, DD Screen (Form/Module/Macro), DD Report

### Layer 5 — Automated Code Generation

Sinh source code C#/Avalonia từ DD specifications:

- **Graphview agent** — Map Access forms → WPF View/ViewModel names
- **Service agent** — Sinh C# Service classes
- **Repository agent** — Sinh Repository với PostgreSQL/Oracle queries
- **UI agent** — Sinh XAML views và ViewModel classes
- **`orchestrator.py`** — Full pipeline: analyze → generate → deploy → build → AI fix loop
- **`deploy_to_source.py`** — Copy generated files vào WPF solution đúng chỗ
- **`build_verify.py`** — `dotnet build` + AI auto-fix nếu có build errors (tối đa 3 lần)

---

## 🛠️ Tech Stack

| Layer | Công nghệ |
|-------|----------|
| Frontend | Next.js 15, TailwindCSS, React Flow, Lucide Icons |
| API Gateway | Python gRPC (port `50051`) |
| AI Orchestration | LangGraph, LangChain |
| LLM Providers | Alibaba Qwen, OpenAI, Anthropic, Groq, DeepSeek |
| Database | MongoDB 7.0 (state), Qdrant (vector search) |
| Target DB | PostgreSQL, Oracle XE 23ai |
| Excel Export | `openpyxl` |
| Code Templates | Jinja2 |
| WPF Target | .NET 10, Avalonia UI |
| Infrastructure | Docker Compose (MongoDB, Qdrant, Oracle dev + test) |

---

## ⚡ Cài Đặt & Chạy

### 📋 Yêu cầu

- Python **3.9+**
- Node.js **18+** (yarn hoặc npm)
- MongoDB **7.0** (local hoặc Docker)
- .NET **10 SDK** (nếu dùng Layer 5 / WPF)

### 1. Clone & cài dependencies

```bash
git clone <repo-url>
cd workflow

# Backend Python
pip install -r src/backend/requirements.txt

# Frontend Node.js
cd src/frontend
yarn install   # hoặc npm install
cd ../..
```

### 2. Cấu hình

Copy file template rồi điền thông tin thực:

```bash
cp config.example.json config.json
```

Chỉnh sửa `config.json`:

```jsonc
{
  "llm_providers": {
    "alibaba": {
      "api_key": "sk-YOUR_ALIBABA_KEY",
      "models": ["qwen-max", "qwen3-coder-480b-a35b-instruct"]
    }
  },
  "mongodb": {
    "uri": "mongodb://localhost:27017/vba_brain_core",
    "db": "vba_brain_core"
  },
  "postgresql": {
    "host": "localhost",
    "port": 5432,
    "database": "vba_brain",
    "username": "postgres",
    "password": "YOUR_PG_PASSWORD"
  },
  "localization": {
    "source_language": "ja",
    "target_language": "en"
  },
  "llm_settings": {
    "default_model": "qwen-max",
    "layer5_default_model": "qwen3-coder-480b-a35b-instruct"
  }
}
```

> ⚠️ **KHÔNG commit `config.json`** — file này đã có trong `.gitignore`.

### 3. Khởi động infrastructure (Docker)

```bash
cd infa

# Khởi động MongoDB + Qdrant + Oracle
docker compose up -d

# Kiểm tra trạng thái
docker compose ps

# Xem log MongoDB
docker compose logs -f mongo
```

| Service | URL/Port | Mô tả |
|---------|----------|--------|
| MongoDB | `localhost:27017` | Document database |
| Mongo Express UI | `http://localhost:8082` | Web UI xem database |
| Qdrant | `http://localhost:6333` | Vector DB + dashboard |
| Oracle Dev | `localhost:1522` | Oracle XE 23ai dev DB |
| Oracle Test | `localhost:1523` | Oracle XE 23ai test DB |

---

## 🚀 Chạy Hệ Thống

### Chạy Web Console (Frontend + Backend)

```bash
# Chạy cả FE (Next.js :3000) + BE (gRPC :50051)
python start.py

# Chỉ chạy Frontend
python start.py --fe-only

# Chỉ chạy Backend gRPC gateway
python start.py --be-only

# Clean Next.js cache trước khi chạy (dùng khi gặp lỗi Turbopack)
python start.py --clean
```

Sau khi chạy: mở **http://localhost:3000** để truy cập dashboard.

### Chạy Pipeline Batch (CLI)

Phân tích toàn bộ Access database và sinh tài liệu:

```bash
cd src/backend/workflow/layer1

# Chạy toàn bộ pipeline: Layer 1 parse → seed DB → Layer 2 BD/DD → Layer 3 SQL migrate
python run_all.py
```

Thứ tự thực hiện:
1. Parse Forms → Seed MongoDB
2. Parse Reports → Seed MongoDB
3. Parse Queries → Seed MongoDB
4. Parse Macros → Seed MongoDB
5. Parse Modules → Seed MongoDB
6. Aggregate cross-references
7. Seed tất cả data vào MongoDB
8. Chạy Layer 2: sinh BD & DD cho toàn bộ items
9. Chạy Layer 3: migrate tables → PostgreSQL

### Chạy WPF Application (Avalonia)

```bash
# Build Debug + Run
python start_wpf.py

# Chỉ Build
python start_wpf.py --build-only

# Chạy bằng build cũ
python start_wpf.py --run-only

# Build Release
python start_wpf.py --release

# Clean trước build
python start_wpf.py --clean
```

---

## 📊 Dashboard Web Console

| Trang | URL | Mô tả |
|-------|-----|--------|
| Landing | `/` | Giới thiệu pipeline |
| Layer 1 | `/layer1` | Xem danh sách forms/reports đã parse |
| Layer 2 | `/layer2` | Chạy BD/DD agent, xem kết quả |
| Layer 3 | `/layer3` | Review & convert SQL queries |
| Layer 4 | `/layer4` | Generate Excel specification files |
| Layer 5 | `/layer5` | Run code generation, view graph |
| Graph VBA | `/graph` | Visualize Access dependency graph |
| Graph WPF | `/graph-wpf` | Xem WPF mapping graph |

---

## 🔌 gRPC API Gateway

Server chạy tại port `50051`. Các service được định nghĩa trong `workflow.proto`:

| gRPC Service | Method | Mô tả |
|-------------|--------|--------|
| `Layer1Service` | `ListForms`, `ListQueries`, `GetDbQuery` | Đọc dữ liệu L1 từ MongoDB |
| `Layer2Service` | `RunBdFlowFull`, `RunDdFlowFull`, `GetConfig`, `GetModelsHealth` | Chạy AI agents |
| `Layer3Service` | `GenBd`, `GenDd`, `GenAll`, `ListOutputs`, `DownloadExcel` | Generate Excel |
| `Layer4Service` | `ListMigrationQueries`, `ConvertQuery`, `ConvertTableSchema`, `SeedQueries` | SQL migration |

---

## 🤖 LLM Models

Config trong `config.json → llm_settings` và `llm_providers`. Các model đang sử dụng:

| Layer | Model mặc định | Mô tả |
|-------|---------------|--------|
| Layer 2 BD/DD | `qwen-max` | Alibaba Qwen Max |
| Layer 4 Migration | `qwen-max` | SQL migration |
| Layer 5 Service/Repo | `qwen3-coder-480b-a35b-instruct` | 480B MoE coder |
| Layer 5 ViewModel | `qwen-plus-2025-07-28` | Fast + smart |

Model có thể override qua environment variable:
```bash
export DEFAULT_LLM_MODEL=qwen3-coder-480b-a35b-instruct
```

---

## 🗂️ Output Files

| Loại | Đường dẫn | Mô tả |
|------|-----------|--------|
| BD JSON | `layer2/output/bd_flow/s4_bd_final/<name>.json` | Business Design |
| DD JSON | `layer2/output/dd_flow/{screen|macro|common}/d4_dd_final/<name>.json` | Detailed Design |
| Excel BD | `layer4/outputs/BD/<name>.xlsx` | BD specification sheet |
| Excel DD | `layer4/outputs/DD/<name>.xlsx` | DD specification sheet |
| Generated C# | `layer5/output/` | Avalonia Views, Services, Repositories |
| Cost Report | `layer2/output/token_reports/` | Token usage & cost per run |

---

## 🔒 Bảo Mật

- **`config.json`** đã được thêm vào `.gitignore` — **không bao giờ commit file này**
- **`config.example.json`** là file template an toàn để commit
- **`.env`** files cũng đã trong `.gitignore`
- Nếu API key bị lộ: rotate key ngay trên Alibaba Cloud / OpenAI console

---

## 📄 License

MIT License — xem [LICENSE](LICENSE).
