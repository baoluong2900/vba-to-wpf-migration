"""gRPC gateway servicers (src/backend/api_gateway/grpc_server.py) with the layers faked out."""
from __future__ import annotations

import json
import sys
import threading
import types
from pathlib import Path

import pytest

GATEWAY_DIR = Path(__file__).resolve().parents[2] / "src" / "backend" / "api_gateway"
sys.path.insert(0, str(GATEWAY_DIR))

grpc_server = pytest.importorskip("grpc_server")
import workflow_pb2 as pb  # noqa: E402  (generated module, importable once the gateway dir is on sys.path)


@pytest.mark.parametrize("name", ["F_Login", "T023地区CD設定", "A_メニューバーを表示", "Q (copy) 1", "x.y"])
def test_ordinary_item_names_are_accepted(name):
    assert grpc_server._bad_name(name) is None


@pytest.mark.parametrize("name", ["", ".", "..", "../config", "a/b", "a\\b", "/etc/passwd", "C:evil", "nul\x00byte"])
def test_names_that_could_escape_a_folder_are_rejected(name):
    assert grpc_server._bad_name(name) is not None


def test_bad_name_reports_the_first_offender():
    assert "../x" in grpc_server._bad_name("ok", "../x", "also/bad")


class FakeRouter:
    def __init__(self):
        self.calls = {}

    def update_query(self, name, req):
        self.calls["update"] = (name, req.target_sql, req.status)
        return {"success": True, "result": {"name": name, "target_sql": req.target_sql}}

    def convert_query(self, req):
        self.calls["convert"] = (req.name, req.model)
        return {"success": False, "error": "SQL conversion failed: boom"}

    def seed_queries(self):
        return {"success": False, "error": "mongo down"}

    def get_stats(self):
        return {"success": True, "total": 3, "pending": 1, "converted": 2, "error_count": 0}


@pytest.fixture()
def sql_service(monkeypatch):
    router = FakeRouter()
    monkeypatch.setattr(grpc_server, "l3_router", router)
    return grpc_server.Layer4ServiceServicer(), router


def test_update_passes_the_request_through(sql_service):
    service, router = sql_service
    res = service.UpdateMigrationQuery(pb.UpdateQueryRequest(name="Q1", target_sql="SELECT 1"), None)
    assert res.success and json.loads(res.query_json)["target_sql"] == "SELECT 1"
    assert router.calls["update"] == ("Q1", "SELECT 1", "")


def test_conversion_failure_is_reported(sql_service):
    service, router = sql_service
    res = service.ConvertQuery(pb.ConvertQueryRequest(name="Q1"), None)
    assert not res.success and "boom" in res.error
    assert router.calls["convert"] == ("Q1", "")


def test_seed_failure_is_not_reported_as_success(sql_service):
    res = sql_service[0].SeedQueries(pb.Empty(), None)
    assert not res.success and res.error == "mongo down"


def test_stats(sql_service):
    res = sql_service[0].GetStats(pb.Empty(), None)
    assert res.success and json.loads(res.stats_json)["total"] == 3


def test_excel_generation_failures_propagate():
    service = grpc_server.Layer3ServiceServicer()
    request = pb.GenRequest(screen_name="F_Login", type="screen")

    ok = service._gen(lambda req: {"success": True, "file_info": {}}, request)
    assert ok.success

    failed = service._gen(lambda req: {"success": False, "error": "not generated yet"}, request)
    assert not failed.success and failed.error == "not generated yet"

    half = service._gen(lambda req: {"success": True, "bd": {"success": True}, "dd": {"success": False, "error": "dd broke"}}, request)
    assert not half.success and "dd broke" in half.error


def test_excel_generation_rejects_traversal():
    res = grpc_server.Layer3ServiceServicer()._gen(lambda req: pytest.fail("must not be called"),
                                                    pb.GenRequest(screen_name="../../config", type="screen"))
    assert not res.success and "invalid name" in res.error


def test_status_rejects_traversal():
    res = grpc_server.Layer2ServiceServicer.GetBdStatus(None, pb.BdStatusRequest(screen_name="../x"), None)
    assert not res.success


class FakeDDService:
    """Like DDService.run_full_flow: one LLM call per DD3 module, made on a worker pool."""

    in_flight: threading.Barrier

    def __init__(self, stage=None):
        pass

    def run_full_flow(self, screen_name, model_id=None, force=False):
        ct = sys.modules[grpc_server.CostTracker.__module__]
        FakeDDService.in_flight.wait(timeout=5)  # both requests are running at the same time
        with ct.ContextThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: ct.get_tracker().record(screen_name, "qwen-plus", "DD3", 100, 50), range(3)))
        return {"screen_name": screen_name}


def test_concurrent_dd_runs_report_only_their_own_tokens(monkeypatch, tmp_path):
    ct = sys.modules[grpc_server.CostTracker.__module__]
    monkeypatch.setattr(ct, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(grpc_server, "DDService", FakeDDService)
    monkeypatch.setitem(sys.modules, "push_to_mongo", types.SimpleNamespace(push_dd_one=lambda name: None))
    FakeDDService.in_flight = threading.Barrier(2)
    service = grpc_server.Layer2ServiceServicer.__new__(grpc_server.Layer2ServiceServicer)  # no Mongo repo
    responses = {}

    def run(name):
        responses[name] = service.RunDdFlowFull(pb.DdFlowRequest(screen_name=name), None)

    threads = [threading.Thread(target=run, args=(name,)) for name in ("F_Login", "F_Menu")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert set(responses) == {"F_Login", "F_Menu"}
    for name, res in responses.items():
        assert res.success, res.error
        stats = json.loads(res.token_stats_json)
        assert {r["item"] for r in stats["records"]} == {name}
        assert (stats["total_input_tokens"], stats["total_output_tokens"]) == (300, 150)
    # GetTokenReport: the last finished request, not both mixed together
    last = json.loads(service.GetTokenReport(pb.Empty(), None).token_stats_json)
    assert last["total_tokens"] == 450
