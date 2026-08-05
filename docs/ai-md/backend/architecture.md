# Backend Architecture

> Engineering notes for AI coding agents and new contributors. Verified against the source tree;
> when this file and the code disagree, the code wins — please fix this file in the same PR.

## Overview

The backend parses legacy MS Access / VBA applications, reconstructs their design with LLM
agents, and generates modern C# Avalonia (MVVM, .NET 10) source code. It is organized as five
layers behind a single gRPC entry point.

**Entry point:** `src/backend/api_gateway/grpc_server.py` — a gRPC server on **port 50051**,
started by `python start.py` (or `python start.py --be-only`). There is no public HTTP API;
the Next.js console reaches the gateway through its own API routes under
`src/frontend/src/app/api/`.

**Data flow is one-directional through MongoDB.** No layer reads another layer's files directly —
each one reads MongoDB and writes back to it. That is what makes any single layer re-runnable in
isolation.

```
Access JSON exports (data/)
   → L1 parsers        → MongoDB: forms, reports, queries_v2, modules, macros, tables,
                                  dependency_graph
   → L2 BD/DD agents   → MongoDB: bds, dds        + layer2/output/**.json
   → L3 SQL migration  → PostgreSQL DDL
   → L4 Excel export   → src/excel_outputs/**
   → L5 code gen       → src/wpf/vba_brain.*/ (deployed) + dotnet build verify
```

---

## Layer 1 — AST extraction

`src/backend/workflow/layer1/`

- Parsers in `parser/` handle one artifact type each: `frm_parser` (forms **and** reports),
  `query_parser`, `macro_parser`, `modules_parser`, `table_parser`.
- `aggregator.py` performs cross-reference enrichment — it resolves the call graph Access hides in
  string literals: `DoCmd.OpenForm/OpenReport/OpenQuery/RunMacro/OutputTo`,
  `DLookup`/`DCount`/`DSum` targets, `Form_X.Proc()`, `[Forms]![Name]`, `Module.Procedure()`,
  `CallSub`, and `Application.Run`.
- `seed_db.py` pushes parsed JSON into MongoDB; `run_all.py` is the batch CLI that chains
  parse → aggregate → seed → Layer 2 → Layer 3.
- Graph output also lands on disk in `data/graphs/` for the web console.

## Layer 2 — AI design specification

`src/backend/workflow/layer2/`

- Orchestrated by a LangGraph `StateGraph` (`pipeline.py`): BD node → DD node → `END`, carrying a
  `PipelineState` TypedDict (`state.py`).
- **BD flow** (`agents/bd_agent/`, forms and reports only):
  `bd1_extract → bd2_map → bd3_logic → bd4_final`.
- **DD flow** (`agents/dd_agent/`, all item types):
  `dd1_skeleton → dd2_sql_map → dd3_llm_enrich → dd4_final`.
- Reads source data from **MongoDB** via `db/layer1_repo.py`, never from Layer 1 files.
- Output is always structured JSON under `layer2/output/{bd_flow,dd_flow}/…`, then pushed to the
  `bds` / `dds` collections by `runners/push_to_mongo.py`.
- `utils/`: `llm_client.py` (provider wrapper with `call_with_fallback`), `model_router.py`
  (stage → model plus quota fallback chains), `cost_tracker.py` (token and USD accounting),
  `vba_utils.py`.
- CLI: `runners/main.py --item / --all / --all-forms / --dry-run --stage dev|pilot|production`.

## Layer 3 — SQL migration

`src/backend/workflow/layer3/sql_migration/`

- `table_converter.py` — Access data types → PostgreSQL DDL. Pure function; the easiest module to
  unit-test.
- `postgres_migrator.py` — LLM-assisted runner: read table metadata → generate `CREATE TABLE` →
  execute against the target database.
- `seed_queries_v2.py` — seeds Access queries into MongoDB, preserving both `raw_sql` and `sql`.
- `router.py` — list / get / update / convert query, convert table schema, migration stats.
- PostgreSQL is the **only** supported target dialect; Oracle support was removed deliberately.

