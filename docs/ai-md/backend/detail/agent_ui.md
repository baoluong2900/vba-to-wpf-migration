# Agent UI

**File:** `agents/ui/agent_ui.py`  
**Pipeline step:** #3 (after Agent Service)

## Purpose

Generates the Avalonia XAML View and ViewModel skeleton for a given form.  
Data source: MongoDB `forms` collection only — no BD JSON dependency.

## Flow

```
MongoDB forms
    │
    ▼
control_mapper.py       → map Access controls → Avalonia controls
    │
    ▼
LLM (JSONL prompt)      → structured JSONL spec (controls + bindings)
    │
    ▼
tool_skeleton.py        → deterministic .axaml + .axaml.cs + ViewModel skeleton
    │
    ▼
outputs/<FormName>/Views/       ← XAML View
outputs/<FormName>/ViewModels/  ← ViewModel skeleton (for Agent Logic to patch)
```

LLM generates **JSONL only** (not raw XAML) to save tokens. `tool_skeleton.py` assembles the final XAML deterministically.

## Key Files

| File | Role |
|------|------|
| `agent_ui.py` | Main agent, LangGraph `UIChunkState` map-reduce |
| `control_mapper.py` | Access control type → Avalonia control type mapping |
| `tool_skeleton.py` | Deterministic XAML + ViewModel skeleton generator |
| `tool_query_stubs.py` | Generates query stub bindings |
| `configs/ui_event_map.json` | F-ID registry per form (written atomically by `core/fid_resolver.py`; `_auto` ids are stable) |
| `configs/ui_query_stubs.json` | Query stub config |
| `name_spacing/ui_name_map.json` | Control name normalization map |
| `prompts/agent_ui.md` | LLM system prompt |

## LLM Prompt Rules (from `prompts/agent_ui.md`)

- Output **JSONL** — one JSON object per control per line, no raw XAML
- `binding` must be PascalCase of `physical_name` (e.g. `txtID` → `TxtID`)
- `PasswordBox`: always set `"password_event": true`, never set `binding`
- `Button`: map `onclick` → `command` field
- Macro references → `comment` field only (no command)
- `visible: false` → `Visibility="Collapsed"`
- Never translate or rename control `name` or `content`

## F-IDs and events

- F-IDs (`F003Command` / `F003Async`) come from `core/fid_resolver.py`: the BD `module_id` first
  (matched on handler, raw `macro.X` value, or control + trigger), then the registry entry, then
  a new `_auto` id. The agent resolves once per run and passes the same map to the AXAML,
  ViewModel and code-behind generators, so Agent Logic and Agent Service see the same ids.
- Access form events without an Avalonia equivalent become a TODO comment in the code-behind,
  never a raw VBA event name. Avalonia has no `Interaction.Triggers`: control events
  (AfterUpdate → `LostFocus`, `DoubleTapped`, `PointerReleased`, `GotFocus`) are subscribed in
  the code-behind.
- The converted PasswordBox is `<TextBox PasswordChar="*" Text="{Binding TxtPass}"/>`.
- The code-behind has a public parameterless constructor (XAML loader) and a view-model
  constructor that chains `: this()`, wires events and closes on `CloseRequested`.

## Form Name Resolution

Uses `agents/graphview/outputs/forms/listFormJpToEn.json` to resolve Japanese Access form names → Avalonia View/ViewModel class names.

## LangGraph State

```python
class UIChunkState(TypedDict):
    form_name, window_name, wpf_controls, wpf_sections
    vm_bindings, form_config, system_prompt, model_override, llm
    chunks, total_chunks, current_idx
    partial_specs: Annotated[list[dict], operator.add]  # appended across steps
    final_spec: dict
```

## Model

`L5_ROUTING["view_xaml"]` → `qwen-plus-2025-07-28` (default)

## Outputs

```
agents/ui/outputs/<FormName>/
├── Views/<Name>View.axaml
├── Views/<Name>View.axaml.cs
└── ViewModels/<Name>ViewModel.cs   ← skeleton (patched by Agent Logic)
```
