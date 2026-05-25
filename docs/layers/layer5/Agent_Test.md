# 🧪 Agent Test — Gen Test Cases từ BD/DD per Agent Output

> **Mục đích:** Đọc BD/DD JSON → sinh test cases cho từng agent output, verify migration đúng 100%  
> **Model:** `qwen3-235b-a22b` (gen test code) + Deterministic (run tests)  
> **Ref:** [AI_Agent_Workflow.md](./AI_Agent_Workflow.md) — Slide 6b, 6c, 6d

---

## Input / Output

| | Nguồn | Chi tiết |
|---|---|---|
| **Input 1** | BD JSON | `sheet_2_layout.events[]`, `sheet_3_screen_edit` |
| **Input 2** | DD JSON | `sheet_3_detail_specs[]`, `sheet_4_sel_query_templates[]` |
| **Input 3** | Generated C# / XAML files | Output từ all agents |
| **Output** | Test files per agent | `Tests/{Agent}/{Form}*.cs` (xUnit) |

---

## Layer5 Files

```
agents/agent_test.py             ← Main agent logic
core/prompts/agent_test.md       ← System prompt (xUnit rules)
tests/
├── ui/                          ← Agent UI tests
├── logic/                       ← Agent Logic tests
├── service/                     ← Agent Service tests
├── repo/                        ← Agent Repo tests
└── graph/                       ← Agent GraphView tests
```

---

## Test Generation per Agent

### ① Agent UI Tests

> **Source:** BD `sheet_3_screen_edit` (controls) + BD `sheet_2_layout.events[]`  
> **Target:** `Views/{Form}Window.xaml`

| Test File | BD/DD Source | Kiểm tra |
|---|---|---|
| `Tests/UI/LoginWindow_ControlTests.cs` | BD `sheet_3_screen_edit.controls[]` | Control tồn tại, type đúng, label đúng |
| `Tests/UI/LoginWindow_BindingTests.cs` | BD `events[].trigger` | DataBinding đúng property, Command đúng tên |
| `Tests/UI/LoginWindow_LayoutTests.cs` | BD `screen_edit.positions[]` | Grid layout, row/column đúng |

```json
{
  "agent": "UI",
  "source_file": "Views/LoginWindow.xaml",
  "test_cases": [
    {
      "id": "UI_TC001",
      "bd_source": "sheet_3_screen_edit.controls[0]",
      "check": "TextBox x:Name='txtID' exists",
      "expected": "TextBox with Text='{Binding LoginId}'"
    },
    {
      "id": "UI_TC002",
      "bd_source": "sheet_3_screen_edit.controls[1]",
      "check": "PasswordBox x:Name='txtPass' exists",
      "expected": "PasswordBox bound to Password"
    },
    {
      "id": "UI_TC003",
      "bd_source": "sheet_2_layout.events['閉じる_Click']",
      "check": "Button Command binding",
      "expected": "Command='{Binding CloseCommand}'"
    }
  ]
}
```

---

### ② Agent Logic Tests

> **Source:** BD `events[]` + DD `sheet_3_detail_specs[]` (steps)  
> **Target:** `ViewModels/{Form}ViewModel.cs`

| Test File | BD/DD Source | Kiểm tra |
|---|---|---|
| `Tests/Logic/LoginViewModel_CommandTests.cs` | BD `events[].trigger` | Command tồn tại, type RelayCommand |
| `Tests/Logic/LoginViewModel_PropertyTests.cs` | BD `events[].controls` | Property tồn tại, INotifyPropertyChanged |
| `Tests/Logic/LoginViewModel_DITests.cs` | DD `detail_specs[].steps` | DI inject đúng services |
| `Tests/Logic/LoginViewModel_FlowTests.cs` | DD `detail_specs[].steps` | Logic flow khớp DD steps |

```json
{
  "agent": "Logic",
  "source_file": "ViewModels/LoginViewModel.cs",
  "test_cases": [
    {
      "id": "LG_TC001",
      "bd_source": "events['txtPass_AfterUpdate']",
      "check": "LoginCommand exists as RelayCommand",
      "expected": "public RelayCommand LoginCommand { get; }"
    },
    {
      "id": "LG_TC002",
      "dd_source": "detail_specs[F003].steps[1]",
      "check": "Login flow calls AuthService.AuthenticateAsync",
      "expected": "_authService.AuthenticateAsync(new LoginRequest{...})"
    },
    {
      "id": "LG_TC003",
      "dd_source": "detail_specs[F003].steps[2]",
      "check": "Error message matches VBA MsgBox",
      "expected": "パスワードが違います!!"
    },
    {
      "id": "LG_TC004",
      "bd_source": "events['閉じる_Click']",
      "check": "CloseCommand calls Window.Close()",
      "expected": "CloseCommand invokes close action"
    }
  ]
}
```

