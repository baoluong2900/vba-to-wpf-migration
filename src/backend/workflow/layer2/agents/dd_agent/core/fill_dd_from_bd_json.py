"""
dd_agent/fill_dd_from_bd_json.py — DD1 & DD2 static processing (NO LLM)

DD1: Parse logic_{screen}.jsonl + bd4_bd_final → build dd_form.json skeleton
DD2: Map SQL queries → sheet_4 (SELECT) / sheet_5 (UPDATE/INSERT/DELETE)

CLI usage:
    python -m dd_agent.fill_dd_from_bd_json \
        --logic-jsonl output/bd_flow/bd3_bd_logic/logic_F_Login.jsonl \
        --bd-final output/bd_flow/bd4_bd_final/F_Login.json \
        --sample schema/template/dd_form.json \
        --output output/dd_flow/dd1_dd_skeleton/F_Login.json
"""
from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .fill_utils import (
    collect_pending_refers,
    build_event_map,
    build_steps_placeholder,
    parse_dd_source
)
from utils.paths import safe_child_path

# ── Parse DD Source (D1) ────────────────────────────────────────────────────────












# ── SQL Query mapping ─────────────────────────────────────────────────────────

def _normalize_parameters(params: Any) -> list:
    """Normalize parameters to list format.
    
    DB may store parameters as:
    - list: [{"name": ..., "value": ...}] → returned as-is
    - dict/Object: {"param_name": "value"} → converted to [{"name": "param_name", "value": "value"}]
    - str: "" → returned as []
    """
    if isinstance(params, list):
        return params
    if isinstance(params, dict) and params:
        return [{"name": k, "value": v} for k, v in params.items()]
    return []


def _parse_query_sql_dict(query: dict[str, Any]) -> dict[str, Any]:
    """Parse the nested SQL object from a query item in logic jsonl."""
    raw_sql_str = query.get("sql", "")
    if not raw_sql_str:
        return {}
    # sql field may be JSON string or already a dict
    if isinstance(raw_sql_str, str):
        try:
            val = json.loads(raw_sql_str)
            if isinstance(val, dict):
                return val
            return {"raw_sql": str(val)}
        except json.JSONDecodeError:
            return {"raw_sql": raw_sql_str}
    if isinstance(raw_sql_str, dict):
        return raw_sql_str
    return {}


def _is_update_query(sql_dict: dict[str, Any]) -> bool:
    """Determine if this query is an UPDATE/INSERT/DELETE (sheet_5) vs SELECT (sheet_4)."""
    select_str = str(sql_dict.get("select", "")).upper()
    # SELECT ... INTO means it creates a table → still sheet_5 (side-effect)
    if " INTO " in select_str:
        return True
    # If there's no "select" key but there's "update_table" → sheet_5
    if sql_dict.get("update_table"):
        return True
    # Check raw_sql
    raw = str(sql_dict.get("raw_sql", "")).upper().strip()
    if raw.startswith(("UPDATE ", "INSERT ", "DELETE ")):
        return True
    return False


def _map_query_to_sel_sheet(query: dict[str, Any]) -> dict[str, Any]:
    """Map a SELECT query → sheet_4_sel_query object."""
    sql_dict = _parse_query_sql_dict(query)
    q_name = query.get("query_name", "")

    # Parse SELECT columns
    select_str = sql_dict.get("select", "")
    columns: list[dict[str, str]] = []
    if select_str:
        parts = [p.strip() for p in select_str.split(",")]
        for idx, part in enumerate(parts, 1):
            # Handle AS alias
            alias = ""
            col = part
            as_match = re.search(r"\bAS\s+([\w＿一-龯ぁ-ゔァ-ヶー\[\]]+)", part, re.IGNORECASE)
            if as_match:
                alias = as_match.group(1).strip("[]")
                col = part[: as_match.start()].strip()
            # Simplify table.col
            table_name = ""
            col_name = col
            if "." in col:
                parts2 = col.split(".", 1)
                table_name = parts2[0].strip("[] ")
                col_name = parts2[1].strip("[] ")

            columns.append(
                {
                    "no": str(idx),
                    "table_name": table_name,
                    "column_name": col_name,
                    "alias": alias,
                    "confirm_item": "",
                }
            )

    return {
        "query_purpose": "",
        "query_name": q_name,
        "parameters": _normalize_parameters(query.get("parameters")),
        "sql": {
            "select": [
                {"expression": p.strip(), "confirm_item": ""}
                for p in select_str.split(",")
                if p.strip()
            ],
            "from": sql_dict.get("from", ""),
            "join": [],
            "where": sql_dict.get("where", ""),
            "group_by": sql_dict.get("group_by", "なし"),
            "order_by": sql_dict.get("order_by", "なし"),
        },
        "columns": columns,
        "raw_sql": sql_dict.get("raw_sql", ""),
    }


