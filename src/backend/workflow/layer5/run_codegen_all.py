"""
run_codegen_all.py — Run the Layer 5 pipeline (repo → service → UI → logic → build) for forms.

Usage:
    python run_codegen_all.py                       # the default form set
    python run_codegen_all.py --form F_TestForm     # one form (repeat --form for several)

Exit code 1 when any form does not finish with status "success".
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add paths to sys.path
LAYER5_DIR = Path(__file__).resolve().parent
BACKEND_DIR = LAYER5_DIR.parent.parent
sys.path.insert(0, str(LAYER5_DIR))
sys.path.insert(0, str(BACKEND_DIR))
sys.path.append(str(BACKEND_DIR / "workflow" / "layer2"))

# Force MONGO_DB to vba_brain_core
os.environ.setdefault("MONGO_DB", "vba_brain_core")

from core.naming import form_name_error  # noqa: E402
from pipeline.orchestrator import L5Orchestrator  # noqa: E402

DEFAULT_FORMS = ["F_Login", "F_Menu", "F_ProductDetail", "F_ProductList", "F_TestForm"]


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Layer 5 code-gen pipeline")
    parser.add_argument("--form", action="append", dest="forms", metavar="NAME",
                        help="Form to generate (repeatable). Default: " + ", ".join(DEFAULT_FORMS))
    args = parser.parse_args(argv)
    forms = args.forms or DEFAULT_FORMS
    for name in forms:
        error = form_name_error(name)
        if error:
            parser.error(error)

    print(f"Running Layer 5 Code Gen Orchestrator for: {forms}")
    orch = L5Orchestrator()
    failures = 0

    for idx, f in enumerate(forms, 1):
        print("\n==================================================")
        print(f"[Form {idx}/{len(forms)}] Running pipeline for {f}...")
        print("==================================================")
        try:
            res = await orch.run_form(f)
            print(f"[{f}] Finished status: {res.status}")
            print(f"[{f}] Files created: {len(res.all_files)}")
            for file_obj in res.all_files:
                print(f"  - {file_obj.path} (agent={file_obj.agent}, generator={file_obj.generator})")
            if res.error:
                print(f"[{f}] Error: {res.error}")
            failures += res.status != "success"
        except Exception as e:
            print(f"[{f}] Pipeline crashed: {e}")
            failures += 1

    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
