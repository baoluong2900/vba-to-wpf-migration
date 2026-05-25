"""
llm/model_router.py — Chọn ModelConfig phù hợp dựa trên complexity và stage.

Dùng bởi BDAgent và DDAgent để dispatch tới đúng model.
"""
from __future__ import annotations

from config import (
    ModelConfig,
    STAGE,
    DEV_MODEL,
    PILOT_MODEL,
    PRODUCTION_ROUTING,
    AVAILABLE_MODELS,
)


def select_model(
    complexity_level: str = "low",
    stage: str | None = None,
    model_id: str | None = None,
) -> ModelConfig:
    """
    Chọn ModelConfig phù hợp theo complexity và stage hiện tại, hoặc dùng model_id cụ thể.

    Args:
        complexity_level: "critical" | "high" | "medium" | "low"
        stage: "dev" | "pilot" | "production" (mặc định dùng STAGE từ env)
        model_id: Explicitly requested model ID (e.g. from UI)

    Returns:
        ModelConfig instance.
    """
    # 1. Nếu có model_id cụ thể, ưu tiên trả về config đó
    if model_id and model_id in AVAILABLE_MODELS:
        return AVAILABLE_MODELS[model_id]

    effective_stage = stage or STAGE

    if effective_stage == "dev":
        return DEV_MODEL

    if effective_stage == "pilot":
        return PILOT_MODEL

    # production: route theo complexity
    return PRODUCTION_ROUTING.get(complexity_level, PRODUCTION_ROUTING["low"])
