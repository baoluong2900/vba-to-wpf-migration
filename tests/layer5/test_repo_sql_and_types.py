"""agents/repo/tool_repo — SQL building, dependency graph, name lookups, type map and generation."""
from __future__ import annotations

import json

import pytest

from agents.repo import tool_repo as tr


# ── AS-split ──────────────────────────────────────────────────────────────────
def test_insert_target_columns_keep_names_containing_as():
    sql = tr.build_sql({
        "target_table": '"T_ID_Pass"', "select": "src.ID, src.Pass", "from": "src",
        "set_columns": [{"column": "Pass"}, {"column": "LAST_NAME"}, {"column": "x AS 担当者"}, {"column": "y as Kind"}],
    })
    assert '"Pass"' in sql and '"LAST_NAME"' in sql and '"担当者"' in sql and '"Kind"' in sql
    assert '"s"' not in sql and '"T_NAME"' not in sql


def test_update_set_columns_keep_names_containing_as():
    sql = tr.build_sql({
        "target_table": '"T_ID_Pass"',
        "set_columns": [{"column": "PASSWORD", "source_field_or_fixed_value": ":newPass"},
                        {"column": "CLASS_CD AS 区分", "source_field_or_fixed_value": "1"}],
        "where": [{"condition": "ID = :id"}],
    })
    assert "PASSWORD = :newPass" in sql and "CLASS_CD = 1" in sql
    assert "WHERE ID = :id" in sql


# ── Dependency graph ──────────────────────────────────────────────────────────
def test_table_as_query_does_not_reference_itself():
    queries = [tr.normalize_query({"query_name": "T023_地区CD設定", "sql": {"select": "*", "from": "T023_地区CD設定"}})]
    table_queries, _, deps_map = tr.build_dependency_graph(queries)
    assert deps_map == {"T023_地区CD設定": []}
    assert list(table_queries) == ["T023_地区CD設定"]


def test_recursive_deps_cut_cycles():
    deps = {"A": ["B"], "B": ["C", "A"], "C": []}
    assert tr.get_recursive_deps("A", deps) == ["C", "B"]


# ── Lookups: exact / NFKC only ────────────────────────────────────────────────
@pytest.fixture
def config():
    return {"table_name": {"TBLビルＡＭ報告": "BuildingAMReport", "TBLビルＡＭ報告処置": "BuildingAMReportAction",
                           "T011_期": "T011Period"},
            "field_name": {}, "parameter_name": {}, "function_name": {}, "cte_name": {}}


def test_find_table_key_has_no_substring_fallback(config):
    assert tr.find_table_key("TBLビルＡＭ報告", config) == "BuildingAMReport"
    assert tr.find_table_key("TBLビルAM報告", config) == "BuildingAMReport"     # half-width AM (NFKC)
    assert tr.find_table_key("TBLビルＡＭ報告写真", config) == "TBLビルＡＭ報告写真"
    assert tr.find_table_key("T011", config) == "T011"


def test_lookup_schema_has_no_substring_fallback():
    schemas = {"T_Customer": {"fields": [1]}, "Ｔ_Order": {"fields": [2]}}
    assert tr.lookup_schema(schemas, "T_Customer") == {"fields": [1]}
    assert tr.lookup_schema(schemas, "T_Order") == {"fields": [2]}
    assert tr.lookup_schema(schemas, "T_CustomerDetail") is None


def test_colliding_class_names_get_suffix_and_are_remembered(config):
    used: set = set()
    assert tr.class_base_name("T_顧客", config, used) == "T顧客"
    assert tr.class_base_name("T顧客", config, used) == "T顧客2"
    assert config["table_name"]["T顧客"] == "T顧客2"


# ── Type map ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("db_type, cs_type", [
    ("Long", "int"), ("Long Integer", "int"), ("AutoNumber", "int"), ("Integer", "int"),
    ("Currency", "decimal"), ("Yes/No", "bool"), ("Boolean", "bool"), ("Single", "float"),
    ("Double", "double"), ("Byte", "byte"), ("Memo", "string"), ("Text", "string"),
    ("Text(50)", "string"), ("Short Text", "string"), ("Long Text", "string"), ("Date/Time", "DateTime?"),
    ("INT8", "long"), ("BIGINT", "long"), ("INTEGER", "int"), ("INTERVAL", "TimeSpan?"), ("TIME", "TimeSpan?"),
    ("TIMESTAMPTZ", "DateTime?"), ("timestamp without time zone", "DateTime?"), ("NUMERIC(19,4)", "decimal"),
    ("character varying", "string"), ("uuid", "Guid"), ("bytea", "byte[]"), ("whatever", "object"),
])
def test_sql_to_cs_type(db_type, cs_type):
    assert tr.sql_to_cs_type(db_type) == cs_type


