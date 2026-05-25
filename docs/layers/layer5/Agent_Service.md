# ⚙️ Agent Service — Gen Service Layer

> **Mục đích:** Đọc DD logic + Macro + Module → sinh Service C# theo 3 loại  
> **Model:** `qwen3-235b-a22b-instruct-2507` (~4K tokens/form, think mode)  
> **Ref:** [AI_Agent_Workflow.md](./AI_Agent_Workflow.md) — Slide 3

---

## Input / Output

| | Nguồn | Chi tiết |
|---|---|---|
| **Input 1** | DD JSON `sheet_3_detail_specs` | Event logic (steps, event_trigger) |
| **Input 2** | MongoDB `forms.functions[]` | VBA code gốc (handler, code, references) |
| **Input 3** | MongoDB `macros[]` | Macro steps, references |
| **Input 4** | MongoDB `modules[]` | Module VBA code (handler, code) |
| **Input 5** | Agent Repo output: `LoginRequest.cs` | DTO — param cho Service method |
| **Input 6** | Agent Repo output: `LoginResponse.cs` | DTO — return type |
| **Input 7** | Agent Repo output: `IUserRepository.cs` | Interface — inject vào Service (DI) |
| **Input 8** | Agent Repo output: `UserEntity.cs` | Entity — dùng map fields trong logic |
| **Output 1** | `Application/Interfaces/IAuthService.cs` | Interface — Jinja2 |
| **Output 2** | `Application/Services/AuthService.cs` | Implementation — LLM |
| **Output 3** | `Application/Services/NavigationService.cs` | Macro → Navigation |
| **Output 4** | `Application/Services/CommonService.cs` | Module → Utility |

> **Output → downstream:** `IAuthService.cs` + DTOs → Agent Logic (ViewModel inject DI)

---

## 3 Loại Service (chia theo source)

| Loại | Source | Input | Output | Ví dụ |
|:---:|---|---|---|---|
| **Form Service** | DD `sheet_3` + Repo DTOs | Events có query/logic | `AuthService.cs` + DTOs | Login, CRUD |
| **Macro Service** | DD events + MongoDB `macros[]` | Macro steps + VBA code | `NavigationService.cs` | OpenForm, RunSQL |
| **Module Service** | DD events + MongoDB `modules[]` | Module code + VBA code | `CommonService.cs` | Utility functions |

---

## Layer5 Folder / Files

```
backend/layer5/
├── agents/
│   └── agent_service.py              ← Main agent (route 3 loại)
├── core/
│   └── prompts/
│       ├── agent_service_form.md     ← Prompt cho Form Service
│       ├── agent_service_macro.md    ← Prompt cho Macro Service
│       └── agent_service_module.md   ← Prompt cho Module Service
└── codegen/
    └── templates/
        └── Interface.cs.j2          ← IService interface template
```

---

## Logic Flow

```
agent_service.py nhận form_name
    ↓
1. Scan DD detail_specs → events nào có query/DLookup/DCount?
   → Tạo Form Service (AuthService, CrudService...)
    ↓
2. Scan DD detail_specs → events nào gọi RunMacro?
   → Lấy macro từ MongoDB → Tạo Macro Service (NavigationService...)
    ↓
3. Scan DD detail_specs → events nào gọi module procedure?
   → Lấy module từ MongoDB → Tạo Module Service (TimerService...)
    ↓
4. Output: N service files
```

---

## ① Form Service (DD → Business Logic + DTOs)

> Dành cho màn hình có tương tác query (DLookup, DCount, RunSQL...)  
> Input: DD `sheet_3_detail_specs` + DD queries + MongoDB `forms.functions[].code`  
> Output: Service.cs **+ Request/Response DTOs**

### Input: `service_inputs/F_Login_form.json`

> Gom theo event — mỗi event = 1 chunk chứa đủ DD + VBA + queries

