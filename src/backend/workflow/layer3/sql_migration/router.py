"""
sql_migration/router.py — Layer 3 SQL-migration operations behind the gRPC Layer4Service.

Every function returns a plain dict: ``{"success": True, ...}`` or ``{"success": False, "error": str}``.
Queries under review live in the ``queries_v2`` collection (seeded from Layer 1's ``queries``
by seed_queries_v2.py); table schemas come from Layer 1's ``tables`` collection.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

L3_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = L3_DIR.parent.parent
for _path in (BACKEND_DIR, BACKEND_DIR / "workflow", BACKEND_DIR / "workflow" / "layer2"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from common.config import get_model, QWEN_MAX, LAYER3_MIGRATION_MODEL_NAME
from common.llm.llm_client import parse_json_response
from db.mongo_client import get_db
from utils.llm_client import LLMClient

from layer3.sql_migration.query_utils import build_sql_from_parts, extract_bind_variables

QUERIES_COLLECTION = "queries_v2"
TABLES_COLLECTION = "tables"

_CONVERT_SYSTEM_PROMPT = (
    "You are an expert database administrator specialized in migrating database queries from MS Access dialect to PostgreSQL.\n"
    "Translate the input query into valid PostgreSQL syntax.\n\n"
    "Follow these strict rules:\n"
    "1. Maintain all bind variables (parameters) exactly as they are in the original query (e.g. :txt工事名称, :txt店所コード, etc.). Keep the colons and variable names identical.\n"
    "2. Convert dialect-specific functions to PostgreSQL equivalents:\n"
    "   - IIF() -> CASE WHEN ... THEN ... ELSE ... END\n"
    "   - NVL() / Nz() -> COALESCE()\n"
    "   - Mid() / Mid$() -> SUBSTRING()\n"
    "   - Len() -> LENGTH()\n"
    "   - InStr() -> POSITION() or STRPOS()\n"
    "   - Date() / Now() -> CURRENT_DATE / CURRENT_TIMESTAMP\n"
    "   - Format() -> TO_CHAR()\n"
    "3. Return a JSON response containing:\n"
    "   - \"target_sql\": The translated PostgreSQL query.\n"
    "   - \"target_query_json\": A JSON representation of the query structure (keys: \"select\", \"from\", \"where\", \"group_by\", \"order_by\" if applicable).\n"
    "   - \"explanation\": Brief explanation of the changes made (in English).\n\n"
    "Return ONLY a valid JSON block, without markdown formatting if possible, or inside a ```json ``` block."
)

_CODE_FENCE_RE = re.compile(r"^\s*```[\w-]*\s*\n?(.*?)\n?```\s*$", re.DOTALL)
_SQL_START_RE = re.compile(r"^\s*(select|with|insert|update|delete)\b", re.IGNORECASE)


def _now() -> str:
    return datetime.now().isoformat()


def _queries():
    return get_db()[QUERIES_COLLECTION]


def _with_raw_sql(q: dict | None) -> dict | None:
    """Older documents only carry ``sql``; the review UI reads ``raw_sql``."""
    if q and "sql" in q and "raw_sql" not in q:
        q["raw_sql"] = q["sql"]
    return q


def _target_sql_from_response(response_text: str) -> tuple[str, dict, str]:
    """Return (target_sql, target_query_json, explanation) from the model's reply."""
    try:
        parsed = parse_json_response(response_text)
    except Exception:
        parsed = None
    if isinstance(parsed, dict) and str(parsed.get("target_sql") or "").strip():
        return (
            str(parsed["target_sql"]).strip(),
            parsed.get("target_query_json") or {},
            parsed.get("explanation") or "",
        )
    # Some models ignore the JSON instruction and answer with bare (often fenced) SQL.
    fenced = _CODE_FENCE_RE.match(response_text or "")
    bare = (fenced.group(1) if fenced else response_text or "").strip()
    if _SQL_START_RE.match(bare):
        return bare, {}, ""
    return "", {}, ""


# --- Query review endpoints ---------------------------------------------------------------