@pytest.mark.parametrize("param_type, cs_type", [
    ("Long", "int"), ("Currency", "decimal"), ("Yes/No", "bool"), ("Date/Time", "DateTime?"),
    ("Date", "DateTime?"), ("String", "string"), ("Text Box", "string"), ("Combo Box", "string"), ("", "string"),
])
def test_vba_to_cs_type(param_type, cs_type):
    assert tr.vba_to_cs_type(param_type) == cs_type


@pytest.mark.parametrize("value, expected", [
    ("True", True), (True, True), ("yes", True), ("y", True), (-1, True), ("-1", True),
    ("False", False), ("n", False), (0, False), (None, False), ("", False),
])
def test_is_required(value, expected):
    assert tr.is_required(value) is expected


# ── SELECT aliasing (Dapper maps by name) and password exclusion ──────────────
def test_select_items_are_aliased_to_properties_and_passwords_dropped():
    sql = tr.build_sql({"select": "T.製品名, T.Pass, T.単価 AS 価格", "from": "T"},
                       alias_map={"製品名": "ProductName", "価格": "Price"})
    assert 'T.製品名 AS "ProductName"' in sql
    assert 'T.単価 AS "Price"' in sql
    assert "Pass" not in sql


def test_star_is_expanded_for_a_single_table():
    sql = tr.build_sql({"select": "*", "from": '"T_ID_Pass"'}, alias_map={},
                       expand_fields=[("ユーザーID", "UserId"), ("管理者フラグ", "AdminFlag")])
    assert '"ユーザーID" AS "UserId"' in sql and '"管理者フラグ" AS "AdminFlag"' in sql
    assert "*" not in sql


def test_rewrite_select_sql_keeps_the_rest_of_the_statement():
    sql = tr.rewrite_select_sql("SELECT DISTINCT a.ID, a.Pass, Count(*) AS 件数 FROM a WHERE a.ID = :id",
                                {"ID": "Id", "件数": "Count"})
    assert sql.startswith("SELECT DISTINCT")
    assert 'a.ID AS "Id"' in sql and 'Count(*) AS "Count"' in sql and "Pass" not in sql
    assert sql.rstrip().endswith("FROM a WHERE a.ID = :id")
    assert tr.rewrite_select_sql("SELECT Pass FROM T", {}) is None


def test_bind_variables_skip_casts_and_literals():
    sql = "SELECT a::text, '12:30' FROM t WHERE c = :txt連番 AND d = @id AND e = ':no'"
    assert tr.bind_variables(sql) == ["txt連番", "id"]


# ── DD shape normalisation ────────────────────────────────────────────────────
def test_normalize_query_accepts_both_layer2_shapes():
    q = tr.normalize_query({
        "query_name": None, "name": "Q1", "parameters": [{"name": "txtID"}, {"name": "txtPass"}],
        "sql": {"select": None, "from": None, "where": "ID = :txtID", "update_table": "T_ID_Pass",
                "set_columns": [{"column": "Pass", "value_expression": ":txtPass"}]},
        "raw_sql": None,
    })
    assert q["query_name"] == "Q1" and q["parameters"] == "txtID, txtPass"
    assert q["sql"]["from"] == "" and q["sql"]["target_table"] == "T_ID_Pass"
    assert q["sql"]["where"] == [{"condition": "ID = :txtID"}]
    assert q["sql"]["set_columns"][0]["source_field_or_fixed_value"] == ":txtPass"
    assert q["raw_sql"] == ""


# ── Generation ────────────────────────────────────────────────────────────────
def _generate(queries, schema=None, config=None, table_name=None):
    config = config if config is not None else {"table_name": {}, "field_name": {}, "parameter_name": {},
                                                "function_name": {}, "cte_name": {}}
    qs = [tr.normalize_query(q) for q in queries]
    table_queries, query_map, deps_map = tr.build_dependency_graph(qs, config)
    table = table_name or next(iter(table_queries))
    files = tr.generate_files_for_table(table, table_queries[table], schema, query_map, deps_map, [], config, {})
    # SQL sits in C# verbatim strings (@"…") where '"' is doubled; compare against the plain SQL text
    by_suffix = {f["path"].rsplit("/", 1)[-1]: f["content"].replace('""', '"') for f in files}
    repo_json = json.loads(next(f["content"] for f in files if f["path"].endswith(".json")))
    return by_suffix, repo_json


def test_raw_sql_is_used_when_the_sql_block_is_empty():
    files, repo_json = _generate([{
        "query_name": "Q000_T_LoginUser", "sheet_name_pattern": "F000_SelQuery01",
        "sql": {"select": "", "from": ""},
        "raw_sql": "SELECT\nTBL_Users.Username\n, TBL_Users.LoginTime\nFROM\nTBL_Users",
    }])
    repo = files["Q000TLoginUserRepository.cs"]
    assert "NotImplementedException" not in repo and "Enumerable.Empty" not in repo
    assert 'TBL_Users.Username AS "TODO_Username"' in repo
    assert repo_json["function"][0]["implemented"] is True


