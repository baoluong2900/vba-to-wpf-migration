import logging
from typing import Any

logger = logging.getLogger("vba_brain.bd_agent.macro_resolver")

def resolve_macro_module_info(repo: Any, ref_name: str, ref_type: str, mod_id: str, title: str) -> dict | None:
    """
    For macro.XXX  → build synthetic logic_result for the referenced macro (no LLM).
    For module.XXX → return None here; caller should route code through LLM instead.
    Returns None if not found (will be left as empty in S4).
    """
    try:
        if ref_type == "macro":
            raw = repo.get_bd_code_json_macro(ref_name)
            if not raw:
                return None
            # Macro steps are deliberately not summarised into event_content (left empty).
            return {
                "module_id": mod_id,
                "event_content": "",
                "action_type": "SYS",
                "notes": f"参照マクロ: {ref_name}.xlsx",
            }

    except Exception as e:
        logger.warning(f"Could not resolve {ref_type} '{ref_name}': {e}")
    return None
