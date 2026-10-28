"""Shared naming helpers (core/naming.py) and deterministic SYS bodies (agents/logic/sys_bodies.py)."""
from __future__ import annotations

import pytest

from agents.logic.sys_bodies import sys_body, taskkill_image
from core.naming import cs_identifier, dto_namespace, form_name_error, validate_form_name


@pytest.mark.parametrize("name, expected", [
    ("F_Login", "F_Login"),
    ("AM報告書(施工)_印刷_PDF", "AM報告書_施工_印刷_PDF"),
    ("1st Form", "_1st_Form"),
    ("class", "_class"),
    ("", "Window"),
])
def test_cs_identifier(name, expected):
    assert cs_identifier(name) == expected


def test_dto_namespace_is_a_valid_namespace_for_any_form_name():
    assert dto_namespace("F_Login", "Requests") == "vba_brain.Application.DTOs.Requests.F_Login"
    assert dto_namespace("AM報告書(施工)_印刷_PDF", "Responses") == \
        "vba_brain.Application.DTOs.Responses.AM報告書_施工_印刷_PDF"


@pytest.mark.parametrize("bad", ["", "  ", "../F_Login", "a/b", "a\\b", "x\x00y", "F..Login"])
def test_unsafe_form_names_are_rejected(bad):
    assert form_name_error(bad)
    with pytest.raises(ValueError):
        validate_form_name(bad)


def test_safe_form_names_pass():
    for ok in ("F_Login", "AM依頼_印刷_PDF", "M300_Splash(M)を開く"):
        assert form_name_error(ok) is None and validate_form_name(ok) == ok


def test_taskkill_image_stops_at_the_vba_closing_quote():
    assert taskkill_image('Shell("taskkill /F /IM wmplayer.exe")') == "wmplayer.exe"
    assert taskkill_image('Shell "taskkill /F /IM wmplayer.exe", vbHide') == "wmplayer.exe"
    assert taskkill_image("no image here") == "wmplayer.exe"


def test_quit_body_uses_the_avalonia_desktop_lifetime():
    body = sys_body("F005Async", 'If MsgBox("終了?", vbYesNo) = vbYes Then DoCmd.Quit')
    assert "IClassicDesktopStyleApplicationLifetime desktop" in body and "desktop.Shutdown();" in body
    for wpf in ("MessageBox", "MessageBoxResult", "System.Windows"):
        assert wpf not in body


def test_taskkill_body_is_a_valid_string_literal():
    body = sys_body("F010Async", 'Shell("taskkill /F /IM wmplayer.exe")')
    assert 'Arguments = "/F /IM wmplayer.exe",' in body


def test_function_key_body_uses_avalonia_keys():
    body = sys_body("F002Async", "Private Sub Form_KeyDown(KeyCode As Integer)\nIf KeyCode = vbKeyF11 Then")
    assert "F002Async(global::Avalonia.Input.KeyEventArgs? e = null)" in body
    assert "case global::Avalonia.Input.Key.F11:" in body and "System.Windows" not in body


def test_close_and_fallback_bodies():
    assert "CloseRequested?.Invoke(this, EventArgs.Empty);" in sys_body("F003Async", "DoCmd.Close acForm, Me.Name")
    # "強制終了" (kill a process) must not be read as "終了" (quit the app)
    assert "taskkill.exe" in sys_body("F010Async", "", event_content="メディアプレイヤーを強制終了する")
    assert sys_body("F001Async", "x = 1") is None
