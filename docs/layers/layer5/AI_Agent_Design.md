# 🤖 AI Agent Design — Source Structure & Index

> **7 Agents** — Mỗi agent có folder riêng → dev sửa agent nào chỉ touch folder đó → **zero conflict khi push**  
> **Design docs:** [AI Agent workflow/](./AI%20Agent%20workflow/)  
> **Ref:** [AI_Agent_Workflow.md](./AI_Agent_Workflow.md)

---

## Agent Index

| # | Agent | Design Doc | Source Folder | Owner |
|---|-------|-----------|---------------|-------|
| 🎨 | **Agent UI** | [Agent_UI.md](./AI%20Agent%20workflow/Agent_UI.md) | `agents/ui/` | Dev A |
| 🧠 | **Agent Logic** | [Agent_Logic.md](./AI%20Agent%20workflow/Agent_Logic.md) | `agents/logic/` | Dev B |
| ⚙️ | **Agent Service** | [Agent_Service.md](./AI%20Agent%20workflow/Agent_Service.md) | `agents/service/` | Dev C |
| 🗃️ | **Agent Repo** | [Agent_Repo.md](./AI%20Agent%20workflow/Agent_Repo.md) | `agents/repo/` | Dev D |
| 📊 | **Agent Report** | [Agent_Report.md](./AI%20Agent%20workflow/Agent_Report.md) | `agents/report/` | Dev E |
| 🔍 | **Agent GraphView** | [Agent_GraphView.md](./AI%20Agent%20workflow/Agent_GraphView.md) | `agents/graphview/` | Dev F |
| 🧪 | **Agent Test** | [Agent_Test.md](./AI%20Agent%20workflow/Agent_Test.md) | `agents/test/` | Dev G |

---

## Source Structure (Conflict-Free)

> **Rule:** Mỗi agent = 1 folder riêng (agent code + prompt + template)  
> **Shared:** `core/`, `llm/`, `pipeline/` — chỉ 1 người maintain, ít thay đổi

```
backend/layer5/
│
├── __init__.py
│
├── agents/                          ← MỖI AGENT = 1 FOLDER RIÊNG
│   │
│   ├── ui/                          ← 🎨 Agent UI (Dev A)
│   │   ├── __init__.py
│   │   ├── agent_ui.py              ← Main agent logic
│   │   ├── inputs/                  ← BD JSON, form image, ViewModel interface
│   │   ├── outputs/                 ← LoginWindow.xaml
│   │   ├── prompts/
│   │   │   └── agent_ui.md          ← System prompt (XAML gen rules)
│   │   └── templates/
│   │       └── Window.xaml.j2       ← Jinja2 template (nếu cần)
│   │
│   ├── logic/                       ← 🧠 Agent Logic (Dev B)
│   │   ├── __init__.py
│   │   ├── agent_logic.py           ← Main agent logic
│   │   ├── inputs/                  ← BD events, DD detail_specs, IService interfaces
│   │   ├── outputs/                 ← LoginViewModel.cs
│   │   └── prompts/
│   │       └── agent_logic.md       ← System prompt (MVVM + DI rules)
│   │
│   ├── service/                     ← ⚙️ Agent Service (Dev C)
│   │   ├── __init__.py
│   │   ├── agent_service.py         ← Main agent (route 3 loại)
│   │   ├── inputs/                  ← DD detail_specs, VBA code, Repo DTOs
│   │   ├── outputs/                 ← IAuthService.cs, AuthService.cs, NavigationService.cs
│   │   └── prompts/
│   │       ├── agent_service_form.md
│   │       ├── agent_service_macro.md
│   │       └── agent_service_module.md
│   │
│   ├── repo/                        ← 🗃️ Agent Repo (Dev D)
│   │   ├── __init__.py
│   │   ├── agent_repo.py            ← Main agent (Jinja2 + LLM)
│   │   ├── inputs/                  ← DD sheet_4 queries, table schemas
│   │   ├── outputs/                 ← IdPassEntity.cs, IdPassRepository.cs, DTOs
│   │   ├── prompts/
│   │   │   └── agent_repo.md        ← System prompt (Dapper + Oracle rules)
│   │   └── templates/
│   │       ├── Entity.cs.j2
│   │       ├── DTO.cs.j2
│   │       └── Interface.cs.j2
│   │
│   ├── report/                      ← 📊 Agent Report (Dev E)
│   │   ├── __init__.py
│   │   ├── agent_report.py          ← Main agent logic
│   │   ├── inputs/                  ← BD/DD JSON raw
│   │   ├── outputs/                 ← Report Excel/PDF
│   │   └── prompts/
│   │       └── agent_report.md
│   │
│   ├── graphview/                   ← 🔍 Agent GraphView (Dev F)
│   │   ├── __init__.py
│   │   ├── agent_graphview.py       ← Mapping gen + dependency build
│   │   ├── dependency_builder.py    ← Parse C# → build graph (deterministic)
│   │   ├── inputs/                  ← FE graph JSON, all agent outputs
│   │   ├── outputs/                 ← mapping_F_Login.json, dependency_F_Login.json
│   │   └── prompts/
│   │       └── agent_graphview.md
│   │
│   └── test/                        ← 🧪 Agent Test (Dev G)
│       ├── __init__.py
│       ├── agent_test.py            ← Main agent logic
│       ├── inputs/                  ← BD/DD JSON, all generated C#/XAML
│       ├── outputs/                 ← Test files, migration certificate
│       ├── golden_master/
│       │   ├── builder.py
│       │   ├── verifier.py
│       │   └── masters/
│       └── prompts/
│           └── agent_test.md
│
├── core/                            ← 🔧 SHARED — ít thay đổi
│   ├── __init__.py
│   ├── config.py                    ← Config loader (MongoDB, LLM endpoints)
│   ├── models.py                    ← Pydantic models (shared DTOs)
│   └── utils.py                     ← Common utilities (file IO, logging)
│
├── llm/                             ← 🤖 SHARED — ít thay đổi
│   ├── __init__.py
│   └── llm_client.py               ← LLM API client (OpenRouter, Alibaba)
│
├── pipeline/                        ← 🔄 SHARED — orchestration
│   ├── __init__.py
│   ├── orchestrator.py              ← Main pipeline (call agents in order)
│   └── file_planner.py              ← Gen file_plan.json
│
└── output/                          ← 📁 Final merged output (gitignored)
    └── {form_name}/
```

