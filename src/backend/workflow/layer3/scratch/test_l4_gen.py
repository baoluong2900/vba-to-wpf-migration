import sys
import os
from pathlib import Path

# Add paths to sys.path
L4_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = L4_DIR.parent.parent
sys.path.insert(0, str(L4_DIR))
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "workflow"))
sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer2"))

# Force MONGO_DB to vba_brain_core for testing if not set
os.environ.setdefault("MONGO_DB", "vba_brain_core")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/vba_brain_core")

from sql_migration import router

class ConvertReqObj:
    def __init__(self, name, model="qwen-max"):
        self.name = name
        self.model = model

def test_layer3():
    print("--- Starting Layer 3 Seed ---")
    seed_res = router.seed_queries()
    print("Seed Result:", seed_res)

    print("\n--- Getting Stats ---")
    stats = router.get_stats()
    print("Stats:", stats)

    if stats.get("total", 0) > 0:
        # Get one query name
        queries_res = router.list_queries()
        if queries_res.get("success") and queries_res.get("result"):
            q_name = queries_res["result"][0]["name"]
            print(f"\n--- Testing SQL Translation for query: {q_name} ---")
            
            # Print raw query info
            q_detail = router.get_query(q_name)
            print("Raw SQL:\n", q_detail["result"].get("sql"))
            
            # Convert
            req = ConvertReqObj(q_name, "qwen-max")
            conv_res = router.convert_query(req)
            print("\nConvert Result Success:", conv_res.get("success"))
            if conv_res.get("success"):
                print("Converted Target SQL:\n", conv_res["result"].get("target_sql"))
                print("Bind Variables Extracted:", conv_res["result"].get("bind_variables"))
                print("Notes / Explanation:", conv_res["result"].get("notes"))
            else:
                print("Error:", conv_res.get("error"))

if __name__ == "__main__":
    test_layer3()
