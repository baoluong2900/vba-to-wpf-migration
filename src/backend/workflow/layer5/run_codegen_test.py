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
    print("Running Layer 5 Code Gen Orchestrator for F_TestForm...")
    orch = L5Orchestrator()
    res = await orch.run_form("F_TestForm")
    print("\nGeneration finished!")
    print("Status:", res.status)
    print("Files created:", len(res.all_files))
    for f in res.all_files:
        print(f"  - {f.path} (agent={f.agent}, generator={f.generator})")
    if res.error:
        print("Error:", res.error)

if __name__ == "__main__":
    asyncio.run(main())
