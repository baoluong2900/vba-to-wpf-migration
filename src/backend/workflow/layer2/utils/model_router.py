"""
llm/model_router.py — Select the appropriate ModelConfig based on complexity and stage.

Used by BDAgent and DDAgent to dispatch to the correct model.
"""
from __future__ import annotations

import logging
import threading

from config import (
    ModelConfig,
    STAGE,
    DEV_MODEL,
    PILOT_MODEL,
    PRODUCTION_ROUTING,
    AVAILABLE_MODELS,
)

logger = logging.getLogger(__name__)

_warned_substitutions: set[tuple[str, str]] = set()
_warned_lock = threading.Lock()

# Fallback chain: if primary model fails, try these in order
FALLBACK_CHAIN = {
    # Coder models
    "qwen3-coder-480b-a35b-instruct": ["qwen3-coder-next", "qwen3-coder-plus", "qwen-max", "qwen-plus"],
    "qwen3-coder-next": ["qwen3-coder-480b-a35b-instruct", "qwen3-coder-plus", "qwen-max", "qwen-plus"],
    "qwen3-coder-plus": ["qwen3-coder-flash", "qwen-max", "qwen-plus"],
    "qwen3-coder-flash": ["qwen3-coder-plus", "qwen-flash", "qwen-plus"],
    "qwen3-coder-30b-a3b-instruct": ["qwen3-coder-flash", "qwen-max", "qwen-plus"],
    # Max/flagship models
    "qwen3-max": ["qwen3.5-plus", "qwen-max", "qwen-plus"],
    "qwen-max": ["qwen-max-latest", "qwen3.5-plus", "qwen-plus", "qwen-turbo"],
    "qwen-max-latest": ["qwen-max", "qwen3.5-plus", "qwen-plus", "qwen-turbo"],
    # Plus models
    "qwen3.5-plus": ["qwen-plus", "qwen-plus-latest", "qwen-turbo"],
    "qwen-plus": ["qwen-plus-latest", "qwen-plus-2025-12-01", "qwen-plus-2025-07-28", "qwen-turbo"],
    "qwen-plus-latest": ["qwen-plus", "qwen-plus-2025-12-01", "qwen-turbo"],
    "qwen-plus-2025-12-01": ["qwen-plus", "qwen-plus-2025-07-28", "qwen-turbo"],
    "qwen-plus-2025-09-11": ["qwen-plus", "qwen-plus-2025-07-28", "qwen-turbo"],
    "qwen-plus-2025-07-28": ["qwen-plus", "qwen-plus-latest", "qwen-turbo"],
    # Flash models
    "qwen3.5-flash": ["qwen-flash", "qwen-turbo"],
    "qwen-flash": ["qwen-flash-latest", "qwen3.5-flash", "qwen-turbo"],
    "qwen-flash-latest": ["qwen-flash", "qwen3.5-flash", "qwen-turbo"],
    # Turbo models
    "qwen-turbo": ["qwen-turbo-latest", "qwen-flash", "qwen-plus"],
    "qwen-turbo-latest": ["qwen-turbo", "qwen-flash", "qwen-plus"],
    # Large open-source models
    "qwen3-235b-a22b": ["qwen3-235b-a22b-thinking-2507", "qwen-max", "qwen-plus"],
    "qwen3-235b-a22b-thinking-2507": ["qwen3-235b-a22b", "qwen-max", "qwen-plus"],
    "qwen3-235b-a22b-instruct-2507": ["qwen3-235b-a22b", "qwen-max", "qwen-plus"],
    "qwen3-next-80b-a3b-thinking": ["qwen3-235b-a22b-thinking-2507", "qwen-max"],
    "qwen3-next-80b-a3b-instruct": ["qwen3-235b-a22b-instruct-2507", "qwen-max"],
    "qwen3-32b": ["qwen3-30b-a3b", "qwen-plus", "qwen-turbo"],
    "qwen3-30b-a3b": ["qwen3-32b", "qwen-plus", "qwen-turbo"],
    "qwen3-30b-a3b-thinking-2507": ["qwen3-30b-a3b", "qwen-plus"],
    "qwen3-30b-a3b-instruct-2507": ["qwen3-30b-a3b", "qwen-plus"],
    "qwen3-14b": ["qwen3-8b", "qwen-turbo"],
    "qwen3-8b": ["qwen3-14b", "qwen-turbo"],
    "qwen3-4b": ["qwen3-8b", "qwen-flash"],
    # Reasoning
    "qwq-plus": ["qwen3-max", "qwen-max", "qwen-plus"],
    # VL models
    "qwen3-vl-plus": ["qwen3-vl-flash", "qwen-vl-max", "qwen-vl-plus"],
    "qwen3-vl-flash": ["qwen3-vl-plus", "qwen-vl-plus"],
    "qwen-vl-max": ["qwen-vl-max-latest", "qwen3-vl-plus"],
    "qwen-vl-plus": ["qwen-vl-plus-latest", "qwen3-vl-flash"],
    # Math
    "qwen-math-plus": ["qwen-math-plus-latest", "qwen-math-turbo", "qwen-plus"],
    "qwen-math-turbo": ["qwen-math-plus", "qwen-plus"],
    # Translation
    "qwen-mt-plus": ["qwen-mt-flash", "qwen-mt-lite"],
    "qwen-mt-flash": ["qwen-mt-plus", "qwen-mt-lite"],
}


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
        chosen = DEV_MODEL
    elif effective_stage == "pilot":
        chosen = PILOT_MODEL
    else:
        # production: route by complexity
        chosen = PRODUCTION_ROUTING.get(complexity_level, PRODUCTION_ROUTING["low"])

    if model_id:
        with _warned_lock:
            first_time = (model_id, chosen.model_id) not in _warned_substitutions
            _warned_substitutions.add((model_id, chosen.model_id))
        if first_time:
            logger.warning(
                "[ModelRouter] Requested model '%s' is not in AVAILABLE_MODELS — using '%s' instead "
                "(stage=%s, complexity=%s)",
                model_id, chosen.model_id, effective_stage, complexity_level,
            )
    return chosen


def get_fallback_model(primary_model_id: str, tried: frozenset[str] | set[str] = frozenset()) -> ModelConfig | None:
    """
    Get the next fallback model when the primary model fails (e.g., quota exhausted).
    
    Args:
        primary_model_id: The model ID whose fallback chain is walked
        tried: Model IDs already attempted (skipped)
        
    Returns:
        First available fallback ModelConfig in the chain that has not been tried, or None
    """
    for fallback_id in FALLBACK_CHAIN.get(primary_model_id, []):
        if fallback_id in AVAILABLE_MODELS and fallback_id not in tried and fallback_id != primary_model_id:
            return AVAILABLE_MODELS[fallback_id]
    return None
