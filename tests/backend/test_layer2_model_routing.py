"""Layer 2 model routing and quota fallback (src/backend/workflow/layer2/utils/{model_router,llm_client}.py)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

LAYER2 = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer2"
if str(LAYER2) not in sys.path:
    sys.path.insert(0, str(LAYER2))

import pytest

from common.config import ModelConfig
from common.llm.llm_client import MaxRetriesExceeded
from utils import llm_client, model_router

QUOTA_ERROR = "Error code: 403 - {'error': {'code': 'AllocationQuota.FreeTierOnly'}}"


def _cfg(model_id: str) -> ModelConfig:
    return ModelConfig(provider="alibaba", model_id=model_id)


@pytest.fixture()
def fake_models(monkeypatch):
    """Chain a → [missing, b, c, d]; 'missing' is not an available model."""
    models = {mid: _cfg(mid) for mid in ("a", "b", "c", "d")}
    monkeypatch.setattr(model_router, "AVAILABLE_MODELS", models)
    monkeypatch.setattr(model_router, "FALLBACK_CHAIN", {"a": ["missing", "b", "c", "d"], "b": ["a"]})
    return models


def test_fallback_returns_first_available_untried(fake_models):
    assert model_router.get_fallback_model("a").model_id == "b"
    assert model_router.get_fallback_model("a", frozenset({"a", "b"})).model_id == "c"
    assert model_router.get_fallback_model("a", {"a", "b", "c", "d"}) is None
    assert model_router.get_fallback_model("unknown") is None


def test_chat_walks_the_whole_chain_on_quota(fake_models, monkeypatch):
    calls = []

    def fake_base_chat(self, cfg, system, user):
        calls.append(cfg.model_id)
        if cfg.model_id in ("a", "b", "c"):
            raise RuntimeError(QUOTA_ERROR)
        return "ok", {"input_tokens": 1, "output_tokens": 1}

    monkeypatch.setattr(llm_client.CommonLLMClient, "chat_with_usage", fake_base_chat)
    text, _ = llm_client.LLMClient().chat_with_usage(fake_models["a"], "sys", "user")
    assert text == "ok"
    # b's own chain points back to a; the walk follows a's chain, so it reaches c and d
    assert calls == ["a", "b", "c", "d"]


def test_chat_raises_when_chain_exhausted(fake_models, monkeypatch):
    def always_quota(self, cfg, system, user):
        raise RuntimeError(QUOTA_ERROR)

    monkeypatch.setattr(llm_client.CommonLLMClient, "chat_with_usage", always_quota)
    with pytest.raises(RuntimeError, match="FreeTierOnly"):
        llm_client.LLMClient().chat_with_usage(fake_models["a"], "sys", "user")


def test_non_quota_errors_do_not_fall_back(fake_models, monkeypatch):
    calls = []

    def server_error(self, cfg, system, user):
        calls.append(cfg.model_id)
        raise RuntimeError("Error code: 500 - internal")

    monkeypatch.setattr(llm_client.CommonLLMClient, "chat_with_usage", server_error)
    with pytest.raises(RuntimeError, match="500"):
        llm_client.LLMClient().chat_with_usage(fake_models["a"], "sys", "user")
    assert calls == ["a"]


class _RawCall:
    """Stands in for the undecorated base DashScope call."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, client, cfg, system, user):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture()
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(llm_client.time, "sleep", recorded.append)
    return recorded


def _patch_raw_call(monkeypatch, raw):
    monkeypatch.setattr(llm_client.CommonLLMClient._call_alibaba_with_usage, "__wrapped__", raw)


def test_alibaba_quota_error_fails_fast(monkeypatch, sleeps):
    raw = _RawCall([RuntimeError(QUOTA_ERROR)])
    _patch_raw_call(monkeypatch, raw)
    with pytest.raises(RuntimeError, match="FreeTierOnly"):
        llm_client.LLMClient()._call_alibaba_with_usage(_cfg("a"), "sys", "user")
    assert raw.calls == 1
    assert sleeps == []


def test_alibaba_transient_errors_are_retried(monkeypatch, sleeps):
    raw = _RawCall([RuntimeError("timeout"), RuntimeError("timeout"), ("ok", {})])
    _patch_raw_call(monkeypatch, raw)
    assert llm_client.LLMClient()._call_alibaba_with_usage(_cfg("a"), "sys", "user") == ("ok", {})
    assert raw.calls == 3
    assert sleeps == [2.0, 4.0]


def test_alibaba_gives_up_after_three_attempts(monkeypatch, sleeps):
    raw = _RawCall([RuntimeError("timeout")] * 3)
    _patch_raw_call(monkeypatch, raw)
    with pytest.raises(MaxRetriesExceeded, match="timeout"):
        llm_client.LLMClient()._call_alibaba_with_usage(_cfg("a"), "sys", "user")
    assert raw.calls == 3


def test_select_model_prefers_known_explicit_model():
    known = next(iter(model_router.AVAILABLE_MODELS))
    assert model_router.select_model(model_id=known, stage="production") is model_router.AVAILABLE_MODELS[known]


def test_select_model_routes_by_stage_and_complexity():
    assert model_router.select_model(stage="dev") is model_router.DEV_MODEL
    assert model_router.select_model(stage="pilot") is model_router.PILOT_MODEL
    for level in ("critical", "high", "medium", "low"):
        assert model_router.select_model(level, stage="production") is model_router.PRODUCTION_ROUTING[level]
    assert model_router.select_model("bogus", stage="production") is model_router.PRODUCTION_ROUTING["low"]


def test_select_model_warns_on_unknown_model(monkeypatch, caplog):
    monkeypatch.setattr(model_router, "_warned_substitutions", set())
    with caplog.at_level(logging.WARNING, logger=model_router.__name__):
        chosen = model_router.select_model(model_id="no-such-model", stage="dev")
        model_router.select_model(model_id="no-such-model", stage="dev")
    assert chosen is model_router.DEV_MODEL
    warnings = [r.getMessage() for r in caplog.records if "no-such-model" in r.getMessage()]
    assert len(warnings) == 1
    assert chosen.model_id in warnings[0]