def list_queries():
    try:
        queries = [_with_raw_sql(q) for q in _queries().find({}, {"_id": 0})]
        return {"success": True, "result": queries}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_query(name):
    try:
        q = _queries().find_one({"name": name}, {"_id": 0})
        if q:
            return {"success": True, "result": _with_raw_sql(q)}
        return {"success": False, "error": "Query not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_query(name, req):
    """
    Save a reviewed conversion. ``req`` is the gRPC UpdateQueryRequest (or any object with the
    same attributes). proto3 cannot tell "not sent" from "", so empty optional fields are left
    as stored instead of being wiped; ``target_sql`` — the edited SQL itself — is always written.
    """
    try:
        target_sql = req.target_sql or ""
        update_data = {
            "target_sql": target_sql,
            "bind_variables": extract_bind_variables(target_sql),
            "updated_at": _now(),
        }
        if req.target_query_json:
            target_query_json = req.target_query_json
            if isinstance(target_query_json, str):
                try:
                    target_query_json = json.loads(target_query_json)
                except json.JSONDecodeError:
                    return {"success": False, "error": "target_query_json is not valid JSON"}
            update_data["target_query_json"] = target_query_json
        for field, value in (
            ("notes", req.notes),
            ("conversion_status", req.status),
            ("reviewer", req.reviewer),
            ("description", req.description),
        ):
            if value:
                update_data[field] = value

        col = _queries()
        if col.update_one({"name": name}, {"$set": update_data}).matched_count == 0:
            return {"success": False, "error": "Query not found"}
        return {"success": True, "result": _with_raw_sql(col.find_one({"name": name}, {"_id": 0}))}
    except Exception as e:
        return {"success": False, "error": str(e)}


def convert_query(req):
    """LLM-convert one Access query (``req.name``) to PostgreSQL and store it for review."""
    try:
        col = _queries()
        q = col.find_one({"name": req.name})
        if not q:
            return {"success": False, "error": "Query not found"}

        raw_sql = q.get("sql") or build_sql_from_parts(q.get("query"))
        model_name = req.model or LAYER3_MIGRATION_MODEL_NAME
        user_prompt = (
            f"Original Query Name: {req.name}\n"
            f"Original SQL Dialect:\n{raw_sql}\n\n"
            "Translate to PostgreSQL."
        )
        response_text = LLMClient().chat(get_model(model_name, QWEN_MAX), _CONVERT_SYSTEM_PROMPT, user_prompt)

        target_sql, target_query_json, explanation = _target_sql_from_response(response_text)
        if not target_sql:
            raise ValueError(f"model {model_name} returned no target_sql")

        col.update_one({"name": req.name}, {"$set": {
            "target_sql": target_sql,
            "target_query_json": target_query_json,
            "conversion_status": "converted",
            "notes": f"Converted using model: {model_name}. {explanation}".strip(),
            "bind_variables": extract_bind_variables(target_sql),
            "updated_at": _now(),
        }})
        return {"success": True, "result": _with_raw_sql(col.find_one({"name": req.name}, {"_id": 0}))}
    except Exception as e:
        # Record the failure for the review UI, but keep the stored target_sql untouched:
        # it may already hold a reviewer's hand-corrected SQL.
        try:
            _queries().update_one({"name": req.name}, {"$set": {
                "conversion_status": "error",
                "notes": f"Conversion error: {e}",
                "updated_at": _now(),
            }})
        except Exception:
            pass
        return {"success": False, "error": f"SQL conversion failed: {e}"}


def get_stats():
    try:
        col = _queries()
        return {
            "success": True,
            "total": col.count_documents({}),
            "pending": col.count_documents({"conversion_status": "pending"}),
            "converted": col.count_documents({"conversion_status": "converted"}),
            "error_count": col.count_documents({"conversion_status": "error"}),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def seed_queries():
    try:
        from layer3.sql_migration.seed_queries_v2 import seed_v2
        return {"success": True, "count": seed_v2()}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- Table explorer endpoints -------------------------------------------------------------

def list_tables():
    try:
        return {"success": True, "result": list(get_db()[TABLES_COLLECTION].find({}, {"_id": 0}))}
    except Exception as e:
        return {"success": False, "error": str(e)}


def convert_table_schema(table_name: str, target_db: str):
    from layer3.sql_migration.table_converter import convert_table_to_ddl
    try:
        table = get_db()[TABLES_COLLECTION].find_one({"table_name": table_name}, {"_id": 0})
        if not table:
            return {"success": False, "error": f"Table '{table_name}' not found."}
        return {"success": True, "ddl": convert_table_to_ddl(table, target_db)}
    except Exception as e:
        return {"success": False, "error": str(e)}
