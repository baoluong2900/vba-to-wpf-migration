"""
core/config.py — Layer 5 Configuration
Model config, API keys, paths for Avalonia code-gen pipeline.

Reuse API key từ config.json chung (workflow/config.json) qua common config.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure backend root is in sys.path
_LAYER5_DIR  = Path(__file__).resolve().parent.parent          # .../core/ → layer5/
_BACKEND_DIR = _LAYER5_DIR.parent.parent                       # layer5 → workflow → backend/
_WORKFLOW_DIR = _LAYER5_DIR.parent.parent.parent.parent        # layer5 → workflow → backend → src → workflow/
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Import unified configuration
from common.config import (
    AVAILABLE_MODELS as _COMMON_AVAILABLE_MODELS,
    MONGO_URI as _COMMON_MONGO_URI,
    MONGO_DB as _COMMON_MONGO_DB,
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
LAYER4_INPUTS_DIR = LAYER5_DIR.parent / "layer4" / "inputs"          # BD_json/screen, DD_json/form
UI_EVENT_MAP_PATH = LAYER5_DIR / "agents" / "ui" / "configs" / "ui_event_map.json"   # F-ID registry
SERVICE_OUTPUTS_DIR = LAYER5_DIR / "agents" / "service" / "outputs"
SERVICE_CONTRACT_BACKUP_DIR = WORKFLOW_DIR / "data" / "database_json" / "agent_service"


def _find_avalonia_project_dir() -> Path:
    """Locate the Avalonia solution root by climbing until vba_brain.slnx is found.

    Robust against directory-depth changes (replaces fragile hand-counted
    .parent chains that previously drifted to orphan paths).
    """
    for base in (_LAYER5_DIR, *_LAYER5_DIR.parents):
        candidate = base / "src" / "wpf"
        if (candidate / "vba_brain.slnx").exists() or (candidate / "vba_brain.sln").exists():
            return candidate
    # Fallback: conventional location under the workflow root
    return WORKFLOW_DIR / "src" / "wpf"


# ── Source tree (single source of truth — import these, never recompute) ──
AVALONIA_PROJECT_DIR = _find_avalonia_project_dir()      # .../src/wpf (solution root)
UI_PROJECT_DIR = AVALONIA_PROJECT_DIR / "vba_brain.UI.Avalonia"
VIEWS_DIR = UI_PROJECT_DIR / "Views"
VIEWMODELS_DIR = UI_PROJECT_DIR / "ViewModels"
SERVICES_DIR = UI_PROJECT_DIR / "Services"
DOMAIN_PROJECT_DIR = AVALONIA_PROJECT_DIR / "vba_brain.Domain"
APPLICATION_PROJECT_DIR = AVALONIA_PROJECT_DIR / "vba_brain.Application"

# Back-compat alias (solution root) — used by file_writer / build_verify / orchestrator
vba_brain_PROJECT_DIR = AVALONIA_PROJECT_DIR

# ──────────────────────────────────────────────
# Localization (re-exported from common)
# ──────────────────────────────────────────────
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
COL_TABLES: str = os.getenv("MONGO_COL_TABLES", "tables")
COL_MODULES: str = os.getenv("MONGO_COL_MODULES", "modules")
COL_REPORTS: str = os.getenv("MONGO_COL_REPORTS", "reports")
# Layer 2 / Layer 5 — design / agent artifacts stored in the same MongoDB database
COL_BDS: str = os.getenv("MONGO_COL_BDS", "bds")
COL_DDS: str = os.getenv("MONGO_COL_DDS", "dds")
COL_AGENT_REPO: str = os.getenv("MONGO_COL_AGENT_REPO", "agent_repo")
COL_AGENT_SERVICE: str = os.getenv("MONGO_COL_AGENT_SERVICE", "agent_service")
COL_AGENT_GRAPHVIEW: str = os.getenv("MONGO_COL_AGENT_GRAPHVIEW", "agent_graphview")

# ── Dynamic Model Routing ──────────────────────
# Allow overriding models dynamically via environment variables or config.json
DEFAULT_MODEL: ModelConfig = get_model(LAYER5_DEFAULT_MODEL_NAME, QWEN3_CODER_480B)

L5_ROUTING = {
    # Heavy — cần suy luận logic phức tạp
    "service":    get_model(LAYER5_SERVICE_MODEL_NAME, QWEN3_CODER_480B),      # DD steps → C# business logic
    "viewmodel":  get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),    # MVVM commands + event flow
    "repository": get_model(LAYER5_REPOSITORY_MODEL_NAME, QWEN3_CODER_480B),      # SQL → Dapper code

    # Medium — cần reasoning nhưng pattern rõ ràng
    "view_xaml":  get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),    # Layout từ BD → XAML
    "validator":  get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),    # Business rules → FluentValidation

    # Light — Jinja2 handle, chỉ dùng LLM nếu cần custom logic
    "entity":     get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),    # Fallback nếu Jinja2 không đủ
    "dto":        get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),
    "mapper":     get_model(LAYER5_VIEWMODEL_MODEL_NAME, QWEN_PLUS_20250728),
}

# Available models for explicit selection (--model): everything Layers 2/3 resolve (incl. the
# config.json llm_providers.<p>.models list), with the Layer 5 entries below as overrides.
AVAILABLE_MODELS: dict[str, ModelConfig] = {
    **_COMMON_AVAILABLE_MODELS,
    QWEN3_CODER_PLUS.model_id: QWEN3_CODER_PLUS,
    QWEN3_CODER_480B.model_id: QWEN3_CODER_480B,
    QWEN3_CODER_NEXT.model_id: QWEN3_CODER_NEXT,
    QWEN3_235B.model_id: QWEN3_235B,
    QWEN_PLUS_20250728.model_id: QWEN_PLUS_20250728,
}

# ──────────────────────────────────────────────
# Output paths
# ──────────────────────────────────────────────
OUTPUT_DIR = LAYER5_DIR / "output"      # staging for generated files with no project mapping

# ──────────────────────────────────────────────
# Retry settings
# ──────────────────────────────────────────────
MAX_RETRIES: int = 3
