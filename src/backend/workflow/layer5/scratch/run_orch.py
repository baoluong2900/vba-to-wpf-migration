import sys
import asyncio
import logging
from pathlib import Path

# Set up logging to show everything clearly
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.orchestrator import L5Orchestrator

async def run():
    orch = L5Orchestrator()
    res = await orch.run_form("F_Login")
    print("\n" + "="*50)
    print(f"Pipeline Result for F_Login:")
    print(f"  Status: {res.status}")
    print(f"  Build Success: {res.build_success}")
    print(f"  Total Files Generated: {len(res.all_files)}")
    print(f"  Generated Files:")
    for f in res.all_files:
        print(f"    - {f.path}")
    if res.error:
        print(f"  Error: {res.error}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run())
