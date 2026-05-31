# Backend — Layer 5: C# / Avalonia Code Generation

## Purpose

Layer 5 converts DD/BD JSON specifications (from Layer 2) into build-ready C# source code targeting the Avalonia MVVM architecture. It runs a sequential multi-agent pipeline per form and writes output directly into the WPF solution.

---

## Pipeline Order

For each form, agents run in this fixed order:

```
Agent Repo → Agent Service → Agent UI → Agent Logic → Write → dotnet build
```

| Step | Agent | Output |
|------|-------|--------|
| 1 | **Repo** | Entity, DTO, IRepository, Repository (Dapper) |
| 2 | **Service** | IService, Service, `service_contract.json` |
| 3 | **UI** | ViewModel skeleton (Commands, DI, SetProperty) + XAML + code-behind |
| 4 | **Logic** | LLM-generated method bodies patched into UI skeleton ViewModel |
| 5 | **Write** | Files deployed to WPF solution directories |
| 6 | **Build** | `dotnet build` + AI auto-fix loop (max 3 retries) |

> UI runs **before** Logic so Logic patches into an existing skeleton rather than generating a new ViewModel from scratch.

---

## Entry Points

```bash
# Run all forms
python src/backend/workflow/layer5/run_codegen_all.py

# Run single form (test)
python src/backend/workflow/layer5/run_codegen_test.py
```

Default forms: `F_Login`, `F_Menu`, `F_ProductDetail`, `F_ProductList`, `F_TestForm`

---

## Agents

### Agent Repo (`agents/repo/agent_repo.py`)

- Reads DD SQL specs + table schemas from MongoDB (`queries_v2`, `tables`)
- Generates: `Entity.cs`, `DTO.cs`, `IRepository.cs`, `Repository.cs` (Dapper)
- Mostly deterministic via Jinja2 templates (`codegen/templates/`)
- LLM only used for translating unknown field names (batch TODO phase)
- Config: `agents/repo/config/name_config.json`, `table_config.json`
- Outputs: `agents/repo/outputs/<FormName>/`

### Agent Service (`agents/service/agent_service.py`)

- Reads DD step-by-step logic + repo contract
- Generates: `IService.cs`, `Service.cs`, `service_contract.json`
- LLM model: `service` routing slot → `qwen3-coder-480b` (default)
- Prompts: `agents/service/prompts/agent_service_form.md`, `_macro.md`, `_module.md`
- Outputs: `agents/service/outputs/<FormName>/Application/`

### Agent UI (`agents/ui/agent_ui.py`)

- Reads BD layout + service contract
- Generates: XAML View (`.axaml`), ViewModel skeleton, code-behind stub
- Control mapping: `agents/ui/control_mapper.py` (Access control → Avalonia control)
- Event mapping: `agents/ui/configs/ui_event_map.json`
- LLM model: `view_xaml` / `viewmodel` routing slots → `qwen-plus-2025-07-28`
- Outputs: `agents/ui/outputs/<FormName>/Views/`, `ViewModels/`

### Agent Logic (`agents/logic/agent_logic.py`)

- Reads DD event steps + UI skeleton ViewModel
- Translates VBA events → C# RelayCommands, Properties, Service DI injections
- Breaks complex events into chunks (`chunk_builder.py`) and merges via AST (`tool_method_merger.py`)
- LLM model: `viewmodel` routing slot
- Prompts: `agents/logic/prompts/agent_logic.md`, `agent_vm_methods.md`
- Outputs: `agents/logic/outputs/<FormName>/ViewModels/`, `method_outputs.json`

### Agent Mapping (`agents/mapping/agent_mapping.py`)

- Builds Access→WPF name mapping tables (forms, events, modules, macros, queries)
- Outputs: `agents/mapping/outputs/` — `form_access_to_wpf.json`, `event_access_to_dotnet.json`, etc.
- Runs once as a pre-step; results consumed by all other agents

### Agent GraphView (`agents/graphview/agent_graphview.py`)

- Builds a deterministic dependency graph of generated C# code
- Compares WPF graph vs original VBA graph to detect:
  - `MISSING` — VBA features not yet implemented in WPF
  - `EXTRA` — new features added in WPF with no VBA equivalent
- Inputs: `agents/graphview/inputs/dependency_<FormName>.json`, `mapping_<FormName>.json`
- Outputs: `agents/graphview/outputs/review_<FormName>.json`
- Currently disabled in the main pipeline; run separately

