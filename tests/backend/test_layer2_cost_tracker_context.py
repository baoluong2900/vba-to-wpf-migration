"""Per-request cost tracking (layer2/utils/cost_tracker): concurrent requests keep their own records."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

LAYER2 = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer2"
if str(LAYER2) not in sys.path:
    sys.path.insert(0, str(LAYER2))

import pytest

from utils import cost_tracker
from utils.cost_tracker import ContextThreadPoolExecutor, get_tracker, last_request_tracker, track_request


def _record(item: str) -> None:
    get_tracker().record(item, "qwen-plus", "BD3", 10, 5)


@pytest.fixture(autouse=True)
def fresh_module_state(monkeypatch):
    monkeypatch.setattr(cost_tracker, "_tracker", None)
    monkeypatch.setattr(cost_tracker, "_last_request", None)


def test_concurrent_requests_keep_their_own_records():
    # The gateway used to reset one shared tracker per request: both requests then recorded
    # into whichever tracker was created last.
    both_inside = threading.Barrier(2)
    trackers = {}

    def request(name):
        with track_request() as tracker:
            both_inside.wait(timeout=5)
            _record(name)
            both_inside.wait(timeout=5)
            _record(name)
        trackers[name] = tracker

    threads = [threading.Thread(target=request, args=(name,)) for name in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert [r.item_name for r in trackers["A"].records] == ["A", "A"]
    assert [r.item_name for r in trackers["B"].records] == ["B", "B"]


def test_pool_workers_record_into_the_submitting_request():
    with track_request() as tracker:
        with ContextThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(_record, ["m1", "m2", "m3", "m4"]))
    assert sorted(r.item_name for r in tracker.records) == ["m1", "m2", "m3", "m4"]
    assert get_tracker().records == []


def test_outside_a_request_the_process_wide_tracker_is_used():
    process_wide = get_tracker()
    assert get_tracker() is process_wide
    assert last_request_tracker() is process_wide  # no request has finished yet

    with track_request() as tracker:
        assert get_tracker() is tracker
        assert tracker is not process_wide

    assert get_tracker() is process_wide
    assert last_request_tracker() is tracker


def test_langgraph_nodes_record_into_the_request():
    # BD/DD agents are LangGraph graphs: their nodes must see the request's tracker.
    langgraph = pytest.importorskip("langgraph.graph")
    from typing_extensions import TypedDict

    class State(TypedDict):
        n: int

    def node(state: State) -> dict:
        _record("node")
        return {"n": state["n"] + 1}

    graph = langgraph.StateGraph(State)
    graph.add_node("a", node)
    graph.add_edge(langgraph.START, "a")
    graph.add_edge("a", langgraph.END)
    app = graph.compile()

    with track_request() as tracker:
        with ContextThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: app.invoke({"n": 0}), range(2)))
    assert [r.item_name for r in tracker.records] == ["node", "node"]
