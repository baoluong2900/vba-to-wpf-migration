#!/usr/bin/env python3
"""
Enrich exported Access form/report JSON with VBA dependency hints:

  - references: forms, reports, queries, macros, modules, tables
  - Callable refs: same-form/report procedures as <Document>.<proc>; standard modules from
    modules_json as <module_name>.<proc> when known.
  - DLookup/DCount/… 2nd arg and OpenRecordset("…"): name in exported query_json → queries;
    else → tables (heuristic).
  - commands: DoCmd.RunCommand / DoCmd.Maximize|Minimize|Restore
  - Design-time events: non-own handlers are replaced by a single qualified string, e.g.
    macro.<name>, query.<name>, form.<name>, report.<name>, module.<module>.<proc>
    (two-part only for standard-module procedures).

Reads from output/forms_json and output/report_json (configurable); writes mirrored
copies under a separate root (default: output/forms_report_json_refs/).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2].parent
DATABASE_JSON_DIR = PROJECT_ROOT.parent / "data"

DEFAULT_FORMS_SRC = DATABASE_JSON_DIR / "forms"
DEFAULT_REPORTS_SRC = DATABASE_JSON_DIR / "reports"
DEFAULT_MODULES_JSON_DIR = DATABASE_JSON_DIR / "modules"
DEFAULT_QUERIES_JSON_DIR = DATABASE_JSON_DIR / "queries"
DEFAULT_MACROS_JSON_DIR = DATABASE_JSON_DIR / "macros"
DEFAULT_OUTPUT_ROOT = DATABASE_JSON_DIR

_HEURISTIC_MACRO_NAME = re.compile(r"^M\d+_", re.I)

_VB_KEYWORDS = frozenset(
    x.lower()
    for x in (
        "If Then Else ElseIf End Select Case For Each Next Do Loop Until While Wend With "
        "Dim As Set Call Private Public Sub Function Property Type Enum Event Const Static "
        "ByVal ByRef Optional ParamArray True False Nothing Empty Null "
        "Long Integer String Boolean Date Variant Single Double Currency Byte Object "
        "And Or Not Xor Mod Is Like GoTo On Error Resume Exit Stop GoSub "
        "ByRef ByVal New Me ReDim Preserve TypeOf AddressOf "
        "Open Close Print FreeFile As "
        "AndAlso OrElse Continue "
        "Option Compare Database Explicit "
        "Declare Lib PtrSafe "
    ).split()
)

_DCMD_OPEN_FORM = re.compile(r"DoCmd\.OpenForm\s+\"([^\"]+)\"", re.I)
_DCMD_CLOSE_FORM = re.compile(r"(?:DoCmd\.)?Close\s+acForm\s*,\s*\"([^\"]+)\"", re.I)
_DCMD_OUTPUTTO_FORM = re.compile(
    r"DoCmd\.OutputTo\s+acOutputForm\s*,\s*\"([^\"]+)\"",
    re.I,
)
_DCMD_OPEN_REPORT = re.compile(r"DoCmd\.OpenReport\s+\"([^\"]+)\"", re.I)
_DCMD_CLOSE_REPORT = re.compile(
    r"(?:DoCmd\.)?Close\s+acReport\s*,\s*\"([^\"]+)\"", re.I
)
_DCMD_OUTPUTTO_REPORT = re.compile(
    r"DoCmd\.OutputTo\s+acOutputReport\s*,\s*\"([^\"]+)\"",
    re.I,
)
_DCMD_OPEN_QUERY = re.compile(r"DoCmd\.OpenQuery\s+\"([^\"]+)\"", re.I)
_DCMD_OUTPUTTO_QUERY = re.compile(
    r"DoCmd\.OutputTo\s+acQuery\s*,\s*\"([^\"]+)\"",
    re.I,
)
_DCMD_OPEN_TABLE = re.compile(r"DoCmd\.OpenTable\s+\"([^\"]+)\"", re.I)
_DCMD_OUTPUTTO_TABLE = re.compile(
    r"DoCmd\.OutputTo\s+acOutputTable\s*,\s*\"([^\"]+)\"",
    re.I,
)
_DCMD_RUN_MACRO = re.compile(r"DoCmd\.RunMacro\s+\"([^\"]+)\"", re.I)
_CALL_SUB = re.compile(r"\bCall\s+(\w+)\b", re.I)
_VBA_WORD = re.compile(r"\b([A-Za-z_]\w*)\b")
_FORM_INSTANCE_PROC = re.compile(r"\bForm_([^.]+)\.([^(\s]+)")
_FORMS_REF = re.compile(r"\[Forms\]\s*!\s*\[([^\]]+)\]", re.I)
_TABLE_IN_EXPR = re.compile(
    r"(?:DCount|DSum|DAvg|DMin|DMax|DLookup|DFirst|DLast)\s*\(\s*"
    r"(?:\"([^\"\\]|\\.)*\"|'([^'\\]|\\.)*')\s*,\s*"
    r"\"([^\"]+)\"",
    re.I,
)
_OPENRECORDSET_STR = re.compile(r"OpenRecordset\s*\(\s*\"([^\"]+)\"", re.I)
_RUNCOMMAND = re.compile(r"DoCmd\.RunCommand\s+(\w+)", re.I)
_DOCMD_WINDOW = re.compile(r"DoCmd\.(Maximize|Minimize|Restore)\b", re.I)
_APP_RUN = re.compile(r"Application\.Run\s+\"([^\"]+)\"", re.I)
_SINGLE_WORD_LINE = re.compile(r"^\s*([A-Za-z_][\w]*)\s*(?:'.*)?$", re.MULTILINE)

_VBA_CONTROL_EVENT_SUFFIXES = frozenset(
    {
        "Click",
        "DblClick",
        "Change",
        "Enter",
        "Exit",
        "GotFocus",
        "LostFocus",
        "KeyDown",
        "KeyUp",
        "KeyPress",
        "MouseDown",
        "MouseUp",
        "MouseMove",
        "BeforeUpdate",
        "AfterUpdate",
        "BeforeInsert",
        "AfterInsert",
        "Updated",
        "Timer",
        "Open",
        "Close",
        "Load",
        "Unload",
        "Resize",
        "Paint",
        "Current",
        "Print",
        "Format",
        "Retreat",
        "NotInList",
        "Delete",
        "BeforeDelConfirm",
        "AfterDelConfirm",
        "ApplyFilter",
        "Filter",
        "Error",
        "NoData",
        "Page",
        "Foot",
        "Activate",
        "Deactivate",
    }
)


def _strip_vba_comments(code: str) -> str:
    if not code:
        return ""
    cleaned: list[str] = []
    for raw_line in code.splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()
        if not stripped:
            cleaned.append("")
            continue
        if stripped.startswith("'") or re.match(r"Rem(\s|$)", stripped, re.I):
            continue
        i = 0
        n = len(line)
        in_str = False
        while i < n:
            ch = line[i]
            if in_str:
                if ch == '"':
                    if i + 1 < n and line[i + 1] == '"':
                        i += 2
                        continue
                    in_str = False
                i += 1
                continue
            if ch == '"':
                in_str = True
                i += 1
                continue
            if ch == "'":
                line = line[:i].rstrip()
                break
            rem = line[i : i + 3]
            if rem.lower() == "rem":
                prev_char = line[i - 1] if i > 0 else " "
                next_char = line[i + 3] if i + 3 < n else " "
                if (not (prev_char.isalnum() or prev_char == "_")) and (
                    next_char.isspace() or i + 3 >= n
                ):
                    line = line[:i].rstrip()
                    break
            i += 1
        if not line.strip():
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def collect_json_stems_casefold(src_dir: Path) -> frozenset[str]:
    if not src_dir.is_dir():
        return frozenset()
    return frozenset(p.stem.casefold() for p in src_dir.glob("*.json"))


def load_known_macro_names_casefold(macros_dir: Path) -> frozenset[str]:
    names: set[str] = set()
    if not macros_dir.is_dir():
        return frozenset()
    for path in sorted(macros_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        mn = (raw.get("macro_name") or path.stem or "").strip()
        if mn:
            names.add(mn.casefold())
    return frozenset(names)


def load_known_query_names_casefold(queries_dir: Path) -> frozenset[str]:
    names: set[str] = set()
    if not queries_dir.is_dir():
        return frozenset()
    for path in sorted(queries_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        qn = (raw.get("query_name") or path.stem or "").strip()
        if qn:
            names.add(qn.casefold())
    return frozenset(names)


def collect_form_report_references(data: dict[str, Any], label: str, known_queries_cf: frozenset[str]) -> dict[str, list[str]]:
    refs = {
        "forms": set(),
        "reports": set(),
        "queries": set(),
        "macros": set(),
        "modules": set(),
        "tables": set()
    }
    
    rs = data.get("record_source") or (data.get("properties") or {}).get("data", {}).get("recordsource")
    if isinstance(rs, str):
        rs = rs.strip()
        if rs and not rs.upper().startswith("SELECT"):
            if rs.startswith("[") and rs.endswith("]"):
                rs = rs[1:-1]
            if rs.casefold() in known_queries_cf:
                refs["queries"].add(rs)
            else:
                refs["tables"].add(rs)
                
    funcs = data.get("functions") or []
    for fn in funcs:
        fn_refs = fn.get("references")
        if isinstance(fn_refs, dict):
            for k in ["forms", "reports", "queries", "macros", "modules", "tables"]:
                for item in fn_refs.get(k) or []:
                    if isinstance(item, str) and item.strip():
                        val = item.strip()
                        if k == "forms" and "." in val:
                            val = val.split(".")[0]
                            if val.lower().startswith("form_"):
                                val = val[5:]
                        elif k == "modules" and "." in val:
                            val = val.split(".")[0]
                        refs[k].add(val)

    def scan_event_dict(event_dict: Any):
        if not isinstance(event_dict, dict):
            return
        for v in event_dict.values():
            if isinstance(v, str):
                parts = v.strip().split(".")
                if len(parts) >= 2:
                    ref_type = parts[0]
                    ref_name = parts[1]
                    if ref_type == "macro":
                        refs["macros"].add(ref_name)
                    elif ref_type == "query":
                        refs["queries"].add(ref_name)
                    elif ref_type == "form":
                        refs["forms"].add(ref_name)
                    elif ref_type == "report":
                        refs["reports"].add(ref_name)
                    elif ref_type == "module":
                        refs["modules"].add(ref_name)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        parts = item.strip().split(".")
                        if len(parts) >= 2:
                            ref_type = parts[0]
                            ref_name = parts[1]
                            if ref_type == "macro":
                                refs["macros"].add(ref_name)
                            elif ref_type == "query":
                                refs["queries"].add(ref_name)
                            elif ref_type == "form":
                                refs["forms"].add(ref_name)
                            elif ref_type == "report":
                                refs["reports"].add(ref_name)
                            elif ref_type == "module":
                                refs["modules"].add(ref_name)
                            
    props = data.get("properties")
    if isinstance(props, dict):
        scan_event_dict(props.get("event"))
    for it in data.get("items") or []:
        if isinstance(it, dict):
            ip = it.get("properties")
            if isinstance(ip, dict):
                scan_event_dict(ip.get("event"))
                
    doc_name = (data.get("name") or data.get("module_name") or "").strip()
    if not doc_name:
        other = (data.get("properties") or {}).get("other") or {}
        doc_name = str(other.get("name") or "").strip()
        
    if doc_name:
        if label == "forms":
            refs["forms"].discard(doc_name)
        elif label == "reports":
            refs["reports"].discard(doc_name)
            
    return {k: sorted(list(v)) for k, v in refs.items()}


def collect_macro_references(data: dict[str, Any]) -> dict[str, list[str]]:
    refs = {
        "forms": set(),
        "reports": set(),
        "queries": set(),
        "macros": set(),
        "modules": set(),
        "tables": set()
    }
    
    macro_refs = data.get("references")
    if isinstance(macro_refs, dict):
        for k in ["forms", "reports", "queries", "macros", "modules", "tables"]:
            for item in macro_refs.get(k) or []:
                if isinstance(item, str) and item.strip():
                    val = item.strip()
                    if k == "modules" and "." in val:
                        val = val.split(".")[0]
                    refs[k].add(val)
                    
    doc_name = (data.get("macro_name") or data.get("name") or "").strip()
    if doc_name:
        refs["macros"].discard(doc_name)
        
    return {k: sorted(list(v)) for k, v in refs.items()}


def collect_module_references(data: dict[str, Any]) -> dict[str, list[str]]:
    refs = {
        "forms": set(),
        "reports": set(),
        "queries": set(),
        "macros": set(),
        "modules": set(),
        "tables": set()
    }
    
    funcs = data.get("functions") or []
    for fn in funcs:
        fn_refs = fn.get("references")
        if isinstance(fn_refs, dict):
            for k in ["forms", "reports", "queries", "macros", "modules", "tables"]:
                for item in fn_refs.get(k) or []:
                    if isinstance(item, str) and item.strip():
                        val = item.strip()
                        if k == "forms" and "." in val:
                            val = val.split(".")[0]
                            if val.lower().startswith("form_"):
                                val = val[5:]
                        elif k == "modules" and "." in val:
                            val = val.split(".")[0]
                        refs[k].add(val)
                        
    doc_name = (data.get("module_name") or data.get("name") or "").strip()
    if doc_name:
        refs["modules"].discard(doc_name)
        
    return {k: sorted(list(v)) for k, v in refs.items()}


def collect_all_query_references(queries_dir: Path, known_queries_cf: frozenset[str]) -> dict[str, dict[str, list[str]]]:
    query_map = {}
    if not queries_dir.is_dir():
        return query_map
    
    for path in sorted(queries_dir.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                continue
            
            q_name = data.get("query_name") or path.stem
            refs = {
                "forms": set(),
                "reports": set(),
                "queries": set(),
                "macros": set(),
                "modules": set(),
                "tables": set()
            }
            
            tables_list = data.get("tables") or []
            for t in tables_list:
                if not isinstance(t, str):
                    continue
                t_clean = t.strip()
                if not t_clean:
                    continue
                if t_clean.startswith("[") and t_clean.endswith("]"):
                    t_clean = t_clean[1:-1]
                
                if t_clean.casefold() in known_queries_cf:
                    refs["queries"].add(t_clean)
                else:
                    refs["tables"].add(t_clean)
                    
            params = data.get("parameters") or {}
            sql_text = ""
            if isinstance(data.get("query"), dict):
                sql_text = " ".join(str(v) for v in data["query"].values() if isinstance(v, str))
            
            for p_val in params.values():
                if isinstance(p_val, str):
                    for m in re.finditer(r"\[[Ff]orms\]\s*!\s*\[([^\]]+)\]", p_val, re.I):
                        refs["forms"].add(m.group(1))
                        
            if sql_text:
                for m in re.finditer(r"\[[Ff]orms\]\s*!\s*\[([^\]]+)\]", sql_text, re.I):
                    refs["forms"].add(m.group(1))
                    
            refs["queries"].discard(q_name)
            
            query_map[q_name] = {k: sorted(list(v)) for k, v in refs.items()}
        except Exception as e:
            print(f"Error parsing query reference {path.name}: {e}", file=sys.stderr)
            
    return query_map


def collect_all_tables(tables_dir: Path) -> dict[str, dict[str, list[str]]]:
    table_map = {}
    if not tables_dir.is_dir():
        return table_map
    for path in sorted(tables_dir.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                continue
            t_name = data.get("table_name") or path.stem
            table_map[t_name] = {
                "forms": [],
                "reports": [],
                "queries": [],
                "macros": [],
                "modules": [],
                "tables": []
            }
        except Exception:
            pass
    return table_map


def _domain_fn_second_arg_is_query(name: str, known_queries_cf: frozenset[str]) -> bool:
    s = name.strip()
    return bool(s) and s.casefold() in known_queries_cf


def _event_target_looks_like_macro(name: str, known_macros_cf: frozenset[str]) -> bool:
    s = name.strip()
    if not s or s.startswith("["):
        return False
    if s.casefold() in known_macros_cf:
        return True
    if _HEURISTIC_MACRO_NAME.match(s):
        return True
    return s.startswith("A_") and len(s) > 2


def _is_likely_document_module_procedure(proc: str) -> bool:
    p = proc.strip()
    if not p:
        return False
    if p.startswith("Form_") or p.startswith("Report_"):
        return True
    if "_" not in p:
        return False
    suf = p.rsplit("_", 1)[-1]
    return suf in _VBA_CONTROL_EVENT_SUFFIXES


def _declare_handler_lookup_key(handler: str | None) -> str | None:
    if not handler or not isinstance(handler, str):
        return None
    h = handler.strip()
    if not h or " Lib " in h:
        return None
    return h.split(None, 1)[0] or None


def load_procedure_to_module(modules_dir: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not modules_dir.is_dir():
        return mapping
    for path in sorted(modules_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        mod = (raw.get("module_name") or path.stem or "").strip()
        if not mod:
            continue
        for fn in raw.get("functions") or []:
            if not isinstance(fn, dict):
                continue
            key = _declare_handler_lookup_key(fn.get("handler"))
            if not key:
                continue
            ck = key.casefold()
            if ck not in mapping:
                mapping[ck] = mod
    return mapping


def _add_callable_ref(
    name: str,
    document_name: str,
    proc_index: dict[str, str],
    forms: list[str],
    sf: set[str],
    modules: list[str],
    smod: set[str],
) -> None:
    name = name.strip()
    if not name:
        return
    if _is_likely_document_module_procedure(name) and document_name:
        _add_unique(forms, sf, f"{document_name}.{name}")
        return
    mod = proc_index.get(name.casefold())
    if mod:
        _add_unique(modules, smod, f"{mod}.{name}")
    else:
        _add_unique(modules, smod, name)


def _add_unique(bucket: list[str], seen: set[str], val: str) -> None:
    v = val.strip()
    if not v:
        return
    k = v.casefold()
    if k not in seen:
        seen.add(k)
        bucket.append(v)


def extract_vba_references_and_commands(
    code: str,
    document_name: str = "",
    proc_index: dict[str, str] | None = None,
    known_queries_cf: frozenset[str] | None = None,
) -> tuple[dict[str, list[str]], list[str]]:
    if not (code and code.strip()):
        return (
            {
                "forms": [],
                "reports": [],
                "queries": [],
                "macros": [],
                "modules": [],
                "tables": [],
            },
            [],
        )

    proc_map = proc_index or {}
    queries_cf = known_queries_cf or frozenset()
    doc = (document_name or "").strip()
    normalized_code = _strip_vba_comments(code)

    forms: list[str] = []
    reports: list[str] = []
    queries: list[str] = []
    macros: list[str] = []
    modules: list[str] = []
    tables: list[str] = []
    commands: list[str] = []

    sf, sr, sq, sm, smod, st, sc = (
        set(),
        set(),
        set(),
        set(),
        set(),
        set(),
        set(),
    )

    for m in _DCMD_OPEN_FORM.finditer(normalized_code):
        _add_unique(forms, sf, m.group(1))
    for m in _DCMD_CLOSE_FORM.finditer(normalized_code):
        _add_unique(forms, sf, m.group(1))
    for m in _DCMD_OUTPUTTO_FORM.finditer(normalized_code):
        _add_unique(forms, sf, m.group(1))
    for m in _FORMS_REF.finditer(normalized_code):
        _add_unique(forms, sf, m.group(1))
    for m in _FORM_INSTANCE_PROC.finditer(normalized_code):
        _add_unique(forms, sf, f"{m.group(1)}.{m.group(2)}")

    for m in _DCMD_OPEN_REPORT.finditer(normalized_code):
        _add_unique(reports, sr, m.group(1))
    for m in _DCMD_CLOSE_REPORT.finditer(normalized_code):
        _add_unique(reports, sr, m.group(1))
    for m in _DCMD_OUTPUTTO_REPORT.finditer(normalized_code):
        _add_unique(reports, sr, m.group(1))

    for m in _DCMD_OPEN_QUERY.finditer(normalized_code):
        _add_unique(queries, sq, m.group(1))
    for m in _DCMD_OUTPUTTO_QUERY.finditer(normalized_code):
        _add_unique(queries, sq, m.group(1))

    for m in _DCMD_RUN_MACRO.finditer(normalized_code):
        _add_unique(macros, sm, m.group(1))

    for m in _APP_RUN.finditer(normalized_code):
        _add_callable_ref(m.group(1), doc, proc_map, forms, sf, modules, smod)
    for m in _CALL_SUB.finditer(normalized_code):
        _add_callable_ref(m.group(1), doc, proc_map, forms, sf, modules, smod)

    for m in _DCMD_OPEN_TABLE.finditer(normalized_code):
        _add_unique(tables, st, m.group(1))
    for m in _DCMD_OUTPUTTO_TABLE.finditer(normalized_code):
        _add_unique(tables, st, m.group(1))
    for m in _TABLE_IN_EXPR.finditer(normalized_code):
        src = (m.group(3) or "").strip()
        if not src:
            continue
        if _domain_fn_second_arg_is_query(src, queries_cf):
            _add_unique(queries, sq, src)
        else:
            _add_unique(tables, st, src)
    for m in _OPENRECORDSET_STR.finditer(normalized_code):
        src = (m.group(1) or "").strip()
        if not src:
            continue
        if _domain_fn_second_arg_is_query(src, queries_cf):
            _add_unique(queries, sq, src)
        else:
            _add_unique(tables, st, src)

    command_hits: list[tuple[int, str]] = []
    for m in _RUNCOMMAND.finditer(normalized_code):
        command_hits.append((m.start(), m.group(1)))
    for m in _DOCMD_WINDOW.finditer(normalized_code):
        command_hits.append((m.start(), f"DoCmd.{m.group(1)}"))
    command_hits.sort(key=lambda t: t[0])
    for _, cmd in command_hits:
        _add_unique(commands, sc, cmd)

    for m in _VBA_WORD.finditer(normalized_code):
        word = m.group(1)
        w_cf = word.casefold()
        if w_cf in proc_map:
            _add_callable_ref(word, doc, proc_map, forms, sf, modules, smod)

    for m in _SINGLE_WORD_LINE.finditer(normalized_code):
        word = m.group(1)
        if word.lower() in _VB_KEYWORDS:
            continue
        if len(word) < 2:
            continue
        _add_callable_ref(word, doc, proc_map, forms, sf, modules, smod)

    refs = {
        "forms": forms,
        "reports": reports,
        "queries": queries,
        "macros": macros,
        "modules": modules,
        "tables": tables,
    }
    return refs, commands


def _collect_own_vba_handler_names_cf(data: dict[str, Any]) -> frozenset[str]:
    names: set[str] = set()
    for fn in data.get("functions") or []:
        if not isinstance(fn, dict):
            continue
        h = fn.get("handler")
        if not isinstance(h, str):
            continue
        h = h.strip()
        if not h or " Lib " in h:
            continue
        key = h.split(None, 1)[0]
        if key:
            names.add(key.casefold())
    return frozenset(names)


def _resolve_design_event_dependencies(
    target: str,
    proc_index: dict[str, str],
    queries_cf: frozenset[str],
    macros_cf: frozenset[str],
    form_names_cf: frozenset[str],
    report_names_cf: frozenset[str],
    own_handlers_cf: frozenset[str],
) -> list[str]:
    t = target.strip()
    if not t:
        return []
    if t.startswith(("[", "=", "+")):
        return []
    low = t.lower()
    if "event procedure" in low:
        return []
    t_cf = t.casefold()
    if t_cf in own_handlers_cf:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        k = s.casefold()
        if k not in seen:
            seen.add(k)
            out.append(s)

    if _event_target_looks_like_macro(t, macros_cf):
        add(f"macro.{t}")
        return out
    if t_cf in macros_cf:
        add(f"macro.{t}")
        mod_m = proc_index.get(t_cf)
        if mod_m:
            add(f"module.{mod_m}.{t}")
        return out
    if not _is_likely_document_module_procedure(t) and _domain_fn_second_arg_is_query(
        t, queries_cf
    ):
        add(f"query.{t}")
        return out
    if t_cf in form_names_cf:
        add(f"form.{t}")
        return out
    if t_cf in report_names_cf:
        add(f"report.{t}")
        return out
    mod = proc_index.get(t_cf)
    if mod:
        add(f"module.{mod}.{t}")
    return out


def _enrich_event_dict_inline(
    event: Any,
    own_handlers_cf: frozenset[str],
    proc_index: dict[str, str],
    queries_cf: frozenset[str],
    macros_cf: frozenset[str],
    form_names_cf: frozenset[str],
    report_names_cf: frozenset[str],
) -> None:
    if not isinstance(event, dict):
        return
    for prop_key in list(event.keys()):
        val = event[prop_key]
        if isinstance(val, dict) and isinstance(val.get("binding"), str):
            t = val["binding"].strip()
        elif isinstance(val, str):
            t = val.strip()
        else:
            continue
        if not t:
            continue
        if t.casefold() in own_handlers_cf:
            event[prop_key] = t
            continue
        deps = _resolve_design_event_dependencies(
            t,
            proc_index,
            queries_cf,
            macros_cf,
            form_names_cf,
            report_names_cf,
            own_handlers_cf,
        )
        if not deps:
            continue
        if len(deps) == 1:
            event[prop_key] = deps[0]
        else:
            event[prop_key] = deps


def enrich_inline_design_event_dependencies(
    data: dict[str, Any],
    proc_index: dict[str, str],
    queries_cf: frozenset[str],
    macros_cf: frozenset[str],
    form_names_cf: frozenset[str],
    report_names_cf: frozenset[str],
) -> None:
    own_handlers_cf = _collect_own_vba_handler_names_cf(data)
    props = data.get("properties")
    if isinstance(props, dict):
        _enrich_event_dict_inline(
            props.get("event"),
            own_handlers_cf,
            proc_index,
            queries_cf,
            macros_cf,
            form_names_cf,
            report_names_cf,
        )
    for it in data.get("items") or []:
        if not isinstance(it, dict):
            continue
        ip = it.get("properties")
        if isinstance(ip, dict):
            _enrich_event_dict_inline(
                ip.get("event"),
                own_handlers_cf,
                proc_index,
                queries_cf,
                macros_cf,
                form_names_cf,
                report_names_cf,
            )


def enrich_macro_refs(data: dict[str, Any], proc_index: dict[str, str]) -> dict[str, Any]:
    refs = data.get("references")
    if not isinstance(refs, dict):
        return data
    
    vba_calls = refs.get("vba_calls")
    if not isinstance(vba_calls, list):
        return data
    
    modules: list[str] = refs.get("modules", [])
    if not isinstance(modules, list):
        modules = []
    
    seen_modules = {m.casefold() for m in modules}
    
    for val in vba_calls:
        if not isinstance(val, str):
            continue
        # Remove everything starting from first parenthesis or space, e.g., "タイマーを開く()" -> "タイマーを開く"
        func_name = val.split("(")[0].strip()
        if not func_name:
            continue
        
        mod = proc_index.get(func_name.casefold())
        if mod:
            qualified = f"{mod}.{func_name}"
            if qualified.casefold() not in seen_modules:
                seen_modules.add(qualified.casefold())
                modules.append(qualified)
        else:
            if func_name.casefold() not in seen_modules:
                seen_modules.add(func_name.casefold())
                modules.append(func_name)
                
    refs["modules"] = modules
    return data


def enrich_functions_list(
    data: dict[str, Any],
    proc_index: dict[str, str],
    known_queries_cf: frozenset[str],
    known_macros_cf: frozenset[str],
    form_names_cf: frozenset[str],
    report_names_cf: frozenset[str],
) -> dict[str, Any]:
    doc_name = (data.get("name") or data.get("module_name") or "").strip()
    if not doc_name:
        other = (data.get("properties") or {}).get("other") or {}
        doc_name = str(other.get("name") or "").strip()
    funcs = data.get("functions")
    if isinstance(funcs, list):
        for fn in funcs:
            if not isinstance(fn, dict):
                continue
            code = fn.get("code")
            if not isinstance(code, str):
                continue
            refs, cmds = extract_vba_references_and_commands(
                code, doc_name, proc_index, known_queries_cf
            )
            fn["references"] = refs
            fn["code"] = _strip_vba_comments(code)
            if cmds:
                fn["commands"] = cmds
            elif "commands" in fn:
                del fn["commands"]
    data.pop("references_from_design_events", None)
    enrich_inline_design_event_dependencies(
        data,
        proc_index,
        known_queries_cf,
        known_macros_cf,
        form_names_cf,
        report_names_cf,
    )
    return data


def process_json_tree(
    source_dir: Path,
    dest_dir: Path,
    dry_run: bool,
    label: str,
    proc_index: dict[str, str],
    known_queries_cf: frozenset[str],
    known_macros_cf: frozenset[str],
    form_names_cf: frozenset[str],
    report_names_cf: frozenset[str],
) -> tuple[int, int, dict[str, Any]]:
    if not source_dir.is_dir():
        print(f"Skip {label}: not a directory: {source_dir}", file=sys.stderr)
        return 0, 0, {}
    paths = sorted(source_dir.glob("*.json"))
    if not paths:
        print(f"Skip {label}: no .json in {source_dir}", file=sys.stderr)
        return 0, 0, {}
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
    updated = 0
    errors = 0
    refs_dict: dict[str, Any] = {}
    for path in paths:
        out_path = dest_dir / path.name
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                continue
            if label == "macros":
                data = enrich_macro_refs(data, proc_index)
                item_name = data.get("macro_name") or path.stem
                item_refs = collect_macro_references(data)
                refs_dict[item_name] = item_refs
            else:
                data = enrich_functions_list(
                    data,
                    proc_index,
                    known_queries_cf,
                    known_macros_cf,
                    form_names_cf,
                    report_names_cf,
                )
                item_name = data.get("name") or data.get("module_name") or path.stem
                if label == "forms" or label == "reports":
                    item_refs = collect_form_report_references(data, label, known_queries_cf)
                else:  # modules
                    item_refs = collect_module_references(data)
                refs_dict[item_name] = item_refs

            out = json.dumps(data, ensure_ascii=False, indent=4) + "\n"
            if not dry_run:
                out_path.write_text(out, encoding="utf-8")
            updated += 1
            action = "Would write" if dry_run else "Wrote"
            print(f"{action} {label}: {out_path.name}", file=sys.stderr)
        except (OSError, json.JSONDecodeError) as e:
            errors += 1
            print(f"Error {label} {path}: {e}", file=sys.stderr)
    return updated, errors, refs_dict


def generate_graphs_folder(collected_refs: dict[str, dict[str, Any]], out_root: Path):
    graphs_dir = out_root / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)
    
    cat_to_type = {
        "forms": "form",
        "reports": "report",
        "macros": "macro",
        "modules": "module",
        "queries": "query",
        "tables": "table"
    }

    def build_graph(root_name: str, root_cat: str) -> dict:
        nodes = []
        edges = []
        added_nodes = set()
        added_edges = set()

        def add_node(node_id: str, label: str, node_type: str):
            if node_id not in added_nodes:
                added_nodes.add(node_id)
                nodes.append({
                    "data": {
                        "id": node_id,
                        "label": label,
                        "type": node_type
                    }
                })

        def add_edge(source: str, target: str, label: str = ""):
            edge_id = f"{source}__{target}"
            if edge_id not in added_edges:
                added_edges.add(edge_id)
                edges.append({
                    "data": {
                        "id": edge_id,
                        "source": source,
                        "target": target,
                        "label": label
                    }
                })

        queue = [(root_name, root_cat, None, "")]
        visited = set()

        while queue:
            name, cat, parent_id, rel_label = queue.pop(0)
            node_id = f"{cat_to_type[cat]}:{name}"
            
            add_node(node_id, name, cat_to_type[cat])
            
            if parent_id:
                add_edge(parent_id, node_id, rel_label)

            state_key = (name, cat)
            if state_key in visited:
                continue
            visited.add(state_key)

            item_refs = collected_refs.get(cat, {}).get(name, {})
            if not item_refs:
                continue

            for ref_cat in ["forms", "reports", "queries", "macros", "modules", "tables"]:
                ref_items = item_refs.get(ref_cat, [])
                for ref_item in ref_items:
                    label = ""
                    if ref_cat == "queries":
                        label = "recordsource" if cat in ("forms", "reports") else "uses query"
                    elif ref_cat == "tables":
                        label = "reads/writes"
                    elif ref_cat == "modules":
                        label = "calls module"
                    elif ref_cat == "macros":
                        label = "runs macro"
                    elif ref_cat == "forms":
                        label = "opens form"
                    
                    queue.append((ref_item, ref_cat, node_id, label))

        stats = {}
        for node in nodes:
            ntype = node["data"]["type"]
            stats[ntype] = stats.get(ntype, 0) + 1

        return {
            "name": root_name,
            "type": cat_to_type[root_cat],
            "success": True,
            "elements": {
                "nodes": nodes,
                "edges": edges
            },
            "stats": stats
        }

    for cat in ["forms", "reports", "macros", "modules", "queries"]:
        for name in collected_refs.get(cat, {}).keys():
            graph = build_graph(name, cat)
            out_path = graphs_dir / f"{name}.json"
            try:
                out_path.write_text(
                    json.dumps(graph, ensure_ascii=False, indent=4) + "\n",
                    encoding="utf-8"
                )
            except OSError as e:
                print(f"Error writing graph for {name} to {out_path}: {e}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Add references/commands to form & report JSON; "
            "write copies under --output-root (forms_json/ + report_json/)."
        )
    )
    ap.add_argument(
        "--forms-src",
        type=Path,
        default=DEFAULT_FORMS_SRC,
        help=f"Source forms JSON dir (default: {DEFAULT_FORMS_SRC})",
    )
    ap.add_argument(
        "--reports-src",
        type=Path,
        default=DEFAULT_REPORTS_SRC,
        help=f"Source reports JSON dir (default: {DEFAULT_REPORTS_SRC})",
    )
    ap.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Output root; creates forms_json/ and report_json/ (default: {DEFAULT_OUTPUT_ROOT})",
    )
    ap.add_argument(
        "--modules-dir",
        type=Path,
        default=DEFAULT_MODULES_JSON_DIR,
        help=(
            "Directory of module JSON files (handler → module mapping; "
            f"default: {DEFAULT_MODULES_JSON_DIR})"
        ),
    )
    ap.add_argument(
        "--queries-dir",
        type=Path,
        default=DEFAULT_QUERIES_JSON_DIR,
        help=(
            "Directory of query JSON files (query_name → classify D* / OpenRecordset; "
            f"default: {DEFAULT_QUERIES_JSON_DIR})"
        ),
    )
    ap.add_argument(
        "--macros-dir",
        type=Path,
        default=DEFAULT_MACROS_JSON_DIR,
        help=(
            "Directory of macro JSON files (macro_name → design events; "
            f"default: {DEFAULT_MACROS_JSON_DIR})"
        ),
    )
    ap.add_argument(
        "--skip-forms",
        action="store_true",
        help="Do not process forms_src",
    )
    ap.add_argument(
        "--skip-reports",
        action="store_true",
        help="Do not process reports_src",
    )
    ap.add_argument(
        "--skip-modules",
        action="store_true",
        help="Do not process modules_json",
    )
    ap.add_argument(
        "--skip-macros",
        action="store_true",
        help="Do not process macros_src",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only; do not write files",
    )
    args = ap.parse_args()

    out_root: Path = args.output_root
    proc_index = load_procedure_to_module(args.modules_dir)
    known_queries_cf = load_known_query_names_casefold(args.queries_dir)
    known_macros_cf = load_known_macro_names_casefold(args.macros_dir)
    form_names_cf = collect_json_stems_casefold(args.forms_src)
    report_names_cf = collect_json_stems_casefold(args.reports_src)
    total_updated = 0
    total_errors = 0
    collected_refs = {
        "forms": {},
        "reports": {},
        "macros": {},
        "modules": {},
        "queries": {},
        "tables": {}
    }

    if not args.skip_forms:
        u, e, f_refs = process_json_tree(
            args.forms_src,
            out_root / "forms",
            args.dry_run,
            "forms",
            proc_index,
            known_queries_cf,
            known_macros_cf,
            form_names_cf,
            report_names_cf,
        )
        total_updated += u
        total_errors += e
        collected_refs["forms"].update(f_refs)

    if not args.skip_reports:
        u, e, r_refs = process_json_tree(
            args.reports_src,
            out_root / "reports",
            args.dry_run,
            "reports",
            proc_index,
            known_queries_cf,
            known_macros_cf,
            form_names_cf,
            report_names_cf,
        )
        total_updated += u
        total_errors += e
        collected_refs["reports"].update(r_refs)

    if not args.skip_macros:
        u, e, m_refs = process_json_tree(
            args.macros_dir,
            out_root / "macros",
            args.dry_run,
            "macros",
            proc_index,
            known_queries_cf,
            known_macros_cf,
            form_names_cf,
            report_names_cf,
        )
        total_updated += u
        total_errors += e
        collected_refs["macros"].update(m_refs)

    if not args.skip_modules:
        u, e, mod_refs = process_json_tree(
            args.modules_dir,
            out_root / "modules",
            args.dry_run,
            "modules",
            proc_index,
            known_queries_cf,
            known_macros_cf,
            form_names_cf,
            report_names_cf,
        )
        total_updated += u
        total_errors += e
        collected_refs["modules"].update(mod_refs)

    # Compile queries and tables references
    collected_refs["queries"].update(collect_all_query_references(args.queries_dir, known_queries_cf))
    tables_dir = DATABASE_JSON_DIR / "tables"
    if tables_dir.is_dir():
        collected_refs["tables"].update(collect_all_tables(tables_dir))

    # Write reference map JSON and individual graph views
    if not args.dry_run:
        ref_map_path = out_root / "reference_map.json"
        try:
            out_root.mkdir(parents=True, exist_ok=True)
            ref_map_path.write_text(
                json.dumps(collected_refs, ensure_ascii=False, indent=4) + "\n",
                encoding="utf-8"
            )
            print(f"Wrote reference map: {ref_map_path}", file=sys.stderr)
            
            print("Generating individual graphviews...", file=sys.stderr)
            generate_graphs_folder(collected_refs, out_root)
            print("Done generating graphviews.", file=sys.stderr)
        except OSError as e:
            print(f"Error writing reference map or graphs: {e}", file=sys.stderr)

    print(
        f"Done: {total_updated} file(s) processed, {total_errors} error(s). "
        f"Output root: {out_root}",
        file=sys.stderr,
    )
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