---

### ③ Agent Service Tests

> **Source:** DD `sheet_3_detail_specs[]` (steps with DLookup/DCount) + DD `sheet_4` queries  
> **Target:** `Application/Services/AuthService.cs`, `NavigationService.cs`, `CommonService.cs`

| Test File | DD Source | Kiểm tra |
|---|---|---|
| `Tests/Service/AuthService_MethodTests.cs` | DD `detail_specs[].steps` (DLookup) | Method tồn tại, return type đúng |
| `Tests/Service/AuthService_DITests.cs` | DD queries → Repo inject | DI constructor inject đúng IRepo |
| `Tests/Service/NavigationService_Tests.cs` | DD events (RunMacro) | Macro → NavigateTo method |
| `Tests/Service/CommonService_Tests.cs` | DD events (Call Module) | Module → Utility method |

```json
{
  "agent": "Service",
  "test_cases": [
    {
      "id": "SV_TC001",
      "source_file": "Application/Services/AuthService.cs",
      "dd_source": "detail_specs[F003].steps['DLookup']",
      "check": "AuthenticateAsync method exists",
      "expected": "Task<LoginResponse> AuthenticateAsync(LoginRequest request)"
    },
    {
      "id": "SV_TC002",
      "source_file": "Application/Services/AuthService.cs",
      "dd_source": "detail_specs[F003].steps['DCount']",
      "check": "AuthService injects IChikuCdRepository",
      "expected": "constructor param: IChikuCdRepository"
    },
    {
      "id": "SV_TC003",
      "source_file": "Application/Services/NavigationService.cs",
      "dd_source": "detail_specs[F003].steps['RunMacro AutoExec_A']",
      "check": "NavigateToMain method exists",
      "expected": "void NavigateToMain()"
    },
    {
      "id": "SV_TC004",
      "source_file": "Application/Services/CommonService.cs",
      "dd_source": "detail_specs[F002].steps['Call タイマーを開く']",
      "check": "StartSplash method exists",
      "expected": "Task StartSplash()"
    }
  ]
}
```

---

### ④ Agent Repo Tests

> **Source:** DD `sheet_4_sel_query_templates[]` + MongoDB `tables[]`  
> **Target:** `IdPassEntity.cs`, `IdPassRepository.cs`, `ChikuCdRepository.cs`

| Test File | DD Source | Kiểm tra |
|---|---|---|
| `Tests/Repo/IdPassEntity_FieldTests.cs` | DD `sheet_4` columns | Entity fields khớp table schema |
| `Tests/Repo/IdPassRepository_MethodTests.cs` | DD `sheet_4` queries | SQL method tồn tại, SQL syntax đúng |
| `Tests/Repo/IdPassRepository_SQLTests.cs` | DD `sheet_4.sql` | Oracle SQL khớp, params `:param` đúng |
| `Tests/Repo/ChikuCdRepository_Tests.cs` | DD inline DCount | GetCountAsync SQL đúng |
| `Tests/Repo/LoginDTO_Tests.cs` | BD form controls | Request/Response DTO fields đúng |

```json
{
  "agent": "Repo",
  "test_cases": [
    {
      "id": "RP_TC001",
      "source_file": "Domain/Entities/IdPassEntity.cs",
      "dd_source": "sheet_4[F000_SelQuery01].columns",
      "check": "Entity has field 工事担当_担当者名 mapped",
      "expected": "public string KojiTantoName { get; set; }"
    },
    {
      "id": "RP_TC002",
      "source_file": "Infrastructure/Repositories/IdPassRepository.cs",
      "dd_source": "sheet_4[F000_SelQuery01].sql",
      "check": "GetLoginUserAsync SQL matches DD",
      "expected": "SELECT ... FROM T_ID_PASS main WHERE main.ID = :id"
    },
    {
      "id": "RP_TC003",
      "source_file": "Infrastructure/Repositories/IdPassRepository.cs",
      "dd_source": "sheet_4[F000_SelQuery01]",
      "check": "Oracle param binding uses ':'",
      "expected": "new { id } — NOT @id"
    },
    {
      "id": "RP_TC004",
      "source_file": "Infrastructure/Repositories/ChikuCdRepository.cs",
      "dd_source": "inline DCount(T023_地区CD設定)",
      "check": "GetCountAsync returns int",
      "expected": "ExecuteScalarAsync<int>(\"SELECT COUNT(*) FROM T023_地区CD設定\")"
    },
    {
      "id": "RP_TC005",
      "source_file": "Application/DTOs/LoginRequest.cs",
      "bd_source": "sheet_3_screen_edit.controls[txtID, txtPass]",
      "check": "Request DTO has LoginId and Password",
      "expected": "{ LoginId: string, Password: string }"
    }
  ]
}
```

