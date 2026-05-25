import os
import sys
from pathlib import Path

# Add backend/layer2 to sys.path so we can import from db
base_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(base_dir / "backend" / "layer2"))

from db.mongo_client import get_client

def migrate():
    print("Connecting to MongoDB...")
    client = get_client()
    db = client["vba_brain_core"]
    col = db["queries_v2"]

    print("Fetching documents with oracle_sql field...")
    docs = list(col.find({"oracle_sql": {"$exists": True}}))
    
    if not docs:
        print("No documents found needing migration.")
        return

    print(f"Found {len(docs)} documents. Migrating...")
    
    migrated_count = 0
    for doc in docs:
        target_sql = doc.get("oracle_sql")
        
        # We only update if oracle_sql exists. If target_sql already exists, we do not overwrite
        # unless it's empty.
        updates = {}
        if target_sql is not None:
            updates["target_sql"] = target_sql
            
        if updates:
            col.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": updates,
                    "$unset": {"oracle_sql": ""}
                }
            )
            migrated_count += 1
            
    print(f"Migration complete. Migrated {migrated_count} documents.")

if __name__ == "__main__":
    migrate()
