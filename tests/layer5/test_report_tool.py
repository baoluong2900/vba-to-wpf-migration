"""agents/report/tool_report — colours, RDLC naming/borders, report routing, Avalonia-safe handlers."""
from __future__ import annotations

import re

import pytest

from agents.report import tool_report as tr


@pytest.mark.parametrize("value, expected", [
    (255, "#FF0000"),               # BGR: red
    (16711680, "#0000FF"),          # BGR: blue
    (16777215, "#FFFFFF"),
    ("65280", "#00FF00"),
    (-2147483640, "#000000"),       # 0x80000008 window text
    (-2147483633, "#F0F0F0"),       # 0x8000000F button face
    (-2147483643, "#FFFFFF"),       # 0x80000005 window
    (-2147483630, "#000000"),       # 0x80000012 button text
    (-2147483617, "#A6A6A6"),       # Access default border grey
    (None, "#000000"),
    ("abc", "#000000"),
])
def test_access_color_to_hex(value, expected):
    assert tr.access_color_to_hex(value) == expected


def test_access_color_backstyle_zero_is_transparent():
    assert tr.access_color_to_hex(255, backstyle=0) == "Transparent"
    assert tr.access_color_to_hex(255, backstyle="0") == "Transparent"


def _item(itype, name, top=0, **fmt):
    return {"type": itype, "name": name, "properties": {"format": {"top": top, "left": 0, **fmt}, "data": {}}}


def test_bordered_label_uses_its_own_border_colour():
    rdlc = tr.generate_report_rdlc("R_X", [
        _item("Label", "見出し", top=0, caption="見出し", oldborderstyle=1, bordercolor=255),
        _item("Line", "直線1", top=100, bordercolor=16711680),
    ])
    label = rdlc[rdlc.index("<Textbox"):rdlc.index("</Textbox>")]
    assert "<Color>#FF0000</Color>" in label


def test_rdlc_item_names_are_unique_and_start_with_a_letter():
    rdlc = tr.generate_report_rdlc("R_X", [
        _item("Label", "見出し", top=0, caption="a"),
        _item("Label", "小計", top=100, caption="b"),
        _item("TextBox", "1行目", top=200),
    ])
    names = re.findall(r'<(?:Textbox|Line|Rectangle) Name="([^"]+)"', rdlc)
    assert len(names) == len(set(names)) == 3
    assert all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", n) for n in names)


@pytest.mark.parametrize("doc, name, expected", [
    ({"type": "Reports"}, "アフター請求書_NONOS", True),
    ({"type": "Forms"}, "R_Menu", False),
    ({}, "R005_作業依頼書", True),
])
def test_report_routing_prefers_document_type(doc, name, expected):
    assert tr.is_report_document(name, doc) is expected


def test_pdf_handler_is_avalonia_safe_and_escapes_vba_strings():
    vba = ('MsgBox "出力します"\nFolderName = "C:\\Users\\共有"\n'
           'DoCmd.OutputTo acOutputReport, "R005_作業依頼書", acFormatPDF, '
           'FolderName & "\\" & Format(Now, "yyyymmdd-hhnn") & "_報告書{1}" & ".pdf"')
    code = tr.generate_pdf_click_csharp(vba, "F_X", "PDF出力_Click", "R005WorkRequest", "IXService.F000Async → Data")
    assert "Microsoft.Reporting" not in code and "MessageBox" not in code and "System.Windows" not in code
    assert '"C:\\\\Users\\\\共有"' in code
    assert 'ToString("yyyyMMdd-HHmm")}_報告書{{1}}.pdf"' in code
    assert "TODO(report)" in code and "IXService.F000Async → Data" in code
