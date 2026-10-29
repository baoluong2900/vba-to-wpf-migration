# Agent GraphView

**File:** `agents/graphview/agent_graphview.py`  
**Pipeline step:** after Agent Logic, for every form (orchestrator step 6) — non-blocking: failures are logged and never fail the form

## Purpose

Reviews generated Avalonia source against the original VBA dependency graph to detect missing or extra implementations.

## Flow

```
MongoDB forms / reports / macros
    │
    ▼
build_vba_graph()                   → VBA dependency graph of the form
    │
    ▼
LLM (agent_graphview.md)            → inputs/mapping_<FormName>.json (expected Access→Avalonia nodes/edges)
    │
    ▼
Parse C# source files               → inputs/dependency_<FormName>.json (deterministic, generated .NET source)
    │
    ▼
Compare expected mapping vs Avalonia graph
    │
    ▼
outputs/review_<FormName>.json      ← review result: ok / missing / extra / mismatch, overall PASS / FAIL
MongoDB agent_graphview             ← persist mapping, dependency and review
```

## Review Result Flags

| Status | Meaning |
|------|---------|
| `missing` | VBA feature exists but not implemented in Avalonia |
| `extra` | Avalonia has new feature with no VBA equivalent |
| `ok` | Correctly implemented |
| `mismatch` | Layer-direction violation in the .NET graph (e.g. ViewModel → Repository) |

The review's overall `status` is `PASS` when nothing is `missing` or `mismatch`, else `FAIL`.

## Key Files

| File | Role |
|------|------|
| `agent_graphview.py` | Main agent + `GraphNode` / `GraphEdge` dataclasses |
| `inputs/export_forms_layer1.py` | Exports the JP name lists and JP→EN name maps (`outputs/{forms,queries,macros,modules,events}/`) from MongoDB |
| `prompts/agent_graphview.md` | LLM prompt that generates the expected mapping from the VBA graph |

## Inputs (per form)

```
agents/graphview/inputs/
├── mapping_<FormName>.json       ← the agent's own LLM output, built from build_vba_graph()
└── dependency_<FormName>.json    ← parsed from the generated .NET source
```

From the console, both files are built before the agent runs (mapping from the VBA graph by
`buildWpfMappingFromVbaGraph`, dependency by `parseActualSourceGraph` over `src/wpf`); the CLI then
reuses them instead of calling the LLM.

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
- Runs in `pipeline/orchestrator.py` for every form (non-blocking); can also be run via
  `python agent_graphview.py <form>`, which reuses existing `inputs/` files or else generates them
- Requires Avalonia source files to exist in `src/wpf/` directory for C# parsing
