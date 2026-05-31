"""
pipeline/avalonia_cs.py — WPF C# → Avalonia C# post-processor.

Single deterministic transform applied to emitted C# (ViewModels, code-behind)
so all Layer 5 generators target the Avalonia project instead of WPF.
"""
from __future__ import annotations

import re

# WPF using directive → Avalonia equivalent (applied line-wise).
# NOTE: `System.Windows.Input` is intentionally NOT remapped — ICommand lives there
# (System.ObjectModel, cross-platform) and Avalonia uses it directly. Only the
# Avalonia-specific KeyEventArgs is rewritten (fully-qualified) below.
_USING_MAP = {
    "using System.Windows.Controls;": "using Avalonia.Controls;",
    "using System.Windows.Threading;": "using Avalonia.Threading;",
    "using System.Windows.Media;":    "using Avalonia.Media;",
    "using System.Windows;":          "using Avalonia.Controls;",
}


def to_avalonia_cs(code: str) -> str:
    """Convert a WPF C# source string to compile under Avalonia."""
    # 1. Namespace + project-internal usings
    code = code.replace("vba_brain.UI.WPF", "vba_brain.UI.Avalonia")

    # 2. KeyEventArgs lives in Avalonia.Input
    code = code.replace("System.Windows.Input.KeyEventArgs", "global::Avalonia.Input.KeyEventArgs")

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

    # 5. WPF MessageBox.Show(msg, ...) has no Avalonia equivalent → Debug.WriteLine(msg)
    code = re.sub(
        r"(?:System\.Windows\.)?MessageBox\.Show\(\s*([^,;)]+)(?:[^;]*)?\)",
        r"System.Diagnostics.Debug.WriteLine(\1)",
        code,
    )

    # 6. WPF ContentRendered/PreviewKeyDown events → Avalonia equivalents
    code = code.replace("ContentRendered", "Loaded").replace("PreviewKeyDown", "KeyDown")
    return code
