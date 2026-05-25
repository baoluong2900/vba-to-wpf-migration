from pathlib import Path
from typing import Any
from ..core.fill_dd_from_bd_json import get_dd_skeleton as _get_dd_skeleton

def get_dd_skeleton(
    screen_name: str,
    dd_code_json_path: Path,
    bd_final_path: Path,
    template_path: Path,
    output_dir: Path,
    category: str = "macro",
) -> dict[str, Any]:
    """Wraps core fill_dd_from_bd_json specifically for Macros."""
    return _get_dd_skeleton(
        screen_name=screen_name,
        dd_code_json_path=dd_code_json_path,
        bd_final_path=bd_final_path,
        template_path=template_path,
        output_dir=output_dir,
        category=category,
    )
