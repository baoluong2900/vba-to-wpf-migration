
import sys
import os
from pathlib import Path

# Add the backend and layer2 directory to sys.path dynamically
backend_path = Path(__file__).resolve().parent.parent.parent.parent
layer2_path = backend_path / "workflow" / "layer2"
sys.path.append(str(backend_path))
sys.path.append(str(layer2_path))

try:
    from db.mongo_client import get_client
    db = get_client()["vba_brain_core"]
    
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    query_name = "C000_MAINⅡ_未入金_改"
    
    print(f"--- Checking query: {query_name} ---")
    
    v1 = db["queries"].find_one({"$or": [{"name": query_name}, {"query_name": query_name}]})
    if v1:
        print("\n[V1 - queries]")
        print(f"Name: {v1.get('name') or v1.get('query_name')}")
        params = v1.get('parameters', {})
        print(f"Parameters ({len(params)}):")
        for k, v in params.items():
            print(f"  - {k}: {v}")
    else:
        print("\n[V1 - queries] Not found")
        
    v2 = db["queries_v2"].find_one({"name": query_name})
    if v2:
        print("\n[V2 - queries_v2]")
        print(f"Name: {v2.get('name')}")
        params = v2.get('parameters', {})
        print(f"Parameters ({len(params)}):")
        for k, v in params.items():
            print(f"  - {k}: {v}")
        
        print("\n[V2 - Oracle SQL]")
        print(v2.get("raw_sql", ""))
    else:
        print("\n[V2 - queries_v2] Not found")

except Exception as e:
    print(f"Error: {e}")
