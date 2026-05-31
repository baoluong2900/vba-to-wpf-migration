"""
agents/logic/gen_vm_methods.py — Agent Logic Service: Gen ViewModel Async Method Bodies

Flow:
  1. Đọc {FormName}_service.json (SERVICE events)
  2. Inject _<feature>Service field + constructor DI vào ViewModel nếu chưa có
  3. Với mỗi event có cs_stub:
     a. Build prompt: cs_stub.signature + dd_steps + service_context + bd_items + VBA
     b. LLM gen → ViewModel method body (gọi _loginService.FXXXAsync(request))
     c. patch_vm_method() — thay thế stub body trong ViewModels/F_Login.cs
  4. Save snapshot → outputs/{FormName}/vm_methods_output.json
  5. Log summary table

Usage:
  python -m agents.logic.gen_vm_methods F_Login
  python -m agents.logic.gen_vm_methods F_Login --dry-run
  python -m agents.logic.gen_vm_methods F_Login --model qwen
  python -m agents.logic.gen_vm_methods --all
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from core.config import TARGET_LANGUAGE

# ── Path setup ──────────────────────────────────────────────────────────────
LAYER5_DIR = Path(__file__).parent.parent.parent.resolve()
if str(LAYER5_DIR) not in sys.path:
    sys.path.insert(0, str(LAYER5_DIR))

BACKEND_DIR = LAYER5_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

AGENT_DIR    = Path(__file__).parent
INPUTS_DIR   = AGENT_DIR / "inputs"
OUTPUTS_DIR  = AGENT_DIR / "outputs"
PROMPTS_DIR  = AGENT_DIR / "prompts"

# UI Agent's ViewModel skeleton outputs — read-only input
UI_VIEWMODELS_DIR = AGENT_DIR.parent / "ui" / "outputs"

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _form_to_feature(form_name: str) -> str:
    """F_Login → Login"""
    name = form_name or ""
    if name.startswith("F_"):
        name = name[2:]
    return re.sub(r"[^\w]", "", name) or "Default"


def _feature_to_service_field(feature: str) -> str:
    """Login → _loginService"""
    if not feature:
        return "_service"
    return f"_{feature[0].lower()}{feature[1:]}Service"


def _feature_to_iface(feature: str) -> str:
    """Login → ILoginService (fallback only — prefer _resolve_iface_from_service_context)"""
    return f"I{feature}Service"


def _feature_to_service_class(feature: str) -> str:
    """Login → LoginService"""
    return f"{feature}Service"


def _resolve_iface_from_service_context(events: list[dict], feature: str, form_name: str = "") -> str:
    """
    Đọc interface name THỰC TẾ từ service_context trong JSON hoặc từ thư mục service output/source.
    Fallback về _feature_to_iface(feature) nếu không tìm thấy.
    """
    if form_name:
        # 1. Check service outputs dir
        service_iface_dir = AGENT_DIR.parent / "service" / "outputs" / form_name / "Application" / "Interfaces"
        if service_iface_dir.exists():
            files = list(service_iface_dir.glob("I*Service.cs"))
            if files:
                logger.info("[Agent VM] Found actual interface file in service outputs: %s", files[0].name)
                return files[0].stem
                
        # 2. Check actual source directory
        source_dir = AGENT_DIR.parent.parent.parent.parent / "source"
        iface_dir = source_dir / "vba_brain.Application" / "Interfaces"
        if iface_dir.exists():
            for f in iface_dir.glob("*.cs"):
                if feature.lower() in f.name.lower() and f.name.lower().startswith("i") and f.name.lower().endswith("service.cs"):
                    logger.info("[Agent VM] Found actual interface file in source tree: %s", f.name)
                    return f.stem

    for event in events:
        svc_ctx = event.get("service_context")
        if not svc_ctx:
            continue
        # Structured dict (mới)
        if isinstance(svc_ctx, dict):
            iface_content = svc_ctx.get("interface", {}).get("content", "") or ""
            m = re.search(r'public\s+interface\s+(I\w+Service)', iface_content)
            if m:
                return m.group(1)
            # Cũng check file name
            iface_file = svc_ctx.get("interface", {}).get("file", "") or ""
            fname_m = re.match(r'^(I\w+Service)\.cs$', iface_file, re.IGNORECASE)
            if fname_m:
                return fname_m.group(1)
        # Legacy string blob
        elif isinstance(svc_ctx, str):
            m = re.search(r'public\s+interface\s+(I\w+Service)', svc_ctx)
            if m:
                return m.group(1)
    # Fallback: derive từ feature name
    return _feature_to_iface(feature)


def _resolve_field_from_iface(iface_name: str) -> str:
    """
    IFLoginService → _fLoginService
    ILoginService  → _loginService
    Strip leading I, lowercase first char, add Service suffix.
    """
    # Strip leading 'I'
    name = iface_name[1:] if iface_name.startswith("I") else iface_name
    # Strip trailing 'Service' to get feature part
    if name.endswith("Service"):
        feature = name[:-len("Service")]
    else:
        feature = name
    if not feature:
        return "_service"
    return f"_{feature[0].lower()}{feature[1:]}Service"


def load_system_prompt() -> str:
    prompt_file = PROMPTS_DIR / "agent_vm_methods.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return (
        "You are a WPF MVVM expert. Generate the ViewModel async method body "
        "that delegates to the Application Service layer."
    )


# ── Code status classifier ───────────────────────────────────────────────────

def _classify_code_status(code: str) -> tuple[str, str]:
    if not code or code.strip().startswith("// Error:"):
        return "ERROR", "generation failed"
    c = code.strip()
    body_match = re.search(r'\{(.*)\}', c, re.DOTALL)
    if body_match:
        body = body_match.group(1).strip()
        if not body:
            return "TODO", "empty body"
        non_comment = re.sub(r'//.*$', '', body, flags=re.MULTILINE).strip()
        if not non_comment:
            return "TODO", "only comments"
        if re.search(r'^\s*await\s+System\.Threading\.Tasks\.Task\.CompletedTask', body, re.MULTILINE):
            return "TODO", "still stub body"
    return "DONE", ""


# ── Service field injector ───────────────────────────────────────────────────

def inject_service_field(
    vm_file: Path,
    iface_name: str,
    field_name: str,
    feature: str,
    dry_run: bool = False,
    form_name: str = "",
) -> bool:
    """
    Thêm service field và cập nhật constructor để inject ILoginService.
    Chỉ thêm nếu chưa có.

    Strategy:
      - Thêm `private readonly I{Feature}Service {field};` vào sau class opening brace
      - Thêm param vào constructor + assign
    """
    if not vm_file.exists():
        logger.warning("[VMInjector] File not found: %s", vm_file)
        return False

    content = vm_file.read_text(encoding="utf-8")

    # Kiểm tra đã có field chưa
    if re.search(re.escape(field_name), content):
        logger.debug("[VMInjector] Service field already exists: %s", field_name)
        return True

    if dry_run:
        logger.info("    [DRY-RUN] Would inject service field: %s %s", iface_name, field_name)
        return True

    # ── Thêm using directives cần thiết ──
    for ns in (
        "vba_brain.Application.Interfaces",
        f"vba_brain.Application.DTOs.Requests.{form_name}" if form_name else "vba_brain.Application.DTOs.Requests",
        "System.Windows",          # MessageBox, MessageBoxButton, MessageBoxImage
    ):
        if not re.search(r'^\s*using\s+' + re.escape(ns) + r'\s*;', content, re.MULTILINE):
            content = re.sub(
                r'(^using\s+[\w\.]+;)',
                f'\\1\nusing {ns};',
                content, count=1, flags=re.MULTILINE,
            )

    # ── Thêm field sau opening brace của class ──
    class_open = re.search(r'(public\s+class\s+\w+[^{]*\{)', content)
    if not class_open:
        logger.warning("[VMInjector] Cannot find class opening brace in %s", vm_file.name)
        return False

    field_decl = (
        f"\n    private readonly {iface_name} {field_name};\n"
    )
    insert_pos = class_open.end()
    content = content[:insert_pos] + field_decl + content[insert_pos:]

    # ── Cập nhật constructor: dùng class name từ file stem, không phải feature ──
    class_name = vm_file.stem
    ctor_pattern = re.compile(
        r'(public\s+' + re.escape(class_name) + r'\s*\()([^)]*?)(\))',
        re.DOTALL,
    )
    ctor_match = ctor_pattern.search(content)
    if ctor_match:
        start_idx = ctor_match.start()
        
        existing_params = ctor_match.group(2).strip()
        # Derive param variable name từ iface_name để nhất quán với field_name
        # IFLoginService → fLoginService; ILoginService → loginService
        iface_strip = iface_name[1:] if iface_name.startswith("I") else iface_name
        if iface_strip.endswith("Service"):
            iface_feature = iface_strip[:-len("Service")]
        else:
            iface_feature = iface_strip
        param_var = f"{iface_feature[0].lower()}{iface_feature[1:]}Service" if iface_feature else "service"
        new_param  = f"{iface_name} {param_var}"

        new_params = f"{existing_params}, {new_param}" if existing_params else new_param
        new_ctor_sig = f"{ctor_match.group(1)}{new_params}{ctor_match.group(3)}"
        
        # Modify the parameterized constructor first
        content = content[:ctor_match.start()] + new_ctor_sig + content[ctor_match.end():]

        # Thêm assignment vào đầu constructor body
        ctor_brace = content.find('{', start_idx)
        if ctor_brace != -1:
            assign = f"\n        {field_name} = {param_var};"
            content = content[:ctor_brace + 1] + assign + content[ctor_brace + 1:]
            
    else:
        logger.warning("[VMInjector] Constructor not found for %s in %s", feature, vm_file.name)

    vm_file.write_text(content, encoding="utf-8")
    logger.info("[VMInjector] ✅ Injected service field %s via parameterized constructor → %s", field_name, vm_file.name)
    return True


def inject_vm_properties(
    vm_file: Path,
    bd_items: list[dict],
    dry_run: bool = False,
) -> int:
    """
    Thêm các ViewModel properties còn thiếu (từ bd_items) vào trước comment '# ─ Properties ──'.
    Chỉ thêm property nếu tên chưa tồn tại trong file.
    Returns: number of properties injected.
    """
    if not vm_file.exists() or not bd_items:
        return 0

    content = vm_file.read_text(encoding="utf-8")
    added = 0
    new_props: list[str] = []

    existing_props = set(re.findall(r'public\s+[\w<>?]+\s+(\w+)\s*\{', content))

    for item in bd_items:
        pn   = item.get("physical_name", "").strip()
        ln   = item.get("logical_name", "").strip()
        attr = item.get("item_attribute", "").strip().upper()
        if not pn:
            continue
        # PascalCase property name
        prop_name = pn[:1].upper() + pn[1:]
        
        # Already in file?
        if prop_name in existing_props:
            continue
            
        # Pick C# type
        cs_type = "string"
        if attr in ("INT", "INTEGER", "NUM", "NUMBER"):
            cs_type = "int"
        elif attr in ("BOOL", "BOOLEAN"):
            cs_type = "bool"
            
        new_props.append(
            f"    // [BD] {ln}\n"
            f"    public {cs_type} {prop_name} {{ get; set; }} = "
            + ("string.Empty;" if cs_type == "string" else "default;") + "\n"
        )
        existing_props.add(prop_name)
        added += 1
        
        # Special sync linkage for F_Login txtID -> ID binding
        if prop_name == "TxtID" and "ID" not in existing_props:
            new_props.append(
                f"    // Link ID binding to TxtID for DTO mapping\n"
                f"    public string ID\n"
                f"    {{\n"
                f"        get => TxtID;\n"
                f"        set => TxtID = value;\n"
                f"    }}\n"
            )
            existing_props.add("ID")
            added += 1

    if not new_props:
        return 0

    if dry_run:
        logger.info("    [DRY-RUN] Would inject %d ViewModel properties", added)
        return added

    # Insert before the '// ─ Properties ──' comment block or before first public property
    prop_block = "\n".join(new_props)
    insert_pat = re.search(r'([ \t]*// ─+ Properties)', content)
    if insert_pat:
        pos = insert_pat.start()
        content = content[:pos] + prop_block + "\n" + content[pos:]
    else:
        # Fallback: insert before first 'public string'
        pub = re.search(r'([ \t]*public\s+\w+\s+\w+\s*\{)', content)
        if pub:
            content = content[:pub.start()] + prop_block + "\n" + content[pub.start():]

    vm_file.write_text(content, encoding="utf-8")
    logger.info("[VMInjector] ➕ Injected %d missing properties → %s", added, vm_file.name)
    return added

def inject_vm_method(
    vm_file: Path,
    cs_name: str,
    new_method: str,
    dry_run: bool = False,
) -> bool:
    """
    Inject a new method at the end of the ViewModel class.
    """
    if not vm_file.exists():
        logger.warning("[VMInjector] File not found: %s", vm_file)
        return False

    content = vm_file.read_text(encoding="utf-8")

    # Check if already exists
    if re.search(r'\b' + re.escape(cs_name) + r'\b', content):
        logger.debug("[VMInjector] Method already exists: %s", cs_name)
        return False

    if dry_run:
        preview = new_method[:300] + ("..." if len(new_method) > 300 else "")
        logger.info("    [DRY-RUN] VM INJECT %s preview:\n%s", cs_name, preview)
        return True

    # Find the closing brace of the class
    last_brace_pos = content.rfind("}")
    if last_brace_pos == -1:
        logger.warning("[VMInjector] Cannot find class closing brace in %s", vm_file.name)
        return False

    # Indent 4 spaces, add blank line
    indented = "\n    " + new_method.strip().replace("\n", "\n    ") + "\n"
    new_content = content[:last_brace_pos] + indented + content[last_brace_pos:]
    vm_file.write_text(new_content, encoding="utf-8")
    logger.info("[VMInjector] ✅ Injected new VM method: %s → %s", cs_name, vm_file.name)
    return True

def patch_vm_method(
    vm_file: Path,
    cs_name: str,
    new_method: str,
    dry_run: bool = False,
) -> bool:
    """
    Replace a ViewModel async method body with LLM-generated implementation.
    Supports both:
      - `public virtual async System.Threading.Tasks.Task F000Async()`
      - `public virtual async Task F000Async()`
    """
    if not vm_file.exists():
        logger.warning("[VMPatcher] File not found: %s", vm_file)
        return False

    content = vm_file.read_text(encoding="utf-8")

    # Find method signature — flexible match (Task / System.Threading.Tasks.Task)
    sig_pattern = re.compile(
        r'([ \t]*(?:public|private|protected|internal)\s+(?:virtual\s+|override\s+)?'
        r'(?:async\s+)?(?:System\.Threading\.Tasks\.)?Task\s+'
        + re.escape(cs_name)
        + r'\s*\(\s*\))\s*',
        re.DOTALL,
    )
    sig_match = sig_pattern.search(content)
    if not sig_match:
        logger.warning("[VMPatcher] ⚠  Method not found: %s in %s", cs_name, vm_file.name)
        return False

    # Find balanced braces
    body_start = content.find('{', sig_match.end())
    if body_start == -1:
        logger.warning("[VMPatcher] ⚠  No opening brace for: %s", cs_name)
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

    # Determine indentation
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

    vm_file.write_text(content[:method_start] + reindented + content[method_end:], encoding="utf-8")
    logger.info("[VMPatcher] ✅ Patched: %s → %s", cs_name, vm_file.name)
    return True


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_vm_prompt(event: dict, form_name: str, feature: str, vm_method_name: str,
                    iface: str = "") -> str:
    """
    Build LLM prompt for generating a ViewModel async method body.
    vm_method_name: e.g. 'F003Async' — the ViewModel method to implement.
    iface: actual interface name resolved from service_context (e.g. 'IFLoginService').
           Falls back to _feature_to_iface(feature) if not provided.
    """
    meta        = event.get("event_meta", {})
    logic       = event.get("logic_detail", {})
    dd_steps    = event.get("dd_steps", {})
    svc_ctx_raw = event.get("service_context")   # dict (structured) hoặc str (legacy)
    bd_items    = event.get("bd_items", [])

    event_id    = meta.get("event_id", "")
    module_id   = meta.get("module_id", meta.get("event_id", ""))
    trigger     = meta.get("event_trigger", "")
    notes       = meta.get("notes", "")
    vba_code    = logic.get("code", "")

    # ── Resolve interface / service_field từ structured context ────────
    resolved_iface = iface or _feature_to_iface(feature)
    service_field  = _resolve_field_from_iface(resolved_iface)
    request_type  = f"{module_id}Request"
    response_type = f"{module_id}Response"

    svc_structured: dict = {}
    if isinstance(svc_ctx_raw, dict):
        svc_structured = svc_ctx_raw
        hint = svc_structured.get("service_field_hint", "")
        if hint:
            service_field = hint

    # Shortcut helpers
    req_props  = svc_structured.get("request",  {}).get("properties", [])  if svc_structured else []
    res_props  = svc_structured.get("response", {}).get("properties", [])  if svc_structured else []
    iface_sig  = svc_structured.get("interface_method", "")                if svc_structured else ""

    # ── Fallback: đọc Request DTO từ source nếu không có structured ─────
    dto_fallback = ""
    if not req_props and not svc_structured:
        source_root = LAYER5_DIR.parent.parent / "source"
        dto_file = source_root / "vba_brain.Application" / "DTOs" / "Requests" / f"{feature}ServiceRequests.cs"
        if dto_file.exists():
            try:
                dto_fallback = dto_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("[VMBuilder] Error reading DTO file %s: %s", dto_file.name, e)

    # ── Build prompt ─────────────────────────────────────────────────────
    vm_signature = f"public virtual async System.Threading.Tasks.Task {vm_method_name}()"

    # Header thay đổi format để break Qwen prefix cache
    import time as _time
    _ts = int(_time.time()) % 10000  # 4-digit rotating suffix
    prompt  = f"# WPF ViewModel実装 [{_ts}]: `{form_name}.{vm_method_name}`\n"
    prompt += f"イベント: `{event_id}` | トリガー: `{trigger}`\n\n"

    # ── Reminder: comment language + TODO rules ────────────────────────
    prompt += (
        f"> ⚠️ **必須ルール**: コメントはすべて{TARGET_LANGUAGE}で書くこと。英語コメント禁止。\n"
        "> TODOは最大1個、仕様で判断不能な箇所のみ。コメント行数は最大5行。\n\n"
    )

    prompt += (
        f"> **SERVICE**: Build `{request_type}` from ViewModel properties, "
        f"call `await {service_field}.{vm_method_name}(request)`, handle result.\n\n"
    )

    prompt += "### Method to implement (EXACT signature):\n"
    prompt += f"```csharp\n{vm_signature}\n{{\n    // TODO: implement\n}}\n```\n"
    prompt += f"F-ID: `{module_id}` | VBA: `{notes}`\n\n"

    # Interface signature (1 dòng)
    if iface_sig:
        prompt += f"### Service method signature:\n`{iface_sig}`\n\n"

    # Request properties (compact list)
    if req_props:
        prompt += f"### `{request_type}` properties (ONLY these — no hallucination):\n"
        for p in req_props:
            nullable_mark = "?" if p.get("nullable") else ""
            prompt += f"- `{p['name']}`: {p['type']}{nullable_mark}\n"
        prompt += "\n"
    elif dto_fallback:
        prompt += f"### `{request_type}` definition:\n```csharp\n{dto_fallback}\n```\n\n"

    # Response properties (compact list)
    if res_props:
        prompt += f"### `{response_type}` properties — **ONLY these exist, do NOT use others**:\n"
        for p in res_props:
            nullable_mark = "?" if p.get("nullable") else ""
            prompt += f"- `{p['name']}`: {p['type']}{nullable_mark}\n"
        prompt += f"> ❌ 禁止: `result.LatestVersionComment`, `result.RecordCount` など上記以外のプロパティを使わない\n\n"

        # ── Entity shape hints: resolve IEnumerable<XEntity> fields ──────────
        # LLMがAuthEntity.IsAdminなど存在しないプロパティを作らないよう、
        # entity の実際のフィールドをプロンプトに含める
        entity_shapes = []
        for p in res_props:
            shape = p.get("entity_shape")
            if shape:
                entity_shapes.append(shape)

        if entity_shapes:
            prompt += "### Entity field definitions (use ONLY these — do NOT invent properties):\n"
            for shape in entity_shapes:
                cls  = shape["class"]
                flds = shape["fields"]
                prompt += f"#### `{cls}`:\n"
                for f in flds:
                    col_hint = f" // DB column: {f['column']}" if f.get("column") else ""
                    prompt += f"- `{f['name']}`: `{f['type']}`{col_hint}\n"
                prompt += (
                    f"> ❌ 禁止: `{cls}.IsAdmin`, `{cls}.AdminId` など上記以外のフィールドを使わない\n"
                    f"> 管理者判定は `{cls}.AdminFlag` (string) — `!= \"0\"` でチェック\n\n"
                    if any(f["name"] == "AdminFlag" for f in flds)
                    else f"> ❌ 禁止: 上記リスト以外の `{cls}` フィールドを使わない\n\n"
                )
    else:
        prompt += f"> `{response_type}` has only `Success` (bool) + `Message` (string?) — no other properties.\n"
        prompt += f"> ❌ **絶対禁止**: `result.VersionComment`, `result.LatestVersionComment` など存在しないプロパティを使わない\n"
        prompt += f"> `result.Message` にサービス側からのメッセージが入る。それだけを使う。\n\n"

    prompt += f"**Service call:** `await {service_field}.{vm_method_name}(request)`\n\n"

    # ── DD pattern hints: version check, auth, etc. ───────────────────────
    dd_text_flat = json.dumps(dd_steps, ensure_ascii=False) if dd_steps else ""

    # Version check pattern (F002-type)
    # DD: "バージョン比較" / "最新版" → Service returns VersionComment=latestVersion,
    # ViewModel lưu vào Comment1 property (bound to label) + show install message nếu có
    _is_version_check = any(kw in dd_text_flat for kw in ("バージョン", "最新版", "インストール", "コメント"))
    if _is_version_check:
        prompt += (
            "### ⚠️ 実装ガイド: バージョンチェックパターン\n"
            f"> `{response_type}.VersionComment` にはServiceがDBから取得した最新バージョン文字列が入る。\n"
            f"> ViewModelは以下の順序で処理すること:\n"
            f"> 1. `response.VersionComment` を `Comment1` プロパティに代入 (XAMLのラベルにバインド済み)\n"
            f"> 2. `Comment1` が空でない場合 → バージョン不一致と判断してインストールメッセージを表示\n"
            f"> **禁止**: `ラベル400`やUIコントロールから直接Captionを読み取るコードを書かない。\n"
            f"> **禁止**: `currentVersionPart`, `sLvlCmnt` などのローカル変数でUIから値を取得しない。\n"
            f"> **実装例:**\n"
            f"> ```csharp\n"
            f"> var request = new {request_type}();\n"
            f"> var response = await {service_field}.{vm_method_name}(request);\n"
            f"> if (!response.Success)\n"
            f"> {{\n"
            f'>     MessageBox.Show(response.Message ?? "バージョン情報の取得に失敗しました。",\n'
            f'>         "エラー", MessageBoxButton.OK, MessageBoxImage.Error);\n'
            f">     return;\n"
            f"> }}\n"
            f"> // DBから取得した最新バージョンをComment1プロパティに設定 (XAMLラベルにバインド)\n"
            f"> Comment1 = response.VersionComment ?? string.Empty;\n"
            f"> if (!string.IsNullOrEmpty(Comment1))\n"
            f"> {{\n"
            f'>     MessageBox.Show("最新版ではありません！\\nインストールします。",\n'
            f'>         "確認", MessageBoxButton.OK, MessageBoxImage.Exclamation);\n'
            f"> }}\n"
            f"> ```\n\n"
        )

    # VBA-derived ViewModel init hints (before service call)
    # Detect patterns that need ViewModel property initialization before building request
    vm_init_hints: list[str] = []
    if vba_code:
        # Pattern: WScript.Network.UserName → Me.txtID = UserName → TxtID = Environment.UserName
        if "WshNetworkObject" in vba_code or "WScript.Network" in vba_code or ".UserName" in vba_code:
            vm_init_hints.append("TxtID = System.Environment.UserName;  // VBA DD 2.1: WScript.Network.UserName → Me.txtID")
    if vm_init_hints:
        prompt += "### ⚠️ 必須: service呼び出し前にこのコードを実行すること:\n```csharp\n"
        for hint in vm_init_hints:
            prompt += f"{hint}\n"
        prompt += "```\n(これを省略すると仕様違反になる)\n\n"

    # BD items (input fields)
    input_items = [i for i in bd_items if i.get("io", "").upper() == "I"]
    if input_items:
        prompt += "### BD Input fields → Request mapping:\n"
        for item in input_items:
            ln = item.get("logical_name", "")
            pn = item.get("physical_name", "")
            prompt += f"- ViewModel.`{pn}` ({ln}) → `{request_type}.{_pascal(pn)}`\n"
        prompt += "\n"

    # VBA source — suppress khi version-check pattern active để tránh LLM
    # gen currentVersionPart / label caption extraction
    _suppress_vba = _is_version_check
    if not _suppress_vba and vba_code and "not found" not in vba_code.lower() and not vba_code.strip().startswith("//"):
        prompt += f"### Original VBA:\n```vba\n{vba_code}\n```\n\n"

    # Event info (chỉ giữ fields quan trọng)
    event_info = {k: meta[k] for k in (
        "event_id", "event_trigger", "event_content", "notes",
    ) if meta.get(k) and meta[k] not in ("-", "")}
    prompt += f"### Event:\n```json\n{json.dumps(event_info, ensure_ascii=False, indent=2)}\n```\n\n"

    # DD Steps
    if dd_steps:
        prompt += f"### DD Steps:\n```json\n{json.dumps(dd_steps, ensure_ascii=False, indent=2)}\n```\n\n"

    # Special instruction for events where DD says "compare/check" but Response only has Success+Message
    # In this case, the service has already done the comparison, ViewModel just handles result
    # EXCLUDE version-check pattern — ViewModel needs to compare version itself
    _is_version_check = any(kw in dd_text_flat for kw in ("バージョン", "最新版", "インストール", "コメント"))
    if not _is_version_check and res_props and len(res_props) <= 2 and all(p['name'] in ('Success','Message') for p in res_props):
        if dd_steps:
            import json as _json
            dd_text = _json.dumps(dd_steps, ensure_ascii=False)
            if any(kw in dd_text for kw in ['比較', '確認', 'チェック', '取得', 'カウント']):
                prompt += (
                    "> **実装ガイド**: DDの比較・確認処理はすでにService層で実装済み。\n"
                    "> ViewModelは `result.Success` を確認し、`false` なら `result.Message` を表示するだけ。\n"
                    "> `result.Message` にはService層からの適切なメッセージが入っている。\n\n"
                )

    prompt += "Return ONLY the ```csharp ... ``` block with the complete ViewModel method (signature + body)."
    return prompt


def _pascal(name: str) -> str:
    if not name:
        return ""
    return name[:1].upper() + name[1:]


# ── LLM caller ────────────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_prompt: str, form_name: str = "", model=None) -> str:
    from llm.llm_client import L5LLMClient, extract_code_block
    llm = L5LLMClient()
    raw = llm.generate_code(
        task_type="viewmodel",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        agent="logic_vm",
        form_name=form_name,
    )
    code = extract_code_block(raw, "csharp")
    return code.strip() if code else raw.strip()


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_vm_agent(
    form_name: str,
    dry_run: bool = False,
    model=None,
    skip_field_inject: bool = False,
) -> dict:
    """
    Main pipeline:
    1. Load service JSON
    2. Inject service field + DI into ViewModel (if not already present)
    3. For each event: LLM gen → patch ViewModel method
    4. Save snapshot
    """
    input_file = INPUTS_DIR / f"{form_name}_service.json"
    if not input_file.exists():
        raise FileNotFoundError(
            f"Input not found: {input_file}\n"
            f"Run: python agent_logic.py {form_name} --event-class service --input-only"
        )

    # ── Auto-sync service_context from contract file ─────────────────────────
    # Try {form_name}.json first (new canonical), fallback to service_contract.json
    _svc_dir = AGENT_DIR.parent / "service" / "outputs" / form_name
    _contract_path = next((
        p for p in [_svc_dir / f"{form_name}.json", _svc_dir / "service_contract.json"]
        if p.exists()
    ), None)
    if _contract_path.exists():
        _contract_mtime = _contract_path.stat().st_mtime
        _input_mtime = input_file.stat().st_mtime
        if _contract_mtime > _input_mtime:
            logger.info(
                "[Agent VM] service_contract.json mới hơn input JSON → auto-refresh service_context..."
            )
            try:
                import asyncio as _asyncio
                from agents.logic.agent_logic import LogicAgent as _LA
                from core.models import AgentInput as _AI
                _loop = _asyncio.new_event_loop()
                _refresh = _loop.run_until_complete(
                    _LA().run(_AI(form_name=form_name, logic_event_class="all"), input_only=True)
                )
                _loop.close()
                # Reload updated input
                data = json.loads(input_file.read_text(encoding="utf-8"))
                logger.info("[Agent VM] ✅ Input JSON refreshed — service_context synced")
            except Exception as _re:
                logger.warning("[Agent VM] ⚠️  Auto-refresh failed: %s — using existing input", _re)
                data = json.loads(input_file.read_text(encoding="utf-8"))
        else:
            data = json.loads(input_file.read_text(encoding="utf-8"))
    else:
        data = json.loads(input_file.read_text(encoding="utf-8"))

    events    = data.get("events", [])
    feature   = _form_to_feature(form_name)
    # Ưu tiên đọc interface name từ service_context trong JSON (tránh naming mismatch)
    iface     = _resolve_iface_from_service_context(events, feature, form_name)
    field     = _resolve_field_from_iface(iface)
    logger.info("[Agent VM] Resolved: interface=%s | field=%s", iface, field)
    sys_prompt = load_system_prompt()

    # Resolve English view name
    from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
    _name_map = _load_form_name_map()
    _, vm_file_stem = _resolve_wpf_names(form_name, _name_map)

    # ── ViewModel file paths ──
    # Source skeleton: ui/outputs/{FormName}/ViewModels/{vm_file_stem}.cs
    ui_skeleton = UI_VIEWMODELS_DIR / form_name / "ViewModels" / f"{vm_file_stem}.cs"
    # Output: logic/outputs/{FormName}/ViewModels/{vm_file_stem}.cs
    out_dir    = OUTPUTS_DIR / form_name
    vm_out_dir = out_dir / "ViewModels"
    vm_out_dir.mkdir(parents=True, exist_ok=True)
    vm_file = vm_out_dir / f"{vm_file_stem}.cs"

    if not ui_skeleton.exists():
        raise FileNotFoundError(
            f"UI skeleton not found: {ui_skeleton}\n"
            f"Run Agent UI first: python -m agents.ui.agent_ui {form_name}"
        )

    # Copy skeleton → logic output working file (if not already patched)
    import shutil
    if not vm_file.exists() or vm_file.stat().st_mtime < ui_skeleton.stat().st_mtime:
        if not dry_run:
            shutil.copy2(ui_skeleton, vm_file)
            logger.info("[Agent VM] Copied skeleton: %s → %s", ui_skeleton.name, vm_file.relative_to(AGENT_DIR))
        else:
            logger.info("[Agent VM] [DRY-RUN] Would copy skeleton: %s → logic/outputs/%s/ViewModels/",
                        ui_skeleton.name, form_name)

    # ── Ensure required usings present ──────────────────────────────────────
    # Must be done after copy and before patching, regardless of inject_service_field
    if not dry_run and vm_file.exists():
        _content = vm_file.read_text(encoding="utf-8")
        _required = [
            "using System;",
            "using System.Linq;",
            "using System.Threading.Tasks;",
            "using System.Windows;",
            "using System.Windows.Input;",
            "using vba_brain.UI.WPF.Utils;",
            "using vba_brain.UI.WPF.Services;",
            "using vba_brain.Application.Interfaces;",
            f"using vba_brain.Application.DTOs.Requests.{form_name};",
            f"using vba_brain.Application.DTOs.Responses.{form_name};",
        ]
        _changed = False
        for _u in _required:
            if _u not in _content:
                _content = _u + "\n" + _content
                _changed = True
        if _changed:
            vm_file.write_text(_content, encoding="utf-8")
            logger.info("[Agent VM] ✅ Injected missing using directives → %s", vm_file.name)

    # ── Ensure CloseRequested event is present (stale skeleton guard) ────────
    # tool_skeleton.py now always injects this, but old skeletons may not have it.
    # Logic Agent injects it here so re-gen is not required after tool_skeleton fix.
    if not dry_run and vm_file.exists():
        _vm_content = vm_file.read_text(encoding="utf-8")

        # ── Post-copy syntax repair: fix known skeleton corruption patterns ──
        # F009-type: LLM generates Arguments = "/F /IM x.exe")", — extra )" after string
        # Strategy: replace entire Arguments value, keeping only the clean string content
        _before = _vm_content
        _vm_content = re.sub(
            r'(Arguments\s*=\s*)"([^"]*)"[^,\n]*(,)',
            r'\1"\2"\3',
            _vm_content
        )
        if _vm_content != _before:
            logger.info("[Agent VM] 🔧 Fixed corrupted Arguments string → %s", vm_file.name)

        if "event EventHandler" not in _vm_content or "CloseRequested" not in _vm_content:
            _close_event = (
                "\n    /// <summary>ウィンドウを閉じる要求イベント (DoCmd.Close相当)。</summary>\n"
                "    public event EventHandler? CloseRequested;\n"
            )
            # Inject before "// ─ Commands ──" or before first ICommand property
            _cmd_section = re.search(r'([ \t]*// ─+ Commands)', _vm_content)
            _icmd_section = re.search(r'([ \t]*public\s+ICommand\s+)', _vm_content)
            _insert_pat = _cmd_section or _icmd_section
            if _insert_pat:
                _pos = _insert_pat.start()
                _vm_content = _vm_content[:_pos] + _close_event + "\n" + _vm_content[_pos:]
                logger.info("[Agent VM] ✅ Injected CloseRequested event into skeleton → %s", vm_file.name)

        vm_file.write_text(_vm_content, encoding="utf-8")

    SEP = "─" * 62
    logger.info("")
    logger.info("┌%s", SEP)
    logger.info("│ Agent Logic VM [SERVICE]  ·  %s", form_name)
    logger.info("│ Feature: %s | Service: %s | Field: %s", feature, iface, field)
    logger.info("│ Events: %d  |  Output: logic/outputs/%s/ViewModels/%s.cs",
                len(events), form_name, vm_file_stem)
    if dry_run:
        logger.info("│ ⚠  DRY-RUN — no files written")
    logger.info("└%s", SEP)
    logger.info("")

    # ── Step 1: Inject service field + DI ──
    if not skip_field_inject:
        injected = inject_service_field(
            vm_file=vm_file,
            iface_name=iface,
            field_name=field,
            feature=feature,
            dry_run=dry_run,
            form_name=form_name,
        )
        if not injected:
            logger.warning("[Agent VM] ⚠  Service field injection failed — continuing anyway")
    else:
        logger.info("[Agent VM] Skipping service field injection (--skip-inject)")

    # ── Step 1b: Inject missing ViewModel properties from ALL bd_items & Request DTOs ──
    # Collect unique bd_items across all events so ViewModel has all needed properties
    all_bd_items: list[dict] = []
    seen_props: set[str] = set()
    for ev in events:
        for item in ev.get("bd_items", []):
            pn = item.get("physical_name", "").strip()
            if pn and pn not in seen_props:
                seen_props.add(pn)
                all_bd_items.append(item)

    # Also extract properties from Request DTOs
    source_root = LAYER5_DIR.parent.parent / "source"
    dto_file = source_root / "vba_brain.Application" / "DTOs" / "Requests" / f"{feature}ServiceRequests.cs"
    # Fallback to local service output directory if not yet deployed to source root
    if not dto_file.exists() and form_name:
        local_dto_file = AGENT_DIR.parent / "service" / "outputs" / form_name / "Application" / "DTOs" / "Requests" / f"{feature}ServiceRequests.cs"
        if local_dto_file.exists():
            dto_file = local_dto_file
    if dto_file.exists():
        try:
            dto_content = dto_file.read_text(encoding="utf-8")
            for m in re.finditer(r'public\s+([\w<>?]+)\s+(\w+)\s*\{\s*get;\s*set;\s*\}(?:\s*=\s*[^;]+;)?', dto_content):
                prop_type = m.group(1)
                prop_name = m.group(2)
                if prop_name not in seen_props:
                    seen_props.add(prop_name)
                    attr = "STRING"
                    if prop_type == "int":
                        attr = "INT"
                    elif prop_type == "bool":
                        attr = "BOOL"
                    all_bd_items.append({
                        "physical_name": prop_name,
                        "logical_name": f"Request DTO property {prop_name}",
                        "item_attribute": attr
                    })
        except Exception as e:
            logger.warning("[VMBuilder] Error scanning DTO properties: %s", e)

    if all_bd_items:
        n = inject_vm_properties(vm_file=vm_file, bd_items=all_bd_items, dry_run=dry_run)
        if n:
            logger.info("[Agent VM] ✅ Injected %d missing ViewModel properties", n)

    # ── Step 2: Process each event ──
    results = {"total": 0, "generated": 0, "patched": 0, "skipped": 0, "errors": []}
    method_outputs: list[dict] = []

    for idx, event in enumerate(events):
        meta     = event.get("event_meta", {})
        cs_stub  = event.get("cs_stub")
        event_id = meta.get("event_id", "?")
        module_id = meta.get("module_id", event_id)
        notes    = meta.get("notes", "")[:38]
        results["total"] += 1

        step = f"[{idx+1}/{len(events)}]"

        # cs_name from stub or derive from module_id
        if cs_stub:
            cs_name = cs_stub.get("cs_name", f"{module_id}Async")
            # VM async method has no suffix like _Loaded — it's just FXXXAsync()
            # Strip event suffix if present: F000_Loaded → F000Async
            # But in ViewModel the method is F000Async() not F000_Loaded
            # Detect if cs_name looks like a code-behind method (has _suffix)
            if "_" in cs_name:
                # e.g. F000_Loaded → F000
                base = cs_name.split("_")[0]
                vm_method_name = f"{base}Async"
            else:
                vm_method_name = cs_name if cs_name.endswith("Async") else f"{cs_name}Async"
        else:
            vm_method_name = f"{module_id}Async"

        logger.info("  🔄 %s %-8s  %-38s  → %s",
                    step, event_id, notes, vm_method_name)

        try:
            vba_code_event = event.get("logic_detail", {}).get("code", "")
            action_type    = meta.get("action_type", "")

            # ── Deterministic SYS patterns — skip LLM entirely ──────────────
            # Nếu VBA có pattern rõ ràng (taskkill, DoCmd.Quit) → gen thẳng,
            # không tốn token LLM và tránh LLM gen syntax error.
            deterministic_body: str | None = None

            if re.search(r'taskkill', vba_code_event, re.IGNORECASE) or (
                action_type == "SYS" and re.search(r'強制終了|taskkill|wmplayer|Media Player',
                                                    meta.get("event_content", ""), re.IGNORECASE)
            ):
                im_match = re.search(r'/IM\s+(\S+)', vba_code_event, re.IGNORECASE)
                im_arg   = im_match.group(1).strip('"\'') if im_match else "wmplayer.exe"
                deterministic_body = (
                    f"public virtual async System.Threading.Tasks.Task {vm_method_name}()\n"
                    "{\n"
                    "    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo\n"
                    "    {\n"
                    f'        FileName = "taskkill.exe",\n'
                    f'        Arguments = "/F /IM {im_arg}",\n'
                    "        CreateNoWindow = true,\n"
                    "        UseShellExecute = false\n"
                    "    });\n"
                    "    await System.Threading.Tasks.Task.CompletedTask;\n"
                    "}"
                )

            elif re.search(r'DoCmd\.Quit|acQuitPrompt', vba_code_event, re.IGNORECASE) or (
                action_type == "SYS" and re.search(r'終了|Quit|アプリケーション.*終了',
                                                    meta.get("event_content", ""), re.IGNORECASE)
            ):
                deterministic_body = (
                    f"public virtual async System.Threading.Tasks.Task {vm_method_name}()\n"
                    "{\n"
                    "    var result = MessageBox.Show(\n"
                    '        "アプリケーションを終了しますか？",\n'
                    '        "確認", MessageBoxButton.YesNo, MessageBoxImage.Question);\n'
                    "    if (result == MessageBoxResult.Yes)\n"
                    "        System.Windows.Application.Current.Shutdown();\n"
                    "    await System.Threading.Tasks.Task.CompletedTask;\n"
                    "}"
                )

            if deterministic_body is not None:
                logger.info("  ⚡ %s DETERMINISTIC (SYS pattern) → %s", step, vm_method_name)
                patched = patch_vm_method(vm_file, vm_method_name, deterministic_body, dry_run=dry_run)
                if not patched:
                    patched = inject_vm_method(vm_file, vm_method_name, deterministic_body, dry_run=dry_run)
                method_outputs.append({
                    "event_id":    event_id,
                    "notes":       meta.get("notes", ""),
                    "vm_method":   vm_method_name,
                    "is_patched":  patched,
                    "code":        deterministic_body,
                    "status":      "success",
                    "code_status": "DONE",
                    "note":        "deterministic SYS pattern",
                })
                results["generated"] += 1
                if patched:
                    results["patched"] += 1
                continue  # skip LLM for this event

            user_prompt = build_vm_prompt(event, form_name, feature, vm_method_name, iface=iface)
            generated   = call_llm(sys_prompt, user_prompt, form_name, model)
            
            # ── Post-gen correction: inject required lines that LLM may miss ──
            if generated:
                # vba_code_event đã được resolve ở trên (trước deterministic check)

                # F000-type: VBA uses WScript.Network.UserName → TxtID must be initialized
                if ("WshNetworkObject" in vba_code_event or "WScript.Network" in vba_code_event
                        or ".UserName" in vba_code_event):
                    if "System.Environment.UserName" not in generated:
                        # Inject before the request build line
                        generated = re.sub(
                            r'(var request\s*=\s*new\s+\w+Request)',
                            r'// DD 2.1: ログインユーザー名取得\n        TxtID = System.Environment.UserName;\n        \1',
                            generated, count=1
                        )
                        logger.info("[Agent VM] 🔧 Injected TxtID=UserName into %s", vm_method_name)

                # F002-type: Remove hallucinated properties not in Response DTO
                svc_ctx = event.get("service_context", {})
                if isinstance(svc_ctx, dict):
                    res_props_names = {p['name'] for p in svc_ctx.get("response", {}).get("properties", [])}
                    # Remove any result.XYZ where XYZ not in response properties
                    hallucinated = re.findall(r'result\.(\w+)', generated)
                    for prop in hallucinated:
                        if prop not in res_props_names and prop not in ("Success", "Message"):
                            logger.warning("[Agent VM] ⚠️  Removing hallucinated result.%s in %s", prop, vm_method_name)
                            # Replace usage with a comment
                            generated = re.sub(
                                r'result\.' + re.escape(prop) + r'\b',
                                f'/* result.{prop} — property not in DTO */',
                                generated
                            )
                    # Remove undefined local vars (Label400Caption etc.)
                    for undef in ("Label400Caption", "JudgeInstAsync", "LatestVersionComment", "currentVersionPart"):
                        if undef in generated:
                            logger.warning("[Agent VM] ⚠️  Removing undefined ref '%s' in %s", undef, vm_method_name)
                            # Replace the offending line with a comment
                            generated = re.sub(
                                r'[^\n]*\b' + re.escape(undef) + r'\b[^\n]*\n',
                                f'        // TODO: {undef} — 未実装\n',
                                generated
                            )

                    # ── Orphan line cleanup ──────────────────────────────────────────
                    # 上記の置換後にコロンや比較演算子だけ残った行を削除
                    # 例: "                    : "";" (ternary片側が削除されて残ったケース)
                    generated = re.sub(r'^\s*:\s*"[^"]*"\s*;?\s*$', '', generated, flags=re.MULTILINE)
                    generated = re.sub(r'^\s*:\s*string\.Empty\s*;?\s*$', '', generated, flags=re.MULTILINE)
                    # 複数の連続TODOを1行に圧縮 (同じ内容が3回以上続く場合)
                    generated = re.sub(
                        r'(        // TODO: (\w+) — 未実装\n){2,}',
                        r'        // TODO: \2 — 未実装\n',
                        generated
                    )

                    # ── Entity field hallucination correction ─────────────────────
                    # Scan `varName.XYZ` where XYZ không tồn tại trong entity shape
                    # Ví dụ: auth.IsAdmin → AuthEntity không có IsAdmin, chỉ có AdminFlag
                    res_dto_props = svc_ctx.get("response", {}).get("properties", [])
                    for dto_prop in res_dto_props:
                        shape = dto_prop.get("entity_shape")
                        if not shape:
                            continue
                        entity_cls   = shape["class"]
                        valid_fields = {f["name"] for f in shape["fields"]}
                        # Tìm biến local chứa entity này: var auth = response.AuthEntity?.FirstOrDefault()
                        var_pat = re.compile(
                            r'\bvar\s+(\w+)\s*=\s*\w+\.' + re.escape(dto_prop["name"]) + r'\b'
                        )
                        for vm in var_pat.finditer(generated):
                            var_name = vm.group(1)
                            # Tìm tất cả var_name.XYZ trong generated
                            access_pat = re.compile(r'\b' + re.escape(var_name) + r'\.(\w+)\b')
                            for am in access_pat.finditer(generated):
                                field_used = am.group(1)
                                if field_used not in valid_fields and field_used not in ("Invoke", "ToString", "GetType"):
                                    logger.warning(
                                        "[Agent VM] ⚠️  Hallucinated entity field %s.%s in %s — valid: %s",
                                        entity_cls, field_used, vm_method_name, sorted(valid_fields),
                                    )
                                    # Replace offending field access with a TODO comment on that line
                                    generated = re.sub(
                                        r'[^\n]*\b' + re.escape(var_name) + r'\.' + re.escape(field_used) + r'\b[^\n]*\n',
                                        f'        // TODO: {entity_cls}.{field_used} は存在しない — 正しいフィールド: {", ".join(sorted(valid_fields))}\n',
                                        generated,
                                    )
            
            # Post-process: Correct casing of ViewModel properties in generated method body
            if seen_props and generated:
                pascal_props = {p[:1].upper() + p[1:] for p in seen_props if p}
                for prop in pascal_props:
                    pattern = r'\b' + re.escape(prop) + r'\b'
                    def repl(m, p=prop):
                        return p if m.group(0) != p else m.group(0)
                    generated = re.sub(pattern, repl, generated, flags=re.IGNORECASE)
            
            results["generated"] += 1

            code_status, code_note = _classify_code_status(generated)

            patched = False
            patched = patch_vm_method(vm_file, vm_method_name, generated, dry_run=dry_run)
            if not patched:
                patched = inject_vm_method(vm_file, vm_method_name, generated, dry_run=dry_run)
            if patched:
                results["patched"] += 1
            else:
                code_status = "ERROR"
                code_note   = f"patch failed — method {vm_method_name} not found in ViewModel"

            icon = "✅" if code_status == "DONE" else ("⚠️ " if code_status == "TODO" else "❌")
            extra = f"  [{code_note}]" if code_note else ""
            logger.info("     %s %s  %s%s", icon, code_status, vm_method_name, extra)

            method_outputs.append({
                "event_id":   event_id,
                "notes":      meta.get("notes", ""),
                "vm_method":  vm_method_name,
                "is_patched": patched,
                "code":       generated,
                "status":     "success",
                "code_status": code_status,
                "note":       code_note,
            })

        except Exception as exc:
            logger.error("     ❌ ERROR: %s", exc)
            results["errors"].append({"event_id": event_id, "error": str(exc)})
            method_outputs.append({
                "event_id": event_id, "notes": meta.get("notes", ""),
                "vm_method": vm_method_name, "code": f"// Error: {exc}",
                "status": "error", "code_status": "ERROR", "note": str(exc)[:80],
            })

    # ── Summary table ──
    logger.info("")
    logger.info("┌─────────────────────────────────────────────────────────────")
    logger.info("│ RESULTS — %s ViewModel Methods", form_name)
    logger.info("├──────────┬────────────────────────────┬────────────┬────────")
    logger.info("│ EventID  │ VBA Handler                │ VM Method  │ Status")
    logger.info("├──────────┼────────────────────────────┼────────────┼────────")

    done_n = todo_n = skip_n = err_n = 0
    for m in method_outputs:
        st   = m.get("code_status", "?")
        icon = {"DONE": "✅", "TODO": "⚠️ ", "EMPTY": "⚠️ ", "SKIP": "⏭ ", "ERROR": "❌"}.get(st, " ?")
        note = m.get("note", "")[:20]
        vm   = (m.get("vm_method") or "—")[:14]
        handler = m.get("notes", "")[:28]
        logger.info("│ %-8s │ %-28s │ %-14s │ %s %-5s %s",
                    m["event_id"], handler, vm, icon, st, note)
        if   st == "DONE":  done_n += 1
        elif st in ("TODO", "EMPTY"): todo_n += 1
        elif st == "SKIP":  skip_n += 1
        elif st == "ERROR": err_n  += 1

    logger.info("├──────────┴────────────────────────────┴────────────┴────────")
    logger.info("│  ✅ DONE: %-3d  ⚠️  TODO: %-3d  ❌ ERR: %d",
                done_n, todo_n, err_n)
    compile_ok = (todo_n + err_n) == 0
    if compile_ok and done_n > 0:
        logger.info("│  🟢 All ViewModel methods implemented — ready to compile")
    elif todo_n > 0:
        logger.info("│  🟡 %d method(s) have stub body — review before build", todo_n)
    if err_n > 0:
        logger.info("│  🔴 %d error(s) — check above logs", err_n)
    logger.info("└─────────────────────────────────────────────────────────────")
    logger.info("")

    # Save snapshot
    snapshot_name = "vm_methods_output.json"
    (out_dir / snapshot_name).write_text(
        json.dumps({
            "form_name": form_name,
            "feature":   feature,
            "service":   iface,
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
    logger.info("📦 Snapshot saved: %s/%s", form_name, snapshot_name)

    if not dry_run and results["patched"] > 0:
        logger.info("📝 Updated: %s", vm_file.name)

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Agent Logic VM — Gen ViewModel async method bodies từ _service.json, patch vào ViewModels/*.cs"
    )
    parser.add_argument("form_name",        nargs="?", help="Form name, e.g. F_Login")
    parser.add_argument("--all",            action="store_true", help="Process all forms")
    parser.add_argument("--dry-run",        action="store_true", help="Preview only, no write")
    parser.add_argument("--model",          help="Override LLM model")
    parser.add_argument("--skip-inject",    action="store_true",
                        help="Skip injecting service field/DI into ViewModel")
    args = parser.parse_args()

    if not args.all and not args.form_name:
        parser.error("Need form_name or --all")

    from core.config import AVAILABLE_MODELS
    model = AVAILABLE_MODELS.get(args.model) if args.model else None

    forms = (
        sorted(p.stem.replace("_service", "") for p in INPUTS_DIR.glob("*_service.json"))
        if args.all else [args.form_name]
    )
    if args.all:
        logger.info("[Agent VM] Found %d forms", len(forms))

    for form in forms:
        try:
            run_vm_agent(
                form_name=form,
                dry_run=args.dry_run,
                model=model,
                skip_field_inject=args.skip_inject,
            )
        except FileNotFoundError as exc:
            logger.error("❌ %s: %s", form, exc)
        except Exception as exc:
            logger.error("❌ %s failed: %s", form, exc, exc_info=True)


if __name__ == "__main__":
    main()
