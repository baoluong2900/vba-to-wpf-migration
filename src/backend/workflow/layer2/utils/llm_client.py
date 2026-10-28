"""
llm/llm_client.py — Layer 2 wrapper inheriting from the common LLMClient.
"""
from __future__ import annotations

import sys
import time
import logging
from pathlib import Path

# Ensure common is in sys.path
_LAYER2_DIR = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _LAYER2_DIR.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from common.llm.llm_client import (
    LLMClient as CommonLLMClient,
    MaxRetriesExceeded,
)
# Re-exported: Layer 2 modules import these from utils.llm_client.
from common.llm.llm_client import extract_code_block, parse_json_response  # noqa: F401
from common.config import ModelConfig
from .model_router import get_fallback_model

logger = logging.getLogger(__name__)

# Same policy as the base client's @retry on _call_alibaba_with_usage
_ALIBABA_MAX_ATTEMPTS = 3
_ALIBABA_INITIAL_DELAY = 2.0


def is_quota_exhausted(exc: BaseException) -> bool:
    """True for DashScope's HTTP 403 AllocationQuota.FreeTierOnly (retrying the same model is pointless)."""
    msg = str(exc)
    return "403" in msg and "FreeTierOnly" in msg


class LLMClient(CommonLLMClient):
    """
    Layer 2 LLM Client wrapper. Inherits all features from common LLMClient.
    Adds fallback model support for quota exhaustion (403 errors).
    """
    
    def chat_with_usage(self, model_cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        """
        Override base: on quota exhaustion (403 AllocationQuota.FreeTierOnly) walk the requested
        model's fallback chain in order until a model answers or the chain is exhausted.
        """
        current = model_cfg
        tried: set[str] = set()
        while True:
            try:
                return super().chat_with_usage(current, system, user)
            except Exception as e:
                tried.add(current.model_id)
                if not is_quota_exhausted(e):
                    raise
                fallback = get_fallback_model(model_cfg.model_id, tried)
                if fallback is None:
                    raise
                logger.warning(
                    "[Quota exhausted] %s — falling back to %s",
                    current.model_id, fallback.model_id,
                )
                current = fallback

    def _call_alibaba_with_usage(self, cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        """Base DashScope call with the base retry policy, except that quota exhaustion fails fast."""
        base_call = CommonLLMClient._call_alibaba_with_usage
        call = getattr(base_call, "__wrapped__", base_call)  # skip the base @retry; retried below
        delay = _ALIBABA_INITIAL_DELAY
        for attempt in range(1, _ALIBABA_MAX_ATTEMPTS + 1):
            try:
                return call(self, cfg, system, user)
            except Exception as exc:
                if is_quota_exhausted(exc):
                    raise
                if attempt == _ALIBABA_MAX_ATTEMPTS:
                    raise MaxRetriesExceeded(
                        f"_call_alibaba_with_usage failed after {attempt} attempts. Last error: {exc}"
                    ) from exc
                logger.warning(
                    "[retry] _call_alibaba_with_usage failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt, _ALIBABA_MAX_ATTEMPTS, exc, delay,
                )
                time.sleep(delay)
                delay *= 2.0
