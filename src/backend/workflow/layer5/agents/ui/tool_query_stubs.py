"""
agents/ui/tool_query_stubs.py — Control Source → Query Stub Generator

Phân tích control_source expressions (DLookUp, field references) từ WPF controls
và gen ra:
  1. agents/ui/configs/ui_query_stubs.json  — contract giữa UI agent & Logic agent
  2. Property stubs với // TODO [QUERY] tag trong ViewModel (qua tool_skeleton.py)

Supported control_source patterns:
  - "=DLookUp(\"field\",\"table\")"          → simple DLookUp
  - "=DLookUp(\"field\",\"table\",\"crit\")" → DLookUp with criteria
  - "=DCount(\"*\",\"table\",\"crit\")"      → DCount
  - "=DSum(\"field\",\"table\")"             → DSum
  - "=\"prefix:\" & [FieldName]"             → expression with field ref
  - "[FieldName]"                            → direct field reference
  - "TableName.FieldName"                    → table.field reference

Usage:
    from agents.ui.tool_query_stubs import QueryStubTool
    tool = QueryStubTool()
    stubs = tool.extract(form_name, wpf_controls)   # returns dict
    tool.save(form_name, stubs)                      # merges into ui_query_stubs.json
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from core.fsutil import atomic_write_text, file_lock

logger = logging.getLogger(__name__)

_UI_QUERY_STUBS = Path(__file__).resolve().parent / "configs" / "ui_query_stubs.json"

# Repo agent name_config — nguồn mapping JP field/table/function → EN names
_REPO_NAME_CONFIG = (
    Path(__file__).resolve().parent.parent / "repo" / "config" / "name_config.json"
)

# UI Agent's own name mapping — copy of repo name_config, can be extended independently
_UI_NAME_MAP = Path(__file__).resolve().parent.parent / "ui" / "name_spacing" / "ui_name_map.json"


def _load_name_config() -> dict:
    """
    Load name mapping for UI agent.
    Priority: ui_name_map.json (UI-owned) → repo name_config.json (fallback).
    """
    # Try UI-owned mapping first
    if _UI_NAME_MAP.exists():
        try:
            return json.loads(_UI_NAME_MAP.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[QueryStubTool] Failed to load ui_name_map.json: %s", exc)

    # Fallback to repo config
    if _REPO_NAME_CONFIG.exists():
        try:
            return json.loads(_REPO_NAME_CONFIG.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[QueryStubTool] Failed to load name_config.json: %s", exc)

    logger.warning("[QueryStubTool] No name mapping found — property names will use JP originals")
    return {}


def _resolve_en_name(jp_name: str, name_config: dict) -> str:
    """
    Lookup jp_name trong field_name mapping.
    Returns EN name nếu tìm thấy, else empty string.

    Example:
        _resolve_en_name("コメント", cfg)  → "Comment1"
        _resolve_en_name("電話番号", cfg)  → "PhoneNumber"
    """
    return name_config.get("field_name", {}).get(jp_name, "")

# ── Access domain function patterns ──────────────────────────────────────────
# DLookUp("field","table") or DLookUp("field","table","criteria")
_RE_DLOOKUP = re.compile(
    r'DLookUp\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]*)")?\s*\)',
    re.IGNORECASE,
)
# DCount("*","table") / DCount("*","table","criteria")
_RE_DCOUNT = re.compile(
    r'DCount\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]*)")?\s*\)',
    re.IGNORECASE,
)
# DSum("field","table") / DSum("field","table","criteria")
_RE_DSUM = re.compile(
    r'DSum\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]*)")?\s*\)',
    re.IGNORECASE,
)
# DMax/DMin/DAvg
_RE_DAGG = re.compile(
    r'(DMax|DMin|DAvg)\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]*)")?\s*\)',
    re.IGNORECASE,
)
# Field reference in expression: [FieldName]
_RE_FIELD_REF = re.compile(r'\[([^\]]+)\]')
# Table.Field reference
_RE_TABLE_FIELD = re.compile(r'^([A-Za-z\u3000-\u9FFF][^.\s]+)\.([^.\s]+)$')


def _make_property_name(control_name: str, field: str, func: str) -> str:
    """
    Derive a clean C# property name from context.
    Rules:
      - DLookUp("コメント","Access配信日") on control 最新版公開日 → "最新版公開日"
      - [電話番号] expression                                     → "電話番号"
      - DCount on control cntOrders                              → "cntOrdersCount"
    """
    if func in ("DCount", "DAvg"):
        suffix = "Count" if func == "DCount" else "Avg"
        base = control_name or field
        return base + suffix
    if func in ("DSum",):
        return (control_name or field) + "Sum"
    # Default: use control_name if available, else field name
    return control_name or field


class QueryStubTool:
    """
    Extracts control_source expressions from WPF controls and generates
    query stub contracts for Logic Agent to implement.
    """

    def extract(self, form_name: str, wpf_controls: list[dict]) -> dict[str, dict]:
        """
        Parse all control_source fields in wpf_controls.

        Returns:
            dict[control_name → stub_entry], e.g.::
                {
                    "最新版公開日": {
                        "control_name":       "最新版公開日",
                        "wpf_type":           "TextBox",
                        "control_source":     "=DLookUp(\"コメント\",\"Access配信日\")",
                        "source_type":        "DLookUp",
                        "table":              "Access配信日",
                        "table_en":           "GetComment",
                        "field":              "コメント",
                        "field_en":           "Comment1",
                        "criteria":           "",
                        "suggested_property": "Comment1",
                        "suggested_method":   "LoadComment1Async",
                        "status":             "pending",
                    }
                }
        """
        name_config = _load_name_config()
        stubs: dict[str, dict] = {}

        for ctrl in wpf_controls:
            name         = ctrl.get("name", "")
            wpf_type     = ctrl.get("wpf_type", "")
            data         = ctrl.get("data", {})
            control_source = (
                data.get("control_source") or
                data.get("controlsource") or
                ""
            )

            if not control_source:
                continue

            # Strip leading = for expressions
            expr = control_source.lstrip("=").strip()

            stub = self._parse_expression(expr, name, wpf_type, control_source, name_config)
            if stub:
                stubs[name] = stub
                logger.debug("[QueryStubTool] %s → %s (prop=%s)", name, stub["source_type"], stub["suggested_property"])

        if stubs:
            logger.info(
                "[QueryStubTool] Found %d control_source stub(s) for %s",
                len(stubs), form_name,
            )
        return stubs

    def _parse_expression(
        self,
        expr: str,
        control_name: str,
        wpf_type: str,
        raw_source: str,
        name_config: dict | None = None,
    ) -> dict | None:
        """Parse a single expression into a stub entry. Returns None if not parseable."""

        # Normalize escaped quotes from JSON storage (\\\" → ") before regex matching
        expr = expr.replace('\\"', '"').replace("\\'", "'")
        cfg  = name_config or {}

        # ── DLookUp ──────────────────────────────────────────────────────
        m = _RE_DLOOKUP.search(expr)
        if m:
            field, table, criteria = m.group(1), m.group(2), (m.group(3) or "")
            field_en = _resolve_en_name(field, cfg)
            prop     = field_en or _make_property_name(control_name, field, "DLookUp")
            return {
                "control_name":       control_name,
                "wpf_type":           wpf_type,
                "control_source":     raw_source,
                "source_type":        "DLookUp",
                "table":              table,
                "field":              field,
                "field_en":           field_en,
                "criteria":           criteria,
                "suggested_property": prop,
                "suggested_method":   f"Load{prop}Async",
                "status":             "pending",
            }

        # ── DCount ───────────────────────────────────────────────────────
        m = _RE_DCOUNT.search(expr)
        if m:
            field, table, criteria = m.group(1), m.group(2), (m.group(3) or "")
            field_en = _resolve_en_name(field, cfg)
            prop     = _make_property_name(control_name, field_en or field, "DCount")
            return {
                "control_name":       control_name,
                "wpf_type":           wpf_type,
                "control_source":     raw_source,
                "source_type":        "DCount",
                "table":              table,
                "field":              field,
                "field_en":           field_en,
                "criteria":           criteria,
                "suggested_property": prop,
                "suggested_method":   f"Load{prop}Async",
                "status":             "pending",
            }

        # ── DSum ─────────────────────────────────────────────────────────
        m = _RE_DSUM.search(expr)
        if m:
            field, table, criteria = m.group(1), m.group(2), (m.group(3) or "")
            field_en = _resolve_en_name(field, cfg)
            prop     = _make_property_name(control_name, field_en or field, "DSum")
            return {
                "control_name":       control_name,
                "wpf_type":           wpf_type,
                "control_source":     raw_source,
                "source_type":        "DSum",
                "table":              table,
                "field":              field,
                "field_en":           field_en,
                "criteria":           criteria,
                "suggested_property": prop,
                "suggested_method":   f"Load{prop}Async",
                "status":             "pending",
            }

        # ── DMax/DMin/DAvg ───────────────────────────────────────────────
        m = _RE_DAGG.search(expr)
        if m:
            func, field, table, criteria = m.group(1), m.group(2), m.group(3), (m.group(4) or "")
            field_en = _resolve_en_name(field, cfg)
            prop     = _make_property_name(control_name, field_en or field, func)
            return {
                "control_name":       control_name,
                "wpf_type":           wpf_type,
                "control_source":     raw_source,
                "source_type":        func,
                "table":              table,
                "field":              field,
                "field_en":           field_en,
                "criteria":           criteria,
                "suggested_property": prop,
                "suggested_method":   f"Load{prop}Async",
                "status":             "pending",
            }

        # ── [FieldRef] or expression with [FieldRef] ─────────────────────
        fields = _RE_FIELD_REF.findall(expr)
        if fields:
            fields_en = [_resolve_en_name(f, cfg) or f for f in fields]
            prop = "".join(fields_en) + ("Display" if len(fields_en) > 1 else "")
            prop = prop or control_name
            return {
                "control_name":       control_name,
                "wpf_type":           wpf_type,
                "control_source":     raw_source,
                "source_type":        "FieldRef",
                "table":              "",
                "field":              ", ".join(fields),
                "field_en":           ", ".join(fields_en),
                "criteria":           "",
                "suggested_property": prop,
                "suggested_method":   f"Load{prop}Async",
                "status":             "pending",
            }

        # ── Table.Field ──────────────────────────────────────────────────
        m = _RE_TABLE_FIELD.match(expr)
        if m:
            table, field = m.group(1), m.group(2)
            field_en = _resolve_en_name(field, cfg)
            prop     = field_en or _make_property_name(control_name, field, "Field")
            return {
                "control_name":       control_name,
                "wpf_type":           wpf_type,
                "control_source":     raw_source,
                "source_type":        "TableField",
                "table":              table,
                "field":              field,
                "field_en":           field_en,
                "criteria":           "",
                "suggested_property": prop,
                "suggested_method":   f"Load{prop}Async",
                "status":             "pending",
            }

        # ── Simple field name (no special syntax) ────────────────────────
        if expr and not expr.startswith("=") and " " not in expr:
            field_en = _resolve_en_name(expr, cfg)
            prop     = field_en or control_name or expr
            return {
                "control_name":       control_name,
                "wpf_type":           wpf_type,
                "control_source":     raw_source,
                "source_type":        "DirectField",
                "table":              "",
                "field":              expr,
                "field_en":           field_en,
                "criteria":           "",
                "suggested_property": prop,
                "suggested_method":   "",
                "status":             "pending",
            }

        return None

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self, form_name: str, stubs: dict[str, dict]) -> Path:
        """
        Merge stubs into ui_query_stubs.json (atomic, locked).
        Existing entries with status != "pending" are preserved (not overwritten).
        """
        with file_lock(_UI_QUERY_STUBS):
            registry: dict = {}
            if _UI_QUERY_STUBS.exists():
                try:
                    registry = json.loads(_UI_QUERY_STUBS.read_text(encoding="utf-8"))
                except Exception as exc:
                    # Never rewrite a file we could not read: it holds every form's stubs.
                    logger.warning("[QueryStubTool] %s unreadable (%s) — not saving", _UI_QUERY_STUBS.name, exc)
                    return _UI_QUERY_STUBS

            # Merge: preserve non-pending entries
            form_stubs = registry.get(form_name, {})
            for ctrl_name, new_stub in stubs.items():
                existing = form_stubs.get(ctrl_name, {})
                if existing.get("status", "pending") != "pending":
                    continue   # Keep resolved entries as-is
                form_stubs[ctrl_name] = new_stub

            registry[form_name] = form_stubs
            atomic_write_text(_UI_QUERY_STUBS, json.dumps(registry, ensure_ascii=False, indent=2))
        logger.info("[QueryStubTool] Saved %d stub(s) for %s → %s", len(stubs), form_name, _UI_QUERY_STUBS.name)
        return _UI_QUERY_STUBS
