"""
core/pipeline.py — LangGraph pipeline builder cho Layer 2.

Hiện tại: stub đơn giản vì server.py gọi trực tiếp BDService.
Pipeline đầy đủ (BD → DD → Review) sẽ được mở rộng trong phiên bản sau.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_pipeline():
    """
    Xây dựng và trả về LangGraph pipeline object.

    Stub: trả về object có method invoke() gọi theo thứ tự BD → DD.
    Sẽ được thay bằng LangGraph StateGraph khi DD stage hoàn thiện.
    """
    try:
        from langgraph.graph import StateGraph, END
        from state import PipelineState
        from agents.bd_agent.bd_service import BDService
        from config import STAGE

        builder = StateGraph(PipelineState)

        def run_bd(state: PipelineState) -> PipelineState:
            from db.layer1_repo import Layer1Repo
            service = BDService(state.get("stage", STAGE))
            repo = state.get("repo") or Layer1Repo()
            result = service.run_full_flow(
                screen_name=state["screen_name"],
                bd_code_json=state["bd_code_json"],
                item_type=state["item_type"],
                repo=repo,
                model_id=state.get("model_id"),
            )
            state["bd_docs_json"] = result
            return state

        builder.add_node("bd_stage", run_bd)
        builder.set_entry_point("bd_stage")
        builder.add_edge("bd_stage", END)

        return builder.compile()

    except ImportError:
        logger.warning("[Pipeline] LangGraph not installed. Using minimal pipeline.")
        return _MinimalPipeline()


class _MinimalPipeline:
    """Fallback pipeline khi LangGraph chưa được cài."""

    def invoke(self, state: dict) -> dict:
        from agents.bd_agent.bd_service import BDService
        from config import STAGE

        from db.layer1_repo import Layer1Repo
        stage = state.get("stage", STAGE)
        service = BDService(stage)
        repo = state.get("repo") or Layer1Repo()
        result = service.run_full_flow(
            screen_name=state["screen_name"],
            bd_code_json=state["bd_code_json"],
            item_type=state["item_type"],
            repo=repo,
            model_id=state.get("model_id"),
        )
        state["bd_docs_json"] = result
        return state
