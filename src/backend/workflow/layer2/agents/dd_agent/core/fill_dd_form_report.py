"""
dd_agent/fill_dd_form_report.py — D1 & D2 processing for Forms/Reports (Advanced SQL logic)
"""
from __future__ import annotations

import argparse
import json
import re
import logging
from pathlib import Path
from typing import Any, List, Dict, Optional
from copy import deepcopy

from .fill_utils import (
    parse_dd_source,
    extract_vba_dim_vars,
    collect_pending_refers,
    build_event_map,
    build_steps_placeholder,
    normalize_vba_name,
    find_queries_for_code,
    normalize_query_name
)
from .query_mapper import TableResolver, _load_table_config, _fill_query_sheets, parse_aliases, _get_mapped_query
from db.layer1_repo import Layer1Repo
from db.query_dd import get_dd_code_json_table

logger = logging.getLogger(__name__)

# ── Skeleton & Mapping Flow ──────────────────────────────────────────────────

def map_db_type_to_csharp(db_type: str, total_digits: str = "", decimal_digits: str = "") -> str:
    """Map database data types to C# types."""
    db_type = (db_type or "").upper()
    if any(x in db_type for x in ["VARCHAR", "CHAR", "TEXT", "CLOB", "STRING"]):
        return "string"
    if "NUMBER" in db_type or "DECIMAL" in db_type or "NUMERIC" in db_type:
        if decimal_digits and decimal_digits != "0":
            return "decimal"
        try:
            p = int(total_digits) if total_digits else 0
            if p > 9:
                return "long"
        except ValueError:
            pass
        return "int"
    if "INT" in db_type:
        return "int"
    if "DATE" in db_type or "TIME" in db_type:
        return "DateTime"
    if "FLOAT" in db_type or "DOUBLE" in db_type:
        return "double"
    if "BIT" in db_type or "BOOL" in db_type:
        return "bool"
    return "string"