def _map_query_to_upd_sheet(query: dict[str, Any]) -> dict[str, Any]:
    """Map an UPDATE/INSERT/DELETE/SELECT INTO query → sheet_5_upd_query object."""
    sql_dict = _parse_query_sql_dict(query)
    q_name = query.get("query_name", "")

    # Try to detect table
    update_table = sql_dict.get("update_table", "")
    select_str = str(sql_dict.get("select", ""))
    raw = sql_dict.get("raw_sql", "")

    # If SELECT INTO → target table is after INTO
    if not update_table and " INTO " in select_str.upper():
        m = re.search(r"INTO\s+([\w＿一-龯\[\]]+)", select_str, re.IGNORECASE)
        if m:
            update_table = m.group(1).strip("[]")

    # Reconstruct set_columns from SELECT expression when it's a SELECT INTO
    set_columns: list[dict[str, str]] = []
    if select_str and " INTO " in select_str.upper():
        # Parse columns from the SELECT part before INTO
        before_into = re.split(r"\s+INTO\s+", select_str, flags=re.IGNORECASE)[0]
        for idx, part in enumerate(before_into.split(","), 1):
            part = part.strip()
            as_match = re.search(r"\bAS\s+([\w＿一-龯\[\]]+)", part, re.IGNORECASE)
            col = as_match.group(1).strip("[]") if as_match else part.strip("[] ")
            expr = part[: as_match.start()].strip() if as_match else part
            set_columns.append(
                {
                    "column": col,
                    "value_expression": expr,
                    "confirm_item": "",
                }
            )

    return {
        "query_purpose": "",
        "query_name": q_name,
        "parameters": _normalize_parameters(query.get("parameters")),
        "sql": {
            "update_table": update_table,
            "set_columns": set_columns,
            "where_condition": {
                "key_column": sql_dict.get("where", ""),
                "parameter_symbol": "",
                "confirm_item": "",
            },
        },
        "raw_sql": raw or select_str,
    }


# ── BD Final helpers ──────────────────────────────────────────────────────────




def _build_parameter_info_from_bd(bd_final: dict[str, Any]) -> list[dict[str, str]]:
    """Build sheet_2_overview.parameter_info from BD sheet_3 items."""
    items = (bd_final.get("sheet_3_screen_edit") or {}).get("items") or []
    result: list[dict[str, str]] = []
    for idx, item in enumerate(items, 1):
        attr = item.get("item_attribute", "")
        # Skip structural section rows (roman numerals)
        if not attr:
            continue
        result.append(
            {
                "no": str(idx),
                "io": "I/O",
                "item_name": item.get("logical_name", ""),
                "symbol_name": item.get("logical_name", ""),
                "data_type": attr,
                "total_digits": item.get("attribute_digits", ""),
                "decimal_digits": "",
                "required": item.get("required", ""),
                "notes": item.get("source_field_or_fixed_value", ""),
            }
        )
    return result


# ── Build skeleton (D1) ───────────────────────────────────────────────────────

