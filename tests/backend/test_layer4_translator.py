"""Layer 4 JP→EN translation (src/backend/workflow/layer4/scripts/excel_translator.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer4" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

openpyxl = pytest.importorskip("openpyxl")
import excel_translator as tr  # noqa: E402

from common import config  # noqa: E402


@pytest.fixture()
def english(monkeypatch):
    monkeypatch.setattr(config, "TARGET_LANGUAGE", "en")


def test_translate_text_prefers_the_longest_key():
    assert tr.translate_text("＜レコードソース＞") == "Record Source"
    assert tr.translate_text("イベントID") == "Event ID"


@pytest.mark.parametrize(("jp", "en"), [
    ("変更履歴", "Change History"),
    ("画面仕様書(レイアウト)", "Screen Spec (Layout)"),
    ("画面仕様書（E001）", "Screen Spec（E001）"),
    ("ファイル仕様書（E002）", "File Spec（E002）"),
    ("詳細仕様書_F_Login_01", "Detailed Design Spec_F_Login_01"),
    ("F000_SelQuery01", "F000_SelQuery01"),
])
def test_sheet_titles_translate_and_restore(jp, en):
    assert tr.translate_sheet_title(jp) == en
    wb = openpyxl.Workbook()
    wb.active.title = en
    tr.restore_japanese_sheet_names(wb)
    assert wb.sheetnames == [jp]


def test_sheet_title_keeps_the_json_part_untranslated():
    # "情報" is in the mapping, but it belongs to the item name here.
    assert tr.translate_sheet_title("詳細仕様書_受注情報_01") == "Detailed Design Spec_受注情報_01"


def test_target_language_comes_from_common_config(monkeypatch):
    monkeypatch.setattr(config, "TARGET_LANGUAGE", "ja")
    assert tr.get_target_language() == "ja"
    assert tr.translate_label("処理") == "処理"
    monkeypatch.setattr(config, "TARGET_LANGUAGE", "en")
    assert tr.translate_label("処理") == "Process"


def _workbook():
    wb = openpyxl.Workbook()
    ov = wb.active
    ov.title = "概要仕様書"
    ov["A1"] = "システム名"
    ov["A2"] = "備考"
    det = wb.create_sheet("詳細仕様書_FD010M_01")
    det["A1"] = "システム名"
    det["E1"] = "=概要仕様書!E1"
    det["H6"] = "処理記述"
    return wb


def test_only_template_labels_are_translated(english):
    wb = _workbook()
    labels = tr.snapshot_template_labels(wb)
    ov = wb["概要仕様書"]
    ov["A2"] = "受注情報を更新する"   # JSON value written over a template label
    ov["B5"] = "初期処理"            # JSON value in a fresh cell
    clone = wb.copy_worksheet(wb["詳細仕様書_FD010M_01"])
    clone.title = "Detailed Spec_F000"
    clone["H7"] = "1. 初期処理"

    tr.translate_workbook(wb, labels)

    ov, clone = wb["Overview Spec"], wb["Detailed Spec_F000"]
    assert ov["A1"].value == "System Name"
    assert ov["A2"].value == "受注情報を更新する"
    assert ov["B5"].value == "初期処理"
    assert clone["A1"].value == "System Name"       # label of a sheet cloned after the snapshot
    assert clone["H6"].value == "Process Description"
    assert clone["H7"].value == "1. 初期処理"


def test_formulas_follow_renamed_sheets(english):
    wb = _workbook()
    labels = tr.snapshot_template_labels(wb)
    tr.translate_workbook(wb, labels)
    det = wb["Detailed Design Spec_FD010M_01"]
    assert det["E1"].value == "='Overview Spec'!E1"
    assert det["E1"].data_type == "f"


def test_nothing_changes_for_a_japanese_target(monkeypatch):
    monkeypatch.setattr(config, "TARGET_LANGUAGE", "ja")
    wb = _workbook()
    tr.translate_workbook(wb, tr.snapshot_template_labels(wb))
    assert wb.sheetnames == ["概要仕様書", "詳細仕様書_FD010M_01"]
    assert wb["概要仕様書"]["A1"].value == "システム名"


def test_restore_retargets_formulas():
    wb = openpyxl.Workbook()
    wb.active.title = "Screen Spec (Layout)"
    edit = wb.create_sheet("Screen Spec (Edit)")
    edit["G1"] = "='Screen Spec (Layout)'!G1"
    tr.restore_japanese_sheet_names(wb)
    assert wb.sheetnames == ["画面仕様書(レイアウト)", "画面仕様書(画面編集)"]
    assert wb["画面仕様書(画面編集)"]["G1"].value == "='画面仕様書(レイアウト)'!G1"
