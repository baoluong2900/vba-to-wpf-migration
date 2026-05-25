import logging
from typing import Any

logger = logging.getLogger("vba_brain.bd_agent.macro_resolver")

def resolve_macro_module_info(repo: Any, ref_name: str, ref_type: str, mod_id: str, title: str) -> dict | None:
    """
    For macro.XXX  → build synthetic logic_result from macro steps (no LLM).
    For module.XXX → return None here; caller should route code through LLM instead.
    Returns None if not found (will be left as empty in S4).
    """
    try:
        if ref_type == "macro":
            raw = repo.get_bd_code_json_macro(ref_name)
            if not raw:
                return None
            macro_data = raw.get("macro") or raw
            steps = macro_data.get("steps", [])

            # Build human-readable step summary
            step_parts = []
            for s in steps:
                action = s.get("action", "")
                if not action or action == "SetWarnings":
                    continue
                args = s.get("arguments", [])
                macro_name = s.get("macro_name", "")
                if action == "SetValue" and len(args) >= 2:
                    step_parts.append(f"{args[0]}を{args[1]}に設定")
                elif action == "RunMacro" and macro_name:
                    step_parts.append(f"マクロ「{macro_name}」を実行")
                elif action == "OpenForm" and args:
                    step_parts.append(f"フォーム「{args[0]}」を開く")
                elif action == "OpenQuery" and args:
                    step_parts.append(f"クエリ「{args[0]}」を実行")
                elif action == "Close":
                    obj_name = s.get("object_name")
                    if obj_name:
                        step_parts.append(f"画面「{obj_name}」を閉じる")
                    else:
                        step_parts.append("画面を閉じる")
                elif action == "GoToRecord":
                    step_parts.append("レコードを移動する")
                elif args:
                    step_parts.append(f"{action}({', '.join(str(a) for a in args)})")
                else:
                    step_parts.append(action)

            # The user requested not to detail macro steps in event_content and just leave it empty.
            event_content = ""
            return {
                "module_id": mod_id,
                "event_content": event_content,
                "action_type": "SYS",
                "notes": f"参照マクロ: {ref_name}.xlsx",
            }

    except Exception as e:
        logger.warning(f"Could not resolve {ref_type} '{ref_name}': {e}")
    return None
