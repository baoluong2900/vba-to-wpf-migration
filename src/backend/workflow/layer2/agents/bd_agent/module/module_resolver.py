import logging
from typing import Any

logger = logging.getLogger("vba_brain.bd_agent.module_resolver")

def find_module_function_code(repo: Any, func_name: str) -> tuple[str, list]:
    """
    Find the VBA code of a module procedure in MongoDB.
    func_name is "ModuleName.FunctionName" (what Layer 1 emits for module.<Module>.<Proc> event
    bindings) or a bare "FunctionName".
    Returns (code, queries_list) or ("", []) if not found.
    """
    module_name, _, proc_name = func_name.rpartition(".")
    try:
        if not module_name:
            module_name = repo.find_module_name_for_procedure(proc_name)
        if not module_name:
            return "", []
        raw = repo.get_bd_code_json_module(module_name)
        if not raw:
            return "", []
        module_data = raw.get("module") or raw
        # get_bd_code_json_module stores the procedures under "procedures"
        funcs = module_data.get("procedures") or module_data.get("functions") or []
        for fn in funcs:
            handler = fn.get("handler") or fn.get("name") or ""
            if handler == proc_name:
                code = fn.get("code") or ""
                if code:
                    logger.info(f"Found module function code: {handler} in {module_name}")
                    return code, []
    except Exception as e:
        logger.warning(f"Error searching module function '{func_name}': {e}")
    return "", []
