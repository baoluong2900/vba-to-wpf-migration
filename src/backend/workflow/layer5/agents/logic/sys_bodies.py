"""
agents/logic/sys_bodies.py — Deterministic Avalonia method bodies for SYS events (no LLM).

Bodies are full `public virtual async Task FxxxAsync(...)` methods; the patcher keeps only the
part inside the braces. Everything here compiles under Avalonia as emitted — no WPF MessageBox,
MessageBoxResult, System.Windows.Application or System.Windows.Input.Key.
"""
from __future__ import annotations

import re

_TASKKILL_IMAGE_RE = re.compile(r"/IM\s+([^\s\"')]+)", re.IGNORECASE)


def _cs_string(text: str) -> str:
    """C# regular string literal body for `text`."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def taskkill_image(vba_code: str, default: str = "wmplayer.exe") -> str:
    """Image name after `/IM` in VBA such as `Shell("taskkill /F /IM wmplayer.exe")`."""
    match = _TASKKILL_IMAGE_RE.search(vba_code or "")
    return match.group(1) if match else default


def quit_body(fxxx_async: str) -> str:
    """DoCmd.Quit → shut the desktop application down."""
    return (
        f"public virtual async System.Threading.Tasks.Task {fxxx_async}()\n"
        "{\n"
        "    // DoCmd.Quit 相当: アプリケーションを終了する（確認が必要な場合は View 側で行う）。\n"
        "    if (global::Avalonia.Application.Current?.ApplicationLifetime\n"
        "        is global::Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop)\n"
        "        desktop.Shutdown();\n"
        "    await System.Threading.Tasks.Task.CompletedTask;\n"
        "}"
    )


def close_body(fxxx_async: str) -> str:
    """DoCmd.Close → ask the View to close (the code-behind subscribes CloseRequested)."""
    return (
        f"public virtual async System.Threading.Tasks.Task {fxxx_async}()\n"
        "{\n"
        "    // DoCmd.Close 相当: View にウィンドウを閉じるよう通知する。\n"
        "    CloseRequested?.Invoke(this, EventArgs.Empty);\n"
        "    await System.Threading.Tasks.Task.CompletedTask;\n"
        "}"
    )


def taskkill_body(fxxx_async: str, image: str) -> str:
    return (
        f"public virtual async System.Threading.Tasks.Task {fxxx_async}()\n"
        "{\n"
        "    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo\n"
        "    {\n"
        '        FileName = "taskkill.exe",\n'
        f'        Arguments = "/F /IM {_cs_string(image)}",\n'
        "        CreateNoWindow = true,\n"
        "        UseShellExecute = false\n"
        "    });\n"
        "    await System.Threading.Tasks.Task.CompletedTask;\n"
        "}"
    )


def function_key_block_body(fxxx_async: str, keys: tuple[str, ...] = ("F11", "F12")) -> str:
    """Form_KeyDown that swallows function keys (VBA: KeyCode = 0 + MsgBox)."""
    cases = "".join(
        f"        case global::Avalonia.Input.Key.{key}:\n"
        "            e.Handled = true;\n"
        f'            System.Diagnostics.Debug.WriteLine("ファンクション【{key}】キーは無効に設定されてます！！");\n'
        "            break;\n"
        for key in keys
    )
    return (
        f"public virtual async System.Threading.Tasks.Task {fxxx_async}(global::Avalonia.Input.KeyEventArgs? e = null)\n"
        "{\n"
        "    if (e == null) { await System.Threading.Tasks.Task.CompletedTask; return; }\n"
        "    switch (e.Key)\n"
        "    {\n"
        f"{cases}"
        "    }\n"
        "    await System.Threading.Tasks.Task.CompletedTask;\n"
        "}"
    )


def open_form_todo_body(fxxx_async: str, logical_name: str = "") -> str:
    comment = f"open {logical_name} form" if logical_name and logical_name != "-" else "open related form"
    return (
        f"public virtual async System.Threading.Tasks.Task {fxxx_async}()\n"
        "{\n"
        f"    // TODO: {comment} — verify View class name before instantiating\n"
        "    await System.Threading.Tasks.Task.CompletedTask;\n"
        "}"
    )


def sys_body(fxxx_async: str, vba_code: str, event_content: str = "", notes: str = "",
             logical_name: str = "") -> str | None:
    """Pick a deterministic body from the VBA code, then from the BD description; None = keep the stub."""
    code = vba_code or ""
    if re.search(r"DoCmd\.Quit|acQuitPrompt|Application\.Quit", code, re.IGNORECASE):
        return quit_body(fxxx_async)
    if re.search(r"taskkill", code, re.IGNORECASE):
        return taskkill_body(fxxx_async, taskkill_image(code))
    if re.search(r"Form_KeyDown|vbKeyF11|vbKeyF12", code, re.IGNORECASE):
        return function_key_block_body(fxxx_async)
    if re.search(r"DoCmd\.Close\b", code, re.IGNORECASE):
        return close_body(fxxx_async)

    # Fallback: BD event description / handler name ("強制終了" before the broader "終了")
    if re.search(r"強制終了|taskkill|wmplayer|Media Player", event_content, re.IGNORECASE):
        return taskkill_body(fxxx_async, "wmplayer.exe")
    if re.search(r"終了|Quit|アプリケーション.*終了", event_content, re.IGNORECASE):
        return quit_body(fxxx_async)
    if re.search(r"DblClick|ondblclick|ダブルクリック", notes + event_content, re.IGNORECASE):
        return open_form_todo_body(fxxx_async, logical_name)
    return None
