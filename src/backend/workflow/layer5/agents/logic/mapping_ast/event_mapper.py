"""
agents/logic/ast/event_mapper.py — VBA Event → C# Command Mapper

Deterministic mapping (zero LLM token):
  - VBA event names → C# RelayCommand / method names
  - Classify action_type: SYS | UI | VALID
  - Only VALID events need LLM to generate logic

Ref: Agent_Logic.md — "VBA Event → C# Command Mapping" table
Ref: agents/ui/control_mapper.py — same deterministic pattern
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# VBA Event → C# Command/Method mapping table
# ──────────────────────────────────────────────
# Key: VBA suffix pattern (case-insensitive match)
# Value: (cs_command_or_method, trigger_description, default_action_type)

VBA_EVENT_MAP: dict[str, tuple[str, str, str]] = {
    # Form lifecycle events → SYS (skip or minimal)
    "form_open":        ("OnNavigatedTo",      "Window loaded",       "SYS"),
    "form_load":        ("Window_Loaded",       "After controls ready","SYS"),
    "form_close":       ("OnNavigatedFrom",     "Window closing",      "SYS"),
    "form_unload":      ("OnNavigatedFrom",     "Window unloading",    "SYS"),
    "form_activate":    ("OnActivated",         "Window activated",    "SYS"),
    "form_deactivate":  ("OnDeactivated",       "Window deactivated",  "SYS"),
    "form_current":     ("OnCurrentChanged",    "Record navigation",   "SYS"),
    "form_resize":      ("OnSizeChanged",       "Window resized",      "SYS"),

    # Keyboard events → UI (handled in XAML / code-behind)
    "form_keydown":     ("OnKeyDown",           "Key pressed",         "UI"),
    "form_keyup":       ("OnKeyUp",             "Key released",        "UI"),
    "form_keypress":    ("OnKeyPress",          "Key press",           "UI"),

    # Timer → SYS
    "form_timer":       ("OnTimerTick",         "Timer tick",          "SYS"),
}

# ──────────────────────────────────────────────
# Button/Control click patterns
# ──────────────────────────────────────────────
# These are handled dynamically — extract command name from control name
CLICK_SUFFIXES = ("_click", "_dblclick", "_dbl")

# AfterUpdate / BeforeUpdate → validation/logic
UPDATE_SUFFIXES = ("_afterupdate", "_beforeupdate", "_after", "_before")

# Focus events → usually UI
FOCUS_SUFFIXES = ("_gotfocus", "_lostfocus", "_enter", "_exit")

# Change events → sometimes logic
CHANGE_SUFFIXES = ("_change", "_dirty", "_updated")


class EventMapper:
    """
    Maps VBA events from BD JSON → C# command/method names.
    Deterministic — zero LLM token cost.
    """

    def map_event(self, bd_event: dict) -> dict:
        """
        Map a single BD event to C# command/method info.

        Args:
            bd_event: dict from BD JSON sheet_2_layout.events[] containing:
                - event_id: "E003"
                - module_id: "F003"
                - type: "テキストボックス" | "フォーム" | "コマンドボタン"
                - physical_name: "txtPass" (optional)
                - event_trigger: "更新後処理" (Japanese description)
                - event_content: description of what happens
                - notes: "txtPass_AfterUpdate" (VBA handler name)
                - action_type: "SYS" | "UI" | "VALID" (pre-classified)

        Returns:
            dict with mapped C# info:
                - event_id, module_id (passthrough)
                - vba_event: original VBA handler name
                - cs_command: C# command name (e.g. "LoginCommand")
                - cs_method: C# method name (e.g. "LoginAsync")
                - action_type: "SYS" | "UI" | "VALID"
                - is_main_logic: True if VALID (needs LLM)
                - trigger: human-readable trigger description
        """
        event_id    = bd_event.get("event_id", "")
        module_id   = bd_event.get("module_id", "")
        notes       = bd_event.get("notes", "")           # VBA handler name
        ctrl_type   = bd_event.get("type", "")
        ctrl_name   = bd_event.get("physical_name", "")
        action_type = bd_event.get("action_type", "")

        # Normalize VBA handler name
        vba_event = notes.strip() if notes else ""

        # Step 1: Try exact match from VBA_EVENT_MAP (form-level events)
        vba_lower = vba_event.lower().replace(" ", "_")
        if vba_lower in VBA_EVENT_MAP:
            cs_method, trigger, default_type = VBA_EVENT_MAP[vba_lower]
            # Use pre-classified action_type if available, else default
            final_type = action_type if action_type else default_type
            return {
                "event_id":      event_id,
                "module_id":     module_id,
                "vba_event":     vba_event,
                "cs_command":    "",  # Form events don't have commands
                "cs_method":     cs_method,
                "action_type":   final_type,
                "is_main_logic": final_type == "VALID",
                "trigger":       trigger,
            }

        # Step 2: Click events → RelayCommand
        for suffix in CLICK_SUFFIXES:
            if vba_lower.endswith(suffix):
                base = vba_event[:len(vba_event) - len(suffix)]
                cmd_name = self._to_command_name(base, ctrl_name)
                method_name = self._to_method_name(base, is_async=False)
                final_type = action_type if action_type else "SYS"
                return {
                    "event_id":      event_id,
                    "module_id":     module_id,
                    "vba_event":     vba_event,
                    "cs_command":    cmd_name,
                    "cs_method":     method_name,
                    "action_type":   final_type,
                    "is_main_logic": final_type == "VALID",
                    "trigger":       "Button click",
                }

        # Step 3: AfterUpdate → usually VALID (has business logic)
        for suffix in UPDATE_SUFFIXES:
            if vba_lower.endswith(suffix):
                base = vba_event[:len(vba_event) - len(suffix)]
                # AfterUpdate on TextBox/ComboBox → command + async method
                cmd_name = self._to_command_name(base, ctrl_name)
                method_name = self._to_method_name(base, is_async=True)
                final_type = action_type if action_type else "VALID"
                return {
                    "event_id":      event_id,
                    "module_id":     module_id,
                    "vba_event":     vba_event,
                    "cs_command":    cmd_name,
                    "cs_method":     method_name,
                    "action_type":   final_type,
                    "is_main_logic": final_type == "VALID",
                    "trigger":       "After update / Enter key",
                }

        # Step 4: Focus events → UI
        for suffix in FOCUS_SUFFIXES:
            if vba_lower.endswith(suffix):
                base = vba_event[:len(vba_event) - len(suffix)]
                method_name = f"On{self._pascal_case(base)}Focus"
                final_type = action_type if action_type else "UI"
                return {
                    "event_id":      event_id,
                    "module_id":     module_id,
                    "vba_event":     vba_event,
                    "cs_command":    "",
                    "cs_method":     method_name,
                    "action_type":   final_type,
                    "is_main_logic": final_type == "VALID",
                    "trigger":       "Focus change",
                }

        # Step 5: Change events → may have logic
        for suffix in CHANGE_SUFFIXES:
            if vba_lower.endswith(suffix):
                base = vba_event[:len(vba_event) - len(suffix)]
                method_name = f"On{self._pascal_case(base)}Changed"
                final_type = action_type if action_type else "UI"
                return {
                    "event_id":      event_id,
                    "module_id":     module_id,
                    "vba_event":     vba_event,
                    "cs_command":    "",
                    "cs_method":     method_name,
                    "action_type":   final_type,
                    "is_main_logic": final_type == "VALID",
                    "trigger":       "Value changed",
                }

        # Step 5.5: 参照マクロ (Macro reference events) → SYS
        # Pattern: notes = "参照マクロ: A_メニューバーを表示.xlsx"
        # These are Access macro calls — no business logic, map to SYS stub using module_id
        if vba_event.startswith("参照マクロ") or "参照マクロ" in vba_event:
            # Use module_id as method name (F006Async etc.) from ui_event_map if available
            cs_method = f"{module_id}Async" if module_id else f"MacroRef_{event_id}"
            return {
                "event_id":      event_id,
                "module_id":     module_id,
                "vba_event":     vba_event,
                "cs_command":    "",
                "cs_method":     cs_method,
                "action_type":   "SYS",
                "is_main_logic": False,
                "trigger":       "参照マクロ (macro reference)",
                "macro_ref":     True,
            }

        # Step 6: Fallback — unknown event pattern
        # Prefer module_id-based method name to avoid Japanese in C# identifiers
        final_type = action_type if action_type else "SYS"
        # Use FxxxAsync if module_id available (clean C# identifier)
        # Only fall back to sanitize if no module_id
        if module_id:
            method_name = f"{module_id}Async"
        else:
            method_name = self._sanitize_method_name(vba_event) or f"Handle_{event_id}"
        return {
            "event_id":      event_id,
            "module_id":     module_id,
            "vba_event":     vba_event,
            "cs_command":    "",
            "cs_method":     method_name,
            "action_type":   final_type,
            "is_main_logic": final_type == "VALID",
            "trigger":       "Unknown",
        }

    def map_all_events(self, events: list[dict]) -> list[dict]:
        """
        Batch-map all BD events.

        Args:
            events: list of BD event dicts from sheet_2_layout.events[]

        Returns:
            list of mapped event dicts (same order)
        """
        mapped = []
        for evt in events:
            m = self.map_event(evt)
            mapped.append(m)
            logger.debug(
                "[EventMapper] %s: %s → %s (%s) [%s]",
                m["event_id"], m["vba_event"],
                m["cs_command"] or m["cs_method"],
                m["action_type"],
                "⭐ MAIN" if m["is_main_logic"] else "skip",
            )

        # Summary log
        valid_count = sum(1 for m in mapped if m["is_main_logic"])
        logger.info(
            "[EventMapper] Mapped %d events → %d VALID (need LLM), %d skip",
            len(mapped), valid_count, len(mapped) - valid_count,
        )
        return mapped

    def classify_action_type(self, event: dict) -> str:
        """
        Classify a BD event into SYS / UI / VALID.

        Rules:
            SYS:   Form_Open, Form_Close, Form_Load, Timer, simple button close
            UI:    Form_KeyDown, Focus events, UI-only interactions
            VALID: Has DD steps with actual business logic ⭐
        
        Note: The BD JSON usually has action_type pre-classified.
              This method is a fallback/override mechanism.
        """
        notes = event.get("notes", "").lower().replace(" ", "_")
        event_content = event.get("event_content", "")

        # Form lifecycle → SYS
        if notes in VBA_EVENT_MAP:
            _, _, default_type = VBA_EVENT_MAP[notes]
            return default_type

        # Keyboard events → UI
        if any(kw in notes for kw in ("keydown", "keyup", "keypress")):
            return "UI"

        # Focus events → UI
        if any(notes.endswith(s) for s in FOCUS_SUFFIXES):
            return "UI"

        # Close/Quit buttons → SYS
        close_keywords = ("閉じる", "close", "quit", "exit", "終了")
        if any(kw in notes.lower() for kw in close_keywords):
            return "SYS"
        if any(kw in event_content for kw in ("終了する", "閉じる", "Quit")):
            return "SYS"

        # Has substantial content → likely VALID
        if len(event_content) > 20:
            return "VALID"

        # Default → SYS (safe)
        return "SYS"

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _to_command_name(base: str, ctrl_name: str = "") -> str:
        """
        Derive C# RelayCommand name from VBA handler base.

        Examples:
            base="cmdLogin", ctrl_name="cmdLogin" → "LoginCommand"
            base="btnSave",  ctrl_name="btnSave"  → "SaveCommand"
            base="閉じる",   ctrl_name="cmdClose" → "CloseCommand"
            base="txtPass",  ctrl_name="txtPass"  → "PassCommand"
        """
        name = base

        # Strip common prefixes
        for prefix in ("cmd", "btn", "txt", "cmb", "chk", "opt"):
            if name.lower().startswith(prefix) and len(name) > len(prefix):
                name = name[len(prefix):]
                break

        # Japanese close button → CloseCommand
        close_jp = ("閉じる", "終了", "戻る")
        if any(jp in name for jp in close_jp):
            return "CloseCommand"

        # PascalCase + Command suffix
        name = EventMapper._pascal_case(name)
        if not name.endswith("Command"):
            name += "Command"
        return name

    @staticmethod
    def _to_method_name(base: str, is_async: bool = False) -> str:
        """
        Derive C# method name from VBA handler base.

        Examples:
            base="txtPass", is_async=True → "LoginAsync"  (special case)
            base="cmdSave", is_async=True → "SaveAsync"
            base="btnClose", is_async=False → "Close"
        """
        name = base

        # Strip common prefixes
        for prefix in ("cmd", "btn", "txt", "cmb", "chk", "opt"):
            if name.lower().startswith(prefix) and len(name) > len(prefix):
                name = name[len(prefix):]
                break

        # Japanese → English method names
        jp_method_map = {
            "閉じる": "Close",
            "終了":   "Close",
            "戻る":   "GoBack",
            "保存":   "Save",
            "削除":   "Delete",
            "検索":   "Search",
            "印刷":   "Print",
            "更新":   "Update",
            "登録":   "Register",
            "確認":   "Confirm",
        }
        for jp, en in jp_method_map.items():
            if jp in name:
                name = en
                break

        name = EventMapper._pascal_case(name)

        if is_async and not name.endswith("Async"):
            name += "Async"
        return name

    @staticmethod
    def _pascal_case(s: str) -> str:
        """
        Convert string to PascalCase.
        Handles: snake_case, camelCase, Japanese text (passthrough).
        """
        if not s:
            return s

        # If already PascalCase (starts with upper, has mixed case) → return as-is
        if s[0].isupper() and any(c.islower() for c in s):
            return s

        # snake_case → PascalCase
        if "_" in s:
            return "".join(part.capitalize() for part in s.split("_") if part)

        # camelCase → PascalCase
        return s[0].upper() + s[1:] if s else s

    @staticmethod
    def _sanitize_method_name(vba_event: str) -> str:
        """
        Convert VBA event name to a valid C# method name.
        Supports Japanese (Unicode) natively.
        """
        if not vba_event:
            return ""

        # Keep alphanumeric (including Unicode Japanese) and underscore
        safe = ""
        for ch in vba_event:
            if ch.isalnum() or ch == '_':
                safe += ch
            else:
                safe += '_'

        # Ensure starts with letter/underscore (cannot start with digit)
        if safe and safe[0].isdigit():
            safe = "_" + safe

        return safe or "Handle_Unknown"