---

### ⑤ Agent GraphView Tests

> **Source:** FE Graph API + generated WPF files  
> **Target:** `mapping_{form}.json`, `dependency_{form}.json`

| Test File | Source | Kiểm tra |
|---|---|---|
| `Tests/Graph/LoginMapping_NodeTests.cs` | FE graph nodes | Mỗi VBA node có WPF mapping |
| `Tests/Graph/LoginMapping_EdgeTests.cs` | FE graph edges | Mỗi VBA edge có WPF edge |
| `Tests/Graph/LoginDependency_DITests.cs` | WPF dependency graph | DI chain đúng (Window→VM→Service→Repo) |
| `Tests/Graph/LoginDependency_CoverageTests.cs` | VBA graph vs WPF graph | review.missing == 0 |

```json
{
  "agent": "GraphView",
  "test_cases": [
    {
      "id": "GV_TC001",
      "source_file": "mapping_F_Login.json",
      "check": "All VBA nodes have wpf_id mapping",
      "expected": "node_mapping.length >= vba_graph.nodes.length"
    },
    {
      "id": "GV_TC002",
      "source_file": "mapping_F_Login.json",
      "check": "All VBA edges have wpf edge mapping",
      "expected": "edge_mapping covers: event, opens query, opens form, closes form, calls, references"
    },
    {
      "id": "GV_TC003",
      "source_file": "dependency_F_Login.json",
      "check": "DI chain complete",
      "expected": "window → vm → service → repo → entity (no broken links)"
    },
    {
      "id": "GV_TC004",
      "source_file": "dependency_F_Login.json",
      "check": "No missing migration items",
      "expected": "review.missing == 0, review.status == 'PASS'"
    }
  ]
}
```

---

## Test Summary Table (F_Login)

| Agent | Source File | Test File | # Tests | BD/DD Source |
|---|---|---|---|---|
| **UI** | `LoginWindow.xaml` | `Tests/UI/LoginWindow_*.cs` | 3+ | BD `sheet_3_screen_edit` |
| **Logic** | `LoginViewModel.cs` | `Tests/Logic/LoginViewModel_*.cs` | 4+ | BD `events[]` + DD `detail_specs[]` |
| **Service** | `AuthService.cs` + others | `Tests/Service/*_Tests.cs` | 4+ | DD `detail_specs[]` steps |
| **Repo** | Entity + Repository | `Tests/Repo/*_Tests.cs` | 5+ | DD `sheet_4` queries + `tables[]` |
| **GraphView** | mapping + dependency | `Tests/Graph/*_Tests.cs` | 4+ | FE graph + WPF files |

---

## Logic Flow

```
1. agent_test.py nhận form_name
    ↓
2. Load BD JSON → extract controls, events
   Load DD JSON → extract detail_specs, queries
    ↓
3. Per agent:
   ├── UI:       BD screen_edit → control/binding tests
   ├── Logic:    BD events + DD steps → command/flow tests
   ├── Service:  DD steps (DLookup/RunMacro/Call) → method/DI tests
   ├── Repo:     DD sheet_4 queries → Entity/SQL/param tests
   └── GraphView: FE graph + mapping → coverage tests
    ↓
4. LLM gen xUnit test code per test case
    ↓
5. Run tests → report
```

---

## Migration Certificate

```
┌──────────────────────────────────────────┐
│  🏆 MIGRATION CERTIFICATE — F_Login     │
├──────────────────────────────────────────┤
│  Agent UI       3/3  ✅ PASS            │
│  Agent Logic    4/4  ✅ PASS            │
│  Agent Service  4/4  ✅ PASS            │
│  Agent Repo     5/5  ✅ PASS            │
│  Agent GraphView 4/4 ✅ PASS            │
├──────────────────────────────────────────┤
│  Total: 20/20 — 100% ✅                 │
│  Status: MIGRATION CERTIFIED 🏆         │
└──────────────────────────────────────────┘
```

---

## Verification

- [ ] Mỗi agent output có ít nhất 3 test cases
- [ ] Test cases trace back tới BD/DD source (field `bd_source`/`dd_source`)
- [ ] Error messages khớp exact (Japanese text)
- [ ] SQL queries đúng Oracle syntax (`:param` not `@param`)
- [ ] DI chain test: Window→VM→Service→Repo→Entity
- [ ] GraphView coverage: `review.missing == 0`
- [ ] `status == "MIGRATION CERTIFIED"` khi all pass
