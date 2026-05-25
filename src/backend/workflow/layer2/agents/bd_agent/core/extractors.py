from __future__ import annotations
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .constants import *
from .utils import *
def extract_procedures(data_root: dict[str, Any]) -> list[dict[str, Any]]:
    form = data_root.get("form") or {}
    procs = form.get("vba_procedures") or data_root.get("vba_procedures")
    if isinstance(procs, list):
        return procs
    procs = form.get("procedures") or data_root.get("procedures")
    if isinstance(procs, list):
        return procs
    return []


def procedure_map(data_root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in extract_procedures(data_root):
        handler = str(p.get("handler") or "").strip()
        if handler:
            out[handler] = p
    return out


def root_properties(data_root: dict[str, Any]) -> dict[str, Any]:
    root_props = data_root.get("properties")
    if isinstance(root_props, dict):
        return root_props
    form = data_root.get("form") or {}
    form_props = form.get("properties")
    if isinstance(form_props, dict):
        return form_props
    flat_data: dict[str, Any] = {}
    record_source = form.get("record_source")
    if isinstance(record_source, str):
        flat_data["recordsource"] = record_source
    if isinstance(form.get("recordsource"), str):
        flat_data["recordsource"] = form.get("recordsource")
    if isinstance(form.get("filter"), str):
        flat_data["filter"] = form.get("filter")
    if isinstance(form.get("orderby"), str):
        flat_data["orderby"] = form.get("orderby")
    flat_event = form.get("event")
    if isinstance(flat_event, dict):
        return {"data": flat_data, "event": flat_event}
    if flat_data:
        return {"data": flat_data}
    return {}


def extract_controls(data_root: dict[str, Any]) -> list[dict[str, Any]]:
    form = data_root.get("form") or {}
    controls = form.get("controls") or data_root.get("controls")
    if isinstance(controls, list):
        return controls
    items = form.get("items") or data_root.get("items")
    if isinstance(items, list):
        return items
    return []


def event_row(
    idx: int,
    kind: str,
    logical_name: str,
    physical_name: str,
    caption: str,
    trigger_key: str,
    handler: str,
    proc: dict[str, Any] | None,
) -> dict[str, str]:
    references = (proc or {}).get("references") or {}
    refs: list[str] = []
    for ref_key in ("queries", "tables", "forms", "modules", "macros"):
        vals = references.get(ref_key) or []
        if vals:
            refs.append(f"{ref_key}:{','.join(str(v) for v in vals[:4])}")
    is_form = kind.strip().lower() == "form"
    return {
        "event_id": f"E{idx:03d}",
        "title": "-" if is_form else (caption or "-"),
        "type": TYPE_MAP.get(kind, kind),
        "logical_name": "-" if is_form else clean_value(logical_name),
        "physical_name": "-" if is_form else clean_value(physical_name),
        "event_trigger": EVENT_TRIGGER_JA.get(trigger_key.lower(), trigger_key),
        "event_content": "",
        "module_id": f"F{idx:03d}",
        "notes": handler,
    }


def collect_events(
    data_root: dict[str, Any],
    proc_map: dict[str, dict[str, Any]],
    label_caption_map: dict[str, str],
    optiongroup_label_map: dict[str, str],
) -> tuple[list[dict[str, str]], dict[str, str]]:
    rows: list[dict[str, str]] = []
    handler_to_event_id: dict[str, str] = {}
    form_name = str((data_root.get("form") or {}).get("name") or data_root.get("name") or "")
    root_events = (root_properties(data_root).get("event")) or {}
    form_prop_events = (((data_root.get("form") or {}).get("properties") or {}).get("event")) or {}
    form_events_merged: dict[str, Any] = {}
    form_events_merged.update(root_events)
    form_events_merged.update(form_prop_events)

    # 1. Guarantee onopen is E000
    onopen_handler = str(form_events_merged.get("onopen") or form_events_merged.get("OnOpen") or "").strip()
    fallback_handler = onopen_handler if onopen_handler else "Form_Open"
    onopen_row = event_row(
        0,
        "Form",
        form_name,
        "-",
        form_name,
        "onopen",
        fallback_handler,
        proc_map.get(fallback_handler),
    )
    onopen_row["event_content"] = "画面の初期表示の処理"
    rows.append(onopen_row)
    handler_to_event_id.setdefault(fallback_handler, onopen_row["event_id"])

    idx = 1
    for trigger, handler_val in form_events_merged.items():
        if trigger.lower() == "onopen":
            continue
        handler = str(handler_val or "").strip()
        if not handler:
            continue
        row = event_row(
            idx,
            "Form",
            form_name,
            "-",
            form_name,
            trigger,
            handler,
            proc_map.get(handler),
        )
        rows.append(row)
        handler_to_event_id.setdefault(handler, row["event_id"])
        idx += 1
    for c in extract_controls(data_root):
        events = (c.get("properties") or {}).get("event") or {}
        if not events:
            continue
        ctype = str(c.get("type") or "")
        logical = logical_name_for_ctrl(c, label_caption_map, optiongroup_label_map)
        cleaned_logical = clean_value(logical)
        final_physical, final_logical = resolve_names(cleaned_logical, ctype)
        desc_title = descriptive_title_for_ctrl(c, label_caption_map, optiongroup_label_map)
        for trigger, handler_val in events.items():
            handler = str(handler_val or "").strip()
            if not handler:
                continue
            row = event_row(
                idx,
                ctype,
                final_logical,
                final_physical,
                desc_title,
                trigger,
                handler,
                proc_map.get(handler),
            )
            rows.append(row)
            handler_to_event_id.setdefault(handler, row["event_id"])
            idx += 1
    return rows, handler_to_event_id


