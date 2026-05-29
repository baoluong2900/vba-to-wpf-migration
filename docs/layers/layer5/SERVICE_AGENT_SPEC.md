# Layer 5 — Service Agent Operational Specification

This document details the mechanics, directories, inputs, and execution rules of the **Service Agent** inside the Layer 5 C# Generation pipeline, responsible for producing `IService` interfaces and implementation files.

---

## 1. Pipeline Execution Role

- **Execution Order:** Executes immediately after **Agent Repo** has finalized the Domain Entities, DTOs, and Repository Interfaces.
- **Responsibility:** Produces the concrete Application Services layer for every screen. Each functional user action mapped inside the Detailed Design (DD) is translated into an async method orchestrating repository database calls.
- **Contract Enforcement:** Method names, properties, and types must exactly match the Repository contracts and ViewModel specifications.

---

## 2. Service Generation Directory Layout

```text
src/backend/workflow/layer5/agents/service/
├── agent_service.py            # Loader, orchestrator, and optional LLM-driven generation
├── tool_service_gen.py         # Primary deterministic C# codegen engine (No-LLM)
├── __init__.py                 # Export hooks for the ServiceAgent
├── inputs/                     # Local diagnostic fallback files (Offline only)
│   ├── {Form}_dd.json
│   ├── {Form}_repository_output.json
│   └── {Form}_service_input.json
├── outputs/                    # Snapshots of generated service files
│   └── {Form}/*.cs
└── prompts/
    ├── agent_service.md
    ├── agent_service_form.md   # Used in --llm mode to build service implementations
    ├── agent_service_macro.md
    └── agent_service_module.md
```

---

## 3. Unified In-Memory Input Specification

The loader `agent_service.build_service_input` aggregates data into a single unified JSON schema in RAM prior to execution:

| Asset Source | Target Repository Collection |
|---|---|
| Detailed Design (DD) | MongoDB **`dds`** collection (`find_one({ "name": form_name })`) |
| Repository Outputs | MongoDB **`agent_repo`** collection (`find_one({ "name": form_name })`) |
| Legacy UI Elements | MongoDB **`forms`** collection |

### Unified In-Memory JSON Schema:

```json
{
  "form_name": "F_Login",
  "screen_id": "F_Login",
  "screen_name": "F_Login",
  "source": {
    "dd_path": "",
    "repo_output_path": "",
    "dd_origin": "mongodb:dds",
    "repo_origin": "mongodb:agent_repo",
    "mongodb_forms": true,
    "filter_mode": "any_repo_signal"
  },
  "stats": {
    "detail_specs_total": 10,
    "events_kept": 4,
    "events_with_query_mappings": 2,
    "events_with_vba_query_op": 3,
    "vba_functions": 9
  },
  "events": [
    {
      "sheet_name_pattern": "詳細仕様書_F003",
      "module_id": "F003",
      "module_name": "Password Check",
      "event_trigger": "AfterUpdate",
      "event_content": "Processes password verification logic.",
      "steps": [...],
      "query_mappings": [],
      "matched_vba": {
        "handler": "txtPass_AfterUpdate",
        "type": "Sub",
        "input": "",
        "output": "",
        "code": "..."
      },
      "repo_signals": ["vba_query_op"]
    }
  ],
  "vba_functions": [
    { "handler": "Form_Open", "type": "Sub", "input": "...", "output": "", "code": "..." }
  ],
  "repository_contracts": {
    "repositories": [...],
    "dtos": [...],
    "entities": [...]
  }
}
```

---

## 4. Deterministic vs. LLM Generation Modes

1. **Deterministic Mode (Default):** Executed via `tool_service_gen.py`. It parses events, matches SQL queries with repository signatures, maps inputs to entity variables, and outputs clean C# service code using 0 LLM tokens.
2. **AI-Driven Mode (`--llm`):** Executed by passing the `--llm` flag. It feeds the unified input payload and `agent_service_form.md` system prompt to `L5LLMClient` (using model `qwen3-235b`) to handle complex calculations and highly customized validation logic.