def _build_dd_skeleton(
    logic_items: list[dict[str, Any]],
    bd_final: dict[str, Any],
    sample: dict[str, Any],
    category: str = "screen",
) -> dict[str, Any]:
    """Build full DD skeleton closely following the dd_form.json structure."""

    out = deepcopy(sample)
    screen_id = bd_final.get("screen_id", "")
    screen_name = bd_final.get("screen_name", "")

    # Meta
    out["screen_id"] = screen_id
    out["screen_name"] = screen_name
    out["system_name"] = bd_final.get("system_name", "")
    out["subsystem_name"] = bd_final.get("subsystem_name", "")
    out["author"] = bd_final.get("author", "")
    out["created_date"] = bd_final.get("created_date", "")
    out["updated_by"] = bd_final.get("updated_by", "")
    out["updated_date"] = bd_final.get("updated_date", "")

    # sheet_1: empty change history
    out["sheet_1_change_history"] = {"sheet_name": "Change History", "data": []}

    # sheet_2_overview
    param_info = _build_parameter_info_from_bd(bd_final) if bd_final.get("sheet_3_screen_edit") else []
    layout = bd_final.get("sheet_2_layout") or {}

    
    # Check if this is a report (screen_id usually starts with R_ or is explicitly marked)
    is_report = screen_id.startswith("R_") or "report" in bd_final
    
    overview: dict[str, Any] = {
        "sheet_name": "Overview Spec",
        "description": layout.get("description", ""),
        "parameter_info": param_info if param_info else [],
        "grouping_sorting_pagebreak": {
            "sort_fields": [],
            "group_fields": [],
        }
    }
    # Include constants and types in special notes for Modules
    extra_notes = []
    first_item_data = (logic_items[0].get("_raw_module_data") or {}) if logic_items else {}
    constants = (bd_final.get("module") or {}).get("constants") or first_item_data.get("constants") or []

    if constants:
        extra_notes.append("【定数定義】")
        for c in constants:
            extra_notes.append(f"  - {c.get('name')}: {c.get('value')}")
    
    user_types = (bd_final.get("module") or {}).get("user_types") or first_item_data.get("user_types") or []

    if user_types:
        extra_notes.append("【ユーザー定義型】")
        for t in user_types:
            fields = ", ".join([f"{f.get('name')} as {f.get('type')}" for f in t.get("fields", [])])
            extra_notes.append(f"  - {t.get('name')}: ({fields})")

    if is_report:
        overview["special_print_notes"] = (layout.get("constraints", "") + "\n" + "\n".join(extra_notes)).strip()
    else:
        overview["special_notes"] = (layout.get("constraints", "") + "\n" + "\n".join(extra_notes)).strip()
        
    out["sheet_2_overview"] = overview



    # sheet_3_detail_specs: 1 entry per logic_item module
    event_map = build_event_map(bd_final)
    details: list[dict[str, Any]] = []
    for item in logic_items:
        mid = item.get("module_id", "")
        code = item.get("code", "")
        bd_ev = event_map.get(mid, {})
        
        # logical_name from BD screen_edit items if possible
        # but screen_edit usually refers to UI controls.
        # For modules, we use the title from the event map.
        m_name = bd_ev.get("title", "") or item.get("title", "") or mid

        refers = collect_pending_refers(code)
        if "macro_actions" in item:
            steps = []
            for idx, act in enumerate(item["macro_actions"], 1):
                name = act.get("action", "Action")
                steps.append({
                    "step": f"{idx}. {name}",
                    "detail": act
                })
        else:
            steps = build_steps_placeholder(mid, refers)

        detail_obj = {
            "test_item_count": 0,
            "test_completed_count": 0,
            "steps": steps,
            "pending_refers": refers,
            "event_trigger": bd_ev.get("event_trigger", ""),
            "event_content": bd_ev.get("event_content", ""),
        }

        
        # Use the Fxxx ID if available from BD
        final_mid = bd_ev.get("module_id") or mid
        
        if is_report:
            detail_obj["report_scope_name"] = m_name
        else:
            detail_obj["module_id"] = final_mid
            detail_obj["module_name"] = m_name
            # User requested simplified pattern: Detailed Spec_F001
            detail_obj["sheet_name_pattern"] = f"Detailed Spec_{final_mid}"

        details.append(detail_obj)


    if category == "macro":
        macro_details = []
        for idx, item in enumerate(logic_items, 0):  # Start at F000 for macros
            vba_handler = item.get("module_id", "")
            m_name = item.get("title", "") or vba_handler

            # Generate sequential Fxxx ID starting at F000 for macros
            f_id = vba_handler if re.match(r"^F\d{3}", vba_handler) else f"F{idx:03d}"

            macro_details.append({
                "sheet_name_pattern": f"Detailed Spec_{f_id}",
                "module_id": f_id,
                "module_name": m_name,
                "key_id": vba_handler,
                "key_name": m_name,
                "steps": []
            })
            # Update logic_item so query naming (F000_SelQuery01) works correctly
            item["module_id"] = f_id

        out["sheet_2_detail"] = macro_details
        out.pop("sheet_2_overview", None)
        out.pop("sheet_3_detail_specs", None)

        out["sheet_4_sel_query_templates"] = []
        out["sheet_5_upd_query_templates"] = []

    elif category == "screen":
        out["sheet_3_detail_specs"] = details
        out["sheet_4_sel_query_templates"] = []
        out["sheet_5_upd_query_templates"] = []
    elif category == "common":
        module_details = []
        for idx, item in enumerate(logic_items, 1):
            vba_handler = item.get("module_id", "")
            m_name = item.get("title", "") or vba_handler
            
            # Generate sequential Fxxx ID if not already mapped
            f_id = vba_handler if re.match(r"^F\d{3}", vba_handler) else f"F{idx:03d}"
            
            module_details.append({
                "sheet_name_pattern": f"Detailed Spec_{f_id}",
                "module_id": f_id,
                "module_name": m_name,
                "key_id": vba_handler,
                "key_name": m_name,
                "steps": []
            })
            # Update logic_item so query naming can use the Fxxx ID
            item["module_id"] = f_id
        out["sheet_2_detail"] = module_details
        out.pop("sheet_3_detail_specs", None)
        out.pop("sheet_2_overview", None)

        
        out["sheet_4_sel_query_templates"] = []
        out["sheet_5_upd_query_templates"] = []
    else:
        out["sheet_2_overview"]["details"] = details


    return out



