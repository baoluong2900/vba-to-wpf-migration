"""
db/layer1_repo.py — Query Layer 1 data from MongoDB

Provides two query modes:
  • bd_code_json  — overview-level data needed by BD Agent
  • dd_code_json  — detail-level data (logic, procedures) needed by DD Agent

Each returns a dict matching the Input Schema defined in vba_brain_L2_IO.md §1.2–1.4
"""
from __future__ import annotations

from typing import Any

from db.mongo_client import get_db
from config import (
    L1_COLLECTION_FORMS,
    L1_COLLECTION_REPORTS,
    L1_COLLECTION_MODULES,
    L1_COLLECTION_QUERIES,
    L1_COLLECTION_MACROS,
    L1_COLLECTION_GRAPH,
)

from db.query_bd import (
    get_bd_code_json_form as q_bd_form,
    get_bd_code_json_report as q_bd_report,
    get_bd_code_json_module as q_bd_module,
    get_bd_code_json_query as q_bd_query,
    get_bd_code_json_macro as q_bd_macro,
)
from db.query_dd import (
    get_dd_code_json_form as q_dd_form,
    get_dd_code_json_report as q_dd_report,
    get_dd_code_json_module as q_dd_module,
    get_dd_code_json_macro as q_dd_macro,
)

from utils.logger import get_logger

logger = get_logger(__name__)


