import logging
from typing import Any

logger = logging.getLogger("vba_brain.bd_agent.module_resolver")

def find_module_function_code(repo: Any, func_name: str) -> tuple[str, list]:
    """
    Search all VBA modules in MongoDB for a function matching func_name.
    Returns (code, queries_list) or ("", []) if not found.
    ref_name may be "ModuleName" (whole module) or "FunctionName" (specific func).
    """
    try:
        module_names = repo.list_modules()
        for mod_name in module_names:
            raw = repo.get_bd_code_json_module(mod_name)
            if not raw:
                continue
            module_data = raw.get("module") or raw
            funcs = module_data.get("functions", [])
            for fn in funcs:
                handler = fn.get("handler", "")
                # Match exact function name or ModuleName.FunctionName
                if handler == func_name or handler == func_name.split(".")[-1]:
                    code = fn.get("code", "")
                    if code:
                        logger.info(f"Found module function code: {handler} in {mod_name}")
                        return code, []
    except Exception as e:
        logger.warning(f"Error searching module function '{func_name}': {e}")
    return "", []
