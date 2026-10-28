"""F-ID resolution shared by Agent UI (skeleton) and Agent Logic (src/backend/workflow/layer5/core/fid_resolver.py)."""
from __future__ import annotations

import json

from core.fid_resolver import (
    HandlerRef,
    fid_for_bd_event,
    macro_name,
    normalize_event,
    resolve_and_sync,
    resolve_fids,
)

# Trimmed from layer4 BD_json/screen/F_Login.json
BD = [
    {"event_id": "E000", "module_id": "F000", "notes": "Form_Open", "physical_name": "-", "type": "Form", "event_trigger": "On Open"},
    {"event_id": "E001", "module_id": "F001", "notes": "Form_Load", "physical_name": "-", "type": "Form", "event_trigger": "On Load"},
    {"event_id": "E002", "module_id": "F002", "notes": "Form_KeyDown", "physical_name": "-", "type": "Form", "event_trigger": "On Key Down"},
    {"event_id": "E004", "module_id": "F004", "notes": "cmdLogin_Click", "physical_name": "cmdLogin", "type": "Command Button", "event_trigger": "On Click"},
    {"event_id": "E005", "module_id": "F005", "notes": "cmdClose_Click", "physical_name": "cmdClose", "type": "Command Button", "event_trigger": "On Click"},
    {"event_id": "E007", "module_id": "F007", "notes": "macro.A_メニューバーを表示", "physical_name": "lblMenuTrigger", "type": "Label", "event_trigger": "On Click"},
    {"event_id": "E010", "module_id": "F010", "notes": "lblEndProcess_DblClick", "physical_name": "lblEndProcess", "type": "Label", "event_trigger": "On Double Click"},
]

# The stale numbering the UI registry had before (Form_KeyDown/Form_Load swapped, cmdLogin auto F010)
STALE_REGISTRY = {
    "F001": {"vba_handler": "Form_KeyDown", "vm_method_name": "F001Async", "control": "__form__", "event": "onkeydown"},
    "F002": {"vba_handler": "Form_Load", "vm_method_name": "F002Async", "control": "__form__", "event": "onload"},
    "F010": {"vba_handler": "cmdLogin_Click", "vm_method_name": "F010Async", "control": "", "event": "", "_auto": True},
}


def ref(handler, control="", event="", raw=""):
    return HandlerRef(handler=handler, control=control, event=event, raw=raw)


def test_bd_module_ids_win_over_a_stale_registry():
    refs = [ref("Form_Load", "__form__", "onload"), ref("Form_KeyDown", "__form__", "onkeydown"),
            ref("cmdLogin_Click", "cmdLogin", "onclick")]
    fid_map, entries = resolve_fids(refs, BD, STALE_REGISTRY)
    assert fid_map == {"Form_Load": "F001", "Form_KeyDown": "F002", "cmdLogin_Click": "F004"}
    # registry rewritten to the BD numbering, superseded entries gone
    assert {k: v["vba_handler"] for k, v in entries.items()} == {
        "F001": "Form_Load", "F002": "Form_KeyDown", "F004": "cmdLogin_Click"}
    assert all("_auto" not in v for v in entries.values())


def test_macro_event_matches_by_raw_value_and_records_the_note():
    fid_map, entries = resolve_fids([ref("lblMenuTrigger_Click", "lblMenuTrigger", "onclick", "macro.A_メニューバーを表示")], BD, {})
    assert fid_map == {"lblMenuTrigger_Click": "F007"}
    assert entries["F007"]["_note"] == "参照マクロ: A_メニューバーを表示"


def test_control_and_trigger_match_when_the_handler_name_differs():
    fid_map, _ = resolve_fids([ref("閉じる_Click", "cmdClose", "onclick")], BD, {})
    assert fid_map == {"閉じる_Click": "F005"}


def test_unknown_handlers_get_stable_auto_ids_that_skip_bd_ids():
    refs = [ref("Form_Open", "__form__", "onopen"), ref("btnExtra_Click", "btnExtra", "onclick")]
    fid_map, entries = resolve_fids(refs, BD, {})
    assert fid_map["btnExtra_Click"] not in {e["module_id"] for e in BD}
    assert entries[fid_map["btnExtra_Click"]]["_auto"] is True
    # same input again (as the UI's next run would see it) → same ids, no churn
    again, entries2 = resolve_fids(refs, BD, entries)
    assert again == fid_map and entries2 == entries


