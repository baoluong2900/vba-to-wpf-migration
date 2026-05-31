# Agent GraphView

**File:** `agents/graphview/agent_graphview.py`  
**Pipeline step:** Post-step (runs after all forms, currently disabled in main pipeline)

## Purpose

Reviews generated WPF source against the original VBA dependency graph to detect missing or extra implementations.

## Flow

```
inputs/mapping_<FormName>.json      ← Access→WPF name mapping
inputs/dependency_<FormName>.json   ← VBA dependency graph (from Layer 1)
    │
    ▼
Parse C# source files               → deterministic AST parsing
    │
    ▼
LLM (agent_graphview.md)            → AI-assisted mapping validation
    │
    ▼
Compare VBA graph vs WPF graph
    │
    ▼
outputs/review_<FormName>.json      ← review result with MISSING / EXTRA flags
MongoDB agent_repo                  ← persist review result
```

## Review Result Flags

| Flag | Meaning |
|------|---------|
| `MISSING` | VBA feature exists but not implemented in WPF |
| `EXTRA` | WPF has new feature with no VBA equivalent |
| `MATCHED` | Correctly implemented |

## Key Files

| File | Role |
|------|------|
| `agent_graphview.py` | Main agent + `GraphNode` / `GraphEdge` dataclasses |
| `inputs/export_forms_layer1.py` | Exports Layer 1 dependency data from MongoDB |
| `prompts/agent_graphview.md` | LLM prompt for mapping validation |

## Inputs (per form)

```
agents/graphview/inputs/
├── mapping_<FormName>.json       ← from Agent Mapping
└── dependency_<FormName>.json    ← from Layer 1 aggregator
```

## Outputs

```
agents/graphview/outputs/
├── review_<FormName>.json        ← per-form review result
├── forms/
│   ├── listFormJp.json           ← raw JP form list
│   └── listFormJpToEn.json       ← JP→EN mapping (used by Agent UI + Service)
├── events/
│   ├── listEventJp.json
│   └── listEventJpToEn.json
├── macros/
│   ├── listMacroJp.json
│   └── listMacroJpToEn.json
├── modules/
│   ├── listModuleJp.json
│   └── listModuleJpToEn.json
├── queries/
│   ├── listQueryJp.json
│   └── listQueryJpToEn.json
└── reports/
    └── listReportJpToEn.json
```

## Notes

- `listFormJpToEn.json` is a critical shared artifact — Agent UI and Agent Service both read it for form name resolution
- Currently disabled in `pipeline/orchestrator.py` — run manually via `python agent_graphview.py`
- Requires WPF source files to exist in `source/` directory for C# parsing
