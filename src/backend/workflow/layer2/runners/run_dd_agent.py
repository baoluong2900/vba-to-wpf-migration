#!/usr/bin/env python3
"""
run_dd_agent.py — CLI Entrypoint cho DD Agent (được gọi từ Next.js route hoặc CLI)

Nhận payload JSON từ stdin, chạy DDService, in kết quả ra stdout.

Input stdin (JSON):
    {
        "screenName": "C000_MAIN",
        "model": "qwen-max",         # optional
        "force": false               # optional
    }

Output stdout (dòng cuối cùng là JSON):
    { "success": true, "result": "<json_string>", "savedPath": "<path>" }
    hoặc:
    { "error": "<message>" }

Cách gọi:
    echo '<json_payload>' | python -X utf8 run_dd_agent.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# ── Tắt log debug ra stdout ───────────────────────────────────────────────
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.basicConfig(level=logging.ERROR)

# ── Đảm bảo layer2/ và runners/ trong sys.path ────────────────────────────
_RUNNERS_DIR = os.path.dirname(os.path.abspath(__file__))
_LAYER2_DIR = os.path.dirname(_RUNNERS_DIR)
if _LAYER2_DIR not in sys.path:
    sys.path.insert(0, _LAYER2_DIR)
if _RUNNERS_DIR not in sys.path:
    sys.path.insert(0, _RUNNERS_DIR)

# ── Tìm config.json và out_dir ────────────────────────────────────────────
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
    Nếu model được truyền vào khớp với provider trong config.json,
    trả về stage tương ứng. Mặc định 'dev'.
    """
    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        providers = cfg.get("llm_providers", {})
        for pname, pcfg in providers.items():
            if model in pcfg.get("models", []):
                return "pilot" if pname == "beeknoee" else "dev"
    except Exception:
        pass
    return "dev"


def main() -> None:
    # ── Đọc payload từ stdin ────────────────────────────────────────────────
    try:
        raw = sys.stdin.read()
        inp = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    screen_name: str = inp.get("screenName", "")
    model: str       = inp.get("model", "")
    force: bool      = inp.get("force", False)

    if not screen_name:
        print(json.dumps({"error": "Missing screenName"}))
        sys.exit(1)

    # ── Xác định stage từ model được chọn ──────────────────────────────────
    stage = _stage_from_config(model) if model else os.getenv("L2_STAGE", "dev")

    # ── Chạy DDService ──────────────────────────────────────────────────────
    try:
        from agents.dd_agent.dd_service import DDService

        service = DDService()
        result_dict = service.run_full_flow(
            screen_name=screen_name,
            model_id=model or None,
            force=force,
        )

    except Exception as e:
        print(json.dumps({"error": f"DDService failed: {e}"}))
        sys.exit(1)

    # ── Auto push to MongoDB ──
    try:
        import push_to_mongo
        push_to_mongo.push_dd_one(screen_name)
    except Exception as _pe:
        # Don't fail the whole execution if only DB push fails
        pass

    # ── Lưu output file ─────────────────────────────────────────────────────
    import re
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\u0080-\uFFFF]", "", screen_name)
    out_path = OUT_DIR / f"dd_docs_{safe_name}.json"
    result_str = json.dumps(result_dict, ensure_ascii=False, indent=2)
    out_path.write_text(result_str, encoding="utf-8")

    # ── In kết quả ra stdout ─────────────────────────────────────────────────
    print(json.dumps({
        "success": True,
        "result": result_str,
        "savedPath": str(out_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