```json
{
  "form_name": "F_Login",
  "service_type": "form",

  "events": [
    {
      "module_id": "F003",
      "module_name": "パスワード：",
      "event_trigger": "更新後処理",
      "event_content": "パスワードフィールドの更新後に、IDとパスワードによるログイン認証を行い...",
      "steps": [
        {
          "step": "2. 主処理",
          "detail": "2.1. IDフィールドが空の場合のチェック\n2.2. パスワードフィールドが空の場合のチェック\n2.3. テーブル『T_ID_Pass』からIDに一致する管理者フラグを取得する\n2.3.2. 管理者フラグが0の場合エラー\n2.4. テーブル『T_ID_pass』からIDに一致するパスワードを取得する\n2.5. パスワード一致 → F_Login閉じる → T023_地区CD設定カウント\n2.6. パスワード不一致 → エラーメッセージ表示"
        },
        {
          "step": "3. 終了処理",
          "detail": "Err_Shoriで通信接続エラーメッセージ表示"
        }
      ],
      "vba_code": "Dim res\nDim res1\nOn Error GoTo Err_Shori\n If IsNull(Me.txtID) Then\n  MsgBox \"IDを入力してください\"\n  Exit Sub\n End If\n If IsNull(Me.txtPass) Then\n  MsgBox \"パスワードを入力してください\"\n  Exit Sub\n End If\n res1 = DLookup(\"管理者FLG\", \"T_ID_Pass\", \"ID='\" & Me.txtID & \"'\")\n If res1 = 0 Then\n  MsgBox \"施工管理ではありませんのでログインできません！！\"\n  Exit Sub\n Else\n  res = DLookup(\"Pass\", \"T_ID_pass\", \"ID='\" & Me.txtID & \"'\")\n  If IsNull(res) Then\n   MsgBox \"該当するID,PWがありません！！\"\n   Exit Sub\n  End If\n End If\n If res = Me.txtPass Then\n  DoCmd.Close acForm, \"F_Login\"\n  RCount = DCount(\"*\", \"T023_地区CD設定\")\n  If RCount = 0 Then\n   DoCmd.RunMacro \"AutoExec_Restart\"\n  Else\n   Call タイマーを開く\n   DoCmd.RunMacro \"AutoExec_A\"\n  End If\n Else\n  MsgBox \"パスワードが異なります！！\"\n End If\nErr_Shori:\n MsgBox \"通信接続エラーです！！\"",
      "references": {
        "forms": ["F_Login"],
        "macros": ["AutoExec_Restart", "AutoExec_A"],
        "tables": ["T_ID_Pass", "T023_地区CD設定"]
      },
      "queries": ["Q000_T_LoginUser"]
    }
  ]
}
```

### → Output 1: `IAuthService.cs` (Interface — Jinja2)

```csharp
namespace vba_brain.Application.Interfaces;

public interface IAuthService
{
    Task<LoginResponse> AuthenticateAsync(LoginRequest request);
}
```

### → Output 2: `AuthService.cs` (LLM)

```csharp
namespace vba_brain.Application.Services;

public class AuthService : IAuthService
{
    private readonly IUserRepository _userRepo;

    public AuthService(IUserRepository userRepo) => _userRepo = userRepo;

    // F003: txtPass_AfterUpdate → ログイン認証
    public async Task<LoginResponse> AuthenticateAsync(LoginRequest request)
    {
        // DD 2.1: ID空チェック
        if (string.IsNullOrEmpty(request.LoginId))
            return new LoginResponse { Success = false, ErrorMessage = "IDを入力してください" };

        // DD 2.2: パスワード空チェック
        if (string.IsNullOrEmpty(request.Password))
            return new LoginResponse { Success = false, ErrorMessage = "パスワードを入力してください" };

        // DD 2.3: ユーザー取得 (Q000_T_LoginUser)
        var user = await _userRepo.GetByIdAsync(request.LoginId);
        if (user == null)
            return new LoginResponse { Success = false, ErrorMessage = "該当ログインID,PWを確認!!" };

        // DD 2.3.2: 管理FLGチェック
        if (user.KanriFLG == 0)
            return new LoginResponse { Success = false, ErrorMessage = "本工事管理ではありませんのでログインできません!!" };

        // DD 2.4: パスワード照合
        if (user.Pass != request.Password)
            return new LoginResponse { Success = false, ErrorMessage = "パスワードが違います!!" };

        // DD 2.5: 支店CDルーティング (DCount T023_地区CD設定)
        var branchCount = await _userRepo.GetBranchCountAsync();
        return new LoginResponse
        {
            Success = true,
            HasBranch = branchCount > 0,
            UserName = user.KojiTantoName
        };
    }
}
```

