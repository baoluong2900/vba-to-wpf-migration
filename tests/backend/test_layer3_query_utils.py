"""Layer 3 query helpers (src/backend/workflow/layer3/sql_migration/query_utils.py)."""
from __future__ import annotations

from layer3.sql_migration.query_utils import build_sql_from_parts, extract_bind_variables


def test_japanese_bind_variables():
    sql = """
    SELECT * FROM T
    WHERE field1 = :txt工事名称
      AND field2 = :txt店所コード
      AND field3 = :txtⅡ型
      AND field4 = :ひらがな
    """
    assert extract_bind_variables(sql) == ["txt工事名称", "txt店所コード", "txtⅡ型", "ひらがな"]


def test_postgres_casts_and_time_values_are_not_bind_variables():
    sql = "SELECT a::text, b::date FROM t WHERE c = :id AND d = '12:30' AND e > :since"
    assert extract_bind_variables(sql) == ["id", "since"]


def test_colons_inside_string_literals_are_ignored():
    assert extract_bind_variables("SELECT 'note : x', 'it''s :y' FROM t WHERE k = :key") == ["key"]


def test_duplicates_keep_first_seen_order():
    assert extract_bind_variables("WHERE a = :b OR c = :a OR d = :b") == ["b", "a"]


def test_empty_input():
    assert extract_bind_variables("") == []
    assert extract_bind_variables(None) == []


def test_build_sql_skips_missing_and_none_clauses():
    query = {"select": "ID, Name", "from": "TBL_Users", "where": "なし", "order_by": "Name"}
    assert build_sql_from_parts(query) == "SELECT ID, Name\nFROM TBL_Users\nORDER BY Name"


def test_build_sql_from_nothing():
    assert build_sql_from_parts(None) == ""
    assert build_sql_from_parts({}) == ""
