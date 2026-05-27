"""Layer4 CLI output filename prefixes for DD and BD Excel scripts.

Reads ``layer4_output.env`` next to this file. If missing, falls back to legacy
``dd_output.env`` so older checkouts keep working.

Priority (highest first):
    1) Real OS environment variables (e.g. set in shell / CI).
    2) Key/value pairs in the env file (``setdefault``).
    3) Built-in default string in this module per key.
"""

from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_LAYER4_OUTPUT_ENV = _HERE / "layer4_output.env"
_LEGACY_OUTPUT_ENV = _HERE / "dd_output.env"

_DEFAULT_DD_OUTPUT_FILENAME_PREFIX = "APP 114_プログラム・モジュール仕様書_"
_DEFAULT_BD_SCREEN_OUTPUT_FILENAME_PREFIX = "APP 148-03_画面仕様書_"
_DEFAULT_BD_REPORT_OUTPUT_FILENAME_PREFIX = "APP 148-06_帳票仕様書_"


def _prefix_from_env(env_key: str, fallback: str) -> str:
    v = os.environ.get(env_key, fallback)
    return str(v).strip() or fallback


def _strip_env_value(raw: str) -> str:
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def _output_env_paths() -> list[Path]:
    paths: list[Path] = []
    if _LAYER4_OUTPUT_ENV.is_file():
        paths.append(_LAYER4_OUTPUT_ENV)
    elif _LEGACY_OUTPUT_ENV.is_file():
        paths.append(_LEGACY_OUTPUT_ENV)
    return paths


def _load_output_env_files() -> None:
    for path in _output_env_paths():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if not key:
                continue
            os.environ.setdefault(key, _strip_env_value(val))


_load_output_env_files()


def get_dd_output_filename_prefix() -> str:
    """Prefix for default DD output ``*.xlsx`` batch names."""
    return _prefix_from_env("DD_OUTPUT_FILENAME_PREFIX", _DEFAULT_DD_OUTPUT_FILENAME_PREFIX)


def get_bd_screen_output_filename_prefix() -> str:
    """Prefix for default BD screen (画面仕様書) batch ``*.xlsx`` names."""
    return _prefix_from_env(
        "BD_SCREEN_OUTPUT_FILENAME_PREFIX",
        _DEFAULT_BD_SCREEN_OUTPUT_FILENAME_PREFIX,
    )


def get_bd_report_output_filename_prefix() -> str:
    """Prefix for default BD report (帳票仕様書) batch ``*.xlsx`` names."""
    return _prefix_from_env(
        "BD_REPORT_OUTPUT_FILENAME_PREFIX",
        _DEFAULT_BD_REPORT_OUTPUT_FILENAME_PREFIX,
    )
