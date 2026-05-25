from pathlib import Path
from typing import Any
from ..core.fill_dd_form_report import get_dd_skeleton as _get_dd_skeleton

def get_dd_skeleton(
    screen_name: str,
    dd_code_json_path: Path,
    bd_final_path: Path,
    template_path: Path,
    output_dir: Path,
    category: str = "report",
) -> dict[str, Any]:
    """Wraps fill_dd_form_report specifically for Reports (report category)."""
    return _get_dd_skeleton(
        screen_name=screen_name,
        dd_code_json_path=dd_code_json_path,
        bd_final_path=bd_final_path,
        template_path=template_path,
        output_dir=output_dir,
        category=category,
    )
