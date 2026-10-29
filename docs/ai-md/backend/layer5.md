# Backend — Layer 5: C# / Avalonia Code Generation

## Purpose

Layer 5 converts DD/BD JSON specifications (from Layer 2) into build-ready C# source code targeting the Avalonia MVVM architecture. It runs a sequential multi-agent pipeline per form and writes output directly into the Avalonia solution.

---

## Pipeline Order

For each form, the orchestrator (`pipeline/orchestrator.py`) runs agents in this fixed order:

```
Repo → Service → (Logic input refresh) → UI → Logic → GraphView (non-blocking) → Write → dotnet build
```

| Step | Agent | Output |
|------|-------|--------|
| 1 | **Repo** | Entity, DTO, IRepository, Repository (Dapper) + the form's repo contract |
| 2 | **Service** | IService, Service, DTOs, service contract (keyed by the shared F-ID) |
| 3 | **UI** | ViewModel skeleton (Commands, DI, SetProperty) + AXAML + code-behind |
| 4 | **Logic** | Method bodies (LLM, or deterministic `sys_bodies.py`) patched into the skeleton |
| 5 | **GraphView** | Access ↔ .NET review graph; failures are logged, never block the form |
| 6 | **Write** | Code files (`.cs` / `.axaml`) written inside the solution, de-duplicated by target path |
| 7 | **Build** | `dotnet build` + LLM auto-fix of the on-disk file that failed (`MAX_RETRIES = 3` builds, so at most 2 fix rounds) |

> UI runs **before** Logic so Logic patches into an existing skeleton rather than generating a new
> ViewModel. All agents number methods through `core/fid_resolver.py`, so `F003Command`,
> `F003Async` and the service contract's `F003` are the same event. A form counts as `success`
> only when Repo, Service, UI and Logic succeeded **and** the build passed.

---

## Entry Points

```bash
# Run the default forms (DEFAULT_FORMS, listed below)
python src/backend/workflow/layer5/run_codegen_all.py

# Run selected forms (repeatable; exits 1 if any form fails)
python src/backend/workflow/layer5/run_codegen_all.py --form F_Login --form F_Menu
```

Default forms: `F_Login`, `F_Menu`, `F_ProductDetail`, `F_ProductList`, `F_TestForm`

The console's **Run pipeline** button does not use the orchestrator: it starts the agent scripts one
by one in the order Repo → Service → Logic → UI (Report for reports) → GraphView, i.e. Logic
before UI; for macros/modules it runs Mapping → Repo.

---

## Agents

### Agent Repo (`agents/repo/agent_repo.py`)

- Reads DD SQL specs + table schemas from MongoDB (`queries_v2`, `tables`)
- Generates: `Entity.cs`, `DTO.cs`, `IRepository.cs`, `Repository.cs` (Dapper)
- Deterministic: `tool_repo.py` builds the C# as strings (no Jinja2)
- LLM only used for translating unknown field names (batch TODO phase)
- Config: `agents/repo/config/name_config.json` (`table_config.json` next to it is not read by any code)
- Outputs: `agents/repo/outputs/<FormName>/`

### Agent Service (`agents/service/agent_service.py`)

- Reads DD step-by-step logic + repo contract
- Generates: `IService.cs`, `Service.cs`, request/response DTOs, and the service contract
  `outputs/<FormName>/<FormName>.json`
- LLM model: `service` routing slot → `qwen3-coder-480b-a35b-instruct` (default)
- Prompt (LLM mode only): `agents/service/prompts/agent_service_form.md`
- Outputs: `agents/service/outputs/<FormName>/Application/`

### Agent UI (`agents/ui/agent_ui.py`)

- Reads the form layout from MongoDB `forms`, BD events (for F-IDs) + service contract
- Generates: XAML View (`.axaml`), ViewModel skeleton, code-behind stub
- Control mapping: `agents/ui/control_mapper.py` (Access control → Avalonia control)
- F-ID registry: `agents/ui/configs/ui_event_map.json` (via `core/fid_resolver.py`)
- LLM model: `view_xaml` routing slot → `qwen-plus-2025-07-28`
- Outputs: `agents/ui/outputs/<FormName>/Views/`, `ViewModels/`

### Agent Logic (`agents/logic/agent_logic.py`)

- Reads DD event steps + UI skeleton ViewModel
- Translates VBA events → C# method bodies (commands, properties and service DI come from the UI skeleton)
- Breaks complex events into chunks (`chunk_builder.py`) and patches each `FxxxAsync` body into the UI skeleton; system events (quit, kill process, keys) come from `sys_bodies.py` without an LLM call
- The CLI exits 1 only when a whole form's run fails; a failed LLM call for one method is logged and recorded with status `error` in `method_outputs.json`, which is cleared at the start of every run
- LLM model: `viewmodel` routing slot
- Prompt: `agents/logic/prompts/agent_logic.md` (`agent_vm_methods.md` sits next to it but is never loaded)
- Outputs: `agents/logic/outputs/<FormName>/ViewModels/`, `method_outputs.json`

### Agent Mapping (`agents/mapping/agent_mapping.py`)

- `ALL` (no LLM call): runs `export_forms_layer1.py`, which rebuilds the Access→Avalonia name maps
  (forms, events, modules, macros, queries) in `agents/graphview/outputs/`, then copies them
- Outputs: `agents/mapping/outputs/` — `form_access_to_wpf.json`, `event_access_to_dotnet.json`, etc.
  (copies only; agents read the `agents/graphview/outputs/` files)
- Given a macro or module name instead, generates one C# class for it via LLM
- Not a pre-step: the orchestrator and `run_codegen_all.py` never call it; the console runs it
  (then Repo) only for macros/modules

