from __future__ import annotations
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..core.constants import *
from ..core.utils import *
from ..core.extractors import *
def collect_sheet3(
    controls: list[dict[str, Any]],
    recordsource: str,
    label_caption_map: dict[str, str],
    optiongroup_label_map: dict[str, str],
    query_meta: dict[str, Any] | None = None,
    table_index: dict[str, Any] | None = None,
    query_index: dict[str, Any] | None = None,
    handler_to_event_id: dict[str, str] | None = None,
    form_name: str = "",
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    section_i = 0
    control_i = 1
    sections: list[dict[str, Any]] = []
    children_by_nodekey: dict[str, list[dict[str, Any]]] = {}
    ungrouped_children: list[dict[str, Any]] = []

    # Collect all input fields for this form from all queries in query_index
    form_input_fields = set()
    if query_index and form_name:
        fn_norm = form_name.strip().lower()
        for q_meta in query_index.values():
            inputs_map = q_meta.get("_form_inputs") or {}
            for f_name, fields in inputs_map.items():
                if f_name.strip().lower() == fn_norm:
                    for f in fields:
                        form_input_fields.add(normalize_field_token(f).lower())

    def find_parameter_mapping(ctrl_name: str) -> tuple[str, str]:
        if not form_name or not query_index:
            return "", ""
        fn_norm = form_name.strip().lower()
        c_norm = normalize_field_token(ctrl_name).lower()
        
        for q_name, q_meta in query_index.items():
            params = q_meta.get("parameters") or {}
            for p_name, p_val in params.items():
                p_str = str(p_val)
                m = re.search(r"(?:Forms|\[Forms\])!\[?([^!\]]+)\]?!\[?([^!\]]+)\]?", p_str, re.IGNORECASE)
                if m:
                    f_n = m.group(1).strip().lower()
                    c_n = normalize_field_token(m.group(2)).lower()
                    
                    if f_n == fn_norm and c_n == c_norm:
                        p_name_clean = p_name.strip().lstrip(":").strip("[]")
                        where_clause = str((q_meta.get("query") or {}).get("where") or "")
                        
                        p1 = r"(?:\[([^\]]+)\]|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+))\.(?:\[([^\]]+)\]|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+))[\s\)]*(?:=|<=|>=|<|>|LIKE|IN)[\s\(]*:?\[?" + re.escape(p_name_clean) + r"\]?(?!\w)"
                        m1 = re.search(p1, where_clause, re.IGNORECASE)
                        if m1:
                            tbl, fld = (m1.group(1) or m1.group(2)), (m1.group(3) or m1.group(4))
                            alias_map = q_meta.get("_alias_to_table") or {}
                            real_tbl = alias_map.get(normalize_field_token(tbl), tbl)
                            return real_tbl, fld
                            
                        p2 = r":?\[?" + re.escape(p_name_clean) + r"\]?(?!\w)[\s\)]*(?:=|<=|>=|<|>|LIKE|IN)[\s\(]*(?:\[([^\]]+)\]|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+))\.(?:\[([^\]]+)\]|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+))"
                        m2 = re.search(p2, where_clause, re.IGNORECASE)
                        if m2:
                            tbl, fld = (m2.group(1) or m2.group(2)), (m2.group(3) or m2.group(4))
                            alias_map = q_meta.get("_alias_to_table") or {}
                            real_tbl = alias_map.get(normalize_field_token(tbl), tbl)
                            return real_tbl, fld
        return "", ""

    for c in controls:
        ctype = str(c.get("type") or "")
        if ctype in STRUCT_TYPES:
            sections.append(c)
            continue
        nodekey = str(c.get("nodekey") or "").strip().lower()
        if nodekey:
            children_by_nodekey.setdefault(nodekey, []).append(c)
        else:
            ungrouped_children.append(c)

    def _resolve_item_no(ctrl: dict[str, Any], fallback: Any) -> str:
        if handler_to_event_id:
            evs = (ctrl.get("properties") or {}).get("event") or {}
            ids = []
            for hv in evs.values():
                h = str(hv or "").strip()
                if h in handler_to_event_id:
                    ids.append(handler_to_event_id[h])
            if ids:
                # Return unique event IDs joined by comma
                return (",".join(list(dict.fromkeys(ids))) + " " + str(fallback)).strip()
        return str(fallback)

    def append_control_row(ctrl: dict[str, Any]) -> None:
        nonlocal control_i
        ctype = str(ctrl.get("type") or "")
        if ctype in SKIP_TYPES_SHEET3:
            return

        logical = logical_name_for_ctrl(ctrl, label_caption_map, optiongroup_label_map)
        cleaned_logical = clean_value(logical)
        final_physical, final_logical = resolve_names(cleaned_logical, ctype)
        caption_val = caption(ctrl)
        data = (ctrl.get("properties") or {}).get("data") or {}
        fmt = (ctrl.get("properties") or {}).get("format") or {}

        # Determine effective query_meta for this control:
        # If the control has a rowsource query, prefer that for resolution
        ctrl_query_meta = query_meta
        ctrl_rs = recordsource
        rstype = str(data.get("rowsourcetype") or "").strip().lower()
        rowsource = str(data.get("rowsource") or "").strip()
        if rstype == "table/query" and rowsource and query_index and rowsource in query_index:
            ctrl_query_meta = query_index[rowsource]
            ctrl_rs = rowsource

        src_tbl, src_f, extra_note = resolve_source_table_field(
            str(data.get("controlsource") or ""), ctrl_rs, ctrl_query_meta, query_index
        )
        if not src_tbl and rstype == "table/query" and rowsource and query_index and rowsource in query_index:
            # Fallback for combo/listbox: pick first field from rowsource
            q_m = query_index[rowsource]
            select_sql = ""
            q_obj = q_m.get("query") or q_m
            if isinstance(q_obj, dict):
                select_sql = str(q_obj.get("select") or "")
            if select_sql:
                m = re.search(r"(?:[A-Za-z0-9_＿\[\]]+\.)?\[?([^, ]+)\]?", select_sql)
                if m:
                    first_f = normalize_field_token(m.group(1))
                    src_tbl, src_f, fallback_extra = resolve_source_table_field(first_f, rowsource, q_m, query_index)
                    if not extra_note: extra_note = fallback_extra
        if ctype == "Label":
            src_f = caption_val

        ctrl_name = control_name(ctrl)
        ctrl_source = str(data.get("controlsource") or "").strip()
        
        is_param_mapped = False
        # Resolve table and field from parameter mapping if not already bound
        if not src_tbl and not src_f:
            p_tbl, p_fld = find_parameter_mapping(ctrl_name)
            if p_tbl and p_fld:
                src_tbl = p_tbl
                src_f = p_fld
                is_param_mapped = True

        # Try to fetch field metadata from table_index
        attr_digits = ""
        required = ""
        flen = ""
        
        # Use either the bound source or the parameter mapped source to get attributes
        eval_tbl, eval_fld = src_tbl, src_f
            
        if table_index and eval_tbl and eval_fld:
            # src_tbl might be multi-line if resolved from expression
            first_tbl = eval_tbl.split("\n")[0].strip()
            first_fld = eval_fld.split("\n")[0].strip()
            
            tbl_data = table_index.get(first_tbl)
            if not tbl_data:
                # Fallback to case-insensitive lookup
                for k, v in table_index.items():
                    if k.lower() == first_tbl.lower():
                        tbl_data = v
                        break
                        
            if tbl_data:
                columns = tbl_data.get("columns") or []
                for col in columns:
                    pname = col.get("physical_name")
                    if pname and normalize_field_token(pname) == normalize_field_token(first_fld):
                        ftype = str(col.get("data_type") or "")
                        flen = str(col.get("length") or "")
                        sql_t = f"{ftype}({flen})" if flen and flen != "0" else ftype
                        cs_t = sql_to_csharp(ftype, flen)
                        attr_digits = f"{sql_t} / {cs_t}" if cs_t else sql_t
                        required = "○" if str(col.get("required")).lower() in ("true", "1", "yes", "on", "required", "y") else ""
                        if col.get("required"):
                            required = "○"
                        break

        # Determine I/O status
        is_output = bool(src_tbl and src_f and not is_param_mapped)
        if ctype.lower() == "label" and clean_value(src_f):
            is_output = True
            
        is_input = False
        if ctype.lower() in ("textbox", "combobox", "checkbox"):
            is_input = True
        elif normalize_field_token(ctrl_name).lower() in form_input_fields:
            is_input = True
        elif ctrl_source and normalize_field_token(ctrl_source).lower() in form_input_fields:
            is_input = True
            
        io_status = ""
        if is_input and is_output:
            io_status = "I/O"
        elif is_input:
            io_status = "I"
        elif is_output:
            io_status = "O"

        notes = ""
        if ctype == "Subform":
            subform_name = str(data.get("sourceobject") or ctrl.get("name") or "")
            doc_name = SUBFORM_DOC_MAP.get(subform_name, subform_name)
            notes = f"詳細は「{doc_name}」を参照"
        
        final_notes = _resolve_item_no(ctrl, notes)
        # if extra_note and extra_note != src_f:
        #     final_notes = (final_notes + "\n" + extra_note).strip()

        final_src_tbl = format_source_table_names(src_tbl)

        rows.append(
            {
                "item_no": control_i,
                "io": io_status,
                "logical_name": final_logical,
                "physical_name": final_physical,
                "item_attribute": TYPE_MAP.get(ctype, ctype),
                "attribute_digits": flen,
                "required": required,
                "format": ACCESS_FORMAT_MAP.get(str(fmt.get("format") or ""), str(fmt.get("format") or "")),
                "other_input_checks": format_input_checks(data, fmt),
                "source_table": final_src_tbl,
                "source_field_or_fixed_value": clean_value(src_f),
                "notes": final_notes,
            }
        )
        control_i += 1

    for sec in sections:
        ctype = str(sec.get("type") or "")
        sec_key = ctype.strip().lower()
        logical = logical_name_for_ctrl(sec, label_caption_map, optiongroup_label_map)
        cleaned_logical = clean_value(logical)
        final_physical, final_logical = resolve_names(cleaned_logical, ctype)
        rows.append(
            {
                "item_no": roman(section_i),
                "io": "",
                "logical_name": final_logical,
                "physical_name": "",
                "item_attribute": "",
                "attribute_digits": "",
                "required": "",
                "format": "",
                "other_input_checks": "",
                "source_table": "",
                "source_field_or_fixed_value": "",
                "notes": "",
            }
        )
        section_i += 1
        for child in children_by_nodekey.get(sec_key, []):
            append_control_row(child)

    for child in ungrouped_children:
        append_control_row(child)

    return rows



