"""
common/config.py — Consolidated configuration module for the backend.
Loads config.json from the workspace root and environment variables.
"""
from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────
COMMON_DIR = Path(__file__).resolve().parent
BACKEND_DIR = COMMON_DIR.parent

# Robustly find workspace root containing config.json by climbing up
_curr = COMMON_DIR
WORKSPACE_DIR = BACKEND_DIR.parent
for _ in range(5):
    if (_curr / "config.json").exists():
        WORKSPACE_DIR = _curr
        break
    _curr = _curr.parent

# ── Load environment variables (.env) ──────────────────────
try:
    from dotenv import load_dotenv
    # Load from common/.env
    load_dotenv(dotenv_path=COMMON_DIR / ".env")
    # Load from backend/.env
    load_dotenv(dotenv_path=BACKEND_DIR / ".env")
    # Load from workspace root/.env
    load_dotenv(dotenv_path=WORKSPACE_DIR / ".env")
except ImportError:
    pass

# ── Load config.json ──────────────────────────────────────
CONFIG_FILE = Path("config.json")
if not CONFIG_FILE.exists():
    CONFIG_FILE = WORKSPACE_DIR / "config.json"

config_data: dict = {}
if CONFIG_FILE.exists():
    try:
        config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Failed to parse config.json at {CONFIG_FILE}: {e}")

# ── Configuration Resolvers ───────────────────────────────
def get_setting(env_key: str, json_path: list[str] | None = None, default: str = "") -> str:
    """
    Helper to resolve a configuration setting.
    1. Check system environment variables or loaded .env
    2. Check config.json using a path list (e.g. ["llm_providers", "openai", "api_key"])
    3. Return default
    """
    val = os.getenv(env_key)
    if val is not None:
        return val
    
    if json_path:
        curr = config_data
        for key in json_path:
            if isinstance(curr, dict) and key in curr:
                curr = curr[key]
            else:
                return default
        return str(curr)
        
    return default

# ── Stage ──────────────────────────────────────────────────
STAGE = os.getenv("L2_STAGE", os.getenv("STAGE", "dev"))

# ── API Keys ───────────────────────────────────────────────
OPENAI_API_KEY = get_setting("OPENAI_API_KEY", ["llm_providers", "openai", "api_key"])
ANTHROPIC_API_KEY = get_setting("ANTHROPIC_API_KEY", ["llm_providers", "anthropic", "api_key"])
DEEPSEEK_API_KEY = get_setting("DEEPSEEK_API_KEY", ["llm_providers", "deepseek", "api_key"])
ALIBABA_API_KEY = get_setting("ALIBABA_API_KEY", ["llm_providers", "alibaba", "api_key"])
GROQ_API_KEY = get_setting("GROQ_API_KEY", ["llm_providers", "groq", "api_key"])
MEGALLM_API_KEY = get_setting("MEGALLM_API_KEY", ["llm_providers", "megallm", "api_key"])

# ── Database Configurations ────────────────────────────────
_mongo_cfg = config_data.get("mongodb", {})
MONGO_URI = os.getenv("MONGO_URI", _mongo_cfg.get("uri", "mongodb://localhost:27017"))
MONGO_DB = os.getenv("MONGO_DB", _mongo_cfg.get("db", "vba_brain_core"))

_pg_cfg = config_data.get("postgresql", {})
POSTGRES_CONN = os.getenv(
    "POSTGRES_CONN",
    _pg_cfg.get(
        "connection_string",
        f"Host={_pg_cfg.get('host', 'localhost')};Port={_pg_cfg.get('port', 5432)};Database={_pg_cfg.get('database', 'vba_brain')};Username={_pg_cfg.get('username', 'vba_brain')};Password={_pg_cfg.get('password', '')}"
    )
)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", _pg_cfg.get("host", "localhost"))
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", str(_pg_cfg.get("port", 5432))))
POSTGRES_DB   = os.getenv("POSTGRES_DB", _pg_cfg.get("database", "vba_brain"))
POSTGRES_USER = os.getenv("POSTGRES_USER", _pg_cfg.get("username", "vba_brain"))
POSTGRES_PASS = os.getenv("POSTGRES_PASSWORD", _pg_cfg.get("password", ""))

