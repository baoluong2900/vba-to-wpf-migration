"""
db/query_dd.py — Detail Design (DD) Query Implementations
"""
from __future__ import annotations
from typing import Any
import xml.dom.minidom
import html

def _format_xml(xml_str: str) -> str:
    if not xml_str:
        return ""
    try:
        # Remove extra whitespace between tags to avoid minidom bug
        cleaned = "".join(line.strip() for line in xml_str.splitlines())
        dom = xml.dom.minidom.parseString(cleaned)
        return dom.toprettyxml(indent="  ")
    except Exception:
        return xml_str

def _unescape_action(action: dict) -> dict:
    if not isinstance(action, dict):
        return action
    new_act = {}
    for k, v in action.items():
        if isinstance(v, str):
            new_act[k] = html.unescape(v)
        elif isinstance(v, dict):
            new_act[k] = _unescape_action(v)
        elif isinstance(v, list):
            new_act[k] = [_unescape_action(x) if isinstance(x, dict) else x for x in v]
        else:
            new_act[k] = v
    return new_act

from config import (
    L1_COLLECTION_FORMS,
    L1_COLLECTION_GRAPH,
    L1_COLLECTION_MACROS,
    L1_COLLECTION_MODULES,
)


def get_dd_code_json_form(repo: Any, form_name: str, bd_source: dict | None = None) -> dict[str, Any]:
    """
    Return dd_code_json payload for a form.
    If bd_source is provided, use it to find deeper dependencies (macros, modules, tables).
    """

    form = repo._find_one(L1_COLLECTION_FORMS, form_name)
    if not form:
        raise ValueError(f"Form not found in Layer 1: {form_name}")

    # Combine dependencies from DB and BD source
    dep_queries = set(form.get("dependencies", {}).get("queries", []))
    dep_macros = set(form.get("dependencies", {}).get("macros", []))
    dep_modules = set(form.get("dependencies", {}).get("modules", []))
    dep_tables = set(form.get("dependencies", {}).get("tables", []))

    if bd_source:
        # Extract from bd1_bd_form/F_Login.json structure
        # (usually in 'references' field of each procedure)
        for proc in bd_source.get("form", {}).get("vba_procedures", []):
            refs = proc.get("references", {})
            dep_queries.update(refs.get("queries", []))
            dep_macros.update(refs.get("macros", []))
            dep_modules.update(refs.get("modules", []))
            dep_tables.update(refs.get("tables", []))

    related_queries = repo._get_related_queries(list(dep_queries), with_sql=True)
    related_macros = repo._get_related_macros(list(dep_macros))
    related_modules = repo._get_related_modules(list(dep_modules))
    # Tables are usually included in queries, but we can list them explicitly if needed

    graph_context = repo._get_graph_context(L1_COLLECTION_GRAPH, form_name)

    # Get advanced properties if present in the old DB schema
    props = form.get("properties", {})
    data_props = props.get("data", {})

    payload = {
        "request_type": "form_detail_analysis",
        "form": {
            "name": form.get("name"),
            "file": form.get("file"),
            "record_source": form.get("record_source", data_props.get("RecordSource")),
            "controls": repo._sanitize_items(form.get("controls", form.get("items", []))),
            "vba_procedures": form.get("vba_procedures", form.get("functions", [])),   # full detail
            "dependencies": form.get("dependencies", {}),
            "vba_loc": form.get("vba_loc", 0),
            "complexity_level": form.get("complexity_level", "low"),
        },
        "related_queries": related_queries,
        "related_macros": related_macros,
        "related_modules": related_modules,
        "graph_context": graph_context,
    }

    return repo._remove_empty(payload)

def get_dd_code_json_report(repo: Any, report_name: str) -> dict[str, Any]:
    """Return dd_code_json for a report (deep detail)."""
    # For reports, bd and dd payloads are structurally similar;
    # dd includes full section/subreport trees and full vba
    return repo.get_bd_code_json_report(report_name)