### → Output 3: `LoginRequest.cs` (DTO)

```csharp
namespace vba_brain.Application.DTOs;

public class LoginRequest
{
    public string LoginId { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
}
```

### → Output 4: `LoginResponse.cs` (DTO)

```csharp
namespace vba_brain.Application.DTOs;

public class LoginResponse
{
    public bool Success { get; set; }
    public string? ErrorMessage { get; set; }
    public bool HasBranch { get; set; }
    public string? UserName { get; set; }
}
```

---

## ② Macro Service (DD events + MongoDB macros → Navigation/Action)

> Dành cho events có gọi RunMacro / 参照マクロ  
> Input: DD events + MongoDB `macros` collection  
> Output: NavigationService.cs  
> **Note:** Macro có thể gọi OpenForm (→ navigation) + OpenQuery (→ repo call)

### Input: `service_inputs/F_Login_macro.json`

> Gom theo event — mỗi event = 1 chunk chứa đủ DD + VBA + macro data

```json
{
  "form_name": "F_Login",
  "service_type": "macro",

  "events": [
    {
      "module_id": "F003",
      "event_trigger": "更新後処理",
      "macro_call": "RunMacro AutoExec_A / AutoExec_Restart",
      "detail": "2.5.4. レコード数が0の場合、マクロ『AutoExec_Restart』を実行する\n2.5.5. レコード数が存在する場合、マクロ『AutoExec_A』を実行する",
      "vba_code": "RCount = DCount(\"*\", \"T023_地区CD設定\")\nIf RCount = 0 Then\n  DoCmd.RunMacro \"AutoExec_Restart\"\nElse\n  Call タイマーを開く\n  DoCmd.RunMacro \"AutoExec_A\"\nEnd If",
      "macros": [
        {
          "name": "AutoExec_A",
          "steps": [
            { "action": "RunMacro", "macro_name": "M300_Splash(M)を開く" },
            { "condition": "DCount(\"*\",\"T023_地区CD設定\")=0", "action": "OpenForm", "form_name": "F022_支店選択フォーム" },
            { "action": "OpenForm", "form_name": "C000_MAINⅡ" }
          ]
        },
        {
          "name": "AutoExec_Restart",
          "steps": [
            { "condition": "DCount(\"*\",\"T023_地区CD設定\")=0", "action": "OpenForm", "form_name": "F022_ベースオフィス" }
          ]
        }
      ],
      "references": {
        "forms": ["C000_MAINⅡ", "F022_支店選択フォーム", "F022_ベースオフィス"],
        "tables": ["T023_地区CD設定"]
      }
    },
    {
      "module_id": "F006",
      "event_trigger": "クリック時",
      "macro_call": "参照マクロ: A_メニューバーを表示",
      "detail": "マクロ『A_メニューバーを表示』を実行",
      "vba_code": "(参照マクロ — BD直接参照)",
      "macros": [
        {
          "name": "A_メニューバーを表示",
          "steps": [{ "action": "ShowToolbar", "toolbar_name": "Ribbon" }]
        }
      ]
    }
  ]
}
```

### → Output: `NavigationService.cs`

```csharp
namespace vba_brain.Application.Services;

public class NavigationService : INavigationService
{
    private readonly IWindowService _windowService;

    public NavigationService(IWindowService windowService) => _windowService = windowService;

    // F003 DD 2.5.5: AutoExec_A → OpenForm C000_MAINⅡ
    public void NavigateToMain() => _windowService.Show<MainWindow>();

    // F003 DD 2.5.4: AutoExec_Restart → OpenForm F022_ベースオフィス
    public void NavigateToSetup() => _windowService.Show<SetupWindow>();

    // F006: A_メニューバーを表示 → ShowToolbar
    public void ShowMenuBar() { /* WPF: Menu.Visibility = Visible */ }
}
```

