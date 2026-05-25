"""
dd_agent/fill_dd_macro_module.py — D1 & D2 static processing for Macros/Modules
"""
from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .fill_utils import parse_dd_source, extract_vba_dim_vars, collect_pending_refers, build_steps_placeholder
from .query_mapper import TableResolver, _load_table_config, _fill_query_sheets



# ── Skeleton Building ──────────────────────────────────────────────────────────

def _build_dd_skeleton(
    logic_items: list[dict[str, Any]],
    bd_final: dict[str, Any],
    sample: dict[str, Any],
    category: str = "common",
) -> dict[str, Any]:
    out = deepcopy(sample)
    screen_id = bd_final.get("screen_id", "")
    screen_name = bd_final.get("screen_name", "")

    out["screen_id"] = screen_id
    out["screen_name"] = screen_name
    for key in ["system_name", "subsystem_name", "author", "created_date", "updated_by", "updated_date"]:
        out[key] = bd_final.get(key, "")

    out["sheet_1_change_history"] = {"sheet_name": "変更履歴", "data": []}

    details = []
    for item in logic_items:
        mid = item.get("module_id", "")
        code = item.get("code", "")
        m_name = item.get("title", "") or mid
        input_vars = extract_vba_dim_vars(code)
        refers = collect_pending_refers(code)
        
        if "macro_actions" in item:
            steps = [{"step": f"{idx}. {act.get('action', 'Action')}", "detail": act} for idx, act in enumerate(item["macro_actions"], 1)]
        else:
            steps = build_steps_placeholder(mid, refers)

        detail_obj = {
            "module_id": mid,
            "module_name": m_name,
            "key_id": mid,
            "key_name": m_name,
            "steps": steps,
            "pending_refers": refers,
        }
        details.append(detail_obj)

    if category == "macro":
        out["sheet_2_detail"] = {"sheet_name_pattern": "詳細仕様書", "details": details}
        out.pop("sheet_2_overview", None)
        out.pop("sheet_3_detail_specs", None)
    else: # common / module
        out["sheet_2_detail"] = details
        out.pop("sheet_3_detail_specs", None)
        out.pop("sheet_2_overview", None)

    out["sheet_4_sel_query_templates"] = []
    out["sheet_5_upd_query_templates"] = []
    return out

def get_dd_skeleton(
    screen_name: str,
    dd_code_json_path: Path,
    bd_final_path: Path,
    template_path: Path,
    output_dir: Path,
    category: str = "common",
) -> dict[str, Any]:
    if bd_final_path.exists():
        with open(bd_final_path, encoding="utf-8") as f: bd_final = json.load(f)
    else:
        bd_final = {"screen_id": screen_name, "screen_name": screen_name}
    logic_items = parse_dd_source(dd_code_json_path)
    sample = json.loads(template_path.read_text(encoding="utf-8"))
    
    l1_dir = Path(__file__).resolve().parent.parent / "db" / "l1_repo"
    resolver = TableResolver(l1_dir if l1_dir.exists() else None)
    
    table_config = _load_table_config(template_path)
    
    skeleton = _build_dd_skeleton(logic_items, bd_final, sample, category=category)
    skeleton = _fill_query_sheets(logic_items, skeleton, resolver, table_config, dd_code_json_path=dd_code_json_path)
    
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / f"{screen_name}.json"
        out_file.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[D2 Macro/Module] Wrote {out_file}")
    return skeleton, logic_items