def test_auto_ids_do_not_depend_on_which_subset_of_handlers_is_resolved():
    registry = {}
    full = [ref("a_Click", "a", "onclick"), ref("b_Click", "b", "onclick"), ref("c_Click", "c", "onclick")]
    fid_full, registry = resolve_fids(full, [], registry)
    # a later lookup with fewer handlers (prune=False) must not renumber anything
    fid_sub, registry_after = resolve_fids(full[1:], [], registry, prune=False)
    assert fid_sub == {k: fid_full[k] for k in ("b_Click", "c_Click")}
    assert registry_after == registry


def test_prune_drops_stale_auto_entries_but_keeps_free_human_ones():
    registry = {
        "F050": {"vba_handler": "gone_Click", "vm_method_name": "F050Async", "_auto": True},
        "F051": {"vba_handler": "human_Click", "vm_method_name": "F051Async", "_note": "keep me"},
        "F004": {"vba_handler": "閉じる_Click", "vm_method_name": "F004Async"},   # id now cmdLogin's
        "_comment": "extras are preserved",
    }
    _, entries = resolve_fids([ref("cmdLogin_Click", "cmdLogin", "onclick")], BD, registry)
    assert "F050" not in entries
    assert entries["F051"]["_note"] == "keep me"
    assert entries["F004"]["vba_handler"] == "cmdLogin_Click"
    assert entries["_comment"] == "extras are preserved"
    # new auto ids never reuse a kept human id
    fid_map, _ = resolve_fids([ref("new_Click", "new", "onclick")], [], {"F000": {"vba_handler": "x"}}, prune=True)
    assert fid_map["new_Click"] != "F000"


def test_fid_for_bd_event_follows_the_skeleton_registry_then_module_id():
    stale = {"F001": {"vba_handler": "Form_KeyDown", "control": "__form__", "event": "onkeydown"},
             "F009": {"vba_handler": "lblMenuTrigger_Click", "control": "lblMenuTrigger", "event": "onclick"}}
    by_notes = {"event_id": "E002", "module_id": "F002", "notes": "Form_KeyDown", "event_trigger": "On Key Down", "type": "Form"}
    by_control = BD[5]  # macro event: notes differ from the UI handler name
    assert fid_for_bd_event(by_notes, stale) == "F001"          # patch where the skeleton put it
    assert fid_for_bd_event(by_control, stale) == "F009"
    assert fid_for_bd_event(BD[3], {}) == "F004"
    assert fid_for_bd_event({"event_id": "E012"}, {}) == "F012"


def test_normalize_event_and_macro_name():
    assert normalize_event("On Double Click") == "ondblclick"
    assert normalize_event("After Update") == "afterupdate"
    assert normalize_event("ダブルクリック時") == "ondblclick"
    assert normalize_event("onkeydown") == "onkeydown"
    assert macro_name("Macro.M_CloseSystem") == "M_CloseSystem"
    assert macro_name("参照マクロ: A_メニューバーを表示.xlsx") == "A_メニューバーを表示"
    assert macro_name("cmdClose_Click") == ""


def test_resolve_and_sync_writes_atomically_and_is_idempotent(tmp_path):
    path = tmp_path / "ui_event_map.json"
    path.write_text(json.dumps({"_comment": "UI", "Other": {"F000": {"vba_handler": "x"}}}), encoding="utf-8")
    refs = [ref("Form_Open", "__form__", "onopen"), ref("cmdLogin_Click", "cmdLogin", "onclick")]
    fid_map = resolve_and_sync("F_Login", refs, BD, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert fid_map == {"Form_Open": "F000", "cmdLogin_Click": "F004"}
    assert data["_comment"] == "UI" and data["Other"] == {"F000": {"vba_handler": "x"}}
    assert set(data["F_Login"]) == {"F000", "F004"}
    mtime = path.stat().st_mtime_ns
    assert resolve_and_sync("F_Login", refs, BD, path) == fid_map
    assert path.stat().st_mtime_ns == mtime                     # unchanged → not rewritten
    assert not list(tmp_path.glob("*.tmp"))


def test_resolve_and_sync_never_overwrites_an_unreadable_registry(tmp_path):
    path = tmp_path / "ui_event_map.json"
    path.write_text("{ not json", encoding="utf-8")
    assert resolve_and_sync("F_Login", [ref("Form_Open", "__form__", "onopen")], BD, path) == {"Form_Open": "F000"}
    assert path.read_text(encoding="utf-8") == "{ not json"
