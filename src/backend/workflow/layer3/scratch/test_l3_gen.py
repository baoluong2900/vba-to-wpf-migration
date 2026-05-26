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
    import tempfile
    import shutil
    
    # Create temporary directory for test output files
    temp_dir = Path(tempfile.mkdtemp())
    original_output_dir = server.OUTPUT_DIR
    server.OUTPUT_DIR = temp_dir

    try:
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
        print(f"\nChecking outputs in {temp_dir}:")
        for p in temp_dir.glob("**/*.*"):
            print(f" - {p.relative_to(temp_dir)} (Size: {p.stat().st_size} bytes)")
    finally:
        # Restore output directory configuration
        server.OUTPUT_DIR = original_output_dir
        # Clean up temporary files
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_generation()
