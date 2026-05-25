import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class VMSyncTool:
    """
    Tool để đồng bộ hóa các Method Stubs từ Code-behind sang ViewModel.
    Giúp Logic Agent có target chính xác để inject code.
    """
    
    def __init__(self, wpf_root: str):
        self.wpf_root = Path(wpf_root)
        self.views_dir = self.wpf_root / "Views"
        self.vms_dir = self.wpf_root / "ViewModels"

    def sync_form(self, form_name: str):
        try:
            import sys
            layer5_dir = Path(__file__).parent.parent
            if str(layer5_dir) not in sys.path:
                sys.path.insert(0, str(layer5_dir))
            from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
            _name_map = _load_form_name_map()
            view_file_stem, vm_file_stem = _resolve_wpf_names(form_name, _name_map)
        except ImportError:
            view_file_stem = form_name
            vm_file_stem = form_name

        view_file = self.views_dir / f"{view_file_stem}.xaml.cs"
        vm_file = self.vms_dir / f"{vm_file_stem}.cs"
        
        if not view_file.exists():
            print(f"[Error] View file not found: {view_file}")
            return
            
        if not vm_file.exists():
            print(f"[Error] ViewModel file not found: {vm_file}")
            return

        view_content = view_file.read_text(encoding="utf-8")
        vm_content = vm_file.read_text(encoding="utf-8")
        
        # 1. Tìm tất cả các event handler trong Code-behind
        # Pattern: private [async] void MethodName(object sender, ...)
        handlers = re.findall(r"private\s+(?:async\s+)?void\s+([a-zA-Z0-9_]+)\s*\(object sender", view_content)
        
        # 2. Đọc file phân loại SERVICE để lọc ra các event thực sự cần ViewModel stub
        service_json = Path(__file__).parent / "inputs" / f"{form_name}_service.json"
        service_handlers = set()
        if service_json.exists():
            import json
            try:
                data = json.loads(service_json.read_text(encoding="utf-8"))
                for event in data.get("events", []):
                    stub = event.get("cs_stub")
                    if stub and stub.get("cs_name"):
                        service_handlers.add(stub["cs_name"])
                print(f"[Info] Found {len(service_handlers)} SERVICE events in JSON classification.")
            except Exception as e:
                print(f"[Warn] Could not read {service_json.name}: {e}")
        else:
            print(f"[Warn] {service_json.name} not found. Will sync ALL handlers blindly.")

        updated_vm = vm_content
        changes_made = False
        
        for method in handlers:
            # Nếu có danh sách service events mà method không nằm trong đó (tức là UI event) -> Bỏ qua
            if service_handlers and method not in service_handlers:
                print(f"[Sync] Skipping UI event: {method}")
                continue

            vm_method = f"{method}Async"
            
            # Nếu method này chưa có trong ViewModel, hãy thêm stub vào
            if vm_method not in updated_vm:
                print(f"[Sync] Adding stub for {vm_method} to {vm_file.name}")
                
                stub = f"""
    /// <summary>
    /// Logic Agent implements the business logic for {method} here.
    /// </summary>
    public virtual async System.Threading.Tasks.Task {vm_method}()
    {{
        await System.Threading.Tasks.Task.CompletedTask;
        throw new System.NotImplementedException();
    }}
"""
                # Chèn vào trước dấu đóng ngoặc cuối cùng của class
                last_brace = updated_vm.rfind("}")
                if last_brace != -1:
                    updated_vm = updated_vm[:last_brace] + stub + updated_vm[last_brace:]
                    changes_made = True
                
        if changes_made:
            vm_file.write_text(updated_vm, encoding="utf-8")
            print(f"[Success] Updated {vm_file.name} with new stubs.")
        else:
            print(f"[Info] {vm_file.name} is already in sync.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python sync_vm_stubs.py FormName")
    else:
        # Resolve path dynamically based on project layout
        _LAYER5_DIR = Path(__file__).resolve().parent.parent.parent
        _WORKFLOW_DIR = _LAYER5_DIR.parent.parent
        
        # Check Avalonia project first, fall back to WPF if not found
        wpf_path = _WORKFLOW_DIR / "src" / "wpf" / "vba_brain.UI.Avalonia"
        if not wpf_path.exists():
            wpf_path = _WORKFLOW_DIR / "src" / "wpf" / "vba_brain.UI.WPF"
        if not wpf_path.exists():
            wpf_path = _WORKFLOW_DIR / "source" / "vba_brain.UI.WPF"
            
        sync_tool = VMSyncTool(str(wpf_path))
        sync_tool.sync_form(sys.argv[1])