def _extract_parameter_info(logic_items: list[dict], repo: Any, all_queries: list[dict] | None = None) -> list[dict]:
    """Extract metadata for parameters used in queries by resolving them against table columns."""
    params_metadata = []
    seen_params = set()
    table_cache = {}

    import logging
    logger.info(f"[DEBUG] Extracting parameters from {len(logic_items)} logic items")
    
    # Collect queries from logic_items
    queries_to_process = []
    for item in logic_items:
        for q in item.get("queries", []):
            queries_to_process.append(q)
            
    # Also collect from all_queries to make sure orphan queries are processed
    if all_queries:
        seen_qnames = set(normalize_query_name(q.get("query_name") or q.get("name", "")) for q in queries_to_process if q.get("query_name") or q.get("name"))
        for aq in all_queries:
            aqname = aq.get("query_name") or aq.get("name")
            if aqname and normalize_query_name(aqname) not in seen_qnames:
                queries_to_process.append({
                    "query_name": aqname,
                    "sql": aq.get("sql_logic") or aq.get("sql") or {},
                    "parameters": aq.get("parameters", []),
                })

    for q in queries_to_process:
        logger.info(f"[DEBUG] Found query: {q.get('query_name')} with params: {q.get('parameters')} and sql: {q.get('sql')}")
        params = q.get("parameters")
        
        # Normalize parameters to a dict
        params_dict = {}
        if isinstance(params, list):
            for p in params:
                if isinstance(p, dict):
                    k = p.get("key") or (next(iter(p.keys())) if p.keys() else None)
                    if k:
                        v = p.get("value") or p.get(k)
                        params_dict[k] = v
                elif isinstance(p, str) and p.strip():
                    params_dict[p.strip()] = ""
        elif isinstance(params, dict):
            params_dict = params.copy()
        elif isinstance(params, str) and params.strip():
            for p in params.split(","):
                p = p.strip()
                if p:
                    params_dict[p] = ""
        
        sql = q.get("sql", "")
        from_clause = ""
        if isinstance(sql, dict):
            from_clause = str(sql.get("from") or "")
            if not from_clause and sql.get("update"):
                from_clause = sql.get("update")
            sql_str = json.dumps(sql, ensure_ascii=False)
        else:
            sql_str = str(sql)
            # Try to extract FROM or UPDATE from raw string if possible
            m_from = re.search(r'(?i)\bFROM\b\s+(.*?)(\bWHERE\b|\bGROUP BY\b|\bORDER BY\b|$)', sql_str)
            if m_from:
                from_clause = m_from.group(1).strip()
            else:
                m_upd = re.search(r'(?i)\bUPDATE\b\s+(.*?)(\bSET\b|$)', sql_str)
                if m_upd:
                    from_clause = m_upd.group(1).strip()

        alias_map = parse_aliases(from_clause)
        if isinstance(sql, dict) and "join" in sql and isinstance(sql["join"], list):
            for j in sql["join"]:
                if isinstance(j, dict) and j.get("table"):
                    alias_map.update(parse_aliases(j["table"]))
        
        # Auto-extract parameters from SQL
        found_p = re.findall(r'[:@]([a-zA-Z0-9_＿一-龯ぁ-ゔァ-ヶー]+)', sql_str)
        for p in found_p:
            if p not in params_dict:
                params_dict[p] = ""

        if not params_dict:
            continue

        for symbol, expression in params_dict.items():
            if symbol in seen_params:
                continue
            
            meta = {
                "no": str(len(params_metadata) + 1),
                "io": "I",
                "item_name": symbol,
                "symbol_name": "",
                "data_type": "",
                "total_digits": "",
                "decimal_digits": "",
                "required": "",
                "notes": str(expression)
            }

            # Try to find table/column comparison in SQL to resolve metadata
            pattern = r"\[?([A-Za-z0-9_＿]+)\]?\.\[?([A-Za-z0-9_＿]+)\]?[^=]*=\s*:" + re.escape(symbol)
            match = re.search(pattern, sql_str, re.IGNORECASE)
            if not match:
                 pattern = r":" + re.escape(symbol) + r"\s*=\s*\[?([A-Za-z0-9_＿]+)\]?\.\[?([A-Za-z0-9_＿]+)\]?"
                 match = re.search(pattern, sql_str, re.IGNORECASE)
            
            if match:
                tbl_name = match.group(1)
                col_name = match.group(2)
                
                # Resolve alias
                tbl_name = alias_map.get(tbl_name, tbl_name)
                
                if tbl_name not in table_cache:
                    try:
                        table_cache[tbl_name] = get_dd_code_json_table(repo, tbl_name)
                    except Exception:
                        table_cache[tbl_name] = None
                
                tbl_info = table_cache[tbl_name]
                if tbl_info:
                    for col in tbl_info.get("columns", []):
                        if col.get("physical_name") == col_name:
                            db_type = col.get("data_type", "VARCHAR2")
                            length = str(col.get("length", ""))
                            t_digits, d_digits = "", ""
                            if "," in length:
                                parts = length.split(",")
                                t_digits = parts[0]
                                d_digits = parts[1]
                            else:
                                t_digits = length
                            
                            meta["data_type"] = map_db_type_to_csharp(db_type, t_digits, d_digits)
                            meta["total_digits"] = t_digits
                            meta["decimal_digits"] = d_digits
                            meta["required"] = "o" if col.get("required") == "Y" else ""
                            break
            
            params_metadata.append(meta)
            seen_params.add(symbol)
                
    return params_metadata

