#!/usr/bin/env python3
"""
seed_db.py — Python utility to seed Layer 1 JSON files from database_json/ into MongoDB.

Replicates the exact functionality of frontend/seed_db.js.
Reads configuration from workflow/config.json or environment variables.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# ── Load PyMongo dynamically to allow prompt execution without pre-installed packages ──
try:
    from pymongo import MongoClient
except ImportError:
    print("[ERROR] pymongo is not installed. Please run: pip install pymongo", file=sys.stderr)
    sys.exit(1)

# ── Paths & Folders (Hardcoded) ────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[4]
CONFIG_FILE = Path("config.json")
if not CONFIG_FILE.exists():
    CONFIG_FILE = ROOT / "config.json"

DATABASE_JSON_DIR = ROOT / "src" / "VBA" / "vba_source" / "output"

ALL_FOLDERS = ["forms", "macros", "modules", "queries", "tables"]

# ── Load Config ────────────────────────────────────────────────────────────────
def load_config() -> tuple[str, str]:
    # Default fallback values
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.environ.get("MONGO_DB", "vba_brain_core")

    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            mongo_cfg = cfg.get("mongodb", {})
            if "uri" in mongo_cfg:
                mongo_uri = mongo_cfg["uri"]
            if "db" in mongo_cfg:
                mongo_db = mongo_cfg["db"]
        except Exception as e:
            print(f"[WARN] Error reading config.json: {e}. Using defaults/environment.")
            
    return mongo_uri, mongo_db

# ── Helpers ───────────────────────────────────────────────────────────────────
def clean_large_fields(obj: Any) -> None:
    """Recursively drops extremely large fields (e.g. picturedata) to optimize DB space."""
    if not isinstance(obj, dict):
        return
    keys_to_delete = []
    for key, val in list(obj.items()):
        lower_key = key.lower()
        if lower_key in ("picturedata", "picturedata_base64"):
            keys_to_delete.append(key)
        elif isinstance(val, str) and len(val) > 500000:
            keys_to_delete.append(key)  # drop strings > 500 KB
        elif isinstance(val, dict):
            clean_large_fields(val)
        elif isinstance(val, list):
            for item in val:
                clean_large_fields(item)
    for key in keys_to_delete:
        del obj[key]

def get_record_name(data: dict, file_stem: str) -> str:
    """Deduce name field for identification."""
    return (
        data.get("name")
        or data.get("screen_id")
        or data.get("form_name")
        or data.get("screen_name")
        or data.get("query_name")
        or data.get("table_name")
        or data.get("macro_name")
        or data.get("module_name")
        or file_stem
    )

def parse_file(file_path: Path) -> dict:
    """Parses JSON or JSONL format."""
    text = file_path.read_text(encoding="utf-8").lstrip("\ufeff")
    if file_path.suffix.lower() == ".jsonl":
        merged = {}
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    merged.update(json.loads(line))
                except Exception:
                    pass
        return merged
    return json.loads(text)

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed Layer 1 JSON files from database_json/ into MongoDB."
    )
    parser.add_argument("--dry-run", action="store_true", help="List files without inserting.")
    parser.add_argument("--only", type=str, default=None, help="Process only a single folder (e.g. forms).")
    args = parser.parse_args()

    if not DATABASE_JSON_DIR.exists():
        print(f"[ERROR] Directory database_json not found at {DATABASE_JSON_DIR}", file=sys.stderr)
        return 1

    mongo_uri, mongo_db_name = load_config()

    # Use hardcoded list of directories
    folders = [f for f in ALL_FOLDERS if f == args.only] if args.only else ALL_FOLDERS

    if not folders:
        print(f"[WARN] No matching directories found in {DATABASE_JSON_DIR}")
        return 0

    if args.dry_run:
        print(f"[DRY-RUN] Would seed these directories -> {', '.join(folders)}")

    print(f"MongoDB URI -> {mongo_uri}")
    print(f"Database    -> {mongo_db_name}\n")

    client = None
    if not args.dry_run:
        print("Connecting to MongoDB...")
        try:
            client = MongoClient(mongo_uri)
            db = client[mongo_db_name]
            print("Connected.\n")
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}", file=sys.stderr)
            return 1

    total_ok = 0
    total_skip = 0
    total_err = 0

    for folder_name in folders:
        folder_path = DATABASE_JSON_DIR / folder_name
        collection_name = folder_name

        # Find .json or .jsonl files (exclude .gitkeep)
        files = sorted([
            f for f in folder_path.iterdir()
            if f.is_file() and f.suffix.lower() in (".json", ".jsonl") and f.name != ".gitkeep"
        ])

        print(f"📂 [{collection_name}] {len(files)} file(s)")

        if args.dry_run:
            for f in files:
                print(f"   • {f.name}")
            total_ok += len(files)
            continue

        col = db[collection_name]
        ok = 0
        skip = 0
        err_count = 0

        for f in files:
            try:
                data = parse_file(f)
                if not data or not isinstance(data, dict):
                    skip += 1
                    continue

                record_name = get_record_name(data, f.stem)
                if "name" not in data:
                    data["name"] = record_name

                clean_large_fields(data)

                col.update_one(
                    {"name": record_name},
                    {"$set": data},
                    upsert=True
                )
                ok += 1
            except Exception as e:
                print(f"   ❌ {f.name}: {e}", file=sys.stderr)
                err_count += 1

        print(f"   ✅ upserted={ok}  skipped={skip}  errors={err_count}")
        total_ok += ok
        total_skip += skip
        total_err += err_count

    # Seed reference_map.json if it exists
    ref_map_path = DATABASE_JSON_DIR / "reference_map.json"
    if ref_map_path.exists() and not args.dry_run:
        try:
            print("📂 [reference_map] 1 file(s)")
            ref_map_data = json.loads(ref_map_path.read_text(encoding="utf-8"))
            col = db["reference_map"]
            col.update_one(
                {"name": "global_reference_map"},
                {"$set": {
                    "name": "global_reference_map",
                    "data": ref_map_data
                }},
                upsert=True
            )
            print("   ✅ upserted=1  skipped=0  errors=0")
            total_ok += 1
        except Exception as e:
            print(f"   ❌ reference_map.json: {e}", file=sys.stderr)
            total_err += 1

    print(f"\n🎉 Done — upserted={total_ok}  skipped={total_skip}  errors={total_err}")
    if client:
        client.close()

    return 1 if total_err > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