def test_query_without_sql_throws_and_is_flagged():
    files, repo_json = _generate([{"query_name": "Q_Empty", "sheet_name_pattern": "F001_SelQuery01",
                                   "columns": [{"column_name": "A"}, {"column_name": "B"}]}])
    assert "throw new NotImplementedException(" in files["QEmptyRepository.cs"]
    assert repo_json["function"][0]["implemented"] is False


def test_table_as_query_select_star_gets_from_and_schema_columns():
    schema = tr.unify_schema_fields({"table_name": "T_ID_Pass", "columns": [
        {"physical_name": "ユーザーID", "data_type": "Text", "length": "50", "required": "True"},
        {"physical_name": "パスワード", "data_type": "Text", "length": "50", "required": "True"},
        {"physical_name": "管理者フラグ", "data_type": "Integer"},
    ]})
    files, repo_json = _generate([{"query_name": "T_ID_Pass", "sheet_name_pattern": "F003_SelQuery01",
                                   "sql": {}, "raw_sql": "SELECT\n*"}], schema=schema)
    repo, entity = files["TIDPassRepository.cs"], files["TIDPassEntity.cs"]
    # entity: Domain.Common using, no password property
    assert "using vba_brain.Domain.Common;" in entity and "public class TIDPassEntity : BaseEntity" in entity
    assert "パスワード" not in entity
    # SELECT * expanded without the password column
    assert '"ユーザーID" AS "TODO_ユーザーID"' in repo and 'FROM "T_ID_Pass"' in repo
    assert '"パスワード" AS' not in repo
    # parameterized credential check
    assert "public async Task<bool> VerifyCredentialsAsync(string id, string password)" in repo
    assert 'WHERE "ユーザーID" = @id' in repo and 'AND "パスワード" = @password' in repo
    check = next(fn for fn in repo_json["function"] if fn.get("kind") == "credential_check")
    assert [i["name"] for i in check["input"]] == ["id", "password"]
    assert all("パスワード" != f["description"] for f in repo_json["entity"][0]["fields"])


def test_password_only_select_is_not_generated():
    files, repo_json = _generate([{"query_name": "Q_Pass", "sheet_name_pattern": "F003_SelQuery01",
                                   "raw_sql": "SELECT T_ID_Pass.Pass FROM T_ID_Pass WHERE T_ID_Pass.ID = :txtID"}])
    repo = files["QPassRepository.cs"]
    assert "throw new NotImplementedException(" in repo and "VerifyCredentialsAsync" in repo
    assert repo_json["function"][0]["implemented"] is False


def test_binds_become_typed_parameters_and_dapper_members():
    schema = tr.unify_schema_fields({"table_name": "T_Order", "columns": [
        {"physical_name": "注文番号", "data_type": "Long"}, {"physical_name": "顧客名", "data_type": "Text"}]})
    config = {"table_name": {}, "field_name": {"注文番号": "OrderNo", "顧客名": "CustomerName"},
              "parameter_name": {"注文番号": "orderNo"}, "function_name": {"Q_Order": "GetOrder"}, "cte_name": {}}
    files, repo_json = _generate([{"query_name": "Q_Order", "sheet_name_pattern": "F000_SelQuery01",
                                   "sql": {"select": "注文番号, 顧客名", "from": "T_Order",
                                           "where": [{"condition": "注文番号 = :txt注文番号"}]}}],
                                 schema=schema, config=config)
    repo = files["TOrderRepository.cs"]
    assert "GetOrderAsync(int orderNo)" in repo
    assert "new { txt注文番号 = orderNo }" in repo
    assert '注文番号 AS "OrderNo"' in repo and '顧客名 AS "CustomerName"' in repo
    fn = repo_json["function"][0]
    assert fn["input"] == [{"name": "orderNo", "type": "int", "description": "注文番号", "vba": "txt注文番号"}]
    assert fn["return_type"] == "IEnumerable<TOrderEntity>"


def test_translated_name_collisions_get_suffixes():
    schema = tr.unify_schema_fields({"table_name": "T_Flag", "columns": [
        {"physical_name": "ONOFF", "data_type": "Yes/No"}, {"physical_name": "ＯＮＯＦＦ", "data_type": "Yes/No"}]})
    config = {"table_name": {}, "field_name": {"ONOFF": "OnOff", "ＯＮＯＦＦ": "OnOff"}, "parameter_name": {},
              "function_name": {"Q_A": "GetFlag", "Q_B": "GetFlag"}, "cte_name": {}}
    files, _ = _generate([
        {"query_name": "Q_A", "sheet_name_pattern": "F000_SelQuery01", "sql": {"select": "*", "from": "T_Flag"}},
        {"query_name": "Q_B", "sheet_name_pattern": "F000_SelQuery02", "sql": {"select": "*", "from": "T_Flag"}},
    ], schema=schema, config=config)
    entity, repo = files["TFlagEntity.cs"], files["TFlagRepository.cs"]
    assert "public bool OnOff { get; set; }" in entity and "public bool OnOff2 { get; set; }" in entity
    assert "GetFlagAsync(" in repo and "GetFlag2Async(" in repo
