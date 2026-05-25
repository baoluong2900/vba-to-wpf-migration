# 🔍 Agent GraphView — Mapping File + Dependency Review

> **Mục đích:** AI Agent tạo file **mapping** (JP→EN, VBA→WPF) + kết hợp Repo/Logic output tạo **dependency graph** → đảm bảo migration không ảnh hưởng  
> **Model:** `qwen3-235b-a22b-instruct-2507` (mapping gen) + Deterministic (dependency build)  
> **Ref:** [AI_Agent_Workflow.md](./AI_Agent_Workflow.md) — Slide 6

---

## 2 Nhiệm Vụ

| # | Task | Input | Output | Tool |
|---|---|---|---|---|
| ① | **Gen Mapping File** | VBA graph (FE) + generated WPF files | `mapping_{form}.json` | **AI Agent** |
| ② | **Build Dependency + Review** | Mapping file + Repo/Logic/Service outputs | Dependency graph + Review report | **Deterministic** |

> **User tool:** Bạn viết tool convert GraphView FE source → GraphView WPF  
> **Agent output:** Mapping file để tool biết tên cũ ↔ tên mới

---

## Input / Output

| | Nguồn | Chi tiết |
|---|---|---|
| **Input 1** | FE GraphView API `/api/graph?name=F_Login` | VBA dependency data (nodes, edges) |
| **Input 2** | Agent Repo output | Entity, IRepo, Repository files |
| **Input 3** | Agent Service output | IService, Service files |
| **Input 4** | Agent Logic output | ViewModel files |
| **Input 5** | Agent UI output | XAML Window files |
| **Output 1** | `mapping_{form}.json` | JP→EN name mapping + VBA→WPF file mapping |
| **Output 2** | `dependency_{form}.json` | WPF dependency graph (Cytoscape) |
| **Output 3** | `review_{form}.json` | Missing/extra items report |

---

## Layer5 Files

```
agents/agent_graphview.py        ← Mapping gen + dependency build
core/prompts/agent_graphview.md  ← Mapping rules (JP→EN naming)
ast/dependency_builder.py        ← Parse C# → build graph (deterministic)
```

---

## ① Gen Mapping File (AI Agent)

### Logic Flow

```
1. Load VBA graph từ FE API (nodes: forms, events, tables, macros, modules)
2. Load generated WPF files (from Agent UI/Logic/Service/Repo)
3. AI Agent tạo mapping:
   ├── JP name → EN name (table, field, event, form)
   ├── VBA source file → WPF target file
   ├── VBA function → C# method
   └── VBA table → Entity class
4. Output: mapping_{form}.json
```

### Mapping Rules

```
VBA (Japanese)                    WPF (English)
──────────────────                ────────────────────
F_Login                          → LoginWindow
T_ID_PASS                       → IdPassEntity
管理者FLG                        → KanriFLG (property)
工事担当_担当者名                 → KojiTantoName
txtPass_AfterUpdate              → LoginCommand
閉じる_Click                     → CloseCommand
Form_Open                       → constructor / OnNavigatedTo
DLookup("Pass","T_ID_Pass")     → IdPassRepository.GetByIdAsync()
DCount("T023_地区CD設定")        → ChikuCdRepository.GetCountAsync()
DoCmd.RunMacro "AutoExec_A"     → NavigationService.NavigateToMain()
Call タイマーを開く               → CommonService.StartSplash()
```

### VBA Graph Input (từ FE API `/api/graph?name=F_Login&type=form`)

> FE graph cấu trúc: `form → event(handler) → {opens form, closes form, opens query, calls macro, references module}`

```json
{
  "elements": {
    "nodes": [
      { "data": { "id": "form:F_Login",                      "label": "F_Login",           "type": "form",   "badge": "9 events" } },
      { "data": { "id": "event:F_Login::Form_Open",          "label": "Form_Open",         "type": "event"  } },
      { "data": { "id": "event:F_Login::Form_Load",          "label": "Form_Load",         "type": "event"  } },
      { "data": { "id": "event:F_Login::txtPass_AfterUpdate","label": "txtPass_AfterUpdate","type": "event"  } },
      { "data": { "id": "event:F_Login::閉じる_Click",        "label": "閉じる_Click",       "type": "event"  } },
      { "data": { "id": "query:Q000_T_LoginUser",            "label": "Q000_T_LoginUser",  "type": "query"  } },
      { "data": { "id": "query:Q000_T_ID_PASS",              "label": "Q000_T_ID_PASS",    "type": "query"  } },
      { "data": { "id": "macro:AutoExec_A",                  "label": "AutoExec_A",        "type": "macro"  } },
      { "data": { "id": "form:F_Main",                       "label": "F_Main",            "type": "form"   } },
      { "data": { "id": "module:Common",                     "label": "Common",            "type": "module" } }
    ],
    "edges": [
      { "data": { "source": "form:F_Login",                       "target": "event:F_Login::Form_Open",          "label": "event" } },
      { "data": { "source": "form:F_Login",                       "target": "event:F_Login::Form_Load",          "label": "event" } },
      { "data": { "source": "form:F_Login",                       "target": "event:F_Login::txtPass_AfterUpdate","label": "event" } },
      { "data": { "source": "form:F_Login",                       "target": "event:F_Login::閉じる_Click",        "label": "event" } },
      { "data": { "source": "event:F_Login::Form_Open",           "target": "query:Q000_T_LoginUser",            "label": "opens query" } },
      { "data": { "source": "event:F_Login::txtPass_AfterUpdate", "target": "query:Q000_T_ID_PASS",              "label": "opens query" } },
      { "data": { "source": "event:F_Login::txtPass_AfterUpdate", "target": "macro:AutoExec_A",                  "label": "calls" } },
      { "data": { "source": "event:F_Login::txtPass_AfterUpdate", "target": "module:Common",                     "label": "references" } },
      { "data": { "source": "macro:AutoExec_A",                   "target": "form:F_Main",                       "label": "opens form" } },
      { "data": { "source": "event:F_Login::閉じる_Click",         "target": "form:F_Login",                      "label": "closes form" } }
    ]
  }
}
```

