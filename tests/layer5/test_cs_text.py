"""Literal/comment-aware C# helpers used to patch generated ViewModels (layer5/core/cs_text.py)."""
from __future__ import annotations

from core.cs_text import (
    declares_namespace,
    declares_type,
    extract_method_body,
    find_matching,
    mask_non_code,
    replace_method_body,
    split_top_level,
)

VM = '''\
public class FLoginViewModel : ViewModelBase
{
    public FLoginViewModel()
    {
        F003Command = Cmd(async _ => await F003Async());
    }

    /// <summary>[F003] txtPass_AfterUpdate — "{" in a doc comment</summary>
    public virtual async System.Threading.Tasks.Task F003Async()
    {
        var s = "}";               // a brace in a string
        var c = '{';
        var t = $"{TxtID} {{x}}";
        if (s == "x") { Debug.WriteLine(@"a ""}"" b"); }
    }

    public virtual async System.Threading.Tasks.Task F004Async(global::Avalonia.Input.KeyEventArgs? e = null)
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }
}
'''


def test_mask_keeps_length_and_blanks_literals_and_comments():
    masked = mask_non_code(VM)
    assert len(masked) == len(VM)
    assert masked.count("\n") == VM.count("\n")
    assert '"}"' not in masked and "'{'" not in masked and "a brace in a string" not in masked
    assert "public virtual async" in masked


def test_find_matching_ignores_brackets_inside_literals():
    start = VM.index("{", VM.index("Task F003Async()"))
    end = find_matching(VM, start)
    assert VM[end + 1:].lstrip().startswith("public virtual async System.Threading.Tasks.Task F004Async")


def test_replace_method_body_swaps_only_the_declared_method():
    new, ok = replace_method_body(VM, "F003Async", 'Debug.WriteLine("}");\nawait Task.CompletedTask;')
    assert ok
    assert 'var s = "}";' not in new
    assert '        Debug.WriteLine("}");\n        await Task.CompletedTask;\n    }' in new
    assert "Cmd(async _ => await F003Async());" in new          # call site untouched
    assert "F004Async(global::Avalonia.Input.KeyEventArgs? e = null)" in new
    assert new.count("{") - new.count("}") == VM.count("{") - VM.count("}")


def test_replace_method_body_handles_parameters_and_missing_methods():
    new, ok = replace_method_body(VM, "F004Async", "e?.Handled = true;")
    assert ok and "        e?.Handled = true;\n    }" in new
    same, ok = replace_method_body(VM, "F999Async", "x();")
    assert not ok and same == VM


def test_extract_method_body_from_a_full_llm_method():
    code = '''
    // generated
    public virtual async System.Threading.Tasks.Task F003Async()
    {
        if (string.IsNullOrEmpty(TxtPass)) { return; }
        var msg = "public static void Main() {}";
    }'''
    assert extract_method_body(code) == (
        'if (string.IsNullOrEmpty(TxtPass)) { return; }\nvar msg = "public static void Main() {}";'
    )


def test_extract_method_body_leaves_plain_bodies_alone():
    body = 'var note = "public value";\nif (x) { y(); }'
    assert extract_method_body(body) == body


def test_split_top_level_respects_nesting_and_strings():
    text = 'Show(string.Format("{0}, {1}", a, b), "Title, here", X.OK)'
    open_paren = text.index("(")
    parts = split_top_level(text, open_paren + 1, find_matching(text, open_paren))
    assert parts == ['string.Format("{0}, {1}", a, b)', '"Title, here"', "X.OK"]


def test_declaration_lookups(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "DTOs").mkdir()
    (tmp_path / "DTOs" / "Req.cs").write_text("namespace vba_brain.Application.DTOs.Requests.F_Login\n{\n}\n", encoding="utf-8")
    (tmp_path / "IFoo.cs").write_text("namespace X;\npublic interface IFooService { }\n", encoding="utf-8")
    (tmp_path / "bin" / "Stale.cs").write_text("namespace Only.In.Bin;\n", encoding="utf-8")
    assert declares_namespace("vba_brain.Application.DTOs.Requests.F_Login", [tmp_path])
    assert not declares_namespace("vba_brain.Application.DTOs.Requests.F_Menu", [tmp_path])
    assert not declares_namespace("Only.In.Bin", [tmp_path])
    assert declares_type("IFooService", [tmp_path]) and not declares_type("IBarService", [tmp_path])
    assert not declares_namespace("X", [tmp_path / "missing"])
