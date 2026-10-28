"""Cell helpers of the Layer 4 Excel fillers (src/backend/workflow/layer4/scripts/fill_bd_excel.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer4" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

openpyxl = pytest.importorskip("openpyxl")
import fill_bd_excel as fb  # noqa: E402


def test_access_expressions_stay_text_without_an_apostrophe():
    ws = openpyxl.Workbook().active
    fb.put(ws, "A1", "=DLookUp(\"x\",\"T\")")
    cell = ws["A1"]
    assert cell.value == "=DLookUp(\"x\",\"T\")"
    assert cell.data_type == "s"
    assert cell.quotePrefix is True


def test_put_writes_the_top_left_cell_of_a_merge():
    ws = openpyxl.Workbook().active
    ws.merge_cells("C2:E2")
    fb.put(ws, "E2", "value")
    assert ws["C2"].value == "value"


def test_label_lookup_is_japanese_first_then_english():
    ws = openpyxl.Workbook().active
    ws["A40"] = "Event ID"
    assert fb.find_row_by_cell_text(ws, "A", "イベントID") == 40
    ws["A60"] = "イベントID"
    assert fb.find_row_by_cell_text(ws, "A", "イベントID") == 60
    assert fb.find_row_by_cell_contains(ws, "A", "") is None


def test_lookups_do_not_create_cells():
    ws = openpyxl.Workbook().active
    ws["A1"] = "x"
    fb.find_row_by_cell_text(ws, "B", "missing", row_end=300)
    assert ws.max_row == 1


def test_missing_change_history_labels_are_restored():
    ws = openpyxl.Workbook().active
    for rng in ("A1:AM1", "A2:B2", "C2:E2", "F2:Q2", "R2:AC2", "AD2:AH2", "AI2:AM2"):
        ws.merge_cells(rng)
    ws["A2"], ws["F2"], ws["R2"] = "改訂", "更新内容", "更新理由/案件番号"
    fb.ensure_change_history_labels(ws)
    assert [ws[c].value for c in ("A1", "C2", "AD2", "AI2")] == ["変更履歴", "更新日", "更新者", "承認者"]
    assert ws["F2"].value == "更新内容"


def test_event_sheet_header_values_go_below_the_labels():
    ws = openpyxl.Workbook().active
    labels = {"G2": "システム名", "N2": "サブシステム名", "AJ2": "作成者", "AN2": "作成日"}
    for coord, text in labels.items():
        ws[coord] = text
    fb.fill_common_header_event(ws, {
        "system_name": "SYS", "author": "Alice", "created_date": "2026-01-01", "subsystem_name": "SUB",
    })
    assert {c: ws[c].value for c in labels} == labels
    assert [ws[c].value for c in ("G3", "N3", "AJ3", "AN3")] == ["SYS", "SUB", "Alice", "2026-01-01"]


@pytest.mark.parametrize(("src", "label"), [
    ({"query_name": "Q_A", "query_display": "F000_SelQuery01"}, "F000_SelQuery01"),
    ({"query_name": "TBL_Products"}, "TBL_Products"),
    ("Q_Raw", "Q_Raw"),
])
def test_record_source_label(src, label):
    assert fb.record_source_label(src) == label
