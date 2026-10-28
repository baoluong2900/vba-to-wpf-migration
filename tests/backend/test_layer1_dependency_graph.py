"""reference_map.json → dependency_graph documents (src/backend/workflow/layer1/seed_db.py)."""
from __future__ import annotations

from layer1.seed_db import build_dependency_graph

REFERENCE_MAP = {
    "forms": {
        "F_Login": {
            "forms": ["F_Menu"], "reports": [], "queries": ["Q000_T_LoginUser"],
            "macros": ["A_メニューバーを表示"], "modules": ["Common"], "tables": ["T_ID_Pass"],
        },
        "F_Menu": {"forms": ["F_ProductList"], "reports": ["R_MonthlySales"], "queries": [], "macros": [], "modules": [], "tables": []},
        "F_ProductList": {},
    },
    "reports": {"R_MonthlySales": {"queries": ["Q_Sales"]}},
    "macros": {"A_メニューバーを表示": {"forms": ["F_Menu"]}},
    "modules": {"Common": {"modules": ["Mod_CommonUtils"]}},
    "queries": {"Q000_T_LoginUser": {"tables": ["TBL_Users"]}},
    "tables": {"TBL_Users": {}},
}


def _by_name(docs):
    return {d["name"]: d for d in docs}


def test_fields_layer2_reads():
    login = _by_name(build_dependency_graph(REFERENCE_MAP))["F_Login"]
    assert login["type"] == "form"
    assert login["opens_forms"] == ["F_Menu"]
    assert login["uses_queries"] == ["Q000_T_LoginUser"]
    assert login["calls_modules"] == ["Common"]
    assert login["direct_macros"] == ["A_メニューバーを表示"]
    assert login["uses_tables"] == ["T_ID_Pass"]


def test_opened_by_is_the_reverse_index():
    docs = _by_name(build_dependency_graph(REFERENCE_MAP))
    assert docs["F_Menu"]["opened_by"] == ["A_メニューバーを表示", "F_Login"]
    assert docs["F_ProductList"]["opened_by"] == ["F_Menu"]
    assert docs["R_MonthlySales"]["opened_by"] == ["F_Menu"]
    assert docs["F_Login"]["opened_by"] == []


def test_every_item_category_except_tables_gets_a_document():
    docs = build_dependency_graph(REFERENCE_MAP)
    assert {(d["name"], d["type"]) for d in docs} == {
        ("F_Login", "form"), ("F_Menu", "form"), ("F_ProductList", "form"),
        ("R_MonthlySales", "report"), ("A_メニューバーを表示", "macro"),
        ("Common", "module"), ("Q000_T_LoginUser", "query"),
    }


def test_empty_map():
    assert build_dependency_graph({}) == []
