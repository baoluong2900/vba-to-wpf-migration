#!/usr/bin/env python3
"""
run_bd_agent.py — CLI Entrypoint for BD Agent (called from Next.js route)

Receives JSON payload from stdin, runs BDService, and prints the result to stdout.

Input stdin (JSON):
    {
        "screenName": "C000_MAIN",
        "model": "gpt-5.4-mini",     # optional — if provided, overrides stage routing
        "dbData": { ... }             # bd_code_json from MongoDB
    }

Output stdout (the last line is JSON):
    { "success": true, "result": "<json_string>", "savedPath": "<path>" }
    or:
    { "error": "<message>" }

How to call from Next.js:
    echo '<json_payload>' | python -X utf8 run_bd_agent.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# ── Disable debug log to stdout ───────────────────────────────────────────────
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.basicConfig(level=logging.ERROR)

# ── Ensure layer2/ and runners/ are in sys.path ────────────────────────────
_RUNNERS_DIR = os.path.dirname(os.path.abspath(__file__))
_LAYER2_DIR = os.path.dirname(_RUNNERS_DIR)
if _LAYER2_DIR not in sys.path:
    sys.path.insert(0, _LAYER2_DIR)
if _RUNNERS_DIR not in sys.path:
    sys.path.insert(0, _RUNNERS_DIR)

# ── Find config.json and out_dir ────────────────────────────────────────────
def _find_workspace_root() -> Path:
    curr = Path(_LAYER2_DIR)
    for _ in range(5):
        if (curr / "config.json").exists():
            return curr
        curr = curr.parent
    return Path(_LAYER2_DIR).parent.parent.parent.parent  # fallback

WORKSPACE_ROOT = _find_workspace_root()
CONFIG_FILE = WORKSPACE_ROOT / "config.json"
OUT_DIR = WORKSPACE_ROOT / "src" / "backend" / "out"


def _stage_from_config(model: str) -> str:
    """
    If the passed model matches a provider in config.json,
    return the corresponding stage. Default 'dev'.
    """
    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        providers = cfg.get("llm_providers", {})
        for pname, pcfg in providers.items():
            if model in pcfg.get("models", []):
                # megallm / beeknoee → map sang stage dev/pilot
                return "pilot" if pname == "beeknoee" else "dev"
    except Exception:
        pass
    return "dev"


def main() -> None:
    # ── Read payload from stdin ────────────────────────────────────────────────
    try:
        raw = sys.stdin.read()
        inp = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    screen_name: str = inp.get("screenName", "")
    model: str       = inp.get("model", "")
    db_data: dict    = inp.get("dbData", {})

    if not screen_name:
        print(json.dumps({"error": "Missing screenName"}))
        sys.exit(1)

    if not db_data:
        print(json.dumps({"error": "Missing dbData"}))
        sys.exit(1)

    # ── Determine stage from the selected model ──────────────────────────────────
    stage = _stage_from_config(model) if model else os.getenv("L2_STAGE", "dev")

    # ── Determine item_type from dbData structure ──────────────────────────────
    if "form" in db_data:
        item_type = "form"
    elif "report" in db_data:
        item_type = "report"
    elif "module" in db_data:
        item_type = "module"
    else:
        item_type = "form"  # fallback

    # ── Run BDService ──────────────────────────────────────────────────────
    try:
        from agents.bd_agent.bd_service import BDService

        service = BDService(stage=stage)
        bd_docs = service.run(bd_code_json=db_data, item_type=item_type)

    except Exception as e:
        print(json.dumps({"error": f"BDService failed: {e}"}))
        sys.exit(1)

    # ── Save output file ─────────────────────────────────────────────────────
    import re
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\u0080-\uFFFF]", "", screen_name)
    out_path = OUT_DIR / f"bd_docs_{safe_name}.json"
    result_str = json.dumps(bd_docs, ensure_ascii=False, indent=2)
    out_path.write_text(result_str, encoding="utf-8")

    # ── Print result to stdout ─────────────────────────────────────────────────
    print(json.dumps({
        "success": True,
        "result": result_str,
        "savedPath": str(out_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
