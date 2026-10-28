"""Configuration resolution order: env → config.json → default (src/backend/common/config.py)."""
from __future__ import annotations

import pytest

from common import config


@pytest.fixture()
def fake_config(monkeypatch):
    data = {
        "llm_settings": {"default_model": "from-json"},
        "llm_providers": {"alibaba": {"api_key": "json-key"}},
        "model_overrides": {"alias-model": "qwen-plus"},
    }
    monkeypatch.setattr(config, "config_data", data)
    return data


def test_env_beats_config_json(fake_config, monkeypatch):
    monkeypatch.setenv("UNIT_TEST_MODEL", "from-env")
    assert config.get_setting("UNIT_TEST_MODEL", ["llm_settings", "default_model"], "dflt") == "from-env"


def test_config_json_used_when_env_missing(fake_config, monkeypatch):
    monkeypatch.delenv("UNIT_TEST_MODEL", raising=False)
    assert config.get_setting("UNIT_TEST_MODEL", ["llm_settings", "default_model"], "dflt") == "from-json"


def test_default_when_path_missing(fake_config, monkeypatch):
    monkeypatch.delenv("UNIT_TEST_MODEL", raising=False)
    assert config.get_setting("UNIT_TEST_MODEL", ["llm_settings", "nope"], "dflt") == "dflt"
    assert config.get_setting("UNIT_TEST_MODEL", ["missing", "deeper"], "dflt") == "dflt"
    assert config.get_setting("UNIT_TEST_MODEL", None, "dflt") == "dflt"


def test_nested_provider_key(fake_config, monkeypatch):
    monkeypatch.delenv("UNIT_TEST_KEY", raising=False)
    assert config.get_setting("UNIT_TEST_KEY", ["llm_providers", "alibaba", "api_key"]) == "json-key"


def test_get_model_direct_id(fake_config):
    assert config.get_model("qwen-max", config.QWEN_PLUS_20250728) is config.QWEN_MAX


def test_get_model_unknown_falls_back_to_default(fake_config):
    assert config.get_model("does-not-exist", config.QWEN_MAX) is config.QWEN_MAX


def test_get_model_env_override(fake_config, monkeypatch):
    monkeypatch.setenv("MODEL_OVERRIDE_QWEN_MAX", "qwen3-coder-next")
    assert config.get_model("qwen-max", config.QWEN_MAX).model_id == "qwen3-coder-next"


def test_get_model_env_override_to_unknown_model_is_ignored(fake_config, monkeypatch):
    monkeypatch.setenv("MODEL_OVERRIDE_QWEN_MAX", "not-a-model")
    assert config.get_model("qwen-max", config.QWEN_PLUS_20250728) is config.QWEN_MAX


def test_get_model_config_json_override(fake_config, monkeypatch):
    monkeypatch.delenv("MODEL_OVERRIDE_ALIAS_MODEL", raising=False)
    assert config.get_model("alias-model", config.QWEN_MAX).model_id == "qwen-plus"


def test_models_listed_in_config_json_become_available(monkeypatch):
    registry = dict(config.AVAILABLE_MODELS)
    monkeypatch.setattr(config, "AVAILABLE_MODELS", registry)
    monkeypatch.setattr(config, "config_data", {"llm_providers": {
        "openai": {"models": ["gpt-4o", "qwen-max"]},
        "anthropic": {"models": ["claude-x"]},
        "someone-else": {"models": ["mystery-model"]},
    }})
    config._register_config_models()
    assert registry["gpt-4o"].provider == "openai"
    assert registry["claude-x"].provider == "anthropic"
    assert registry["qwen-max"] is config.QWEN_MAX, "built-in definitions keep precedence"
    assert "mystery-model" not in registry, "providers the client cannot call are ignored"


def test_redact_uri():
    assert config.redact_uri("mongodb://vba:s3cret@localhost:27017/db?authSource=admin") == (
        "mongodb://***@localhost:27017/db?authSource=admin"
    )
    assert config.redact_uri("mongodb://localhost:27017") == "mongodb://localhost:27017"
