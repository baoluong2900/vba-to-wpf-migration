<div align="center">

# vba_brain

**AI pipeline that modernizes MS Access + VBA into a .NET 10 / Avalonia application.**

Five layers turn `.accdb` / `.mdb` exports into an AST, then into Business & Detailed Design
documents, a PostgreSQL schema, Excel specification workbooks, and finally build-verified
C# / AXAML source code.

[![CI](https://github.com/baoluong2900/vba-to-wpf-migration/actions/workflows/ci.yml/badge.svg)](https://github.com/baoluong2900/vba-to-wpf-migration/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![.NET](https://img.shields.io/badge/.NET-10-512BD4?logo=dotnet&logoColor=white)](https://dotnet.microsoft.com/)
[![Avalonia](https://img.shields.io/badge/Avalonia-UI-8B44AC)](https://avaloniaui.net/)
[![gRPC](https://img.shields.io/badge/gRPC-50051-244c5a?logo=grpc&logoColor=white)](https://grpc.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[Quick start](#-quick-start) ·
[Architecture](#-architecture) ·
[The five layers](#-the-five-layers) ·
[gRPC API](#-grpc-api-gateway) ·
[Configuration](#-configuration) ·
[Contributing](CONTRIBUTING.md)

</div>

---

## What this does

Legacy MS Access applications carry business logic in three places that no modern tool reads
well: VBA behind forms, saved Access queries, and macro action sequences. `vba_brain` walks all
three, reconstructs the intent as reviewable design documents, and then generates a modern
replacement it actually compiles.

| Stage | You put in | You get out |
| --- | --- | --- |
| **Layer 1** | Access JSON exports | Parsed AST in MongoDB + a cross-reference dependency graph |
| **Layer 2** | Layer 1 AST | Business Design (BD) & Detailed Design (DD) JSON, LLM cost report |
| **Layer 3** | Access queries + table schemas | PostgreSQL DDL, converted SQL, migration status |
| **Layer 4** | BD / DD JSON | `.xlsx` specification workbooks (JP → EN translated) |
| **Layer 5** | DD JSON + name mapping | C# / AXAML Avalonia source, `dotnet build`-verified |

Everything is driven from a Next.js web console, or headlessly from the CLI.

> [!NOTE]
> **Status: working prototype, not hardened for production.** The gRPC gateway is
> unauthenticated (`add_insecure_port`, `grpc_server.py:595`) and automated test coverage is
> still thin. See [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) for the tracked backlog and
> [SECURITY.md](SECURITY.md) before exposing any port beyond `localhost`.

---

## 📑 Table of contents

- [Quick start](#-quick-start)
- [Architecture](#-architecture)
- [Repository layout](#-repository-layout)
- [Tech stack](#-tech-stack)
- [The five layers](#-the-five-layers)
- [MongoDB collections](#-mongodb-collections)
- [gRPC API gateway](#-grpc-api-gateway)
- [LLM model routing](#-llm-model-routing)
- [Configuration](#-configuration)
- [Running the system](#-running-the-system)
- [Web console](#-web-console)
- [Outputs & artifacts](#-outputs--artifacts)
- [Environment variables](#-environment-variables)
- [Troubleshooting](#-troubleshooting)
- [Project docs](#-project-docs)
- [Contributing](#-contributing)
- [License](#-license)

---

## ⚡ Quick start

### Prerequisites

| Tool | Version | Required for |
| --- | --- | --- |
| Python | **3.10+** (3.11+ recommended) | Backend pipeline — the source uses PEP 604 `X \| None` syntax without `from __future__ import annotations` in some modules |
| Node.js | **≥ 20.9** (Next.js 16 `engines`) | Web console |
| Yarn | 1.x — `npm install -g yarn` | Frontend package manager (**do not use npm**) |
| Docker Desktop | latest | MongoDB + PostgreSQL |
| .NET SDK | 10 | Layer 5 build-verify / running the Avalonia app |

### Five commands

```bash
# 1. Clone
git clone https://github.com/baoluong2900/vba-to-wpf-migration.git
cd vba-to-wpf-migration

# 2. Dependencies
pip install -r src/backend/requirements.txt
(cd src/frontend && yarn install)

# 3. Config — fill in your API key + credentials
cp config.example.json config.json
cp infa/.env.example infa/.env

# 4. Infrastructure (MongoDB 7 + Mongo Express + PostgreSQL 16)
(cd infa && docker compose up -d)

# 5. Run the console: frontend :3000 + gRPC gateway :50051
python start.py
```

Open **<http://localhost:3000>** — it redirects to `/layer1`.

> [!IMPORTANT]
> `config.json` and every `.env` are git-ignored and hold real secrets. Never commit them.
> `config.example.json` and `infa/.env.example` are the templates that *are* tracked.

---

## 🏗 Architecture

```
                 MS Access .accdb / .mdb  →  JSON exports in data/
                                  │
        ┌─────────────────────────▼─────────────────────────┐
        │  LAYER 1 · AST Extraction                (Python) │
        │  frm · query · macro · modules · table parsers    │
        │  + aggregator.py cross-reference enrichment       │
        └─────────────────────────┬─────────────────────────┘
                                  │  MongoDB: forms, reports, queries_v2,
                                  │           modules, macros, tables,
                                  │           dependency_graph
        ┌─────────────────────────▼─────────────────────────┐
        │  LAYER 2 · AI Design Specification     (LangGraph)│
        │  BD flow bd1→bd4        DD flow dd1→dd4           │
        └────────┬────────────────────────────────┬─────────┘
                 │  MongoDB: bds, dds             │
        ┌────────▼─────────┐            ┌─────────▼──────────┐
        │  LAYER 3 · SQL   │            │  LAYER 4 · Excel   │
        │  → PostgreSQL 16 │            │  → .xlsx / .docx   │
        └──────────────────┘            └─────────┬──────────┘
                                                  │
                                        ┌─────────▼──────────┐
                                        │  LAYER 5 · Codegen │
                                        │  → C# / AXAML      │
                                        │  → dotnet build ✓  │
                                        └────────────────────┘

  ── Infrastructure ───────────────────────────────────────────────────
  Next.js 16 console :3000  ◄── HTTP ──►  gRPC gateway :50051
  MongoDB 7 :27017 · Mongo Express :8082 · PostgreSQL 16 :5432 (Docker)
  All container ports bound to 127.0.0.1 only.
```

**Data flows one way.** Every layer reads from MongoDB rather than from the previous layer's
files, so any layer can be re-run in isolation without replaying the whole pipeline.

---

## 📁 Repository layout

```
workflow/
├── start.py                     Launcher: frontend :3000 + gRPC gateway :50051
├── start_wpf.py                 Launcher: Avalonia desktop app (dotnet build + run)
├── clean_generated_files.py     Utility: wipe Layer 5 generated output
├── config.example.json          ✅ tracked template
├── config.json                  ⚠️ git-ignored — real secrets
│
├── src/backend/
│   ├── requirements.txt
│   ├── common/config.py         Single config resolver: env → config.json → default
│   ├── protos/workflow.proto    Protobuf service + message contracts
│   ├── api_gateway/
│   │   └── grpc_server.py       ⭐ entry point, port 50051
│   └── workflow/
│       ├── layer1/              AST extraction
│       │   ├── parser/          frm · query · macro · modules · table
│       │   ├── aggregator.py    Cross-reference enrichment
│       │   ├── seed_db.py       Parsed JSON → MongoDB
│       │   └── run_all.py       Batch CLI: parse → seed → L2 → L3
│       ├── layer2/              AI design generation
│       │   ├── agents/bd_agent/ bd1_extract → bd2_map → bd3_logic → bd4_final
│       │   ├── agents/dd_agent/ dd1_skeleton → dd2_sql → dd3_llm → dd4_final
│       │   ├── utils/           cost_tracker · llm_client · model_router
│       │   ├── runners/main.py  CLI: --item / --all / --all-forms / --dry-run
│       │   └── pipeline.py      LangGraph StateGraph: BD → DD → END
│       ├── layer3/sql_migration/
│       │   ├── table_converter.py     Access DDL → PostgreSQL DDL
│       │   ├── postgres_migrator.py   LLM-assisted migration runner
│       │   └── router.py              list/get/update/convert endpoints
│       ├── layer4/              Excel specification export
│       │   ├── server.py        gen_bd / gen_dd / download
│       │   ├── scripts/         excel_translator + fill_* template fillers
│       │   └── template/        BD_Screen · BD_Report · DD_Screen · DD_Report
│       └── layer5/              Code generation
│           ├── agents/          graphview · logic · mapping · repo · service · ui · report
│           ├── codegen/         Jinja2 engine + C#/AXAML templates
│           ├── llm/             llm_client · token_tracker
│           ├── core/            config · models · utils
│           └── pipeline/        orchestrator · deploy_to_source · build_verify · file_writer
│
├── src/frontend/                Next.js 16 web console  (see its own README)
│   └── src/{app,components,lib}/
│
├── src/vba/vba_source/          Legacy VBA source exports (reference input)
│
├── src/wpf/                     Target .NET solution — vba_brain.slnx
│   ├── vba_brain.Domain/            Entities, interfaces
│   ├── vba_brain.Application/       Services, DTOs
│   ├── vba_brain.Infrastructure/    Dapper repositories
│   └── vba_brain.UI.Avalonia/       ⭐ Views (AXAML) + ViewModels
│
├── infa/
│   ├── docker-compose.yml       MongoDB 7 · Mongo Express · PostgreSQL 16
│   ├── .env.example             ✅ tracked template
│   └── mongo-init/              MongoDB bootstrap script
│
├── data/                        ⚠️ git-ignored — raw Access exports & DB volumes
└── docs/
    ├── UPGRADE_PLAN.md          Tracked backlog with gap analysis
    └── ai-md/                   Per-layer engineering notes & coding standards
```

---

## 🛠 Tech stack

<table>
<tr><th align="left" colspan="3">Backend</th></tr>
<tr><td>Language</td><td>Python</td><td><code>3.10+</code></td></tr>
<tr><td>API gateway</td><td>gRPC (<code>grpcio</code>)</td><td><code>≥1.62</code></td></tr>
<tr><td>AI orchestration</td><td>LangGraph + LangChain Core</td><td><code>≥0.2</code></td></tr>
<tr><td>MongoDB client</td><td>PyMongo</td><td><code>≥4.8</code></td></tr>
<tr><td>PostgreSQL driver</td><td>psycopg2-binary</td><td><code>≥2.9</code></td></tr>
<tr><td>Excel</td><td>openpyxl</td><td><code>≥3.1</code></td></tr>
<tr><td>Templating</td><td>Jinja2</td><td><code>≥3.1</code></td></tr>
<tr><td>HTTP (aux)</td><td>FastAPI + uvicorn</td><td><code>≥0.111</code></td></tr>
</table>

<table>
<tr><th align="left" colspan="3">Frontend</th></tr>
<tr><td>Framework</td><td>Next.js (App Router) + React</td><td><code>16.2.4</code> / <code>19.2.4</code></td></tr>
<tr><td>Language</td><td>TypeScript</td><td><code>^6.0</code></td></tr>
<tr><td>Styling</td><td>Tailwind CSS + CSS custom-property tokens</td><td><code>^4.3</code></td></tr>
<tr><td>Graph canvas</td><td><code>@xyflow/react</code> (React Flow) + Cytoscape</td><td><code>^12.10</code> / <code>^3.33</code></td></tr>
<tr><td>Backend bridge</td><td><code>@grpc/grpc-js</code> + <code>@grpc/proto-loader</code></td><td><code>^1.14</code></td></tr>
<tr><td>UI</td><td>lucide-react · framer-motion · sql-formatter</td><td>—</td></tr>
<tr><td>Package manager</td><td><b>yarn 1.x</b> (never npm)</td><td>—</td></tr>
</table>

<table>
<tr><th align="left">Service</th><th align="left">Image</th><th align="left">Bind</th><th align="left">Purpose</th></tr>
<tr><td>MongoDB</td><td><code>mongo:7.0</code></td><td><code>127.0.0.1:27017</code></td><td>Document store — L1/L2 state</td></tr>
<tr><td>Mongo Express</td><td><code>mongo-express:1.0.2</code></td><td><code>127.0.0.1:8082</code></td><td>DB admin UI — <b>dev only</b></td></tr>
<tr><td>PostgreSQL</td><td><code>postgres:16-alpine</code></td><td><code>127.0.0.1:5432</code></td><td>Migration target — L3/L5</td></tr>
</table>

<table>
<tr><th align="left" colspan="2">Target platform</th></tr>
<tr><td>Desktop UI</td><td>Avalonia UI (AXAML)</td></tr>
<tr><td>Runtime</td><td>.NET 10</td></tr>
<tr><td>Data access</td><td>Dapper → PostgreSQL</td></tr>
<tr><td>Architecture</td><td>MVVM — Domain / Application / Infrastructure / UI</td></tr>
</table>

---

## 🔬 The five layers

### Layer 1 — AST extraction & parsing

**Entry point** `src/backend/workflow/layer1/run_all.py`
**Input** Access JSON exports in `data/`
**Output** MongoDB L1 collections + `data/graphs/`

| Parser | Input | Collection | Extracts |
| --- | --- | --- | --- |
| `frm_parser.py` | `data/forms/*.json` | `forms` | Controls, events, VBA procedures, form properties |
| `frm_parser.py` | `data/reports/*.json` | `reports` | Report sections, fields, embedded queries |
| `query_parser.py` | `data/queries/*.json` | `queries_v2` | SQL text, parameters, join type, `raw_sql` |
| `macro_parser.py` | `data/macros/*.json` | `macros` | Action sequences, conditions, arguments |
| `modules_parser.py` | `data/modules/*.json` | `modules` | Public subs/functions, constants, `Declare` |
| `table_parser.py` | `data/tables/*.json` | `tables` | Columns, data types, PK/FK, indexes |

**Cross-reference enrichment** — `aggregator.py` resolves the implicit call graph that Access
hides in string literals:

- `DoCmd` targets: `OpenForm`, `OpenReport`, `OpenQuery`, `RunMacro`, `OutputTo`
- Domain aggregates: `DLookup` / `DCount` / `DSum` → the table or query they read
- Cross-form access: `Form_X.Proc()`, `[Forms]![FormName]`
- Standard-module calls: `Module.Procedure()`
- Dynamic dispatch: `CallSub`, `Application.Run`

Results land in `data/graphs/` and the `dependency_graph` collection.

---

### Layer 2 — AI design specification

**Entry point** `src/backend/workflow/layer2/runners/main.py`
**Orchestration** LangGraph `StateGraph` — BD node → DD node → `END`
**State** `PipelineState` TypedDict

#### BD flow — forms & reports only

```
bd1_extract  →  bd2_map  →  bd3_logic  →  bd4_final
extract         map VBA      analyse       emit BD JSON
screens &       events &     business      + persist
controls        UI elements  logic
```

Output `layer2/output/bd_flow/bd4_bd_final/<name>.json`
Skipped entirely for `--type module` and `--type macro`.

#### DD flow — all item types

```
dd1_skeleton  →  dd2_sql_map  →  dd3_llm_enrich  →  dd4_final
build DD         map SQL          LLM fills steps,   emit DD JSON
skeleton         queries →        logic, pseudo-     + persist
from BD          sheet 4/5        code
```

Output `layer2/output/dd_flow/{screen|macro|common}/dd4_dd_final/<name>.json`

#### CLI

```bash
cd src/backend/workflow/layer2/runners

python main.py --item F_Login --type form --stage dev   # one item
python main.py --all-forms --stage dev                  # every form
python main.py --all --stage production                 # forms + reports + modules
python main.py --all --dry-run                          # list work, call no LLM
```

`--stage` selects the model tier:

| Stage | Model | Use for |
| --- | --- | --- |
| `dev` | `qwen-max` | Development, quick iteration |
| `pilot` | `qwen-max` | UAT, quality review |
| `production` | `qwen3-coder-480b` (critical/high) · `qwen3-235b` (medium) · `qwen3-coder-next` (low) | Full document generation, routed by item complexity |

#### Cost tracking

Every LLM call is recorded by the `CostTracker` singleton
(`layer2/utils/cost_tracker.py`), priced per 1M tokens in USD:

| Model | Input | Output |
| --- | --- | --- |
| `qwen-max` | $2.80 | $8.40 |
| `qwen-plus` | $0.56 | $1.68 |
| `gpt-4o` | $2.50 | $10.00 |
| `gpt-4o-mini` | $0.15 | $0.60 |

Reports are written after each run to `layer2/output/token_reports/<name>_<timestamp>.json`
and `src/excel_outputs/<name>_cost.xlsx`.

---

### Layer 3 — SQL migration

**Input** `queries_v2` + `tables` · **Output** PostgreSQL DDL and converted SQL

| Module | Responsibility |
| --- | --- |
| `table_converter.py` | Access data types → PostgreSQL DDL (pure function — the easiest place to add tests) |
| `postgres_migrator.py` | LLM-assisted runner: read table → generate `CREATE TABLE` → execute |
| `seed_queries_v2.py` | Seed Access queries (keeping both `raw_sql` and `sql`) into MongoDB |
| `router.py` | list / get / update / convert query, convert table schema, stats |

```
MongoDB (queries_v2 · tables)
        │
        ├─ table_converter.py       Access DDL  → PostgreSQL DDL
        ├─ postgres_migrator.py     execute DDL → target PostgreSQL
        └─ router.py::convert_query LLM: Access SQL → PostgreSQL dialect
```

> [!WARNING]
> Layer 3 currently focuses on `CREATE TABLE`. Index / FK / constraint migration, dry-run diff,
> and rollback scripts are open items in [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) §4.1.

---

### Layer 4 — Excel specification export

**Input** BD/DD JSON (`layer2/output/` or MongoDB `bds`/`dds`) · **Output** `src/excel_outputs/`

| Template | File | For |
| --- | --- | --- |
| BD Screen | `BD_Screen/bd_template.xlsx` | Forms — Business Design |
| BD Report | `BD_Report/bd_report_template.xlsx` | Reports — Business Design |
| DD Screen | `DD_Screen/dd_template.xlsx` | Forms — Detailed Design |
| DD Report | `DD_Report/dd_report_template.xlsx` | Reports — Detailed Design |
| DD Macro | `DD_Screen/dd_template_macro.xlsx` | Macros — Detailed Design |
| DD Module | `DD_Screen/dd_template_module.xlsx` | Modules — Detailed Design |

**Translation engine** (`excel_translator.py`) — when
`config.json → localization.target_language = "en"`:

- Cell values translated Japanese → English via the `JP_EN_MAPPING` dictionary
- Sheet names translated (e.g. `変更履歴` → `Change History`)
- `restore_japanese_sheet_names()` reverses the sheet renaming after export

Alongside `.xlsx`, `layer4/server.py` can emit a `.docx` rendition of the same document.

---

### Layer 5 — Automated code generation

**Input** DD JSON + Access→Avalonia name mapping · **Output** compiling C# / AXAML

| Agent | Generates | Deployed to |
| --- | --- | --- |
| `ui` (view) | `Views/F_Login.axaml` | `vba_brain.UI.Avalonia/Views/` |
| `ui` (viewmodel) | `ViewModels/F_LoginViewModel.cs` | `vba_brain.UI.Avalonia/ViewModels/` |
| `service` | `Services/LoginService.cs` | `vba_brain.Application/` |
| `repo` | `Repositories/LoginRepository.cs` | `vba_brain.Infrastructure/` |
| `repo` (interface) | `Interfaces/ILoginRepository.cs` | `vba_brain.Domain/` |
| `entity` | `Entities/User.cs` | `vba_brain.Domain/` |
| `report` | Report `UserControl` + ViewModel | `vba_brain.UI.Avalonia/` |
| `graphview` | Access → .NET name-mapping graph | consumed by the web console |

**Model routing** (`layer5/core/config.py`) — every entry is overridable by environment
variable or `config.json → llm_settings`:

```python
L5_ROUTING = {
    "service":    qwen3-coder-480b,   # DD steps → C# business logic
    "repository": qwen3-coder-480b,   # SQL → Dapper
    "viewmodel":  qwen-plus-2025,     # MVVM commands, event flow
    "view_xaml":  qwen-plus-2025,     # BD layout → AXAML
    "validator":  qwen-plus-2025,     # Business rules → FluentValidation
    "entity":     qwen-plus-2025,     # Data models
    "dto":        qwen-plus-2025,
    "mapper":     qwen-plus-2025,
}
```

**Build-verify loop** (`pipeline/build_verify.py`) — this is what separates generated code from
generated *text*:

1. Run `dotnet build`, parse the compiler diagnostics.
2. On error → send errors + offending source to the LLM → apply the returned patch.
3. Repeat up to `MAX_RETRIES = 3`, then report the remaining diagnostics.

---

## 🗄 MongoDB collections

| Collection | Layer | Contents |
| --- | --- | --- |
| `forms` | L1 | Form metadata, controls, VBA procedures, resolved references |
| `reports` | L1 | Report metadata, sections, fields |
| `queries_v2` | L1 | Access query definitions (`sql`, `raw_sql`, params) |
| `modules` | L1 | VBA standard modules — procedures, functions, constants |
| `macros` | L1 | Macro action sequences |
| `tables` | L1 | Table schemas — columns, types, constraints |
| `dependency_graph` | L1 | Cross-reference graph from `aggregator.py` |
| `bds` | L2 | Business Design documents |
| `dds` | L2 | Detailed Design documents |
| `agent_repo` | L5 | Repository contract artifacts consumed by `agent_service` |

Collection names are configurable — see `layer2/config.py` and `layer5/core/config.py`
(`MONGO_COL_AGENT_REPO` and friends).

---

## 🔌 gRPC API gateway

**Port** `50051` · **Entry** `src/backend/api_gateway/grpc_server.py` · **Contract**
`src/backend/protos/workflow.proto`

> [!CAUTION]
> **Service names do not match layer numbers.** `Layer3Service` serves Excel export (pipeline
> Layer 4) and `Layer4Service` serves SQL migration (pipeline Layer 3). This is a historical
> naming swap kept for wire compatibility; renaming it is tracked in
> [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) §3.3. The table below is authoritative.

<details open>
<summary><b>Layer1Service</b> — AST browsing</summary>

| Method | Request | Returns |
| --- | --- | --- |
| `ListForms` | `Empty` | All forms from MongoDB |
| `ListQueries` | `Empty` | All queries |
| `ListAllItems` | `Empty` | Forms + reports + modules + macros |
| `GetDbQuery` | `screen_name, item_type, deep` | Raw JSON for one item |

</details>

<details open>
<summary><b>Layer2Service</b> — BD/DD generation</summary>

| Method | Request | Returns |
| --- | --- | --- |
| `GetConfig` | `Empty` | LLM providers + available models (never API keys) |
| `GetModelsHealth` | `Empty` | Parallel ping of every configured model |
| `GetBdStatus` | `screen_name` | Whether BD/DD already exists |
| `RunBdFlowFull` | `screen_name, model, force` | Run bd1→bd4 |
| `RunBdFlowExtract` | `screen_name` | Run bd1_extract only |
| `RunBdFlowAnalysis` | `screen_name, model, force` | Extract + analysis phases |
| `RunDdFlowFull` | `screen_name, model, force` | Run dd1→dd4 |
| `GetTokenReport` | `Empty` | Current token/cost report |

</details>

<details>
<summary><b>Layer3Service</b> — ⚠️ Excel export (pipeline Layer 4)</summary>

| Method | Request | Returns |
| --- | --- | --- |
| `ListItems` | `Empty` | Items eligible for Excel generation |
| `ListOutputs` | `Empty` | Generated `.xlsx` / `.docx` / `.zip` files |
| `GenBd` | `screen_name, type` | Generate BD workbook |
| `GenDd` | `screen_name, type` | Generate DD workbook |
| `GenAll` | `screen_name, type` | Generate BD + DD |
| `DownloadExcel` | `doc_kind, doc_type, filename` | File bytes |

</details>

<details>
<summary><b>Layer4Service</b> — ⚠️ SQL migration (pipeline Layer 3)</summary>

| Method | Request | Returns |
| --- | --- | --- |
| `ListMigrationQueries` | `Empty` | Access queries awaiting migration |
| `GetMigrationQuery` | `name` | One query — `sql` + `target_sql` |
| `UpdateMigrationQuery` | `name, target_sql, status, …` | Persist review result |
| `ConvertQuery` | `name, model` | LLM convert → PostgreSQL dialect |
| `SeedQueries` | `Empty` | Re-seed queries from MongoDB |
| `ListMigrationTables` | `Empty` | Tables awaiting migration |
| `ConvertTableSchema` | `table_name, target_db` | Convert DDL for one table |
| `GetStats` | `Empty` | Migration progress statistics |

</details>

Regenerate the Python stubs after editing the `.proto`:

```bash
python -m grpc_tools.protoc \
  -I src/backend/protos \
  --python_out=src/backend/api_gateway \
  --grpc_python_out=src/backend/api_gateway \
  src/backend/protos/workflow.proto
```

---

## 🤖 LLM model routing

### Resolution order

Implemented by `get_setting()` in `src/backend/common/config.py`:

```
1. Environment variable            (e.g. ALIBABA_API_KEY, LAYER5_SERVICE_MODEL)
        ↓  not set
2. config.json → llm_providers.<provider>.api_key
   config.json → llm_settings.<key>
        ↓  missing
3. Hard-coded default              (qwen-max / qwen3-coder-480b-a35b-instruct)
```

### Models in active use

Declared in `config.json → llm_providers.alibaba.models` (Alibaba Cloud DashScope):

| Model ID | Context | Used by |
| --- | --- | --- |
| `qwen-max` | 128K | L2 dev/pilot, L3 migration, L2 production (medium) |
| `qwen3-coder-480b-a35b-instruct` | 262K | L5 service/repository, L2 production (critical/high) |
| `qwen3-coder-next` | 262K | L2 production (low complexity) |
| `qwen3-235b-a22b-instruct-2507` | 262K | L2 production (medium) reasoning |
| `qwen-plus-2025-07-28` | 262K | L5 viewmodel/AXAML/entity/DTO/mapper, fallback |

OpenAI, Anthropic, and Groq providers are wired in `common/config.py` but optional — add a key
to `config.json` and select the model at runtime.

### Runtime overrides

```bash
export L2_STAGE=production                                       # model tier for Layer 2
export LAYER5_SERVICE_MODEL=qwen3-coder-480b-a35b-instruct        # per-role override
export MODEL_OVERRIDE_QWEN_MAX=qwen3-coder-480b-a35b-instruct     # alias remap (any model id)
```

`MODEL_OVERRIDE_<MODEL_ID>` uppercases the id and replaces `-` with `_`.

### Quota exhaustion & fallback

When a model returns HTTP 403 `AllocationQuota.FreeTierOnly`, Layer 2 walks a fallback chain
defined in `layer2/utils/model_router.py`:

```
qwen3-coder-480b-a35b-instruct → qwen3-coder-next → qwen3-coder-plus → qwen-max → qwen-plus
qwen3-coder-next               → qwen3-coder-480b → qwen3-coder-plus → qwen-max → qwen-plus
```

```python
from layer2.utils.llm_client import LLMClient
from layer2.config import DEV_MODEL

client = LLMClient()
text, usage = client.call_with_fallback(DEV_MODEL, system_prompt, user_prompt)
```

To resolve quota problems: disable *"use free tier only"* in the
[DashScope console](https://dashscope.console.aliyun.com/), swap in another key, or wait for the
monthly reset. Track spend in `layer2/output/token_reports/` and `src/excel_outputs/*_cost.xlsx`.

---

## ⚙ Configuration

Two files, both copied from tracked templates:

| File | Template | Holds |
| --- | --- | --- |
| `config.json` | `config.example.json` | LLM keys, model routing, MongoDB/PostgreSQL, ports, localization |
| `infa/.env` | `infa/.env.example` | Docker Compose credentials for MongoDB / Mongo Express / PostgreSQL |
| `.env` *(optional)* | `.env.example` | Shell-level overrides read by `python-dotenv` |

Minimum fields to fill in `config.json`:

- `llm_providers.alibaba.api_key` — DashScope API key
- `mongodb.uri` — e.g. `mongodb://vba_brain:<pw>@localhost:27017/vba_brain_core?authSource=admin`
- `postgresql.connection_string` — ADO.NET-style string used by both Python and the Avalonia app

Default local credentials (from `infa/.env.example` — **change these before sharing a host**):

| Service | URL | Credentials |
| --- | --- | --- |
| MongoDB | `localhost:27017` | `vba_brain` / `vba_brain2024` |
| Mongo Express | <http://localhost:8082> | `admin` / `admin123` |
| PostgreSQL | `localhost:5432` | `vba_brain` / `vba_brain2024` — db `vba_brain` |

---

## 🚀 Running the system

### Web console

```bash
python start.py              # frontend :3000 + gRPC gateway :50051
python start.py --fe-only    # frontend only
python start.py --be-only    # gateway only
python start.py --clean      # wipe .next cache first (Turbopack/OOM recovery)
```

### Full batch pipeline

```bash
cd src/backend/workflow/layer1
python run_all.py            # parse → seed → Layer 2 BD/DD → Layer 3 PostgreSQL migrate
```

Execution order, from `SCRIPTS` in `run_all.py`:

| # | Script | Step |
| --- | --- | --- |
| 1 | `parser/table_parser.py` | Parse tables |
| 2 | `parser/query_parser.py` | Parse queries |
| 3 | `parser/frm_parser.py` | Parse forms & reports |
| 4 | `parser/macro_parser.py` | Parse macros |
| 5 | `parser/modules_parser.py` | Parse modules |
| 6 | `aggregator.py` | Aggregate cross-references |
| 7 | `seed_db.py` | Seed everything → MongoDB |
| 8 | `layer2/runners/main.py --all --stage dev` | Generate BD + DD |
| 9 | `layer3/sql_migration/postgres_migrator.py` | Migrate → PostgreSQL |

### Layer 5 code generation

```bash
cd src/backend/workflow/layer5
python run_codegen_all.py    # generate for every mapped item
python run_codegen_test.py   # single-item smoke run
```

### Avalonia desktop app

```bash
python start_wpf.py                # build Debug + run
python start_wpf.py --build-only   # build, do not launch
python start_wpf.py --run-only     # launch existing build
python start_wpf.py --release      # Release configuration
python start_wpf.py --clean        # dotnet clean, then build
```

> On Windows, run Python with `python -X utf8` to avoid console encoding errors.

---

## 📊 Web console

| Page | Route | What you do there |
| --- | --- | --- |
| Layer 1 | `/layer1` | Browse parsed forms, reports, queries, modules; inspect the dependency graph |
| Layer 2 | `/layer2` | Run BD/DD agents, read JSON output, watch token spend |
| Layer 3 | `/layer3` | Review and convert SQL (Access → PostgreSQL) |
| Layer 4 | `/layer4` | Generate and download BD/DD specification workbooks |
| Layer 5 | `/layer5` | Run codegen agents, inspect generated files, explore the Avalonia mapping graph |

`/` redirects to `/layer1`. Theme is persisted to `localStorage.theme` and applied before first
paint. Frontend conventions live in [`src/frontend/README.md`](src/frontend/README.md).

---

## 📦 Outputs & artifacts

| Artifact | Path | Format |
| --- | --- | --- |
| BD JSON | `layer2/output/bd_flow/bd4_bd_final/<name>.json` | JSON |
| DD JSON | `layer2/output/dd_flow/{screen\|macro\|common}/dd4_dd_final/<name>.json` | JSON |
| BD workbook | `src/excel_outputs/BD/<type>/<name>.xlsx` | XLSX (+ `.docx`) |
| DD workbook | `src/excel_outputs/DD/<type>/<name>.xlsx` | XLSX (+ `.docx`) |
| Token report | `layer2/output/token_reports/<name>_<ts>.json` | JSON |
| Cost workbook | `src/excel_outputs/<name>_cost.xlsx` | XLSX |
| Generated C#/AXAML | `layer5/output/` → deployed into `src/wpf/vba_brain.*/` | `.cs` / `.axaml` |
| Dependency graph | `data/graphs/<name>.json` | JSON |

All of these are runtime artifacts and git-ignored. `clean_generated_files.py` clears Layer 5
output when you want a fresh generation.

---

## 🌐 Environment variables

Every variable below overrides `config.json`. Names verified against
`src/backend/common/config.py` and `layer5/core/config.py`.

<details open>
<summary><b>Infrastructure</b></summary>

| Variable | Purpose | Default |
| --- | --- | --- |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGO_DB` | MongoDB database name | `vba_brain_core` |
| `MONGO_COL_AGENT_REPO` | Layer 5 repo-contract collection | `agent_repo` |
| `POSTGRES_CONN` | Full ADO.NET-style connection string | built from the parts below |
| `POSTGRES_HOST` / `POSTGRES_PORT` | PostgreSQL host / port | `localhost` / `5432` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database / user / password | `vba_brain` / `vba_brain` / from `config.json` |

</details>

<details open>
<summary><b>LLM providers & routing</b></summary>

| Variable | Purpose | Default |
| --- | --- | --- |
| `ALIBABA_API_KEY` | DashScope key (primary provider) | from `config.json` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY` / `DEEPSEEK_API_KEY` / `MEGALLM_API_KEY` | Optional providers | from `config.json` |
| `L2_STAGE` *(alias `STAGE`)* | Layer 2 model tier — `dev` / `pilot` / `production` | `dev` |
| `DEFAULT_LLM_MODEL` | Global default model | `qwen-max` |
| `LAYER2_DEV_MODEL` / `LAYER2_PILOT_MODEL` | Layer 2 per-stage model | `qwen-max` |
| `LAYER3_MIGRATION_MODEL` / `LAYER4_MIGRATION_MODEL` | Migration models | `qwen-max` |
| `LAYER5_DEFAULT_MODEL` / `LAYER5_SERVICE_MODEL` / `LAYER5_VIEWMODEL_MODEL` / `LAYER5_REPOSITORY_MODEL` | Layer 5 per-role models | `qwen3-coder-480b-a35b-instruct` / `qwen-plus-2025-07-28` |
| `MODEL_OVERRIDE_<MODEL_ID>` | Remap any model alias → real id | — |

</details>

<details open>
<summary><b>Localization</b></summary>

| Variable | Purpose | Default |
| --- | --- | --- |
| `SOURCE_LANGUAGE` | Source document language | `ja` |
| `TARGET_LANGUAGE` | Output language for BD/DD + Excel translation | `en` |

</details>

---

## 🧯 Troubleshooting

<details>
<summary><b>Frontend won't start / Turbopack out-of-memory</b></summary>

`start.py` already sets `NODE_OPTIONS=--max-old-space-size=4096`. Clear the build cache:

```bash
python start.py --clean
```

</details>

<details>
<summary><b>gRPC calls fail with UNAVAILABLE</b></summary>

The gateway must be listening on `50051`:

```bash
lsof -nP -iTCP:50051 -sTCP:LISTEN     # macOS / Linux
python start.py --be-only             # start it standalone
```

The frontend reaches the gateway only through the API routes under
`src/frontend/src/app/api/` — a browser cannot speak gRPC directly.

</details>

<details>
<summary><b>MongoDB authentication failed</b></summary>

The Docker Compose stack enables root auth, so the URI needs `authSource`:

```
mongodb://vba_brain:<password>@localhost:27017/vba_brain_core?authSource=admin
```

</details>

<details>
<summary><b>SyntaxError on <code>str | None</code></b></summary>

You are on Python 3.9. Some modules (`layer1/parser/frm_parser.py`,
`layer3/sql_migration/router.py`) use PEP 604 unions without
`from __future__ import annotations`. Use Python **3.10+**.

</details>

<details>
<summary><b>Layer 5 build-verify keeps failing</b></summary>

`build_verify.py` retries three times. If diagnostics remain, build by hand to read the full
compiler output:

```bash
dotnet build src/wpf/vba_brain.slnx
```

The .NET 10 SDK is required — `dotnet --version` must report `10.x`.

</details>

<details>
<summary><b>Excel export produces empty cells</b></summary>

Layer 4 reads BD/DD JSON, not raw AST. Generate the design documents first
(`layer2/runners/main.py --item <name>`), then export.

</details>

---

## 📚 Project docs

| Document | Contents |
| --- | --- |
| [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) | Gap analysis + phased backlog (security, tests, CI, refactors) |
| [`docs/ai-md/backend/`](docs/ai-md/backend/) | Per-layer engineering notes, agent detail specs |
| [`docs/ai-md/frontend/architecture.md`](docs/ai-md/frontend/architecture.md) | Web console architecture |
| [`docs/ai-md/rules/coding_standards.md`](docs/ai-md/rules/coding_standards.md) | Code conventions |
| [`src/frontend/README.md`](src/frontend/README.md) | Frontend design system & scripts |
| [`src/frontend/AGENTS.md`](src/frontend/AGENTS.md) | Instructions for AI coding agents in this repo |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, quality gates, commit & PR conventions |
| [SECURITY.md](SECURITY.md) | Threat model, hardening checklist, vulnerability reporting |
| [CHANGELOG.md](CHANGELOG.md) | Notable changes |

---

## 🤝 Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) first. Short version:

```bash
python -m compileall -q src/backend        # backend must compile
(cd src/frontend && yarn lint)             # frontend must lint clean
(cd src/frontend && yarn build)            # frontend must build
```

Hard rules: no secrets in tracked files, no hard-coded API keys or hosts (everything goes through
`config.json` / env), `yarn` never `npm`, and any new LLM provider is a `config.json` change
rather than a code change.

---

## 📄 License

[MIT](LICENSE) © baoluong2900
