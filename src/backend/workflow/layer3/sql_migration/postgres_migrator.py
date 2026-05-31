#!/usr/bin/env python3
"""
postgres_migrator.py
--------------------
Reads tables from MongoDB collection ("tables"), converts their schema to PostgreSQL DDL,
and executes the DDL against the PostgreSQL database configured in config.json.
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from pymongo import MongoClient

# Add necessary paths to sys.path
SQL_MIGRATION_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SQL_MIGRATION_DIR.parent.parent.parent
sys.path.insert(0, str(SQL_MIGRATION_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from table_converter import convert_table_to_ddl

def load_config() -> dict:
    # Resolve config.json path
    root_dir = BACKEND_DIR.parent
    config_file = root_dir / "config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Error reading config.json: {e}")
    return {}

def migrate_to_postgres():
    print("[POSTGRES MIGRATOR] Starting migration of tables to PostgreSQL...")
    
    cfg = load_config()
    
    # MongoDB Config
    mongo_cfg = cfg.get("mongodb", {})
    mongo_uri = os.environ.get("MONGO_URI", mongo_cfg.get("uri", "mongodb://localhost:27017"))
    mongo_db_name = os.environ.get("MONGO_DB", mongo_cfg.get("db", "vba_brain_core"))
    
    # PostgreSQL Config
    pg_cfg = cfg.get("postgresql", {})
    pg_host = pg_cfg.get("host", "localhost")
    pg_port = pg_cfg.get("port", 5432)
    pg_db = pg_cfg.get("database", "vba_brain")
    pg_user = pg_cfg.get("username", "postgres")
    pg_pass = pg_cfg.get("password", "")
    
    # Fetch tables from MongoDB
    client = MongoClient(mongo_uri)
    db = client[mongo_db_name]
    tables_col = db["tables"]
    
    tables = list(tables_col.find({}, {"_id": 0}))
    if not tables:
        print("[POSTGRES MIGRATOR] No tables found in MongoDB 'tables' collection. Skipping.")
        return
        
    print(f"[POSTGRES MIGRATOR] Found {len(tables)} tables in MongoDB. Commencing migration...")
    
    # Configure env with PGPASSWORD for psql CLI
    env = os.environ.copy()
    if pg_pass:
        env["PGPASSWORD"] = pg_pass
        
    success_count = 0
    
    import re
    JP_REGEX = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]')
    
    for table in tables:
        table_name = table.get("table_name")
        if not table_name:
            continue

        # Guard against SQL injection: table_name is interpolated into psql -c commands
        # (both the CREATE/DROP below and the Japanese-name DROP branch). Allow only
        # alphanumerics, underscore and Japanese characters — block quotes/semicolons/etc.
        if not re.fullmatch(r'[A-Za-z0-9_\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+', table_name):
            print(f"[POSTGRES MIGRATOR] Skipping table with unsafe name '{table_name}'.")
            continue
            
        # Check if table name contains Japanese characters and skip/drop
        if JP_REGEX.search(table_name):
            print(f"[POSTGRES MIGRATOR] Skipping Japanese table '{table_name}' for PostgreSQL.")
            try:
                drop_cmd = [
                    "psql",
                    "-h", pg_host,
                    "-p", str(pg_port),
                    "-U", pg_user,
                    "-d", pg_db,
                    "-c", f"DROP TABLE IF EXISTS \"{table_name.lower()}\" CASCADE;"
                ]
                subprocess.run(drop_cmd, env=env, capture_output=True, check=True)
            except Exception as drop_err:
                pass
            continue
            
        print(f"\n--- Migrating Table: {table_name} ---")
        
        # Generate PostgreSQL DDL
        ddl = convert_table_to_ddl(table, "PostgreSQL")
        
        # Drop and create commands
        full_sql = f"DROP TABLE IF EXISTS {table_name} CASCADE;\n\n{ddl}"
        print(f"[DDL Generated]:\n{ddl}")
        
        # Execute using psql CLI
        cmd = [
            "psql",
            "-h", pg_host,
            "-p", str(pg_port),
            "-U", pg_user,
            "-d", pg_db,
            "-c", full_sql
        ]
        
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
            print(f"[SUCCESS] Table '{table_name}' migrated successfully.")
            success_count += 1
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to execute DDL for table '{table_name}':")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            
    print(f"\n[POSTGRES MIGRATOR] Migration complete. {success_count}/{len(tables)} tables migrated successfully.")
    client.close()

if __name__ == "__main__":
    migrate_to_postgres()
