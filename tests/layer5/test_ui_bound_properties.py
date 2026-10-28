"""AXAML bindings ↔ ViewModel properties (agents/ui/agent_ui.UIAgent._sync_bound_properties)."""
from __future__ import annotations

from agents.ui.agent_ui import UIAgent

CONTROLS = [
    {"type": "Section", "name": "section", "controls": [
        {"type": "TextBox", "name": "txtID", "binding": "TxtID"},
        {"type": "TextBox", "name": "txtProductID", "binding": "TxtProductID"},
        {"type": "ComboBox", "name": "cboSupplier", "binding": "CboSupplier"},
        {"type": "Button", "name": "btnSave", "command": "F004Command"},
        {"type": "TextBox", "name": "weird", "binding": "Items[0].Name"},
    ]},
    {"type": "TextBox", "name": "dup", "binding": "TxtID"},
]


def test_bound_names_are_collected_recursively_in_order_without_duplicates():
    assert UIAgent._bound_property_names(CONTROLS) == ["TxtID", "TxtProductID", "CboSupplier"]


def test_missing_bound_properties_are_added():
    # txtID is an unbound Access text box filled by VBA: never inferred, but the AXAML binds it.
    vmb = {"properties": ["Pass", "Comment1"], "password_property": "Pass"}
    UIAgent._sync_bound_properties(vmb, CONTROLS)
    assert vmb["properties"] == ["Pass", "Comment1", "TxtID", "TxtProductID", "CboSupplier"]


def test_case_only_differences_take_the_axaml_spelling():
    vmb = {"properties": ["txtProductID", "cboSupplier"]}
    UIAgent._sync_bound_properties(vmb, CONTROLS)
    assert vmb["properties"] == ["TxtProductID", "CboSupplier", "TxtID"]


def test_password_property_is_left_for_the_skeleton_to_rename():
    vmb = {"properties": ["txtID"], "password_property": "txtID"}
    UIAgent._sync_bound_properties(vmb, [{"name": "txtID", "binding": "TxtID"}])
    assert vmb["properties"] == ["txtID"]


def test_missing_properties_key_is_created():
    vmb: dict = {}
    UIAgent._sync_bound_properties(vmb, [{"name": "a", "binding": "TxtA"}])
    assert vmb["properties"] == ["TxtA"]
