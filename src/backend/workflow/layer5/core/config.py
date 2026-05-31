"""
core/config.py — Layer 5 Configuration
Model config, API keys, paths for WPF Code Gen pipeline.

Reuse API key từ config.json chung (workflow/config.json) qua common config.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

# Ensure backend root is in sys.path
_LAYER5_DIR  = Path(__file__).resolve().parent.parent          # .../core/ → layer5/
_BACKEND_DIR = _LAYER5_DIR.parent.parent                       # layer5 → workflow → backend/
_WORKFLOW_DIR = _LAYER5_DIR.parent.parent.parent.parent        # layer5 → workflow → backend → src → workflow/
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Import unified configuration
from common.config import (
    STAGE as _COMMON_STAGE,
    MONGO_URI as _COMMON_MONGO_URI,
    MONGO_DB as _COMMON_MONGO_DB,
    ALIBABA_API_KEY,
    SOURCE_LANGUAGE,
    TARGET_LANGUAGE,
    ModelConfig,
    QWEN3_CODER_PLUS,
    QWEN3_CODER_480B,
    QWEN3_CODER_NEXT,
    QWEN3_235B,
    QWEN_PLUS_20250728,
    LAYER5_DEFAULT_MODEL_NAME,
    LAYER5_SERVICE_MODEL_NAME,
    LAYER5_VIEWMODEL_MODEL_NAME,
    LAYER5_REPOSITORY_MODEL_NAME,
    get_model,
)

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
LAYER5_DIR = _LAYER5_DIR
WORKFLOW_DIR = _WORKFLOW_DIR
CONFIG_FILE = Path("config.json")
if not CONFIG_FILE.exists():
    CONFIG_FILE = WORKFLOW_DIR / "config.json"
vba_brain_PROJECT_DIR = WORKFLOW_DIR / "source"
if not vba_brain_PROJECT_DIR.exists():
    vba_brain_PROJECT_DIR = WORKFLOW_DIR / "src" / "wpf"

# ──────────────────────────────────────────────
# Localization
# ──────────────────────────────────────────────
# Re-exported from common
SOURCE_LANGUAGE = SOURCE_LANGUAGE
TARGET_LANGUAGE = TARGET_LANGUAGE

# ──────────────────────────────────────────────
# MongoDB (reuse config)
# ──────────────────────────────────────────────
MONGO_URI: str = _COMMON_MONGO_URI
MONGO_DB: str = _COMMON_MONGO_DB

# Collections (Layer 1 MongoDB — aligned with backend/layer2/core/config)
COL_FORMS: str = "forms"
COL_QUERIES: str = "queries_v2"
COL_MACROS: str = "macros"
COL_TABLES: str = "tables"
COL_GRAPH: str = "dependency_graph"
# Layer 5 — design / agent artifacts stored in the same MongoDB database
COL_DDS: str = os.getenv("MONGO_COL_DDS", "dds")
COL_AGENT_REPO: str = os.getenv("MONGO_COL_AGENT_REPO", "agent_repo")

# ── Dynamic Model Routing ──────────────────────
# Allow overriding models dynamically via environment variables or config.json
DEFAULT_MODEL: ModelConfig = get_model(LAYER5_DEFAULT_MODEL_NAME, QWEN3_CODER_480B)

L5_ROUTING = {
    # Heavy — cần suy luận logic phức tạp
    "service":    get_model(LAYER5_SERVICE_MODEL_NAME, QWEN3_CODER_480B),      # DD steps → C# business logic
    "viewmodel":  get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),    # MVVM commands + event flow
    "repository": get_model(LAYER5_REPOSITORY_MODEL_NAME, QWEN3_CODER_480B),      # Oracle SQL → Dapper code

    # Medium — cần reasoning nhưng pattern rõ ràng
    "view_xaml":  get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),    # Layout từ BD → XAML
    "validator":  get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),    # Business rules → FluentValidation

    # Light — Jinja2 handle, chỉ dùng LLM nếu cần custom logic
    "entity":     get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),    # Fallback nếu Jinja2 không đủ
    "dto":        get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),
    "mapper":     get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),
}

# Available models for explicit selection
AVAILABLE_MODELS: dict[str, ModelConfig] = {
    QWEN3_CODER_PLUS.model_id: QWEN3_CODER_PLUS,
    QWEN3_CODER_480B.model_id: QWEN3_CODER_480B,
    QWEN3_CODER_NEXT.model_id: QWEN3_CODER_NEXT,
    QWEN3_235B.model_id: QWEN3_235B,
    QWEN_PLUS_20250728.model_id: QWEN_PLUS_20250728,
}

# ──────────────────────────────────────────────
# Output paths
# ──────────────────────────────────────────────
OUTPUT_DIR = LAYER5_DIR / "output"
TEMPLATE_DIR = LAYER5_DIR / "codegen" / "templates"
LOG_DIR = LAYER5_DIR.parent.parent / "logs"

# ──────────────────────────────────────────────
# Retry settings
# ──────────────────────────────────────────────
MAX_RETRIES: int = 3
