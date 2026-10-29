# Agent Mapping

**File:** `agents/mapping/agent_mapping.py`  
**Pipeline step:** none — the orchestrator and `run_codegen_all.py` never call it; the console runs it (then Agent Repo) for a selected macro/module, or with `ALL`

## Purpose

`ALL`: rebuilds the Access → Avalonia name mapping tables for forms, events, modules, macros, and
queries (no LLM call) and copies them here. Agents resolve names from
`agents/graphview/outputs/*/list*JpToEn.json`, not from these copies.  
A macro or module name: generates one C# class for that macro or module (LLM).

## Flow

```
ALL
MongoDB (forms, queries, macros, modules)
    │
    ▼
export_forms_layer1.py (subprocess)   → agents/graphview/outputs/{forms,events,queries,macros,modules}/list*Jp.json + list*JpToEn.json
    │
    ▼  copied and renamed (no LLM)
outputs/forms_layer1.json             ← raw form list (listFormJp.json)
outputs/events_layer1.json            ← raw event list (listEventJp.json)
outputs/queries_layer1.json
outputs/macros_layer1.json
outputs/modules_layer1.json
outputs/form_access_to_wpf.json       ← Access form → Avalonia View/ViewModel names (listFormJpToEn.json)
outputs/event_access_to_dotnet.json   ← Access event → .NET event names (listEventJpToEn.json)
outputs/query_access_to_dotnet.json
outputs/macro_access_to_dotnet.json
outputs/module_access_to_dotnet.json
    │
    ▼
<repo>/docs/mappings/                 ← same copies for documentation (resolved from WORKFLOW_DIR)

<macro or module name>
MongoDB macros / modules
    │
    ▼
LLM (agent_mapping_macro.md)          → one C# workflow class for the macro → vba_brain.UI.Avalonia/Services/
LLM (agent_mapping_module.md)         → one C# service class for the module → vba_brain.Domain/Common/
    │
    ▼
outputs/<Name>/<ClassName>.cs         ← copy of the deployed class
```

The `outputs/*.json` tables are regenerated per run and git-ignored; macro/module class names are
read from `agents/graphview/outputs/{macros,modules}/list*JpToEn.json` (both key spellings), and
fallback names get a short hash when characters had to be dropped, so two macros never share a
class name.

## Key Files

| File | Role |
|------|------|
| `agent_mapping.py` | Main agent |
| `graphview/inputs/export_forms_layer1.py` | Exports Layer 1 data from MongoDB |
| `prompts/agent_mapping_macro.md` | LLM prompt: C# workflow class for one macro |
| `prompts/agent_mapping_module.md` | LLM prompt: C# service class for one module |

## Outputs

```
agents/mapping/outputs/
├── forms_layer1.json
├── events_layer1.json
├── queries_layer1.json
├── macros_layer1.json
├── modules_layer1.json
├── form_access_to_wpf.json         ← copy of graphview listFormJpToEn.json (not read by any agent)
├── event_access_to_dotnet.json     ← copy of graphview listEventJpToEn.json (not read by any agent)
├── query_access_to_dotnet.json
├── macro_access_to_dotnet.json
├── module_access_to_dotnet.json
└── <Name>/                         ← per-macro / per-module generated C#
    └── <ClassName>.cs              ← mapped class name, e.g. AMenuBarShowMacroWorkflow.cs
```

The macro class is also written to `vba_brain.UI.Avalonia/Services/`, the module class to
`vba_brain.Domain/Common/`.

## Notes

- The argument is `"ALL"` (the default) or a macro/module name — not a form name
- The name maps are deterministic (`export_forms_layer1.py` makes no LLM call) and are rebuilt on every `ALL` run
- `agents/graphview/outputs/forms/listFormJpToEn.json` (copied here as `form_access_to_wpf.json`) is what Agent UI, Agent Service and Agent Logic read to resolve Japanese form names to Avalonia class names
