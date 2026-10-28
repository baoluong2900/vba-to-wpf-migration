"""Layer 3 review workflow (src/backend/workflow/layer3/sql_migration/router.py) on an in-memory store."""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from layer3.sql_migration import router


class FakeCollection:
    """The handful of pymongo Collection methods router.py uses."""

    def __init__(self, docs):
        self.docs = [copy.deepcopy(d) for d in docs]

    @staticmethod
    def _matches(doc, flt):
        return all(doc.get(k) == v for k, v in (flt or {}).items())

    @staticmethod
    def _project(doc, projection):
        out = copy.deepcopy(doc)
        if projection and projection.get("_id") == 0:
            out.pop("_id", None)
        return out

    def find(self, flt=None, projection=None):
        return [self._project(d, projection) for d in self.docs if self._matches(d, flt)]

    def find_one(self, flt=None, projection=None):
        found = self.find(flt, projection)
        return found[0] if found else None

    def update_one(self, flt, update):
        for doc in self.docs:
            if self._matches(doc, flt):
                doc.update(update["$set"])
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    def count_documents(self, flt):
        return len(self.find(flt))


REVIEWED = {
    "_id": 1,
    "name": "Q_Users",
    "sql": "SELECT IIf(Age > 18, 'adult', 'minor') FROM TBL_Users WHERE ID = :id",
    "target_sql": "SELECT CASE WHEN age > 18 THEN 'adult' ELSE 'minor' END FROM tbl_users WHERE id = :id",
    "conversion_status": "converted",
    "reviewer": "alice",
    "notes": "hand-checked",
    "description": "user age band",
}


@pytest.fixture()
def store(monkeypatch):
    collections = {
        "queries_v2": FakeCollection([REVIEWED, {"_id": 2, "name": "Q_Pending", "sql": "SELECT 1", "conversion_status": "pending"}]),
        "tables": FakeCollection([{"_id": 9, "table_name": "TBL_Users", "columns": [{"logical_name": "ID", "data_type": "Long"}]}]),
    }
    monkeypatch.setattr(router, "get_db", lambda: collections)
    return collections


def fake_llm(monkeypatch, reply=None, error=None):
    class _Client:
        def chat(self, model_cfg, system, user):
            if error:
                raise error
            return reply

    monkeypatch.setattr(router, "LLMClient", _Client)


def update_request(**fields):
    base = dict(target_sql="", target_query_json="", notes="", status="", reviewer="", description="", model="")
    base.update(fields)
    return SimpleNamespace(**base)


def test_list_and_get_add_raw_sql(store):
    listed = router.list_queries()
    assert listed["success"] and {q["name"] for q in listed["result"]} == {"Q_Users", "Q_Pending"}
    got = router.get_query("Q_Users")["result"]
    assert got["raw_sql"] == REVIEWED["sql"] and "_id" not in got


def test_save_keeps_fields_the_client_did_not_send(store):
    # The console's Save sends only target_sql + description; proto3 delivers "" for the rest.
    res = router.update_query("Q_Users", update_request(target_sql="SELECT 1 WHERE id = :id", description="new"))
    assert res["success"]
    saved = res["result"]
    assert saved["target_sql"] == "SELECT 1 WHERE id = :id"
    assert saved["bind_variables"] == ["id"]
    assert saved["description"] == "new"
    assert (saved["conversion_status"], saved["reviewer"], saved["notes"]) == ("converted", "alice", "hand-checked")


def test_save_parses_target_query_json(store):
    res = router.update_query("Q_Users", update_request(target_sql="SELECT 1", target_query_json='{"select": "1"}'))
    assert res["result"]["target_query_json"] == {"select": "1"}


def test_save_rejects_invalid_target_query_json(store):
    res = router.update_query("Q_Users", update_request(target_sql="SELECT 1", target_query_json="{nope"))
    assert not res["success"]


def test_save_unknown_query(store):
    assert router.update_query("Nope", update_request(target_sql="x")) == {"success": False, "error": "Query not found"}


def test_convert_stores_model_json(store, monkeypatch):
    fake_llm(monkeypatch, '```json\n{"target_sql": "SELECT 1 FROM t WHERE a = :p", "explanation": "IIf → CASE"}\n```')
    res = router.convert_query(SimpleNamespace(name="Q_Pending", model="qwen-max"))
    assert res["success"]
    doc = res["result"]
    assert doc["target_sql"] == "SELECT 1 FROM t WHERE a = :p"
    assert doc["conversion_status"] == "converted"
    assert doc["bind_variables"] == ["p"]
    assert "IIf → CASE" in doc["notes"]


def test_convert_accepts_bare_fenced_sql(store, monkeypatch):
    fake_llm(monkeypatch, "```sql\nSELECT 2\n```")
    assert router.convert_query(SimpleNamespace(name="Q_Pending", model=""))["result"]["target_sql"] == "SELECT 2"


def test_convert_garbage_is_an_error_not_a_conversion(store, monkeypatch):
    fake_llm(monkeypatch, "Sorry, I cannot help with that.")
    res = router.convert_query(SimpleNamespace(name="Q_Users", model="qwen-max"))
    assert not res["success"]
    doc = store["queries_v2"].find_one({"name": "Q_Users"})
    assert doc["conversion_status"] == "error"
    assert doc["target_sql"] == REVIEWED["target_sql"], "reviewed SQL must survive a failed conversion"


def test_convert_llm_failure_keeps_reviewed_sql(store, monkeypatch):
    fake_llm(monkeypatch, error=TimeoutError("upstream timeout"))
    res = router.convert_query(SimpleNamespace(name="Q_Users", model="qwen-max"))
    assert not res["success"] and "upstream timeout" in res["error"]
    doc = store["queries_v2"].find_one({"name": "Q_Users"})
    assert doc["target_sql"] == REVIEWED["target_sql"]
    assert doc["notes"].startswith("Conversion error")


def test_convert_unknown_query(store, monkeypatch):
    fake_llm(monkeypatch, "{}")
    assert router.convert_query(SimpleNamespace(name="Nope", model=""))["success"] is False


def test_stats(store):
    assert router.get_stats() == {"success": True, "total": 2, "pending": 1, "converted": 1, "error_count": 0}


def test_tables(store):
    assert router.list_tables()["result"][0]["table_name"] == "TBL_Users"
    assert router.convert_table_schema("TBL_Users", "PostgreSQL")["ddl"].startswith("CREATE TABLE TBL_Users (")
    assert router.convert_table_schema("Missing", "PostgreSQL")["success"] is False
