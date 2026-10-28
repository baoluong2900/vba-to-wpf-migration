"""
utils/paths.py — Output-path helpers for Layer 2.

Item names (screen_name) arrive from gRPC/HTTP requests, so every file name built from one goes
through safe_child_path() and can never point outside its output directory.
"""
from __future__ import annotations

from pathlib import Path

LAYER2_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = LAYER2_DIR / "output"
BD_FLOW_DIR = OUTPUT_DIR / "bd_flow"
BD3_LOGIC_DIR = BD_FLOW_DIR / "bd3_bd_logic"

_FORBIDDEN_CHARS = ("/", "\\", "\x00")


def validate_item_name(name: str) -> str:
    """Return *name* if it is usable as a single file-name component, else raise ValueError."""
    if not isinstance(name, str) or not name or name in (".", "..") or any(c in name for c in _FORBIDDEN_CHARS):
        raise ValueError(f"Invalid item name for an output path: {name!r}")
    return name


def safe_child_path(base_dir: str | Path, name: str, suffix: str = ".json", *, prefix: str = "") -> Path:
    """Return base_dir/<prefix><name><suffix>, raising ValueError if it would resolve outside base_dir."""
    validate_item_name(name)
    base = Path(base_dir)
    path = base / f"{prefix}{name}{suffix}"
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError(f"Output path for {name!r} escapes {base}")
    return path


def bd3_result_path(screen_name: str, bd3_dir: str | Path | None = None) -> Path:
    """BD3 logic results, as written by BDService.run_logic_analysis and read by the DD flow."""
    return safe_child_path(bd3_dir or BD3_LOGIC_DIR, screen_name, ".json", prefix="result_")
