"""BD LangGraph agents with a fake LLM: UI-formula retry loop and BD3 batch merging (layer2/agents/bd_agent/core)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAYER2 = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer2"
if str(LAYER2) not in sys.path:
    sys.path.insert(0, str(LAYER2))

import pytest

from agents.bd_agent.core import bd_logic_graph, bd_ui_graph
from utils.cost_tracker import CostTracker

BATCH = [
    {"item_no": "1", "formula": "=Date()", "physical_name": "src_1"},
    {"item_no": "2", "formula": "=[Total]", "physical_name": "src_2"},
]


class ScriptedClient:
    """LLMClient stand-in: each chat_with_usage call consumes the next scripted reply (Exception = raise)."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def __call__(self):  # used as the LLMClient class: LLMClient() -> self
        return self

    def chat_with_usage(self, cfg, system, user):
        self.calls += 1
        reply = self.replies.pop(0) if self.replies else self.last
        self.last = reply
        if isinstance(reply, Exception):
            raise reply
        return reply, {"input_tokens": 10, "output_tokens": 5}


@pytest.fixture()
def tracker(monkeypatch):
    t = CostTracker()
    monkeypatch.setattr(bd_ui_graph, "get_tracker", lambda: t)
    monkeypatch.setattr(bd_logic_graph, "get_tracker", lambda: t)
    return t


def _use_client(monkeypatch, module, client):
    monkeypatch.setattr(module, "LLMClient", client)


def test_ui_batch_stops_after_bounded_retries_on_garbage(monkeypatch, tracker):
    client = ScriptedClient(["not json at all"])
    _use_client(monkeypatch, bd_ui_graph, client)
    out = bd_ui_graph.BDUIFormulaGraph().run_ui_batch(BATCH, stage="dev")
    assert client.calls == 1 + bd_ui_graph._MAX_RETRIES
    assert [o["translated_description"] for o in out] == ["=Date()", "=[Total]"]


def test_ui_batch_stops_after_bounded_retries_on_errors(monkeypatch, tracker):
    client = ScriptedClient([RuntimeError("boom")])
    _use_client(monkeypatch, bd_ui_graph, client)
    out = bd_ui_graph.BDUIFormulaGraph().run_ui_batch(BATCH, stage="dev")
    assert client.calls == 1 + bd_ui_graph._MAX_RETRIES
    assert [o["translated_description"] for o in out] == ["=Date()", "=[Total]"]


def test_ui_batch_recovers_after_a_transient_error(monkeypatch, tracker):
    good = "\n".join(json.dumps({"item_no": n, "translated_description": f"desc {n}"}) for n in ("1", "2"))
    client = ScriptedClient([RuntimeError("timeout"), good])
    _use_client(monkeypatch, bd_ui_graph, client)
    out = bd_ui_graph.BDUIFormulaGraph().run_ui_batch(BATCH, stage="dev")
    assert client.calls == 2
    assert [o["translated_description"] for o in out] == ["desc 1", "desc 2"]
    assert [r.stage for r in tracker.records] == ["bd_ui_formula"]


def test_ui_batch_falls_back_when_graph_does_not_terminate(monkeypatch, tracker):
    client = ScriptedClient(["not json"])
    _use_client(monkeypatch, bd_ui_graph, client)
    monkeypatch.setattr(bd_ui_graph, "_RECURSION_LIMIT", 2)
    out = bd_ui_graph.BDUIFormulaGraph().run_ui_batch(BATCH, stage="dev")
    assert [o["translated_description"] for o in out] == ["=Date()", "=[Total]"]


def test_logic_batch_is_keyed_by_module_id(monkeypatch, tracker):
    items = [
        {"module_id": "F001", "title": "Open", "code": "Sub A()\nEnd Sub", "queries": []},
        {"module_id": "F002", "title": "Save", "code": "Sub B()\nEnd Sub", "queries": []},
    ]
    reply = "\n".join([
        json.dumps({"module_id": "F002", "event_content": "保存する", "action_type": "UPDATE", "notes": None}),
        json.dumps({"module_id": "F999", "event_content": "unexpected"}),
        "garbage line",
        json.dumps({"module_id": "F002", "event_content": "duplicate ignored"}),
    ])
    _use_client(monkeypatch, bd_logic_graph, ScriptedClient([reply]))
    rerun = []

    def fake_run_logic(self, item, model_id=None, **kwargs):
        rerun.append(item["module_id"])
        return {"module_id": item["module_id"], "event_content": "single", "action_type": "ETC", "notes": ""}

    monkeypatch.setattr(bd_logic_graph.BDLogicGraph, "run_logic", fake_run_logic)
    out = bd_logic_graph.BDLogicGraph().run_logic_batch(items, stage="dev")

    assert [o["module_id"] for o in out] == ["F001", "F002"]
    assert rerun == ["F001"]
    assert out[1] == {"module_id": "F002", "event_content": "保存する", "action_type": "UPDATE", "notes": ""}


def test_logic_batch_reruns_everything_when_the_call_fails(monkeypatch, tracker):
    items = [{"module_id": "F001", "title": "Open", "code": "x", "queries": []}]
    _use_client(monkeypatch, bd_logic_graph, ScriptedClient([RuntimeError("down")]))
    monkeypatch.setattr(
        bd_logic_graph.BDLogicGraph, "run_logic",
        lambda self, item, model_id=None, **kw: {"module_id": item["module_id"], "event_content": "single",
                                                 "action_type": "ETC", "notes": ""},
    )
    out = bd_logic_graph.BDLogicGraph().run_logic_batch(items, stage="dev")
    assert out == [{"module_id": "F001", "event_content": "single", "action_type": "ETC", "notes": ""}]


def test_normalize_result_coerces_llm_fields_to_text():
    norm = bd_logic_graph._normalize_result("F1", {"event_content": ["a", "b"], "action_type": None, "notes": {"x": "n"}})
    assert norm == {"module_id": "F1", "event_content": "a b", "action_type": "", "notes": "n"}
