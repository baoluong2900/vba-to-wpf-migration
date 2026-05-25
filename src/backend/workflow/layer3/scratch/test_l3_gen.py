import sys
from pathlib import Path

# Add paths to sys.path
L3_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = L3_DIR.parent.parent
sys.path.insert(0, str(L3_DIR))
sys.path.insert(0, str(L3_DIR / "scripts"))
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "workflow"))
sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer2"))

# Force MONGO_DB to vba_brain_core for testing if not set
import os
os.environ.setdefault("MONGO_DB", "vba_brain_core")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/vba_brain_core")

import server

class Req:
    def __init__(self, name, doc_type="screen"):
        self.screenName = name
        self.type = doc_type

def test_generation():
    print("--- Starting BD Generation for F_Login ---")
    req = Req("F_Login", "screen")
    res_bd = server.gen_bd(req)
    print("BD Result:", res_bd)

    print("\n--- Starting DD Generation for F_Login ---")
    res_dd = server.gen_dd(req)
    print("DD Result:", res_dd)

    print("\n--- Starting Zip Generation for F_Login ---")
    res_all = server.gen_all(req)
    print("Zip Result:", res_all)

    # Check output files
    output_base = server.OUTPUT_DIR
    print(f"\nChecking outputs in {output_base}:")
    for p in output_base.glob("**/*.*"):
        print(f" - {p.relative_to(output_base)} (Size: {p.stat().st_size} bytes)")

if __name__ == "__main__":
    test_generation()