def _build_dd_skeleton(logic_items: list[dict[str, Any]], bd_final: dict[str, Any], sample: dict[str, Any], all_queries: list[dict] | None = None) -> dict[str, Any]:
    out = deepcopy(sample)
    screen_id, screen_name = bd_final.get("screen_id", ""), bd_final.get("screen_name", "")
    out.update({"screen_id": screen_id, "screen_name": screen_name})
    for key in ["system_name", "subsystem_name", "author", "created_date", "updated_by", "updated_date"]:
        out[key] = bd_final.get(key, "")

    # Overview Sheet
    repo = Layer1Repo()
    layout = bd_final.get("sheet_2_layout") or {}
    out["sheet_1_change_history"] = {"sheet_name": "変更履歴", "data": []}
    _param_info = _extract_parameter_info(logic_items, repo, all_queries=all_queries) if repo else []
    _overview: dict = {
        "sheet_name": "概要仕様書",
        "description": layout.get("description", ""),
        "grouping_sorting_pagebreak": {"sort_fields": [], "group_fields": []},
        "special_notes": layout.get("constraints", ""),
    }
    _overview["parameter_info"] = _param_info
    out["sheet_2_overview"] = _overview


    # sheet_3_detail_specs: driven by BD events (1 detail per event, matching module/macro pattern)
    bd_events: list[dict] = layout.get("events") or []
    # Trigger WatchFiles reload

    # ── Load S3 BD Logic result for event_content ─────────────────────────
    s3_logic_map: dict[str, dict] = {}
    from pathlib import Path
    _OUTPUT_BASE = Path(__file__).resolve().parent.parent / "output"
    s3_logic_path = _OUTPUT_BASE / "bd_flow" / "s3_bd_logic" / f"logic_{screen_id}_result.json"
    if s3_logic_path.exists():
        try:
            import json
            s3_results = json.loads(s3_logic_path.read_text(encoding="utf-8"))
            for r in s3_results:
                mid = r.get("module_id", "")
                if mid:
                    s3_logic_map[mid] = r
            logger.info("[DD Skeleton] Loaded S3 BD logic result: %d entries", len(s3_logic_map))
        except Exception as e:
            logger.warning("[DD Skeleton] Could not load S3 logic result: %s", e)

    # ── Resolve RecordSource name for event_content ───────────────────────
    record_sources: list[dict] = layout.get("record_sources") or []
    rs_name_raw = record_sources[0].get("query_name", "") if record_sources else ""
    rs_name = rs_name_raw or screen_id
    screen_edit_items: list = layout.get("screen_edit_items") or []

    # event_map now handles both module_id and VBA handler names
    event_map = build_event_map(bd_final)

    details = []
    for item in logic_items:
        raw_mid = item.get("module_id", "")
        code = item.get("code", "")
        
        # Look up event by module_id (Fxxx) or VBA handler name
        bd_ev = event_map.get(raw_mid, {})
        
        # Resolved module_id (Fxxx) and title from BD
        mid = bd_ev.get("module_id", "") or raw_mid
        m_name = bd_ev.get("title", "") or item.get("title", "") or raw_mid
        
        # Ensure logic_item uses the resolved module_id (Fxxx)
        item["module_id"] = mid

        if raw_mid == "RecordSource":
            continue
        else:
            input_vars = extract_vba_dim_vars(code)
            refers = collect_pending_refers(code)
            steps = []
            if "macro_actions" in item:
                for idx, act in enumerate(item.get("macro_actions", []), 1):
                    name = act.get("action", "Action")
                    steps.append({
                        "step": f"{idx}. {name}",
                        "detail": act
                    })
            else:
                steps = build_steps_placeholder(mid, refers)
                
            # Use S3 BD Logic event_content if available, otherwise fall back to BD event
            s3_entry = s3_logic_map.get(mid, {})
            event_content_value = s3_entry.get("event_content", "") if s3_entry else bd_ev.get("event_content", "")
            
            detail_obj = {
                "sheet_name_pattern": f"詳細仕様書_{mid}",
                "module_id": mid,
                "module_name": m_name,
                "event_trigger": bd_ev.get("event_trigger", ""),
                "event_content": event_content_value,
                "steps": steps,
            }
            
            # Only add _screen_edit_items if not empty
            if screen_edit_items:
                detail_obj["_screen_edit_items"] = screen_edit_items
            
            # Removed redundant _record_sources logic as per user request
            # query_mappings will be populated by _fill_query_sheets later

            # Removed output_data_area logic as per user request
            details.append(detail_obj)

    # Sort details by their appearance order in the BD events list
    bd_order = {ev.get("module_id"): i for i, ev in enumerate(bd_events)}
    details.sort(key=lambda x: bd_order.get(x.get("module_id"), 999))

    is_report = bd_final.get("category") == "report" or screen_id.upper().startswith("R")
    if is_report:
        # If no events/logic_items, build a synthetic detail from file_spec + process_overview
        if not details:
            file_specs = bd_final.get("sheet_5_file_spec", [])
            output_items = []
            for fs in file_specs:
                for fi in fs.get("items", []):
                    output_items.append(fi)

            process_lines = layout.get("process_overview", [])
            event_content = layout.get("description", "")
            if process_lines:
                event_content = "\n".join(
                    p.get("summary_line", "") for p in process_lines if p.get("summary_line")
                )

            synthetic_detail = {
                "sheet_name_pattern": f"詳細仕様書_{screen_id}",
                "module_id": screen_id,
                "module_name": screen_name,
                "event_trigger": "",
                "event_content": event_content,
                "steps": build_steps_placeholder(screen_id, []),
                "output_data_area": output_items,
            }
            details = [synthetic_detail]

        merged_details = details[0] if details else {}
        if details and "steps" in merged_details:
            merged_steps = []
            for item in details:
                mod_id = item.get("module_id", "") or item.get("report_scope_name", "")
                stps = item.get("steps", [])
                if mod_id and len(details) > 1:
                    merged_steps.append({"step": f"■ {mod_id}", "detail": ""})
                merged_steps.extend(stps)
            merged_details["steps"] = merged_steps
            merged_details["report_scope_name"] = screen_id

        merged_details["sheet_name_pattern"] = f"詳細仕様書_{screen_id}"
        out["sheet_3_detail_specs"] = [merged_details] if merged_details else []
    else:
        out["sheet_3_detail_specs"] = details

    # Placeholder for query templates
    out["sheet_4_sel_query_templates"] = []
    out["sheet_5_upd_query_templates"] = []
    
    return out

