"""
core/fid_resolver.py — One F-ID (module id) numbering shared by the UI skeleton and Agent Logic.

F### ids name the generated members (F003Command / F003Async) and key Agent Service's contract,
so every agent must map a VBA handler to the same id. Per handler, in priority order:
  1. the BD event whose `notes` equals the handler (or the raw "macro.X" event value)  → module_id
  2. the BD event whose physical_name + trigger match the handler's control + event   → module_id
  3. the handler's existing entry in agents/ui/configs/ui_event_map.json (human or `_auto`)
  4. a new `_auto` id that collides with no BD id and no kept registry id
BD ids stay reserved even when no UI handler matches them, so a BD-only event never shares an id.

The UI agent resolves once per run (`resolve_and_sync`) and passes the map down; Agent Logic maps
BD events back to the ids the skeleton used (`fid_for_bd_event`).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from core.config import LAYER4_INPUTS_DIR, UI_EVENT_MAP_PATH
from core.fsutil import atomic_write_text, file_lock

logger = logging.getLogger(__name__)

FID_RE = re.compile(r"^F\d{3}$")
FORM_CONTROL = "__form__"

# Normalised (lower-case, no spaces/underscores) trigger spellings → Mongo `forms` event keys.
_EVENT_ALIASES = {
    "click": "onclick",
    "dblclick": "ondblclick",
    "ondoubleclick": "ondblclick",
    "doubleclick": "ondblclick",
    "onafterupdate": "afterupdate",
    "onbeforeupdate": "beforeupdate",
    "open": "onopen",
    "load": "onload",
    "keydown": "onkeydown",
    "クリック時": "onclick",
    "ダブルクリック時": "ondblclick",
    "更新後処理": "afterupdate",
    "更新前処理": "beforeupdate",
    "キー押下時": "onkeydown",
    "画面を開く時": "onopen",
    "フォーム読み込み後": "onload",
}


@dataclass(frozen=True)
class HandlerRef:
    """A VBA handler as the UI agent sees it (vm_bindings["event_handlers"] entry)."""
    handler: str
    control: str = ""
    event: str = ""
    raw: str = ""  # raw event property value, e.g. "macro.A_メニューバーを表示"

    @classmethod
    def from_binding(cls, binding: dict) -> "HandlerRef":
        return cls(
            handler=binding.get("method", "") or "",
            control=binding.get("control", "") or "",
            event=binding.get("event", "") or "",
            raw=binding.get("raw", "") or "",
        )


def normalize_event(value: str | None) -> str:
    """'On Double Click' / 'ondblclick' / 'ダブルクリック時' → 'ondblclick'."""
    key = re.sub(r"[\s_]+", "", value or "").lower()
    return _EVENT_ALIASES.get(key, key)


def _key(value: str | None) -> str:
    return (value or "").strip().casefold()


def _bd_module_id(event: dict) -> str:
    mid = (event.get("module_id") or "").strip()
    return mid if FID_RE.match(mid) else ""


def _is_form_level(event: dict) -> bool:
    return _key(event.get("type")) in ("form", "フォーム") or _key(event.get("physical_name")) in ("", "-")


def _notes_key(event: dict) -> str:
    notes = _key(event.get("notes"))
    return "" if notes in ("", "-") or notes.startswith("[") else notes


def macro_name(value: str | None) -> str:
    """Macro name for "macro.X" / "参照マクロ: X(.xlsx)" event values, else ""."""
    text = (value or "").strip()
    m = re.match(r"(?i)^(?:macro\.|参照マクロ[:：]\s*)(.+?)(?:\.xlsx)?$", text)
    return m.group(1).strip() if m else ""


def bd_events_of(bd_json: dict | None) -> list[dict]:
    """BD events from a flat or sheet-structured BD document."""
    if not isinstance(bd_json, dict):
        return []
    events = bd_json.get("events")
    if not events and isinstance(bd_json.get("sheet_2_layout"), dict):
        events = bd_json["sheet_2_layout"].get("events")
    return [e for e in (events or []) if isinstance(e, dict)]


def load_bd_events_from_file(form_name: str) -> list[dict]:
    """BD events from layer4/inputs/BD_json/screen/{form}.json ([] when missing/unreadable)."""
    path = LAYER4_INPUTS_DIR / "BD_json" / "screen" / f"{form_name}.json"
    try:
        return bd_events_of(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []


def next_free_fid(used: Iterable[str]) -> str:
    taken = set(used)
    for i in range(1000):
        candidate = f"F{i:03d}"
        if candidate not in taken:
            return candidate
    raise RuntimeError("Exhausted all module IDs F000–F999")


def _registry_entry(ref: HandlerRef, fid: str, old: dict | None, bd_event: dict | None, auto: bool) -> dict:
    entry = {
        "vba_handler": ref.handler,
        "vm_method_name": f"{fid}Async",
        "control": ref.control,
        "event": ref.event,
    }
    for key, value in (old or {}).items():  # keep human annotations such as `_note`
        if key.startswith("_") and key != "_auto":
            entry[key] = value
    macro = macro_name(ref.raw) or macro_name((bd_event or {}).get("notes"))
    if macro:
        entry["_note"] = f"参照マクロ: {macro}"
    if auto:
        entry["_auto"] = True
    return entry


def resolve_fids(
    refs: Iterable[HandlerRef],
    bd_events: Iterable[dict] | None,
    entries: dict | None,
    *,
    prune: bool = True,
) -> tuple[dict[str, str], dict[str, dict]]:
    """
    Pure resolution → (handler → F-id, the form's updated ui_event_map entries).

    prune=True (a full UI run) drops `_auto` entries whose handler is no longer present; entries
    whose id now belongs to another handler are always dropped.
    """
    unique: list[HandlerRef] = []
    seen: set[str] = set()
    for ref in refs:
        if ref.handler and _key(ref.handler) not in seen:
            seen.add(_key(ref.handler))
            unique.append(ref)

    bd = [e for e in (bd_events or []) if _bd_module_id(e)]
    reserved = {_bd_module_id(e) for e in bd}
    registry = {k: v for k, v in (entries or {}).items() if isinstance(v, dict) and FID_RE.match(k)}

    assigned: dict[str, str] = {}      # handler → fid
    matched_bd: dict[str, dict] = {}   # handler → BD event
    used_bd: set[str] = set()

    def take(ref: HandlerRef, fid: str, bd_event: dict | None = None) -> None:
        assigned[ref.handler] = fid
        if bd_event is not None:
            matched_bd[ref.handler] = bd_event
            used_bd.add(fid)

    by_notes: dict[str, dict] = {}
    for e in bd:
        by_notes.setdefault(_notes_key(e), e)
    by_notes.pop("", None)

    # 1. BD notes == handler / raw value
    for ref in unique:
        for name in (ref.handler, ref.raw):
            e = by_notes.get(_key(name)) if name else None
            if e is not None and _bd_module_id(e) not in used_bd:
                take(ref, _bd_module_id(e), e)
                break

    # 2. BD control + event
    for ref in unique:
        if ref.handler in assigned or not normalize_event(ref.event):
            continue
        for e in bd:
            mid = _bd_module_id(e)
            if mid in used_bd or normalize_event(e.get("event_trigger")) != normalize_event(ref.event):
                continue
            if ref.control == FORM_CONTROL:
                same_control = _is_form_level(e)
            else:
                same_control = bool(_key(ref.control)) and _key(e.get("physical_name")) == _key(ref.control)
            if same_control:
                take(ref, mid, e)
                break

    # 3. existing registry entry for the same handler (keeps human and `_auto` ids stable)
    taken = reserved | set(assigned.values())
    sources: dict[str, dict] = {}
    for ref in unique:
        if ref.handler in assigned:
            continue
        for fid, entry in registry.items():
            if _key(entry.get("vba_handler")) == _key(ref.handler) and fid not in taken:
                take(ref, fid)
                sources[ref.handler] = entry
                taken.add(fid)
                break

    # Registry entries that survive: not superseded, id not claimed, and (when pruning) not stale `_auto`.
    handler_keys = {_key(r.handler) for r in unique}
    kept = {
        fid: entry for fid, entry in registry.items()
        if fid not in taken
        and _key(entry.get("vba_handler")) not in handler_keys
        and not (prune and entry.get("_auto"))
    }

    # 4. new `_auto` ids
    blocked = taken | set(kept)
    for ref in unique:
        if ref.handler in assigned:
            continue
        fid = next_free_fid(blocked)
        blocked.add(fid)
        take(ref, fid)

    old_by_handler = {_key(e.get("vba_handler")): e for e in registry.values()}
    new_entries: dict[str, dict] = dict(kept)
    for ref in unique:
        fid = assigned[ref.handler]
        old = sources.get(ref.handler) or old_by_handler.get(_key(ref.handler))
        if ref.handler in matched_bd:
            auto = False
        elif ref.handler in sources:
            auto = bool(sources[ref.handler].get("_auto"))
        else:
            auto = True
        new_entries[fid] = _registry_entry(ref, fid, old, matched_bd.get(ref.handler), auto)

    extras = {k: v for k, v in (entries or {}).items() if not FID_RE.match(k)}
    ordered = {**extras, **dict(sorted(new_entries.items()))}
    return assigned, ordered


def fid_for_bd_event(bd_event: dict, entries: dict | None) -> str:
    """F-id the UI skeleton uses for a BD event: registry match by handler / control+event, else module_id."""
    registry = {k: v for k, v in (entries or {}).items() if isinstance(v, dict) and FID_RE.match(k)}
    notes = _notes_key(bd_event)
    if notes:
        for fid, entry in registry.items():
            if _key(entry.get("vba_handler")) == notes:
                return fid
    trigger = normalize_event(bd_event.get("event_trigger"))
    if trigger:
        for fid, entry in registry.items():
            if normalize_event(entry.get("event")) != trigger:
                continue
            if _is_form_level(bd_event):
                if entry.get("control") == FORM_CONTROL:
                    return fid
            elif _key(entry.get("control")) and _key(entry.get("control")) == _key(bd_event.get("physical_name")):
                return fid
    mid = _bd_module_id(bd_event)
    if mid:
        return mid
    eid = (bd_event.get("event_id") or "").strip()
    return "F" + eid[1:] if re.match(r"^E\d{3}$", eid) else ""


# ── Registry file (agents/ui/configs/ui_event_map.json) ────────────────────

def _read_registry(path: Path) -> dict | None:
    """Whole registry; {} when missing, None when unreadable (never overwrite a corrupt file)."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("[FID] %s unreadable (%s) — resolving without it, not rewriting", path.name, exc)
        return None
    return data if isinstance(data, dict) else None


def load_form_entries(form_name: str, path: Path = UI_EVENT_MAP_PATH) -> dict:
    registry = _read_registry(path) or {}
    entries = registry.get(form_name)
    return entries if isinstance(entries, dict) else {}


def resolve_and_sync(
    form_name: str,
    refs: Iterable[HandlerRef],
    bd_events: Iterable[dict] | None = None,
    path: Path = UI_EVENT_MAP_PATH,
    *,
    prune: bool = True,
) -> dict[str, str]:
    """Resolve handler → F-id for one form and persist the registry atomically under a lock."""
    refs = list(refs)
    with file_lock(path):
        registry = _read_registry(path)
        entries = (registry or {}).get(form_name) or {}
        fid_map, new_entries = resolve_fids(refs, bd_events, entries, prune=prune)
        if registry is not None and new_entries != entries:
            registry[form_name] = new_entries
            atomic_write_text(path, json.dumps(registry, ensure_ascii=False, indent=2))
            logger.info("[FID] ui_event_map.json updated for %s (%d handlers)", form_name, len(fid_map))
    return fid_map
