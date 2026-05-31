"""
agents/service/tool_service_gen.py — Deterministic code generator for Agent Service.

Generates ``{Feature}Service.cs`` (Application Service implementation) from the
unified service-input produced by ``agent_service.py`` (``build_service_input``). No LLM calls —
pure string templating, mirroring the style of ``agents/repo/tool_repo.py``.

Output rules (per generated method):

1.  Method signature derived from event_trigger (e.g. 更新後処理 → ``SubmitAsync``,
    with a special case ``AuthenticateAsync`` for F_Login).
2.  DD ``steps[].detail`` is emitted as ``// {module_id} step ...`` comments,
    preserving the original Japanese for traceability.
3.  Each ``query_mappings`` entry is resolved against
    ``repository_contracts.repositories[*].function[*]`` using
    ``sheet_query_name`` first, then ``query_name`` as fallback. A matching
    repo function becomes::

        var <varName> = await _<field>.<FunctionName>(<args>);

    Input arguments are pulled from the ``parameters[].mapping`` field (the
    part after ``.`` is treated as the source DTO property).
4.  Repositories actually called are auto-injected via constructor DI; unused
    repositories from the contract are NOT injected (avoid dead deps).
5.  When the event has no resolvable mapping but VBA shows a data-access op
    (``DLookup``/``DCount``/...), a ``// TODO`` comment is inserted with the
    matched VBA handler name so the developer can wire repo calls manually.
6.  Every method body is wrapped in ``try/catch`` returning a ``Success=false``
    response on exception.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Name helpers
# ──────────────────────────────────────────────
def _form_to_feature(form_name: str) -> str:
    """Resolve feature name via listFormJpToEn.json / listReportJpToEn.json if possible."""
    try:
        import json
        from pathlib import Path
        agent_dir = Path(__file__).parent
        gv_out = agent_dir.parent / "graphview" / "outputs"

        # Check both forms and reports mapping files
        for mapping_file in [
            gv_out / "forms" / "listFormJpToEn.json",
            gv_out / "reports" / "listReportJpToEn.json",
        ]:
            if not mapping_file.exists():
                continue
            data = json.loads(mapping_file.read_text(encoding="utf-8"))
            for item in data.get("items", []):
                if item.get("access_form_name") == form_name:
                    # Use wpf_viewmodel_name strip 'ViewModel' → cleanest EN feature name
                    vm = item.get("wpf_viewmodel_name", "")
                    if vm and vm.endswith("ViewModel"):
                        return vm[:-9]   # e.g. "R005WorkRequestViewModel" → "R005WorkRequest"
                    view = item.get("wpf_view_name", "")
                    if view and view.endswith("View"):
                        return view[:-4]
    except Exception:
        pass

    name = form_name or ""
    if name.startswith("F_"):
        name = name[2:]
    return re.sub(r"[^\w]", "", name) or "Default"


def _to_field(repo_name: str) -> str:
    """``IAuthRepository``/``AuthRepository`` → ``authRepository``."""
    if not repo_name:
        return "repository"
    name = repo_name[1:] if repo_name.startswith("I") else repo_name
    return name[:1].lower() + name[1:]


def _to_var(fn_name: str) -> str:
    """``GetUserInfoAsync`` → ``userInfo``."""
    name = fn_name or "result"
    for prefix in ("Get", "Find", "Load", "Fetch", "Select", "Read", "Query"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    if name.endswith("Async"):
        name = name[: -len("Async")]
    if not name:
        name = "result"
    return name[:1].lower() + name[1:]


def _is_label_control(ctrl_name: str) -> bool:
    """Return True when the control name looks like a UI label (not an input field).

    Patterns excluded:
      - Japanese label controls: ラベル<digits>  (e.g. ラベル400)
      - English-style label prefixes: lbl*, label*
    """
    name_lower = ctrl_name.lower()
    if name_lower.startswith(("lbl", "label")):
        return True
    if ctrl_name.startswith("ラベル"):
        return True
    return False


def _pascal(token: str) -> str:
    token = (token or "").strip()
    if not token:
        return ""
    return token[:1].upper() + token[1:]


# ── name_config JP→EN field lookup ───────────────────────────────────────────
_NAME_CONFIG_PATH = Path(__file__).parent.parent / "repo" / "config" / "name_config.json"

def _load_field_map() -> dict[str, str]:
    """Load field_name mapping from repo name_config.json (JP → EN)."""
    if _NAME_CONFIG_PATH.exists():
        try:
            import json as _j
            return _j.loads(_NAME_CONFIG_PATH.read_text(encoding="utf-8")).get("field_name", {})
        except Exception:
            pass
    return {}

_FIELD_MAP: dict[str, str] = _load_field_map()


def _to_en_prop(ctrl: str) -> str:
    """
    Translate a JP control/field/parameter name to a PascalCase C# property name.

    Priority:
      1. Already ASCII → _pascal(ctrl)
      2. In name_config field_name map → _pascal(EN value)
      3. In name_config parameter_name map → _pascal(EN value)
      4. Fallback → "TODO"  (downstream knows to fill in)
    """
    ctrl = (ctrl or "").strip()
    if not ctrl:
        return "TODO"
    if ctrl.isascii():
        return _pascal(ctrl)
    # Try field_name
    en = _FIELD_MAP.get(ctrl, "")
    if en and en not in ("TODO", "") and not en.startswith("TODO"):
        return _pascal(en)
    # Try parameter_name
    if _NAME_CONFIG_PATH.exists():
        try:
            import json as _j
            _param_map = _j.loads(_NAME_CONFIG_PATH.read_text(encoding="utf-8")).get("parameter_name", {})
            en2 = _param_map.get(ctrl, "")
            if en2 and en2 not in ("TODO", "") and not en2.startswith("TODO"):
                return _pascal(en2)
        except Exception:
            pass
    return "TODO"


# DD trigger → method name (mirrors agent_service.ServiceAgent._derive_form_method_name)
_TRIGGER_TO_METHOD: dict[str, str] = {
    "画面を開く時": "GetInitialDataAsync",
    "フォーム読み込み後": "OnLoadAsync",
    "フォーム読み込み時": "OnLoadAsync",
    "更新後処理": "SubmitAsync",
    "更新前処理": "OnBeforeUpdateAsync",
    "クリック時": "OnClickAsync",
    "ダブルクリック時": "OnDoubleClickAsync",
    "キー押下時": "OnKeyDownAsync",
    "キー離した時": "OnKeyUpAsync",
    "フォーカス取得時": "OnGotFocusAsync",
    "フォーカス喪失時": "OnLostFocusAsync",
    "タイマー時": "OnTimerAsync",
}


def _load_response_field_mapping() -> dict:
    """Load response field mapping config from configs/response_field_mapping.json."""
    config_path = Path(__file__).parent / "configs" / "response_field_mapping.json"
    if config_path.exists():
        try:
            import json as _json
            with open(config_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
                return {
                    "function_name_map": data.get("function_name_map", {}),
                    "column_name_map": data.get("column_name_map", {}),
                }
        except Exception as e:
            logger.warning("Failed to load response_field_mapping.json: %s", e)
    return {"function_name_map": {}, "column_name_map": {}}


def _load_method_names() -> dict:
    config_path = Path(__file__).parent / "configs" / "method_names.json"
    if config_path.exists():
        try:
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load method_names.json: %s", e)
    return {}


def derive_method_name(event: dict, feature: str, form_name: str = "") -> str:
    trigger = (event.get("event_trigger") or "").strip()
    module_id = (event.get("module_id") or "").strip()

    if form_name:
        registry = _load_method_names()
        custom_name = registry.get(form_name, {}).get(module_id, {}).get("method_name")
        if custom_name:
            return custom_name

    if trigger == "更新後処理" and feature.lower() == "login":
        return "AuthenticateAsync"
    if trigger in _TRIGGER_TO_METHOD:
        return _TRIGGER_TO_METHOD[trigger]
    return f"On{module_id}Async" if module_id else "ExecuteAsync"



# ──────────────────────────────────────────────
# Repository index
# ──────────────────────────────────────────────
def build_repo_index(
    repository_contracts: dict,
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Build two lookups: ``by_query_name`` and ``by_sheet_query_name``.

    Returns ``(by_query_name, by_sheet_query_name)``. Callers should prefer
    the logical ``query_name`` over the sheet identifier — sheet numbers in
    DD vs. Agent Repo output are not always aligned.
    """
    by_query: dict[str, dict] = {}
    by_sheet: dict[str, dict] = {}
    for repo in (repository_contracts or {}).get("repositories", []) or []:
        repo_name = repo.get("repository_name") or ""
        table_name = repo.get("table_name") or ""
        for fn in repo.get("function") or []:
            info = {
                "repo_name": repo_name,
                "table_name": table_name,
                "function_name": fn.get("function_name") or "",
                "input": fn.get("input") or [],
                "output": fn.get("output") or [],
                "description": fn.get("description") or "",
            }
            qn = (fn.get("query_name") or "").strip()
            sn = (fn.get("sheet_query_name") or "").strip()
            if qn and qn not in by_query:
                by_query[qn] = info
            if sn and sn not in by_sheet:
                by_sheet[sn] = info
    return by_query, by_sheet


