"""
llm/llm_client.py — Layer 2 wrapper inheriting from the common LLMClient.
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

# Ensure common is in sys.path
_LAYER2_DIR = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _LAYER2_DIR.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from common.llm.llm_client import (
    LLMClient as CommonLLMClient,
    parse_json_response,
    extract_code_block,
)
from common.config import ModelConfig
from .model_router import get_fallback_model

logger = logging.getLogger(__name__)

class LLMClient(CommonLLMClient):
    """
    Layer 2 LLM Client wrapper. Inherits all features from common LLMClient.
    Adds fallback model support for quota exhaustion (403 errors).
    """
    
    def chat_with_usage(self, model_cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        """
        Override base: automatically fall back to an alternative model on quota
        exhaustion (403 AllocationQuota.FreeTierOnly). Per-model retries are still
        handled by the base provider call's @retry decorator.
        """
        current = model_cfg
        tried: set[str] = set()
        while True:
            try:
                return super().chat_with_usage(current, system, user)
            except Exception as e:
                tried.add(current.model_id)
                msg = str(e)
                if "403" in msg and "FreeTierOnly" in msg:
                    fallback = get_fallback_model(current.model_id)
                    if fallback and fallback.model_id not in tried:
                        logger.warning(
                            "[Quota exhausted] %s — falling back to %s",
                            current.model_id, fallback.model_id,
                        )
                        current = fallback
                        continue
                raise

    def call_with_fallback(self, model_cfg: ModelConfig, system: str, user: str, max_retries: int = 3) -> tuple[str, dict]:
        """Backward-compat alias — fallback is now built into chat_with_usage."""
        return self.chat_with_usage(model_cfg, system, user)
    
    # Keep backward-compat aliases if any Layer 2 modules use them directly
    def _call_groq(self, cfg, system, user) -> str:
        text, _ = self._call_groq_with_usage(cfg, system, user)
        return text

    def _call_megallm(self, cfg, system, user) -> str:
        text, _ = self._call_megallm_with_usage(cfg, system, user)
        return text

    def _call_deepseek(self, cfg, system, user) -> str:
        text, _ = self._call_deepseek_with_usage(cfg, system, user)
        return text

    def _call_alibaba(self, cfg, system, user) -> str:
        text, _ = self._call_alibaba_with_usage(cfg, system, user)
        return text
