"""
dd_agent/dd_agent.py — LLM executor for DD stage (D3 detail spec generation)

Rewrote to fix import errors and align with bd_agent pattern.
"""
from __future__ import annotations

import json
from typing import Any

from utils.llm_client import LLMClient, parse_json_response
from utils.cost_tracker import get_tracker
from .dd_prompt import SYSTEM_PROMPT, build_dd_prompt
from utils.logger import get_logger

logger = get_logger(__name__)


class DDAgent:
    """Calls LLM to generate detail spec steps for one VBA module (D3)."""

    def __init__(self) -> None:
        self._client = LLMClient()

    def run(
        self,
        logic_item: dict[str, Any],
        bd_event: dict[str, Any],
        dd_schema_template: str,
        category: str = "screen",
        model_id: str | None = None,
        retry_context: dict | None = None,
    ) -> dict[str, Any]:
        """
        Run D3 for one module.
        """
        from utils.model_router import select_model
        model_cfg = select_model(complexity_level="medium", model_id=model_id)

        module_id = logic_item.get("module_id", "UNKNOWN")
        user_prompt = build_dd_prompt(logic_item, bd_event, dd_schema_template, category, retry_context)


        logger.info(
            "[DD Agent] %s/%s  module=%s  retry=%s",
            model_cfg.provider, model_cfg.model_id, module_id,
            retry_context is not None,
        )

        raw, usage = self._client.chat_with_usage(model_cfg, SYSTEM_PROMPT, user_prompt)

        # Cost tracking — use real token counts from API
        tracker = get_tracker()
        tracker.record(
            item_name=module_id,
            model_id=model_cfg.model_id,
            stage="dd_detail",
            input_tokens=usage.get("input_tokens") or len(user_prompt) // 4,
            output_tokens=usage.get("output_tokens") or len(raw) // 4,
            flow_type="DD Agent",
        )

        try:
            result = parse_json_response(raw)
            logger.debug("[DD Agent] module=%s  output keys=%s", module_id, list(result.keys()))
            return result
        except Exception as e:
            logger.error("[DD Agent] Parse error module=%s: %s | raw=%s", module_id, e, raw[:200])
            return {
                "module_id": module_id,
                "steps": [
                    {"step": "1. 初期処理", "detail": ""},
                    {"step": "2. 主処理",   "detail": ""},
                    {"step": "3. 終了処理", "detail": ""},
                ],
                "event_detail": ""
            }