def _add_recordsource_if_missing(logic_items: list[dict], bd_final: dict, dd_code_json_path: Path, table_config: dict = None):
    """Detect RecordSource and add it to the Form_Open event (usually F000)."""
    rs = bd_final.get("sheet_2_layout", {}).get("record_sources", [])
    if not rs and "report" in bd_final:
        rs = bd_final.get("report", {}).get("properties", {}).get("data", {}).get("recordsource")
    
    if rs:
        q_name = rs[0].get("query_name") if isinstance(rs, list) else rs
        if q_name:
            # Support table-to-query mapping in RecordSource
            mapped_q = _get_mapped_query(q_name, table_config)
            q_name = mapped_q if mapped_q else q_name
            
            # Map VBA handlers (notes) to Module IDs (FXXX)
            vba_to_f_map = {}
            for ev in bd_final.get("sheet_2_layout", {}).get("events", []):
                notes = ev.get("notes")
                if notes:
                    vba_to_f_map[normalize_vba_name(notes)] = ev.get("module_id")
                    vba_to_f_map[notes] = ev.get("module_id")

            # Identify the module_id of Form_Open
            target_module_id = "F000"
            events = bd_final.get("sheet_2_layout", {}).get("events", [])
            for ev in events:
                if ev.get("notes") == "Form_Open" or ev.get("event_trigger") == "画面を開く時" or ev.get("event_trigger") == "onopen":
                    if ev.get("module_id"):
                        target_module_id = ev.get("module_id")
                        break
            
            # CHECK: If this query is already explicitly mapped to ANY event (including F000), 
            # we should skip the "RecordSource" injection to avoid redundancy.
            already_mapped = False
            for item in logic_items:
                for q in item.get("queries", []):
                    if normalize_query_name(q.get("query_name", "")) == normalize_query_name(q_name):
                        already_mapped = True
                        break
                if already_mapped: break
            
            if already_mapped:
                logger.info("[DD Form/Report] Skipping RecordSource injection for %s (already mapped to an event)", q_name)
                return

            # Remove any queries with the same q_name from all logic_items (deduplication)
            for item in logic_items:
                if "queries" in item:
                    item["queries"] = [q for q in item["queries"] if q.get("query_name") != q_name]

            actual_sql = {"select": "", "from": ""}
            actual_params = []
            found = False
            try:
                with open(dd_code_json_path, encoding="utf-8") as f:
                    dd_source = json.load(f)
                for rq in dd_source.get("related_queries", []):
                    if rq.get("name") == q_name:
                        actual_sql = rq.get("sql_logic") or rq.get("raw_sql") or actual_sql
                        actual_params = rq.get("parameters") or []
                        found = True
                        break
            except Exception:
                pass

            if not found:
                try:
                    from db.query_dd import get_dd_code_json_query_raw
                    repo = Layer1Repo()
                    q_doc = get_dd_code_json_query_raw(repo, q_name)
                    if q_doc:
                        sql_logic = q_doc.get("query") or q_doc.get("sql_logic")
                        raw_sql = q_doc.get("raw_sql")
                        actual_sql = sql_logic if sql_logic else (raw_sql if raw_sql else actual_sql)
                        actual_params = q_doc.get("parameters") or []
                except Exception as e:
                    logger.warning("Could not fetch RecordSource query %s from DB: %s", q_name, e)
            
            new_q = {
                "query_name": q_name, 
                "sql": actual_sql if isinstance(actual_sql, dict) else json.dumps(actual_sql, ensure_ascii=False), 
                "parameters": actual_params
            }
            
            # Try to find existing target_module_id
            target_item = next((it for it in logic_items if it.get("module_id") == target_module_id), None)
            
            if target_item:
                if "queries" not in target_item:
                    target_item["queries"] = []
                target_item["queries"].insert(0, new_q)
                
                # Force injection of RecordSource into virtual code so LLM sees it
                prefix = f"' [RecordSource Initialization]\n' Fetch data using mapped query for screen display.\n' Call Query: {q_name}\n\n"
                if prefix not in target_item.get("code", ""):
                    target_item["code"] = prefix + target_item.get("code", "")
            else:
                logic_items.insert(0, {
                    "module_id": target_module_id,
                    "title": "画面を開く時",
                    "code": f"' [RecordSource Initialization]\n' Fetch data using mapped query for screen display.\n' Call Query: {q_name}\n\n' Virtual module for RecordSource: {q_name}",
                    "queries": [new_q]
                })

