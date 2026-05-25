# 🎨 Agent UI — Gen XAML View

> **Mục đích:** Đọc BD layout + form image → sinh WPF XAML view hoàn chỉnh  
> **Model:** `qwen3-coder-plus` (~4K tokens/form)  
> **Ref:** [AI_Agent_Workflow.md](./AI_Agent_Workflow.md) — Slide 3

---

## Input / Output

| | Nguồn | Chi tiết |
|---|---|---|
| **Input 1** | BD JSON `sheet_3_screen_edit` | Control list, positions, sizes |
| **Input 2** | MongoDB `forms.items[]` | Control types, properties, labels |
| **Input 3** | Form Image (screenshot) | Visual reference cho layout |
| **Input 4** | ViewModel interface (step trước) | Property names + Command names để bind |
| **Output** | `Views/{Form}Window.xaml` | WPF XAML with Grid layout + bindings |

---

## Layer5 Folder / Files

```
backend/layer5/
├── agents/
│   └── agent_ui.py                   ← Main agent logic
├── core/
│   └── prompts/
│       └── agent_ui.md               ← System prompt (XAML rules)
├── ast/
│   ├── control_mapper.py             ← Access TextBox → WPF TextBox
│   └── ui_ast_builder.py             ← JSON → XAML layout tree
└── codegen/
    └── templates/
        └── Window.xaml.j2            ← Base window template
```

---

## Logic Flow

```
BD layout + MongoDB items
    ↓
control_mapper.py: Access controls → WPF controls
    ↓
ui_ast_builder.py: left/top/width/height → Canvas positions
    ↓
agent_ui.py: build prompt
    ├── UI AST tree (controls + Canvas positions)
    ├── ViewModel bindings (Property names, Command names)
    ├── Form image (visual reference)
    └── Access → WPF mapping rules
    ↓
LLM (qwen3-coder-plus) → XAML code
    ↓
Output: Views/LoginWindow.xaml
```

---

## Control Mapping (Access → WPF)

| Access Control | WPF Control | Binding Pattern |
|:---:|:---:|---|
| TextBox | `TextBox` | `Text="{Binding Prop}"` |
| Label | `Label` | `Content="{Binding Prop}"` |
| ComboBox | `ComboBox` | `ItemsSource + SelectedItem` |
| CommandButton | `Button` | `Command="{Binding Cmd}"` |
| CheckBox | `CheckBox` | `IsChecked="{Binding Prop}"` |
| SubForm | `DataGrid` / `UserControl` | Sub-ViewModel |
| TabControl | `TabControl` | `TabItem` per page |

---

## Prompt Template (概要)

```
## Task: Generate WPF XAML for {form_name}

## UI AST (controls + layout):
{ui_ast_json}

## ViewModel Bindings (must match exactly):
Properties: {property_list}
Commands: {command_list}

## Rules:
- Use Canvas layout with Canvas.Left/Canvas.Top (maps directly from Access positions)
- Bind ALL controls to ViewModel properties
- Use MaterialDesign or modern styling
- PasswordBox for password fields (no direct binding — use attached behavior)
- Output ONLY XAML, no code-behind
- Namespace: vba_brain.Views
```

---

## Ví dụ Input JSON (F_Login)

```json
{
  "form_name": "F_Login",
  "form_properties": {
    "caption": "ログイン",
    "width": 4988,
    "popup": true,
    "modal": true,
    "autocenter": true,
    "maxbutton": false,
    "minbutton": false,
    "closebutton": false,
    "controlbox": false,
    "scrollbars": 0,
    "borderstyle": 3,
    "moveable": 0,
    "fittoscreen": 1,
    "events": { "onopen": "Form_Open", "onload": "Form_Load", "onkeydown": "Form_KeyDown" }
  },

  "bd_layout": {
    "items": [
      { "logical_name": "ログインID", "physical_name": "txtID", "item_attribute": "テキストボックス", "io_type": "出力", "note": "PCから自動取得、編集不可" },
      { "logical_name": "パスワード", "physical_name": "txtPass", "item_attribute": "パスワードボックス", "io_type": "入力" }
    ]
  },

  "mongodb_controls": [
    { "name": "txtID",     "type": "TextBox",       "format": { "left": 2191, "top": 930,  "width": 1701, "height": 270 }, "data": { "locked": true },  "labelname": "ログインID" },
    { "name": "txtPass",   "type": "TextBox",       "format": { "left": 2191, "top": 1530, "width": 1701, "height": 270 }, "data": { "inputmask": "Password" }, "labelname": "パスワード" },
    { "name": "cmdLogin",  "type": "CommandButton", "format": { "left": 2211, "top": 1814, "width": 1701, "height": 435 }, "caption": "ログイン" },
    { "name": "閉じる",    "type": "CommandButton",  "format": { "left": 4480, "top": 60,   "width": 454,  "height": 454 }, "caption": "閉じる", "event": "閉じる_Click" },
    { "name": "施工店情報", "type": "Label",          "format": { "left": 1080, "top": 150,  "width": 2830, "height": 340 }, "caption": "新アフター管理DB" }
  ],

  "viewmodel_bindings": {
    "properties": ["LoginId", "ErrorMessage", "HasError"],
    "commands": ["LoginCommand", "CloseCommand"]
  }
}
```

---

## Ví dụ Output: LoginWindow.xaml

```xml
<Window x:Class="vba_brain.Views.LoginWindow"
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="ログイン" Width="499" Height="300"
        WindowStartupLocation="CenterScreen"
        WindowStyle="None"
        ResizeMode="NoResize"
        ShowInTaskbar="False"
        Topmost="True">
    <Canvas>
        <!-- Title label -->
        <Label   Canvas.Left="108" Canvas.Top="15"  Width="283" Height="34"
                 Content="新アフター管理DB" FontSize="12" FontWeight="Bold"/>
        <!-- Close button (閉じる) -->
        <Button  Canvas.Left="448" Canvas.Top="6"   Width="45"  Height="45"
                 Content="✕" Command="{Binding CloseCommand}"/>
        <!-- ログインID label -->
        <Label   Canvas.Left="81"  Canvas.Top="93"  Width="129" Height="27"
                 Content="ログインID：" FontWeight="Bold"/>
        <!-- ログインID textbox (ReadOnly — auto-fill from Windows) -->
        <TextBox Canvas.Left="219" Canvas.Top="93"  Width="170" Height="27"
                 Text="{Binding LoginId}" IsReadOnly="True"/>
        <!-- パスワード label -->
        <Label       Canvas.Left="85"  Canvas.Top="153" Width="122" Height="27"
                     Content="パスワード：" FontWeight="Bold"/>
        <!-- パスワード input -->
        <PasswordBox Canvas.Left="219" Canvas.Top="153" Width="170" Height="27"
                     x:Name="pbPass"/>
        <!-- ログイン button -->
        <Button  Canvas.Left="221" Canvas.Top="181" Width="170" Height="44"
                 Content="ログイン" FontWeight="Bold"
                 Command="{Binding LoginCommand}"
                 CommandParameter="{Binding ElementName=pbPass}"/>
        <!-- Version label -->
        <Label   Canvas.Left="8"   Canvas.Top="227" Width="162" Height="35"
                 Content="2025/06/30公開Ver" FontSize="8"/>
    </Canvas>
</Window>
```

---

## Verification

- [ ] Tất cả controls từ BD đều có trong XAML
- [ ] Bindings match ViewModel properties/commands
- [ ] Layout positions tương đối khớp Access form
- [ ] XAML parse thành công (no syntax errors)
