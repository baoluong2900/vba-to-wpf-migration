"""
core/pipeline.py — LangGraph pipeline builder for Layer 2.

Currently: simple stub because server.py directly calls BDService.
Full pipeline (BD → DD → Review) will be expanded in a future version.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_pipeline():
    """
    Build and return LangGraph pipeline object.

    Call in BD → DD order.
    """
    from langgraph.graph import StateGraph, END
    from state import PipelineState
    from agents.bd_agent.bd_service import BDService
    from agents.dd_agent.dd_service import DDService
    from config import STAGE

    builder = StateGraph(PipelineState)

    def run_bd(state: PipelineState) -> PipelineState:
        if state.get("item_type") in ("module", "macro"):
            state["bd_docs_json"] = None
            return state

        from db.layer1_repo import Layer1Repo
        service = BDService(state.get("stage", STAGE))
        repo = state.get("repo") or Layer1Repo()
        result = service.run_full_flow(
            screen_name=state["screen_name"],
            bd_code_json=state["bd_code_json"],
            item_type=state["item_type"],
            repo=repo,
            model_id=state.get("model_id"),
            complexity_level=state.get("complexity_level"),
        )
        state["bd_docs_json"] = result
        return state

    def run_dd(state: PipelineState) -> PipelineState:
        service = DDService(state.get("stage", STAGE))
        result = service.run_full_flow(
            screen_name=state["screen_name"],
            model_id=state.get("model_id"),
            force=True,
            complexity_level=state.get("complexity_level"),
        )
        state["dd_docs_json"] = result
        return state

    builder.add_node("bd_stage", run_bd)
    builder.add_node("dd_stage", run_dd)
    builder.set_entry_point("bd_stage")
    builder.add_edge("bd_stage", "dd_stage")
    builder.add_edge("dd_stage", END)

    return builder.compile()