---

## ③ Module Service (DD events + MongoDB modules → Utility)

> Dành cho events có gọi VBA module procedure (Call, Sub)  
> Input: DD events + MongoDB `modules` collection  
> Output: Utility Service.cs  
> **Note:** Module code có thể gọi OpenForm (→ navigation) + DLookup/OpenQuery (→ repo call)

### Input: `service_inputs/F_Login_module.json`

> Gom theo event — mỗi event = 1 chunk chứa đủ DD + VBA + module code

```json
{
  "form_name": "F_Login",
  "service_type": "module",

  "events": [
    {
      "module_id": "F003",
      "event_trigger": "更新後処理",
      "module_call": "Call タイマーを開く",
      "detail": "2.5.5. プロシージャ『タイマーを開く』を呼び出し",
      "vba_code": "Call タイマーを開く\nDoCmd.RunMacro \"AutoExec_A\"",
      "module": {
        "name": "Common",
        "handler": "タイマーを開く",
        "type": "Sub",
        "code": "Public Sub タイマーを開く()\n  DoCmd.OpenForm \"F300_Splash(M)\"\nEnd Sub"
      },
      "references": {
        "forms": ["F300_Splash(M)"]
      }
    },
    {
      "module_id": "F002",
      "event_trigger": "フォーム読み込み後",
      "module_call": "Call Judge_Inst",
      "detail": "バージョン確認を行い、最新版でなければインストール処理を実行する",
      "vba_code": "sCmnt = DLookup(\"コメント\", \"Access配信日\")\nIf sLvlCmnt <> sCmnt Then\n  MsgBox \"最新版ではありません！\"\n  Call Judge_Inst\nEnd If",
      "module": {
        "name": "Common",
        "handler": "Judge_Inst",
        "type": "Sub",
        "code": "Public Sub Judge_Inst()\n  If MsgBox(\"最新版ではありません！！インストールします。\", 4+48) = 7 Then Exit Sub\n  ' バージョンチェック → OpenCurrentDatabase\nEnd Sub"
      },
      "references": {
        "queries": ["Access配信日"]
      }
    }
  ]
}
```

### → Output: `CommonService.cs`

```csharp
namespace vba_brain.Application.Services;

public class CommonService : ICommonService
{
    private readonly IWindowService _windowService;

    public CommonService(IWindowService windowService) => _windowService = windowService;

    // Module Common.タイマーを開く → OpenForm F300_Splash
    // F003 DD 2.5.5: プロシージャ呼び出し
    public void StartSplash() => _windowService.Show<SplashWindow>();

    // Module Common.Judge_Inst → バージョンチェック
    // F002: フォーム読み込み後
    public async Task<bool> CheckVersionAsync()
    {
        // TODO: ネットワークパス → API endpoint に変換
        return true;
    }
}
```

---

## Pipeline Dependencies (DTO Flow)

> Đảm bảo DTOs chạy xuyên suốt: Repo → Service → Logic → UI

### Agent Repo → Agent Service (upstream)

```
Agent Repo Output              Agent Service sử dụng
─────────────────               ──────────────────────
LoginRequest.cs                 → AuthService nhận LoginRequest param
LoginResponse.cs                → AuthService trả LoginResponse
UserEntity.cs                   → AuthService dùng để map fields
IUserRepository.cs              → AuthService inject _userRepo (DI)
UserRepository.cs               → Infrastructure (runtime)
```

| Repo Output | Service Input | Ràng buộc |
|---|---|---|
| `LoginRequest { LoginId, Password }` | `AuthenticateAsync(LoginRequest request)` | **Field names phải khớp** |
| `LoginResponse { Success, ErrorMessage, HasBranch, UserName }` | `return new LoginResponse { ... }` | **Field names phải khớp** |
| `IUserRepository.GetByIdAsync(string id)` | `_userRepo.GetByIdAsync(request.LoginId)` | **Method name + param type phải khớp** |
| `IUserRepository.GetBranchCountAsync()` | `_userRepo.GetBranchCountAsync()` | **Return type phải khớp (int)** |

