"""
agents/logic/gen_code_behind.py — Agent Logic UI: Gen C# code-behind từ _ui.json

Flow:
  1. Đọc {FormName}_ui.json (tất cả events)
  2. Với mỗi event có logic thực tế (VBA code / DD steps / macro ref):
     a. Nếu có cs_stub sẵn trong xaml.cs → build prompt → LLM gen → patch body
     b. Nếu chưa có stub (e.g. SYS events như E004 閉じる) → suy ra signature
        từ event meta → LLM gen → inject method mới vào xaml.cs
  3. Logic được xác định từ code nghiệp vụ thực tế, không phân loại event_class
  4. Log terminal: progress per event + summary table cuối
  5. Lưu output snapshot vào outputs/{FormName}/codebehind_ui_output.json

Usage:
  python -m agents.logic.gen_code_behind F_Login
  python -m agents.logic.gen_code_behind F_Login --dry-run
  python -m agents.logic.gen_code_behind F_Login --model qwen
  python -m agents.logic.gen_code_behind --all
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────
LAYER5_DIR = Path(__file__).parent.parent.parent.resolve()
if str(LAYER5_DIR) not in sys.path:
    sys.path.insert(0, str(LAYER5_DIR))

BACKEND_DIR = LAYER5_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

AGENT_DIR   = Path(__file__).parent
INPUTS_DIR  = AGENT_DIR / "inputs"
OUTPUTS_DIR = AGENT_DIR / "outputs"
PROMPTS_DIR = AGENT_DIR / "prompts"

from core.config import VIEWS_DIR as WPF_VIEWS_DIR

logger = logging.getLogger(__name__)


# ── Prompt builder ─────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    prompt_file = PROMPTS_DIR / "agent_logic.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return "You are a WPF C# expert. Generate the method body implementing the given VBA logic in WPF .NET 8."


def has_real_logic(event: dict) -> bool:
    """
    Kiểm tra event có code nghiệp vụ thực tế không.
    Dựa vào VBA code thực + DD steps — không dùng event_class.

    Returns True nếu:
      - logic_detail.code có VBA code thực (không phải placeholder)
      - hoặc dd_steps có nội dung step_2.detail (main logic)
      - hoặc references.macros không rỗng
    """
    logic    = event.get("logic_detail", {})
    dd_steps = event.get("dd_steps", {})
    code     = logic.get("code", "").strip()
    macros   = logic.get("references", {}).get("macros", [])

    # VBA code thực: không phải placeholder "not found" hay comment-only
    has_vba = (
        code
        and "not found" not in code.lower()
        and not code.startswith("//")
    )

    # DD main logic có nội dung
    step2_detail = (dd_steps.get("step_2") or {}).get("detail", "").strip()
    has_dd = bool(step2_detail)

    # Macro reference
    has_macro = bool(macros)

    return has_vba or has_dd or has_macro


def derive_cs_method_name(event: dict, form_name: str) -> str | None:
    """
    Suy ra tên C# method cho event không có cs_stub.
    Pattern: {module_id}_{TriggerSuffix}
    e.g. F004 + クリック時 → F004_Click
    """
    meta      = event.get("event_meta", {})
    module_id = meta.get("module_id", "")
    trigger   = meta.get("event_trigger", "")

    trigger_map = {
        "クリック時":       "Click",
        "ダブルクリック時":  "DblClick",
        "更新後処理":       "AfterUpdate",
        "キー押下時":       "PreviewKeyDown",
        "画面を開く時":     "Loaded",
        "フォーム読み込み後": "ContentRendered",
    }
    suffix = trigger_map.get(trigger)
    if module_id and suffix:
        return f"{module_id}_{suffix}"
    return None


def build_cs_stub_for_new_method(cs_method_name: str, event: dict) -> str:
    """
    Xây dựng C# method signature cho event không có stub sẵn trong xaml.cs.
    """
    meta    = event.get("event_meta", {})
    trigger = meta.get("event_trigger", "")

    # Xác định event args dựa vào trigger
    trigger_args = {
        "クリック時":       "object sender, RoutedEventArgs e",
        "ダブルクリック時":  "object sender, MouseButtonEventArgs e",
        "更新後処理":       "object sender, RoutedEventArgs e",
        "キー押下時":       "object sender, KeyEventArgs e",
        "画面を開く時":     "object sender, RoutedEventArgs e",
        "フォーム読み込み後": "object? sender, EventArgs e",
    }
    args = trigger_args.get(trigger, "object sender, RoutedEventArgs e")
    return f"private void {cs_method_name}({args})"


def ensure_dependency_injection_using(cs_file: Path):
    """
    Ensure the namespace using Microsoft.Extensions.DependencyInjection; and using vba_brain.UI.WPF.Services; are present at the top of the file.
    """
    if not cs_file.exists():
        return
    content = cs_file.read_text(encoding="utf-8")
    modified = False
    
    if "using Microsoft.Extensions.DependencyInjection;" not in content:
        content = "using Microsoft.Extensions.DependencyInjection;\n" + content
        modified = True
        logger.info("[Injector] ✅ Added using Microsoft.Extensions.DependencyInjection; to %s", cs_file.name)
        
    if "using vba_brain.UI.Avalonia.Services;" not in content:
        content = "using vba_brain.UI.Avalonia.Services;\n" + content
        modified = True
        logger.info("[Injector] ✅ Added using vba_brain.UI.Avalonia.Services; to %s", cs_file.name)
        
    if modified:
        cs_file.write_text(content, encoding="utf-8")


def inject_method_into_cs(
    cs_file: Path,
    cs_method_name: str,
    new_method: str,
    dry_run: bool = False,
) -> bool:
    """
    Inject một method hoàn toàn mới vào xaml.cs (không có sẵn trong file).
    Chèn trước dấu đóng ngoặc cuối cùng của class.
    """
    if not cs_file.exists():
        logger.warning("[Injector] File not found: %s", cs_file)
        return False

    content = cs_file.read_text(encoding="utf-8")

    # Kiểm tra method đã tồn tại chưa
    if re.search(r'\b' + re.escape(cs_method_name) + r'\b', content):
        logger.debug("[Injector] Method already exists: %s", cs_method_name)
        return patch_method_in_cs(cs_file, cs_method_name, new_method, dry_run=dry_run)

    if dry_run:
        preview = new_method[:300] + ("..." if len(new_method) > 300 else "")
        logger.info("    [DRY-RUN] INJECT %s preview:\n%s", cs_method_name, preview)
        return True

    # Ensure DI using directive
    ensure_dependency_injection_using(cs_file)
    content = cs_file.read_text(encoding="utf-8")  # reload content after adding using

    # Tìm dấu đóng ngoặc cuối của class (dòng cuối cùng có "}")
    last_brace_pos = content.rfind("\n}")
    if last_brace_pos == -1:
        logger.warning("[Injector] Cannot find class closing brace in %s", cs_file.name)
        return False

    # Indent 4 spaces, thêm blank line trước method
    indented = "\n    " + new_method.strip().replace("\n", "\n    ") + "\n"
    new_content = content[:last_brace_pos] + "\n" + indented + content[last_brace_pos:]
    cs_file.write_text(new_content, encoding="utf-8")
    logger.info("[Injector] ✅ Injected new method: %s → %s", cs_method_name, cs_file.name)
    return True


def build_ui_prompt(event: dict, form_name: str) -> str:
    meta      = event.get("event_meta", {})
    logic     = event.get("logic_detail", {})
    dd_steps  = event.get("dd_steps", {})
    cs_stub   = event.get("cs_stub")
    event_id  = meta.get("event_id", "")
    notes     = meta.get("notes", "")
    vba_code  = logic.get("code", "")
    macros    = logic.get("references", {}).get("macros", [])
    module_id = cs_stub["module_id"] if cs_stub else meta.get("module_id", "")

    # Load macro mappings if available
    macro_map_file = LAYER5_DIR / "agents" / "graphview" / "outputs" / "macros" / "listMacroJpToEn.json"
    macro_mappings = {}
    if macro_map_file.exists():
        try:
            macro_data = json.loads(macro_map_file.read_text(encoding="utf-8"))
            for item in macro_data.get("items", []):
                jp_name = item.get("access_macro_name")
                en_name = item.get("suggested_dotnet_type_name")
                if jp_name and en_name:
                    macro_mappings[jp_name] = en_name
        except Exception as e:
            logger.warning(f"Failed to load macro mappings: {e}")

    # Xác định loại xử lý từ code thực tế (không dùng event_class)
    refs       = logic.get("references", {})
    has_data   = bool(refs.get("queries") or refs.get("tables"))
    has_macro  = bool(refs.get("macros"))
    action_type = meta.get("action_type", "").upper()  # VALID / UI / SYS / FILE

    from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
    _name_map = _load_form_name_map()
    _, vm_file_stem = _resolve_wpf_names(form_name, _name_map)

    prompt  = f"## Generate C# code-behind method\n"
    prompt += f"Form: `{form_name}` | Event: `{event_id}` | Module: `{module_id}`\n\n"

    if has_data:
        # SERVICE events: có query/table → delegate to ViewModel
        vm_method = f"{module_id}Async" if module_id else f"{notes}Async"
        prompt += (
            "> This event accesses data (queries/tables) — SERVICE event.\n"
            f"> Delegate to ViewModel: `if (DataContext is ViewModels.{vm_file_stem} vm) await vm.{vm_method}();`\n"
            "> Code-behind body should be short — just the delegation call.\n\n"
        )
    elif has_macro:
        # Macro events: ViewModel holds the DI-injected macro workflow interface
        # → ALWAYS delegate to ViewModel, NOT call App.ServiceProvider directly in code-behind
        vm_method = f"{module_id}Async" if module_id else f"{notes}Async"
        prompt += (
            "> This event executes an Access macro workflow.\n"
            "> The ViewModel holds the DI-injected macro service interface.\n"
            f"> Delegate to ViewModel: `if (DataContext is ViewModels.{vm_file_stem} vm) await vm.{vm_method}();`\n"
            "> Do NOT call App.ServiceProvider.GetRequiredService<T>() directly in code-behind.\n"
            "> Code-behind body should be short — just the delegation call.\n\n"
        )
    elif action_type == "SYS":
        # SYS events: system/process-level actions inline in code-behind (no ViewModel needed)
        prompt += (
            "> This is a SYS event — system-level action only, no data or macro.\n"
            "> Implement INLINE in code-behind. Do NOT delegate to ViewModel.\n"
            "> Examples: Application.Current.Shutdown(), Process.Start(), MessageBox confirm, etc.\n\n"
        )
    else:
        prompt += (
            "> UI logic only — no DB/service calls.\n"
            "> Use MessageBox.Show, Application.Current.Shutdown(), e.Handled, navigation, etc.\n\n"
        )

    if cs_stub:
        sig      = cs_stub["signature"]
        m_id     = cs_stub["module_id"]
        vba_hdlr = cs_stub["vba_handler"]
        if (has_data or has_macro) and "async" not in sig:
            sig = sig.replace("private void", "private async void", 1)
        prompt += f"### C# method to implement (from `{form_name}.xaml.cs`):\n"
        prompt += f"```csharp\n{sig}\n{{\n    // TODO: implement\n}}\n```\n"
        prompt += f"**Use this exact signature** — F-ID `{m_id}`, VBA: `{vba_hdlr}`\n\n"
    else:
        # Không có stub sẵn — suy ra signature từ event meta
        derived_name = derive_cs_method_name(event, form_name)
        if derived_name:
            derived_sig = build_cs_stub_for_new_method(derived_name, event)
            if (has_data or has_macro) and "async" not in derived_sig:
                derived_sig = derived_sig.replace("private void", "private async void", 1)
            prompt += f"### C# method to generate (new — not yet in xaml.cs):\n"
            prompt += f"```csharp\n{derived_sig}\n{{\n    // TODO: implement\n}}\n```\n"
            prompt += f"**Generate with this exact signature** — Module: `{module_id}`, VBA: `{notes}`\n\n"
        else:
            prompt += f"### Notes: `{notes}` | Module: `{module_id}`\n\n"

    if vba_code and "not found" not in vba_code.lower() and not vba_code.strip().startswith("//"):
        prompt += f"### Original VBA source:\n```vba\n{vba_code}\n```\n\n"
    elif macros:
        prompt += f"### Access macro reference: `{'`, `'.join(macros)}`\n"
        for m in macros:
            mapped_type = macro_mappings.get(m)
            if mapped_type:
                prompt += f"> Mapped Macro Service Type: `{mapped_type}`\n"
                prompt += f"> To execute this macro, use the standard DI pattern:\n"
                prompt += f"> `await App.GetService<{mapped_type}>().ExecuteAsync();`\n"
        prompt += "\n"

    event_info = {k: meta[k] for k in (
        "event_id", "event_trigger", "event_content",
        "logical_name", "physical_name", "notes",
    ) if meta.get(k) and meta[k] not in ("-", "")}
    prompt += f"### Event info:\n```json\n{json.dumps(event_info, ensure_ascii=False, indent=2)}\n```\n\n"

    if dd_steps:
        prompt += f"### DD Steps (business logic):\n```json\n{json.dumps(dd_steps, ensure_ascii=False, indent=2)}\n```\n\n"

    prompt += "Return ONLY the ```csharp ... ``` block with the complete method."
    return prompt


# ── LLM caller ─────────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_prompt: str, form_name: str = "", model=None) -> str:
    from llm.llm_client import L5LLMClient, extract_code_block
    llm = L5LLMClient()
    raw = llm.generate_code(
        task_type="viewmodel",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        agent="logic_ui",
        form_name=form_name,
    )
    code = extract_code_block(raw, "csharp")
    return code.strip() if code else raw.strip()


# ── Code status classifier ─────────────────────────────────────────────────

def _classify_code_status(code: str) -> tuple[str, str]:
    """
    Returns (status_tag, note):
    - DONE  : has real implementation
    - TODO  : only TODO comments or empty body
    - ERROR : generation failed
    """
    if not code or code.strip().startswith("// Error:"):
        return "ERROR", "generation failed"
    c = code.strip()
    body_match = re.search(r'\{([^{}]*)\}', c, re.DOTALL)
    if body_match:
        body = body_match.group(1).strip()
        if not body:
            return "TODO", "empty body"
        non_comment = re.sub(r'//.*$', '', body, flags=re.MULTILINE).strip()
        if not non_comment:
            return "TODO", "only comments"
        if re.search(r'^\s*//\s*TODO', body, re.MULTILINE) and len(non_comment.splitlines()) <= 1:
            return "TODO", "TODO comment only"
    return "DONE", ""


# ── Patcher ────────────────────────────────────────────────────────────────

def patch_method_in_cs(
    cs_file: Path,
    cs_name: str,
    new_method: str,
    dry_run: bool = False,
) -> bool:
    """
    Replace a method in xaml.cs with LLM-generated implementation.
    Uses brace-depth counting to handle any existing body (empty or already patched).
    Preserves doc comments (/// lines) before the method.
    """
    if not cs_file.exists():
        logger.warning("[Patcher] File not found: %s", cs_file)
        return False

    if not dry_run:
        ensure_dependency_injection_using(cs_file)

    content = cs_file.read_text(encoding="utf-8")

    # Find method signature — skip doc comments, find only code signature
    sig_pattern = re.compile(
        r'([ \t]*private\s+(?:async\s+)?(?:void|Task)\s+'
        + re.escape(cs_name)
        + r'\s*\([^)]*\))\s*',
        re.DOTALL,
    )
    sig_match = sig_pattern.search(content)
    if not sig_match:
        logger.warning("[Patcher] ⚠  Method not found: %s in %s", cs_name, cs_file.name)
        return False

    # Find balanced braces from end of signature
    body_start = content.find('{', sig_match.end())
    if body_start == -1:
        logger.warning("[Patcher] ⚠  No opening brace for: %s", cs_name)
        return False

    depth = 0
    body_end = body_start
    for i in range(body_start, len(content)):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                body_end = i
                break

    method_start = sig_match.start()
    method_end   = body_end + 1

    # Determine indentation from first non-doc line
    method_text = content[method_start:method_end]
    first_code_line = next(
        (l for l in method_text.splitlines() if l.strip() and not l.strip().startswith("///")),
        method_text.splitlines()[0] if method_text.splitlines() else "",
    )
    indent = re.match(r'^([ \t]*)', first_code_line).group(1)

    # Re-indent new_method
    new_lines = new_method.strip().splitlines()
    if not new_lines:
        return False
    min_indent = min(
        (len(l) - len(l.lstrip()) for l in new_lines if l.strip()), default=0
    )
    reindented = "\n".join(
        indent + l[min_indent:] if l.strip() else ""
        for l in new_lines
    )

    if dry_run:
        preview = reindented[:300] + ("..." if len(reindented) > 300 else "")
        logger.info("    [DRY-RUN] %s preview:\n%s", cs_name, preview)
        return True

    cs_file.write_text(content[:method_start] + reindented + content[method_end:], encoding="utf-8")
    return True

# ── Cleanup UI Event Bindings ──────────────────────────────────────────────

def patch_xaml_ui_event(xaml_content: str, mod_id: str, cs_name: str) -> str | None:
    """
    Smarter cleanup for non-Button controls using behaviors triggers:
    If a Command is inside <i:EventTrigger EventName="EvName"> and <i:InvokeCommandAction>,
    wire EvName="cs_name" directly to the parent control tag, and remove the EventTrigger block.
    """
    trigger_pattern = re.compile(
        r'<i:EventTrigger\s+EventName="(?P<event_name>[^"]+)"\s*>\s*'
        r'<i:InvokeCommandAction\s+Command="\{Binding\s+' + re.escape(mod_id) + r'Command\}"\s*/?>\s*'
        r'</i:EventTrigger>',
        re.IGNORECASE | re.DOTALL
    )
    
    match = trigger_pattern.search(xaml_content)
    if not match:
        return None
        
    event_name = match.group("event_name")
    start_idx = match.start()
    end_idx = match.end()
    
    # Locate the enclosing <i:Interaction.Triggers>
    triggers_open_match = re.search(r'<i:Interaction\.Triggers\s*>', xaml_content[:start_idx], re.IGNORECASE)
    if triggers_open_match:
        triggers_start = triggers_open_match.start()
        
        # Find ending '>' of the parent tag before <i:Interaction.Triggers>
        tag_end_idx = xaml_content.rfind('>', 0, triggers_start)
        if tag_end_idx != -1:
            parent_tag_sub = xaml_content[:tag_end_idx].strip()
            insert_pos = tag_end_idx - 1 if parent_tag_sub.endswith('/') else tag_end_idx
            
            # Insert the event handler attribute directly on parent control
            new_attr = f' {event_name}="{cs_name}"'
            
            # Check parent tag context to see if it's already there
            parent_tag_full = xaml_content[xaml_content.rfind('<', 0, tag_end_idx):tag_end_idx+1]
            if f'{event_name}=' not in parent_tag_full:
                xaml_content = xaml_content[:insert_pos] + new_attr + xaml_content[insert_pos:]
                # Adjust indices
                start_idx += len(new_attr)
                end_idx += len(new_attr)
            
            # Remove the EventTrigger
            xaml_content = xaml_content[:start_idx] + xaml_content[end_idx:]
            
            # Clean up empty <i:Interaction.Triggers>
            empty_triggers_pattern = re.compile(
                r'<i:Interaction\.Triggers\s*>\s*</i:Interaction\.Triggers\s*>',
                re.IGNORECASE | re.DOTALL
            )
            xaml_content = empty_triggers_pattern.sub('', xaml_content)
            return xaml_content
    return None


def cleanup_ui_event_bindings(form_name: str, ui_methods: list[dict], dry_run: bool = False):
    """
    Remove unused ViewModel stubs and XAML commands for UI-only events.
    For each UI event (e.g. F004_Click):
      - In XAML: Replace Command="{Binding F004Command}" with Click="F004_Click"
      - In ViewModel: Remove F004Command property, ctor init, and F004Async method
    """
    from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
    _name_map = _load_form_name_map()
    view_file_stem, vm_file_stem = _resolve_wpf_names(form_name, _name_map)

    xaml_file = WPF_VIEWS_DIR / f"{view_file_stem}.xaml"
    vm_file = WPF_VIEWS_DIR.parent / "ViewModels" / f"{vm_file_stem}.cs"

    modules_to_clean = []
    for m in ui_methods:
        cs_name = m.get("cs_name")
        if cs_name and "_" in cs_name:
            # cs_name like F004_Click
            modules_to_clean.append((cs_name.split("_")[0], cs_name))

    if not modules_to_clean:
        return

    # Patch XAML
    # DISABLED: Absolutely AI Agent Logic is not allowed to fix/touch UI (.xaml files)
    logger.info("[Cleanup] ⏭  Skipped XAML patching (AI Agent Logic absolutely must not modify/fix the UI .xaml file).")

    # Patch ViewModel
    if vm_file.exists():
        vm_content = vm_file.read_text(encoding="utf-8")
        patched_vm = vm_content
        for mod_id, cs_name in modules_to_clean:
            # Remove public ICommand FXXXCommand { get; set; }
            patched_vm = re.sub(r'^[ \t]*//.*?\n[ \t]*public ICommand ' + mod_id + r'Command.*?\n', '', patched_vm, flags=re.MULTILINE)
            patched_vm = re.sub(r'^[ \t]*public ICommand ' + mod_id + r'Command.*?\n', '', patched_vm, flags=re.MULTILINE)
            
            # Remove FXXXCommand = Cmd(...) in ctor
            patched_vm = re.sub(r'^[ \t]*' + mod_id + r'Command\s*=\s*Cmd\(.*?\);\n', '', patched_vm, flags=re.MULTILINE)
            
            # Remove public virtual async Task FXXXAsync() { ... }
            method_pattern = r'^[ \t]*(?:///.*?\n)*[ \t]*public virtual async System\.Threading\.Tasks\.Task ' + mod_id + r'Async\(\)\s*\{[^}]*\}[\r\n]*'
            patched_vm = re.sub(method_pattern, '', patched_vm, flags=re.MULTILINE)

        if patched_vm != vm_content and not dry_run:
            vm_file.write_text(patched_vm, encoding="utf-8")
            logger.info("[Cleanup] ✅ Removed unused %s commands from ViewModel.", len(modules_to_clean))

# ── Main ───────────────────────────────────────────────────────────────────

def run_ui_agent(
    form_name: str,
    dry_run: bool = False,
    model=None,
    input_type: str = "ui",   # "ui" | "service" | "all"
    no_cache: bool = False,
) -> dict:
    """
    input_type:
      "ui"      → đọc _ui.json      (UI_ONLY events, gen code-behind UI logic)
      "service" → đọc _service.json (WITH_SERVICE events, gen delegate stubs)
      "all"     → chạy cả ui + service
    """
    if input_type == "all":
        # Resolve English view name
        from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
        _name_map = _load_form_name_map()
        view_file_stem, _ = _resolve_wpf_names(form_name, _name_map)

        db_dir = LAYER5_DIR.parent.parent.parent.parent / "data/database_json" / "agent_logic"
        cache_file = db_dir / f"{form_name}_codebehind.json"

        if cache_file.exists() and not dry_run and not no_cache:
            try:
                logger.info(f"[Cache Load] ⚡ Found cached successful run for form '{form_name}' in database_json/agent_logic/. Restoring code-behind...")
                cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
                
                # 1. Restore axaml.cs file
                xaml_cs_path = WPF_VIEWS_DIR / f"{view_file_stem}.axaml.cs"
                if "xaml_cs_content" in cache_data and cache_data["xaml_cs_content"]:
                    WPF_VIEWS_DIR.mkdir(parents=True, exist_ok=True)
                    xaml_cs_path.write_text(cache_data["xaml_cs_content"], encoding="utf-8")
                    logger.info(f"[Cache Load] Restored WPF code-behind: {xaml_cs_path.name}")
                
                # 2. Restore outputs folder snapshots
                out_dir = OUTPUTS_DIR / form_name
                out_dir.mkdir(parents=True, exist_ok=True)
                
                if "ui_output" in cache_data and cache_data["ui_output"]:
                    (out_dir / "codebehind_ui_output.json").write_text(
                        json.dumps(cache_data["ui_output"], ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                if "service_output" in cache_data and cache_data["service_output"]:
                    (out_dir / "codebehind_service_output.json").write_text(
                        json.dumps(cache_data["service_output"], ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                if "all_output" in cache_data and cache_data["all_output"]:
                    (out_dir / "codebehind_all_output.json").write_text(
                        json.dumps(cache_data["all_output"], ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                
                logger.info("[Cache Load] ✅ Restored all outputs successfully.")
                return cache_data.get("combined_results", {"total": 0, "generated": 0, "patched": 0, "skipped": 0, "errors": []})
            except Exception as load_err:
                logger.warning(f"[Cache Load] Failed to restore from cache: {load_err}, running normally...")

        r1 = run_ui_agent(form_name, dry_run, model, "ui", no_cache=no_cache)
        r2 = run_ui_agent(form_name, dry_run, model, "service", no_cache=no_cache)
        # Merge results + save combined snapshot
        combined = {
            "total":     r1["total"]     + r2["total"],
            "generated": r1["generated"] + r2["generated"],
            "patched":   r1["patched"]   + r2["patched"],
            "skipped":   r1["skipped"]   + r2["skipped"],
            "errors":    r1["errors"]    + r2["errors"],
        }
        # Load both snapshots and merge methods
        out_dir = OUTPUTS_DIR / form_name
        all_methods: list[dict] = []
        for phase in ("ui", "service"):
            snap = out_dir / f"codebehind_{phase}_output.json"
            if snap.exists():
                data = json.loads(snap.read_text(encoding="utf-8"))
                all_methods.extend(
            {**m, "phase_type": phase}
            for m in data.get("methods", [])
        )

        # Sort events by event_id (E000, E001, ..., E009)
        all_methods.sort(key=lambda m: m.get("event_id", "E999"))

        done_n  = sum(1 for m in all_methods if m.get("code_status") == "DONE")
        todo_n  = sum(1 for m in all_methods if m.get("code_status") in ("TODO","EMPTY"))
        skip_n  = sum(1 for m in all_methods if m.get("code_status") == "SKIP")
        err_n   = sum(1 for m in all_methods if m.get("code_status") == "ERROR")
        compile_ok = (todo_n + err_n) == 0

        (out_dir / "codebehind_all_output.json").write_text(
            json.dumps({
                "form_name": form_name,
                "results":   combined,
                "summary":   {"done": done_n, "todo": todo_n, "skip": skip_n, "error": err_n, "compile_ok": compile_ok},
                "methods":   all_methods,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[LogicUI] 📦 Combined snapshot saved: codebehind_all_output.json (%d events)", len(all_methods))

        if compile_ok and not dry_run:
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                
                xaml_cs_path = WPF_VIEWS_DIR / f"{view_file_stem}.axaml.cs"
                if not xaml_cs_path.exists():
                    xaml_cs_path = WPF_VIEWS_DIR / f"{view_file_stem}.xaml.cs"
                xaml_cs_content = xaml_cs_path.read_text(encoding="utf-8") if xaml_cs_path.exists() else ""
                
                ui_output = json.loads((out_dir / "codebehind_ui_output.json").read_text(encoding="utf-8")) if (out_dir / "codebehind_ui_output.json").exists() else None
                service_output = json.loads((out_dir / "codebehind_service_output.json").read_text(encoding="utf-8")) if (out_dir / "codebehind_service_output.json").exists() else None
                all_output = json.loads((out_dir / "codebehind_all_output.json").read_text(encoding="utf-8")) if (out_dir / "codebehind_all_output.json").exists() else None
                
                cache_data = {
                    "form_name": form_name,
                    "xaml_cs_content": xaml_cs_content,
                    "combined_results": combined,
                    "ui_output": ui_output,
                    "service_output": service_output,
                    "all_output": all_output
                }
                
                cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info(f"[Cache Save] 💾 Successfully saved successful code-behind run output to {cache_file}")
            except Exception as cache_err:
                logger.warning(f"[Cache Save] Failed to save code-behind to cache: {cache_err}")

        return combined

    input_file = INPUTS_DIR / f"{form_name}_{input_type}.json"
    if not input_file.exists():
        raise FileNotFoundError(
            f"Input not found: {input_file}\n"
            f"Run: python agent_logic.py {form_name} --event-class {input_type} --input-only"
        )

    # Resolve English view name
    from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
    _name_map = _load_form_name_map()
    view_file_stem, vm_file_stem = _resolve_wpf_names(form_name, _name_map)

    data       = json.loads(input_file.read_text(encoding="utf-8"))
    events     = data.get("events", [])
    view_file  = WPF_VIEWS_DIR / f"{view_file_stem}.axaml.cs"
    if not view_file.exists():
        view_file = WPF_VIEWS_DIR / f"{view_file_stem}.xaml.cs"
    sys_prompt = load_system_prompt()

    if not view_file.exists():
        raise FileNotFoundError(f"WPF xaml.cs not found: {view_file}")

    out_dir = OUTPUTS_DIR / form_name
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {"total": 0, "generated": 0, "patched": 0, "skipped": 0, "errors": []}
    method_outputs: list[dict] = []

    total_with_logic = sum(1 for e in events if has_real_logic(e))
    total_stub = sum(1 for e in events if e.get("cs_stub"))
    phase_label = "UI" if input_type == "ui" else "SERVICE" if input_type == "service" else "ALL"
    SEP = "─" * 62
    logger.info("")
    logger.info("┌%s", SEP)
    logger.info("│ Agent Logic [%s]  ·  %s", phase_label, form_name)
    logger.info("│ Events: %d total  /  %d with logic  /  %d with stub  /  %d skip",
                len(events), total_with_logic, total_stub, len(events) - total_with_logic)
    if dry_run:
        logger.info("│ ⚠  DRY-RUN — no files written")
    logger.info("└%s", SEP)
    logger.info("")

    for idx, event in enumerate(events):
        meta     = event.get("event_meta", {})
        cs_stub  = event.get("cs_stub")
        event_id = meta.get("event_id", "?")
        notes    = meta.get("notes", "")[:38]
        results["total"] += 1

        step = f"[{idx+1}/{len(events)}]"

        # ── Skip events with no real logic (không có VBA code, DD steps, hay macro) ──
        if not has_real_logic(event):
            reason = "no VBA code / DD steps / macro"
            logger.info("  ⏭  %s %-8s  %-38s  SKIP (%s)", step, event_id, notes, reason)
            results["skipped"] += 1
            method_outputs.append({
                "event_id": event_id, "notes": meta.get("notes",""),
                "cs_name": None, "code": "", "status": "skipped",
                "code_status": "SKIP", "note": reason,
                "phase_type": input_type,
            })
            continue

        # ── Xác định cs_name: dùng stub sẵn hoặc suy ra từ event meta ──
        if cs_stub:
            cs_name   = cs_stub["cs_name"]
            if cs_name and view_file.exists():
                cs_content = view_file.read_text(encoding="utf-8")
                is_new = not bool(re.search(r'\b' + re.escape(cs_name) + r'\b', cs_content))
            else:
                is_new = True
        else:
            cs_name   = derive_cs_method_name(event, form_name)
            is_new    = True  # method chưa có trong xaml.cs → sẽ inject mới

        logger.info("  🔄 %s %-8s  %-38s  → %s%s",
                    step, event_id, notes, cs_name or "?",
                    " [NEW]" if is_new else "")

        try:
            user_prompt = build_ui_prompt(event, form_name)
            generated   = call_llm(sys_prompt, user_prompt, form_name, model)
            # Post-process: fix legacy GetService patterns
            generated = re.sub(r'App\.GetService<', 'App.ServiceProvider.GetRequiredService<', generated)
            generated = re.sub(r'App\.Current\.Services\.GetService<', 'App.ServiceProvider.GetRequiredService<', generated)
            # Post-process: macro events MUST delegate via ViewModel, not App.ServiceProvider in code-behind
            _logic_refs = event.get("logic_detail", {}).get("references", {})
            _module_id  = (cs_stub["module_id"] if cs_stub else meta.get("module_id", ""))
            if bool(_logic_refs.get("macros")) and "App.ServiceProvider.GetRequiredService" in generated:
                vm_method_name = f"{_module_id}Async" if _module_id else f"{cs_name}Async"
                stub_sig = cs_stub["signature"] if cs_stub else f"private async void {cs_name}(object sender, EventArgs e)"
                if "async" not in stub_sig:
                    stub_sig = stub_sig.replace("private void", "private async void", 1)
                generated = (
                    f"{stub_sig}\n"
                    f"{{\n"
                    f"    // Macro workflow \u2014 delegate to ViewModel which holds DI-injected service\n"
                    f"    if (DataContext is ViewModels.{vm_file_stem} vm)\n"
                    f"        await vm.{vm_method_name}();\n"
                    f"}}"
                )
                logger.info("     [PostProcess] Fixed macro event %s \u2192 delegate via vm.%s()", event_id, vm_method_name)
            results["generated"] += 1

            code_status, code_note = _classify_code_status(generated)

            patched = False
            if cs_name:
                if is_new:
                    # Method chưa có → inject vào xaml.cs
                    patched = inject_method_into_cs(view_file, cs_name, generated, dry_run=dry_run)
                else:
                    # Method có sẵn → patch body
                    patched = patch_method_in_cs(view_file, cs_name, generated, dry_run=dry_run)

                if patched:
                    results["patched"] += 1
                else:
                    code_status = "ERROR"
                    code_note   = "patch/inject failed — check xaml.cs"
            else:
                code_note = "cannot derive cs_name from event meta"

            icon = "✅" if code_status == "DONE" else ("⚠️ " if code_status == "TODO" else "❌")
            extra = f"  [{code_note}]" if code_note else ""
            logger.info("     %s %s  %s%s", icon, code_status, cs_name or event_id, extra)

            method_outputs.append({
                "event_id":   event_id,
                "notes":      meta.get("notes",""),
                "cs_name":    cs_name,
                "is_new":     is_new,
                "code":       generated,
                "status":     "success",
                "code_status": code_status,
                "note":       code_note,
                "phase_type": input_type,
            })

        except Exception as exc:
            logger.error("     ❌ ERROR: %s", exc)
            results["errors"].append({"event_id": event_id, "error": str(exc)})
            method_outputs.append({
                "event_id": event_id, "notes": meta.get("notes",""),
                "cs_name": cs_name, "code": f"// Error: {exc}",
                "status": "error", "code_status": "ERROR", "note": str(exc)[:80],
                "phase_type": input_type,
            })

    # ── Summary table ──────────────────────────────────────────────────
    logger.info("")
    logger.info("┌─────────────────────────────────────────────────────────────")
    logger.info("│ RESULTS — %s", form_name)
    logger.info("├──────────┬────────────────────────────┬────────────┬────────")
    logger.info("│ EventID  │ VBA Handler                │ C# Method  │ Status")
    logger.info("├──────────┼────────────────────────────┼────────────┼────────")

    done_n = todo_n = skip_n = err_n = 0
    for m in method_outputs:
        st   = m.get("code_status", "?")
        icon = {"DONE":"✅","TODO":"⚠️ ","EMPTY":"⚠️ ","SKIP":"⏭ ","ERROR":"❌"}.get(st, " ?")
        note = m.get("note", "")[:20]
        cs   = (m.get("cs_name") or "—")[:12]
        handler = m.get("notes","")[:28]
        logger.info("│ %-8s │ %-28s │ %-10s │ %s %-5s %s",
                    m["event_id"], handler, cs, icon, st, note)
        if   st == "DONE":  done_n += 1
        elif st in ("TODO","EMPTY"): todo_n += 1
        elif st == "SKIP":  skip_n += 1
        elif st == "ERROR": err_n  += 1

    logger.info("├──────────┴────────────────────────────┴────────────┴────────")
    logger.info("│  ✅ DONE: %-3d  ⚠️  TODO: %-3d  ⏭ SKIP: %-3d  ❌ ERR: %d",
                done_n, todo_n, skip_n, err_n)

    compile_ok = (todo_n + err_n) == 0
    if compile_ok and done_n > 0:
        logger.info("│  🟢 All generated methods have implementation — ready to compile")
    elif todo_n > 0:
        logger.info("│  🟡 %d method(s) have empty/TODO body — review before build", todo_n)
    if err_n > 0:
        logger.info("│  🔴 %d error(s) — check above logs", err_n)
    logger.info("└─────────────────────────────────────────────────────────────")
    logger.info("")

    # Save snapshot — tên file theo input_type để không ghi đè
    snapshot_name = f"codebehind_{input_type}_output.json"
    (out_dir / snapshot_name).write_text(
        json.dumps({
            "form_name": form_name,
            "results":   results,
            "summary":   {
                "done": done_n, "todo": todo_n,
                "skip": skip_n, "error": err_n,
                "compile_ok": compile_ok,
            },
            "methods": method_outputs,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if not dry_run and results["patched"] > 0:
        logger.info("📝 Updated: %s", view_file.name)

    # Nếu là phase "ui", dọn dẹp các command dư thừa ở XAML và ViewModel
    if input_type == "ui":
        cleanup_ui_event_bindings(form_name, method_outputs, dry_run=dry_run)

    return results


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Agent Logic UI — Gen C# code-behind methods từ _ui.json, patch vào xaml.cs"
    )
    parser.add_argument("form_name",        nargs="?", help="Form name, e.g. F_Login")
    parser.add_argument("--all",            action="store_true", help="Process all forms")
    parser.add_argument("--dry-run",        action="store_true", help="Preview only, no write")
    parser.add_argument("--model",          help="Override LLM model")
    parser.add_argument("--input-type",     choices=["ui","service","all"], default="ui",
                        help="Input type: ui, service, or all (default: ui)")
    parser.add_argument("--no-cache",       action="store_true", help="Bypass cached run and execute LLM generation")
    args = parser.parse_args()

    if not args.all and not args.form_name:
        parser.error("Need form_name or --all")

    from core.config import AVAILABLE_MODELS
    model = AVAILABLE_MODELS.get(args.model) if args.model else None

    forms = (
        sorted(p.stem.replace("_ui","") for p in INPUTS_DIR.glob("*_ui.json"))
        if args.all else [args.form_name]
    )
    if args.all:
        logger.info("[LogicUI] Found %d forms", len(forms))

    for form in forms:
        try:
            run_ui_agent(
                form_name=form,
                dry_run=args.dry_run,
                model=model,
                input_type=args.input_type,
                no_cache=args.no_cache,
            )
        except FileNotFoundError as exc:
            logger.error("❌ %s: %s", form, exc)
        except Exception as exc:
            logger.error("❌ %s failed: %s", form, exc, exc_info=True)


if __name__ == "__main__":
    main()
