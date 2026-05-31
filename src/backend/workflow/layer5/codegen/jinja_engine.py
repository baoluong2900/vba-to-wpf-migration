"""
codegen/jinja_engine.py — Jinja2 Template Engine for C# Code Generation

Renders Entity, DTO, Interface templates from structured data.
Zero LLM tokens — pure deterministic generation.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _create_env() -> Environment:
    """Create Jinja2 environment with C# friendly settings."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env


_env = _create_env()


def render_template(template_name: str, **kwargs: Any) -> str:
    """
    Render a Jinja2 template with given context.

    Args:
        template_name: Template file name (e.g., "Entity.cs.j2")
        **kwargs: Template variables

    Returns:
        Rendered C# code string.
    """
    tmpl = _env.get_template(template_name)
    result = tmpl.render(**kwargs)
    logger.info("[Jinja2] Rendered: %s", template_name)
    return result


def render_entity(
    entity_name: str,
    fields: list[dict],
    table_name: str = "",
) -> str:
    """
    Render Entity.cs from table schema.

    Args:
        entity_name: e.g., "IdPassEntity"
        fields: [{"name": "UserId", "type": "string", "default": "string.Empty"}, ...]
        table_name: source table name for doc comment

    Returns:
        Complete C# Entity class code.
    """
    return render_template(
        "Entity.cs.j2",
        entity_name=entity_name,
        fields=fields,
        table_name=table_name,
    )


def render_interface(
    entity_name: str,
    methods: list[dict],
) -> str:
    """
    Render IRepository interface.

    Args:
        entity_name: e.g., "IdPass" (without Entity suffix)
        methods: [{"name": "GetByIdAsync", "return_type": "IdPassEntity?", "params": "string id"}, ...]

    Returns:
        Complete C# Interface code.
    """
    return render_template(
        "Interface.cs.j2",
        entity_name=entity_name,
        methods=methods,
    )


def render_dto(
    class_name: str,
    fields: list[dict],
    form_name: str = "",
    purpose: str = "",
) -> str:
    """
    Render DTO (Request or Response).

    Args:
        class_name: e.g., "LoginRequest", "LoginResponse"
        fields: [{"name": "UserId", "type": "string", "default": "string.Empty"}, ...]
        form_name: Source form for doc comment
        purpose: Description of this DTO

    Returns:
        Complete C# DTO class code.
    """
    return render_template(
        "DTO.cs.j2",
        class_name=class_name,
        fields=fields,
        form_name=form_name,
        purpose=purpose,
    )


def render_service_interface(
    service_name: str,
    methods: list[dict],
    usings: list[str] | None = None,
    form_name: str = "",
    purpose: str = "",
) -> str:
    """
    Render IService interface (Form / Macro / Module service).

    Args:
        service_name: e.g., "AuthService", "NavigationService", "CommonService"
                      (the "I" prefix is added by the template).
        methods: [{
            "name": "AuthenticateAsync",
            "return_type": "Task<LoginResponse>",
            "params": "LoginRequest request",
            "comment": "Login authentication (F003 更新後処理)",
        }, ...]
        usings: Additional using statements (e.g. "vba_brain.Application.DTOs").
        form_name: Source form for documentation comment.
        purpose: One-line description of the service.

    Returns:
        Complete C# interface code.
    """
    return render_template(
        "IService.cs.j2",
        service_name=service_name,
        methods=methods,
        usings=usings or [],
        form_name=form_name,
        purpose=purpose,
    )
