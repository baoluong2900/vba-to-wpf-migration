"""BD2 mapping helpers (layer2/agents/bd_agent/core): field resolution, naming, required flags, report detection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAYER2 = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer2"
if str(LAYER2) not in sys.path:
    sys.path.insert(0, str(LAYER2))

import pytest

from agents.bd_agent.core import core as bd_core
from agents.bd_agent.core import utils as bd_utils
from utils.vba_utils import is_required_flag


@pytest.fixture()
def no_name_maps(monkeypatch):
    monkeypatch.setattr(bd_utils, "_name_maps", lambda: ({}, {}))


@pytest.mark.parametrize("value", ["True", "true", " TRUE ", "-1", "1", "Y", "yes", "on", "required", True, -1])
def test_required_flag_affirmative(value):
    assert is_required_flag(value)


@pytest.mark.parametrize("value", ["False", "false", "", "0", "N", "no", None, False, 0])
def test_required_flag_negative(value):
    assert not is_required_flag(value)


@pytest.mark.parametrize("control_source", [
    '=Format(Date(),"yyyy.mm.dd")',
    "=[cboX].[Column](1)",
    "T_Users.UserName",
    "=Date()",
])
def test_resolve_source_without_query_meta_does_not_crash(control_source):
    tbl, fld, _ = bd_utils.resolve_source_table_field(control_source, "", None, {})
    assert isinstance(tbl, str) and isinstance(fld, str)


def test_resolve_dotted_reference_without_query_meta():
    assert bd_utils.resolve_source_table_field("T_Users.UserName", "", None, {}) == ("T_Users", "UserName", "")


def test_field_references_skip_string_literals():
    refs = bd_utils.extract_field_references('Format([OrderDate],"yyyy.mm.dd") & T_Orders.Total')
    assert "[OrderDate]" in refs
    assert "T_Orders.Total" in refs
    assert not any("yyyy" in r for r in refs)


@pytest.mark.parametrize("name, ctype, caption, expected", [
    ("cboSupplier", "ComboBox", "仕入先", ("cboSupplier", "仕入先")),
    ("btnSave", "CommandButton", "保存", ("btnSave", "保存")),
    ("optStatus", "OptionGroup", "", ("optStatus", "optStatus")),
    ("txtName", "TextBox", "", ("txtName", "txtName")),
    ("Supplier", "ComboBox", "", ("cmbSupplier", "Supplier")),
    ("Status", "OptionButton", "", ("optStatus", "Status")),
    ("subtotal", "TextBox", "", ("txtsubtotal", "subtotal")),
])
def test_resolve_names_keeps_prefixed_names_and_uses_captions(no_name_maps, name, ctype, caption, expected):
    assert bd_utils.resolve_names(name, ctype, caption) == expected


def test_resolve_names_never_emits_todo_logical_names(no_name_maps):
    physical, logical = bd_utils.resolve_names("lblTitle", "Label")
    assert not logical.startswith("TODO_")


def _sample() -> dict:
    return json.loads((LAYER2 / "schema" / "template" / "bd_form.json").read_text(encoding="utf-8"))


def test_report_payload_takes_the_report_branch(no_name_maps):
    report_payload = {
        "request_type": "report_analysis",
        "report": {
            "name": "R_MonthlySales",
            "type": "report",
            "properties": {"event": {"onopen": "Report_Open"}},
            "controls": [
                {"type": "section", "name": "Detail"},
                {"type": "TextBox", "name": "txtTotal", "nodekey": "section",
                 "properties": {"data": {"controlsource": "Total"}}},
            ],
        },
    }
    out = bd_core.generate_bd(report_payload, _sample())
    assert out["screen_id"] == "R_MonthlySales"
    assert "sheet_3_screen_edit" not in out and "sheet_4_table_update" not in out
    assert out["sheet_2_layout"]["events"][0]["notes"] == "Report_Open"
    spec = out["sheet_5_file_spec"]
    assert isinstance(spec, list) and spec[0]["header"]["file_type"] == "レポート"
    assert [i["output_field_name"] for i in spec[0]["items"]] == ["Detail", "txtTotal"]


def test_form_payload_keeps_the_form_branch(no_name_maps):
    form_payload = {"request_type": "form_analysis", "form": {"name": "F_Login", "type": "Forms", "controls": []}}
    out = bd_core.generate_bd(form_payload, _sample())
    assert out["screen_id"] == "F_Login"
    assert "sheet_3_screen_edit" in out