---

## Data Flow: inputs/ → outputs/ per Agent

> **Review:** Bạn vào `agents/{name}/inputs/` xem data vào, `agents/{name}/outputs/` xem kết quả  
> **Pipeline** tự copy output agent trước → input agent sau

| Agent | `inputs/` chứa gì | `outputs/` chứa gì |
|---|---|---|
| 🗃️ **Repo** | DD `sheet_4` queries JSON, `tables[]` schema, VBA form code | `IdPassEntity.cs`, `LoginRequest.cs`, `LoginResponse.cs`, `IIdPassRepository.cs`, `IdPassRepository.cs` |
| ⚙️ **Service** | DD `detail_specs[]`, VBA code, **Repo outputs** (DTOs + IRepo) | `IAuthService.cs`, `AuthService.cs`, `NavigationService.cs`, `CommonService.cs` |
| 🧠 **Logic** | BD `events[]`, DD `detail_specs[]`, **Service outputs** (IService) | `LoginViewModel.cs` |
| 🎨 **UI** | BD `screen_edit`, form image, **Logic outputs** (ViewModel bindings) | `LoginWindow.xaml` |
| 📊 **Report** | BD/DD JSON raw | Report Excel/PDF |
| 🔍 **GraphView** | FE graph JSON, **all agent outputs** (C#/XAML) | `mapping_F_Login.json`, `dependency_F_Login.json`, `review_F_Login.json` |
| 🧪 **Test** | BD/DD JSON, **all generated C#/XAML** | `Tests/UI/*.cs`, `Tests/Logic/*.cs`, `Tests/Service/*.cs`, `Tests/Repo/*.cs`, `Tests/Graph/*.cs`, `migration_certificate.json` |

### Pipeline copies data flow

```
orchestrator.py:
  1. Repo.run()     → agents/repo/outputs/
  2. Copy repo/outputs/ → service/inputs/       ← auto copy
  3. Service.run()  → agents/service/outputs/
  4. Copy service/outputs/ → logic/inputs/       ← auto copy
  5. Logic.run()    → agents/logic/outputs/
  6. Copy logic/outputs/ → ui/inputs/            ← auto copy
  7. UI.run()       → agents/ui/outputs/
  8. Copy all outputs/ → graphview/inputs/       ← auto copy
  9. GraphView.run()→ agents/graphview/outputs/
 10. Copy all → test/inputs/                     ← auto copy
 11. Test.run()     → agents/test/outputs/
 12. Merge all outputs/ → output/{form_name}/    ← final
```
```

---

## Conflict-Free Rules

### Rule 1: Mỗi agent = 1 folder

| Dev sửa | Chỉ touch files trong | Không touch |
|---|---|---|
| Dev A (UI) | `agents/ui/*` | `agents/logic/`, `agents/service/`... |
| Dev B (Logic) | `agents/logic/*` | `agents/ui/`, `agents/repo/`... |
| Dev C (Service) | `agents/service/*` | `agents/logic/`, `agents/repo/`... |
| Dev D (Repo) | `agents/repo/*` | `agents/service/`, `agents/ui/`... |
| Dev E (Report) | `agents/report/*` | tất cả agents khác |
| Dev F (GraphView) | `agents/graphview/*` | tất cả agents khác |
| Dev G (Test) | `agents/test/*` | tất cả agents khác |

### Rule 2: Shared code qua Interface/Contract

```python
# core/models.py — SHARED CONTRACT (1 người maintain)
@dataclass
class AgentInput:
    form_name: str
    bd_json: dict
    dd_json: dict

@dataclass
class AgentOutput:
    files: list[GeneratedFile]
    status: str  # "success" | "error"

# Mỗi agent implement cùng interface:
class BaseAgent(ABC):
    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput: ...
```

### Rule 3: Agent giao tiếp qua file, không import lẫn nhau

```
❌ WRONG: agents/service/agent_service.py  import agents.repo.agent_repo
✅ RIGHT: agents/service/agent_service.py  đọc output/ files từ Agent Repo
```

```python
# agents/service/agent_service.py
class ServiceAgent(BaseAgent):
    async def run(self, input: AgentInput) -> AgentOutput:
        # Đọc Repo output từ disk (KHÔNG import agent_repo)
        repo_output = load_json(f"output/{input.form_name}/Domain/Interfaces/")
        ...
```

---

## Execution Order (Pipeline)

```
pipeline/orchestrator.py gọi agents theo thứ tự:

 1.  pipeline/file_planner.py      → output/{form}/file_plan.json
     ↓
 2.  agents/repo/agent_repo.py     → Entity, DTO, Interface (Jinja2)
 3.  agents/repo/agent_repo.py     → Repository.cs (LLM)
     ↓
 4.  agents/service/agent_service.py → IService, Service.cs
     ↓
 5.  agents/logic/agent_logic.py   → ViewModel.cs
     ↓
 6.  agents/ui/agent_ui.py         → Window.xaml
     ↓
 7.  agents/graphview/agent_graphview.py → mapping + dependency
     ↓
 8.  agents/test/agent_test.py     → test cases + report
```

---

## Git Branching Strategy

```
main
 ├── feature/agent-ui          ← Dev A chỉ sửa agents/ui/
 ├── feature/agent-logic       ← Dev B chỉ sửa agents/logic/
 ├── feature/agent-service     ← Dev C chỉ sửa agents/service/
 ├── feature/agent-repo        ← Dev D chỉ sửa agents/repo/
 ├── feature/agent-report      ← Dev E chỉ sửa agents/report/
 ├── feature/agent-graphview   ← Dev F chỉ sửa agents/graphview/
 └── feature/agent-test        ← Dev G chỉ sửa agents/test/
```

> **Merge:** Không conflict vì mỗi branch chỉ sửa folder riêng  
> **Shared code:** `core/`, `llm/`, `pipeline/` → chỉ tech lead maintain trên branch riêng

---

## Token Budget

| Agent | Model | Tokens/form | 154 forms |
|---|---|---|---|
| Repo (Jinja2) | Template | 0 | 0 |
| Repo (LLM) | `qwen3-coder-480b` | ~3K | ~462K |
| Service | `qwen3-235b` | ~4K | ~616K |
| Logic | `qwen3-235b` | ~6K | ~924K |
| UI | `qwen3-coder-plus` | ~4K | ~616K |
| Test | `qwen3-235b` | ~3K | ~462K |
| **Total** | | **~20K** | **~3M tokens** |
