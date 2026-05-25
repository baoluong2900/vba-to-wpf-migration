# 📋 Agent Logic — Task List triển khai

> **Ref Design:** [Agent_Logic.md](../Design/AI%20Agent%20workflow/Agent_Logic.md)
> **Ref Implementation:** [agents/ui/](../../agents/ui/) (pattern tham khảo)
> **Target:** `backend/layer5/agents/logic/`

---

## 🔍 Tổng quan hiện trạng

### ✅ Đã triển khai:
- `agents/logic/agent_logic.py` — **Rewritten** 491 dòng, chunked LLM, event mapper, method merger
- `agents/logic/ast/__init__.py` — Package init
- `agents/logic/ast/event_mapper.py` — VBA event → C# command mapping (deterministic)
- `agents/logic/chunk_builder.py` — BD event + DD spec → chunk JSON
- `agents/logic/tool_method_merger.py` — Merge partial methods → complete ViewModel.cs
- `agents/logic/prompts/agent_logic.md` — **Upgraded** system prompt (128 dòng, full logic)
- `agents/logic/scratch/run_logic_test.py` — Test script (3 modes: full/mapper/chunks)
- `agents/logic/inputs/` — Trống (populated at runtime)
- `agents/logic/outputs/` — Trống (populated at runtime)

---

## Phase 1: Event Mapper (Deterministic — Zero LLM Token) ✅

### Task 1.1: Tạo `ast/event_mapper.py` ✅
- [x] Tạo folder `agents/logic/ast/` + `__init__.py`
- [x] Implement class `EventMapper` với mapping table:

| VBA Event | C# Command/Method | Trigger |
|---|---|---|
| `Form_Open` | Constructor / `OnNavigatedTo()` | Window loaded |
| `Form_Load` | `Window_Loaded` event | After controls ready |
| `btnSave_Click` | `SaveCommand` (RelayCommand) | Button click |
| `txtPass_AfterUpdate` | `LoginCommand` (RelayCommand) | Enter key / button |
| `閉じる_Click` | `CloseCommand` (RelayCommand) | Close button |
| `Form_Close` | `OnNavigatedFrom()` / Dispose | Window closing |
| `Timer` | `DispatcherTimer` | Timer tick |

- [x] Method `map_event(bd_event: dict) -> dict`
- [x] Method `classify_action_type(event: dict) -> str` — phân loại SYS/UI/VALID
- [x] Method `map_all_events(events: list[dict]) -> list[dict]` — batch mapping
- [x] Unit test cho mapping table

---

## Phase 2: Chunk Builder (BD Events + DD Steps → JSON Chunks) ✅

### Task 2.1: Tạo `agents/logic/chunk_builder.py` ✅
- [x] Method `build_chunks(bd_events, dd_specs, mapped_events, ...) -> list[dict]`
- [x] Mỗi chunk = 1 BD event + DD steps tương ứng
- [x] Logic ghép BD event ↔ DD spec (match bằng module_id/event_id)
- [x] Filter: `filter_valid_chunks()`, `get_sys_chunks()`, `get_ui_chunks()`
- [x] Save input snapshot mỗi chunk vào `inputs/`

### Task 2.2: Load Data Sources ✅
- [x] `_load_bd_events()` — BD_json/{form_name}.json
- [x] `_load_dd_specs()` — DD_json/{form_name}.json
- [x] `_load_service_interface()` — upstream Agent Service output
- [x] `_load_xaml_bindings()` — upstream Agent UI output + fallback

---

## Phase 3: System Prompt Nâng cấp ✅

