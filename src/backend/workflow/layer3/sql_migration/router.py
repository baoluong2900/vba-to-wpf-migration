import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient

# Add necessary paths to sys.path
L4_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = L4_DIR.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BACKEND_DIR / "workflow" / "layer2") not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer2"))

from common.config import get_model, QWEN_MAX, ModelConfig, LAYER3_MIGRATION_MODEL_NAME
from utils.llm_client import LLMClient
from common.llm.llm_client import parse_json_response

def _get_db():
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    client = MongoClient(mongo_uri)
    db_name = os.environ.get("MONGO_DB", "vba_brain_core")
    db = client[db_name]
    
    # Fallback to vba_brain_core if queries_v2 exists there or queries collection exists there
    if "queries_v2" not in db.list_collection_names() and "queries" not in db.list_collection_names():
        if "vba_brain_core" in client.list_database_names():
            db = client["vba_brain_core"]
    return db

def _parse_sql_components(sql: str) -> list[str]:
    """Helper used by verify_fix.py to simulate bind variable extraction."""
    # Matches :var_name including Japanese characters and Roman numerals
    pattern = r':\s*([a-zA-Z0-9_＿\u4e00-\u9fa5\u3040-\u309F\u30A0-\u30FF\uFF00-\uFFEF\u2160-\u216B]+)'
    return list(set(re.findall(pattern, sql)))

def list_queries():
    try:
        db = _get_db()
        col = db["queries_v2"]
        queries = list(col.find({}, {"_id": 0}))
        return {"success": True, "result": queries}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_query(name):
    try:
        db = _get_db()
        col = db["queries_v2"]
        q = col.find_one({"name": name}, {"_id": 0})
        if q:
            return {"success": True, "result": q}
        return {"success": False, "error": "Query not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def update_query(name, req):
    try:
        db = _get_db()
        col = db["queries_v2"]
        
        # Resolve target query json safely
        target_query_json = req.target_query_json
        if isinstance(target_query_json, str):
            try:
                target_query_json = json.loads(target_query_json)
            except Exception:
                target_query_json = {}
                
        # Simulate bind variable extraction if target_sql changes
        bind_vars = _parse_sql_components(req.target_sql or "")
        
        update_data = {
            "target_sql": req.target_sql,
            "target_query_json": target_query_json,
            "notes": req.notes,
            "conversion_status": req.status,
            "reviewer": req.reviewer,
            "description": req.description,
            "bind_variables": bind_vars,
            "updated_at": datetime.now().isoformat()
        }
        
        result = col.update_one({"name": name}, {"$set": update_data})
        if result.matched_count > 0:
            updated = col.find_one({"name": name}, {"_id": 0})
            return {"success": True, "result": updated}
        return {"success": False, "error": "Query not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def convert_query(req):
    try:
        db = _get_db()
        col = db["queries_v2"]
        q = col.find_one({"name": req.name})
        if not q:
            return {"success": False, "error": "Query not found"}
            
        raw_sql = q.get("sql") or ""
        if not raw_sql:
            # Build from query field if sql is empty
            q_dict = q.get("query", {}) or {}
            sql_parts = []
            if q_dict.get("select") and q_dict["select"] != "なし":
                sql_parts.append(f"SELECT {q_dict['select']}")
            if q_dict.get("from") and q_dict["from"] != "なし":
                sql_parts.append(f"FROM {q_dict['from']}")
            if q_dict.get("where") and q_dict["where"] != "なし":
                sql_parts.append(f"WHERE {q_dict['where']}")
            if q_dict.get("group_by") and q_dict["group_by"] != "なし":
                sql_parts.append(f"GROUP BY {q_dict['group_by']}")
            if q_dict.get("order_by") and q_dict["order_by"] != "なし":
                sql_parts.append(f"ORDER BY {q_dict['order_by']}")
            raw_sql = "\n".join(sql_parts)
            
        # Call LLM for translation
        model_name = req.model if req.model else LAYER3_MIGRATION_MODEL_NAME
        model_cfg = get_model(model_name, QWEN_MAX)
        
        system_prompt = (
            "You are an expert database administrator specialized in migrating database queries from MS Access/Oracle dialect to PostgreSQL.\n"
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
        
        user_prompt = (
            f"Original Query Name: {req.name}\n"
            f"Original SQL Dialect:\n{raw_sql}\n\n"
            "Translate to PostgreSQL."
        )
        
        client = LLMClient()
        response_text = client.chat(model_cfg, system_prompt, user_prompt)
        
        # Parse response JSON
        parsed = {}
        try:
            parsed = parse_json_response(response_text)
        except Exception:
            # Fallback regex extraction of json if custom parser fails
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except Exception:
                    pass
                    
        target_sql = parsed.get("target_sql") or response_text
        target_query_json = parsed.get("target_query_json") or {}
        explanation = parsed.get("explanation") or ""
        
        # Extract bind variables
        bind_vars = _parse_sql_components(target_sql)
        
        update_data = {
            "target_sql": target_sql,
            "target_query_json": target_query_json,
            "conversion_status": "converted",
            "notes": f"Converted using model: {model_name}. {explanation}",
            "bind_variables": bind_vars,
            "updated_at": datetime.now().isoformat()
        }
        
        col.update_one({"name": req.name}, {"$set": update_data})
        updated = col.find_one({"name": req.name}, {"_id": 0})
        return {"success": True, "result": updated}
        
    except Exception as e:
        # Save error status and rollback target_sql dynamically to raw_sql to avoid hardcoding
        try:
            db = _get_db()
            col = db["queries_v2"]
            fallback_sql = raw_sql if 'raw_sql' in locals() else ""
            col.update_one(
                {"name": req.name},
                {"$set": {
                    "target_sql": fallback_sql,
                    "conversion_status": "error",
                    "notes": f"Conversion error: {str(e)}",
                    "updated_at": datetime.now().isoformat()
                }}
            )
        except Exception:
            pass
        return {"success": False, "error": f"Lỗi chuyển đổi SQL: {str(e)}"}

def get_stats():
    try:
        db = _get_db()
        col = db["queries_v2"]
        total = col.count_documents({})
        pending = col.count_documents({"conversion_status": "pending"})
        converted = col.count_documents({"conversion_status": "converted"})
        error_count = col.count_documents({"conversion_status": "error"})
        return {
            "success": True,
            "total": total,
            "pending": pending,
            "converted": converted,
            "error_count": error_count
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def seed_queries():
    try:
        from sql_migration.seed_queries_v2 import seed_v2
        count = seed_v2()
        return {"success": True, "count": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- Table Explorer Endpoints ---
def list_tables():
    from db.mongo_client import get_db
    db = get_db()
    col = db["tables"]
    # Return all tables as a list of dicts
    tables = list(col.find({}, {"_id": 0}))
    return {"success": True, "result": tables}

def convert_table_schema(table_name: str, target_db: str):
    from db.mongo_client import get_db
    from layer3.sql_migration.table_converter import convert_table_to_ddl
    db = get_db()
    col = db["tables"]
    table = col.find_one({"table_name": table_name}, {"_id": 0})
    if not table:
        return {"success": False, "error": f"Table '{table_name}' not found."}
    
    try:
        ddl = convert_table_to_ddl(table, target_db)
        return {"success": True, "ddl": ddl}
    except Exception as e:
        return {"success": False, "error": str(e)}
