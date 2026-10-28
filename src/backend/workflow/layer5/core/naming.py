"""
core/naming.py — C# identifier / namespace helpers and form-name validation shared by Layer 5.

Agent Service declares the per-form DTO namespaces and UI/Logic emit `using` directives for them,
so every agent must derive the namespace segment from the Access form name the same way.
"""
from __future__ import annotations

import re
import unicodedata

_CS_KEYWORDS = frozenset(
    "abstract as base bool break byte case catch char checked class const continue decimal default "
    "delegate do double else enum event explicit extern false finally fixed float for foreach goto if "
    "implicit in int interface internal is lock long namespace new null object operator out override "
    "params private protected public readonly ref return sbyte sealed short sizeof stackalloc static "
    "string struct switch this throw true try typeof uint ulong unchecked unsafe ushort using virtual "
    "void volatile while".split()
)


def cs_identifier(name: str, fallback: str = "Window") -> str:
    """
    Valid C# identifier for any Access name: invalid characters → "_", runs of "_" collapsed,
    leading digit prefixed. Unicode letters are kept (C# accepts them).
        "F_Login" → "F_Login", "AM報告書(施工)_印刷_PDF" → "AM報告書_施工_印刷_PDF"
    """
    if not name:
        return fallback
    chars: list[str] = []
    for i, ch in enumerate(name):
        cat = unicodedata.category(ch)
        is_letter = cat.startswith("L") or cat == "Nl" or ch == "_"
        is_digit = cat == "Nd"
        if i == 0:
            chars.append(ch if is_letter else ("_" + ch if is_digit else "_"))
        else:
            chars.append(ch if (is_letter or is_digit) else "_")
    sanitized = re.sub(r"_+", "_", "".join(chars))
    if len(sanitized) > 1 and sanitized.endswith("_"):
        sanitized = sanitized[:-1]
    if sanitized in _CS_KEYWORDS:
        sanitized = "_" + sanitized
    return sanitized


def dto_namespace(form_name: str, kind: str) -> str:
    """Namespace of a form's service DTOs; kind is "Requests" or "Responses"."""
    return f"vba_brain.Application.DTOs.{kind}.{cs_identifier(form_name, fallback='Form')}"


def form_name_error(name: str | None) -> str | None:
    """Why `name` must not be joined into a filesystem path, or None when it is safe."""
    if not name or not name.strip():
        return "form name is empty"
    if any(ch in name for ch in ("/", "\\", "\x00")) or ".." in name:
        return f"unsafe form name {name!r}: '/', '\\', NUL and '..' are not allowed"
    return None


def validate_form_name(name: str | None) -> str:
    """Return `name` unchanged, or raise ValueError when it is unsafe to use in paths."""
    error = form_name_error(name)
    if error:
        raise ValueError(error)
    return name  # type: ignore[return-value]
