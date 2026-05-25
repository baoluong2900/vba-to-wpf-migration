"""
seed_queries_v2.py
------------------
Seeds raw queries from Layer 1 MongoDB collection ("queries") into Layer 4 SQL Migration collection ("queries_v2").
Supports both 'vba_brain_core' and 'vba_brain_core' databases.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient

def seed_v2() -> int:
    # Resolve MongoDB connection
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    client = MongoClient(mongo_uri)
    
    # Auto-detect DB containing L1 data
    db_name = os.environ.get("MONGO_DB", "vba_brain_core")
    db = client[db_name]
    
    # If the configured db doesn't have queries, check 'vba_brain_core'
    if "queries" not in db.list_collection_names() and "vba_brain_core" in client.list_database_names():
        print(f"[INFO] Collection 'queries' not found in db '{db_name}'. Falling back to 'vba_brain_core'.")
        db = client["vba_brain_core"]
        db_name = "vba_brain_core"
        
    if "queries" not in db.list_collection_names():
        print("[WARN] No 'queries' collection found in any database. Seeding aborted.")
        return 0
        
    raw_queries_col = db["queries"]
    target_queries_col = db["queries_v2"]
    
    count = 0
    now_iso = datetime.now().isoformat()
    
    for doc in raw_queries_col.find():
        name = doc.get("name") or doc.get("query_name")
        if not name:
            continue
            
        # Check if already exists in queries_v2 to avoid duplicate seeds
        if target_queries_col.find_one({"name": name}):
            continue
            
        # Rebuild raw SQL from structured select/from/where/etc.
        q_dict = doc.get("query", {}) or {}
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
            
        raw_sql = "\n".join(sql_parts) if sql_parts else ""
        
        # Build entry
        new_doc = {
            "name": name,
            "sql": raw_sql,
            "parameters": doc.get("parameters") or [],
            "target_sql": "",
            "target_query_json": {},
            "conversion_status": "pending",
            "reviewer": "",
            "notes": "",
            "description": doc.get("description", ""),
            "created_at": now_iso,
            "updated_at": now_iso
        }
        
        target_queries_col.insert_one(new_doc)
        count += 1
        
    print(f"[INFO] Seeded {count} queries into database '{db_name}' collection 'queries_v2'.")
    client.close()
    return count

if __name__ == "__main__":
    seed_v2()
