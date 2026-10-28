"""SQL text rules of the shared DD engine (src/backend/workflow/layer4/scripts/dd_common.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer4" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

pytest.importorskip("openpyxl")
import dd_common  # noqa: E402

# What Layer 2 emits for a form query: structured clauses left empty, statement in raw_sql.
LAYER2_QUERY = {
    "query_name": "Q000_T_LoginUser",
    "sql": {"select": "", "from": "", "join": [], "where": [], "group_by": "なし", "order_by": "なし"},
    "raw_sql": "SELECT\nTBL_Users.Username\nFROM\nTBL_Users",
}


@pytest.mark.parametrize("value", [None, "", "  ", "なし", "N/A", "n/a", [], ["なし", ""]])
def test_placeholder_clauses_are_empty(value):
    assert dd_common._sql_clause(value) == ""


def test_placeholders_never_become_blocks():
    sql = {
        "select": "A.ID", "from": "N/A", "join": ["なし"],
        "where": [{"condition": "なし"}, {"condition": "A.ID = @ID", "notes": "key"}],
        "group_by": "なし", "order_by": "",
    }
    assert dd_common._build_sel_sql_section_blocks(sql) == [
        ("SELECT", "A.ID"),
        ("WHERE", "A.ID = @ID  # key"),
    ]


def test_layer2_query_renders_raw_sql():
    assert not dd_common._has_meaningful_sel_sql(LAYER2_QUERY["sql"])
    kind, text = dd_common._sel_sql_source(LAYER2_QUERY)
    assert kind == "raw"
    assert text.startswith("SELECT\nTBL_Users.Username")


def test_raw_sql_wins_when_select_and_from_are_empty():
    q = {"sql": {"select": "", "from": "", "where": [{"condition": "A.ID = 1"}]}, "raw_sql": "SELECT 1"}
    assert dd_common._sel_sql_source(q) == ("raw", "SELECT 1")


def test_structured_sql_wins_when_present():
    q = {"sql": {"select": "A.ID", "from": "T A", "order_by": "なし"}, "raw_sql": "SELECT * FROM T"}
    kind, sql = dd_common._sel_sql_source(q)
    assert kind == "structured"
    assert dd_common.compose_sel_query_sql_text(q) == "SELECT\nA.ID\n\nFROM\nT A"


def test_nothing_to_render():
    assert dd_common._sel_sql_source({"sql": {"group_by": "なし"}, "raw_sql": ""}) == ("none", None)
    assert dd_common.compose_sel_query_sql_text({}) == ""


def test_standardized_join_objects_are_rendered():
    sql = {"join": [{"type": "LEFT JOIN", "table": "T_ROLE R", "on": "R.ID = A.ROLE_ID"}, "なし"]}
    assert dd_common._format_sql_joins(sql) == "LEFT JOIN T_ROLE R ON R.ID = A.ROLE_ID"


def test_compact_query_sheet_names_for_report_templates():
    assert dd_common._resolve_query_sheet_name({}, "R_Sales", kind="sel", fallback_idx=0) == "R_Sales_00SelQuery01"
    assert dd_common._resolve_query_sheet_name(
        {}, "R_Sales", kind="sel", fallback_idx=1, compact=True,
    ) == "R_Sales_SelQuery02"