# ── Fill query sheets (D2) ────────────────────────────────────────────────────

def _fill_query_sheets(
    logic_items: list[dict[str, Any]],
    skeleton: dict[str, Any],
    repo: Any = None
) -> dict[str, Any]:
    """D2: Map SQL queries from logic items → sheet_4 / sheet_5."""
    sel_queries: list[dict[str, Any]] = []
    upd_queries: list[dict[str, Any]] = []
    query_counts: dict[str, dict[str, int]] = {} # mid -> {'sel': N, 'upd': M}
    seen_queries: set[str] = set()

    for item in logic_items:
        mid = item.get("module_id", "")
        if mid not in query_counts:
            query_counts[mid] = {"sel": 0, "upd": 0}

        for query in item.get("queries") or []:
            q_name = query.get("query_name", "")
            if q_name in seen_queries:
                continue
            seen_queries.add(q_name)

            sql_dict = _parse_query_sql_dict(query)
            
            # If SQL is mostly empty and we have a repo, try to fetch from MongoDB
            is_sql_empty = not sql_dict or (not sql_dict.get("select") and not sql_dict.get("update_table"))
            if is_sql_empty and repo and q_name:
                try:
                    from db.query_dd import get_dd_code_json_query_raw
                    q_doc = get_dd_code_json_query_raw(repo, q_name)
                    if q_doc:
                        sql_logic = q_doc.get("query") or q_doc.get("sql_logic")
                        raw_sql = q_doc.get("raw_sql")
                        if sql_logic:
                            query["sql"] = sql_logic
                        elif raw_sql:
                            query["sql"] = raw_sql
                        
                        if q_doc.get("parameters"):
                            # Normalize: DB may return dict {name: value} or list
                            query["parameters"] = _normalize_parameters(q_doc["parameters"])
                            
                        sql_dict = _parse_query_sql_dict(query)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("Could not fetch query %s from DB: %s", q_name, e)

            if _is_update_query(sql_dict):
                query_counts[mid]["upd"] += 1
                idx = query_counts[mid]["upd"]
                upd_obj = _map_query_to_upd_sheet(query)
                upd_obj["_source_module"] = mid
                # Standard naming: F001_UpdQuery01
                q_display = f"{mid}_UpdQuery{idx:02d}"
                upd_obj["sheet_name_pattern"] = q_display
                upd_obj["query_display"] = q_display
                upd_queries.append(upd_obj)
            else:
                query_counts[mid]["sel"] += 1
                idx = query_counts[mid]["sel"]
                sel_obj = _map_query_to_sel_sheet(query)
                sel_obj["_source_module"] = mid
                # Standard naming: F001_SelQuery01
                q_display = f"{mid}_SelQuery{idx:02d}"
                sel_obj["sheet_name_pattern"] = q_display
                sel_obj["query_display"] = q_display
                sel_queries.append(sel_obj)

    # Canonical keys for queries: sheet_4_sel and sheet_5_upd
    # Legacy keys (from old templates or Modules template): sheet_3_sel and sheet_4_upd

    # 1. Fill/Migrate SELECT queries
    if "sheet_4_sel_query_templates" in skeleton or "sheet_3_sel_query_templates" in skeleton:
        skeleton["sheet_4_sel_query_templates"] = sel_queries
        skeleton.pop("sheet_3_sel_query_templates", None)
        if not sel_queries:
            skeleton.pop("sheet_4_sel_query_templates", None)

    # 2. Fill/Migrate UPDATE/INSERT/DELETE queries
    if "sheet_5_upd_query_templates" in skeleton or "sheet_4_upd_query_templates" in skeleton:
        skeleton["sheet_5_upd_query_templates"] = upd_queries
        skeleton.pop("sheet_4_upd_query_templates", None)
        if not upd_queries:
            skeleton.pop("sheet_5_upd_query_templates", None)

    # ── Track query mappings (Q_Name -> [SheetName]) to inject as hints ──
    # This ensures the LLM knows the correct reference format [F001_SelQuery01]
    query_name_to_sheet = {}
    query_name_to_info = {}
    for q in sel_queries:
        if q.get("query_name") and q.get("query_display"):
            query_name_to_sheet[q["query_name"]] = f"[{q['query_display']}]"
            query_name_to_info[q["query_name"]] = {"type": "SELECT", "parameters": q.get("parameters", [])}
    for q in upd_queries:
        if q.get("query_name") and q.get("query_display"):
            query_name_to_sheet[q["query_name"]] = f"[{q['query_display']}]"
            query_name_to_info[q["query_name"]] = {"type": "UPDATE", "parameters": q.get("parameters", [])}

    # Map of module_id -> list of query mappings
    module_query_mappings = {}
    for item in logic_items:
        mid = item.get("module_id", "")
        mappings = []
        for query in item.get("queries") or []:
            qn = query.get("query_name")
            if qn in query_name_to_sheet:
                s_name = query_name_to_sheet[qn].strip("[]")
                q_info = query_name_to_info.get(qn, {})
                params = q_info.get("parameters")
                mappings.append({
                    "sheet_name": s_name,
                    "logic_query_name": qn,
                    "type": q_info.get("type", "UNKNOWN"),
                    "parameters": params if isinstance(params, list) else []
                })
        if mappings:
            module_query_mappings[mid] = mappings

    # Inject query_mappings into skeleton details
    s_details = []
    if "sheet_3_detail_specs" in skeleton:
        s_details = skeleton["sheet_3_detail_specs"]
    elif "sheet_2_detail" in skeleton:
        s_details = skeleton["sheet_2_detail"]

    if isinstance(s_details, list):
        for detail in s_details:
            if not isinstance(detail, dict):
                continue
            mid = detail.get("module_id") or detail.get("key_id") or detail.get("module_name")
            if mid in module_query_mappings:
                detail["query_mappings"] = module_query_mappings[mid]

    # ── Fallback: add UpdQuery stubs for tables referenced directly in macro XML
    # (DCount / DLookup conditions) not already covered by an explicit upd_query.
    ref_tables: list[str] = []
    for item in logic_items:
        refs = item.get("references") or {}
        if isinstance(refs, dict):
            ref_tables.extend(str(t) for t in (refs.get("tables") or []) if t)

    if ref_tables:
        upd_key = "sheet_5_upd_query_templates"
        if upd_key not in skeleton:
            skeleton[upd_key] = []
        existing_upd: list[dict] = skeleton[upd_key]
        covered_tables: set[str] = set()
        for q in existing_upd:
            if not isinstance(q, dict):
                continue
            sql = q.get("sql") or {}
            if isinstance(sql, dict):
                for k in ("update_table", "target_table"):
                    t = sql.get(k)
                    if t:
                        covered_tables.add(str(t))
            for k in ("table_name", "table_physical_name"):
                t = q.get(k)
                if t:
                    covered_tables.add(str(t))
        seen_ref: set[str] = set(covered_tables)
        for tbl in ref_tables:
            if tbl in seen_ref:
                continue
            seen_ref.add(tbl)
            existing_upd.append({
                "query_name": tbl,
                "query_purpose": f"テーブル『{tbl}』への参照",
                "table_name": tbl,
                "table_physical_name": tbl,
                "parameters": "",
                "sql": {},
                "columns": [],
                "_synthesized_from_references": True,
            })

    return skeleton



