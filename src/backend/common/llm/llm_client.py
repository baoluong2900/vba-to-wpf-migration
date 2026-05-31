"""
common/llm/llm_client.py — Unified Multi-provider LLM Wrapper and utilities.
Supports: Google Gemini / Anthropic Claude / OpenAI GPT / DeepSeek / Alibaba DashScope / Groq / Ollama.
"""
from __future__ import annotations

import os
import json
import time
import logging
import functools
from typing import Any, Callable, TypeVar

from common.config import (
    MEGALLM_API_KEY,
    GROQ_API_KEY,
    DEEPSEEK_API_KEY,
    ALIBABA_API_KEY,
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    ModelConfig,
)

logger = logging.getLogger(__name__)

# ── Retry Decorator ──────────────────────────────────────────────────────────
F = TypeVar("F", bound=Callable)

class MaxRetriesExceeded(Exception):
    """Raised when all retry attempts are exhausted."""

def retry(max_attempts: int = 3, initial_delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator: retry function on exception with exponential backoff.
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exc: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        logger.warning(
                            "[retry] %s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                            fn.__qualname__, attempt, max_attempts, exc, delay,
                        )
                        time.sleep(delay)
                        delay *= backoff
                    else:
                        logger.error(
                            "[retry] %s failed after %d attempts: %s",
                            fn.__qualname__, max_attempts, exc,
                        )

            raise MaxRetriesExceeded(
                f"{fn.__qualname__} failed after {max_attempts} attempts. "
                f"Last error: {last_exc}"
            ) from last_exc
        return wrapper  # type: ignore[return-value]
    return decorator


# ── Unified LLM Client ────────────────────────────────────────────────────────
class LLMClient:
    """Thin wrapper around multiple LLM providers with automatic retry and token usage tracking."""

    def __init__(self, api_key: str | None = None, provider: str | None = None):
        self._api_key = api_key
        self._provider = provider
        self._usage_callbacks: list[Callable[[ModelConfig, dict, dict], None]] = []

    def register_usage_callback(self, cb: Callable[[ModelConfig, dict, dict], None]) -> None:
        """Register a callback for token usage tracking."""
        self._usage_callbacks.append(cb)

    def chat(self, model_cfg: ModelConfig, system: str, user: str) -> str:
        """
        Send a system+user prompt and return the raw response text.
        Dispatches to the correct provider backend.
        """
        text, _ = self.chat_with_usage(model_cfg, system, user)
        return text

    def chat_with_usage(
        self, model_cfg: ModelConfig, system: str, user: str
    ) -> tuple[str, dict]:
        """
        Send a system+user prompt and return the raw response text along with usage info.
        Returns: (response_text, {"input_tokens": int, "output_tokens": int})
        """
        logger.info(
            "[LLM] provider=%s model=%s tokens=%d",
            model_cfg.provider, model_cfg.model_id, model_cfg.max_tokens,
        )
        provider = model_cfg.provider

        if provider == "megallm":
            text, usage = self._call_megallm_with_usage(model_cfg, system, user)
        elif provider == "groq":
            text, usage = self._call_groq_with_usage(model_cfg, system, user)
        elif provider == "deepseek":
            text, usage = self._call_deepseek_with_usage(model_cfg, system, user)
        elif provider == "alibaba":
            text, usage = self._call_alibaba_with_usage(model_cfg, system, user)
        elif provider == "anthropic":
            text, usage = self._call_anthropic_with_usage(model_cfg, system, user)
        elif provider == "openai":
            text, usage = self._call_openai_with_usage(model_cfg, system, user)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        # Execute registered callbacks (e.g. L5LLMClient.layer5_callback)
        meta = {"system": system, "user": user}
        has_callbacks = bool(self._usage_callbacks)
        for cb in self._usage_callbacks:
            try:
                cb(model_cfg, usage, meta)
            except Exception as e:
                logger.debug("Usage callback error: %s", e)

        # Auto-track only when no specific callback handled it (avoids duplicate records)
        if not has_callbacks:
            self._auto_track_usage(model_cfg, usage)

        return text, usage

    def _auto_track_usage(self, model_cfg: ModelConfig, usage: dict) -> None:
        """Dynamically detect and report to Layer 2 and Layer 5 cost/token trackers if present."""
        # Layer 5 Token Tracker Integration
        try:
            from llm.token_tracker import get_tracker as get_l5_tracker
            l5_tracker = get_l5_tracker()
            if l5_tracker:
                l5_tracker.record(
                    form_name="unknown",
                    agent="unknown",
                    task_type="chat",
                    model_id=model_cfg.model_id,
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                )
        except Exception:
            pass

        # Layer 2 Cost Tracker Integration
        try:
            from llm.cost_tracker import get_tracker as get_l2_tracker
            l2_tracker = get_l2_tracker()
            if l2_tracker:
                l2_tracker.record(
                    item_name="unknown",
                    model_id=model_cfg.model_id,
                    stage="unknown",
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    flow_type="chat"
                )
        except Exception:
            pass

    def _get_usage(self, resp: Any, system: str, user: str) -> dict:
        """Extract token counts from an OpenAI-compatible response object, with fallback estimation."""
        usage = getattr(resp, "usage", None)
        if not usage and isinstance(resp, dict):
            usage = resp.get("usage")
        
        input_tok = 0
        output_tok = 0

        if usage:
            if hasattr(usage, "prompt_tokens"):
                input_tok = getattr(usage, "prompt_tokens", 0)
                output_tok = getattr(usage, "completion_tokens", 0)
            elif isinstance(usage, dict):
                input_tok = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                output_tok = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        
        # Fallback estimation if API returned 0
        if input_tok == 0:
            input_tok = (len(system) + len(user)) // 4
        if output_tok == 0:
            content = ""
            if hasattr(resp, "choices") and len(resp.choices) > 0:
                content = resp.choices[0].message.content or ""
            elif isinstance(resp, dict) and "choices" in resp:
                content = resp["choices"][0].get("message", {}).get("content", "")
            output_tok = len(content) // 4
            
        return {"input_tokens": input_tok, "output_tokens": output_tok}

    # ──────────────────────────────────────────────────────────────────────
    # Groq (Extreme low-latency)
    # ──────────────────────────────────────────────────────────────────────
    @retry(max_attempts=5, initial_delay=5.0, backoff=2.0)
    def _call_groq_with_usage(self, cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        from groq import Groq  # type: ignore[import]
        api_key = self._api_key or GROQ_API_KEY
        client = Groq(api_key=api_key, timeout=120.0)
        resp = client.chat.completions.create(
            model=cfg.model_id,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or "", self._get_usage(resp, system, user)

    # ──────────────────────────────────────────────────────────────────────
    # MegaLLM (OpenAI-compatible)
    # ──────────────────────────────────────────────────────────────────────
    @retry(max_attempts=3, initial_delay=2.0)
    def _call_megallm_with_usage(self, cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        from openai import OpenAI  # type: ignore[import]
        api_key = self._api_key or MEGALLM_API_KEY
        client = OpenAI(
            api_key=api_key,
            base_url="https://ai.megallm.io/v1",
        )
        resp = client.chat.completions.create(
            model=cfg.model_id,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or "", self._get_usage(resp, system, user)

    # ──────────────────────────────────────────────────────────────────────
    # DeepSeek
    # ──────────────────────────────────────────────────────────────────────
    @retry(max_attempts=3, initial_delay=2.0)
    def _call_deepseek_with_usage(self, cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        from openai import OpenAI  # type: ignore[import]
        api_key = self._api_key or DEEPSEEK_API_KEY
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        resp = client.chat.completions.create(
            model=cfg.model_id,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}}
        )
        return resp.choices[0].message.content or "", self._get_usage(resp, system, user)

    # ──────────────────────────────────────────────────────────────────────
    # Alibaba Cloud (DashScope)
    # ──────────────────────────────────────────────────────────────────────
    # qwen3 open-source models require enable_thinking=False
    _QWEN3_THINKING_MODELS = {
        "qwen3-32b", "qwen3-30b-a3b", "qwen3-14b", "qwen3-8b", "qwen3-4b", "qwen3-1.7b", "qwen3-0.6b",
    }

    @retry(max_attempts=3, initial_delay=2.0)
    def _call_alibaba_with_usage(self, cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        from openai import OpenAI  # type: ignore[import]
        api_key = self._api_key or ALIBABA_API_KEY
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        extra = {"enable_thinking": False} if cfg.model_id in self._QWEN3_THINKING_MODELS else {}
        resp = client.chat.completions.create(
            model=cfg.model_id,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **({"extra_body": extra} if extra else {}),
        )
        return resp.choices[0].message.content or "", self._get_usage(resp, system, user)

    # ──────────────────────────────────────────────────────────────────────
    # Anthropic (Claude)
    # ──────────────────────────────────────────────────────────────────────
    @retry(max_attempts=3, initial_delay=2.0)
    def _call_anthropic_with_usage(self, cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        import anthropic  # type: ignore[import]
        api_key = self._api_key or ANTHROPIC_API_KEY
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=cfg.model_id,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            system=system,
            messages=[
                {"role": "user", "content": user},
            ],
        )
        content = ""
        for block in resp.content:
            if hasattr(block, "text"):
                content += block.text
        
        usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }
        return content, usage

    # ──────────────────────────────────────────────────────────────────────
    # OpenAI (GPT / Codex)
    # ──────────────────────────────────────────────────────────────────────
    @retry(max_attempts=3, initial_delay=2.0)
    def _call_openai_with_usage(self, cfg: ModelConfig, system: str, user: str) -> tuple[str, dict]:
        from openai import OpenAI  # type: ignore[import]
        api_key = self._api_key or OPENAI_API_KEY
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=cfg.model_id,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or "", self._get_usage(resp, system, user)


# ── Layer 5 Client Compatible Subclass ───────────────────────────────────────
class L5LLMClient(LLMClient):
    """
    Subclass that provides Layer 5 specific generate_code method.
    """
    def __init__(self, api_key: str | None = None):
        super().__init__(api_key=api_key, provider="alibaba")

    def generate_code(
        self,
        task_type: str,
        system_prompt: str,
        user_prompt: str,
        model: ModelConfig | None = None,
        agent: str = "unknown",
        form_name: str = "",
    ) -> str:
        # Import dynamically here to avoid circular dependencies
        try:
            from core.config import L5_ROUTING, DEFAULT_MODEL
            cfg = model or L5_ROUTING.get(task_type, DEFAULT_MODEL)
        except Exception:
            # Fallback
            cfg = model
            if not cfg:
                raise ValueError("Model configuration not provided and fallback lookup failed.")

        logger.info(
            "[L5-LLM] 🚀 [%s/%s] task=%s model=%s max_tokens=%d",
            form_name or "?", agent, task_type, cfg.model_id, cfg.max_tokens,
        )

        # Build usage metadata callback hook
        def layer5_callback(model_cfg, usage, meta):
            try:
                from llm.token_tracker import get_tracker
                get_tracker().record(
                    form_name=form_name or "unknown",
                    agent=agent,
                    task_type=task_type or "unknown",
                    model_id=model_cfg.model_id,
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                )
            except Exception as track_err:
                logger.debug("[L5-LLM] Token tracking error (non-fatal): %s", track_err)

        self.register_usage_callback(layer5_callback)
        content = self.chat(cfg, system_prompt, user_prompt)
        
        # Clear the callback to avoid memory accumulation or duplicate callbacks next time
        self._usage_callbacks.clear()
        
        return content


# ── Utilities ────────────────────────────────────────────────────────────────
import re as _re

def extract_code_block(raw: str, language: str = "csharp") -> str:
    """
    Extract code from markdown fence.
    Input:  ```csharp\\n...code...\\n```
    Output: ...code...
    """
    lines = raw.strip().splitlines()

    # Find opening fence
    start = -1
    end = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") and start == -1:
            start = i + 1
        elif stripped == "```" and start != -1:
            end = i
            break

    if start == -1:
        # No fence — return as-is
        return raw.strip()

    return "\n".join(lines[start:end]).strip()


def parse_json_response(raw: str) -> dict[str, Any]:
    """
    Extract JSON from LLM response text robustly.
    """
    text = raw.strip()

    # 1. Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        text = inner.strip()

    # 2. Find outermost { ... } block using brace-matching
    def extract_json_block(s: str) -> str | None:
        depth = 0
        start = None
        for i, ch in enumerate(s):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    return s[start:i + 1]
        # Truncated: return everything from start even if unclosed
        if start is not None and depth > 0:
            return s[start:]
        return None

    def repair_truncated_json(s: str) -> str:
        """
        Repair a truncated JSON string by finding the last complete value
        and closing all open structures after it.
        """
        last_safe = -1
        depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(s):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ('{', '['):
                depth += 1
            elif ch in ('}', ']'):
                depth -= 1
                if depth >= 1:  # closed a nested item (still inside parent)
                    last_safe = i
        
        if last_safe > 0:
            truncated = s[:last_safe + 1].rstrip(',').rstrip()
        else:
            tl_depth = 0
            tl_in_str = False
            tl_esc = False
            last_tl_comma = -1
            for i2, ch in enumerate(s):
                if tl_esc: tl_esc = False; continue
                if ch == '\\' and tl_in_str: tl_esc = True; continue
                if ch == '"': tl_in_str = not tl_in_str; continue
                if tl_in_str: continue
                if ch in ('{', '['): tl_depth += 1
                elif ch in ('}', ']'): tl_depth -= 1
                elif ch == ',' and tl_depth == 1:
                    last_tl_comma = i2
            if last_tl_comma > 0:
                truncated = s[:last_tl_comma].rstrip()
            else:
                truncated = s.rstrip(',').rstrip()

        stack2 = []
        in_str2 = False
        esc2 = False
        for ch in truncated:
            if esc2: esc2 = False; continue
            if ch == '\\' and in_str2: esc2 = True; continue
            if ch == '"': in_str2 = not in_str2; continue
            if in_str2: continue
            if ch == '{': stack2.append('}')
            elif ch == '[': stack2.append(']')
            elif ch in ('}', ']'):
                if stack2 and stack2[-1] == ch: stack2.pop()
        
        for closer in reversed(stack2):
            truncated += closer
        return truncated

    def sanitize_newlines_in_strings(s: str) -> str:
        """
        Replace literal newlines/tabs inside JSON string values with escaped versions.
        """
        result = []
        in_string = False
        escape_next = False
        for ch in s:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == '\\' and in_string:
                result.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == '\n':
                    result.append('\\n')
                    continue
                if ch == '\r':
                    result.append('\\r')
                    continue
                if ch == '\t':
                    result.append('\\t')
                    continue
            result.append(ch)
        return ''.join(result)

    json_block = extract_json_block(text)
    if json_block:
        try:
            result = json.loads(json_block, object_pairs_hook=lambda pairs: dict(pairs))
            return result
        except json.JSONDecodeError:
            try:
                sanitized = sanitize_newlines_in_strings(json_block)
                result = json.loads(sanitized, object_pairs_hook=lambda pairs: dict(pairs))
                return result
            except json.JSONDecodeError:
                pass
            try:
                repaired = repair_truncated_json(json_block)
                result = json.loads(repaired, object_pairs_hook=lambda pairs: dict(pairs))
                return result
            except json.JSONDecodeError:
                pass
            try:
                sanitized = sanitize_newlines_in_strings(json_block)
                repaired = repair_truncated_json(sanitized)
                result = json.loads(repaired, object_pairs_hook=lambda pairs: dict(pairs))
                return result
            except json.JSONDecodeError:
                pass

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    merged_result = {}
    for line in text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        try:
            chunk = json.loads(line_str)
            if isinstance(chunk, dict):
                merged_result.update(chunk)
        except json.JSONDecodeError:
            continue

    if merged_result:
        return merged_result

    raise ValueError(f"[LLM] Could not extract valid JSON from response: {raw[:200]}")
