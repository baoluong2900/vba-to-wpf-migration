"""
db/query_bd.py — Basic Design (BD) Query Implementations
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
    L1_COLLECTION_REPORTS,
    L1_COLLECTION_MODULES,
    L1_COLLECTION_QUERIES,
    L1_COLLECTION_GRAPH,
)

def get_bd_code_json_form(repo: Any, form_name: str) -> dict[str, Any]:
    """Return bd_code_json payload for a form (overview: controls, dependencies, graph)."""
    form = repo._find_one(L1_COLLECTION_FORMS, form_name)
    if not form:
        raise ValueError(f"Form not found in Layer 1: {form_name}")

    related_queries = repo._get_related_queries(form.get("dependencies", {}).get("queries", []))
    graph_context = repo._get_graph_context(L1_COLLECTION_GRAPH, form_name)

    # Get advanced properties if present in the old DB schema
    props = form.get("properties", {})
    data_props = props.get("data", {})
    format_props = props.get("format", {})

    payload = {
        "request_type": "form_analysis",
        "form": {
            "name": form.get("name"),
            "file": form.get("file"),
            "type": form.get("type"),
            "record_source": form.get("record_source", data_props.get("recordsource")),
            "filter": form.get("filter", data_props.get("filter")),
            "orderby": form.get("orderby", data_props.get("orderby")),
            "event": form.get("event", props.get("event")),
            "caption": form.get("caption", format_props.get("caption")),
            "properties": form.get("properties", {}),
            "variables": form.get("variables", []),
            "controls": repo._sanitize_items(form.get("controls", form.get("items", []))),
            "vba_procedures": form.get("functions", form.get("vba_procedures", [])),
            "dependencies": form.get("dependencies", {}),
            "vba_loc": form.get("vba_loc", 0),
            "complexity_level": form.get("complexity_level", "low"),
        },
        "related_queries": related_queries,
        "graph_context": graph_context,
    }
    return repo._remove_empty(payload)

def get_bd_code_json_report(repo: Any, report_name: str) -> dict[str, Any]:
    """Return bd_code_json payload for a report."""
    report = repo._find_one(L1_COLLECTION_REPORTS, report_name)
    if not report:
        raise ValueError(f"Report not found in Layer 1: {report_name}")

    related_queries = repo._get_related_queries(
        report.get("dependencies", {}).get("queries", [])
    )
    payload = {
        "request_type": "report_analysis",
        "report": {
            "name": report.get("name"),
            "file": report.get("file"),
            "type": report.get("type", "report"),
            "report_type": report.get("report_type", "report"),
            "record_source": report.get("record_source"),
            "properties": report.get("properties", {}),
            "controls": repo._sanitize_items(report.get("controls", report.get("items", []))),
            "grouping": report.get("grouping", []),
            "sorting": report.get("sorting", []),
            "sections": report.get("sections", []),
            "subreports": report.get("subreports", []),
            "has_vba": report.get("has_vba", False),
            "vba_procedures": report.get("vba_procedures", report.get("functions", [])),
            "dependencies": report.get("dependencies", {}),
        },
        "related_queries": related_queries,
    }
    return repo._remove_empty(payload)

def get_bd_code_json_module(repo: Any, module_name: str) -> dict[str, Any]:
    """Return bd_code_json payload for a module."""
    module = repo._find_one(L1_COLLECTION_MODULES, module_name)
    if not module:
        raise ValueError(f"Module not found in Layer 1: {module_name}")

    called_by = repo._get_called_by(module_name)
    payload = {
        "request_type": "module_analysis",
        "module": {
            "name": module.get("name"),
            "file": module.get("file"),
            "procedures": module.get("vba_procedures", module.get("functions", module.get("procedures", []))),
            "api_declarations": module.get("api_declarations", []),
            "global_variables": module.get("global_variables", []),
            "constants": module.get("constants", []),
            "user_types": module.get("user_types", []),
            "com_references": module.get("com_references", []),
            "table_renames": module.get("table_renames", []),
            "loc": module.get("vba_loc", module.get("loc", 0)),
            "called_by": called_by,
        },
    }
    return repo._remove_empty(payload)


def get_bd_code_json_macro(repo: Any, macro_name: str) -> dict[str, Any]:
    """Return bd_code_json payload for a macro."""
    from config import L1_COLLECTION_MACROS
    macro = repo._find_one(L1_COLLECTION_MACROS, macro_name)
    if not macro:
        raise ValueError(f"Macro not found in Layer 1: {macro_name}")

    payload = {
        "request_type": "macro_analysis",
        "macro": {
            "name": macro.get("name"),
            "file": macro.get("file"),
            "actions": [_unescape_action(a) for a in macro.get("actions", macro.get("steps", []))],
            "steps": [_unescape_action(a) for a in macro.get("steps", macro.get("actions", []))],
            "references": macro.get("references", macro.get("dependencies", {})),
            "raw_xml": _format_xml(macro.get("raw_xml", "")),
        },
    }
    return repo._remove_empty(payload)


def get_bd_code_json_query(repo: Any, query_name: str) -> dict[str, Any]:
    """Return bd_code_json payload for a standalone query."""
    q = repo._find_one(L1_COLLECTION_QUERIES, query_name)
    if not q:
        raise ValueError(f"Query not found in Layer 1: {query_name}")

    payload = {
        "request_type": "query_analysis",
        "query": {
            "name": q.get("name"),
            "query_type": q.get("query_type"),
            "tables": q.get("tables", []),
            "target_table": q.get("target_table"),
            "description": q.get("description"),
            "parameters": q.get("parameters", []),
            "sql_logic": q.get("query", {}),
            "form_references": q.get("form_references", []),
        },
    }
    return repo._remove_empty(payload)


def get_bd_code_json_table(repo: Any, table_name: str) -> dict[str, Any]:
    """Get all data of a table from Layer 1."""
    from config import L1_COLLECTION_TABLES
    t = repo._find_one(L1_COLLECTION_TABLES, table_name)
    if not t:
        raise ValueError(f"Table not found in Layer 1: {table_name}")
    return t


def get_bd_code_json_query_raw(repo: Any, query_name: str) -> dict[str, Any]:
    """Get all data of a query from Layer 1 (without transformation)."""
    from config import L1_COLLECTION_QUERIES
    q = repo._find_one(L1_COLLECTION_QUERIES, query_name)
    if not q:
        raise ValueError(f"Query not found in Layer 1: {query_name}")
    return q