### Agent Service → Agent Logic (downstream)

```
Agent Service Output            Agent Logic sử dụng
────────────────────            ──────────────────────
IAuthService.cs                 → ViewModel inject _authService (DI)
LoginRequest.cs                 → ViewModel tạo new LoginRequest { }
LoginResponse.cs                → ViewModel đọc result.Success, result.ErrorMessage
INavigationService.cs           → ViewModel inject _navService (DI)
ICommonService.cs               → ViewModel inject _commonService (DI)
```

| Service Output | Logic Input | Ràng buộc |
|---|---|---|
| `IAuthService.AuthenticateAsync(LoginRequest)` | `await _authService.AuthenticateAsync(new LoginRequest { LoginId, Password })` | **Method signature khớp** |
| `LoginResponse.Success` | `if (!result.Success)` | **Property name khớp** |
| `LoginResponse.ErrorMessage` | `ErrorMessage = result.ErrorMessage` | **Property name khớp** |
| `LoginResponse.HasBranch` | `if (result.HasBranch)` → navigate | **Property name khớp** |
| `INavigationService.NavigateToMain()` | `_navService.NavigateToMain()` | **Method name khớp** |
| `ICommonService.StartSplash()` | `_commonService.StartSplash()` | **Method name khớp** |

### Full Pipeline (F_Login)

```
Agent Repo                  Agent Service               Agent Logic                Agent UI
──────────                  ─────────────               ───────────                ────────
UserEntity.cs          →    AuthService.cs          →    LoginViewModel.cs     →    LoginWindow.xaml
LoginRequest.cs        →    IAuthService.cs         →    (inject DI)          →    (bind properties)
LoginResponse.cs       →    (return type)           →    (check result)       →    ErrorMessage display
IUserRepository.cs     →    (inject _userRepo)
UserRepository.cs      →    (runtime Dapper)
                            NavigationService.cs    →    (inject _navService)
                            CommonService.cs        →    (inject _commonService)
```

---

## VBA → Service Mapping

| VBA Construct | Service Type | C# Output |
|---|:---:|---|
| `DLookup(...)` / `DCount(...)` | ① Form | `_repo.GetByIdAsync()` |
| `DoCmd.RunMacro "AutoExec_A"` | ② Macro | `_navService.NavigateToMain()` |
| `DoCmd.OpenForm "F_Main"` | ② Macro | `_windowService.Show<MainWindow>()` |
| `参照マクロ: A_メニューバーを表示` | ② Macro | `_navService.ShowMenuBar()` |
| `Call タイマーを開く` | ③ Module | `_commonService.StartSplash()` |
| `Call Judge_Inst` | ③ Module | `_commonService.CheckVersionAsync()` |
| `DoCmd.RunSQL "UPDATE..."` | ① Form | `_repo.ExecuteAsync(sql)` |
| `MsgBox "エラー!!"` | ① Form | `return Response { ErrorMessage }` |

---

## Verification

### Code Contract
- [ ] Tất cả DD steps (query/DLookup/DCount) → Form Service method
- [ ] Tất cả RunMacro references → Macro Service (NavigationService)
- [ ] Tất cả Module calls → Module Service (TimerService, CommonService)
- [ ] Error messages khớp VBA gốc (exact match)
- [ ] Interface khớp implementation (method signatures)

### DTO Cross-Check (Pipeline Integrity)
- [ ] `LoginRequest` fields khớp giữa Repo output vs Service param vs Logic `new LoginRequest{}`
- [ ] `LoginResponse` fields khớp giữa Service return vs Logic `result.Success`, `result.ErrorMessage`
- [ ] `IAuthService` method signatures khớp giữa Service output vs Logic DI inject
- [ ] `IUserRepository` method signatures khớp giữa Repo output vs Service `_userRepo.xxx()`
- [ ] `INavigationService` methods khớp giữa Service output vs Logic `_navService.xxx()`
- [ ] `ICommonService` methods khớp giữa Service output vs Logic `_commonService.xxx()`
- [ ] DI registration: tất cả interfaces → implementations đăng ký trong `Program.cs`
