"""
llm/model_router.py — Select the appropriate ModelConfig based on complexity and stage.

Used by BDAgent and DDAgent to dispatch to the correct model.
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
    Select the appropriate ModelConfig based on complexity and current stage, or use a specific model_id.

    Args:
        complexity_level: "critical" | "high" | "medium" | "low"
        stage: "dev" | "pilot" | "production" (default is STAGE from env)
        model_id: Explicitly requested model ID (e.g. from UI)

    Returns:
        ModelConfig instance.
    """
    # 1. If a specific model_id is provided, prioritize returning that config
    if model_id and model_id in AVAILABLE_MODELS:
        return AVAILABLE_MODELS[model_id]

    effective_stage = stage or STAGE

    if effective_stage == "dev":
        return DEV_MODEL

    if effective_stage == "pilot":
        return PILOT_MODEL

    # production: route theo complexity
    return PRODUCTION_ROUTING.get(complexity_level, PRODUCTION_ROUTING["low"])