def resolve_repo_for_mapping(
    qm: dict,
    by_query: dict[str, dict],
    by_sheet: dict[str, dict],
) -> dict | None:
    """Find the repo function for one ``query_mappings`` entry.

    Priority: ``logic_query_name`` (stable business identifier) first, then
    ``sheet_name`` (numbered slot — may be reassigned between agents).
    """
    logic = (qm.get("logic_query_name") or "").strip()
    if logic and logic in by_query:
        return by_query[logic]
    sheet = (qm.get("sheet_name") or "").strip()
    if sheet and sheet in by_sheet:
        return by_sheet[sheet]
    return None


# ──────────────────────────────────────────────
# Argument formatting
# ──────────────────────────────────────────────
def format_input_args(qm_params: list[dict]) -> tuple[str, list[str]]:
    """Convert ``query_mappings.parameters[]`` to a positional C# argument list.

    Returns ``(args_str, notes)`` where ``notes`` is a list of human-readable
    notes about how each parameter was mapped.

    UI label controls (ラベル*, lbl*, label*) are automatically excluded because
    they hold display text, not query parameters.
    """
    args: list[str] = []
    notes: list[str] = []
    for p in qm_params or []:
        if (p.get("io") or "I").upper() != "I":
            continue
        mapping = (p.get("mapping") or "").strip()
        # Mapping looks like "＜パラメータ＞.txtID" — take the segment after the last dot.
        ctrl = mapping.rsplit(".", 1)[-1] if "." in mapping else (p.get("name") or "")
        ctrl = ctrl.strip()
        if not ctrl:
            args.append("/* TODO: missing param */ default!")
            notes.append("missing parameter mapping")
            continue
        # Skip UI label controls — they should not be passed as repo arguments
        if _is_label_control(ctrl):
            notes.append(f"skipped UI label control: {ctrl}")
            continue
        prop = _to_en_prop(ctrl)
        args.append(f"request.{prop}")
        notes.append(f"{ctrl} → request.{prop}")
    return ", ".join(args), notes