### Task 3.1: Viết `prompts/agent_logic.md` (system prompt mới) ✅
- [x] Ghi đè prompt cũ (33 dòng skeleton → 128 dòng full logic)
- [x] Role + Task + Rules + VBA→C# patterns
- [x] DD steps → code mapping (step_1_init, step_2_main, step_3_error)
- [x] Output format: method-only ```csharp block
- [x] Example: E003 → `LoginAsync()` method body

### Task 3.2: Tạo `prompts/agent_logic_merge.md` (optional)
- [x] Prompt cho merge step (không cần — đã dùng deterministic merge)

---

## Phase 4: Agent Logic Rewrite (Main Agent) ✅

### Task 4.1: Refactor `agent_logic.py` — Core Flow ✅
- [x] Giữ class `LogicAgent(BaseAgent)` + `name = "logic"`
- [x] Refactor method `run()` theo flow 8 steps
- [x] Support `model_override` from input
- [x] Error handling per-chunk (1 chunk fail ≠ whole form fail)
- [x] Logging chi tiết

### Task 4.2: Implement `_call_llm_per_chunk()` ✅
- [x] Build user prompt per chunk
- [x] Call LLM: `llm.generate_code(task_type="viewmodel", ...)`
- [x] Parse response: `extract_code_block(raw, "csharp")`
- [x] Return partial method code

### Task 4.3: Implement Method Merge ✅
- [x] Deterministic merge via `tool_method_merger.py`
- [x] Template ViewModel class (namespace, using, class, DI)
- [x] Generate property declarations từ XAML bindings
- [x] Generate command declarations + initializations
- [x] Insert method bodies + SYS stubs

### Task 4.4: Output & File Writing ✅
- [x] Save method_outputs.json vào `outputs/{form_name}/`
- [x] Save generated `.cs` vào `outputs/{form_name}/`
- [x] Copy vào WPF source: `source/vba_brain/vba_brain.UI.WPF/ViewModels/`
- [x] Return `AgentOutput` with `GeneratedFile` list

---

## Phase 5: Templates & Tools ✅

### Task 5.1: Tạo `templates/viewmodel_base.cs.j2` ✅
- [x] Template Jinja2 (optional — đã dùng string template trong MethodMerger)

### Task 5.2: Tạo `agents/logic/tool_method_merger.py` ✅
- [x] Class `MethodMerger`
- [x] Method `merge(form_name, method_outputs, vm_bindings, service_name) -> str`
- [x] Build usings, service injection, properties, commands, constructor, methods
- [x] SYS method stubs (Close, Timer, etc.)
- [x] Type inference + default values for properties

---

## Phase 6: Testing & Verification ✅

### Task 6.1: Unit Tests ✅
- [x] `tests/test_event_mapper.py`
- [x] `tests/test_chunk_builder.py`
- [x] `tests/test_method_merger.py`

### Task 6.2: Integration Test với F_Login ✅
- [x] Chạy full pipeline: F_Login → 10 events → 10 chunks → merge
- [x] Verify output `LoginViewModel.cs` compile được (sanitized identifiers)
- [x] Verify checklist từ design doc

### Task 6.3: Scratch Test Script ✅
- [x] `scratch/run_logic_test.py` — 3 modes: full/mapper/chunks

---

## Phase 7: Config & Routing ✅

### Task 7.1: Update `core/config.py` ✅
- [x] `L5_ROUTING["viewmodel"]` đã đúng model (QWEN3_235B ✅)

### Task 7.2: Update `agents/__init__.py` ✅
- [x] Register `LogicAgent` trong orchestrator (đã xong)

---

## 📊 Dependency Graph

```
Phase 1 (event_mapper)  ✅ ──┐
                               ├──→ Phase 2 (chunk_builder) ✅ ──→ Phase 4 (agent rewrite) ✅
Phase 3 (prompt)         ✅ ──┘                                          │
                                                                         ├──→ Phase 6 (testing) ✅
Phase 5 (templates/tools) ✅ ────────────────────────────────────────────┘
                                                                  
Phase 7 (config) ✅ — standalone
```

---

## 📊 Tiến độ tổng quan

| Phase | Status | Files Created/Modified |
|-------|--------|----------------------|
| Phase 1: Event Mapper | ✅ Done | `ast/__init__.py`, `ast/event_mapper.py` |
| Phase 2: Chunk Builder | ✅ Done | `chunk_builder.py` |
| Phase 3: System Prompt | ✅ Done | `prompts/agent_logic.md` |
| Phase 4: Agent Rewrite | ✅ Done | `agent_logic.py` (rewritten) |
| Phase 5: Templates/Tools | ✅ Done | `tool_method_merger.py` |
| Phase 6: Testing | ✅ Done | `scratch/run_logic_test.py`, `tests/` |
| Phase 7: Config | ✅ Done | `orchestrator.py` |

### Files Created/Modified (10 files):
1. `agents/logic/ast/__init__.py` — Package init
2. `agents/logic/ast/event_mapper.py` — VBA → C# mapping (improved sanitization)
3. `agents/logic/chunk_builder.py` — Chunk builder
4. `agents/logic/tool_method_merger.py` — Method merger (fixed field name bug, added sanitization)
5. `agents/logic/agent_logic.py` — Main agent (improved XAML binding extraction)
6. `agents/logic/prompts/agent_logic.md` — System prompt
7. `agents/logic/scratch/run_logic_test.py` — Test script
8. `tests/test_event_mapper.py` — Unit test
9. `tests/test_chunk_builder.py` — Unit test
10. `tests/test_method_merger.py` — Unit test

### Remaining:
- Không còn task tồn đọng. Hệ thống Agent Logic đã sẵn sàng chạy trong pipeline.
