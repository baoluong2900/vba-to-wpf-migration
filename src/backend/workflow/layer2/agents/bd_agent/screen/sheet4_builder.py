from __future__ import annotations
import re
from copy import deepcopy
from typing import Any

from ..core.constants import *
from ..core.utils import *
from ..core.extractors import *
def _is_file_query(query_name: str) -> bool:
    lower = query_name.lower()
    return any(h in lower for h in FILE_QUERY_HINTS)


def _is_table_update_query(query_name: str) -> bool:
    lower = query_name.lower()
    if _is_file_query(query_name):
        return False
    return any(h in lower for h in TABLE_UPDATE_HINTS)


def collect_sheet4(
    procs: list[dict[str, Any]],
    handler_to_event_id: dict[str, str],
    header_template: dict[dict[str, str]],
    query_index: dict[str, Any] | None = None,
    form_name: str = "",
) -> list[dict[str, Any]]:
    if not query_index:
        return []

    # Grouping structure: (event_id, target_table) -> {header, items, query_names}
    grouped_data: dict[tuple[str, str], dict[str, Any]] = {}

    for p in procs:
        handler = str(p.get("handler") or "")
        event_id = handler_to_event_id.get(handler)
        if not event_id:
            continue
        
        queries = (p.get("references") or {}).get("queries") or []
        update_queries = [str(q) for q in queries if _is_table_update_query(str(q))]
        
        for q_name in update_queries:
            q_meta = query_index.get(q_name)
            if not q_meta:
                continue
            
            q_obj = q_meta.get("query") or q_meta
            if not isinstance(q_obj, dict):
                continue
                
            if "update" in q_obj:
                target_table = str(q_obj["update"])
                update_type = "更新"
                set_items = q_obj.get("set") or []
            elif "insert into" in q_obj or "into" in q_obj:
                target_table = str(q_obj.get("insert into") or q_obj.get("into") or "")
                update_type = "追加"
                set_items = q_obj.get("values") or q_obj.get("set") or []
            elif "delete from" in q_obj or "delete" in q_obj:
                target_table = str(q_obj.get("delete from") or q_obj.get("delete") or "")
                update_type = "削除"
                set_items = []
            else:
                continue
            
            if not target_table:
                target_table = q_meta.get("_primary_table", "")
                if not update_type:
                    update_type = "更新"

            key = (event_id, target_table)
            if key not in grouped_data:
                sheet_header = deepcopy(header_template)
                sheet_header["table_physical_name"] = normalize_field_token(target_table)
                sheet_header["table_logical_name"] = ""
                sheet_header["update_type"] = update_type
                grouped_data[key] = {
                    "header": sheet_header,
                    "items": [],
                    "query_names": []
                }
            
            if q_name not in grouped_data[key]["query_names"]:
                grouped_data[key]["query_names"].append(q_name)
            
            for si in set_items:
                if isinstance(si, str):
                    if "=" in si:
                        parts = si.split("=", 1)
                        fld = parts[0].strip()
                        val = parts[1].strip()
                    else:
                        fld = si.strip()
                        val = ""
                else:
                    fld = str(si.get("field") or "")
                    val = str(si.get("value") or "")
                
                src_tbl, src_f, _ = resolve_source_table_field(val, q_name, q_meta, query_index)
                
                final_src_tbl = src_tbl
                final_src_f = src_f if src_f else val
                final_value = ""

                # Fixed value / Function detection
                is_function = bool(re.match(r'^[A-Za-z0-9_]+\(.*\)$', val.strip()))
                is_fixed = (
                    not val.strip() or 
                    (val.strip().startswith('"') and val.strip().endswith('"')) or
                    (val.strip().startswith("'") and val.strip().endswith("'")) or
                    re.match(r'^[-+]?\d*\.?\d+$', val.strip()) or
                    val.strip().lower() in ("null", "true", "false")
                )

                # Handle parameter logic
                if val.startswith(":"):
                    final_src_f = val
                    final_src_tbl = form_name
                    params = q_meta.get("parameters") or {}
                    p_val = params.get(val[1:])
                    if not p_val:
                        for k, v in params.items():
                            if k.lower() == val[1:].lower():
                                p_val = v
                                break
                    if p_val:
                        m = re.search(r"(?:Forms|\[Forms\])!\[?([^!\]]+)\]?", str(p_val), re.IGNORECASE)
                        if m:
                            ref_form = m.group(1).strip()
                            final_src_tbl = ref_form

                    if final_src_tbl == form_name:
                        final_src_tbl = "本画面"
                
                elif is_function:
                    final_value = val
                    final_src_f = ""
                    final_src_tbl = ""

                elif is_fixed:
                    final_value = f"{val} 固定"
                    final_src_f = ""
                    final_src_tbl = ""

                final_src_tbl = format_source_table_names(final_src_tbl)

                grouped_data[key]["items"].append({
                    "target_field_physical": clean_field_name(fld),
                    "target_field_logical": "",
                    "source_table": final_src_tbl,
                    "source_field_or_fixed_value": final_src_f,
                    "condition_and_format": final_value,
                    "chk": "",
                    "notes": f"From {q_name}" if len(update_queries) > 1 else ""
                })

    # Finalize sheets
    # Group entries by event_id to determine if numbering is needed
    event_groups: dict[str, list] = {}
    for (event_id, target_table), data in grouped_data.items():
        if event_id not in event_groups:
            event_groups[event_id] = []
        event_groups[event_id].append(((event_id, target_table), data))

    sheets: list[dict[str, Any]] = []
    for event_id, entries in event_groups.items():
        # Sort entries by target_table for consistent order
        entries.sort(key=lambda x: x[0][1])
        
        has_multiple = len(entries) > 1
        for idx, ((eid, tt), data) in enumerate(entries, start=1):
            # Re-number items and ensure "no" is first
            final_items = []
            for i, item in enumerate(data["items"], start=1):
                new_item = {"no": str(i)}
                new_item.update(item)
                final_items.append(new_item)
                
            if has_multiple:
                sheet_name = f"画面仕様書（{event_id}_{idx}）"
            else:
                sheet_name = f"画面仕様書（{event_id}）"

            sheets.append({
                "sheet_name_pattern": sheet_name,
                "header": data["header"],
                "items": final_items
            })

            
    return sheets


