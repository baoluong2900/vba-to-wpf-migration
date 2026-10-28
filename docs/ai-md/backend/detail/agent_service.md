# Agent Service

**File:** `agents/service/agent_service.py`  
**Pipeline step:** #2 (after Agent Repo)

## Purpose

Generates the Application Service layer: `IService.cs` interface and `Service.cs` implementation bridging ViewModels and Repositories.

## Flow

```
MongoDB (dds, agent_repo, forms) + Repo contract
    │
    ▼
build_service_input()       → assemble unified service input in-memory
    │
    ▼
tool_service_gen.py         → deterministic IService + Service (default, no LLM)
  OR
LLM (agent_service_form.md) → LLM-generated Service.cs (if mode=llm)
    │
    ▼
outputs/<FormName>/Application/
```

**Default mode is `tool` (deterministic).** LLM mode is opt-in via `AgentInput`.  
The interface (`IService.cs`) is always generated deterministically via `tool_service_gen.generate_service_iface_methods`.

## Key Files

| File | Role |
|------|------|
| `agent_service.py` | Main agent |
| `tool_service_gen.py` | Deterministic service + interface generator |
| `configs/method_names.json` | Method name mapping config |
| `configs/response_field_mapping.json` | Response DTO field mapping |
| `prompts/agent_service_form.md` | LLM prompt (LLM mode only) |

## Contract rules

- `methods` are keyed by the BD `module_id` — the same F-ID the UI skeleton and Agent Logic use
  (`core/fid_resolver.py`); `vba_handler` comes from the BD event `notes`, and `method_name`
  matches the generated `IService`.
- Repository calls follow the repository's own input contract (order and types); a DTO input
  becomes `new XInputDto { … }`. Request DTOs declare exactly those properties.
- DTO namespaces come from `core.naming.dto_namespace(form, "Requests"|"Responses")`, so
  Japanese or punctuated form names still produce valid C#.
- Triggers are recognised in Japanese and English (`On Click`, `After Update`, …).
- **Credentials:** login-style events get a parameterised `VerifyCredentialsAsync`
  (`COUNT(1) … WHERE "<id>" = @id AND "<pass>" = @password`) and return `Authenticated`;
  password columns are never selected or returned.

## Data Sources (in priority order)

1. `AgentInput.dd_json` (if set — overrides MongoDB)
2. MongoDB `dds` collection
3. MongoDB `agent_repo` collection (repo contract)
4. MongoDB `forms` collection (VBA events)
5. Local file fallback: `inputs/<FormName>_service_input.json`

## Form Name Resolution

Uses both:
- `agents/graphview/outputs/forms/listFormJpToEn.json`
- `agents/graphview/outputs/reports/listReportJpToEn.json`

Reports override forms if same name exists.

## Model

`L5_ROUTING["service"]` → `qwen3-coder-480b` (default, only used in LLM mode)

## Outputs

Per-run artifacts (git-ignored):

```
agents/service/outputs/<FormName>/
├── <FormName>.json                       ← service contract
└── Application/
    ├── Interfaces/I<Feature>Service.cs
    └── Services/<Feature>Service.cs
```

## Optional: Save Input JSON

Set `AgentInput.persist_service_input_json=True` or CLI `--save-input` to write `inputs/<FormName>_service_input.json` for debugging.
