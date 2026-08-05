# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
aims at [Semantic Versioning](https://semver.org/spec/v2.0.0/). Dates are `YYYY-MM-DD`.

---

## [Unreleased]

### Added
- `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md`, and this changelog.
- GitHub Actions CI (`.github/workflows/ci.yml`): backend compile check, frontend lint, frontend
  production build.
- Issue and pull-request templates under `.github/`.
- Root `.env.example` and `.nvmrc` so environment expectations are explicit.

### Changed
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
