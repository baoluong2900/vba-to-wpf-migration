"""Deterministic ViewModel / code-behind skeletons (layer5/agents/ui/tool_skeleton.py), no LLM, no registry writes."""
from __future__ import annotations

from agents.ui.tool_skeleton import SkeletonTool
from pipeline.avalonia_cs import to_avalonia_cs

FORM = "F_UnitTestForm"   # no service contract / registry entry exists for it


def codebehind(handlers, fid_map, control_events=None):
    return to_avalonia_cs(SkeletonTool().gen_codebehind(
        FORM, {"event_handlers": handlers},
        class_name_override="UnitTestView", vm_class_name_override="UnitTestViewModel",
        fid_map=fid_map, control_events=control_events,
    ))


def test_codebehind_has_a_parameterless_constructor_and_chains_it():
    cs = codebehind(
        [{"method": "Form_Open", "event": "onopen", "wpf_event": "Loaded", "control": "__form__"}],
        {"Form_Open": "F000"},
    )
    assert "    public UnitTestView()\n    {\n        InitializeComponent();\n    }" in cs
    assert "public UnitTestView(ViewModels.UnitTestViewModel viewModel) : this()" in cs
    assert "DataContext = viewModel;" in cs
    assert "Loaded += (_, _) => viewModel.F000Command.Execute(null);" in cs
    assert cs.rstrip().endswith("viewModel.CloseRequested += (_, _) => Close();\n    }\n}")
    assert "using System.Windows" not in cs and "private readonly" not in cs
    assert "namespace vba_brain.UI.Avalonia.Views;" in cs


def test_codebehind_never_subscribes_raw_vba_event_names():
    cs = codebehind(
        [
            {"method": "Form_KeyDown", "event": "onkeydown", "wpf_event": "PreviewKeyDown", "control": "__form__"},
            {"method": "Form_BeforeUpdate", "event": "beforeupdate", "wpf_event": "", "control": "__form__"},
            {"method": "Form_Current", "event": "oncurrent", "wpf_event": "oncurrent", "control": "__form__"},
        ],
        {"Form_KeyDown": "F001", "Form_BeforeUpdate": "F002", "Form_Current": "F003"},
        control_events=[("txtPass", "LostFocus", "F004Command")],
    )
    assert "KeyDown += (_, e) => viewModel.F001Command.Execute(e);" in cs
    assert "beforeupdate +=" not in cs and "oncurrent +=" not in cs
    assert cs.count("// TODO: Access form event") == 2
    assert "txtPass.LostFocus += (_, _) => viewModel.F004Command.Execute(null);" in cs


def test_viewmodel_close_commands_raise_close_requested():
    vm = to_avalonia_cs(SkeletonTool().gen_viewmodel(
        FORM,
        {
            "properties": [],
            "commands": ["F000Command", "ExitCommand"],
            "event_handlers": [{"method": "btnClose_Click", "event": "onclick", "control": "btnClose"}],
        },
        class_name_override="UnitTestViewModel",
        fid_map={"btnClose_Click": "F000"},
    ))
    assert "public event EventHandler? CloseRequested;" in vm
    assert "F000Command = Cmd(async _ => await F000Async());" in vm
    assert "ExitCommand = Cmd(_ => CloseRequested?.Invoke(this, EventArgs.Empty));" in vm
    body = vm[vm.index("Task F000Async()"):]
    assert body.index("CloseRequested?.Invoke(this, EventArgs.Empty);") < body.index("}")
    assert "RequestClose" not in vm                                # already raised elsewhere
    assert "using vba_brain.Application" not in vm and "private readonly" not in vm   # no contract → no DI


def test_viewmodel_without_close_handler_still_uses_the_event_and_key_args_are_forwarded():
    vm = to_avalonia_cs(SkeletonTool().gen_viewmodel(
        FORM,
        {
            "properties": ["Pass", "PassengerName"],
            "password_property": "Pass",
            "commands": [],
            "event_handlers": [{"method": "Form_KeyDown", "event": "onkeydown", "control": "__form__"}],
        },
        class_name_override="UnitTestViewModel",
        fid_map={"Form_KeyDown": "F001"},
    ))
    assert "protected void RequestClose() => CloseRequested?.Invoke(this, EventArgs.Empty);" in vm
    assert "F001Async(global::Avalonia.Input.KeyEventArgs? e = null)" in vm
    assert "F001Command = Cmd(async p => await F001Async(p as global::Avalonia.Input.KeyEventArgs));" in vm
    assert "using Avalonia.Input;" in vm
    assert "public string TxtPass" in vm and "public string PassengerName" in vm
    assert "public string Pass " not in vm
