using System.Windows;
using System.Windows.Controls;

namespace vba_brain.UI.WPF.Views;

/// <summary>
/// F_TestForm のコードビハインド — MVVM 準拠。
/// </summary>
public partial class F_TestForm : Window
{
    private readonly ViewModels.F_TestFormViewModel viewModel;

    public F_TestForm(ViewModels.F_TestFormViewModel viewModel)
    {
        InitializeComponent();
        this.viewModel = viewModel;
        DataContext = viewModel;
        Loaded += (_, _) => viewModel.F000Command.Execute(null);
    }

    // ── PasswordBox: WPF không support binding Password → sync thủ công ──
    private void PasswordBox_PasswordChanged(object sender, RoutedEventArgs e)
    {
        if (sender is PasswordBox pb)
        {
            viewModel.TxtPass = pb.Password;
            viewModel.F001Command.Execute(null);
        }
    }
}
