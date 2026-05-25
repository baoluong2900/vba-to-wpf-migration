import sys
import json
from pathlib import Path

# Add layer5 to sys.path
layer5_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(layer5_path))

from agents.ui.tool_skeleton import SkeletonTool
from agents.ui.control_mapper import sanitize_class_name

def main():
    form_name = "AM報告書(施工)_印刷_PDF"
    print(f"Regenerating C# skeletons for: {form_name}")
    
    # Paths
    input_path = layer5_path / "agents" / "ui" / "inputs" / f"{form_name}_input.json"
    if not input_path.exists():
        print(f"Error: Input snapshot not found at {input_path}")
        return
        
    with open(input_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)
        
    vm_bindings = input_data.get("viewmodel_bindings", {})
    
    # 1. Instantiate SkeletonTool
    tool = SkeletonTool()
    
    # 2. Generate stubs
    cs_code = tool.gen_codebehind(form_name, vm_bindings)
    vm_code = tool.gen_viewmodel(form_name, vm_bindings)
    
    # 3. Target WPF Source Paths
    wpf_root = Path(__file__).resolve().parent.parent.parent.parent / "source" / "vba_brain.UI.WPF"
    views_dir = wpf_root / "Views"
    viewmodels_dir = wpf_root / "ViewModels"
    
    xaml_file = views_dir / f"{form_name}.xaml"
    cs_file = views_dir / f"{form_name}.xaml.cs"
    vm_file = viewmodels_dir / f"{form_name}.cs"
    
    # 4. Save code-behind & viewmodel
    views_dir.mkdir(parents=True, exist_ok=True)
    viewmodels_dir.mkdir(parents=True, exist_ok=True)
    
    cs_file.write_text(cs_code, encoding="utf-8")
    print(f"Saved Code-behind to {cs_file}")
    
    vm_file.write_text(vm_code, encoding="utf-8")
    print(f"Saved ViewModel to {vm_file}")
    
    # 5. Fix XAML x:Class attribute if needed
    if xaml_file.exists():
        xaml_content = xaml_file.read_text(encoding="utf-8")
        sanitized_class = sanitize_class_name(form_name)
        
        # Replace the class name inside x:Class
        import re
        fixed_xaml = re.sub(
            rf'x:Class="vba_brain\.UI\.WPF\.Views\.{re.escape(form_name)}"',
            f'x:Class="vba_brain.UI.WPF.Views.{sanitized_class}"',
            xaml_content
        )
        if fixed_xaml != xaml_content:
            xaml_file.write_text(fixed_xaml, encoding="utf-8")
            print(f"Updated XAML x:Class to: vba_brain.UI.WPF.Views.{sanitized_class}")
        else:
            print("XAML x:Class was already sanitized or did not match.")
    # 6. Synchronize back to the outputs folder to avoid stale references
    out_dir = layer5_path / "agents" / "ui" / "outputs" / form_name
    out_views = out_dir / "Views"
    out_vms = out_dir / "ViewModels"
    out_views.mkdir(parents=True, exist_ok=True)
    out_vms.mkdir(parents=True, exist_ok=True)
    
    if xaml_file.exists():
        (out_views / xaml_file.name).write_text(xaml_file.read_text(encoding="utf-8"), encoding="utf-8")
    (out_views / cs_file.name).write_text(cs_code, encoding="utf-8")
    (out_vms / vm_file.name).write_text(vm_code, encoding="utf-8")
    print(f"Synchronized updated files to {out_dir}")
    
    print("Done!")

if __name__ == "__main__":
    main()