def get_dd_code_json_module(repo: Any, module_name: str) -> dict[str, Any]:
    """Return dd_code_json for a module (full procedure bodies if available)."""
    module = repo._find_one(L1_COLLECTION_MODULES, module_name)
    if not module:
        raise ValueError(f"Module not found: {module_name}")
    
    # Dependencies
    dep_queries = module.get("dependencies", {}).get("queries", [])
    dep_macros = module.get("dependencies", {}).get("macros", [])
    dep_modules = module.get("dependencies", {}).get("modules", [])

    related_queries = repo._get_related_queries(dep_queries, with_sql=True)
    related_macros = repo._get_related_macros(dep_macros)
    related_modules = repo._get_related_modules(dep_modules)

    payload = {
        "request_type": "module_detail_analysis",
        "module": {
            "name": module.get("name"),
            "file": module.get("file") or module.get("source_file"),
            "options": module.get("options", {}),
            "constants": module.get("constants", []),
            "user_types": module.get("user_types", []),
            "api_declarations": module.get("api_declarations", []),
            "global_variables": module.get("global_variables", []),
            "table_renames": module.get("table_renames", []),
            "functions": module.get("vba_procedures", module.get("functions", module.get("procedures", []))),
            "vba_loc": module.get("vba_loc", module.get("loc", 0)),

            "dependencies": module.get("dependencies", {}),
        },
        "related_queries": related_queries,
        "related_macros": related_macros,
        "related_modules": related_modules,
        "graph_context": repo._get_graph_context(L1_COLLECTION_GRAPH, module_name),
    }


    return repo._remove_empty(payload)

def get_dd_code_json_macro(repo: Any, macro_name: str) -> dict[str, Any]:
    """Return dd_code_json for a macro (full action list)."""
    macro = repo._find_one(L1_COLLECTION_MACROS, macro_name)
    if not macro:
        raise ValueError(f"Macro not found: {macro_name}")
    
    # Dependencies
    refs = macro.get("references") or macro.get("dependencies") or {}
    dep_queries = refs.get("queries", [])
    dep_macros = refs.get("macros", [])
    dep_modules = refs.get("modules", []) or refs.get("vba_calls", [])

    payload = {
        "request_type": "macro_detail_analysis",
        "macro": {
            "name": macro.get("name"),
            "source_file": macro.get("file") or macro.get("source_file") or f"{macro.get('name')}.mac",
            "raw_xml": _format_xml(macro.get("raw_xml", "")),
            "references": {
                "forms": refs.get("forms") or [],
                "queries": refs.get("queries") or [],
                "macros": refs.get("macros") or [],
                "vba_calls": refs.get("vba_calls") or refs.get("modules") or [],
                "tables": refs.get("tables") or []
            }
        },
    }
    return repo._remove_empty(payload)

def get_dd_code_json_table(repo: Any, table_name: str) -> dict[str, Any]:
    from config import L1_COLLECTION_TABLES
    t = repo._find_one(L1_COLLECTION_TABLES, table_name)
    if not t:
        raise ValueError(f"Table not found in Layer 1: {table_name}")
    return t

def get_dd_code_json_query_raw(repo: Any, query_name: str) -> dict[str, Any]:
    from config import L1_COLLECTION_QUERIES
    import unicodedata

    # 1. Try exact match first
    q = repo._db[L1_COLLECTION_QUERIES].find_one({"name": query_name}, {"_id": 0})
    if q:
        return q

    # 2. Fallback: Fullwidth/Halfwidth robust matching
    norm_input = unicodedata.normalize('NFKC', query_name)
    # Fetch all query names from DB
    all_q_names = repo._db[L1_COLLECTION_QUERIES].find({}, {"name": 1})
    
    actual_name = None
    for item in all_q_names:
        db_name = item.get("name", "")
        if unicodedata.normalize('NFKC', db_name) == norm_input:
            actual_name = db_name
            break
            
    if actual_name:
        # Fetch the actual document using the found name
        q = repo._db[L1_COLLECTION_QUERIES].find_one({"name": actual_name}, {"_id": 0})
        if q:
            return q

    raise ValueError(f"Query not found in Layer 1: {query_name}")
