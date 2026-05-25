from __future__ import annotations
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .constants import *
from .utils import *
from .extractors import *
from ..screen.sheet3_builder import collect_sheet3
from ..screen.sheet4_builder import collect_sheet4
from ..report.sheet5_builder import collect_sheet5
def generate_bd(
    data_root: dict[str, Any],
    sample: dict[str, Any],
    query_index: dict[str, Any] | None = None,
    table_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = build_skeleton(sample)
    form_name = str((data_root.get("form") or {}).get("name") or data_root.get("name") or "")
    form_type = str((data_root.get("form") or {}).get("type") or data_root.get("type") or "").strip()
    is_report = form_type.lower() == "reports"
    recordsource = str(((root_properties(data_root).get("data") or {}).get("recordsource") or ""))
    query_meta = None
    if query_index and recordsource:
        key = str(recordsource).strip()
        if key in query_index:
            query_meta = query_index[key]
    procedures = extract_procedures(data_root)
    controls = extract_controls(data_root)
    proc_map = procedure_map(data_root)
    label_caption_map, optiongroup_label_map = build_control_maps(controls)

    out["screen_id"] = form_name
    out["screen_name"] = form_name
    
    events, handler_to_event_id = collect_events(
        data_root, proc_map, label_caption_map, optiongroup_label_map
    )
    out["sheet_2_layout"]["events"] = events

    form_open_module_id = "F000"
    for ev in events:
        if ev.get("notes") == "Form_Open" or ev.get("event_trigger") == "画面を開く時" or ev.get("event_trigger") == "onopen":
            form_open_module_id = ev.get("module_id") or "F000"
            break

    rs_list = []
    rs_index = 1
    if recordsource:
        rs_list.append({"query_name": recordsource, "query_display": f"{form_open_module_id}_SelQuery{rs_index:02d}"})
        rs_index += 1

    # Also include rowsource queries from controls
    added_rs = {recordsource} if recordsource else set()
    for ctrl in controls:
        c_data = (ctrl.get("properties") or {}).get("data") or {}
        rstype = str(c_data.get("rowsourcetype") or "").strip().lower()
        rs_val = str(c_data.get("rowsource") or "").strip()
        if rstype == "table/query" and rs_val and rs_val not in added_rs:
            rs_list.append({"query_name": rs_val, "query_display": f"{form_open_module_id}_SelQuery{rs_index:02d}"})
            added_rs.add(rs_val)
            rs_index += 1

        # Scan controlsource for DLookUp
        cs_val = str(c_data.get("controlsource") or "").strip()
        if cs_val.startswith("="):
            m_dl = re.search(
                r'DLookUp\s*\(\s*[\\"\']+(.*?)[\\"\']+\s*,\s*[\\"\']+(.*?)[\\"\']+',
                cs_val,
                re.IGNORECASE,
            )
            if m_dl:
                rs_domain = m_dl.group(2).strip()
                if rs_domain and rs_domain not in added_rs:
                    rs_list.append({"query_name": rs_domain, "query_display": f"{form_open_module_id}_SelQuery{rs_index:02d}"})
                    added_rs.add(rs_domain)
                    rs_index += 1

    out["sheet_2_layout"]["record_sources"] = rs_list
    out["sheet_2_layout"]["process_overview"] = [
        {"summary_line": f""},
        {"summary_line": f""},
    ]

    if is_report:
        # Clear sheet 3 and sheet 4
        out.pop("sheet_3_screen_edit", None)
        out.pop("sheet_4_table_update", None)
        
        # Reports don't have process_overview, but have grouping and sorting
        out["sheet_2_layout"].pop("process_overview", None)
        grouping = ""
        sorting = ""
        if query_meta:
            q_obj = query_meta.get("query") or {}
            grouping = q_obj.get("group_by", "")
            sorting = q_obj.get("order_by", "")
        out["sheet_2_layout"]["grouping"] = grouping
        out["sheet_2_layout"]["sorting"] = sorting
        
        # Build sheet 5 from report input controls
        sheet5_header = deepcopy((sample.get("sheet_5_file_spec") or {}).get("header") or {})
        sheet5_header["file_name"] = form_name
        sheet5_header["file_type"] = "レポート"
        
        items = []
        idx = 1
        section_i = 0
        target_types = {"textbox", "checkbox", "combobox", "listbox", "optiongroup", "togglebutton", "subform"}
        
        sections = []
        children_by_nodekey = {}
        ungrouped_children = []

        for c in controls:
            ctype = str(c.get("type") or "")
            if ctype.lower() in STRUCT_TYPES:
                sections.append(c)
                continue
            nodekey = str(c.get("nodekey") or "").strip().lower()
            if nodekey:
                children_by_nodekey.setdefault(nodekey, []).append(c)
            else:
                ungrouped_children.append(c)
                
        def append_report_control(ctrl: dict[str, Any]):
            nonlocal idx
            ctype = str(ctrl.get("type") or "").lower()
            if ctype not in target_types:
                return
                
            data = (ctrl.get("properties") or {}).get("data") or {}
            
            if ctype == "subform":
                sourceobject = str(data.get("sourceobject") or "").strip()
                if sourceobject.lower().startswith("report."):
                    sourceobject = sourceobject[7:]
                elif sourceobject.lower().startswith("form."):
                    sourceobject = sourceobject[5:]
                    
                items.append({
                    "no": str(idx),
                    "output_field_name": f"ソース「{sourceobject}」" if sourceobject else "ソース「」",
                    "source_table": "サブレポート",
                    "source_field_or_fixed_value": "",
                    "condition_and_format": "",
                    "chk": "",
                    "notes": f"＊{sourceobject}を参照" if sourceobject else ""
                })
                idx += 1
                return

            controlsource = str(data.get("controlsource") or "").strip()
            
            caption_val = ""
            labelname = str((ctrl.get("properties") or {}).get("other", {}).get("labelname") or "")
            if labelname and labelname in label_caption_map:
                caption_val = label_caption_map[labelname]
            if not caption_val:
                caption_val = caption(ctrl)
                
            condition_and_format = ""
            if controlsource.startswith("="):
                condition_and_format = controlsource
                # Extract variables in brackets [Var]
                fields_in_formula = re.findall(r"\[([^\]]+)\]", controlsource)
                
                all_src_tbls = []
                all_src_fs = []
                
                for f in fields_in_formula:
                    tbl, f_res, _ = resolve_source_table_field(
                        f, recordsource, query_meta, query_index
                    )
                    if not f_res:
                        f_res = f
                    all_src_tbls.append(tbl if tbl else "")
                    all_src_fs.append(f_res)
                    
                src_tbl = "\n".join(all_src_tbls) if all_src_fs else ""
                src_f = "\n".join(all_src_fs) if all_src_fs else ""
            else:
                src_tbl, src_f, _ = resolve_source_table_field(
                    controlsource, recordsource, query_meta, query_index
                )
                if not src_f and controlsource:
                    src_f = controlsource
                
            items.append({
                "no": str(idx),
                "output_field_name": caption_val if caption_val else control_name(ctrl),
                "source_table": src_tbl,
                "source_field_or_fixed_value": src_f,
                "condition_and_format": condition_and_format,
                "chk": "",
                "notes": ""
            })
            idx += 1

        for sec in sections:
            ctype = str(sec.get("type") or "")
            sec_key = ctype.strip().lower()
            logical = logical_name_for_ctrl(sec, label_caption_map, optiongroup_label_map)
            cleaned_logical = clean_value(logical)
            _, final_logical = resolve_names(cleaned_logical, ctype)
            
            items.append({
                "no": roman(section_i),
                "output_field_name": final_logical,
                "source_table": "",
                "source_field_or_fixed_value": "",
                "condition_and_format": "",
                "chk": "",
                "notes": ""
            })
            section_i += 1
            for child in children_by_nodekey.get(sec_key, []):
                append_report_control(child)
                
        for child in ungrouped_children:
            append_report_control(child)
            
        out["sheet_5_file_spec"] = [{
            "sheet_name_pattern": "ファイル仕様書（レポート）",
            "header": sheet5_header,
            "items": items,
        }]

    else:
        out["sheet_3_screen_edit"]["items"] = collect_sheet3(
            controls,
            recordsource,
            label_caption_map,
            optiongroup_label_map,
            query_meta,
            table_index,
            query_index,
            handler_to_event_id,
            form_name,
        )
        out["sheet_4_table_update"] = collect_sheet4(
            procedures,
            handler_to_event_id,
            deepcopy((out.get("sheet_4_table_update") or {}).get("header") or {}),
            query_index,
            form_name,
        )
        out["sheet_5_file_spec"] = collect_sheet5(
            procedures,
            handler_to_event_id,
            deepcopy((out.get("sheet_5_file_spec") or {}).get("header") or {}),
            events,
            query_index,
        )
    return out

def get_bd_mapping_dict(repo: Any, form_name: str, bd_code_json: dict[str, Any]) -> dict[str, Any]:
    """
    Returns the BD mapping dictionary (skeleton) without writing to file.
    """
    proj_root = Path(__file__).resolve().parent.parent.parent

    # 1. Load sample using template_loader
    from backend.layer2.utils.template_loader import load_template
    sample_json = load_template("bd_form.json")
    if not sample_json:
        return {}  # Fallback

    # 2. Fetch queries
    from db.query_bd import get_bd_code_json_query_raw
    q_index = {}
    form_data = bd_code_json.get("form", {})
    query_names = set(form_data.get("dependencies", {}).get("queries", []))

    # Resolve recordsource: check multiple possible key locations
    rs = (
        form_data.get("record_source")
        or form_data.get("recordsource")
        or ((form_data.get("properties") or {}).get("data") or {}).get("recordsource")
        or ((form_data.get("properties") or {}).get("data") or {}).get("record_source")
    )
    if rs:
        query_names.add(str(rs).strip())

    # Also collect rowsource query names from all controls
    controls_raw = form_data.get("controls") or form_data.get("items") or []
    for ctrl in controls_raw:
        ctrl_data = (ctrl.get("properties") or {}).get("data") or {}
        rstype_val = str(ctrl_data.get("rowsourcetype") or "").strip().lower()
        rs_val = str(ctrl_data.get("rowsource") or "").strip()
        if rstype_val == "table/query" and rs_val:
            query_names.add(rs_val)

        # Scan controlsource for DLookUp
        cs_val = str(ctrl_data.get("controlsource") or "").strip()
        if cs_val.startswith("="):
            m_dl = re.search(
                r'DLookUp\s*\(\s*[\\"\']+(.*?)[\\"\']+\s*,\s*[\\"\']+(.*?)[\\"\']+',
                cs_val,
                re.IGNORECASE,
            )
            if m_dl:
                query_names.add(m_dl.group(2).strip())

    # 2.1 Scan VBA for additional query dependencies (e.g. acQuery in OutputTo)
    procedures = extract_procedures(bd_code_json)
    for p in procedures:
        # Add queries listed in procedure references
        for q in (p.get("references") or {}).get("queries") or []:
            query_names.add(str(q))

        code = str(p.get("code") or "")
        # Match acQuery, "QueryName"
        for m in re.finditer(r"acQuery\s*,\s*\"([^\"]+)\"", code, re.IGNORECASE):
            query_names.add(m.group(1))

    fetched_queries = set()
    def fetch_recursive(q_set):
        new_qs = set()
        for q_name in q_set:
            if not q_name or q_name in fetched_queries:
                continue
            fetched_queries.add(q_name)
            try:
                q_raw = get_bd_code_json_query_raw(repo, q_name)
                q_meta = prepare_query_metadata(q_raw)
                q_index[q_name] = q_meta
                
                # Add dependent tables/queries to try to fetch them as well
                for t in q_meta.get("tables") or []:
                    if t:
                        new_qs.add(str(t))
                
                pt = q_meta.get("_primary_table")
                if pt:
                    new_qs.add(str(pt))
                    
                for ft in q_meta.get("_field_to_table", {}).values():
                    if ft:
                        new_qs.add(str(ft))
            except Exception:
                continue
        if new_qs:
            fetch_recursive(new_qs)

    fetch_recursive(query_names)

    # 3. Fetch tables
    from db.query_bd import get_bd_code_json_table
    t_index = {}
    table_names = set()
    for q_meta in q_index.values():
        pt = q_meta.get("_primary_table")
        if pt: table_names.add(pt)
        for t in q_meta.get("_field_to_table", {}).values():
            if t: table_names.add(t)
    
    for t_name in table_names:
        try:
            t_index[t_name] = get_bd_code_json_table(repo, t_name)
        except:
            continue

    res = generate_bd(bd_code_json, sample_json, q_index, t_index)

    # 4. Save output
    try:
        output_dir = proj_root / "output" / "bd_flow" / "s2_bd_mapping"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{form_name}.json"
        output_file.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Warning: Failed to save mapping output to file: {e}")

    return res

def main() -> None:
    parser = argparse.ArgumentParser(description="Build BD JSON from form+analysis JSON.")
    parser.add_argument("--form", type=str, help="Form name to run the integrated flow.")
    parser.add_argument("--data-json", type=Path, help="Source analysis JSON.")
    parser.add_argument("--sample", type=Path, help="Template BD JSON.")
    parser.add_argument("--output", type=Path, help="Output JSON path.")
    parser.add_argument(
        "--query-json",
        type=Path,
        action="append",
        default=[],
        help="Mock query JSON. Repeatable.",
    )
    parser.add_argument(
        "--query-dir",
        type=Path,
        action="append",
        default=[],
        help="Directory containing raw_query_*.json. Repeatable.",
    )
    args = parser.parse_args()

    data_json = json.loads(args.data_json.read_text(encoding="utf-8"))
    sample_json = json.loads(args.sample.read_text(encoding="utf-8"))
    proj_root = Path(__file__).resolve().parent.parent.parent
    data_parent = args.data_json.resolve().parent
    q_dirs: list[Path] = [proj_root, data_parent]
    q_dirs.extend(args.query_dir)
    q_index = load_query_mock_index([Path(p) for p in args.query_json], q_dirs)
    out = generate_bd(data_json, sample_json, q_index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
