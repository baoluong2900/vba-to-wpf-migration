import asyncio
import sys
import os
from pathlib import Path

# Add paths to sys.path
LAYER5_DIR = Path(__file__).resolve().parent
BACKEND_DIR = LAYER5_DIR.parent.parent
sys.path.insert(0, str(LAYER5_DIR))
sys.path.insert(0, str(BACKEND_DIR))
sys.path.append(str(BACKEND_DIR / "workflow" / "layer2"))

# Force MONGO_DB to vba_brain_core
os.environ.setdefault("MONGO_DB", "vba_brain_core")

from pipeline.orchestrator import L5Orchestrator

async def main():
    forms = ["F_Login", "F_Menu", "F_ProductDetail", "F_ProductList", "F_TestForm"]
    print(f"Running Layer 5 Code Gen Orchestrator for all forms: {forms}")
    orch = L5Orchestrator()
    
    for idx, f in enumerate(forms, 1):
        print(f"\n==================================================")
        print(f"[Form {idx}/{len(forms)}] Running pipeline for {f}...")
        print(f"==================================================")
        try:
            res = await orch.run_form(f)
            print(f"[{f}] Finished status: {res.status}")
            print(f"[{f}] Files created: {len(res.all_files)}")
            for file_obj in res.all_files:
                print(f"  - {file_obj.path} (agent={file_obj.agent}, generator={file_obj.generator})")
            if res.error:
                print(f"[{f}] Error: {res.error}")
        except Exception as e:
            print(f"[{f}] Pipeline crashed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