### Edge Types (FE graph labels)

| Edge Label | Ý nghĩa | WPF Tương ứng |
|---|---|---|
| `event` | Form → Event handler | Window → Command/Method |
| `opens query` | Event → DoCmd.OpenQuery | Service → Repository method |
| `opens form` | Event/Macro → DoCmd.OpenForm | NavigationService.NavigateTo() |
| `closes form` | Event → DoCmd.Close acForm | Window.Close() |
| `calls` | Event → DoCmd.RunMacro | Service method call |
| `references` | Event → Call Module procedure | CommonService method |
| `record source` | Form → RecordSource query | ViewModel constructor query |
| `opens report` | Event → DoCmd.OpenReport | ReportService.Show() |

### Output: `mapping_F_Login.json`

```json
{
  "form_name": "F_Login",

  "node_mapping": [
    { "vba_id": "form:F_Login",              "wpf_id": "window:LoginWindow",          "wpf_file": "Views/LoginWindow.xaml" },
    { "vba_id": "event:F_Login::Form_Open",  "wpf_id": "method:LoginViewModel.OnLoaded", "wpf_file": "ViewModels/LoginViewModel.cs" },
    { "vba_id": "event:F_Login::txtPass_AfterUpdate", "wpf_id": "command:LoginViewModel.LoginCommand", "wpf_file": "ViewModels/LoginViewModel.cs" },
    { "vba_id": "event:F_Login::閉じる_Click", "wpf_id": "command:LoginViewModel.CloseCommand", "wpf_file": "ViewModels/LoginViewModel.cs" },
    { "vba_id": "query:Q000_T_LoginUser",    "wpf_id": "method:IdPassRepository.GetLoginUserAsync", "wpf_file": "Infrastructure/Repositories/IdPassRepository.cs" },
    { "vba_id": "query:Q000_T_ID_PASS",      "wpf_id": "method:IdPassRepository.GetAllAsync",       "wpf_file": "Infrastructure/Repositories/IdPassRepository.cs" },
    { "vba_id": "macro:AutoExec_A",          "wpf_id": "method:NavigationService.NavigateToMain",    "wpf_file": "Application/Services/NavigationService.cs" },
    { "vba_id": "form:F_Main",               "wpf_id": "window:MainWindow",           "wpf_file": "Views/MainWindow.xaml" },
    { "vba_id": "module:Common",             "wpf_id": "service:CommonService",        "wpf_file": "Application/Services/CommonService.cs" }
  ],

  "edge_mapping": [
    { "vba_edge": "form:F_Login → event:Form_Open (event)",                        "wpf_edge": "window:LoginWindow → method:OnLoaded (DataContext)" },
    { "vba_edge": "event:Form_Open → query:Q000_T_LoginUser (opens query)",         "wpf_edge": "method:OnLoaded → method:GetLoginUserAsync (calls)" },
    { "vba_edge": "event:txtPass_AfterUpdate → macro:AutoExec_A (calls)",           "wpf_edge": "command:LoginCommand → method:NavigateToMain (calls)" },
    { "vba_edge": "event:txtPass_AfterUpdate → module:Common (references)",         "wpf_edge": "command:LoginCommand → service:CommonService (DI inject)" },
    { "vba_edge": "macro:AutoExec_A → form:F_Main (opens form)",                   "wpf_edge": "method:NavigateToMain → window:MainWindow (navigate)" },
    { "vba_edge": "event:閉じる_Click → form:F_Login (closes form)",                "wpf_edge": "command:CloseCommand → Window.Close() (close)" }
  ],

  "name_mapping": [
    { "jp": "F_Login",           "en": "LoginWindow",        "type": "form" },
    { "jp": "F_Main",            "en": "MainWindow",         "type": "form" },
    { "jp": "Q000_T_LoginUser",  "en": "GetLoginUserAsync",  "type": "query" },
    { "jp": "AutoExec_A",        "en": "NavigateToMain",     "type": "macro" },
    { "jp": "閉じる_Click",       "en": "CloseCommand",       "type": "event" },
    { "jp": "txtPass_AfterUpdate","en": "LoginCommand",      "type": "event" },
    { "jp": "Common",            "en": "CommonService",      "type": "module" }
  ]
}
```