class Layer1Repo:
    """Repository for querying Layer 1 MongoDB collections."""

    CRITICAL_PROPS = {
        "name", "controlsource", "recordsource", "rowsource", "rowsourcetype",
        "format", "inputmask", "validationrule", "validationtext", "defaultvalue",
        "visible", "enabled", "locked", "statusbartext", "controltiptext",
        "linkchildfields", "linkmasterfields", "caption",
        "onclick", "afterupdate", "beforeupdate", "onchange", "ondblclick",
        "ongotfocus", "onlostfocus", "onenter", "onexit",
        "triplestate", "optionvalue", "allowvaluelistedits", "inheritvaluelist",
        "boundcolumn", "columncount", "columnheads", "columnwidths", "listrows", "listwidth",
        "labelname", "optiongroupname",
    }

    def __init__(self) -> None:
        self._db = get_db()

    # ──────────────────────────────────────────────────────────────────────
    # Public: BD queries (overview context)
    # ──────────────────────────────────────────────────────────────────────

    def get_bd_code_json_form(self, form_name: str) -> dict[str, Any]:
        """Return bd_code_json payload for a form (overview: controls, dependencies, graph)."""
        return q_bd_form(self, form_name)

    def get_bd_code_json_report(self, report_name: str) -> dict[str, Any]:
        """Return bd_code_json payload for a report."""
        return q_bd_report(self, report_name)

    def get_bd_code_json_module(self, module_name: str) -> dict[str, Any]:
        """Return bd_code_json payload for a module."""
        return q_bd_module(self, module_name)

    def get_bd_code_json_query(self, query_name: str) -> dict[str, Any]:
        """Return bd_code_json payload for a query."""
        return q_bd_query(self, query_name)

    def get_bd_code_json_macro(self, macro_name: str) -> dict[str, Any]:
        """Return bd_code_json payload for a macro."""
        return q_bd_macro(self, macro_name)

    def get_bd_code_json_unified(self, name: str) -> dict[str, Any]:
        """Auto-detect item type and return its BD code JSON."""
        # Order of search: Forms -> Reports -> Modules -> Queries -> Macros
        for coll, fn in [
            (L1_COLLECTION_FORMS, q_bd_form),
            (L1_COLLECTION_REPORTS, q_bd_report),
            (L1_COLLECTION_MODULES, q_bd_module),
            (L1_COLLECTION_QUERIES, q_bd_query),
            (L1_COLLECTION_MACROS, q_bd_macro),
        ]:
            if self._find_one(coll, name):
                return fn(self, name)
        
        raise ValueError(f"Item not found in any Layer 1 collection: {name}")

    # ──────────────────────────────────────────────────────────────────────
    # Public: DD queries (detail logic context)
    # ──────────────────────────────────────────────────────────────────────

    def get_dd_code_json_form(self, form_name: str, bd_source: dict | None = None) -> dict[str, Any]:
        """Return dd_code_json payload for a form (deep: full vba_procedures with calls)."""
        return q_dd_form(self, form_name, bd_source=bd_source)


    def get_dd_code_json_report(self, report_name: str) -> dict[str, Any]:
        """Return dd_code_json for a report (deep detail)."""
        return q_dd_report(self, report_name)

    def get_dd_code_json_module(self, module_name: str) -> dict[str, Any]:
        """Return dd_code_json for a module (full procedure bodies if available)."""
        return q_dd_module(self, module_name)

    def get_dd_code_json_macro(self, macro_name: str) -> dict[str, Any]:
        """Return dd_code_json for a macro (full action list)."""
        return q_dd_macro(self, macro_name)

    def get_dd_code_json_unified(self, name: str, bd_source: dict | None = None) -> dict[str, Any]:
        """Auto-detect item type and return its DD code JSON."""
        # Forms have special dependency logic using bd_source
        if self._find_one(L1_COLLECTION_FORMS, name):
            return q_dd_form(self, name, bd_source=bd_source)

        for coll, fn in [
            (L1_COLLECTION_REPORTS, q_dd_report),
            (L1_COLLECTION_MODULES, q_dd_module),
            (L1_COLLECTION_MACROS, q_dd_macro),
            (L1_COLLECTION_QUERIES, self.get_bd_code_json_query),
        ]:
            if self._find_one(coll, name):
                return fn(self, name)
        raise ValueError(f"Item not found for DD code JSON: {name}")



    # ──────────────────────────────────────────────────────────────────────

    # Convenience: list all items
    # ──────────────────────────────────────────────────────────────────────
    
    def _remove_empty(self, data: Any) -> Any:
        """Đệ quy để xóa bỏ các giá trị null, rỗng, list rỗng, hoặc dict rỗng."""
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                v_clean = self._remove_empty(v)
                if v_clean is not None and v_clean != "" and v_clean != [] and v_clean != {}:
                    cleaned[k] = v_clean
            return cleaned
        elif isinstance(data, list):
            cleaned_list = []
            for v in data:
                v_clean = self._remove_empty(v)
                if v_clean is not None and v_clean != "" and v_clean != [] and v_clean != {}:
                    cleaned_list.append(v_clean)
            return cleaned_list
        return data
    
    def _sanitize_items(self, items: list) -> list:
        if not items:
            return []
            
        sanitized = []
        for item in items:
            new_item = {"name": item.get("name"), "type": item.get("type")}
            
            # Giữ lại các metadata gốc nhưng bỏ đi uuid 'key' và '_id' thừa thãi
            for k, v in item.items():
                if k not in ["name", "type", "properties", "key", "_id"]:
                    new_item[k] = v

            
            props = item.get("properties", {})
            clean_props = {}
            if isinstance(props, dict):
                for cat, cat_props in props.items():
                    if not isinstance(cat_props, dict):
                        continue
                    
                    cat_lower = cat.lower()
                    # Đặc biệt ưu tiên giữ lại toàn bộ khối 'data' và 'event' (không lọc lẻ tẻ)
                    if cat_lower in ["data", "event"]:
                        if cat_props:
                            clean_props[cat] = cat_props
                    else:
                        # Các khối khác (format, other, ...) thì lọc theo whitelist
                        clean_cat = {pk: pv for pk, pv in cat_props.items() if pk.lower() in self.CRITICAL_PROPS}
                        if clean_cat:
                            clean_props[cat] = clean_cat
            if clean_props:
                new_item["properties"] = clean_props
                
            sanitized.append(new_item)
        return sanitized

    def list_forms(self) -> list[dict]:
        return [{"key": str(d["_id"]), "name": d["name"]} for d in self._db[L1_COLLECTION_FORMS].find({}, {"name": 1, "_id": 1})]

    def list_reports(self) -> list[str]:
        return [d["name"] for d in self._db[L1_COLLECTION_REPORTS].find({}, {"name": 1})]

    def list_modules(self) -> list[str]:
        return [d["name"] for d in self._db[L1_COLLECTION_MODULES].find({}, {"name": 1})]

    def list_queries(self) -> list[str]:
        return [d["name"] for d in self._db[L1_COLLECTION_QUERIES].find({}, {"name": 1})]

    def list_all_items(self) -> list[dict]:
        """Return a list of all forms, reports, modules and macros from MongoDB Layer 1."""
        items = []
        
        mapping = [
            (L1_COLLECTION_FORMS, "form"),
            (L1_COLLECTION_REPORTS, "report"),
            (L1_COLLECTION_MODULES, "module"),
            (L1_COLLECTION_MACROS, "macro")
        ]
        
        for coll, type_label in mapping:
            docs = self._db[coll].find({}, {"name": 1, "_id": 1})
            for d in docs:
                items.append({
                    "key": str(d["_id"]), 
                    "name": d["name"],
                    "type": type_label
                })
        
        # Sort alphabetically by name
        return sorted(items, key=lambda x: x["name"])

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    def _find_one(self, collection: str, name: str) -> dict[str, Any] | None:
        doc = self._db[collection].find_one({"name": name}, {"_id": 0})
        return doc  # type: ignore[return-value]

    def _get_related_macros(self, macro_names: list[str]) -> list[dict[str, Any]]:
        if not macro_names: return []
        items = list(self._db[L1_COLLECTION_MACROS].find({"name": {"$in": macro_names}}, {"_id": 0}))
        return items

    def _get_related_modules(self, module_names: list[str]) -> list[dict[str, Any]]:
        if not module_names: return []
        items = list(self._db[L1_COLLECTION_MODULES].find({"name": {"$in": module_names}}, {"_id": 0}))
        return items


    def _get_related_queries(self, query_names: list[str], with_sql: bool = False) -> list[dict[str, Any]]:
        results = []
        for qname in query_names:
            q = self._find_one(L1_COLLECTION_QUERIES, qname)
            if q:
                entry: dict[str, Any] = {
                    "name": q.get("name"),
                    "query_type": q.get("query_type"),
                    "tables": q.get("tables", []),
                    "target_table": q.get("target_table"),
                    "form_references": q.get("form_references", []),
                    "sql_logic": q.get("query", {}),
                    "parameters": q.get("parameters"),
                }
                if with_sql:
                    entry["raw_sql"] = q.get("raw_sql")
                results.append(entry)
        return results

    def _get_graph_context(self, collection: str, item_name: str) -> dict[str, Any]:
        doc = self._find_one(collection, item_name)
        if not doc:
            return {}
        return {
            "opens_forms": doc.get("opens_forms", []),
            "opened_by": doc.get("opened_by", []),
            "uses_queries": doc.get("uses_queries", []),
            "calls_modules": doc.get("calls_modules", []),
            "direct_macros": doc.get("direct_macros", []),
        }

    def _get_called_by(self, module_name: str) -> list[str]:
        """Find all forms/modules that reference this module."""
        result = []
        for coll in (L1_COLLECTION_FORMS, L1_COLLECTION_MODULES):
            docs = self._db[coll].find(
                {"dependencies.modules": module_name},
                {"name": 1},
            )
            result.extend(d["name"] for d in docs)
        return result