# ──────────────────────────────────────────────
# Per-event code generation
# ──────────────────────────────────────────────
def _emit_step_comments(event: dict, indent: str) -> list[str]:
    """Emit DD ``steps[]`` as inline ``//`` comments."""
    out: list[str] = []
    module_id = event.get("module_id", "")
    for step in event.get("steps") or []:
        step_title = (step.get("step") or "").strip()
        detail = (step.get("detail") or "").strip()
        if not detail or detail == "なし":
            continue
        out.append(f"{indent}// {module_id} {step_title}")
        for line in detail.split("\n"):
            line = line.strip()
            if line:
                out.append(f"{indent}// {line}")
        out.append("")
    return out


def _vba_has_op(vba_code: str, ops: tuple[str, ...]) -> bool:
    if not vba_code:
        return False
    return any(op.lower() in vba_code.lower() for op in ops)


def _safe_class_token(module_id: str, feature: str) -> str:
    """Return a valid C# class name prefix for Request/Response.

    If module_id is a JP name (not ASCII-safe), fall back to feature.
    This ensures we get 'F000Request' or 'R005WorkRequestRequest' instead
    of 'R005_作業依頼書Request'.
    """
    mid = (module_id or "").strip()
    if mid and mid.isascii() and mid.replace("_", "").isalnum():
        return mid
    # JP or contains special chars → use feature (already EN PascalCase)
    return feature or "Default"


