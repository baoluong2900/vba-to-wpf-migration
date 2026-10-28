"""Layer 4 export entry points (src/backend/workflow/layer4/server.py) with the fillers faked out."""
from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace

import pytest

from layer4 import server


@pytest.fixture()
def layer2_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "L2_OUTPUT_DIR", tmp_path / "layer2")
    monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(server, "_find_in_mongo", lambda coll, name: (None, None))
    return tmp_path / "layer2"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("name", ["../x", "../../etc/passwd", "a/b", "/abs"])
def test_names_that_leave_the_folder_raise(tmp_path, name):
    with pytest.raises(ValueError):
        server._child(tmp_path, f"{name}.xlsx")


def test_download_path_is_confined(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path)
    assert server.download_file("BD", "screen", "F_Login.xlsx").path == str(tmp_path / "BD" / "screen" / "F_Login.xlsx")
    with pytest.raises(ValueError, match="Invalid download path"):
        server.download_file("..", "..", "secret.txt")


def test_missing_layer2_output_is_reported_not_built(layer2_dir):
    res = server.gen_bd(SimpleNamespace(screenName="F_None", type="auto"))
    assert res["success"] is False
    assert "not generated yet" in res["error"]


def test_invalid_layer2_json_is_reported(layer2_dir):
    _write(layer2_dir / "bd_flow" / "bd4_bd_final" / "F_Bad.json", "{not json")
    with pytest.raises(server.Layer2DataError, match="F_Bad.json"):
        server.get_bd_data("F_Bad")


def _fake_filler(calls):
    def fill_excel(template, data, out, **kwargs):
        calls.append((template.name, data.get("screen_id"), kwargs))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"xlsx")
    return types.SimpleNamespace(fill_excel=fill_excel)


@pytest.mark.parametrize(("dd_type", "module", "profile"), [
    ("form", "fill_dd_excel_frm", "form"),
    ("report", "fill_dd_excel_report", "form"),
    ("module", "fill_dd_excel_module", "module_macro"),
    ("macro", "fill_dd_excel_macro", "module_macro"),
])
def test_gen_dd_passes_the_detail_profile(layer2_dir, monkeypatch, dd_type, module, profile):
    calls = []
    monkeypatch.setitem(sys.modules, module, _fake_filler(calls))
    monkeypatch.setattr(server, "_build_docx", lambda *a: "Word generation failed: no python-docx")
    _write(layer2_dir / "dd_flow" / "screen" / "dd4_dd_final" / "X_Item.json", {"type": dd_type, "screen_id": ""})

    res = server.gen_dd(SimpleNamespace(screenName="X_Item", type="auto"))

    assert res["success"] is True
    assert calls == [(calls[0][0], "X_Item", {"mock_change_history": False, "detail_profile": profile})]
    assert "docx_url" not in res["file_info"]
    assert res["docx_error"].startswith("Word generation failed")


def test_docx_url_only_when_the_file_exists(tmp_path):
    xlsx, docx = tmp_path / "A.xlsx", tmp_path / "A.docx"
    xlsx.write_bytes(b"x")
    assert "docx_url" not in server._gen_result("BD", "screen", xlsx, docx, None, 0.0)["file_info"]
    docx.write_bytes(b"d")
    assert server._gen_result("BD", "screen", xlsx, docx, None, 0.0)["file_info"]["docx_url"].endswith("/A.docx")


@pytest.mark.parametrize(("bd_ok", "dd_ok"), [(True, True), (True, False), (False, True), (False, False)])
def test_gen_all_succeeds_only_when_both_do(monkeypatch, bd_ok, dd_ok):
    monkeypatch.setattr(server, "gen_bd", lambda req: {"success": bd_ok})
    monkeypatch.setattr(server, "gen_dd", lambda req: {"success": dd_ok})
    assert server.gen_all(SimpleNamespace(screenName="X", type="auto"))["success"] is (bd_ok and dd_ok)
