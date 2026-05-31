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
tool_repo.py                → extract queries, parameters, table schemas
    │
    ▼
fill_json.py                → build repository JSON contract
    │
    ▼
Phase: Translate TODOs      → LLM batch call for unknown field/table names only
    │
    ▼
Jinja2 templates            → Entity.cs, DTO.cs, IRepository.cs, Repository.cs
    │
    ▼
outputs/<FormName>/
```

LLM is used **only** for translating unknown names (TODO batch phase). All code generation is deterministic via Jinja2.

## Key Files

| File | Role |
|------|------|
| `agent_repo.py` | Main agent |
| `tool_repo.py` | Core logic: extract queries, params, register columns |
| `fill_json.py` | Builds repository JSON contract from DD + table schemas |
| `config/name_config.json` | Name translation cache (Access → C# names) |
| `config/table_config.json` | Table schema config |
| `config/repository_template.json` | Repository structure template |
| `config/repository_ref_template.json` | Reference repository template |
| `prompts/agent_repo.md` | LLM prompt for TODO translation |
| `prompts/agent_translate.md` | LLM prompt for name translation |

## TODO Translation Phase

When `name_config.json` contains `"TODO"` values for `table_name`, `field_name`, `parameter_name`, `function_name`, or `cte_name`, the agent sends a batch LLM call to resolve them before code generation.

## Model

`L5_ROUTING["repository"]` → `qwen3-coder-480b` (default)

## Outputs

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
