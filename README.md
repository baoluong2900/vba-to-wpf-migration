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
| **Layer 1** | Access text export (`src/vba/vba_source/`) | Parsed AST in MongoDB + a cross-reference dependency graph |
| **Layer 2** | Layer 1 AST | Business Design (BD) & Detailed Design (DD) JSON, LLM cost report |
| **Layer 3** | Access queries + table schemas | PostgreSQL DDL, converted SQL, migration status |
| **Layer 4** | BD / DD JSON | `.xlsx` specification workbooks (JP → EN translated) |
| **Layer 5** | DD JSON + name mapping | C# / AXAML Avalonia source, `dotnet build`-verified |

Everything is driven from a Next.js web console, or headlessly from the CLI.

> [!NOTE]
> **Status: working prototype, not hardened for production.** The gRPC gateway binds to
> `localhost` by default; a shared bearer token (`GRPC_AUTH_TOKEN`) and TLS (`GRPC_TLS_CERT` /
> `GRPC_TLS_KEY`) are available but off by default. See [`docs/REVIEW_REPORT.md`](docs/REVIEW_REPORT.md) for the latest full-source
> review, [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) for the backlog, and
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
| Node.js | **≥ 22.18** (22 LTS recommended; on 23.x, ≥ 23.6) | Web console — Next.js 16 needs ≥ 20.9; `yarn test` runs TypeScript directly with Node's type stripping, which is on by default only from 22.18 / 23.6 |
| Yarn | 1.x — `npm install -g yarn` | Frontend package manager (**do not use npm**) |
| Docker Desktop | latest | MongoDB + PostgreSQL |
| PostgreSQL client (`psql`) | 16 | Layer 3 table migration (`postgres_migrator.py`) |
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

Working on the code? Install the dev tools and run the tests:

```bash
pip install -r src/backend/requirements.txt -r src/backend/requirements-dev.txt
pytest && pytest tests/layer5        # backend (two sessions — see tests/layer5/conftest.py)
(cd src/frontend && yarn test)       # frontend unit tests
```

> [!IMPORTANT]
> `config.json` and every `.env` are git-ignored and hold real secrets. Never commit them.
> `config.example.json` and `infa/.env.example` are the templates that *are* tracked.

---

## 🏗 Architecture

