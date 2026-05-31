# Agent Mapping

**File:** `agents/mapping/agent_mapping.py`  
**Pipeline step:** Pre-step (runs once before all forms)

## Purpose

Builds Access → Avalonia name mapping tables for forms, events, modules, macros, and queries.  
Output is consumed by all other agents (especially Agent UI and Agent Service) for name resolution.

## Flow

```
MongoDB (forms, queries, macros, modules)
    │
    ▼
export_forms_layer1.py (subprocess)   → extract all Layer 1 data
    │
    ▼
outputs/forms_layer1.json             ← raw form list
outputs/events_layer1.json            ← raw event list
outputs/queries_layer1.json
outputs/macros_layer1.json
outputs/modules_layer1.json
    │
    ▼
LLM (agent_mapping_macro.md)          → macro JP → EN name mapping
LLM (agent_mapping_module.md)         → module JP → EN name mapping
    │
    ▼
outputs/form_access_to_wpf.json       ← Access form → Avalonia View/ViewModel names
outputs/event_access_to_dotnet.json   ← Access event → .NET event names
outputs/query_access_to_dotnet.json
outputs/macro_access_to_dotnet.json
outputs/module_access_to_dotnet.json
    │
    ▼
docs/mappings/                        ← copy for documentation
```

## Key Files

| File | Role |
|------|------|
| `agent_mapping.py` | Main agent |
| `graphview/inputs/export_forms_layer1.py` | Exports Layer 1 data from MongoDB |
| `prompts/agent_mapping_macro.md` | LLM prompt for macro name mapping |
| `prompts/agent_mapping_module.md` | LLM prompt for module name mapping |

## Outputs

```
agents/mapping/outputs/
├── forms_layer1.json
├── events_layer1.json
├── queries_layer1.json
├── macros_layer1.json
├── modules_layer1.json
├── form_access_to_wpf.json         ← used by Agent UI + Agent Service
├── event_access_to_dotnet.json     ← used by Agent Logic
├── query_access_to_dotnet.json
├── macro_access_to_dotnet.json
├── module_access_to_dotnet.json
└── <MacroName>/                    ← per-macro generated C# workflow
    └── <MacroName>MacroWorkflow.cs
```

## Notes

- Run with `form_name = "ALL"` to process all forms at once
- Results are stable across runs (cached in output files)
- `form_access_to_wpf.json` is the most critical output — used by Agent UI to resolve Japanese form names to Avalonia class names