# ── Localization ───────────────────────────────────────────
SOURCE_LANGUAGE = get_setting("SOURCE_LANGUAGE", ["localization", "source_language"], "ja")
TARGET_LANGUAGE = get_setting("TARGET_LANGUAGE", ["localization", "target_language"], "en")

# ── Default LLM Models ─────────────────────────────────────
_llm_cfg = config_data.get("llm_settings", {})
DEFAULT_MODEL_NAME = get_setting("DEFAULT_LLM_MODEL", ["llm_settings", "default_model"], "qwen-max")
LAYER2_DEV_MODEL_NAME = get_setting("LAYER2_DEV_MODEL", ["llm_settings", "layer2_dev_model"], "qwen-max")
LAYER2_PILOT_MODEL_NAME = get_setting("LAYER2_PILOT_MODEL", ["llm_settings", "layer2_pilot_model"], "qwen-max")
LAYER4_MIGRATION_MODEL_NAME = get_setting("LAYER4_MIGRATION_MODEL", ["llm_settings", "layer4_migration_model"], "qwen-max")
LAYER3_MIGRATION_MODEL_NAME = get_setting("LAYER3_MIGRATION_MODEL", ["llm_settings", "layer3_migration_model"], "qwen-max")
LAYER5_DEFAULT_MODEL_NAME = get_setting("LAYER5_DEFAULT_MODEL", ["llm_settings", "layer5_default_model"], "qwen3-coder-480b-a35b-instruct")
LAYER5_SERVICE_MODEL_NAME = get_setting("LAYER5_SERVICE_MODEL", ["llm_settings", "layer5_service_model"], "qwen3-coder-480b-a35b-instruct")
LAYER5_VIEWMODEL_MODEL_NAME = get_setting("LAYER5_VIEWMODEL_MODEL", ["llm_settings", "layer5_viewmodel_model"], "qwen-plus-2025-07-28")
LAYER5_REPOSITORY_MODEL_NAME = get_setting("LAYER5_REPOSITORY_MODEL", ["llm_settings", "layer5_repository_model"], "qwen3-coder-480b-a35b-instruct")

# ── Model Definitions ──────────────────────────────────────
@dataclass
class ModelConfig:
    provider: str
    model_id: str
    max_tokens: int = 8192
    temperature: float = 0.1
    context_window: int = 131072
    description: str = ""

# Define all standard models
QWEN3_CODER_PLUS = ModelConfig(
    provider="alibaba",
    model_id="qwen3-coder-plus",
    max_tokens=16384,
    temperature=0.1,
    context_window=262144,
    description="Flagship Qwen3 coder — complex logic, Service/ViewModel gen",
)

QWEN3_CODER_480B = ModelConfig(
    provider="alibaba",
    model_id="qwen3-coder-480b-a35b-instruct",
    max_tokens=16384,
    temperature=0.1,
    context_window=262144,
    description="480B MoE (35B active) — heavyweight reasoning, Repository SQL gen",
)

QWEN3_CODER_NEXT = ModelConfig(
    provider="alibaba",
    model_id="qwen3-coder-next",
    max_tokens=16384,
    temperature=0.1,
    context_window=262144,
    description="80B MoE (3B active) — fast/cheap, DTO/Mapper/simple gen",
)

QWEN3_235B = ModelConfig(
    provider="alibaba",
    model_id="qwen3-235b-a22b-instruct-2507",
    max_tokens=16384,
    temperature=0.1,
    context_window=262144,
    description="235B MoE (22B active) — mid-tier reasoning, Service/ViewModel gen",
)

QWEN_MAX = ModelConfig(
    provider="alibaba",
    model_id="qwen-max",
    max_tokens=8192,
    temperature=0.1,
)

QWEN3_VL_235B = ModelConfig(
    provider="alibaba",
    model_id="qwen3-vl-235b-a22b-thinking",
    max_tokens=8192,
    temperature=0.1,
)

QWEN_VL_PLUS = ModelConfig(
    provider="alibaba",
    model_id="qwen-vl-plus-latest",
    max_tokens=16000,
    temperature=0.1,
)