```
              Access text export in src/vba/vba_source/
                                  │
        ┌─────────────────────────▼─────────────────────────┐
        │  LAYER 1 · AST Extraction                (Python) │
        │  frm · query · macro · modules · table parsers    │
        │  + aggregator.py cross-reference enrichment       │
        │  → JSON in data/ → seed_db.py → MongoDB           │
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

**Data flows one way.** Layers 2 and 3 read Layer 1's output from MongoDB. Layer 4 reads Layer 2's
JSON files in `layer2/output/` first and falls back to MongoDB `bds` / `dds`. The Layer 5 pipeline
(`run_codegen_all.py`) loads BD/DD from the sample files tracked in `layer4/inputs/BD_json/screen/`
and `layer4/inputs/DD_json/form/`, which nothing in the pipeline writes; a Layer 5 agent run on its
own (e.g. from the console) reads MongoDB `bds` / `dds` first.

---

## 📁 Repository layout

```
workflow/
├── start.py                     Launcher: frontend :3000 + gRPC gateway :50051
├── start_wpf.py                 Launcher: Avalonia desktop app (dotnet build + run)
├── clean_generated_files.py     Utility: delete Layer 5 files deployed into src/wpf (--dry-run first)
├── pyproject.toml               pytest + ruff configuration
├── config.example.json          ✅ tracked template
├── config.json                  ⚠️ git-ignored — real secrets
│
├── tests/
│   ├── backend/                 pytest — gateway, config, Layer 1–4
│   └── layer5/                  pytest — Layer 5 (own session: `pytest tests/layer5`)
│
├── src/backend/
│   ├── requirements.txt         Runtime deps (floor + next-major ceiling)
│   ├── requirements-dev.txt     pytest · ruff · grpcio-tools (stub regeneration)
│   ├── common/config.py         Single config resolver: env → config.json → default
│   ├── protos/workflow.proto    Protobuf service + message contracts
│   ├── api_gateway/
│   │   ├── grpc_server.py       ⭐ entry point, port 50051
│   │   └── auth.py              Optional bearer-token interceptor
│   └── workflow/
│       ├── layer1/              AST extraction
│       │   ├── parser/          frm · query · macro · modules · table
│       │   ├── aggregator.py    Cross-reference enrichment
│       │   ├── seed_db.py       Parsed JSON → MongoDB
│       │   └── run_all.py       Batch CLI: parse → seed → L2 → L3
│       ├── layer2/              AI design generation
│       │   ├── agents/bd_agent/ BD1 source → BD2 mapping → BD3 LLM logic → BD4 final
│       │   ├── agents/dd_agent/ DD1 source → DD2 skeleton + SQL → DD3 LLM steps → DD4 final
│       │   ├── utils/           cost_tracker · llm_client · model_router
│       │   ├── runners/main.py  CLI: --item / --all / --all-forms / --dry-run
│       │   └── pipeline.py      LangGraph StateGraph: BD → DD → END
│       ├── layer3/sql_migration/
│       │   ├── table_converter.py     Access schema → CREATE TABLE (pure function)
│       │   ├── query_utils.py         SQL rebuild · query type · bind variables (pure)
│       │   ├── seed_queries_v2.py     queries → queries_v2 sync (keeps review work)
│       │   ├── postgres_migrator.py   psql runner (--dry-run / --table / --output)
│       │   └── router.py              list/get/update/convert endpoints
│       ├── layer4/              Excel specification export
│       │   ├── server.py        gen_bd / gen_dd / download
│       │   ├── scripts/         excel_translator + fill_* template fillers
│       │   └── template/        BD_Screen · BD_Report · DD_Screen · DD_Report
│       └── layer5/              Code generation
│           ├── agents/          graphview · logic · mapping · repo · service · ui · report
│           ├── codegen/         Jinja2 engine + IService.cs template
│           ├── llm/             llm_client · token_tracker
│           ├── core/            config · models · naming · fid_resolver · fsutil · cs_text
│           └── pipeline/        orchestrator · deploy_to_source · build_verify · file_writer
│
├── src/frontend/                Next.js 16 web console  (see its own README)
│   └── src/{app,components,lib}/
│
├── src/vba/vba_source/          Access text export (Forms · Queries · Macros · Modules · Tables) — Layer 1 input
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
├── data/                        ⚠️ git-ignored — parsed Layer 1 JSON, BD/DD backups & DB volumes
└── docs/
    ├── UPGRADE_PLAN.md          Tracked backlog with gap analysis
    └── ai-md/                   Per-layer engineering notes & coding standards
