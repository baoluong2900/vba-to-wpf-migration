"""WPF → Avalonia C# post-processor (layer5/pipeline/avalonia_cs.py)."""
from __future__ import annotations

from pipeline.avalonia_cs import rewrite_messagebox_statements, to_avalonia_cs


def test_statement_messagebox_becomes_debug_writeline():
    code = '''    MessageBox.Show(
        string.Format("{0}, {1}", a, b),
        "確認", MessageBoxButton.OK, MessageBoxImage.Warning);
    if (x) MessageBox.Show("a");
    else MessageBox.Show(response.Message ?? "Error");
    Cmd(_ => MessageBox.Show("lambda"));'''
    out = rewrite_messagebox_statements(code)
    assert "MessageBox" not in out
    assert 'System.Diagnostics.Debug.WriteLine(string.Format("{0}, {1}", a, b));' in out
    assert 'if (x) System.Diagnostics.Debug.WriteLine("a");' in out
    assert 'else System.Diagnostics.Debug.WriteLine(response.Message ?? "Error");' in out
    assert 'Cmd(_ => System.Diagnostics.Debug.WriteLine("lambda"));' in out


def test_messagebox_whose_result_is_used_is_left_alone():
    code = 'var result = MessageBox.Show("終了しますか？", "確認", MessageBoxButton.YesNo);\n' \
           'if (MessageBox.Show("q") == MessageBoxResult.Yes) { }'
    assert rewrite_messagebox_statements(code) == code


def test_messagebox_inside_strings_and_comments_is_untouched():
    code = 'var s = "MessageBox.Show(\\"x\\");"; // MessageBox.Show("y");'
    assert rewrite_messagebox_statements(code) == code


def test_to_avalonia_cs_maps_namespaces_input_types_and_shutdown():
    code = (
        "using System.Windows;\n"
        "using System.Windows.Controls;\n"
        "using System.Windows.Input;\n"
        "namespace vba_brain.UI.WPF.ViewModels;\n"
        "class X {\n"
        "    void A(System.Windows.Input.KeyEventArgs e) { if (e.Key == System.Windows.Input.Key.F11) e.Handled = true; }\n"
        "    void B() { System.Windows.Application.Current.Shutdown(); PreviewKeyUp += (_, _) => {}; }\n"
        "}\n"
    )
    out = to_avalonia_cs(code)
    assert out.count("using Avalonia.Controls;") == 1
    assert "using System.Windows.Input;" in out                  # ICommand lives there
    assert "namespace vba_brain.UI.Avalonia.ViewModels;" in out
    assert "global::Avalonia.Input.KeyEventArgs e" in out
    assert "global::Avalonia.Input.Key.F11" in out
    assert "IClassicDesktopStyleApplicationLifetime)?.Shutdown()" in out
    assert "System.Windows.Application" not in out
    assert "KeyUp +=" in out and "PreviewKeyUp" not in out


def test_to_avalonia_cs_is_idempotent():
    code = 'namespace vba_brain.UI.WPF.Views;\nclass V { void F() { MessageBox.Show("x"); Application.Current.Shutdown(); } }\n'
    once = to_avalonia_cs(code)
    assert to_avalonia_cs(once) == once
