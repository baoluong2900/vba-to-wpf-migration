# 🧠 Agent Logic — Gen ViewModel

> **Mục đích:** Đọc BD events + DD steps → sinh ViewModel C# với Commands + Properties  
> **Model:** `qwen3-235b-a22b-instruct-2507` (~6K tokens/form, think mode)  
> **Ref:** [AI_Agent_Workflow.md](./AI_Agent_Workflow.md) — Slide 3

---

## Input / Output

| | Nguồn | Chi tiết |
|---|---|---|
| **Input 1** | BD JSON `sheet_2_layout.events[]` | Event names, triggers, descriptions |
| **Input 2** | DD JSON `sheet_3_detail_specs[]` | Step-by-step logic per event |
| **Input 3** | `IAuthService` interface (Agent Service output) | Service method signatures để gọi |
| **Input 4** | XAML bindings (Agent UI output) | Property/Command names cần implement |
| **Output** | `ViewModels/{Form}ViewModel.cs` | MVVM ViewModel with RelayCommand |

---

## Layer5 Folder / Files

```
backend/layer5/
├── agents/
│   └── agent_logic.py                ← Main agent logic
├── core/
│   └── prompts/
│       └── agent_logic.md            ← System prompt (MVVM + DI rules)
└── ast/
    └── event_mapper.py               ← VBA event → C# command mapping
```

---

## Logic Flow

```
BD events + DD steps
    ↓
event_mapper.py: VBA events → C# RelayCommand names
    Form_Open      → constructor / Window_Loaded
    Form_Load      → Window_Loaded
    btnSave_Click  → SaveCommand
    txtPass_After  → LoginCommand
    閉じる_Click    → CloseCommand
    ↓
agent_logic.py: build prompt
    ├── Events + mapped command names
    ├── DD steps (step-by-step logic cho mỗi event)
    ├── IService interface (method signatures)
    └── Property list (từ XAML bindings)
    ↓
LLM (qwen3-235b, think mode) → C# ViewModel code
    ↓
Output: ViewModels/LoginViewModel.cs
```

---

## VBA Event → C# Command Mapping

| VBA Event | C# Command/Method | Trigger |
|---|---|---|
| `Form_Open` | Constructor or `OnNavigatedTo()` | Window loaded |
| `Form_Load` | `Window_Loaded` event | After controls ready |
| `btnSave_Click` | `SaveCommand` (RelayCommand) | Button click |
| `txtPass_AfterUpdate` | `LoginCommand` (RelayCommand) | Enter key / button |
| `閉じる_Click` | `CloseCommand` (RelayCommand) | Close button |
| `Form_Close` | `OnNavigatedFrom()` / Dispose | Window closing |
| `Timer` | `DispatcherTimer` | Timer tick |

---

## Prompt Template (概要)

```
## Task: Generate WPF ViewModel for {form_name}

## Events to implement:
{events_with_dd_steps}

## Service interface available:
{iservice_code}

## Properties needed (from XAML bindings):
{property_list}

## Rules:
- Inherit ViewModelBase (INotifyPropertyChanged)
- Use RelayCommand for ICommand
- Constructor inject IAuthService via DI
- Think mode: reason through DD steps before coding
- Namespace: vba_brain.ViewModels
```

---

## Strategy: Chunk per Event

> **Vấn đề:** Form phức tạp có 10+ events → JSON quá lớn → LLM mất focus  
> **Giải pháp:** Chunk theo từng event → mỗi LLM call = 1 BD event + DD steps tương ứng  
> **Merge:** Roslyn AST merge các method output → 1 ViewModel file

```
F_Login có 5 events → 5 chunks → 5 LLM calls → merge → LoginViewModel.cs

Chunk 0: E000 Form_Open       → constructor logic          (SYS - skip/minimal)
Chunk 1: E001 Form_KeyDown    → OnKeyDown handler          (UI  - skip/minimal)
Chunk 2: E002 Form_Load       → Window_Loaded method       (SYS - version check)
Chunk 3: E003 txtPass_After   → LoginCommand + LoginAsync  (VALID - main logic ⭐)
Chunk 4: E004 閉じる_Click     → CloseCommand              (SYS - simple)
```


---

## Ví dụ Input Files (F_Login → 5 events = 5 JSON files)

> Source: `BD_json/F_Login.json` → `sheet_2_layout.events[]`  
> Source: `DD_json/F_Login.json` → `sheet_3_detail_specs[]`

### `chunks/F_Login_E000.json` — Form_Open (SYS)

```json
{
  "form_name": "F_Login", "chunk": "0/4",
  "bd_event": {
    "event_id": "E000", "module_id": "F000",
    "type": "フォーム", "event_trigger": "画面を開く時",
    "event_content": "アプリケーション起動時にShiftキーを無効化し、UI要素を非表示にしてシステムを初期化する",
    "notes": "Form_Open", "action_type": "SYS"
  },
  "dd_steps": { "step_1_init": "", "step_2_main": "", "step_3_error": "" }
}
```

### `chunks/F_Login_E001.json` — Form_KeyDown (UI)

```json
{
  "form_name": "F_Login", "chunk": "1/4",
  "bd_event": {
    "event_id": "E001", "module_id": "F001",
    "type": "フォーム", "event_trigger": "キー押下時",
    "event_content": "F11とF12キーの押下をブロックして無効化メッセージを表示する",
    "notes": "Form_KeyDown", "action_type": "UI"
  },
  "dd_steps": { "step_2_main": "" }
}
```

### `chunks/F_Login_E002.json` — Form_Load (SYS)

