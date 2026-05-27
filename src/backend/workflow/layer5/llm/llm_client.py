"""
llm/llm_client.py — Layer 5 LLM Client wrapper importing from common.llm.llm_client.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure common is in sys.path
_LAYER5_DIR = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _LAYER5_DIR.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from common.llm.llm_client import (
    L5LLMClient,
    extract_code_block,
    parse_json_response,
)
