# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
aims at [Semantic Versioning](https://semver.org/spec/v2.0.0/). Dates are `YYYY-MM-DD`.

---

## [Unreleased]

Full-source review and cleanup (2026-10-28) — the findings, the reasoning behind each fix and the
open follow-ups are in [`docs/REVIEW_REPORT.md`](docs/REVIEW_REPORT.md).

### Security
- **gRPC gateway** binds `localhost` by default instead of `[::]` (all interfaces); optional
  shared bearer token (`GRPC_AUTH_TOKEN`, `api_gateway/auth.py`) checked in constant time; item
  names / doc kinds / file names that become path components are validated at the gateway and
  again in Layer 2 (`utils/paths.py`) — `screen_name="../../config"` could previously overwrite
  arbitrary `*.json` files.
- MongoDB URIs are redacted before logging (`common.config.redact_uri`); the Layer 1 seeder's
  output, including the password, was streamed to the browser.
- `infa/mongo-init/01_init_user.js` no longer creates a second root account with a hard-coded
  password (it also collided with the default `MONGO_INITDB_ROOT_USERNAME` on first start).
- `System.Security.Cryptography.Pkcs` pinned to 10.0.14 (transitive via Microsoft.Data.SqlClient;
  9.0.x has GHSA-846f-f764-76mx, high, and GHSA-2fmv-rv2c-59x7, moderate).
- `start.py` frees ports by stopping only the process *listening* on them — `lsof -i:PORT` also
  matched clients such as the browser, which were `kill -9`ed.
- Git history scanned for leaked secrets: no `config.json`/`.env` was ever committed and no API
  key patterns were found.
- **Web console:** `/api/v1/layer5/run-agent` interpolated `phase` / `test_agents` from the request
  body into a shell command (remote code execution) — every Python / `dotnet` call now uses
  `execFile` / `spawn` with argument arrays; request names pass `isSafeName` (Japanese names
  allowed, separators / `..` / drive prefixes / leading `-` rejected).
- Generated login services selected the whole `T_ID_Pass` table and returned every user's
  plaintext password to the view model; they now call a parameterised `VerifyCredentialsAsync`
  and return `Authenticated`, and password columns are never selected.
- `src/proxy.ts` rejects cross-site POST/PUT/PATCH/DELETE to `/api/**`; `yarn dev` binds
  `127.0.0.1`; `/api/v1/layer1/extract` is POST-only and never starts the PostgreSQL migration
  (a plain `GET`, e.g. an `<img>` tag on any page, used to run the whole pipeline).

### Added
- **Tests:** `pyproject.toml` (pytest + ruff), `tests/backend/` and `tests/layer5/` (separate
  session), frontend `yarn test` (`node --test` with TypeScript type stripping, no new
  dependency). Layer 1 parsers run end to end on the fixture export.
- **CI:** ruff, pytest (both sessions, Python 3.10–3.12), a check that the committed gRPC stubs
  match `workflow.proto`, frontend type check (`yarn typecheck` generates the Next.js types first,
  so it passes on a fresh checkout) + unit tests, a .NET build job and a vulnerable-NuGet gate.
- `run_all.py`: step keys and `--list`, `--from`, `--only`, `--skip`, `--dry-run`, `--keep-going`;
  new step `seed-queries` (`queries` → `queries_v2`) before Layer 2.
- `postgres_migrator.py`: `--dry-run`, `--table`, `--output`; exit code 1 when a table fails.
- Layer 1 writes the `dependency_graph` collection (one document per item: `opens_forms`,
  `opened_by`, `uses_queries`, `calls_modules`, `direct_macros`, `uses_tables`) — Layer 2 reads it,
  but nothing wrote it, so every BD/DD had an empty dependency context.
- `query_parser.py` keeps the original Access SQL as `sql`; Layer 3 converts that text.
- Every model listed under `config.json → llm_providers.<provider>.models` (supported providers) is
  now resolvable; models picked in the console used to fall back silently to `qwen-max`.
- `config.example.json → grpc` and `.env.example` entries for `GRPC_HOST`, `GRPC_PORT`,
  `GRPC_AUTH_TOKEN`, `GRPC_SERVER_ADDRESS`, `PYTHON_BIN`.
- `GetModelsHealth` results are cached for 5 minutes and stragglers are reported as `timeout`
  instead of discarding every result.
- Layer 2: `--type macro` / `--all-macros`; stage- and complexity-aware model routing for BD and DD.
- Avalonia app: DI container with configuration + `IDbConnectionFactory`, and a placeholder main
  window instead of an invisible process when no generated screen is wired up.
- `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md`, and this changelog.
- GitHub Actions CI (`.github/workflows/ci.yml`): backend compile check, frontend lint, frontend
  production build.
- Issue and pull-request templates under `.github/`.
- Root `.env.example` and `.nvmrc` so environment expectations are explicit.

### Fixed
- **Layer 3 review workflow, end to end:** saving a reviewed query always failed
  (`AttributeError` in the gateway); after fixing that, a save would have wiped `status`,
  `reviewer` and `notes` (proto3 empty strings) — now only sent fields are written; AI conversion
  succeeded server-side but the page always showed "Conversion failed" (`query` vs `result`
  response key); the query detail never loaded; the stats route read fields that `StatsResponse`
  does not have; an unparseable LLM answer was stored as `target_sql` with status `converted`;
  a failed conversion overwrote hand-reviewed SQL with the Access source.
- Layer 3 `table_converter.py`: `Long Text` → `VARCHAR(255)` (now `TEXT`), `LongBinary` →
  `BIGINT` (now `BYTEA`), `AutoNumber` / `Decimal` / `GUID` → `VARCHAR(255)` (now identity /
  `NUMERIC` / `UUID`); names with spaces or reserved words produced invalid DDL (now quoted only
  when required); a table without columns produced invalid SQL.
- Layer 3 `postgres_migrator.py` looked for `config.json` under `src/` and so always ran with user
  `postgres` and no password, ignoring `POSTGRES_*`; Mongo clients leaked per request; bind
  variables matched PostgreSQL `::casts` and `12:30` time values; `queries_v2` lost UPDATE /
  INSERT / DELETE statements (only the `WHERE` survived) and the fields Layer 2 reads.
- Layer 2: UI-formula retry loop never terminated (thousands of billed LLM calls before a
  `GraphRecursionError`); reports never reached the report branch; macros never reached the LLM;
  `--stage` had no effect on BD; quota fallback stopped after one hop; BD3 batch exceptions were
  swallowed and results merged by position; `None` query metadata crashed BD2; required flags were
  inverted ("False" is truthy); module handlers were never analysed (`functions` vs `procedures`);
  BD2 mappings were written to `layer2/agents/output`; DD read a BD3 file name BD never writes;
  module DD3 cache never hit; summary errors were written into deliverables as the description.
- Gateway: `ListForms` always failed (dicts into a `repeated string`); `GetBdStatus` never found
  report DDs; `GenBd` / `GenDd` / `GenAll` / `SeedQueries` / `GetStats` reported failures as
  success; `RunBdFlowFull` treated macros as forms.
- Layer 1: parsers looked for `src/VBA/…` (only worked on case-insensitive file systems, failed on
  Linux/CI); an export without macros or reports aborted the batch pipeline.
- `common/config.py`: fallback workspace root pointed at `src/` instead of the repo root; LLM
  usage callbacks leaked when a call raised.
- `start.py` no longer overrides variables you exported, no longer rewrites
  `api_gateway/.env`, and stops each service's whole process tree on Ctrl+C.
- Frontend: custom `Cache-Control` rule forced `no-store` onto hashed `/_next/static` assets;
  Layer 3 page used a hard-coded model id that does not exist (`deepseek-v4-pro`).
- Frontend: spawned `python`, which does not exist on macOS (now `PYTHON_BIN` → `python3` →
  `python`); Layer 4 downloads with Japanese file names threw in `Content-Disposition`; Layer 5
  file browser, token reports and the Access → .NET name maps pointed at `src/backend/layer5`
  (does not exist); source review looked up views by Access name; the Layer 5 pipeline did not
  wait for Agent Logic and Stop did not stop it; the token-stats call on page load always failed
  (`--input-only` sent to agents that reject it); a failed first MongoDB connect broke the routes
  until restart; stale responses could attach screen A's data to screen B (Layer 2, GraphView);
  SSE readers dropped events split across chunks; every Layer 2 page load pinged every configured
  model (billed); the Layer 3 error panel crashed the page when the route failed.
- **Layer 4 templates:** commit 02417d0 had replaced the six Japanese templates with
  machine-translated English copies while every locator searches for Japanese labels — DD
  workbooks came out with no detail sheets and empty SQL, BD events landed on unstyled rows, and
  template samples (project name, author, dates) shipped. The originals are restored and every
  locator is bilingual.
- Layer 4: `gen_dd` kept only the first detail spec; "なし" was rendered as SQL while the real
  `raw_sql` was dropped; header values overwrote labels (event sheets, `AR2`); the report item
  table started one row low; record sources were blank (`query_name` ignored); a missing Layer 2
  output was "generated" from raw Layer 1 data and reported as success; every `.docx` was an empty
  shell (wrong keys) and `docx_url` pointed at files that did not exist; the translator always ran
  (config looked up one directory too shallow) and translated user data and formulas substring by
  substring; the change-history title and headers were overwritten; report DDs kept the template's
  `RS020` identity and shipped its internal `QA` sheet; `screen_name` was joined into read and
  write paths unchecked.
- **Layer 5 (UI / Logic / pipeline):** the UI skeleton numbered F-IDs from `ui_event_map.json`
  while Service and Logic used BD module ids, so handlers were wired to the wrong logic (clicking
  Login ran the `taskkill` body) — one shared resolver (`core/fid_resolver.py`) now numbers
  everything; the build-fix loop overwrote the Logic-patched ViewModel with an LLM-"fixed"
  skeleton (first basename match) — files are de-duplicated and matched by resolved path; DI
  fields / DTO usings were emitted for services without methods (CS0234/CS0246); unmapped Access
  form events became raw C# event names (CS0103); system-event bodies were WPF code that did not
  compile on Avalonia (`sys_bodies.py` now emits Avalonia code); the Logic CLI always exited 0;
  `--fix` looked for files that are never written; the SERVICE prompt hard-coded F_Login's field;
  the password never reached the view model and AfterUpdate (the login) was never wired;
  `orchestrator.py` contained two concatenated copies and crashed on forms without a service
  contract; `file_writer` wrote to a non-existent staging path with no confinement; backups
  flattened every form's `method_outputs.json` into one file; undefined names in `agent_ui.py`
  (`form_name`, `form_config`). Layer 5 now resolves the same model registry as Layers 2/3 and
  writes `logs/token_report.xlsx`.
- **Layer 5 (repo / service / report / mapping / graphview):** re-running a form made
  `merge_csharp_code` delete the class or interface declaration (four tracked snapshots were
  already corrupted); repository classes with Japanese names were overwritten instead of merged;
  queries whose SQL only existed in `raw_sql` became empty stubs reported as success; Dapper
  never filled properties (it ignores `[Column]` — columns are now aliased); entities lacked
  `using vba_brain.Domain.Common`; service → repository calls ignored the repository's input
  contract (CS1501/CS7036 or silently swapped arguments); `fill_json.py` called `sys.exit(1)`
  from library code; the mapping agent's workflow root resolved to `src/backend`; the report
  agent pasted R005-specific WinForms ReportViewer code into Avalonia sources; `AS` alias
  splitting mangled column names (`Pass` → `s`); self-referencing queries recursed forever;
  substring table matching mapped different tables to one class; Access types (Long, Currency,
  Yes/No, …) fell back to `object`; English DD triggers were never recognised;
  `border_color_hex` was used before assignment and system colours were mis-mapped.
- **Layer 5, found by an offline end-to-end run** (Repo → Service → UI for the five sample forms
  with every LLM call blocked, then `dotnet build`: 0 errors, 0 warnings): the generated
  ViewModel did not declare properties the AXAML binds — unbound text boxes that VBA fills
  (`txtID`), or names that only differ in case (`txtProductID` vs `TxtProductID`) — so Avalonia
  compiled bindings failed with AVLN2000; `clean_generated_files.py` deleted `ViewModelBase.cs`,
  which only a full orchestrator run recreates.
- Avalonia app: 10 build warnings → 0 (`RelayCommand` exceptions no longer crash the app, login
  view gets the public constructor the XAML loader needs, Close raises `CloseRequested`).
- `src/backend/requirements.txt`: floors below what the generated gRPC stubs require
  (`grpcio>=1.71.2`, `protobuf` 5.x gencode); `python-docx` (Layer 4 Word export) and `protobuf`
  were missing.

### Removed
- Dead or broken entry points: legacy `src/frontend/src/app/api/layer3/*` (called Excel RPCs on
  the SQL client), `api/v1/layer3/stats`, `api/bd-agent` and its FastAPI-era fallbacks
  `layer2/runners/run_bd_agent.py` / `run_dd_agent.py`, `api/graph-wpf/{mapping,validate}`,
  the Agent Test pipeline step (its script never existed), `src/frontend/seed_db.js` (wrong
  paths; replaced by `seed_db.py`), `jsconfig.json`, `next.config.mjs` (shadowed by
  `next.config.js`).
- Unused Python dependencies: FastAPI, uvicorn, google-generativeai, langchain-core/-groq/-openai,
  jsonschema, psycopg2-binary, requests (`grpcio-tools` moved to `requirements-dev.txt`).
- Layer 4 `scripts/fix_templates.py` (translated every template in place as an import side
  effect — the source of the broken templates), `patch_translator.py` (one-shot codemod),
  `test_flogin.py` / `test_translate.py` (no assertions, never collected); the four DD fillers'
  copy-pasted helpers moved into `scripts/dd_common.py` (8,031 → 3,022 lines).
- Layer 5 dead modules: `agents/logic/{tool_method_merger,sync_vm_stubs,gen_code_behind,gen_vm_methods}.py`,
  `pipeline/patch_vm_from_output.py`, `core/utils.py`, the unused Entity/Interface/DTO Jinja
  templates, five uncalled `agent_ui.py` helpers; `run_codegen_test.py` is now
  `run_codegen_all.py --form NAME`.
- Layer 5 unused templates/prompts (`repo/config/repository*_template.json`,
  `repo/prompts/agent_repo.md`, `service/prompts/agent_service{,_macro,_module}.md`), the
  `tool_repo` CLI, `fill_json`'s parallel contract derivation; stale or corrupted generated
  artifacts untracked (`repo/outputs/**`, `service/outputs/**`, `mapping/outputs/*.json`,
  per-run graphview inputs/reviews, unused `list*Jp.json`) — name maps, configs and prompts stay.
- Broken utility scripts `infa/scripts/translate_templates.py`, `infa/scripts/update_prompts.py`;
  `src/vba/vba_source/run_tests.py` (now `tests/backend/test_layer1_parsers.py`); template
  leftovers `Class1.cs` ×3; the empty `src/wpf/vba_brain.UI.WPF/`.
- Layer 2 dead code (`fill_dd_macro_module.py`, the unused `call_with_fallback` / `_call_*`
  aliases, `_MinimalPipeline`, duplicated blocks and helpers); repo-wide, ~330 pyflakes findings
  (unused imports/variables, empty f-strings, redefinitions, undefined names) went to zero.
- From the git index (files kept locally, now git-ignored): `layer2/agents/output/`,
  `layer3/scratch/*`, `layer5/logs/token_report.json`, `src/frontend/reports/`.

### Changed
- Layer 4 no longer invents a revision history (`mock_change_history` defaults to off; the CLI
  has `--mock-change-history`), and Japanese text that comes from the BD/DD JSON is no longer
  partially translated — only template labels are.
- **README rewritten** and corrected against the source tree:
  - Python floor raised from 3.9 to **3.10+** — several modules use PEP 604 `X | None` without
    `from __future__ import annotations` (`layer1/parser/frm_parser.py`,
    `layer3/sql_migration/router.py`).
  - Node floor documented as **≥ 20.9** (Next.js 16 `engines.node`).
  - Frontend stack corrected to the installed versions: Next.js 16.2.4, React 19.2.4,
    TypeScript 6, Tailwind 4.
  - The `Layer3Service` (Excel) / `Layer4Service` (SQL migration) naming swap is now called out
    explicitly instead of being silently mismatched with the layer numbering.
  - Docker ports documented as `127.0.0.1`-bound, matching `infa/docker-compose.yml`.
  - Excel output paths corrected to `src/excel_outputs/{BD,DD}/<type>/` per
    `layer4/server.py`; `.docx` output documented.
  - Removed the `migration_queries` collection from the schema table — no code references it.
  - Removed the undocumented `L2_HUMAN_REVIEW` environment variable — it appears only in a
    docstring and has no implementation.
  - Added the environment variables that do exist but were missing:
    `DEFAULT_LLM_MODEL`, `LAYER2_DEV_MODEL`, `LAYER2_PILOT_MODEL`, `LAYER3_MIGRATION_MODEL`,
    `LAYER4_MIGRATION_MODEL`, `LAYER5_DEFAULT_MODEL`, `MONGO_COL_AGENT_REPO`,
    `DEEPSEEK_API_KEY`, `MEGALLM_API_KEY`, `STAGE`.
  - Fallback chain corrected to match `layer2/utils/model_router.py`.
  - Added a project-status notice, troubleshooting section, docs index, and quality gates.
- `docs/ai-md/backend/architecture.md` updated: the backend entry point is the gRPC gateway on
  `:50051`, and Layer 3/4/5 responsibilities now match the code.
- `.gitignore`: added `.codegraph/`.
- `infa/docker-compose.yml`: MongoDB, Mongo Express, and PostgreSQL port bindings moved from
  `0.0.0.0` to `127.0.0.1` (`docs/UPGRADE_PLAN.md` §1.2).

---

## [0.1.0] — 2026-06-01

First consolidated state of the five-layer pipeline.

### Added
- **Layer 1 — AST extraction.** Parsers for forms/reports, queries, macros, modules, and tables;
  `aggregator.py` cross-reference enrichment (`DoCmd`, `DLookup`/`DCount`/`DSum`, cross-form
  calls, module procedure calls, `CallSub`/`Application.Run`); `seed_db.py` and a `run_all.py`
  batch entry point.
- **Layer 2 — AI design specification.** LangGraph `StateGraph` pipeline with the BD flow
  (`bd1_extract` → `bd2_map` → `bd3_logic` → `bd4_final`) and DD flow (`dd1_skeleton` →
  `dd2_sql_map` → `dd3_llm_enrich` → `dd4_final`); stage-based model routing (`dev` / `pilot` /
  `production`); `CostTracker` token and USD accounting; quota-aware fallback chains.
- **Layer 3 — SQL migration.** Access → PostgreSQL type and DDL conversion, an LLM-assisted
  migration runner, query seeding preserving `raw_sql`, and review/convert endpoints.
- **Layer 4 — Excel export.** BD/DD workbook generation from six templates plus a
  Japanese→English translation engine with sheet-name restore, and optional `.docx` output.
- **Layer 5 — Code generation.** Agents for UI (AXAML + ViewModel), service, repository, logic,
  mapping, graphview, and report; a Jinja2 codegen engine; deployment into the correct Avalonia
  project directories; and a `dotnet build` verify loop with LLM auto-fix (max 3 iterations).
- **gRPC gateway** on `:50051` exposing four services generated from
  `src/backend/protos/workflow.proto`.
- **Next.js 16 web console** with one workspace page per layer, React Flow / Cytoscape dependency
  and mapping graphs, a token-cost view, and light/dark themes driven by CSS custom properties.
- **Infrastructure.** Docker Compose stack (MongoDB 7, Mongo Express, PostgreSQL 16),
  `start.py` (frontend + gateway) and `start_wpf.py` (Avalonia build/run) launchers, and a
  centralized configuration resolver (`env` → `config.json` → default).

### Changed
- Standardized on **Avalonia UI / .NET 10** as the sole desktop target; Layer 5 codegen, deploy,
  and the frontend Layer 5 routes all point at `vba_brain.UI.Avalonia`.
- Renamed Layer 2 stages for clarity: `s1`–`s4` → `bd1`–`bd4`, `d1`–`d4` → `dd1`–`dd4`.
- Translated the README and in-code comments to English.

### Removed
- **Oracle** support — PostgreSQL is the only migration target (`table_converter`, `router`
  prompts, `tool_repo` type map, `.proto`, and frontend dropdowns all cleaned).
- **Qdrant** vector store, from both code and infrastructure.
- The legacy landing page and stale mapping JSON / Japanese review documents.

### Security
- Docker Compose credentials moved to environment variables; generic passwords scrubbed from
  `config.example.json`.

---

[Unreleased]: https://github.com/baoluong2900/vba-to-wpf-migration/compare/main...HEAD
