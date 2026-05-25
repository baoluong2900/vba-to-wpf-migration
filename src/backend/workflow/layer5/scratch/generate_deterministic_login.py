# Resolve paths dynamically
_LAYER5_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_LAYER5_DIR))

from agents.ui.tool_skeleton import SkeletonTool

def main():
    input_file = _LAYER5_DIR / "agents" / "ui" / "inputs" / "F_Login_input.json"
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    vm_bindings = data["viewmodel_bindings"]
    form_name = "F_Login"

    # Define strict sequential mapping for sorting
    method_to_id = {
        "Form_Open": "F000",
        "Form_KeyDown": "F001",
        "Form_Load": "F002",
        "txtPass_AfterUpdate": "F003",
        "閉じる_Click": "F004",
        "施工店情報_DblClick": "F005",
        "パスワードテーブルを開く_DblClick": "F008",
        "プロセス終了_DblClick": "F009"
    }

    # Sort event handlers sequentially
    event_handlers = vm_bindings.get("event_handlers", [])
    event_handlers.sort(key=lambda h: method_to_id.get(h["method"], "9999"))
    vm_bindings["event_handlers"] = event_handlers

    skeleton = SkeletonTool()
    
    # 1. Generate C# code-behind and ViewModel code
    cs_code = skeleton.gen_codebehind(form_name, vm_bindings)
    vm_code = skeleton.gen_viewmodel(form_name, vm_bindings)

    # Inject Password property in ViewModel to support PasswordBox sync
    password_property = """public class F_Login : ViewModelBase
{
    private string _password = string.Empty;
    public string Password
    {
        get => _password;
        set { _password = value; OnPropertyChanged(); }
    }"""
    vm_code = vm_code.replace("public class F_Login : ViewModelBase\n{", password_property)

    # 2. Paths for outputs and source projects dynamically resolved
    _WORKFLOW_DIR = _LAYER5_DIR.parent.parent
    _UI_AVALONIA_DIR = _WORKFLOW_DIR / "src" / "wpf" / "vba_brain.UI.Avalonia"
    
    output_cs_path = _LAYER5_DIR / "agents" / "ui" / "outputs" / "F_Login" / "Views" / "F_Login.xaml.cs"
    output_vm_path = _LAYER5_DIR / "agents" / "ui" / "outputs" / "F_Login" / "ViewModels" / "F_Login.cs"
    output_xaml_path = _LAYER5_DIR / "agents" / "ui" / "outputs" / "F_Login" / "Views" / "F_Login.xaml"

    src_cs_path = _UI_AVALONIA_DIR / "Views" / "F_Login.xaml.cs"
    src_vm_path = _UI_AVALONIA_DIR / "ViewModels" / "F_Login.cs"
    src_xaml_path = _UI_AVALONIA_DIR / "Views" / "F_Login.xaml"

    # Make sure parent directories exist
    output_cs_path.parent.mkdir(parents=True, exist_ok=True)
    output_vm_path.parent.mkdir(parents=True, exist_ok=True)
    src_cs_path.parent.mkdir(parents=True, exist_ok=True)
    src_vm_path.parent.mkdir(parents=True, exist_ok=True)

    # 3. Write ViewModel code
    with open(output_vm_path, "w", encoding="utf-8") as f:
        f.write(vm_code)
    with open(src_vm_path, "w", encoding="utf-8") as f:
        f.write(vm_code)
    print(f"ViewModel successfully generated and saved to:")
    print(f"  - {output_vm_path}")
    print(f"  - {src_vm_path}")

    # 4. Write C# code-behind code
    lines = cs_code.splitlines()
    new_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        if "private void F" in line and "(object sender, " in line:
            # Change "private void" to "private async void"
            line = line.replace("private void", "private async void")
            new_lines.append(line)
            # Find the opening brace {
            i += 1
            while i < len(lines) and "{" not in lines[i]:
                new_lines.append(lines[i])
                i += 1
            new_lines.append(lines[i]) # {
            # Inject: if (DataContext is ViewModels.F_Login vm) await vm.FXXXAsync();
            method_name = line.split("private async void ")[1].split("(")[0] # e.g. F005_DblClick
            module_id = method_name.split("_")[0] # e.g. F005
            indent = "        "
            new_lines.append(f"{indent}if (DataContext is ViewModels.F_Login vm)")
            new_lines.append(f"{indent}    await vm.{module_id}Async();")
            i += 1
            # Skip empty lines until the closing brace }
            while i < len(lines) and "}" not in lines[i]:
                i += 1
            new_lines.append(lines[i]) # }
        else:
            new_lines.append(line)
        i += 1
        
    # Append the PasswordBox_PasswordChanged handler before the final class closing brace
    password_changed_handler = """
    // ── Standard PasswordBox Sync (MVVM boilerplate) ──
    private void PasswordBox_PasswordChanged(object sender, RoutedEventArgs e)
    {
        if (this.DataContext is ViewModels.F_Login vm && sender is PasswordBox pb)
        {
            vm.Password = pb.Password;
        }
    }
"""
    
    # We find the last closing brace of the class
    class_closing_index = -1
    for index in range(len(new_lines) - 1, -1, -1):
        if new_lines[index].strip() == "}":
            class_closing_index = index
            break
            
    if class_closing_index != -1:
        new_lines.insert(class_closing_index, password_changed_handler)
        
    cs_code_wired = "\n".join(new_lines)
    
    with open(output_cs_path, "w", encoding="utf-8") as f:
        f.write(cs_code_wired)
    with open(src_cs_path, "w", encoding="utf-8") as f:
        f.write(cs_code_wired)
    print(f"Code-behind successfully generated, wired, and saved to:")
    print(f"  - {output_cs_path}")
    print(f"  - {src_cs_path}")

    # 5. Read, update and write XAML
    if output_xaml_path.exists():
        with open(output_xaml_path, "r", encoding="utf-8") as f:
            xaml_content = f.read()
    elif src_xaml_path.exists():
        with open(src_xaml_path, "r", encoding="utf-8") as f:
            xaml_content = f.read()
    else:
        print("XAML file not found anywhere!")
        return

    # Update event names in XAML
    xaml_content = xaml_content.replace('MouseDoubleClick="施工店情報_DblClick"', 'MouseDoubleClick="F005_DblClick"')
    xaml_content = xaml_content.replace('MouseDoubleClick="パスワードテーブルを開く_DblClick"', 'MouseDoubleClick="F008_DblClick"')
    xaml_content = xaml_content.replace('MouseDoubleClick="プロセス終了_DblClick"', 'MouseDoubleClick="F009_DblClick"')
    
    # Wire window lifecycle events
    window_tag_start = '<Window x:Class="vba_brain.UI.WPF.Views.F_Login"'
    if window_tag_start in xaml_content and 'Loaded=' not in xaml_content:
        # Replace the Window tag end
        xaml_content = xaml_content.replace('SizeToContent="WidthAndHeight">', 'SizeToContent="WidthAndHeight"\n        Loaded="F002_Load"\n        KeyDown="F001_KeyDown"\n        SourceInitialized="F000_Open">')

    with open(output_xaml_path, "w", encoding="utf-8") as f:
        f.write(xaml_content)
    with open(src_xaml_path, "w", encoding="utf-8") as f:
        f.write(xaml_content)
    print(f"XAML successfully updated and saved to:")
    print(f"  - {output_xaml_path}")
    print(f"  - {src_xaml_path}")

if __name__ == "__main__":
    main()
