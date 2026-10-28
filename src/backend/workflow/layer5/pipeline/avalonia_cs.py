"""
pipeline/avalonia_cs.py — WPF C# → Avalonia C# post-processor.

Single deterministic transform applied to emitted C# (ViewModels, code-behind)
so all Layer 5 generators target the Avalonia project instead of WPF.
"""
from __future__ import annotations

import re

from core.cs_text import find_matching, mask_non_code, split_top_level

# WPF using directive → Avalonia equivalent (applied line-wise).
# NOTE: `System.Windows.Input` is intentionally NOT remapped — ICommand lives there
# (System.ObjectModel, cross-platform) and Avalonia uses it directly. Only the
# Avalonia-specific KeyEventArgs / Key types are rewritten (fully-qualified) below.
_USING_MAP = {
    "using System.Windows.Controls;": "using Avalonia.Controls;",
    "using System.Windows.Threading;": "using Avalonia.Threading;",
    "using System.Windows.Media;":    "using Avalonia.Media;",
    "using System.Windows;":          "using Avalonia.Controls;",
}

_DESKTOP_SHUTDOWN = (
    "(global::Avalonia.Application.Current?.ApplicationLifetime as "
    "global::Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime)?.Shutdown()"
)

_MESSAGEBOX_CALL = re.compile(r"(?:\bSystem\.Windows\.)?\bMessageBox\s*\.\s*Show\s*\(")


def _is_statement_start(masked: str, idx: int) -> bool:
    """True when the expression starting at masked[idx] begins a statement (or a lambda body)."""
    j = idx - 1
    while j >= 0 and masked[j].isspace():
        j -= 1
    if j < 0 or masked[j] in ";{}):":
        return True
    if masked[j] == ">" and j > 0 and masked[j - 1] == "=":
        return True
    word = re.search(r"(\w+)$", masked[: j + 1])
    return bool(word and word.group(1) == "else")


def rewrite_messagebox_statements(code: str) -> str:
    """
    WPF `MessageBox.Show(msg, ...);` used as a whole statement → `System.Diagnostics.Debug.WriteLine(msg);`
    (Avalonia has no MessageBox). Calls whose result is used (`var r = MessageBox.Show(...)`) are
    left alone: changing them to a void call would silently change the program.
    """
    masked = mask_non_code(code)
    out: list[str] = []
    last = 0
    for mt in _MESSAGEBOX_CALL.finditer(masked):
        if mt.start() < last or not _is_statement_start(masked, mt.start()):
            continue
        open_paren = mt.end() - 1
        close_paren = find_matching(code, open_paren, masked)
        if close_paren < 0:
            continue
        k = close_paren + 1
        while k < len(masked) and masked[k].isspace():
            k += 1
        if k >= len(masked) or masked[k] not in ";),":
            continue
        args = split_top_level(code, open_paren + 1, close_paren, masked)
        first = args[0] if args and args[0] else '""'
        out.append(code[last:mt.start()])
        out.append(f"System.Diagnostics.Debug.WriteLine({first})")
        last = close_paren + 1
    out.append(code[last:])
    return "".join(out)


def to_avalonia_cs(code: str) -> str:
    """Convert a WPF C# source string to compile under Avalonia."""
    # 1. Namespace + project-internal usings
    code = code.replace("vba_brain.UI.WPF", "vba_brain.UI.Avalonia")

    # 2. Input types live in Avalonia.Input
    code = code.replace("System.Windows.Input.KeyEventArgs", "global::Avalonia.Input.KeyEventArgs")
    code = re.sub(r"\bSystem\.Windows\.Input\.Key\.", "global::Avalonia.Input.Key.", code)

    # 3. Rewrite WPF framework usings line-wise, de-duplicating collisions
    seen: set[str] = set()
    out_lines: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        mapped = _USING_MAP.get(stripped)
        if mapped is not None:
            if mapped in seen:
                continue  # drop duplicate (e.g. System.Windows + System.Windows.Controls)
            seen.add(mapped)
            out_lines.append(mapped)
        else:
            if stripped.startswith("using ") and stripped in seen:
                continue
            if stripped.startswith("using "):
                seen.add(stripped)
            out_lines.append(line)
    code = "\n".join(out_lines)

    # 4. RoutedEventArgs is in Avalonia.Interactivity — ensure import when used
    if "RoutedEventArgs" in code and "using Avalonia.Interactivity;" not in code:
        code = re.sub(r"(namespace\b)", "using Avalonia.Interactivity;\n\n\\1", code, count=1)

    # 5. WPF MessageBox.Show(msg, ...) statements → Debug.WriteLine(msg)
    code = rewrite_messagebox_statements(code)

    # 6. WPF Application.Current.Shutdown() → the Avalonia desktop lifetime
    code = re.sub(
        r"(?:\bSystem\.Windows\.)?\bApplication\.Current\.Shutdown\(\s*\)",
        lambda _m: _DESKTOP_SHUTDOWN,
        code,
    )

    # 7. WPF ContentRendered/Preview* key events → Avalonia equivalents
    return (
        code.replace("ContentRendered", "Loaded")
        .replace("PreviewKeyDown", "KeyDown")
        .replace("PreviewKeyUp", "KeyUp")
    )