```json
{
  "form_name": "F_Login", "chunk": "2/4",
  "bd_event": {
    "event_id": "E002", "module_id": "F002",
    "type": "フォーム", "event_trigger": "フォーム読み込み後",
    "event_content": "バージョン確認を行い、最新版でなければインストール処理を実行する",
    "notes": "Form_Load", "action_type": "SYS"
  },
  "dd_steps": { "step_2_main": "" }
}
```

### `chunks/F_Login_E003.json` — txtPass_AfterUpdate (VALID ⭐)

```json
{
  "form_name": "F_Login", "chunk": "3/4",
  "bd_event": {
    "event_id": "E003", "module_id": "F003",
    "type": "テキストボックス", "physical_name": "txtPass",
    "event_trigger": "更新後処理",
    "event_content": "IDとパスワードで認証し、管理者フラグ確認後にログイン処理を実行する",
    "notes": "txtPass_AfterUpdate", "action_type": "VALID"
  },
  "dd_steps": {
    "step_1_init": "エラーハンドリングを設定する\n1.1. エラー発生時のジャンプ先を『Err_Shori』に指定する",
    "step_2_main": "2.1. IDフィールドが空の場合のチェック\n2.2. パスワードフィールドが空の場合のチェック\n2.3. T_ID_Passから管理者フラグ取得 → 0の場合エラー\n2.4. T_ID_passからパスワード取得 → 存在しない場合エラー\n2.5. パスワード一致 → F_Login閉じる → T023_地区CD設定カウント → 0: AutoExec_Restart, >0: タイマーを開く+AutoExec_A\n2.6. パスワード不一致 → エラーメッセージ表示",
    "step_3_error": "Err_Shoriで通信接続エラーメッセージ表示"
  }
}
```

### `chunks/F_Login_E004.json` — 閉じる_Click (SYS)

```json
{
  "form_name": "F_Login", "chunk": "4/4",
  "bd_event": {
    "event_id": "E004", "module_id": "F004",
    "type": "コマンドボタン", "physical_name": "cmdClose",
    "event_trigger": "クリック時",
    "event_content": "アプリケーションを終了する",
    "notes": "閉じる_Click", "action_type": "SYS"
  },
  "dd_steps": { "step_2_main": "Application.Quit" }
}
```

---

## Output per Chunk → Merge

### E003 → `LoginAsync()`
```csharp
private async Task LoginAsync(object? passwordBox)
{
    if (string.IsNullOrEmpty(LoginId)) { ErrorMessage = "IDを入力してください"; HasError = true; return; }
    var pass = (passwordBox as PasswordBox)?.Password;
    if (string.IsNullOrEmpty(pass)) { ErrorMessage = "パスワードを入力してください"; HasError = true; return; }
    try {
        var result = await _authService.AuthenticateAsync(new LoginRequest { LoginId = LoginId, Password = pass });
        if (!result.Success) { ErrorMessage = result.ErrorMessage; HasError = true; return; }
        CloseApp();
    }
    catch (Exception) { ErrorMessage = "通信接続エラー"; HasError = true; }
}
```

### E004 → `CloseApp()`
```csharp
private void CloseApp() => Application.Current.Shutdown();
```

### Merge (Roslyn AST)
```
5 JSON files → 5 LLM calls → 5 method outputs
    ↓
ast/method_merger.py: merge → LoginViewModel.cs
    ├── Auto-generate: class, constructor, DI, properties
    ├── Insert: each method body
    └── Build check → compile OK → done
```

---

## Ví dụ Output (Merged): LoginViewModel.cs

```csharp
namespace vba_brain.ViewModels;

public class LoginViewModel : ViewModelBase
{
    private readonly IAuthService _authService;

    // Properties (auto-generated from XAML bindings)
    private string _loginId = string.Empty;
    public string LoginId { get => _loginId; set => SetProperty(ref _loginId, value); }

    private string _errorMessage = string.Empty;
    public string ErrorMessage { get => _errorMessage; set => SetProperty(ref _errorMessage, value); }

    private bool _hasError;
    public bool HasError { get => _hasError; set => SetProperty(ref _hasError, value); }

    // Commands (auto-generated from event_mapper)
    public RelayCommand LoginCommand { get; }
    public RelayCommand CloseCommand { get; }

    // E000: Form_Open → constructor
    public LoginViewModel(IAuthService authService)
    {
        _authService = authService;
        LoginId = Environment.UserName;

        LoginCommand = new RelayCommand(async o => await LoginAsync(o));
        CloseCommand = new RelayCommand(_ => CloseApp());
    }

    // E003: txtPass_AfterUpdate → LoginCommand
    private async Task LoginAsync(object? passwordBox)
    {
        HasError = false;
        if (string.IsNullOrEmpty(LoginId))
        { ErrorMessage = "IDを入力してください"; HasError = true; return; }

        var pass = (passwordBox as PasswordBox)?.Password;
        if (string.IsNullOrEmpty(pass))
        { ErrorMessage = "パスワードを入力してください"; HasError = true; return; }

        try
        {
            var result = await _authService.AuthenticateAsync(
                new LoginRequest { LoginId = LoginId, Password = pass });
            if (!result.Success)
            { ErrorMessage = result.ErrorMessage; HasError = true; return; }

            CloseApp();
        }
        catch (Exception)
        { ErrorMessage = "通信接続エラー"; HasError = true; }
    }

    // E004: 閉じる_Click → CloseCommand
    private void CloseApp() => Application.Current.Shutdown();
}
```

---

## Verification

- [ ] Tất cả events từ BD đều có Command/Method tương ứng
- [ ] DD steps đều được implement trong method body
- [ ] Properties match XAML bindings
- [ ] DI injection đúng (IAuthService)
- [ ] Compile thành công