def generate_method(
    event: dict,
    feature: str,
    by_query: dict[str, dict],
    by_sheet: dict[str, dict],
    form_name: str = "",
    include_comments: bool = False,
) -> tuple[str, list[dict]]:
    """Return ``(method_source_block, used_repo_infos)`` for one event."""
    method_name = derive_method_name(event, feature, form_name)
    module_id = event.get("module_id", "")
    _cls = _safe_class_token(module_id, feature)
    request_type = f"{_cls}Request" if _cls else f"{feature}Request"
    response_type = f"{_cls}Response" if _cls else f"{feature}Response"

    trigger = event.get("event_trigger", "")
    summary_full = (event.get("event_content") or "").replace("\r\n", " ").replace("\n", " ").strip()
    summary = summary_full[:200]

    # Indents: method body = 8 spaces, try-block body = 12 spaces.
    BODY = "            "  # 12

    lines: list[str] = []
    lines.append(f"    /// <summary>")
    lines.append(f"    /// {module_id} {trigger} — {summary}")
    lines.append(f"    /// </summary>")
    lines.append(f"    public async Task<{response_type}> {method_name}({request_type} request)")
    lines.append(f"    {{")
    lines.append(f"        try")
    lines.append(f"        {{")

    # DD steps as Japanese comments — chỉ emit khi include_comments=True
    if include_comments:
        lines.extend(_emit_step_comments(event, BODY))

    # Repo calls
    used_repos: list[dict] = []
    var_counts: dict[str, int] = {}
    repo_vars: list[tuple[str, dict]] = []  # (var_name, info) — used for post-call logic

    for qm in event.get("query_mappings") or []:
        info = resolve_repo_for_mapping(qm, by_query, by_sheet)
        sheet = qm.get("sheet_name", "")
        logic = qm.get("logic_query_name", "")
        if not info:
            lines.append(
                f"{BODY}// TODO: Repository function not found for query "
                f"'{logic}' (sheet {sheet}). Add the mapping in Agent Repo output."
            )
            lines.append("")
            continue

        used_repos.append(info)
        base_var = _to_var(info["function_name"])
        var_counts[base_var] = var_counts.get(base_var, 0) + 1
        var = base_var if var_counts[base_var] == 1 else f"{base_var}{var_counts[base_var]}"

        field = _to_field(info["repo_name"])
        repo_inputs = info.get("input") or []
        if not repo_inputs:
            args = ""
            notes = []
        else:
            args, notes = format_input_args(qm.get("parameters") or [])
        if notes:
            lines.append(f"{BODY}// Args: {'; '.join(notes)}")
        lines.append(
            f"{BODY}// {module_id} → {info['repo_name']}.{info['function_name']} "
            f"(query: {logic})"
        )
        lines.append(
            f"{BODY}var {var} = await _{field}.{info['function_name']}({args});"
        )
        lines.append("")
        repo_vars.append((var, info))

    # VBA hints when no query_mappings but VBA shows data-access
    matched = event.get("matched_vba") or {}
    vba_code = matched.get("code") or ""
    if not (event.get("query_mappings") or []) and vba_code:
        if _vba_has_op(vba_code, ("DLookup", "DCount", "DSum")):
            lines.append(
                f"{BODY}// TODO: VBA handler '{matched.get('handler', '')}' uses "
                f"DLookup/DCount but DD has no query_mappings entry. Add a query "
                f"mapping in DD or wire the repository call manually."
            )
            lines.append("")

    if matched.get("handler"):
        lines.append(
            f"{BODY}// VBA reference: {matched['handler']} "
            f"({matched.get('type', 'Sub')}) — see original Access form for "
            f"business rules."
        )
        lines.append("")

    # ── Post-call business logic derived from DD steps ────────────────────
    # Scan DD steps for known patterns and gen real logic instead of TODO.
    post_logic = _derive_post_call_logic(event, repo_vars, response_type, BODY)
    if post_logic:
        lines.extend(post_logic)
    else:
        lines.append(f"{BODY}return new {response_type} {{ Success = true }};")

    lines.append(f"        }}")
    lines.append(f"        catch (System.Exception ex)")
    lines.append(f"        {{")
    lines.append(f"{BODY}return new {response_type} {{ Success = false, Message = ex.Message }};")
    lines.append(f"        }}")
    lines.append(f"    }}")
    return "\n".join(lines), used_repos


