"""
seed_queries_v2.py
------------------
Seed Layer 1's raw Access queries (MongoDB ``queries``) into ``queries_v2`` — the collection
Layer 2 reads for query context and Layer 3 uses for SQL review.

New queries are inserted with review fields reset; queries already present get their source
fields (SQL text, structured query, tables, parameters) refreshed while every review field
(target_sql, conversion_status, reviewer, notes, description, …) is left untouched.

Usage:
    python seed_queries_v2.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
for _path in (BACKEND_DIR, BACKEND_DIR / "workflow", BACKEND_DIR / "workflow" / "layer2"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from common.config import MONGO_DB
from db.mongo_client import get_db

from layer3.sql_migration.query_utils import build_sql_from_parts, query_type_of, target_table_of

SOURCE_COLLECTION = "queries"
TARGET_COLLECTION = "queries_v2"


def source_fields(doc: dict) -> dict:
    """The queries_v2 fields derived from one Layer 1 query document."""
    query = doc.get("query") or {}
    # query_parser stores the original text as "sql"; older imports only have the structure.
    sql = doc.get("sql") or build_sql_from_parts(query)
    return {
        "sql": sql,
        "raw_sql": sql,
        "query": query,
        "query_type": query_type_of(query),
        "tables": doc.get("tables") or [],
        "target_table": target_table_of(query),
        "parameters": doc.get("parameters") or [],
    }


def seed_v2() -> int:
    """Sync ``queries`` → ``queries_v2``; return how many new queries were inserted."""
    db = get_db()
    if SOURCE_COLLECTION not in db.list_collection_names():
        print(f"[WARN] No '{SOURCE_COLLECTION}' collection in database '{MONGO_DB}' — run Layer 1 seeding first.")
        return 0

    target = db[TARGET_COLLECTION]
    inserted = refreshed = 0
    now_iso = datetime.now().isoformat()

    for doc in db[SOURCE_COLLECTION].find():
        name = doc.get("name") or doc.get("query_name")
        if not name:
            continue
        fields = source_fields(doc)

        if target.find_one({"name": name}, {"_id": 1}):
            target.update_one({"name": name}, {"$set": {**fields, "updated_at": now_iso}})
            refreshed += 1
            continue

        target.insert_one({
            "name": name,
            **fields,
            "target_sql": "",
            "target_query_json": {},
            "conversion_status": "pending",
            "reviewer": "",
            "notes": "",
            "description": doc.get("description", ""),
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        inserted += 1

    print(f"[INFO] queries_v2 in '{MONGO_DB}': {inserted} inserted, {refreshed} refreshed.")
    return inserted


if __name__ == "__main__":
    seed_v2()
