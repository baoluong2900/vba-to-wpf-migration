"""
core/config.py — Layer 2 Configuration
Model env, stage, MongoDB connection settings.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

# Ensure common is in sys.path
_LAYER2_DIR = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _LAYER2_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Import unified configuration
from common.config import (
    STAGE as _COMMON_STAGE,
    MONGO_URI as _COMMON_MONGO_URI,
    MONGO_DB as _COMMON_MONGO_DB,
    MEGALLM_API_KEY,
    GROQ_API_KEY,
    ALIBABA_API_KEY,
    SOURCE_LANGUAGE,
    TARGET_LANGUAGE,
    ModelConfig,
    QWEN3_CODER_480B,
    QWEN3_CODER_NEXT,
    QWEN_MAX,
    QWEN3_VL_235B,
    QWEN_VL_PLUS,
    QVQ_MAX,
    QWEN_PLUS_20250728,
    QWEN3_VL_30B,
    AVAILABLE_MODELS,
    get_model,
    LAYER2_DEV_MODEL_NAME,
    LAYER2_PILOT_MODEL_NAME,
)

# ──────────────────────────────────────────────
# Stage
# ──────────────────────────────────────────────
from typing import Literal
Stage = Literal["dev", "pilot", "production"]
STAGE: Stage = _COMMON_STAGE  # type: ignore[assignment]

# ──────────────────────────────────────────────
# MongoDB
# ──────────────────────────────────────────────
MONGO_URI: str = _COMMON_MONGO_URI
MONGO_DB: str = _COMMON_MONGO_DB

# Collections produced by Layer 1
L1_COLLECTION_FORMS: str = "forms"
L1_COLLECTION_REPORTS: str = "reports"
L1_COLLECTION_MODULES: str = "modules"
L1_COLLECTION_QUERIES: str = "queries_v2"
L1_COLLECTION_TABLES: str = "tables"
L1_COLLECTION_MACROS: str = "macros"
L1_COLLECTION_GRAPH: str = "dependency_graph"

# ── Stage Assignment ──────────────────────────
# Dynamic model resolution for flexibility
DEV_MODEL: ModelConfig = get_model("l2-dev-model", AVAILABLE_MODELS.get(LAYER2_DEV_MODEL_NAME, QWEN_MAX))
PILOT_MODEL: ModelConfig = get_model("l2-pilot-model", AVAILABLE_MODELS.get(LAYER2_PILOT_MODEL_NAME, QWEN_MAX))

# production routing by complexity
PRODUCTION_ROUTING: dict[str, ModelConfig] = {
    "critical": get_model("l2-prod-critical", QWEN3_CODER_480B),
    "high":     get_model("l2-prod-high", QWEN3_CODER_480B),
    "medium":   get_model("l2-prod-medium", QWEN_MAX),
    "low":      get_model("l2-prod-low", QWEN3_CODER_NEXT),
}


# ──────────────────────────────────────────────
# Retry / validation settings
# ──────────────────────────────────────────────
MAX_RETRIES: int = 3

# ──────────────────────────────────────────────
# Output directories
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SCHEMA_TEMPLATE_DIR = os.path.join(BASE_DIR, "schema", "template")
SCHEMA_OUTPUT_DIR = os.path.join(BASE_DIR, "schema", "output")
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "logs")