### Agent GraphView (`agents/graphview/agent_graphview.py`)

- Builds a deterministic dependency graph of generated C# code
- Compares Avalonia graph vs original VBA graph to detect:
  - `missing` — VBA features not yet implemented in Avalonia
  - `extra` — new features added in Avalonia with no VBA equivalent
- Inputs: `agents/graphview/inputs/dependency_<FormName>.json`, `mapping_<FormName>.json`
- Outputs: `agents/graphview/outputs/review_<FormName>.json`
- Runs inside the orchestrator as a non-blocking step, or separately from the console

### Agent Report (`agents/report/agent_report.py`)

- Converts an Access report into an Avalonia report view + view model (RDLC layout, fields,
  section formatting); print/PDF handlers get a TODO naming the `.rdlc` and the service call
  that supplies its rows (no WinForms/WPF ReportViewer code)
- Reports are recognised by the `forms` document `type`, then `listReportJpToEn.json`, then the
  "R" prefix

Token usage of every Layer 5 LLM call is recorded by `llm/token_tracker.py` in
`logs/token_report.json` and `logs/token_report.xlsx`.

---

## Model Routing

Defined in `core/config.py` → `L5_ROUTING`:

| Slot | Default Model | Used for |
|------|--------------|---------|
| `service` | `qwen3-coder-480b-a35b-instruct` | DD steps → C# business logic |
| `viewmodel` | `qwen-plus-2025-07-28` | MVVM commands, event flow |
| `repository` | `qwen3-coder-480b-a35b-instruct` | Unused — Agent Repo's only LLM call uses task type `translate_config` |
| `view_xaml` | `qwen-plus-2025-07-28` | Form layout → XAML (JSONL spec) |
| `validator` | `qwen-plus-2025-07-28` | `BuildVerifier` LLM build fixes |
| `entity` | `qwen-plus-2025-07-28` | Unused |
| `dto` | `qwen-plus-2025-07-28` | Unused |
| `mapper` | `qwen-plus-2025-07-28` | Unused |

A task type that is not a slot (e.g. `translate_config`, used by Agent Repo and Agent Report) gets
`DEFAULT_MODEL` (`LAYER5_DEFAULT_MODEL`, default `qwen3-coder-480b-a35b-instruct`).

Override via env vars: `LAYER5_SERVICE_MODEL`, `LAYER5_VIEWMODEL_MODEL`, `LAYER5_REPOSITORY_MODEL`
(only sets the unused `repository` slot), `LAYER5_DEFAULT_MODEL`

---

## Pipeline Infrastructure

### `pipeline/orchestrator.py` — `L5Orchestrator`

- Async orchestrator: runs all agents sequentially per form
- Collects `FormResult` (status, files, build success, duration)
- Calls `SolutionWriter` then `BuildVerifier` after all agents complete

### `pipeline/file_writer.py` — `SolutionWriter`

- Writes generated files to correct Avalonia project directories:
  - `Views/` → `vba_brain.UI.Avalonia/Views/`
  - `ViewModels/` → `vba_brain.UI.Avalonia/ViewModels/`
  - `Application/` → `vba_brain.Application/`
  - `Infrastructure/` → `vba_brain.Infrastructure/`
  - `Domain/` → `vba_brain.Domain/`
- Path-confined write (absolute or escaping paths are refused); overwrites in place, no backup
- Non-source files (anything but `.cs` / `.axaml` / `.xaml`) are skipped

### `pipeline/build_verify.py` — `BuildVerifier`

- Runs `dotnet build` and parses compiler errors
- On error: sends errors + source → LLM → receives patch → applies
- `MAX_RETRIES = 3` (from `core/config.py`) counts builds, so at most 2 LLM fix rounds

### `pipeline/deploy_to_source.py`

- Copies generated files from agent `outputs/` into the Avalonia solution
- Used for manual re-deploy without re-running agents

### `pipeline/base_gen.py`

- Generates base classes (`ViewModelBase`, `RelayCommand`, etc.) if missing from solution

---

## Codegen Templates

Jinja2 templates in `codegen/templates/`:

| Template | Output |
|----------|--------|
| `IService.cs.j2` | Service interface (used by Agent Service) |

Entities, DTOs and repositories are emitted by `agents/repo/tool_repo.py` directly.

Rendered by `codegen/jinja_engine.py`.

---

## MongoDB Collections

| Collection | Used by | Content |
|-----------|---------|---------|
| `forms` | UI, Service, Logic, GraphView | Form metadata, controls, VBA events |
| `queries_v2` | Repo | Access query SQL |
| `tables` | Repo | Table schemas |
| `bds` | UI, Logic | Basic Design JSON |
| `dds` | Repo, Service, Logic | Detailed Design JSON |
| `agent_repo` | Service (read only, last fallback for the repo contract) | Repo contract — nothing in Layer 5 writes it |
| `agent_service` | Service (writes) | Service contract per form |
| `agent_logic` | Logic (writes) | Logic contract per form |
| `agent_graphview` | GraphView (writes) | `mapping_` / `dependency_` / `review_<FormName>.json` content |

---

## Output Structure

```
agents/
├── repo/outputs/<FormName>/
│   ├── <Name>Entity.cs
│   ├── <Name>Repository.cs
│   └── I<Name>Repository.cs
├── service/outputs/<FormName>/
│   ├── <FormName>.json                 ← service contract
│   └── Application/
│       ├── Interfaces/I<Name>Service.cs
│       ├── Services/<Name>Service.cs
│       └── DTOs/{Requests,Responses}/
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
