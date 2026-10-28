"""
Layer 1 parsers, end to end, on the fixture export in src/vba/vba_source/.

Each parser runs as its own CLI (the way run_all.py drives them) and writes into a temp dir,
so the fixture folder stays clean.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VBA_SOURCE = REPO / "src" / "vba" / "vba_source"
PARSER_DIR = REPO / "src" / "backend" / "workflow" / "layer1" / "parser"
PARSER_CONFIG = PARSER_DIR.parent / "config" / "parser_config.json"


def run_parser(script: str, *args: str) -> None:
    res = subprocess.run(
        [sys.executable, "-X", "utf8", str(PARSER_DIR / script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    assert res.returncode == 0, f"{script} failed\n--- stdout\n{res.stdout}\n--- stderr\n{res.stderr}"


def load(path: Path) -> dict:
    assert path.is_file(), f"expected output was not produced: {path.name}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_frm_parser(tmp_path):
    run_parser("frm_parser.py", str(VBA_SOURCE / "Forms"), str(tmp_path), "--config", str(PARSER_CONFIG))

    for name in ("F_Login", "F_Menu", "F_ProductDetail", "F_ProductList", "F_TestForm"):
        form = load(tmp_path / f"{name}.json")
        assert {"key", "type", "name", "properties", "items"} <= form.keys()
        assert form["name"] == name

    login = load(tmp_path / "F_Login.json")
    controls = {item["name"]: item["type"] for item in login["items"]}
    assert controls["txtID"] == "TextBox"
    assert controls["txtPass"] == "TextBox"
    assert controls["cmdLogin"] == "CommandButton"
    assert login["functions"], "VBA event procedures should be extracted"
    assert all("handler" in fn for fn in login["functions"])


def test_macro_parser(tmp_path):
    run_parser("macro_parser.py", str(VBA_SOURCE / "Macros"), "--output-dir", str(tmp_path))

    for name in ("M_TestMacro", "M_OpenDashboard"):
        assert {"macro_name", "source_file", "steps", "references"} <= load(tmp_path / f"{name}.json").keys()

    dashboard = load(tmp_path / "M_OpenDashboard.json")
    assert dashboard["steps"]
    assert "F_Menu" in dashboard["references"]["forms"]


def test_modules_parser(tmp_path):
    run_parser("modules_parser.py", str(VBA_SOURCE / "Modules"), str(tmp_path))

    for name in ("Common", "Mod_CommonUtils", "Mod_TestModule"):
        module = load(tmp_path / f"{name}.json")
        assert {"module_name", "constants", "functions", "variables"} <= module.keys()
        assert module["module_name"] == name

    assert load(tmp_path / "Common.json")["functions"]


def test_query_parser(tmp_path):
    run_parser("query_parser.py", str(VBA_SOURCE / "Queries"), "--output-dir", str(tmp_path))

    for name in ("Q000_T_ID_PASS", "Q000_T_LoginUser", "Q_GetActiveProducts", "Q_TestQuery", "Q_UpdateProductStock"):
        query = load(tmp_path / f"{name}.json")
        assert {"query_name", "tables", "query"} <= query.keys()
        assert query["query_name"] == name

    assert load(tmp_path / "Q000_T_LoginUser.json")["tables"] == ["TBL_Users"]


def test_table_parser(tmp_path):
    run_parser("table_parser.py", str(VBA_SOURCE / "Tables" / "AllColumns.csv"), "--output-dir", str(tmp_path))

    users = load(tmp_path / "TBL_Users.json")
    assert users["table_name"] == "TBL_Users"
    assert [(c["logical_name"], c["data_type"]) for c in users["columns"]] == [
        ("ID", "Long"),
        ("Name", "Text"),
        ("Age", "Integer"),
        ("Username", "Text"),
        ("LoginTime", "Date/Time"),
    ]
    # One JSON per distinct TableName in the CSV.
    assert len(list(tmp_path.glob("*.json"))) == 7
