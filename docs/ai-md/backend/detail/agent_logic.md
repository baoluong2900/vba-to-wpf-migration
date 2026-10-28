# Agent Logic

**File:** `agents/logic/agent_logic.py`  
**Pipeline step:** #4 (after Agent UI)

## Purpose

Generates C# method bodies for the ViewModel by translating VBA events → MVVM RelayCommands.  
Patches method bodies into the ViewModel skeleton created by Agent UI — does **not** generate a new ViewModel from scratch.

## Flow

```
DD events + BD specs + Service interface + XAML bindings
    │
    ▼
event_mapper.py         → deterministic: map VBA events → C# method stubs
    │
    ▼
chunk_builder.py        → 1 chunk per event (split for context window)
    │
    ▼
Filter chunks           → skip SYS / UI action_type events
    │
    ▼
Save input snapshot     → inputs/<FormName>_output.json
    │
    ▼
LangGraph map-reduce    → LLM call per chunk (parallel)
    │
    ▼
patch each FxxxAsync body into the UI skeleton ViewModel.cs (brace-matched; F-IDs from core/fid_resolver.py)
    │
    ▼
outputs/<FormName>/ViewModels/<Name>ViewModel.cs
```

## Key Files

| File | Role |
|------|------|
| `agent_logic.py` | Main agent, LangGraph `LogicChunkState` map-reduce |
| `chunk_builder.py` | Splits events into per-event chunks |
| `sys_bodies.py` | Deterministic Avalonia bodies for system events (quit/close, kill process, key handling) — no LLM |
| `../../core/fid_resolver.py` | One F-ID numbering shared with Agent UI and the service contract |
| `mapping_ast/event_mapper.py` | VBA event → C# method signature mapping |
| `prompts/agent_logic.md` | LLM system prompt |
| `prompts/agent_vm_methods.md` | ViewModel method generation prompt |

## LLM Prompt Rules (from `prompts/agent_logic.md`)

**MVVM separation is mandatory:**
- **ViewModel methods** (`FxxxAsync`): all business logic — notifications, navigation, service calls, state changes
- **Code-behind methods** (`Fxxx_Click` etc.): delegate only — `if (DataContext is ViewModels.XxxViewModel vm) await vm.FxxxAsync();`

**Strict rules:**
- `Application` is qualified as `global::Avalonia.Application` (namespace conflict with `vba_brain.Application`)
- Never reference View class by name — use `// TODO: open FormName view — confirm View class name`
- No `using` statements, no class wrapper, no namespace — method body only
- Comments in `TARGET_LANGUAGE` only, max 3–5 lines per method
- TODO is last resort — only when impossible to determine from spec

**VBA → C# key mappings:**

| VBA | C# |
|-----|----|
| `MsgBox "text"` | `System.Diagnostics.Debug.WriteLine("text")` (Avalonia has no MessageBox) |
| `DoCmd.Quit acQuitPrompt` | confirm dialog + Avalonia desktop lifetime `Shutdown()` |
| `DoCmd.Close acForm, "X"` | `CloseRequested?.Invoke(this, EventArgs.Empty)` |
| `DoCmd.OpenForm "X"` | `// TODO: open X view — confirm View class name` |
| `KeyCode = 0` | `e.Handled = true` in code-behind |
| `Shell.Exec("taskkill /F /IM x.exe")` | `Process.Start(new ProcessStartInfo {...})` |

## LangGraph State

```python
class LogicChunkState(TypedDict):
    form_name, system_prompt, llm, model_override
    chunks: list[dict]      # one per event
    total_chunks: int
    current_idx: int
    # + Annotated[list, operator.add] for partial method outputs
```

## Model

`L5_ROUTING["viewmodel"]` → `qwen-plus-2025-07-28` (default)

## Inputs (per form)

```
agents/logic/inputs/
├── <FormName>.json           ← DD spec
├── <FormName>_ui.json        ← XAML bindings from Agent UI
├── <FormName>_service.json   ← service contract from Agent Service
└── <FormName>_output.json    ← snapshot saved before LLM calls
```

## Outputs

```
agents/logic/outputs/<FormName>/
├── ViewModels/<Name>ViewModel.cs   ← patched with method bodies
└── method_outputs.json             ← raw LLM outputs per chunk
```