## Layer 4 — Excel specification export

`src/backend/workflow/layer4/`

- `server.py` exposes `gen_bd`, `gen_dd`, `gen_all`, `list_outputs`, and `download`; output root is
  `src/excel_outputs/`, split into `BD/<type>/` and `DD/<type>/`. Both `.xlsx` and `.docx` are
  emitted.
- `scripts/fill_*.py` fill the six workbook templates in `template/`
  (BD_Screen, BD_Report, DD_Screen ×3, DD_Report).
- `scripts/excel_translator.py` translates cell values and sheet names Japanese → English when
  `TARGET_LANGUAGE`/`localization.target_language` is `en`, and can restore the original sheet
  names afterwards.

## Layer 5 — C# / AXAML code generation

`src/backend/workflow/layer5/`

- `agents/`: `ui` (AXAML view + ViewModel), `service`, `repo`, `logic`, `mapping`, `graphview`,
  `report`. Each agent owns its prompts in `agents/<name>/prompts/*.md`.
- `codegen/`: Jinja2 engine plus C#/AXAML templates.
- `core/config.py`: model routing per generation role, MongoDB collection names, paths.
- `llm/`: `llm_client.py`, `token_tracker.py`.
- `pipeline/`: `orchestrator.py` (analyze → generate → deploy → verify),
  `deploy_to_source.py` (copies files into the right Avalonia project),
  `file_writer.py` (safe write with backup), `build_verify.py` (`dotnet build`, then LLM auto-fix
  for up to `MAX_RETRIES = 3` iterations).
- Generated code targets `src/wpf/vba_brain.UI.Avalonia`, `.Application`, `.Infrastructure`, and
  `.Domain`. Avalonia is the sole UI target — `vba_brain.UI.WPF/` is an empty leftover and is not
  in `vba_brain.slnx`.

---

## gRPC service naming — read this before touching `.proto`

`src/backend/protos/workflow.proto` defines four services, and **two of them do not match their
pipeline layer numbers:**

| Service | Actually serves |
| --- | --- |
| `Layer1Service` | Layer 1 — AST browsing |
| `Layer2Service` | Layer 2 — BD/DD generation, model health, token report |
| `Layer3Service` | **Layer 4 — Excel export** |
| `Layer4Service` | **Layer 3 — SQL migration** |

This is a historical swap kept for wire compatibility. Renaming it is a deliberate breaking change
tracked in `docs/UPGRADE_PLAN.md` §3.3 — do not rename incidentally. Any `.proto` edit must
regenerate `workflow_pb2.py` and `workflow_pb2_grpc.py` in the same commit:

```bash
python -m grpc_tools.protoc \
  -I src/backend/protos \
  --python_out=src/backend/api_gateway \
  --grpc_python_out=src/backend/api_gateway \
  src/backend/protos/workflow.proto
```

## Configuration

`src/backend/common/config.py` is the single resolver. `get_setting(env_key, json_path, default)`
checks, in order: **environment variable / `.env`** → **`config.json` path** → **default**.

Never hard-code API keys, hosts, ports, or model IDs elsewhere. Adding an LLM provider should be a
`config.json` change, not a code change. Keys stay server-side: the frontend receives only the
model *list*, via `Layer2Service.GetConfig`.

## Constraints to respect

- **Python 3.10+.** Some modules use PEP 604 `X | None` without
  `from __future__ import annotations` (`layer1/parser/frm_parser.py`,
  `layer3/sql_migration/router.py`), so 3.9 raises `SyntaxError`. Add the `__future__` import to
  any new module using those unions.
- **The gateway is unauthenticated** (`add_insecure_port`, `grpc_server.py:595`). Do not expose
  port 50051 beyond localhost — see `SECURITY.md`.
- **Use the module `logger`, not `print`,** in library code.
- **Windows:** run Python with `python -X utf8` to avoid console encoding failures.
