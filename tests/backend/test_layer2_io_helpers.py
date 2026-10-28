"""Layer 2 I/O helpers: output-path safety, token-log persistence, Layer 1 repo lookups, DD prompt routing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAYER2 = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer2"
if str(LAYER2) not in sys.path:
    sys.path.insert(0, str(LAYER2))

import pytest

from agents.bd_agent.module.module_resolver import find_module_function_code
from agents.dd_agent.core.dd_prompt import build_dd_prompt
from db.layer1_repo import Layer1Repo
from utils import cost_tracker
from utils.paths import bd3_result_path, safe_child_path, validate_item_name


# ── Output paths ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["", ".", "..", "../config", "a/b", "a\\b", "/tmp/x", "x\x00y", None])
def test_unsafe_item_names_are_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        safe_child_path(tmp_path, name)


@pytest.mark.parametrize("name", ["F_Login", "C000_MAINⅡ", "a..b", "R_月次売上"])
def test_safe_item_names_stay_inside_base(tmp_path, name):
    path = safe_child_path(tmp_path, name, ".jsonl", prefix="input_")
    assert path == tmp_path / f"input_{name}.jsonl"
    assert validate_item_name(name) == name


def test_bd3_result_path_uses_the_name_bd_writes(tmp_path):
    assert bd3_result_path("F_Login", tmp_path) == tmp_path / "result_F_Login.json"


# ── Token log ─────────────────────────────────────────────────────────────────

def _tracker_with_one_record() -> cost_tracker.CostTracker:
    t = cost_tracker.CostTracker()
    t.record(item_name="F001", model_id="qwen-max", stage="bd_logic", input_tokens=1000, output_tokens=500)
    return t


def test_save_report_appends_history(tmp_path, monkeypatch):
    monkeypatch.setattr(cost_tracker, "LOG_DIR", str(tmp_path))
    _tracker_with_one_record().save_report(label="A")
    _tracker_with_one_record().save_report(label="B")
    history = json.loads((tmp_path / "token_log.json").read_text(encoding="utf-8"))
    assert [h["screen_name"] for h in history] == ["A", "B"]


def test_save_report_keeps_an_unreadable_history_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cost_tracker, "LOG_DIR", str(tmp_path))
    log = tmp_path / "token_log.json"
    log.write_text('[{"timestamp": "truncated', encoding="utf-8")

    _tracker_with_one_record().save_report(label="after-corruption")

    backups = list(tmp_path.glob("token_log.json.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == '[{"timestamp": "truncated'
    history = json.loads(log.read_text(encoding="utf-8"))
    assert [h["screen_name"] for h in history] == ["after-corruption"]


def test_routed_models_have_explicit_prices():
    for model_id in ("qwen3-coder-480b-a35b-instruct", "qwen3-coder-next", "qwen3-235b-a22b-instruct-2507",
                     "qwen-plus-2025-07-28", "qwen-max-latest"):
        assert model_id in cost_tracker._PRICE_INPUT_PER_1M
        assert model_id in cost_tracker._PRICE_OUTPUT_PER_1M


# ── Layer 1 repo ──────────────────────────────────────────────────────────────

class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, flt, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in flt.items()):
                return dict(d)
        return None


def _repo_with(collections: dict) -> Layer1Repo:
    repo = object.__new__(Layer1Repo)  # skip __init__: no MongoDB
    repo._db = {name: FakeCollection(collections.get(name, [])) for name in
                ("forms", "reports", "modules", "macros", "queries_v2", "tables", "dependency_graph")}
    return repo


def test_dd_unified_lookup_handles_queries():
    repo = _repo_with({"queries_v2": [{"name": "Q_Sales", "query_type": "SELECT", "tables": ["T_Sales"]}]})
    payload = repo.get_dd_code_json_unified("Q_Sales")
    assert payload["request_type"] == "query_analysis"
    assert payload["query"]["name"] == "Q_Sales"


# ── Module resolver ───────────────────────────────────────────────────────────

class FakeModuleRepo:
    def __init__(self):
        self.looked_up = []

    def list_modules(self):  # the resolver must not scan every module
        raise AssertionError("list_modules() should not be called")

    def find_module_name_for_procedure(self, proc_name):
        return "Mod_Common" if proc_name == "SafeString" else ""

    def get_bd_code_json_module(self, module_name):
        self.looked_up.append(module_name)
        return {"module": {"name": module_name, "procedures": [{"handler": "SafeString", "code": "Function SafeString()"}]}}


def test_module_resolver_reads_procedures_of_the_named_module():
    repo = FakeModuleRepo()
    assert find_module_function_code(repo, "Mod_Common.SafeString") == ("Function SafeString()", [])
    assert repo.looked_up == ["Mod_Common"]


def test_module_resolver_finds_the_module_of_a_bare_procedure_name():
    repo = FakeModuleRepo()
    assert find_module_function_code(repo, "SafeString") == ("Function SafeString()", [])
    assert find_module_function_code(repo, "Missing") == ("", [])


# ── DD prompt routing ─────────────────────────────────────────────────────────

def test_report_uses_the_screen_prompt():
    item = {"module_id": "F000", "title": "Open", "code": "Sub Report_Open()\nEnd Sub", "queries": []}
    event = {"event_content": "帳票を開く"}
    assert build_dd_prompt(item, event, "", category="report") == build_dd_prompt(item, event, "", category="screen")
    assert build_dd_prompt(item, event, "", category="report") != build_dd_prompt(item, event, "", category="common")
