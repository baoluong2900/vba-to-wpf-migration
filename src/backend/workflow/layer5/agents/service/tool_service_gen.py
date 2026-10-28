"""
agents/service/tool_service_gen.py — Deterministic code generator for Agent Service.

Generates ``{Feature}Service.cs`` and the per-form Request/Response DTOs from the unified
service-input produced by ``agent_service.py`` (``build_service_input``). No LLM calls —
pure string templating, mirroring the style of ``agents/repo/tool_repo.py``.

Interface, implementation, DTOs and the service contract all come from one plan
(``build_service_plan``), so names, call arguments and response properties always agree:

1.  Method names: method_names.json registry → DD trigger (Japanese or English vocabulary,
    e.g. 更新後処理 / After Update → ``SubmitAsync``) → ``On{module_id}Async``; unique per service.
2.  Request/Response class prefixes: the module_id when it is a safe ASCII identifier, else the
    feature name (+2, +3… for further events). DTO namespaces come from core.naming.dto_namespace.
3.  Each ``query_mappings`` entry is resolved against the repository contract
    (``logic_query_name`` first, then ``sheet_name``). Call arguments follow the repository
    function's ``input`` list (order and types); a DTO input becomes ``new XInputDto { … }``.
    The Request DTO declares exactly the properties those calls read.
4.  Response properties: ``Data`` (or one per type) for entity/DTO results, one scalar property
    per scalar result, ``Authenticated`` for credential checks — the service assigns exactly those.
5.  Authentication events call the repository's parameterized ``VerifyCredentialsAsync``;
    credential rows (passwords) are never returned to the UI.
6.  Repositories actually called are injected via constructor DI.
7.  Every method body is wrapped in ``try/catch`` returning a ``Success=false`` response on exception.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

_LAYER5_DIR = Path(__file__).resolve().parent.parent.parent
if str(_LAYER5_DIR) not in sys.path:
    sys.path.insert(0, str(_LAYER5_DIR))

from core.naming import cs_identifier, dto_namespace  # noqa: E402

logger = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).parent
_GRAPHVIEW_OUTPUTS = AGENT_DIR.parent / "graphview" / "outputs"
_NAME_CONFIG_PATH = AGENT_DIR.parent / "repo" / "config" / "name_config.json"
_REPO_OUTPUTS_DIR = AGENT_DIR.parent / "repo" / "outputs"
ENTITY_NAMESPACE = "vba_brain.Domain.Entities"


# ──────────────────────────────────────────────
# Name helpers
# ──────────────────────────────────────────────
def _unique(name: str, used: set, keep_suffix: str = "") -> str:
    """`name`, or name2/name3… (name_2 after a digit) when taken; `keep_suffix` stays last; registers it."""
    stem, tail = name, ""
    if keep_suffix and name.endswith(keep_suffix) and len(name) > len(keep_suffix):
        stem, tail = name[: -len(keep_suffix)], keep_suffix
    candidate, n = name, 1
    while candidate in used:
        n += 1
        sep = "_" if stem[-1:].isdigit() else ""
        candidate = f"{stem}{sep}{n}{tail}"
    used.add(candidate)
    return candidate


def form_to_feature(form_name: str) -> str:
    """WPF feature name: graphview JP→EN map (forms, then reports) ViewModel/View name, else the cleaned form name."""
    for mapping_file in (
        _GRAPHVIEW_OUTPUTS / "forms" / "listFormJpToEn.json",
        _GRAPHVIEW_OUTPUTS / "reports" / "listReportJpToEn.json",
    ):
        if not mapping_file.exists():
            continue
        try:
            data = json.loads(mapping_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("[tool_service_gen] Failed to load %s: %s", mapping_file.name, exc)
            continue
        for item in data.get("items", []):
            if item.get("access_form_name") != form_name:
                continue
            # Use wpf_viewmodel_name strip 'ViewModel' → cleanest EN feature name
            vm = item.get("wpf_viewmodel_name", "")
            if vm and vm.endswith("ViewModel") and vm[:-9]:
                return cs_identifier(vm[:-9], fallback="Default")   # e.g. "R005WorkRequestViewModel" → "R005WorkRequest"
            view = item.get("wpf_view_name", "")
            if view and view.endswith("View") and view[:-4]:
                return cs_identifier(view[:-4], fallback="Default")

    name = form_name or ""
    if name.startswith("F_"):
        name = name[2:]
    return cs_identifier(re.sub(r"[^\w]", "", name), fallback="Default")


def _to_field(repo_name: str) -> str:
    """``IAuthRepository``/``AuthRepository`` → ``authRepository``."""
    if not repo_name:
        return "repository"
    name = repo_name[1:] if len(repo_name) > 1 and repo_name[0] == "I" and repo_name[1].isupper() else repo_name
    return cs_identifier(name[:1].lower() + name[1:], fallback="repository")


def _to_var(fn_name: str) -> str:
    """``GetUserInfoAsync`` → ``userInfo``."""
    name = fn_name or "result"
    for prefix in ("Get", "Find", "Load", "Fetch", "Select", "Read", "Query"):
        if name.startswith(prefix) and len(name) > len(prefix):
            name = name[len(prefix):]
            break
    if name.endswith("Async"):
        name = name[: -len("Async")]
    if not name:
        name = "result"
    return cs_identifier(name[:1].lower() + name[1:], fallback="result")


def is_label_control(ctrl_name: str) -> bool:
    """Return True when the control name looks like a UI label (not an input field).

    Patterns excluded:
      - Japanese label controls: ラベル<digits>  (e.g. ラベル400)
      - English-style label prefixes: lbl*, label*
    """
    ctrl_name = ctrl_name or ""
    return ctrl_name.lower().startswith(("lbl", "label")) or ctrl_name.startswith("ラベル")


def _pascal(token: str) -> str:
    token = (token or "").strip()
    if not token:
        return ""
    return token[:1].upper() + token[1:]


# ── name_config JP→EN field lookup ───────────────────────────────────────────
_NAME_CONFIG_CACHE: dict = {"mtime": None, "data": {}}


def _name_config() -> dict:
    """repo name_config.json, re-read when it changes (Agent Repo updates it during a pipeline run)."""
    try:
        mtime = _NAME_CONFIG_PATH.stat().st_mtime
    except OSError:
        return {}
    if _NAME_CONFIG_CACHE["mtime"] != mtime:
        try:
            _NAME_CONFIG_CACHE["data"] = json.loads(_NAME_CONFIG_PATH.read_text(encoding="utf-8"))
            _NAME_CONFIG_CACHE["mtime"] = mtime
        except (OSError, ValueError) as exc:
            logger.warning("[tool_service_gen] name_config.json unreadable: %s", exc)
    return _NAME_CONFIG_CACHE["data"] or {}


def _to_en_prop(ctrl: str) -> str:
    """
    Translate a JP control/field/parameter name to a PascalCase C# property name.

    Priority:
      1. Already ASCII → sanitized _pascal(ctrl)
      2. In name_config field_name map → _pascal(EN value)
      3. In name_config parameter_name map → _pascal(EN value)
      4. Fallback → "TODO"  (downstream knows to fill in)
    """
    ctrl = (ctrl or "").strip()
    if not ctrl:
        return "TODO"
    if ctrl.isascii():
        return cs_identifier(_pascal(ctrl), fallback="TODO")
    config = _name_config()
    for category in ("field_name", "parameter_name"):
        en = (config.get(category) or {}).get(ctrl, "")
        if en and not str(en).startswith("TODO"):
            return cs_identifier(_pascal(en), fallback="TODO")
    return "TODO"


# ── DD triggers (Japanese and English vocabularies) ──────────────────────────
# Normalised spelling (lower case, no spaces/underscores) → Mongo `forms` event key
# (same keys as core.fid_resolver.normalize_event).
_TRIGGER_ALIASES: dict[str, str] = {
    "画面を開く時": "onopen",
    "フォーム読み込み後": "onload",
    "フォーム読み込み時": "onload",
    "更新後処理": "afterupdate",
    "更新前処理": "beforeupdate",
    "クリック時": "onclick",
    "ダブルクリック時": "ondblclick",
    "キー押下時": "onkeydown",
    "キーが押された時": "onkeydown",
    "キー離した時": "onkeyup",
    "フォーカス取得時": "ongotfocus",
    "フォーカス喪失時": "onlostfocus",
    "タイマー時": "ontimer",
    "閉じる時": "onclose",
    "レコード移動時": "oncurrent",
    "ondoubleclick": "ondblclick",
    "doubleclick": "ondblclick",
    "dblclick": "ondblclick",
    "click": "onclick",
    "onafterupdate": "afterupdate",
    "onbeforeupdate": "beforeupdate",
    "open": "onopen",
    "load": "onload",
    "keydown": "onkeydown",
    "keyup": "onkeyup",
    "timer": "ontimer",
}

_EVENT_METHOD: dict[str, str] = {
    "onopen": "GetInitialDataAsync",
    "onload": "OnLoadAsync",
    "afterupdate": "SubmitAsync",
    "beforeupdate": "OnBeforeUpdateAsync",
    "onclick": "OnClickAsync",
    "ondblclick": "OnDoubleClickAsync",
    "onkeydown": "OnKeyDownAsync",
    "onkeyup": "OnKeyUpAsync",
    "ongotfocus": "OnGotFocusAsync",
    "onlostfocus": "OnLostFocusAsync",
    "ontimer": "OnTimerAsync",
}

_EVENT_VBA_SUFFIX: dict[str, str] = {
    "onopen": "_Open",
    "onload": "_Load",
    "onclose": "_Close",
    "onunload": "_Unload",
    "oncurrent": "_Current",
    "afterupdate": "_AfterUpdate",
    "beforeupdate": "_BeforeUpdate",
    "onclick": "_Click",
    "ondblclick": "_DblClick",
    "onkeydown": "_KeyDown",
    "onkeyup": "_KeyUp",
    "ongotfocus": "_GotFocus",
    "onlostfocus": "_LostFocus",
    "ontimer": "_Timer",
    "onchange": "_Change",
    "onactivate": "_Activate",
    "ondeactivate": "_Deactivate",
    "onresize": "_Resize",
}


def trigger_key(trigger: str | None) -> str:
    """'画面を開く時' / 'On Open' / 'onopen' → 'onopen'."""
    key = re.sub(r"[\s_]+", "", trigger or "").lower()
    return _TRIGGER_ALIASES.get(key, key)


def vba_handler_suffix(trigger: str | None) -> str:
    """VBA handler suffix for a DD trigger ('After Update' → '_AfterUpdate'), '' when unknown."""
    return _EVENT_VBA_SUFFIX.get(trigger_key(trigger), "")


def _load_response_field_mapping() -> dict:
    """Load response field mapping config from configs/response_field_mapping.json."""
    config_path = AGENT_DIR / "configs" / "response_field_mapping.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            return {
                "function_name_map": data.get("function_name_map", {}),
                "column_name_map": data.get("column_name_map", {}),
            }
        except Exception as e:
            logger.warning("Failed to load response_field_mapping.json: %s", e)
    return {"function_name_map": {}, "column_name_map": {}}


def _load_method_names() -> dict:
    config_path = AGENT_DIR / "configs" / "method_names.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load method_names.json: %s", e)
    return {}


def derive_method_name(event: dict, feature: str, form_name: str = "", registry: dict | None = None) -> str:
    trigger = (event.get("event_trigger") or "").strip()
    module_id = (event.get("module_id") or "").strip()

    if form_name:
        registry = registry if registry is not None else _load_method_names()
        custom_name = registry.get(form_name, {}).get(module_id, {}).get("method_name")
        if custom_name:
            return cs_identifier(custom_name, fallback="ExecuteAsync")

    key = trigger_key(trigger)
    if key == "afterupdate" and feature.lower() == "login":
        return "AuthenticateAsync"
    if key in _EVENT_METHOD:
        return _EVENT_METHOD[key]
    mid = cs_identifier(module_id, fallback="") if module_id else ""
    return f"On{mid}Async" if mid else "ExecuteAsync"


def assign_method_names(events: list[dict], feature: str, form_name: str = "") -> list[str]:
    """One service method name per event, unique (a repeated trigger falls back to On{module_id}Async)."""
    registry = _load_method_names() if form_name else {}
    used: set = set()
    names = []
    for ev in events:
        name = derive_method_name(ev, feature, form_name, registry)
        if name in used:
            mid = cs_identifier((ev.get("module_id") or "").strip(), fallback="")
            if mid and f"On{mid}Async" not in used:
                name = f"On{mid}Async"
        names.append(_unique(name, used, keep_suffix="Async"))
    return names


def assign_class_tokens(events: list[dict], feature: str) -> list[str]:
    """Request/Response class prefix per event: the module_id when it is a safe ASCII id, else feature (+2, +3…)."""
    used: set = set()
    tokens = []
    for ev in events:
        mid = (ev.get("module_id") or "").strip()
        base = mid if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", mid) else (feature or "Default")
        tokens.append(_unique(base, used))
    return tokens


# ──────────────────────────────────────────────
# Repository index
# ──────────────────────────────────────────────
def _contract_dtos(repository_contracts: dict) -> dict[str, dict]:
    dtos: dict[str, dict] = {}
    for d in (repository_contracts or {}).get("dtos") or (repository_contracts or {}).get("dto") or []:
        if isinstance(d, dict) and d.get("dto_name"):
            dtos.setdefault(d["dto_name"], d)
    return dtos


def build_repo_index(
    repository_contracts: dict,
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Build two lookups: ``by_query_name`` and ``by_sheet_query_name``.

    Returns ``(by_query_name, by_sheet_query_name)``. Callers should prefer
    the logical ``query_name`` over the sheet identifier — sheet numbers in
    DD vs. Agent Repo output are not always aligned.
    """
    contracts = repository_contracts or {}
    dtos = _contract_dtos(contracts)
    by_query: dict[str, dict] = {}
    by_sheet: dict[str, dict] = {}
    for repo in contracts.get("repositories") or contracts.get("repository") or []:
        repo_name = repo.get("repository_name") or ""
        functions = repo.get("function") or []
        credential = next((fn for fn in functions if fn.get("kind") == "credential_check"), None)
        for fn in functions:
            inputs = fn.get("input") or []
            dto_input = next((i for i in inputs if (i.get("type") or "").lower() == "dto"), None)
            info = {
                "repo_name": repo_name,
                "iface_name": repo.get("interface_name") or f"I{repo_name}",
                "table_name": repo.get("table_name") or "",
                "function_name": fn.get("function_name") or "",
                "input": inputs,
                "output": fn.get("output") or [],
                "description": fn.get("description") or "",
                "return_type": fn.get("return_type") or "",
                "kind": fn.get("kind") or "",
                "implemented": fn.get("implemented", True),
                "credential_check": credential,
                "input_dto": dtos.get(dto_input.get("name")) if dto_input else None,
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
# Arguments / properties
# ──────────────────────────────────────────────
def _qm_controls(qm: dict) -> list[tuple[str, str]]:
    """(parameter name, control) for the input parameters of a query mapping; UI labels skipped."""
    out = []
    for p in qm.get("parameters") or []:
        if not isinstance(p, dict) or (p.get("io") or "I").upper() != "I":
            continue
        mapping = (p.get("mapping") or "").strip()
        # Mapping looks like "＜パラメータ＞.txtID" — take the segment after the last dot.
        ctrl = (mapping.rsplit(".", 1)[-1] if "." in mapping else (p.get("name") or "")).strip()
        if ctrl and not is_label_control(ctrl):
            out.append(((p.get("name") or "").strip(), ctrl))
    return out


def _control_for(qm: dict, *keys) -> str:
    """DD control that feeds a repository input (matched on its VBA name / JP key / C# name)."""
    wanted = {str(k).lower() for k in keys if k}
    for name, ctrl in _qm_controls(qm):
        cands = {name.lower(), ctrl.lower()}
        cands |= {c[3:] for c in cands if c.startswith("txt")}
        if wanted & cands:
            return ctrl
    return ""


def _add_request_prop(props: dict, name: str, cs_type: str, description: str = "", control: str = "") -> str:
    """Declare a Request DTO property once; the same name with another type gets a 2/3… suffix."""
    prop = cs_identifier(_pascal(name or ""), fallback="Value")
    existing = props.get(prop)
    if existing is not None and existing["type"] != (cs_type or "string"):
        prop = _unique(prop, set(props))
        existing = None
    if existing is None:
        props[prop] = {"name": prop, "type": cs_type or "string", "description": description or "", "control": control or ""}
    return prop


def _qualified_type(name: str, namespace: str) -> str:
    if not name:
        return "object"
    if namespace and namespace != ENTITY_NAMESPACE:
        return f"{namespace}.{name}"
    return name


def _call_args(info: dict, qm: dict, req_props: dict) -> tuple[str, list[str]]:
    """C# argument list for one repository call, built from the function's input contract."""
    inputs = info.get("input") or []
    notes: list[str] = []
    dto_input = next((i for i in inputs if (i.get("type") or "").lower() == "dto"), None)
    if dto_input:
        dto = info.get("input_dto") or {}
        type_name = _qualified_type(dto_input.get("name") or dto.get("dto_name", ""),
                                    dto_input.get("namespace") or dto.get("namespace", ""))
        assigns = []
        for f in dto.get("fields") or []:
            control = _control_for(qm, f.get("description"), f.get("name"))
            prop = _add_request_prop(req_props, f.get("name"), f.get("type") or "string", f.get("description"), control)
            assigns.append(f"{f['name']} = request.{prop}")
        if not assigns:
            notes.append(f"fields of {type_name} unknown — fill them manually")
            return f"new {type_name}()", notes
        return f"new {type_name} {{ {', '.join(assigns)} }}", notes

    args = []
    for inp in inputs:
        control = _control_for(qm, inp.get("vba"), inp.get("description"), inp.get("name"))
        prop = _add_request_prop(req_props, inp.get("name"), inp.get("type") or "string", inp.get("description"), control)
        args.append(f"request.{prop}")
        notes.append(f"{control or inp.get('description') or inp.get('name')} → request.{prop}")
    return ", ".join(args), notes


def _output_of(info: dict) -> dict:
    outputs = info.get("output") or []
    return outputs[0] if outputs else {}


def _returns_collection(info: dict) -> bool:
    return_type = info.get("return_type") or ""
    if return_type:
        return return_type.startswith("IEnumerable<")
    # Older contracts without return_type: action queries report a bare int
    return (_output_of(info).get("type") or "").lower() != "int"


def _nullable(cs_type: str) -> str:
    cs_type = cs_type or "string"
    return cs_type if cs_type.endswith("?") else cs_type + "?"


def _scalar_prop_name(info: dict, qm: dict, rf_map: dict) -> str:
    """Scalar response property: column_name_map → function_name_map → stripped function name → 'Data'."""
    qm_cols = qm.get("columns") or []
    if qm_cols:
        col = (qm_cols[0].get("alias") or qm_cols[0].get("column_name") or "").strip()
        if col and col in rf_map.get("column_name_map", {}):
            return rf_map["column_name_map"][col]
    fn_stripped = info.get("function_name", "")
    for prefix in ("Get", "Fetch", "Load", "Select", "Query"):
        if fn_stripped.startswith(prefix):
            fn_stripped = fn_stripped[len(prefix):]
            break
    fn_stripped = fn_stripped.replace("Async", "").strip()
    return rf_map.get("function_name_map", {}).get(fn_stripped, fn_stripped) if fn_stripped else "Data"


# ──────────────────────────────────────────────
# Per-event plan
# ──────────────────────────────────────────────
_AUTH_KEYWORDS = ("認証", "パスワード", "暗証", "password", "authenticat", "credential")


def _event_text(event: dict) -> str:
    parts = [event.get("event_content") or ""]
    for step in event.get("steps") or []:
        parts.append(f"{step.get('detail') or ''} {step.get('step') or ''}")
    return " ".join(parts)


def is_auth_event(event: dict) -> bool:
    """Credential-check events (password / 認証 wording in the DD); a bare 'ID' no longer qualifies."""
    text = _event_text(event).lower()
    return any(k in text for k in _AUTH_KEYWORDS)


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


def _plan_event(
    event: dict,
    method_name: str,
    token: str,
    by_query: dict[str, dict],
    by_sheet: dict[str, dict],
    rf_map: dict,
    dto_namespace_of,
    include_comments: bool = False,
) -> dict:
    module_id = event.get("module_id", "") or ""
    trigger = event.get("event_trigger", "") or ""
    request_type = f"{token}Request"
    response_type = f"{token}Response"
    summary = (event.get("event_content") or "").replace("\r\n", " ").replace("\n", " ").strip()[:200]
    content_lines = (event.get("event_content") or "").splitlines()
    short = content_lines[0][:120] if content_lines else ""
    auth = is_auth_event(event)

    # Indents: method body = 8 spaces, try-block body = 12 spaces.
    BODY = "            "  # 12

    req_props: dict[str, dict] = {}
    call_lines: list[str] = []
    calls: list[dict] = []
    var_used: set = {"request", "ex"}
    verified: set = set()

    for qm in event.get("query_mappings") or []:
        info = resolve_repo_for_mapping(qm, by_query, by_sheet)
        sheet = qm.get("sheet_name", "")
        logic = qm.get("logic_query_name", "")
        if not info:
            call_lines.append(
                f"{BODY}// TODO: Repository function not found for query "
                f"'{logic}' (sheet {sheet}). Add the mapping in Agent Repo output."
            )
            call_lines.append("")
            # No contract to follow — keep the DD inputs as (string) request properties
            for _, ctrl in _qm_controls(qm):
                _add_request_prop(req_props, _to_en_prop(ctrl), "string", ctrl, ctrl)
            continue

        role, call_info = "data", info
        if auth and info.get("credential_check"):
            # Verify the entered credentials in SQL instead of shipping credential rows to the UI
            if info["repo_name"] in verified:
                continue
            verified.add(info["repo_name"])
            check = info["credential_check"]
            call_info = {
                **info,
                "function_name": check.get("function_name", ""),
                "input": check.get("input") or [],
                "output": check.get("output") or [],
                "return_type": check.get("return_type") or "bool",
                "kind": "credential_check",
                "implemented": True,
                "input_dto": None,
            }
            role = "auth"

        args, notes = _call_args(call_info, qm, req_props)
        var = _unique(_to_var(call_info["function_name"]), var_used)
        field = _to_field(call_info["repo_name"])
        if notes:
            call_lines.append(f"{BODY}// Args: {'; '.join(notes)}")
        call_lines.append(
            f"{BODY}// {module_id} → {call_info['repo_name']}.{call_info['function_name']} "
            f"(query: {logic})"
        )
        if not call_info.get("implemented", True):
            call_lines.append(f"{BODY}// NOTE: no SQL in Agent Repo for this query yet — the call throws NotImplementedException")
        call_lines.append(f"{BODY}var {var} = await _{field}.{call_info['function_name']}({args});")
        call_lines.append("")
        calls.append({"var": var, "info": call_info, "qm": qm, "role": role})

    if auth and calls and not verified:
        call_lines.append(
            f"{BODY}// TODO(auth): the repository contract has no VerifyCredentialsAsync "
            f"(credential table schema unknown) — add the check in Agent Repo."
        )
        call_lines.append("")

    # Response properties — exactly what the method assigns
    res_props = [{"name": "Success", "type": "bool"}, {"name": "Message", "type": "string?"}]
    used_names = {"Success", "Message"}
    assigns: list[str] = []
    usings: set = set()
    named = [
        c for c in calls
        if c["role"] == "data"
        and (_output_of(c["info"]).get("type") or "").lower() in ("dto", "entity")
        and _output_of(c["info"]).get("name")
    ]
    for c in calls:
        info = c["info"]
        out = _output_of(info)
        kind = (out.get("type") or "").lower()
        if c["role"] == "auth":
            prop = _unique("Authenticated", used_names)
            res_props.append({"name": prop, "type": "bool"})
            assigns.append(f"{prop} = {c['var']}")
        elif kind in ("dto", "entity"):
            if not out.get("name"):
                continue
            namespace = out.get("namespace") or dto_namespace_of(out["name"], kind)
            if kind == "entity" or namespace == ENTITY_NAMESPACE:
                usings.add(ENTITY_NAMESPACE)
            elif not namespace:
                usings.add("vba_brain.Domain.DTOs")   # namespace unknown (old contract): best effort
            type_name = _qualified_type(out["name"], namespace)
            prop = _unique("Data" if len(named) == 1 else cs_identifier(out["name"], "Data"), used_names)
            res_props.append({"name": prop, "type": f"IEnumerable<{type_name}>?"})
            assigns.append(f"{prop} = {c['var']}")
        else:
            prop = _unique(cs_identifier(_scalar_prop_name(info, c["qm"], rf_map), "Data"), used_names)
            res_props.append({"name": prop, "type": _nullable(out.get("type") or "string")})
            assigns.append(f"{prop} = {c['var']}?.FirstOrDefault()" if _returns_collection(info) else f"{prop} = {c['var']}")

    lines: list[str] = [
        "    /// <summary>",
        f"    /// {module_id} {trigger} — {summary}",
        "    /// </summary>",
        f"    public async Task<{response_type}> {method_name}({request_type} request)",
        "    {",
        "        try",
        "        {",
    ]
    # DD steps as Japanese comments — chỉ emit khi include_comments=True
    if include_comments:
        lines.extend(_emit_step_comments(event, BODY))
    lines.extend(call_lines)

    # VBA hints when no query_mappings but VBA shows data-access
    matched = event.get("matched_vba") or {}
    vba_code = matched.get("code") or ""
    if not (event.get("query_mappings") or []) and vba_code and _vba_has_op(vba_code, ("DLookup", "DCount", "DSum")):
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

    if assigns:
        lines.append(f"{BODY}return new {response_type} {{")
        lines.append(f"{BODY}    Success = true,")
        for a in assigns:
            lines.append(f"{BODY}    {a},")
        lines.append(f"{BODY}}};")
    else:
        if not calls:
            lines.append(f"{BODY}await Task.CompletedTask;")
        lines.append(f"{BODY}return new {response_type} {{ Success = true }};")

    lines.append("        }")
    lines.append("        catch (System.Exception ex)")
    lines.append("        {")
    lines.append(f"{BODY}return new {response_type} {{ Success = false, Message = ex.Message }};")
    lines.append("        }")
    lines.append("    }")

    return {
        "event": event,
        "module_id": module_id,
        "trigger": trigger,
        "method_name": method_name,
        "request_class": request_type,
        "response_class": response_type,
        "request_props": list(req_props.values()),
        "response_props": res_props,
        "calls": calls,
        "repo_calls": [
            {
                "repository": c["info"]["repo_name"],
                "function": c["info"]["function_name"],
                "query": c["qm"].get("logic_query_name") or c["qm"].get("sheet_name", ""),
            }
            for c in calls
        ],
        "method_code": "\n".join(lines),
        "comment": f"{module_id} {trigger} — {short}",
        "response_usings": sorted(usings),
    }


def _find_dto_namespaces(form_name: str) -> dict[str, str]:
    """{DTO class: namespace} from the repo snapshot files (fallback for contracts without namespaces)."""
    ns_map: dict[str, str] = {}
    repo_dto_dir = _REPO_OUTPUTS_DIR / form_name
    if not repo_dto_dir.exists():
        return ns_map
    for cs_file in repo_dto_dir.rglob("*.cs"):
        try:
            text = cs_file.read_text(encoding="utf-8")
        except OSError:
            continue
        ns_m = re.search(r"^namespace\s+([\w.]+)", text, re.MULTILINE)
        cls_m = re.search(r"public\s+class\s+(\w+)", text)
        if ns_m and cls_m:
            ns_map[cls_m.group(1)] = ns_m.group(1)
    return ns_map


def build_service_plan(service_input: dict, include_comments: bool = False) -> dict:
    """Everything the interface, implementation, DTOs and service contract need, derived once."""
    form_name = service_input.get("form_name", "")
    events = service_input.get("events") or []
    contracts = service_input.get("repository_contracts") or {}

    feature = form_to_feature(form_name)
    by_query, by_sheet = build_repo_index(contracts)
    dtos = _contract_dtos(contracts)
    rf_map = _load_response_field_mapping()
    scanned: dict[str, str] | None = None

    def dto_namespace_of(type_name: str, kind: str) -> str:
        nonlocal scanned
        if kind == "entity":
            return ENTITY_NAMESPACE
        ns = (dtos.get(type_name) or {}).get("namespace", "")
        if not ns:
            if scanned is None:
                scanned = _find_dto_namespaces(form_name)
            ns = scanned.get(type_name, "")
        return ns

    method_names = assign_method_names(events, feature, form_name)
    tokens = assign_class_tokens(events, feature)
    event_plans = [
        _plan_event(ev, method_names[i], tokens[i], by_query, by_sheet, rf_map, dto_namespace_of, include_comments)
        for i, ev in enumerate(events)
    ]

    repos: list[dict] = []
    seen: set = set()
    for plan in event_plans:
        for c in plan["calls"]:
            name = c["info"].get("repo_name") or ""
            if name and name not in seen:
                seen.add(name)
                repos.append(c["info"])

    return {
        "form_name": form_name,
        "feature": feature,
        "service_name": f"{feature}Service",
        "iface_name": f"I{feature}Service",
        "request_namespace": dto_namespace(form_name, "Requests"),
        "response_namespace": dto_namespace(form_name, "Responses"),
        "events": event_plans,
        "repos": repos,
    }


# ──────────────────────────────────────────────
# Class assembly
# ──────────────────────────────────────────────
def generate_service_impl(service_input: dict, include_comments: bool = False) -> str:
    """Generate ``{Feature}Service.cs`` source from the unified service input."""
    plan = build_service_plan(service_input, include_comments=include_comments)
    form_name = plan["form_name"]
    service_name = plan["service_name"]
    repos = plan["repos"]

    lines: list[str] = []
    lines.append("namespace vba_brain.Application.Services;")
    lines.append("")
    lines.append("using System;")
    lines.append("using System.Linq;")
    lines.append("using System.Threading.Tasks;")
    lines.append("using vba_brain.Application.DTOs;")
    lines.append(f"using {plan['request_namespace']};")
    lines.append(f"using {plan['response_namespace']};")
    lines.append("using vba_brain.Application.Interfaces;")
    lines.append(f"using {ENTITY_NAMESPACE};")
    lines.append("using vba_brain.Domain.Interfaces;")
    lines.append("")
    lines.append("/// <summary>")
    lines.append(f"/// Application service for {form_name}. Auto-generated by tool_service_gen.")
    lines.append("/// </summary>")
    lines.append(f"public class {service_name} : {plan['iface_name']}")
    lines.append("{")

    # Fields
    for r in repos:
        lines.append(f"    private readonly {r['iface_name']} _{_to_field(r['repo_name'])};")
    if repos:
        lines.append("")

    # Constructor
    if repos:
        lines.append(f"    public {service_name}(")
        for i, r in enumerate(repos):
            sep = "," if i < len(repos) - 1 else ""
            lines.append(f"        {r['iface_name']} {_to_field(r['repo_name'])}{sep}")
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
    for ev_plan in plan["events"]:
        lines.append(ev_plan["method_code"])
        lines.append("")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def generate_service_iface_methods(service_input: dict) -> list[dict]:
    """Return method specs for the IService interface (used by Jinja2 renderer).

    Kept in this module so callers don't need to duplicate naming logic.
    """
    plan = build_service_plan(service_input)
    return [
        {
            "name": ev_plan["method_name"],
            "return_type": f"Task<{ev_plan['response_class']}>",
            "params": f"{ev_plan['request_class']} request",
            "comment": ev_plan["comment"],
        }
        for ev_plan in plan["events"]
    ]


def _request_prop_line(p: dict) -> str:
    cs_type = p.get("type") or "string"
    init = " = default!;" if cs_type in ("string", "object", "byte[]") else ""
    comment = f"  // TODO: translate '{p['description']}'" if p["name"].startswith("TODO") and p.get("description") else ""
    return f"        public {cs_type} {p['name']} {{ get; set; }}{init}{comment}"


def generate_service_dtos(service_input: dict) -> tuple[str, str]:
    """Generate Request and Response C# code for DTOs.

    Returns (requests_code, responses_code).
    """
    plan = build_service_plan(service_input)
    form_name = plan["form_name"]

    req_lines: list[str] = [
        "using System.Collections.Generic;",
        "",
        f"namespace {plan['request_namespace']}",
        "{",
        f"    // Auto-generated by tool_service_gen for {form_name}.",
        "    // Do not edit manually.",
    ]
    res_body_lines: list[str] = [
        "",
        f"namespace {plan['response_namespace']}",
        "{",
        f"    // Auto-generated by tool_service_gen for {form_name}.",
        "    // Do not edit manually.",
    ]
    usings: set = set()

    for ev_plan in plan["events"]:
        usings.update(ev_plan["response_usings"])
        header = f"{ev_plan['module_id']} {ev_plan['trigger']}".strip()

        req_lines.append("")
        req_lines.append(f"    /// <summary>{header} — Request DTO</summary>")
        req_lines.append(f"    public class {ev_plan['request_class']}")
        req_lines.append("    {")
        for p in ev_plan["request_props"]:
            req_lines.append(_request_prop_line(p))
        req_lines.append("    }")

        res_body_lines.append("")
        res_body_lines.append(f"    /// <summary>{header} — Response DTO</summary>")
        res_body_lines.append(f"    public class {ev_plan['response_class']}")
        res_body_lines.append("    {")
        for p in ev_plan["response_props"]:
            res_body_lines.append(f"        public {p['type']} {p['name']} {{ get; set; }}")
        res_body_lines.append("    }")

    req_lines.append("}")
    res_body_lines.append("}")

    res_using_lines: list[str] = ["using System.Collections.Generic;"]
    res_using_lines.extend(f"using {ns};" for ns in sorted(usings))
    res_using_lines.append("")

    return "\n".join(req_lines), "\n".join(res_using_lines + res_body_lines)
