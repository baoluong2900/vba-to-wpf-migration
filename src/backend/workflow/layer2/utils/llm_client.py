"""
llm/llm_client.py — Layer 2 wrapper inheriting from the common LLMClient.
"""
from __future__ import annotations

import sys
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

class LLMClient(CommonLLMClient):
    """
    Layer 2 LLM Client wrapper. Inherits all features from common LLMClient.
    """
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
