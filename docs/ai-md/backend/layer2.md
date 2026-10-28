# Backend — Layer 2 (BD / DD generation)

## Purpose
Layer 2 turns the Layer 1 AST in MongoDB into design documents: a **Business Design (BD)** for
every form/report and a **Detailed Design (DD)** for forms, reports, macros and modules. It runs
inside the gRPC gateway (`Layer2Service`) or from the CLI; there is no HTTP server.

## Flows (`src/backend/workflow/layer2/`)
| Flow | Stages | Output (`layer2/output/`, git-ignored) |
| --- | --- | --- |
| BD (`agents/bd_agent/bd_service.py`) | `bd1_extract` → `bd2_map` → `bd3_logic` (LLM) → `bd4_final` | `bd_flow/bd{1..4}_*/<name>.json` (bd3: `result_<name>.json`) |
| DD (`agents/dd_agent/dd_service.py`) | `dd1_skeleton` → `dd2_sql_map` → `dd3_llm_enrich` (LLM) → `dd4_final` | `dd_flow/{screen,report,macro,common}/dd{1..4}_*/<name>.json` |

`pipeline.py` wires them as a LangGraph `StateGraph` (BD → DD → END); `runners/push_to_mongo.py`
upserts the final documents into `bds` / `dds`.

## Inputs read from MongoDB
`forms`, `reports`, `modules`, `macros` (Layer 1), `queries_v2` (query context — seeded by
Layer 3's `seed_queries_v2.py`, which `run_all.py` runs before Layer 2) and `dependency_graph`
(`opens_forms`, `opened_by`, `uses_queries`, `calls_modules`, `direct_macros`).

## Model routing
- `utils/model_router.select_model(complexity, stage, model_id)` is the only entry point: an
  explicit `model_id` wins; otherwise `dev`/`pilot` use their fixed model and `production` routes
  by complexity. An unknown `model_id` logs one warning naming the substitute.
- `BDService(stage)` / `DDService(stage)`; the gateway passes `L2_STAGE`.
- Quota exhaustion (HTTP 403 `AllocationQuota.FreeTierOnly`) fails fast and walks the requested
  model's whole fallback chain (`FALLBACK_CHAIN`), never retrying a model twice.
- Every model listed in `config.json → llm_providers.<provider>.models` is resolvable (registered
  by `common/config.py`).

## Robustness rules
- **Names are path components:** `utils/paths.safe_child_path()` rejects `/`, `\`, NUL, `..` and
  any path that resolves outside its output directory; services raise `ValueError` early.
- **LangGraph routing functions are pure:** state changes happen in nodes (the UI-formula retry
  counter lives in a `retry` node) and every `invoke` passes an explicit `recursion_limit`.
- **LLM batch results are keyed by `module_id`,** text fields are coerced to `str`, missing ids are
  re-run individually; caches are validated by ids + a content hash.
- **Failures are visible:** a failed screen summary leaves the description empty and returns
  `summary_error`; failed DD3 modules come back in `dd3_failed_modules` while finished modules are
  saved incrementally.
- **Cost tracking** (`utils/cost_tracker.py`): one tracker per flow, written to
  `src/backend/logs/token_log.json` / `.xlsx` under a lock; an unreadable log is moved to `.bak`
  instead of being overwritten. Known limitation: concurrent gRPC requests share the global
  tracker, so per-request attribution can mix (see `docs/REVIEW_REPORT.md` §9).

## CLI
```bash
cd src/backend/workflow/layer2/runners
python main.py --item F_Login --type form --stage dev
python main.py --item A_Menu --type macro
python main.py --all-forms | --all-reports | --all-modules | --all-macros
python main.py --all --stage production
python main.py --all --dry-run
```

## Tests
`tests/backend/test_layer2_*.py` — model routing and fallback, BD graphs (retry loop, batch
keying), BD mapping helpers, IO/path helpers. LLM and MongoDB are faked.