def _derive_post_call_logic(
    event: dict,
    repo_vars: list[tuple[str, dict]],
    response_type: str,
    indent: str,
) -> list[str]:
    """
    Derive post-repo-call business logic từ DD steps thay vì return Success=true cứng.

    Patterns được xử lý:
      1. Version comparison (F002-type): DD steps có "比較" / "バージョン" / "最新版"
         → so sánh kết quả query với giá trị request, trả Message nếu lệch.
      2. Authentication (F003-type): DD steps có "認証" / "管理者" / "パスワード"
         → trả AuthEntity + T022PrefectureEntity đã query.
      3. Count check (DCount-type): DD steps có "カウント" / "レコード数"
         → trả Count hoặc kiểm tra rỗng.
      4. Data retrieval (default): trả data từ repo query vào Response.Data.

    Nếu không match pattern nào → return [] → caller dùng Success=true fallback.
    """
    if not repo_vars:
        return []

    # Lấy DD steps text để phân tích pattern
    dd_text = ""
    for step in event.get("steps") or []:
        dd_text += (step.get("detail") or "") + " " + (step.get("step") or "")
    vba_code = (event.get("matched_vba") or {}).get("code") or ""

    lines: list[str] = []

    # ── Pattern 1: Version comparison ──────────────────────────────────────
    # DD: "バージョン比較" / "最新版ではありません" / "インストール"
    # Chỉ apply khi DD có "最新版" hoặc "インストール" (Access app version),
    # KHÔNG apply khi chỉ có "バージョン情報" (Access version number check như F008)
    is_version_check = any(kw in dd_text for kw in (
        "最新版", "インストール", "コメント"
    )) and not any(kw in dd_text for kw in ("メニューバー", "リボン", "ステータスバー"))
    if is_version_check and len(repo_vars) == 1:
        var, info = repo_vars[0]
        # Detect output type: IEnumerable<string> vs IEnumerable<BuildingAfterCollectionEntity>
        outputs = info.get("output") or []
        first_out = outputs[0] if outputs else {}
        out_kind = (first_out.get("type") or "").lower()
        out_name = (first_out.get("name") or "").strip()

        lines.append(f"{indent}// DD 2.2: DBから最新バージョン情報を取得")
        if out_kind in ("string", "scalar", "") and not out_name:
            # IEnumerable<string> → FirstOrDefault() gives string directly
            lines.append(f"{indent}var latestComment = {var}?.FirstOrDefault() ?? string.Empty;")
            lines.append(f"{indent}// DD 2.3-2.4: バージョン不一致の場合はVersionCommentで通知 (ViewModelが比較)")
            lines.append(f"{indent}return new {response_type} {{")
            lines.append(f"{indent}    Success = true,")
            lines.append(f"{indent}    VersionComment = latestComment,")
            lines.append(f"{indent}}};")
        else:
            # Entity/DTO → return Data collection directly; ViewModel extracts the field it needs
            lines.append(f"{indent}// DD 2.3-2.4: バージョン不一致の場合はViewModelが比較")
            lines.append(f"{indent}return new {response_type} {{")
            lines.append(f"{indent}    Success = true,")
            lines.append(f"{indent}    Data = {var},")
            lines.append(f"{indent}}};")
        return lines

    # ── Pattern 2: Auth / password check ───────────────────────────────────
    # DD: "認証" / "管理者フラグ" / "パスワード一致"
    is_auth = any(kw in dd_text for kw in (
        "認証", "管理者", "パスワード", "ログイン", "ID"
    )) or "AuthenticateAsync" in response_type.replace("Response", "")
    if is_auth:
        # Collect vars by function name pattern
        auth_var = next(
            (v for v, info in repo_vars
             if any(t in (info.get("function_name") or "") for t in ("IdPass", "Auth", "Login"))),
            None
        )
        user_info_var = next(
            (v for v, info in repo_vars
             if any(t in (info.get("function_name") or "") for t in ("UserInfo", "GetUser", "User"))),
            None
        )
        pref_var = next(
            (v for v, info in repo_vars
             if any(t in (info.get("function_name") or "") for t in ("Region", "Prefecture", "T022"))),
            None
        )

        # F000-type: GetUserInfoAsync → Data property (GetUserInfoDto, not AuthEntity)
        if user_info_var and not auth_var:
            lines.append(f"{indent}// DD 2.3: ユーザー情報をResponseに設定")
            lines.append(f"{indent}return new {response_type} {{")
            lines.append(f"{indent}    Success = true,")
            lines.append(f"{indent}    Data = {user_info_var},")
            lines.append(f"{indent}}};")
            return lines

        # F003-type: IdPassAsync + GetRegionCdAsync → AuthEntity + T022PrefectureEntity
        if auth_var:
            lines.append(f"{indent}// DD 2.3: 認証データをResponseに設定")
            lines.append(f"{indent}return new {response_type} {{")
            lines.append(f"{indent}    Success = true,")
            lines.append(f"{indent}    AuthEntity = {auth_var},")
            if pref_var:
                lines.append(f"{indent}    T022PrefectureEntity = {pref_var},")
            lines.append(f"{indent}}};")
            return lines

    # ── Pattern 3: Count / record check ────────────────────────────────────
    is_count = any(kw in dd_text for kw in ("カウント", "レコード数", "件数"))
    if is_count and len(repo_vars) == 1:
        var, info = repo_vars[0]
        lines.append(f"{indent}// DD 2.3: レコード数チェック結果を返す")
        lines.append(f"{indent}return new {response_type} {{")
        lines.append(f"{indent}    Success = true,")
        lines.append(f"{indent}    Data = {var},")
        lines.append(f"{indent}}};")
        return lines

    # ── Pattern 4: General data retrieval ──────────────────────────────────
    # 1つのrepo varがある場合 → Data propertyに設定
    if len(repo_vars) == 1:
        var, info = repo_vars[0]
        # Check if output type is a named type (entity/dto) not scalar
        outputs = info.get("output") or []
        has_named_output = any(
            (o.get("type") or "").lower() in ("dto", "entity")
            for o in outputs
        )
        if has_named_output:
            lines.append(f"{indent}return new {response_type} {{")
            lines.append(f"{indent}    Success = true,")
            lines.append(f"{indent}    Data = {var},")
            lines.append(f"{indent}}};")
            return lines

    # ── Fallback: multiple repos or no named output ─────────────────────────
    # Build response with all named-output vars
    named_pairs: list[tuple[str, str]] = []
    for var, info in repo_vars:
        outputs = info.get("output") or []
        for o in outputs:
            kind = (o.get("type") or "").lower()
            name = (o.get("name") or "").strip()
            if kind in ("dto", "entity") and name:
                named_pairs.append((var, name))
                break

    if named_pairs:
        lines.append(f"{indent}return new {response_type} {{")
        lines.append(f"{indent}    Success = true,")
        for var, type_name in named_pairs:
            lines.append(f"{indent}    {type_name} = {var},")
        lines.append(f"{indent}}};")
        return lines

    return []  # no pattern matched → caller uses Success=true fallback