---

## ② Build Dependency + Review (Deterministic)

### Logic Flow

```
1. Parse generated C# files:
   ├── Extract: class names, DI injections, method calls, using statements
   └── Source: Agent UI + Logic + Service + Repo outputs

2. Build WPF Dependency Graph:
   LoginWindow.xaml
     → DataContext: LoginViewModel
       → DI: IAuthService
         → DI: IIdPassRepository
           → Entity: IdPassEntity
         → DI: IChikuCdRepository
       → DI: INavigationService
       → DI: ICommonService

3. Load VBA Graph (from FE API / mapping file)

4. Compare: mỗi VBA node/edge phải có WPF counterpart
   ├── MATCH: VBA edge có WPF mapping
   ├── MISSING: VBA edge chưa implement → migration risk ⚠️
   └── EXTRA: WPF edge không có VBA source → new feature

5. Output: dependency + review report
```

### Output: `dependency_F_Login.json`

```json
{
  "form_name": "F_Login",

  "wpf_graph": {
    "nodes": [
      { "id": "window:LoginWindow",           "type": "view",       "file": "Views/LoginWindow.xaml" },
      { "id": "vm:LoginViewModel",            "type": "viewmodel",  "file": "ViewModels/LoginViewModel.cs" },
      { "id": "service:AuthService",          "type": "service",    "file": "Application/Services/AuthService.cs" },
      { "id": "service:NavigationService",    "type": "service",    "file": "Application/Services/NavigationService.cs" },
      { "id": "service:CommonService",        "type": "service",    "file": "Application/Services/CommonService.cs" },
      { "id": "repo:IdPassRepository",        "type": "repository", "file": "Infrastructure/Repositories/IdPassRepository.cs" },
      { "id": "repo:ChikuCdRepository",       "type": "repository", "file": "Infrastructure/Repositories/ChikuCdRepository.cs" },
      { "id": "entity:IdPassEntity",          "type": "entity",     "file": "Domain/Entities/IdPassEntity.cs" }
    ],
    "edges": [
      { "source": "window:LoginWindow",    "target": "vm:LoginViewModel",        "label": "DataContext" },
      { "source": "vm:LoginViewModel",     "target": "service:AuthService",      "label": "DI inject" },
      { "source": "vm:LoginViewModel",     "target": "service:NavigationService","label": "DI inject" },
      { "source": "vm:LoginViewModel",     "target": "service:CommonService",    "label": "DI inject" },
      { "source": "service:AuthService",   "target": "repo:IdPassRepository",    "label": "DI inject" },
      { "source": "service:AuthService",   "target": "repo:ChikuCdRepository",   "label": "DI inject" },
      { "source": "repo:IdPassRepository", "target": "entity:IdPassEntity",      "label": "returns" }
    ]
  },

  "review": {
    "matched": 8,
    "missing": 0,
    "extra": 0,
    "missing_items": [],
    "status": "PASS"
  }
}
```

### Review Report (khi có MISSING)

```json
{
  "review": {
    "matched": 7,
    "missing": 1,
    "extra": 0,
    "missing_items": [
      {
        "vba_source": "AutoExec_Restart → OpenForm F022_ベースオフィス",
        "expected_wpf": "NavigationService.NavigateToSetup()",
        "risk": "HIGH",
        "note": "Migration sẽ thiếu navigation path khi branch count = 0"
      }
    ],
    "status": "MISMATCH ⚠️"
  }
}
```

---

## Pipeline Integration

```
Agent UI    ──┐
Agent Logic ──┤
Agent Service─┼──→ Agent GraphView
Agent Repo  ──┘         │
                        ├── ① Gen mapping file (AI)
FE GraphView ───────────┤
                        ├── ② Build dependency graph (deterministic)
                        └── ③ Review report → PASS / MISMATCH
                                │
                        User tool: mapping file → convert FE GraphView → WPF GraphView
```

---

## Verification

- [ ] Mapping file cover tất cả JP→EN names (tables, fields, controls)
- [ ] File mapping cover tất cả VBA source → WPF target
- [ ] Method mapping cover tất cả VBA calls → C# methods
- [ ] WPF dependency graph đúng (DI chain: Window→VM→Service→Repo→Entity)
- [ ] `review.missing == 0` → PASS (migration safe)
- [ ] `review.status == "PASS"` trước khi chạy user conversion tool
