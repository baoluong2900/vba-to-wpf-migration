"""
core/state.py — LangGraph shared state object

Holds all data objects flowing through the BD → Human Review → DD pipeline.
Using TypedDict so LangGraph can merge partial updates cleanly.
"""
from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class ReviewDecision(TypedDict):
    """Human review result for a single item."""
    approved: bool
    notes: str          # reject reason if not approved


class PipelineState(TypedDict, total=False):
    # ── Input identifiers ─────────────────────────────────────────────────
    item_name: str              # e.g. "C000_MAINⅡ"  or  "R005_…"  or  "Common"
    screen_name: str            # alias of item_name, used by BDService
    item_type: str              # "form" | "report" | "module"
    complexity_level: str       # "low" | "medium" | "high" | "critical"

    # ── Layer 1 payloads (raw from MongoDB) ───────────────────────────────
    bd_code_json: dict[str, Any]    # bd query result (overview context)
    dd_code_json: dict[str, Any]    # dd query result (detail logic)

    # ── BD stage ──────────────────────────────────────────────────────────
    bd_docs_json: Optional[dict[str, Any]]      # LLM output for BD
    bd_review: Optional[ReviewDecision]          # human decision

    # ── DD stage ──────────────────────────────────────────────────────────
    dd_docs_json: Optional[dict[str, Any]]      # LLM output for DD
    dd_review: Optional[ReviewDecision]          # human decision

    # ── Runtime metadata ──────────────────────────────────────────────────
    attempt_bd: int             # retry counter for BD
    attempt_dd: int             # retry counter for DD
    errors: list[str]           # accumulated validation errors
    stage: str                  # "dev" | "pilot" | "production"
    repo: Any                   # Layer1Repo instance (passed to avoid re-creating)
    model_id: Optional[str]     # override model for this run (None = stage default)
