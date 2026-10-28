"""Layer 1 query → queries_v2 fields (src/backend/workflow/layer3/sql_migration/seed_queries_v2.py)."""
from __future__ import annotations

from layer3.sql_migration.query_utils import build_sql_from_parts
from layer3.sql_migration.seed_queries_v2 import source_fields

UPDATE_DOC = {
    "query_name": "Q_UpdateProductStock",
    "tables": ["TBL_Products"],
    "parameters": [],
    "query": {
        "update": "TBL_Products",
        "set": ["TBL_Products.UnitsInStock = [NewStock]"],
        "where": "(((TBL_Products.ProductID)=[TargetID]))",
    },
}


def test_original_sql_text_wins():
    doc = dict(UPDATE_DOC, sql="PARAMETERS [NewStock] Short;\nUPDATE TBL_Products SET UnitsInStock = [NewStock];")
    fields = source_fields(doc)
    assert fields["sql"] == fields["raw_sql"] == doc["sql"]


def test_update_rebuild_keeps_update_and_set():
    # Older imports have no "sql": the rebuild used to keep only the WHERE clause.
    fields = source_fields(UPDATE_DOC)
    assert fields["sql"] == (
        "UPDATE TBL_Products\n"
        "SET TBL_Products.UnitsInStock = [NewStock]\n"
        "WHERE (((TBL_Products.ProductID)=[TargetID]))"
    )
    assert fields["query_type"] == "update"
    assert fields["target_table"] == "TBL_Products"
    assert fields["tables"] == ["TBL_Products"]
    assert fields["query"] == UPDATE_DOC["query"]


def test_select_fields():
    doc = {"query": {"select": "ID", "from": "TBL_Users", "where": "なし", "group_by": "なし", "order_by": "なし"}}
    fields = source_fields(doc)
    assert fields["sql"] == "SELECT ID\nFROM TBL_Users"
    assert fields["query_type"] == "select"
    assert fields["target_table"] is None


def test_other_statement_shapes():
    assert build_sql_from_parts({"delete": "* FROM T_Log ", "where": "Age > 3"}) == "DELETE * FROM T_Log\nWHERE Age > 3"
    assert build_sql_from_parts({"insert_into": "T", "values": {"A": "1", "B": "[p]"}}) == "INSERT INTO T (A, B)\nVALUES (1, [p])"
    assert build_sql_from_parts(
        {"insert_into": "T", "values": {"A": "S.X"}, "select": "S.X", "from": "S"}
    ) == "INSERT INTO T (A)\nSELECT S.X\nFROM S"
    assert build_sql_from_parts({"unparsed": True, "sql": "TRANSFORM odd"}) == "TRANSFORM odd"
    assert source_fields({"query": {"delete": "* FROM T_Log ", "where": "なし"}})["target_table"] == "T_Log"
    assert source_fields({"query": {"insert_into": "T", "values": {"A": "1"}}})["query_type"] == "insert"