def _merge_open_events(logic_items: list[dict], bd_final: dict) -> set[str]:
    """
    (Disabled for DD) Merging Form_Load into Form_Open (F000) for screen category.
    Returns empty set to keep them separate in DD documentation.
    """
    return set()

def _update_sheet2_parameter_info(skeleton: dict[str, Any], repo: Any, screen_name: str, table_config: dict = None) -> dict[str, Any]:
    """
    Scan all resolved queries in skeleton['sheet_4_sel_query_templates'] and skeleton['sheet_5_upd_query_templates'],
    extract all parameters, resolve their DB metadata, and update skeleton['sheet_2_overview']['parameter_info']
    to ensure NO parameters are missing for Sheet 2!
    """
    logger.info("[DD Parameter Info] Running post-processing parameter extraction for Sheet 2...")
    params_metadata = list(skeleton.get("sheet_2_overview", {}).get("parameter_info", []))
    seen_params = set(p.get("item_name") for p in params_metadata if p.get("item_name"))
    table_cache = {}

    # Base form name for notes expression (e.g. C000_MAINⅡ_印刷 -> C000_MAINⅡ)
    form_base = screen_name
    for suffix in ["_印刷", "_未入金", "_入金"]:
        if form_base.endswith(suffix):
            form_base = form_base[:-len(suffix)]
            break

    # Collect all queries from the resolved query sheets in skeleton
    queries = []
    for q in skeleton.get("sheet_4_sel_query_templates", []):
        queries.append(q)
    for q in skeleton.get("sheet_5_upd_query_templates", []):
        queries.append(q)

    for q in queries:
        q_params_str = q.get("parameters", "")
        if not q_params_str:
            continue
        
        # Split and clean parameter names
        q_params = []
        if isinstance(q_params_str, str):
            q_params = [p.strip() for p in q_params_str.split(",") if p.strip()]
        
        if not q_params:
            continue

        sql_str = json.dumps(q, ensure_ascii=False)
        
        # Build alias map for this query to resolve table columns
        from_clause = ""
        sql_obj = q.get("sql", {})
        if isinstance(sql_obj, dict):
            from_clause = str(sql_obj.get("from") or "")
            if not from_clause and sql_obj.get("update"):
                from_clause = sql_obj.get("update")
        else:
            # Fallback for raw SQL
            raw_sql = str(q.get("raw_sql", ""))
            m_from = re.search(r'(?i)\bFROM\b\s+(.*?)(\bWHERE\b|\bGROUP BY\b|\bORDER BY\b|$)', raw_sql)
            if m_from:
                from_clause = m_from.group(1).strip()
            else:
                m_upd = re.search(r'(?i)\bUPDATE\b\s+(.*?)(\bSET\b|$)', raw_sql)
                if m_upd:
                    from_clause = m_upd.group(1).strip()

        alias_map = parse_aliases(from_clause)
        if isinstance(sql_obj, dict) and "join" in sql_obj and isinstance(sql_obj["join"], list):
            for j in sql_obj["join"]:
                if isinstance(j, dict) and j.get("table"):
                    alias_map.update(parse_aliases(j["table"]))

        for symbol in q_params:
            if symbol in seen_params:
                continue

            meta = {
                "no": str(len(params_metadata) + 1),
                "io": "I",
                "item_name": symbol,
                "symbol_name": "",
                "data_type": "",
                "total_digits": "",
                "decimal_digits": "",
                "required": "",
                "notes": f"[Forms]![{form_base}]![{symbol}]"
            }

            # Try to find table/column comparison in SQL to resolve metadata
            pattern = r"\[?([A-Za-z0-9_＿]+)\]?\.\[?([A-Za-z0-9_＿]+)\]?[^=]*=\s*:" + re.escape(symbol)
            match = re.search(pattern, sql_str, re.IGNORECASE)
            if not match:
                 pattern = r":" + re.escape(symbol) + r"\s*=\s*\[?([A-Za-z0-9_＿]+)\]?\.\[?([A-Za-z0-9_＿]+)\]?"
                 match = re.search(pattern, sql_str, re.IGNORECASE)
            
            if match:
                tbl_name = match.group(1)
                col_name = match.group(2)
                
                # Resolve alias
                tbl_name = alias_map.get(tbl_name, tbl_name)
                
                if tbl_name not in table_cache:
                    try:
                        table_cache[tbl_name] = get_dd_code_json_table(repo, tbl_name)
                    except Exception:
                        table_cache[tbl_name] = None
                
                tbl_info = table_cache[tbl_name]
                if tbl_info:
                    for col in tbl_info.get("columns", []):
                        if col.get("physical_name") == col_name:
                            db_type = col.get("data_type", "VARCHAR2")
                            length = str(col.get("length", ""))
                            t_digits, d_digits = "", ""
                            if "," in length:
                                parts = length.split(",")
                                t_digits = parts[0]
                                d_digits = parts[1]
                            else:
                                t_digits = length
                            
                            meta["data_type"] = map_db_type_to_csharp(db_type, t_digits, d_digits)
                            meta["total_digits"] = t_digits
                            meta["decimal_digits"] = d_digits
                            meta["required"] = "o" if col.get("required") == "Y" else ""
                            break

            params_metadata.append(meta)
            seen_params.add(symbol)

    if "sheet_2_overview" not in skeleton:
        skeleton["sheet_2_overview"] = {}
    skeleton["sheet_2_overview"]["parameter_info"] = params_metadata
    logger.info("[DD Parameter Info] Done. Sheet 2 now has %d parameters.", len(params_metadata))
    return skeleton