QVQ_MAX = ModelConfig(
    provider="alibaba",
    model_id="qvq-max-2025-03-25",
    max_tokens=8192,
    temperature=0.1,
)

QWEN_PLUS_20250728 = ModelConfig(
    provider="alibaba",
    model_id="qwen-plus-2025-07-28",
    max_tokens=16000,
    context_window=262144,
    temperature=0.1,
)

QWEN3_VL_30B = ModelConfig(
    provider="alibaba",
    model_id="qwen3-vl-30b-a3b-thinking",
    max_tokens=16000,
    temperature=0.1,
)

AVAILABLE_MODELS: dict[str, ModelConfig] = {
    QWEN3_CODER_PLUS.model_id: QWEN3_CODER_PLUS,
    QWEN3_CODER_480B.model_id: QWEN3_CODER_480B,
    QWEN3_CODER_NEXT.model_id: QWEN3_CODER_NEXT,
    QWEN3_235B.model_id: QWEN3_235B,
    QWEN_MAX.model_id: QWEN_MAX,
    QWEN3_VL_235B.model_id: QWEN3_VL_235B,
    QWEN_VL_PLUS.model_id: QWEN_VL_PLUS,
    QVQ_MAX.model_id: QVQ_MAX,
    QWEN_PLUS_20250728.model_id: QWEN_PLUS_20250728,
    QWEN3_VL_30B.model_id: QWEN3_VL_30B,
    # Additional models for fallback chain coverage
    "qwen-max-latest":                  ModelConfig(provider="alibaba", model_id="qwen-max-latest",                  max_tokens=8192,  temperature=0.1),
    "qwen-plus":                        ModelConfig(provider="alibaba", model_id="qwen-plus",                        max_tokens=8192,  temperature=0.1),
    "qwen-plus-latest":                 ModelConfig(provider="alibaba", model_id="qwen-plus-latest",                 max_tokens=8192,  temperature=0.1),
    "qwen-plus-2025-09-11":             ModelConfig(provider="alibaba", model_id="qwen-plus-2025-09-11",             max_tokens=8192,  temperature=0.1),
    "qwen-plus-2025-12-01":             ModelConfig(provider="alibaba", model_id="qwen-plus-2025-12-01",             max_tokens=8192,  temperature=0.1),
    "qwen-turbo":                       ModelConfig(provider="alibaba", model_id="qwen-turbo",                       max_tokens=8192,  temperature=0.1),
    "qwen-turbo-latest":                ModelConfig(provider="alibaba", model_id="qwen-turbo-latest",                max_tokens=8192,  temperature=0.1),
    "qwen-flash":                       ModelConfig(provider="alibaba", model_id="qwen-flash",                       max_tokens=8192,  temperature=0.1),
    "qwen-flash-latest":                ModelConfig(provider="alibaba", model_id="qwen-flash-latest",                max_tokens=8192,  temperature=0.1),
    "qwen3-max":                        ModelConfig(provider="alibaba", model_id="qwen3-max",                        max_tokens=16384, temperature=0.1, context_window=262144),
    "qwen3.5-plus":                     ModelConfig(provider="alibaba", model_id="qwen3.5-plus",                     max_tokens=16384, temperature=0.1, context_window=1048576),
    "qwen3.5-flash":                    ModelConfig(provider="alibaba", model_id="qwen3.5-flash",                    max_tokens=8192,  temperature=0.1, context_window=1048576),
    "qwen3-coder-flash":                ModelConfig(provider="alibaba", model_id="qwen3-coder-flash",                max_tokens=16384, temperature=0.1, context_window=1048576),
    "qwen3-coder-30b-a3b-instruct":     ModelConfig(provider="alibaba", model_id="qwen3-coder-30b-a3b-instruct",     max_tokens=16384, temperature=0.1, context_window=262144),
    "qwen3-235b-a22b":                  ModelConfig(provider="alibaba", model_id="qwen3-235b-a22b",                  max_tokens=16384, temperature=0.1, context_window=131072),
    "qwen3-235b-a22b-thinking-2507":    ModelConfig(provider="alibaba", model_id="qwen3-235b-a22b-thinking-2507",    max_tokens=16384, temperature=0.1, context_window=131072),
    "qwen3-32b":                        ModelConfig(provider="alibaba", model_id="qwen3-32b",                        max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen3-30b-a3b":                    ModelConfig(provider="alibaba", model_id="qwen3-30b-a3b",                    max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen3-30b-a3b-thinking-2507":      ModelConfig(provider="alibaba", model_id="qwen3-30b-a3b-thinking-2507",      max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen3-30b-a3b-instruct-2507":      ModelConfig(provider="alibaba", model_id="qwen3-30b-a3b-instruct-2507",      max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen3-14b":                        ModelConfig(provider="alibaba", model_id="qwen3-14b",                        max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen3-8b":                         ModelConfig(provider="alibaba", model_id="qwen3-8b",                         max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen3-4b":                         ModelConfig(provider="alibaba", model_id="qwen3-4b",                         max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen3-next-80b-a3b-thinking":      ModelConfig(provider="alibaba", model_id="qwen3-next-80b-a3b-thinking",      max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen3-next-80b-a3b-instruct":      ModelConfig(provider="alibaba", model_id="qwen3-next-80b-a3b-instruct",      max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwq-plus":                         ModelConfig(provider="alibaba", model_id="qwq-plus",                         max_tokens=8192,  temperature=0.1, context_window=131072),
    "qwen-vl-max":                      ModelConfig(provider="alibaba", model_id="qwen-vl-max",                      max_tokens=8192,  temperature=0.1),
    "qwen-vl-max-latest":               ModelConfig(provider="alibaba", model_id="qwen-vl-max-latest",               max_tokens=8192,  temperature=0.1),
    "qwen-vl-plus":                     ModelConfig(provider="alibaba", model_id="qwen-vl-plus",                     max_tokens=8192,  temperature=0.1),
    "qwen3-vl-plus":                    ModelConfig(provider="alibaba", model_id="qwen3-vl-plus",                    max_tokens=8192,  temperature=0.1, context_window=262144),
    "qwen3-vl-flash":                   ModelConfig(provider="alibaba", model_id="qwen3-vl-flash",                   max_tokens=8192,  temperature=0.1, context_window=262144),
    "qwen-math-plus":                   ModelConfig(provider="alibaba", model_id="qwen-math-plus",                   max_tokens=4096,  temperature=0.1),
    "qwen-math-plus-latest":            ModelConfig(provider="alibaba", model_id="qwen-math-plus-latest",            max_tokens=4096,  temperature=0.1),
    "qwen-math-turbo":                  ModelConfig(provider="alibaba", model_id="qwen-math-turbo",                  max_tokens=4096,  temperature=0.1),
    "qwen-mt-plus":                     ModelConfig(provider="alibaba", model_id="qwen-mt-plus",                     max_tokens=4096,  temperature=0.1),
    "qwen-mt-flash":                    ModelConfig(provider="alibaba", model_id="qwen-mt-flash",                    max_tokens=4096,  temperature=0.1),
    "qwen-mt-lite":                     ModelConfig(provider="alibaba", model_id="qwen-mt-lite",                     max_tokens=4096,  temperature=0.1),
}

# ── Dynamic Model Helper ───────────────────────────────────
def get_model(model_name_or_id: str, default: ModelConfig) -> ModelConfig:
    """
    Helper to resolve a model configuration.
    Allows overriding models dynamically via environment variables or config.json.
    """
    # 1. Check if model name/id is in environment overrides
    env_override_key = f"MODEL_OVERRIDE_{model_name_or_id.replace('-', '_').upper()}"
    env_val = os.getenv(env_override_key)
    if env_val and env_val in AVAILABLE_MODELS:
        return AVAILABLE_MODELS[env_val]
        
    # 2. Check if model name/id is in config.json overrides
    cfg_override = config_data.get("model_overrides", {}).get(model_name_or_id)
    if cfg_override and cfg_override in AVAILABLE_MODELS:
        return AVAILABLE_MODELS[cfg_override]
        
    # 3. Check if the input is directly an available model ID
    if model_name_or_id in AVAILABLE_MODELS:
        return AVAILABLE_MODELS[model_name_or_id]
        
    return default