### Agent Report (`agents/report/agent_report.py`)

- Aggregates token usage, file counts, build results across all forms
- Outputs: `logs/token_report.json`

---

## Model Routing

Defined in `core/config.py` → `L5_ROUTING`:

| Slot | Default Model | Used for |
|------|--------------|---------|
| `service` | `qwen3-coder-480b` | DD steps → C# business logic |
| `viewmodel` | `qwen-plus-2025-07-28` | MVVM commands, event flow |
| `repository` | `qwen3-coder-480b` | SQL → Dapper code |
| `view_xaml` | `qwen-plus-2025-07-28` | BD layout → XAML |
| `validator` | `qwen-plus-2025-07-28` | Business rules → FluentValidation |
| `entity` | `qwen-plus-2025-07-28` | Fallback if Jinja2 insufficient |
| `dto` | `qwen-plus-2025-07-28` | DTOs |
| `mapper` | `qwen-plus-2025-07-28` | AutoMapper profiles |

Override via env vars: `LAYER5_SERVICE_MODEL`, `LAYER5_VIEWMODEL_MODEL`, `LAYER5_REPOSITORY_MODEL`

---

## Pipeline Infrastructure

### `pipeline/orchestrator.py` — `L5Orchestrator`

- Async orchestrator: runs all agents sequentially per form
- Collects `FormResult` (status, files, build success, duration)
- Calls `SolutionWriter` then `BuildVerifier` after all agents complete

### `pipeline/file_writer.py` — `SolutionWriter`

- Writes generated files to correct WPF project directories:
  - `Views/` → `vba_brain.UI.Avalonia/Views/`
  - `ViewModels/` → `vba_brain.UI.Avalonia/ViewModels/`
  - `Application/` → `vba_brain.Application/`
  - `Infrastructure/` → `vba_brain.Infrastructure/`
  - `Domain/` → `vba_brain.Domain/`
- Safe write with backup (`.bak`) before overwrite

### `pipeline/build_verify.py` — `BuildVerifier`

- Runs `dotnet build` and parses compiler errors
- On error: sends errors + source → LLM → receives patch → applies
- Max retries: `MAX_RETRIES = 3` (from `core/config.py`)

### `pipeline/deploy_to_source.py`

- Copies generated files from agent `outputs/` into the WPF solution
- Used for manual re-deploy without re-running agents

### `pipeline/base_gen.py`

- Generates base classes (`ViewModelBase`, `RelayCommand`, etc.) if missing from solution

### `pipeline/patch_vm_from_output.py`

- Utility to re-patch ViewModel from saved `method_outputs.json` without re-running LLM

---

## Codegen Templates

Jinja2 templates in `codegen/templates/`:

| Template | Output |
|----------|--------|
| `Entity.cs.j2` | Domain entity class |
| `DTO.cs.j2` | Data transfer object |
| `Interface.cs.j2` | Repository/Service interface |
| `IService.cs.j2` | Service interface |

Rendered by `codegen/jinja_engine.py`.

---

## MongoDB Collections

| Collection | Used by | Content |
|-----------|---------|---------|
| `forms` | Repo, UI, Logic | Form metadata, controls, VBA events |
| `queries_v2` | Repo | Access query SQL |
| `tables` | Repo | Table schemas |
| `dds` | Service, Logic | Detailed Design JSON |
| `dependency_graph` | GraphView | Cross-form reference graph |
| `agent_repo` | All agents | Generated artifact registry |

---

## Output Structure

```
agents/
├── repo/outputs/<FormName>/
│   ├── <Name>Entity.cs
│   ├── <Name>Repository.cs
│   └── I<Name>Repository.cs
├── service/outputs/<FormName>/Application/
│   ├── <Name>Service.cs
│   └── I<Name>Service.cs
├── ui/outputs/<FormName>/
│   ├── Views/<Name>View.axaml
│   └── ViewModels/<Name>ViewModel.cs   ← skeleton
└── logic/outputs/<FormName>/
    ├── ViewModels/<Name>ViewModel.cs   ← patched with method bodies
    └── method_outputs.json
```

---

## Localization

- Reads `TARGET_LANGUAGE` (from `config.json` or env)
- Controls language of XML doc comments (`/// <summary>`) and inline code notes
- Source language: `SOURCE_LANGUAGE` (default `ja`)