def get_dd_skeleton(
    screen_name: str,
    dd_code_json_path: Path,
    bd_final_path: Path,
    template_path: Path,
    output_dir: Path,
    category: str = "screen",
) -> dict[str, Any]:
    with open(bd_final_path, encoding="utf-8") as f: bd_final = json.load(f)
    table_config = _load_table_config(template_path)

    # Parse the rich AST for DD generation
    logic_items = parse_dd_source(dd_code_json_path, table_config)

    allowed_mids = set()
    macro_items = []
    vba_to_f_map = {}

    # Build mapping from VBA handler name (notes) to BD module_id (FXXX)
    for ev_list in [bd_final.get("sheet_2_layout", {}).get("events", []), bd_final.get("report", {}).get("events", [])]:
        for ev in ev_list:
            notes, f_mid = ev.get("notes"), ev.get("module_id")
            if notes and f_mid:
                vba_to_f_map[normalize_vba_name(notes)] = f_mid
                vba_to_f_map[notes.lower().strip()] = f_mid
    
    logger.info("[DD Form/Report] vba_to_f_map keys: %s", list(vba_to_f_map.keys()))
    logger.info("[DD Form/Report] Processing %d logic_items from source.", len(logic_items))

    # Apply mapping to all logic_items immediately
    for item in logic_items:
        raw_mid = item.get("module_id", "")
        norm_mid = normalize_vba_name(raw_mid)
        
        mapped_to = None
        if norm_mid in vba_to_f_map:
            mapped_to = vba_to_f_map[norm_mid]
        elif raw_mid.lower().strip() in vba_to_f_map:
            mapped_to = vba_to_f_map[raw_mid.lower().strip()]
            
        if mapped_to:
            item["module_id"] = mapped_to
            logger.info("[DD Form/Report] Mapped logic item '%s' -> '%s'", raw_mid, mapped_to)
        else:
            logger.debug("[DD Form/Report] Could not map logic item '%s'", raw_mid)

    # S3 Load (for macros)
    s3_logic_path = bd_final_path.parent.parent / "s3_bd_logic" / f"logic_{screen_name}_result.json"
    if s3_logic_path.exists():
        try:
            with open(s3_logic_path, encoding="utf-8") as f:
                s3_data = json.load(f)
                for obj in s3_data:
                    if "macro." in obj.get("notes", ""):
                        macro_items.append(obj)
        except Exception as e:
            logger.warning("Failed to load S3 logic result for macro collection: %s", e)
    
    # Add macro items to logic_items for initial processing
    logic_items.extend(macro_items)
    
    _add_recordsource_if_missing(logic_items, bd_final, dd_code_json_path, table_config)

    # Pre-process: Merge Form_Load into Form_Open for screens
    merged_out_ids = set()
    if category == "screen":
        merged_out_ids = _merge_open_events(logic_items, bd_final)
    
    # Finally, ensure EVERY event from BD has a logic_item, even if it had no VBA code!
    # This prevents missing F-numbers (like F007) when their VBA sub was completely empty or missing from AST.
    # ALSO: Extract code from D1 skeleton for events that were filtered out
    existing_mids = set(item.get("module_id") for item in logic_items)
    
    # Load D1 skeleton to get VBA code for all procedures
    d1_vba_map = {}
    d1_all_queries = []  # All queries available in the D1 source (for find_queries_for_code)
    try:
        with open(dd_code_json_path, encoding="utf-8") as f:
            d1_data = json.load(f)
            # Extract all_queries from D1 (support multiple D1 structure patterns)
            form_or_report = d1_data.get("form") or d1_data.get("report") or d1_data
            for q in form_or_report.get("related_queries", []) + d1_data.get("related_queries", []):
                qname = q.get("name") or q.get("query_name")
                if qname:
                    d1_all_queries.append({
                        "name": qname,
                        "query_type": q.get("query_type"),
                        "sql_logic": q.get("sql_logic") or q.get("query") or q.get("sql") or {},
                        "raw_sql": q.get("raw_sql"),
                        "parameters": q.get("parameters", []),
                    })
            vba_procedures = form_or_report.get("vba_procedures", [])
            for proc in vba_procedures:
                handler = proc.get("handler", "")
                if handler:
                    # Map by both original handler name and normalized name
                    d1_vba_map[handler] = proc
                    d1_vba_map[normalize_vba_name(handler)] = proc
    except Exception as e:
        logger.warning("[DD Form/Report] Could not load D1 VBA procedures: %s", e)
    
    for ev in bd_final.get("sheet_2_layout", {}).get("events", []):
        mid = ev.get("module_id")
        if not mid: continue
        
        notes = ev.get("notes", "")
        if notes:
            notes = notes.split("\n")[0].strip()
            # Clean up macro prefix if present
            if notes.startswith("macro."):
                notes = notes.replace("macro.", "")
        
        # Check if we already have this module_id
        if mid in existing_mids:
            # Update title/content if missing
            item = next((it for it in logic_items if it.get("module_id") == mid), None)
            if item:
                if not item.get("title") and ev.get("title"):
                    item["title"] = ev.get("title")
                if item.get("code", "").startswith("' No logic found") or not item.get("code"):
                    vba_proc = d1_vba_map.get(notes) or d1_vba_map.get(normalize_vba_name(notes))
                    if vba_proc and vba_proc.get("code"):
                        item["code"] = vba_proc.get("code")
                        item["_source"] = "d1_vba_recovery"
            continue

        # If not found, try to recover code from D1
        vba_proc = d1_vba_map.get(notes) or d1_vba_map.get(normalize_vba_name(notes))
        
        if vba_proc and vba_proc.get("code"):
            logger.info("[DD Form/Report] Recovered VBA code from D1 for missing event %s (%s)", mid, notes)
            recovered_queries = find_queries_for_code(
                vba_proc.get("code", ""),
                d1_all_queries,
                vba_proc.get("references", {}),
                table_config
            )
            # Normalize query dict keys for consistency with _fill_query_sheets
            normalized_queries = []
            for rq in recovered_queries:
                normalized_queries.append({
                    "query_name": rq.get("query_name") or rq.get("name", ""),
                    "sql": rq.get("sql_logic") or rq.get("sql") or {},
                    "parameters": rq.get("parameters", []),
                })
            logic_items.append({
                "module_id": mid,
                "title": ev.get("title", ""),
                "code": vba_proc.get("code", ""),
                "queries": normalized_queries,
                "references": vba_proc.get("references", {}),
                "_source": "d1_vba_recovery"
            })
            existing_mids.add(mid)
        else:
            # Create a synthetic stub for events with no code
            logger.info("[DD Form/Report] Creating synthetic stub for %s (%s) — no VBA found", mid, notes)
            logic_items.append({
                "module_id": mid,
                "title": ev.get("title", ""),
                "code": f"' No logic found in source code. Event: {ev.get('event_trigger', '')}",
                "queries": [],
                "_source": "empty_stub",
                "_no_real_code": True,
            })
            existing_mids.add(mid)
    
    # FINAL STAIRCASE FILTER: Only allow module_ids present in S4 BD
    allowed_mids = set()
    for ev in bd_final.get("sheet_2_layout", {}).get("events", []):
        mid = ev.get("module_id")
        if mid:
            allowed_mids.add(mid)
    
    if allowed_mids:
        final_filtered = [it for it in logic_items if it.get("module_id") in allowed_mids]
        logger.info("[DD Form/Report] Final filtering: %d -> %d items", len(logic_items), len(final_filtered))
        # Log what we filtered out
        filtered_out = [it.get("module_id") for it in logic_items if it.get("module_id") not in allowed_mids]
        if filtered_out:
            logger.info("[DD Form/Report] Dropped non-S4 items: %s", filtered_out)
        logic_items[:] = final_filtered
    else:
        logger.warning("[DD Form/Report] S4 whitelist is empty, no filtering applied.")

    logger.info("[DD Form/Report] Resulting %d items matching BD.", len(logic_items))
        
    sample = json.loads(template_path.read_text(encoding="utf-8"))
    
    repo = Layer1Repo()
    l1_dir = Path(__file__).resolve().parent.parent / "db" / "l1_repo"
    resolver = TableResolver(l1_dir if l1_dir.exists() else None, repo, table_config)
    
    skeleton = _build_dd_skeleton(logic_items, bd_final, sample, all_queries=d1_all_queries)
    skeleton = _fill_query_sheets(logic_items, skeleton, resolver, table_config, repo, dd_code_json_path=dd_code_json_path)
    skeleton = _update_sheet2_parameter_info(skeleton, repo, screen_name, table_config)
    
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / f"{screen_name}.json"
        out_file.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[DD Form/Report] Wrote %s", out_file)
    return skeleton, logic_items