# ── Public API (called by dd_service.py) ─────────────────────────────────────

def get_dd_skeleton(
    screen_name: str,
    dd_code_json_path: Path,
    bd_final_path: Path,
    template_path: Path,
    output_dir: Path,
    category: str = "screen",
) -> dict[str, Any]:

    """
    Main entry point for D2: Mapping.
    """
    if not dd_code_json_path.exists():
        raise FileNotFoundError(f"D1 dd_code_json not found: {dd_code_json_path}")
    
    # Load BD final if exists, else create dummy
    if bd_final_path.exists():
        with open(bd_final_path, encoding="utf-8") as f:
            bd_final = json.load(f)
    else:
        bd_final = {"screen_id": screen_name, "screen_name": screen_name}


    # Build D2 skeleton
    logic_items = parse_dd_source(dd_code_json_path)
    try:
        from utils.template_loader import load_template
    except ImportError:
        from workflow.layer2.utils.template_loader import load_template
    sample = load_template(template_path.name)
    if not sample:
        sample = json.loads(template_path.read_text(encoding="utf-8"))

    # ── FIX: Load D1 skeleton to get ALL VBA procedures ──────────────────
    import logging
    logger = logging.getLogger(__name__)
    
    d1_vba_map = {}
    try:
        with open(dd_code_json_path, encoding="utf-8") as f:
            d1_data = json.load(f)
            
            # Determine procedure source based on category
            procedures = []
            if category == "common":
                module_data = d1_data.get("module", {})
                # Try both 'procedures' and 'functions' (D1 skeleton uses 'functions')
                procedures = module_data.get("procedures", []) or module_data.get("functions", [])
            elif category == "macro":
                macro_data = d1_data.get("macro", {})
                procedures = macro_data.get("actions", []) or macro_data.get("steps", [])
            else:
                form_or_report = d1_data.get("form") or d1_data.get("report") or {}
                procedures = form_or_report.get("vba_procedures", [])
            
            for proc in procedures:
                # Skip Declare Functions (Windows API declarations)
                if proc.get("type", "").lower() == "declare function":
                    continue
                    
                handler = proc.get("handler", "") or proc.get("name", "")
                if handler:
                    d1_vba_map[handler] = proc
                    from .fill_utils import normalize_vba_name
                    d1_vba_map[normalize_vba_name(handler)] = proc
                    
            logger.info("[DD Module/Macro] Loaded %d procedures from D1", len(d1_vba_map))
    except Exception as e:
        logger.warning("[DD Module/Macro] Could not load D1 procedures: %s", e)
    
    # Ensure ALL procedures from D1 are in logic_items
    from .fill_utils import normalize_vba_name
    existing_handlers = set(item.get("module_id", "") for item in logic_items)
    existing_normalized = set(normalize_vba_name(h) for h in existing_handlers)
    
    for handler, proc in d1_vba_map.items():
        norm_handler = normalize_vba_name(handler)
        if handler not in existing_handlers and norm_handler not in existing_normalized:
            logger.info("[DD Module/Macro] Adding missing procedure: %s", handler)
            logic_items.append({
                "module_id": handler,
                "title": handler,
                "code": proc.get("code", ""),
                "queries": [],
                "references": proc.get("references", {}),
                "_source": "d1_vba"
            })
    # ──────────────────────────────────────────────────────────────────────

    # ── MACRO FALLBACK: if still no logic_items, build one from raw_xml ──
    if category == "macro" and not logic_items:
        try:
            with open(dd_code_json_path, encoding="utf-8") as _f:
                _d1 = json.load(_f)
            macro_data = _d1.get("macro", {})
            macro_name = macro_data.get("name", screen_name)
            raw_xml   = macro_data.get("raw_xml", "")
            references = macro_data.get("references", {})
            logger.info("[DD Macro] No parsed actions found — creating single fallback item from raw_xml for: %s", macro_name)
            # Populate queries from references.queries (if any SQL query names listed)
            # _fill_query_sheets will fetch their SQL from DB and generate F000_SelQuery01 etc.
            ref_query_names = references.get("queries", [])
            fallback_queries = [
                {"query_name": q, "sql": {}, "parameters": [], "query_type": "UNKNOWN"}
                for q in ref_query_names if q
            ]
            logic_items.append({
                "module_id": macro_name,
                "title": macro_name,
                "code": raw_xml,          # raw XML is the "code" sent to LLM
                "queries": fallback_queries,
                "references": references,
                "_source": "macro_raw_xml_fallback"
            })
        except Exception as _e:
            logger.warning("[DD Macro] Could not build macro fallback: %s", _e)
    # ──────────────────────────────────────────────────────────────────────

    # Map VBA procedure names to Fxxx IDs before processing
    event_map = build_event_map(bd_final)
    for item in logic_items:
        mid = item.get("module_id", "")
        bd_ev = event_map.get(mid, {})
        if bd_ev.get("module_id"):
            item["module_id"] = bd_ev["module_id"]

    try:
        from db.layer1_repo import Layer1Repo
        repo = Layer1Repo()
    except Exception:
        repo = None

    skeleton = _build_dd_skeleton(logic_items, bd_final, sample, category=category)
    skeleton = _fill_query_sheets(logic_items, skeleton, repo)


    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = safe_child_path(output_dir, screen_name)

        out_file.write_text(
            json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return skeleton, logic_items


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build DD skeleton (DD2) from DD1 source + BD final.")
    parser.add_argument("--dd-source", type=Path, required=True, help="Path to dd1_dd_source/{screen}.json")
    parser.add_argument("--bd-final", type=Path, required=True, help="Path to bd4_bd_final/{screen}.json")
    parser.add_argument("--sample", type=Path, help="Path to dd_form.json template")
    parser.add_argument("--output", type=Path, help="Output path for skeleton JSON")
    args = parser.parse_args()

    proj_root = Path(__file__).resolve().parent.parent.parent.parent
    sample_path = args.sample or (proj_root / "schema" / "template" / "dd_form.json")
    output_path = args.output or (proj_root / "output" / "dd_flow" / "dd2_dd_mapping" / "output.json")

    logic_items = parse_dd_source(args.dd_source)
    bd_final = json.loads(args.bd_final.read_text(encoding="utf-8"))
    try:
        from utils.template_loader import load_template
    except ImportError:
        from workflow.layer2.utils.template_loader import load_template
    sample = load_template(sample_path.name)
    if not sample:
        sample = json.loads(sample_path.read_text(encoding="utf-8"))

    # Map VBA procedure names to Fxxx IDs before processing
    event_map = build_event_map(bd_final)
    for item in logic_items:
        mid = item.get("module_id", "")
        bd_ev = event_map.get(mid, {})
        if bd_ev.get("module_id"):
            item["module_id"] = bd_ev["module_id"]

    skeleton = _build_dd_skeleton(logic_items, bd_final, sample)
    skeleton = _fill_query_sheets(logic_items, skeleton)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