# ──────────────────────────────────────────────
# Class assembly
# ──────────────────────────────────────────────
def _dedupe_repos(repos: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in repos:
        key = r.get("repo_name") or ""
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def generate_service_impl(service_input: dict, include_comments: bool = False) -> str:
    """Generate ``{Feature}Service.cs`` source from the unified service input."""
    form_name = service_input.get("form_name", "")
    events = service_input.get("events") or []
    contracts = service_input.get("repository_contracts") or {}

    feature = _form_to_feature(form_name)
    service_name = f"{feature}Service"
    iface_name = f"I{service_name}"

    by_query, by_sheet = build_repo_index(contracts)

    method_blocks: list[str] = []
    all_used: list[dict] = []
    for event in events:
        block, used = generate_method(
            event=event,
            feature=feature,
            by_query=by_query,
            by_sheet=by_sheet,
            form_name=form_name,
            include_comments=include_comments
        )
        method_blocks.append(block)
        all_used.extend(used)

    repos = _dedupe_repos(all_used)

    lines: list[str] = []
    lines.append("namespace vba_brain.Application.Services;")
    lines.append("")
    lines.append("using System;")
    lines.append("using System.Threading.Tasks;")
    lines.append("using vba_brain.Application.DTOs;")
    lines.append(f"using vba_brain.Application.DTOs.Requests.{form_name};")
    lines.append(f"using vba_brain.Application.DTOs.Responses.{form_name};")
    lines.append("using vba_brain.Application.Interfaces;")
    lines.append("using vba_brain.Domain.Entities;")
    lines.append("using vba_brain.Domain.Interfaces;")
    lines.append("")
    lines.append(f"/// <summary>")
    lines.append(f"/// Application service for {form_name}. Auto-generated by tool_service_gen.")
    lines.append(f"/// </summary>")
    lines.append(f"public class {service_name} : {iface_name}")
    lines.append("{")

    # Fields
    for r in repos:
        field = _to_field(r["repo_name"])
        lines.append(f"    private readonly I{r['repo_name']} _{field};")
    if repos:
        lines.append("")

    # Constructor
    if repos:
        lines.append(f"    public {service_name}(")
        for i, r in enumerate(repos):
            field = _to_field(r["repo_name"])
            sep = "," if i < len(repos) - 1 else ""
            lines.append(f"        I{r['repo_name']} {field}{sep}")
        lines.append("    )")
        lines.append("    {")
        for r in repos:
            field = _to_field(r["repo_name"])
            lines.append(f"        _{field} = {field};")
        lines.append("    }")
    else:
        lines.append(f"    public {service_name}() {{ }}")
    lines.append("")

    # Methods
    for block in method_blocks:
        lines.append(block)
        lines.append("")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def generate_service_iface_methods(service_input: dict) -> list[dict]:
    """Return method specs for the IService interface (used by Jinja2 renderer).

    Kept in this module so callers don't need to duplicate naming logic.
    """
    form_name = service_input.get("form_name", "")
    feature = _form_to_feature(form_name)
    events = service_input.get("events") or []

    methods: list[dict] = []
    for ev in events:
        method_name = derive_method_name(ev, feature, form_name)
        module_id = ev.get("module_id", "")
        _cls2 = _safe_class_token(module_id, feature)
        request_type = f"{_cls2}Request" if _cls2 else f"{feature}Request"
        response_type = f"{_cls2}Response" if _cls2 else f"{feature}Response"
        event_content = (ev.get("event_content") or "").splitlines()
        short = event_content[0][:120] if event_content else ""
        methods.append({
            "name": method_name,
            "return_type": f"Task<{response_type}>",
            "params": f"{request_type} request",
            "comment": (
                f"{ev.get('module_id', '')} {ev.get('event_trigger', '')} — {short}"
            ),
        })
    return methods


def generate_service_dtos(service_input: dict) -> tuple[str, str]:
    """Generate Request and Response C# code for DTOs.
    
    Returns (requests_code, responses_code).
    """
    form_name = service_input.get("form_name", "")
    feature = _form_to_feature(form_name)
    events = service_input.get("events") or []
    contracts = service_input.get("repository_contracts") or {}
    by_query, by_sheet = build_repo_index(contracts)

    # ── Collect all output type names used in Responses so we can emit correct usings ──
    # We defer header generation until after we know what types are referenced.
    # key: type_name → "dto" | "entity" | "scalar"
    used_output_types: dict[str, str] = {}

    req_lines: list[str] = []
    req_lines.append("using System.Collections.Generic;")
    req_lines.append("")
    req_lines.append(f"namespace vba_brain.Application.DTOs.Requests.{form_name}")
    req_lines.append("{")
    req_lines.append(f"    // Auto-generated by tool_service_gen for {form_name}.")
    req_lines.append(f"    // Do not edit manually.")

    # Responses body built separately; usings injected later
    res_body_lines: list[str] = []
    res_body_lines.append("")
    res_body_lines.append(f"namespace vba_brain.Application.DTOs.Responses.{form_name}")
    res_body_lines.append("{")
    res_body_lines.append(f"    // Auto-generated by tool_service_gen for {form_name}.")
    res_body_lines.append(f"    // Do not edit manually.")

    for event in events:
        module_id = event.get("module_id", "")
        if not module_id:
            continue
        trigger = event.get("event_trigger", "")
        # Use safe EN class prefix — fall back to feature when module_id is JP
        _cls_pfx = _safe_class_token(module_id, feature)

        # ── Request Class ──
        req_lines.append("")
        req_lines.append(f"    /// <summary>{module_id} {trigger} — Request DTO</summary>")
        req_lines.append(f"    public class {_cls_pfx}Request")
        req_lines.append("    {")
        
        # Collect parameters — only include props that the repo function actually accepts
        # as input (cross-checked against repository_contracts).  If the matched repo
        # function has input: [] the request stays empty, meaning no parameters should
        # be forwarded.  Also skip UI-label controls (ラベル*, lbl*, label*).
        params_seen = set()
        for qm in event.get("query_mappings") or []:
            repo_info = resolve_repo_for_mapping(qm, by_query, by_sheet)
            # repo_input_count is None when repo function was NOT found (unresolved mapping)
            # → trust DD params in that case.
            # repo_input_count == 0 means the repo function EXPLICITLY takes no args
            # (e.g. GetCommentAsync queries by a fixed ID) → skip params.
            repo_input_count = len(repo_info.get("input") or []) if repo_info else None

            for p in qm.get("parameters") or []:
                if (p.get("io") or "I").upper() != "I":
                    continue
                mapping = (p.get("mapping") or "").strip()
                ctrl = mapping.rsplit(".", 1)[-1] if "." in mapping else (p.get("name") or "")
                ctrl = ctrl.strip()
                if not ctrl:
                    continue
                if _is_label_control(ctrl):
                    continue
                prop = _to_en_prop(ctrl)
                if prop not in params_seen:
                    params_seen.add(prop)
                    # If fallback TODO, add comment with original JP name
                    comment = f"  // TODO: translate '{ctrl}'" if prop == "TODO" else ""
                    req_lines.append(f"        public string {prop} {{ get; set; }} = default!;{comment}")
        
        req_lines.append("    }")

        # ── Response Class ──
        res_body_lines.append("")
        res_body_lines.append(f"    /// <summary>{module_id} {trigger} — Response DTO</summary>")
        res_body_lines.append(f"    public class {_cls_pfx}Response")
        res_body_lines.append("    {")
        res_body_lines.append("        public bool Success { get; set; }")
        res_body_lines.append("        public string? Message { get; set; }")

        # Resolve repo output types — only emit a Data property for non-scalar,
        # named return types (dto/entity).  For scalar string returns (e.g. GetCommentAsync
        # returns IEnumerable<string>), derive a meaningful property name from DD query columns.
        data_types: list[tuple[str, str]] = []  # (type_name, kind)
        scalar_props: list[tuple[str, str]] = []  # (prop_name, cs_type) for scalar outputs
        for qm in event.get("query_mappings") or []:
            info = resolve_repo_for_mapping(qm, by_query, by_sheet)
            if not info:
                continue
            for o in info.get("output") or []:
                kind = (o.get("type") or "").lower()   # "dto" | "entity" | "string" | ...
                name = (o.get("name") or "").strip()   # class name like "GetUserInfoDto"
                if kind in ("dto", "entity") and name:
                    if name not in [t for t, _ in data_types]:
                        data_types.append((name, kind))
                        used_output_types[name] = kind
                elif kind in ("string", "scalar", "int", "decimal", "bool") or (not name and kind not in ("dto", "entity")):
                    # Scalar output — derive property name from config mapping
                    # Priority: column_name_map → function_name_map → function_name → "Data"
                    prop_name = ""
                    cs_type = "string?" if kind in ("string", "", "scalar") else f"{kind}?"

                    # Load mapping config once per call (cached via module-level read)
                    _rf_map = _load_response_field_mapping()
                    _fn_map = _rf_map.get("function_name_map", {})
                    _col_map = _rf_map.get("column_name_map", {})

                    # 1. Try column_name_map from DD query columns if available
                    qm_cols = qm.get("columns") or []
                    if qm_cols:
                        col = (qm_cols[0].get("alias") or qm_cols[0].get("column_name") or "").strip()
                        if col and col in _col_map:
                            prop_name = _col_map[col]

                    # 2. Derive from function_name and look up in function_name_map
                    if not prop_name:
                        fn = info.get("function_name", "")
                        fn_stripped = fn
                        for prefix in ("Get", "Fetch", "Load", "Select", "Query"):
                            if fn_stripped.startswith(prefix):
                                fn_stripped = fn_stripped[len(prefix):]
                                break
                        fn_stripped = fn_stripped.replace("Async", "").strip()
                        # Look up in config map first, else use stripped name directly
                        prop_name = _fn_map.get(fn_stripped, fn_stripped) if fn_stripped else "Data"

                    if prop_name and prop_name not in [p for p, _ in scalar_props]:
                        scalar_props.append((prop_name, cs_type))

        if len(data_types) == 1:
            t_name, _ = data_types[0]
            res_body_lines.append(f"        public IEnumerable<{t_name}>? Data {{ get; set; }}")
        elif len(data_types) > 1:
            for t_name, _ in data_types:
                res_body_lines.append(f"        public IEnumerable<{t_name}>? {t_name} {{ get; set; }}")

        # Gen scalar properties with proper names (not reusing Message)
        for prop_name, cs_type in scalar_props:
            res_body_lines.append(f"        public {cs_type} {prop_name} {{ get; set; }}")

        res_body_lines.append("    }")

    req_lines.append("}")
    res_body_lines.append("}")

    # ── Build Responses file: emit only the usings that are actually needed ──
    # Scan agents/repo/outputs/{form}/Domain/DTOs/ to find the actual namespace
    # for each DTO class, then emit precise using directives.
    def _find_dto_namespaces(f_name: str) -> dict[str, str]:
        """Return {ClassName: namespace} by scanning repo DTO output files."""
        ns_map: dict[str, str] = {}
        repo_dto_dir = Path(__file__).parent.parent / "repo" / "outputs" / f_name / "Domain" / "DTOs"
        if not repo_dto_dir.exists():
            # fallback: flat outputs dir
            repo_dto_dir = Path(__file__).parent.parent / "repo" / "outputs" / f_name
        if not repo_dto_dir.exists():
            return ns_map
        import re as _re
        for cs_file in repo_dto_dir.rglob("*.cs"):
            try:
                text = cs_file.read_text(encoding="utf-8")
                ns_m = _re.search(r"^namespace\s+([\w.]+)", text, _re.MULTILINE)
                cls_m = _re.search(r"public\s+class\s+(\w+)", text)
                if ns_m and cls_m:
                    ns_map[cls_m.group(1)] = ns_m.group(1)
            except Exception:
                pass
        return ns_map

    dto_ns_map = _find_dto_namespaces(form_name)

    res_using_lines: list[str] = ["using System.Collections.Generic;"]
    has_entity = any(k == "entity" for k in used_output_types.values())
    if has_entity:
        res_using_lines.append("using vba_brain.Domain.Entities;")

    # Emit one using per unique DTO namespace actually referenced
    dto_namespaces_added: set[str] = set()
    for type_name, kind in used_output_types.items():
        if kind == "dto":
            ns = dto_ns_map.get(type_name)
            if ns and ns not in dto_namespaces_added:
                res_using_lines.append(f"using {ns};")
                dto_namespaces_added.add(ns)
            elif not ns:
                # fallback — emit both common namespaces
                for fallback_ns in ("vba_brain.Domain.DTOs", "vba_brain.Domain.DTOs.Auth"):
                    if fallback_ns not in dto_namespaces_added:
                        res_using_lines.append(f"using {fallback_ns};")
                        dto_namespaces_added.add(fallback_ns)
    res_using_lines.append("")

    return "\n".join(req_lines), "\n".join(res_using_lines + res_body_lines)
