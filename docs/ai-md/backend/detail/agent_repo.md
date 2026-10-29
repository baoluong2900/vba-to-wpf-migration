# Agent Repo

**File:** `agents/repo/agent_repo.py`  
**Pipeline step:** #1 (first agent)

## Purpose

Generates the data access layer: Entity, DTO, IRepository interface, and Repository implementation (Dapper) for each form.

## Flow

```
MongoDB (queries_v2, tables) + DD JSON
    │
    ▼
tool_repo.py                → extract queries, parameters, table schemas; per-table repo JSON
    │
    ▼
Phase: Translate TODOs      → LLM batch call for unknown field/table names only
    │
    ▼
tool_repo.py                → Entity.cs, DTO.cs, IRepository.cs, Repository.cs (Dapper)
    │
    ▼
fill_json.py                → aggregate the per-table JSON into the form contract
    │
    ▼
outputs/<FormName>/ + outputs/<FormName>.json, merged into src/wpf
```

LLM is used **only** for translating unknown names (TODO batch phase). Code generation is
deterministic.

## Generated-code rules

- **SQL source order:** the DD `sql` block, then `queries_v2.target_sql` (Layer 3's reviewed
  PostgreSQL), then `raw_sql`. A query with no SQL at all becomes
  `throw new NotImplementedException(...)`; the run stays `success` but lists it in
  `metadata.stubbed_queries`, and the contract marks the method `implemented: false`.
- **Dapper mapping:** every selected column is aliased to its property name
  (`"製品名" AS "ProductName"`); `[Column]` attributes are documentation only.
- **Names:** table/schema lookups are exact or NFKC-normalised (no substring matching);
  colliding properties, methods, parameters, CTEs and class stems get numeric suffixes; every
  identifier goes through `core.naming.cs_identifier`.
- **Types:** Access names first (Long/AutoNumber → `int`, Currency → `decimal`, Yes/No → `bool`,
  Date/Time → `DateTime?`, …), then PostgreSQL types by longest prefix (INT8 → `long`,
  TIME/INTERVAL → `TimeSpan?`, UUID → `Guid`).
- **Re-runs merge, never truncate:** members are merged inside the existing type body only, so a
  re-run cannot delete the class/interface declaration; Japanese class names and base lists are
  supported.

## Key Files

| File | Role |
|------|------|
| `agent_repo.py` | Main agent |
| `tool_repo.py` | Core logic: extract queries, params, register columns |
| `fill_json.py` | Aggregates the per-table repo JSON into the form contract (`outputs/<FormName>.json`) |
| `config/name_config.json` | Name translation cache (Access → C# names) |
| `config/table_config.json` | Table schema config — not read by any code (`tool_repo.py` loads only `name_config.json`) |
| `prompts/agent_translate.md` | LLM prompt for name translation |

## TODO Translation Phase

When `name_config.json` contains `"TODO"` values for `table_name`, `field_name`, `parameter_name`, `function_name`, or `cte_name`, the agent sends a batch LLM call to resolve them before code generation.

## Model

The translation call uses task type `translate_config`, which is not an `L5_ROUTING` slot, so it
gets `DEFAULT_MODEL` (`LAYER5_DEFAULT_MODEL`, default `qwen3-coder-480b-a35b-instruct`) unless a
model override is passed. `L5_ROUTING["repository"]` / `LAYER5_REPOSITORY_MODEL` have no effect.

## Outputs

Per-run artifacts (git-ignored) — regenerated on every run:

```
agents/repo/outputs/
├── <FormName>.json                   ← repository contract
├── <FormName>/
│   ├── <Name>Entity.cs
│   ├── <Name>Repository.cs
│   └── I<Name>Repository.cs
└── repo/
    └── <Name>Repository.json         ← per-query repo spec
```