```

---

## 🛠 Tech stack

<table>
<tr><th align="left" colspan="3">Backend</th></tr>
<tr><td>Language</td><td>Python</td><td><code>3.10+</code></td></tr>
<tr><td>API gateway</td><td>gRPC (<code>grpcio</code>)</td><td><code>≥1.71.2</code></td></tr>
<tr><td>AI orchestration</td><td>LangGraph</td><td><code>≥1.0</code></td></tr>
<tr><td>MongoDB client</td><td>PyMongo</td><td><code>≥4.8</code></td></tr>
<tr><td>PostgreSQL</td><td><code>psql</code> CLI (Layer 3 runs DDL through it)</td><td><code>16</code></td></tr>
<tr><td>Excel / Word</td><td>openpyxl · python-docx</td><td><code>≥3.1</code> / <code>≥1.1</code></td></tr>
<tr><td>Templating</td><td>Jinja2</td><td><code>≥3.1</code></td></tr>
<tr><td>Tests / lint</td><td>pytest · ruff</td><td><code>requirements-dev.txt</code></td></tr>
</table>

<table>
<tr><th align="left" colspan="3">Frontend</th></tr>
<tr><td>Framework</td><td>Next.js (App Router) + React</td><td><code>16.2.4</code> / <code>19.2.4</code></td></tr>
<tr><td>Language</td><td>TypeScript</td><td><code>^6.0</code></td></tr>
<tr><td>Styling</td><td>Tailwind CSS + CSS custom-property tokens</td><td><code>^4.3</code></td></tr>
<tr><td>Graph canvas</td><td><code>@xyflow/react</code> (React Flow) + Cytoscape</td><td><code>^12.10</code> / <code>^3.33</code></td></tr>
<tr><td>Backend bridge</td><td><code>@grpc/grpc-js</code> + <code>@grpc/proto-loader</code></td><td><code>^1.14</code> / <code>^0.8</code></td></tr>
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
**Input** Access text export in `src/vba/vba_source/` (else `VBA_Export_All/` at the repo root)
**Output** One JSON per object in `data/<type>/` + `data/reference_map.json` + `data/graphs/`, which `seed_db.py` loads into the MongoDB L1 collections

| Parser | Input (in the export) | Output → collection | Extracts |
| --- | --- | --- | --- |
| `frm_parser.py` | `Forms/*.frm` | `data/forms/` → `forms` | Controls, events, VBA procedures, form properties |
| `frm_parser.py` | `Forms/*.frm` (report exports) | `data/reports/` → `reports` | Report sections, fields, embedded queries |
| `query_parser.py` | `Queries/*.sql.sql` | `data/queries/` → `queries` | Structured query, tables, parameters, and the original Access SQL as `sql` |
| `macro_parser.py` | `Macros/*.mac` | `data/macros/` → `macros` | Action sequences, conditions, arguments |
| `modules_parser.py` | `Modules/*.bas` | `data/modules/` → `modules` | Public subs/functions, constants, `Declare` |
| `table_parser.py` | `Tables/AllColumns.csv` | `data/tables/` → `tables` | Columns: logical / physical name, data type, length, required |

**Cross-reference enrichment** — `aggregator.py` resolves the implicit call graph that Access
hides in string literals:

- `DoCmd` targets: `OpenForm`, `OpenReport`, `OpenQuery`, `RunMacro`, `OutputTo`
- Domain aggregates: `DLookup` / `DCount` / `DSum` → the table or query they read
- Cross-form access: `Form_X.Proc()`, `[Forms]![FormName]`
- Standard-module calls: `Module.Procedure()`
- Dynamic dispatch: `CallSub`, `Application.Run`

Results land in `data/reference_map.json` and `data/graphs/` (Cytoscape views). `seed_db.py`
flattens the reference map into one `dependency_graph` document per item (`opens_forms`,
`opened_by`, `uses_queries`, `calls_modules`, `direct_macros`, `uses_tables`) — the context Layer 2
reads for every BD/DD. An export without some object type (no macros, no reports) is fine:
parsers exit 0 on an empty folder and the seeder skips missing folders.

---

### Layer 2 — AI design specification

**Entry point** `src/backend/workflow/layer2/runners/main.py`
**Orchestration** LangGraph `StateGraph` — BD node → DD node → `END`
**State** `PipelineState` TypedDict

#### BD flow — forms & reports only

```
bd1_bd_form  →  bd2_bd_mapping  →  bd3_bd_logic  →  bd4_bd_final
extract         map VBA            analyse          emit BD JSON
screens &       events &           business         + persist
controls        UI elements        logic
```

Output `layer2/output/bd_flow/bd4_bd_final/<name>.json`
Skipped entirely for `--type module` and `--type macro`.

#### DD flow — all item types

```
dd1_dd_skeleton  →  dd2_dd_mapping  →  dd3_dd_logic  →  dd4_dd_final
fetch source        build skeleton     LLM fills        emit DD JSON
data from           from DD1 + BD;     detail steps     + persist
MongoDB             queries →          per module
                    sheet 4/5
```

Output `layer2/output/dd_flow/{screen|report|macro|common}/dd4_dd_final/<name>.json`. Despite its
name, `dd1_dd_skeleton/` holds the source data DD1 fetched; the skeleton is DD2's output
(`dd2_dd_mapping/`), built without an LLM.

#### CLI

```bash
cd src/backend/workflow/layer2/runners

python main.py --item F_Login --type form --stage dev   # one item (form | report | module | macro)
python main.py --all-forms --stage dev                  # every form (also --all-reports / --all-modules)
python main.py --all-macros                             # every macro (DD only)
python main.py --all --stage production                 # forms + reports + modules
python main.py --all --dry-run                          # list work, call no LLM
```

After each item only that item is pushed to MongoDB (`bds` / `dds`).

`--stage` selects the model tier:

| Stage | Model | Use for |
| --- | --- | --- |
| `dev` | `qwen-max` | Development, quick iteration |
| `pilot` | `qwen-max` | UAT, quality review |
| `production` | `qwen3-coder-480b` (critical/high) · `qwen-max` (medium) · `qwen3-coder-next` (low) | Full document generation, routed by item complexity |

#### Cost tracking

Every LLM call is recorded by the `CostTracker` singleton
(`layer2/utils/cost_tracker.py`), priced per 1M tokens in USD:

| Model | Input | Output |
| --- | --- | --- |
| `qwen-max` | $2.80 | $8.40 |
| `qwen-plus` | $0.56 | $1.68 |
| `gpt-4o` | $2.50 | $10.00 |
| `gpt-4o-mini` | $0.15 | $0.60 |

Reports are appended after each run to `src/backend/logs/token_log.json`; runs started from the
console (through the gateway) also append to `src/backend/logs/token_log.xlsx`, which CLI runs do
not write. Both are written under a lock; an unreadable log is kept as `.bak` rather than
overwritten. The console's Layer 2 page downloads the workbook.

---

### Layer 3 — SQL migration

**Input** `queries` + `tables` (Layer 1) · **Working collection** `queries_v2` · **Output**
PostgreSQL DDL and reviewed, converted SQL

| Module | Responsibility |
| --- | --- |
| `table_converter.py` | Access types → DDL (pure, table-driven). PostgreSQL target; SQL Server / MySQL / ANSI for comparison. Identifiers are quoted only when required, so PostgreSQL's lower-case folding stays what generated code expects; optional `PRIMARY KEY` |
| `query_utils.py` | Rebuild SQL from the structured query (SELECT / UPDATE / DELETE / INSERT / TRANSFORM), query type, target table, bind variables |
| `seed_queries_v2.py` | Sync `queries` → `queries_v2`: new queries start `pending`; re-seeding refreshes source fields and never touches review fields |
| `router.py` | list / get / update / convert query, stats, list tables, convert table schema |
| `postgres_migrator.py` | Create tables through `psql` — `--dry-run`, `--table NAME`, `--output schema.sql`; exits 1 if any table failed |

```
MongoDB (queries · tables) ──seed──► queries_v2 ◄── review UI (/layer3)
        │                               │
        ├─ table_converter.py           └─ router.py::convert_query   LLM: Access SQL → PostgreSQL
        └─ postgres_migrator.py   DROP + CREATE per table (one transaction each)
```

Review workflow guarantees: a failed or unparseable LLM answer marks the query `error` and keeps
the stored `target_sql`; saving only overwrites the fields the client sent. The console's
**Test** button runs a *static* check (`api/v1/layer3/staticSqlCheck.ts` — leftover Access
functions, `TOP n`, `#date#` literals, form references, quoting, parentheses) and says so; it
never executes SQL.

> [!WARNING]
> Layer 3 covers `CREATE TABLE` (+ optional primary keys). Index / FK migration and rollback
> scripts are open items in [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) §4.1. Always review
> `postgres_migrator.py --dry-run` output first: it drops existing tables.

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

The templates are **Japanese** and every label locator is bilingual, so filling works with either
language. The four DD fillers share `scripts/dd_common.py`.

**Translation engine** (`excel_translator.py`) — when `TARGET_LANGUAGE` /
`config.json → localization.target_language` is `"en"`:

- Template **label** cells (recorded before filling) are translated via `JP_EN_MAPPING`; values
  that come from the BD/DD JSON and formula cells are left exactly as generated
- Sheet names translated (e.g. `変更履歴` → `Change History`), with formula references rewritten
- `restore_japanese_sheet_names()` reverses the sheet renaming

Alongside `.xlsx`, `layer4/server.py` emits a `.docx` rendition (needs `python-docx`); a Word
failure is reported as `docx_error` instead of a dead link. If an item has no Layer 2 output yet,
generation fails with "not generated yet" rather than rendering template samples, and no
fabricated change history is added.

---

### Layer 5 — Automated code generation

**Input** DD JSON + Access→Avalonia name mapping · **Output** compiling C# / AXAML

Example for `F_Login`, whose English names come from
`agents/graphview/outputs/forms/listFormJpToEn.json`; repositories and entities are one per table:

| Agent | Generates | Deployed to |
| --- | --- | --- |
| `ui` (view) | `Views/FLoginView.axaml` | `vba_brain.UI.Avalonia/Views/` |
| `ui` (viewmodel) | `ViewModels/FLoginViewModel.cs` | `vba_brain.UI.Avalonia/ViewModels/` |
| `service` | `Services/FLoginService.cs` + `Interfaces/IFLoginService.cs` | `vba_brain.Application/` |
| `repo` | `Persistence/Repositories/<Table>Repository.cs` | `vba_brain.Infrastructure/` |
| `repo` (interface) | `Interfaces/I<Table>Repository.cs` | `vba_brain.Domain/` |
| `repo` (entity) | `Entities/<Table>Entity.cs` | `vba_brain.Domain/` |
| `report` | `Views/Reports/<Name>Report.rdlc` for a report; PDF / print / close handlers in a form's ViewModel | `vba_brain.UI.Avalonia/` |
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
| `queries` | L1 | Access query definitions (structured `query`, original `sql`, params) |
| `modules` | L1 | VBA standard modules — procedures, functions, constants |
| `macros` | L1 | Macro action sequences |
| `tables` | L1 | Table schemas — columns, types, constraints |
| `reference_map` | L1 | The whole cross-reference map from `aggregator.py` (one document) |
| `dependency_graph` | L1 | One document per item: what it opens / is opened by / uses |
| `graphs` | L1 | One Cytoscape graph per item, from `data/graphs/` |
| `queries_v2` | L3 (read by L2, L5) | Queries under migration review: source fields + `target_sql`, `conversion_status`, … |
| `bds` | L2 | Business Design documents |
| `dds` | L2 | Detailed Design documents |
| `agent_repo` | L5 | Repository contract artifacts consumed by `agent_service` |
| `agent_service` | L5 | Service contract per form, written by the service agent |
| `agent_logic` | L5 | Logic contract per form (the generated ViewModel methods), written by the logic agent |
| `agent_graphview` | L5 | GraphView `mapping_` / `dependency_` / `review_<form>.json` documents |

Layer 1 and Layer 2 collection names are fixed in code (`seed_db.py`, `layer2/config.py`,
`layer2/runners/push_to_mongo.py`). `layer5/core/config.py` reads `MONGO_COL_*` overrides
(`MONGO_COL_DDS`, `MONGO_COL_AGENT_REPO` and friends), but only Layer 5 code that uses its constants
follows them — the logic agent always reads `dds` and `bds`, for example.

---

## 🔌 gRPC API gateway

**Port** `50051` · **Entry** `src/backend/api_gateway/grpc_server.py` · **Contract**
`src/backend/protos/workflow.proto`

- **Bind address** — `GRPC_HOST` (default `localhost`, i.e. not reachable from the network) and
  `GRPC_PORT`, or `config.json → grpc.host / grpc.port`.
- **Authentication** — set `GRPC_AUTH_TOKEN` (or `config.json → grpc.auth_token`) and every RPC
  must carry `authorization: Bearer <token>`, otherwise it fails with `UNAUTHENTICATED`. The
  console's API routes attach the header when they see the same variable; `start.py` passes it to
  them.
- **TLS** — set `GRPC_TLS_CERT` and `GRPC_TLS_KEY` (PEM files, or `config.json → grpc.tls_cert /
  tls_key`; relative paths start at the repo root) and the gateway serves TLS only; setting just
  one of them stops it at startup. The console then needs `GRPC_TLS_CA`, the PEM file to trust
  (the gateway certificate itself when it is self-signed), or `GRPC_TLS=1` for a publicly trusted
  certificate — `start.py` sets `GRPC_TLS_CA` for you. The certificate must name the host the
  console connects to (`localhost` by default). Without TLS the token crosses the network in
  clear text, so keep a plaintext gateway on loopback.
- **Input validation** — item names, document kinds and file names that become path components
  are rejected if they contain `/`, `\`, NUL, `..` or a drive prefix.

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
| `RunBdFlowExtract` | `screen_name` | Run BD1 + BD2 only (no LLM) |
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

Regenerate the Python stubs after editing the `.proto` (with `grpcio-tools==1.71.2` from
`requirements-dev.txt` — CI regenerates them and fails if the committed stubs differ):

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

Built into `src/backend/common/config.py` (Alibaba Cloud DashScope). All but `qwen3-coder-next` are
also listed in `config.example.json → llm_providers.alibaba.models`; the console's model dropdown
shows only the models listed there in your `config.json`, so add `qwen3-coder-next` to pick it:

| Model ID | Context | Used by |
| --- | --- | --- |
| `qwen-max` | 128K | L2 dev/pilot, L3 migration, L2 production (medium) |
| `qwen3-coder-480b-a35b-instruct` | 262K | L5 service/repository, L2 production (critical/high) |
| `qwen3-coder-next` | 262K | L2 production (low complexity) |
| `qwen3-235b-a22b-instruct-2507` | 262K | Default model the console's Layer 5 page sends to the logic and service agents |
| `qwen-plus-2025-07-28` | 262K | L5 viewmodel/AXAML/entity/DTO/mapper, fallback |

OpenAI, Anthropic, and Groq providers are wired in `common/config.py` but optional — add a key
to `config.json` and select the model at runtime.

### Runtime overrides

```bash
export L2_STAGE=production                                           # model tier for Layer 2
export LAYER5_SERVICE_MODEL=qwen3-coder-480b-a35b-instruct            # per-role override
export MODEL_OVERRIDE_L2_PROD_MEDIUM=qwen3-coder-480b-a35b-instruct  # Layer 2 production, medium tier
export MODEL_OVERRIDE_QWEN_MAX=qwen3-coder-480b-a35b-instruct         # Layer 3 conversions that ask for qwen-max
```

`MODEL_OVERRIDE_<NAME>` (or `config.json → model_overrides.<name>`) is read only by `get_model()` in
`common/config.py`: `<NAME>` is the name it is asked for, upper-cased with `-` replaced by `_`, and
the value must be a model id it knows (built in, or listed in `config.json`). Layer 2 asks for
`l2-dev-model`, `l2-pilot-model` and `l2-prod-<critical|high|medium|low>`, Layer 3 for its conversion
model, Layer 5 for each role's model id — so `MODEL_OVERRIDE_QWEN_MAX` does not change Layer 2.

### Quota exhaustion & fallback

When a model returns HTTP 403 `AllocationQuota.FreeTierOnly`, Layer 2 fails fast (no retry
sleeps) and walks the requested model's whole fallback chain from `layer2/utils/model_router.py`,
skipping models it already tried:

```
qwen3-coder-480b-a35b-instruct → qwen3-coder-next → qwen3-coder-plus → qwen-max → qwen-plus
qwen3-coder-next               → qwen3-coder-480b → qwen3-coder-plus → qwen-max → qwen-plus
```

```python
from utils.llm_client import LLMClient        # with src/backend/workflow/layer2 on sys.path
from config import DEV_MODEL

text, usage = LLMClient().chat_with_usage(DEV_MODEL, system_prompt, user_prompt)
```

To resolve quota problems: disable *"use free tier only"* in the
[DashScope console](https://dashscope.console.aliyun.com/), swap in another key, or wait for the
monthly reset. Track spend in `src/backend/logs/token_log.json` (every run) or `token_log.xlsx`
(console runs).

---

## ⚙ Configuration

Each file is copied from a tracked template:

| File | Template | Holds |
| --- | --- | --- |
| `config.json` | `config.example.json` | LLM keys, model routing, MongoDB/PostgreSQL, ports, localization |
| `infa/.env` | `infa/.env.example` | Docker Compose credentials for MongoDB / Mongo Express / PostgreSQL |
| `.env` *(optional)* | `.env.example` | Overrides that `src/backend/common/config.py` loads with `python-dotenv` (`start.py` does not read it — see [Environment variables](#-environment-variables)) |
| `src/wpf/vba_brain.UI.Avalonia/appsettings.json` | `appsettings.example.json` (same folder) | `DatabaseConfig:ConnectionString` — the PostgreSQL connection the Avalonia app uses |

Minimum fields to fill in `config.json`:

- `llm_providers.alibaba.api_key` — DashScope API key
- `mongodb.uri` — e.g. `mongodb://vba_brain:<pw>@localhost:27017/vba_brain_core?authSource=admin`
- `postgresql.*` — host / port / database / username / password (Layer 3). `connection_string` is
  not used by any layer; the Avalonia app takes its connection string from `appsettings.json` (above)
- `grpc.auth_token` — optional; set a long random string before the gateway leaves `localhost`

Every model listed under `llm_providers.<provider>.models` (for the providers the client supports:
alibaba, openai, anthropic, groq, deepseek, megallm) is selectable at runtime — the console's model
dropdown lists exactly these.

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

`start.py` frees the two ports by stopping only the process *listening* on them, passes
`GRPC_SERVER_ADDRESS` / `GRPC_AUTH_TOKEN` / `GRPC_TLS_CA` to the console, never overrides variables you already
exported, and stops each service's whole process tree on Ctrl+C. The dev server listens on
`127.0.0.1` only.

### Full batch pipeline

```bash
cd src/backend/workflow/layer1
python run_all.py                    # everything below, in order
python run_all.py --list             # step keys
python run_all.py --from seed        # resume from a step
python run_all.py --only tables,queries
python run_all.py --skip layer3      # what the web console runs (no DROP/CREATE in PostgreSQL)
python run_all.py --dry-run          # print the plan
python run_all.py --keep-going       # don't stop at the first failed step
```

| # | Key | Script | Step |
| --- | --- | --- | --- |
| 1 | `tables` | `parser/table_parser.py` | Parse tables |
| 2 | `queries` | `parser/query_parser.py` | Parse queries |
| 3 | `forms` | `parser/frm_parser.py` | Parse forms & reports |
| 4 | `macros` | `parser/macro_parser.py` | Parse macros |
| 5 | `modules` | `parser/modules_parser.py` | Parse modules |
| 6 | `aggregate` | `aggregator.py` | Aggregate cross-references |
| 7 | `seed` | `seed_db.py` | Seed everything → MongoDB (+ `dependency_graph`) |
| 8 | `seed-queries` | `layer3/sql_migration/seed_queries_v2.py` | `queries` → `queries_v2` (Layer 2 reads it) |
| 9 | `layer2` | `layer2/runners/main.py --all --stage dev` | Generate BD + DD |
| 10 | `layer3` | `layer3/sql_migration/postgres_migrator.py` | Create tables in PostgreSQL |

### Layer 3 table migration on its own

```bash
cd src/backend/workflow/layer3/sql_migration
python postgres_migrator.py --dry-run --output schema.sql   # review first
python postgres_migrator.py                                 # DROP + CREATE every table
```

### Layer 5 code generation

```bash
cd src/backend/workflow/layer5
python run_codegen_all.py    # the five sample forms: F_Login, F_Menu, F_ProductDetail, F_ProductList, F_TestForm
python run_codegen_all.py --form F_Login   # selected forms only (repeatable)
```

### Avalonia desktop app

The app reads its PostgreSQL connection from `appsettings.json`, not `config.json`. Create it once
from the tracked template and set `DatabaseConfig:ConnectionString`:

```bash
cp src/wpf/vba_brain.UI.Avalonia/appsettings.example.json src/wpf/vba_brain.UI.Avalonia/appsettings.json
```

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
| DD JSON | `layer2/output/dd_flow/{screen\|report\|macro\|common}/dd4_dd_final/<name>.json` | JSON |
| BD workbook | `src/excel_outputs/BD/<type>/<name>.xlsx` | XLSX (+ `.docx`) |
| DD workbook | `src/excel_outputs/DD/<type>/<name>.xlsx` | XLSX (+ `.docx`) |
| Token / cost log (Layer 2) | `src/backend/logs/token_log.json` / `.xlsx` | JSON / XLSX |
| Token report (Layer 5) | `src/backend/workflow/layer5/logs/token_report.json` | JSON |
| Generated C#/AXAML | `layer5/agents/<agent>/outputs/<form>/` → deployed into `src/wpf/vba_brain.*/` (files with no project mapping are staged in `layer5/output/`) | `.cs` / `.axaml` |
| Dependency graph | `data/graphs/<name>.json` | JSON |

All of these are runtime artifacts, and all are git-ignored except some Layer 5 output:
`layer5/agents/{ui,logic,report}/outputs/` and `layer5/agents/logic/inputs/` are not ignored (several
of their files are committed), nor are the files deployed into `src/wpf` (e.g. `FLoginView.axaml` is
committed). The repo and service agent outputs and `layer5/output/` are ignored.

`clean_generated_files.py --dry-run` lists (and without the flag deletes) the Layer 5 files
deployed into `src/wpf` when you want a fresh generation; hand-written infrastructure there and the
shared `ViewModelBase.cs` are left alone.

---

## 🌐 Environment variables

A variable exported in your shell wins over `config.json`. `src/backend/common/config.py` also loads
`.env` (repo root, `src/backend/`, `src/backend/common/`) with `python-dotenv`, which never replaces
a variable that is already set — so for scripts you run directly the order is shell → `.env` →
`config.json` → default. `start.py` does not read `.env`: it hands both services `MONGO_URI` /
`MONGO_DB` from your shell or else `config.json`, so `.env` values for those two are ignored under
`start.py`; and `GRPC_HOST` / `GRPC_PORT` / `GRPC_AUTH_TOKEN` / `GRPC_TLS_CERT` / `GRPC_TLS_KEY` set
only in `.env` reach the gateway but not the console — keep them in `config.json` or export them.
Names verified against `src/backend/common/config.py` and `layer5/core/config.py`.

<details open>
<summary><b>Infrastructure</b></summary>

| Variable | Purpose | Default |
| --- | --- | --- |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGO_DB` | MongoDB database name | `vba_brain_core` |
| `GRPC_HOST` / `GRPC_PORT` | Gateway bind address | `localhost` / `50051` |
| `GRPC_AUTH_TOKEN` | Shared bearer token for every RPC (gateway and console) | unset = auth off |
| `GRPC_TLS_CERT` / `GRPC_TLS_KEY` | Gateway: PEM certificate chain / private key — both set = TLS only | unset = plaintext |
| `GRPC_TLS_CA` / `GRPC_TLS` | Console: PEM file to trust / `1` to trust the system roots | unset = plaintext |
| `GRPC_SERVER_ADDRESS` | Where the console's API routes reach the gateway | `localhost:50051` |
| `PYTHON_BIN` | Python interpreter the console's API routes spawn | `python3`, then `python` |
| `MONGO_COL_DDS` / `MONGO_COL_AGENT_REPO` | Layer 5 collection-name overrides (Layer 2 always writes `dds`; the logic agent always reads it) | `dds` / `agent_repo` |
| `POSTGRES_CONN` | Full ADO.NET-style connection string — parsed by `common/config.py` but not used by any layer | `postgresql.connection_string`, else built from the parts below |
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
| `DEFAULT_LLM_MODEL` | Parsed by `common/config.py` but not used by any layer | `qwen-max` |
| `LAYER2_DEV_MODEL` / `LAYER2_PILOT_MODEL` | Layer 2 per-stage model | `qwen-max` |
| `LAYER3_MIGRATION_MODEL` | Layer 3 query-conversion model when the request names none | `qwen-max` |
| `LAYER4_MIGRATION_MODEL` | Parsed by `common/config.py` but not used by any layer | `qwen-max` |
| `LAYER5_DEFAULT_MODEL` / `LAYER5_SERVICE_MODEL` / `LAYER5_VIEWMODEL_MODEL` / `LAYER5_REPOSITORY_MODEL` | Layer 5 per-role models | `qwen3-coder-480b-a35b-instruct` / `qwen-plus-2025-07-28` |
| `MODEL_OVERRIDE_<NAME>` | Swap the model `get_model()` resolves for `<NAME>` — see [Runtime overrides](#runtime-overrides) | — |

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

With TLS on (`GRPC_TLS_CERT` / `GRPC_TLS_KEY`), the console must use TLS too and trust the
certificate: set `GRPC_TLS_CA` to it (or start both with `python start.py`, which does), and make
sure the certificate names the host in `GRPC_SERVER_ADDRESS` (`localhost` by default).

</details>

<details>
<summary><b>gRPC calls fail with UNAUTHENTICATED</b></summary>

The gateway has `GRPC_AUTH_TOKEN` set but the console doesn't (or has a different value). Start
both with `python start.py` (it passes on a token from your shell or `config.json`, not one that is
only in `.env`), or export the same `GRPC_AUTH_TOKEN` in the shell that runs `yarn dev`.

</details>

<details>
<summary><b>Console routes fail with "python: command not found"</b></summary>

The API routes that spawn Python try `python3` before `python`. Point them at a specific
interpreter (e.g. a virtualenv) with `PYTHON_BIN=/path/to/python`.

</details>

<details>
<summary><b>MongoDB authentication failed</b></summary>

The Docker Compose stack enables root auth, so the URI needs `authSource`:

```
mongodb://vba_brain:<password>@localhost:27017/vba_brain_core?authSource=admin
```

</details>

<details>
<summary><b>TypeError on <code>str | None</code> at import</b></summary>

You are on Python 3.9. Some modules (`layer1/parser/frm_parser.py`, `layer4/server.py`,
`api_gateway/grpc_server.py`, `start.py`) use PEP 604 unions in annotations without
`from __future__ import annotations`, so loading them fails with
`TypeError: unsupported operand type(s) for |`. Use Python **3.10+**.

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
(`layer2/runners/main.py --item <name> --type <type>`), then export.

</details>

---

## 📚 Project docs

| Document | Contents |
| --- | --- |
| [`docs/REVIEW_REPORT.md`](docs/REVIEW_REPORT.md) | Full-source review (2026-10): findings by layer, what was fixed, follow-ups (Vietnamese) |
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
ruff check src/backend tests start.py start_wpf.py clean_generated_files.py infa/scripts
pytest && pytest tests/layer5              # backend tests (two sessions)
(cd src/frontend && yarn lint && yarn typecheck && yarn test && yarn build)
dotnet build src/wpf/vba_brain.slnx        # target app
```

Hard rules: no secrets in tracked files, no hard-coded API keys or hosts (everything goes through
`config.json` / env), `yarn` never `npm`, and any new LLM provider is a `config.json` change
rather than a code change.

---

## 📄 License

[MIT](LICENSE) © baoluong2900
