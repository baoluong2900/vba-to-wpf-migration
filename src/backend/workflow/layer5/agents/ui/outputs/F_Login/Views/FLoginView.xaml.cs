using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace vba_brain.UI.WPF.Views;

/// <summary>
/// F_Login のコードビハインド — MVVM 準拠。
/// </summary>
public partial class FLoginView : Window
{
    private readonly ViewModels.FLoginViewModel viewModel;

    public FLoginView(ViewModels.FLoginViewModel viewModel)
    {
        InitializeComponent();
        this.viewModel = viewModel;
        DataContext = viewModel;
        Loaded += (_, _) => viewModel.F000Command.Execute(null);
        PreviewKeyDown += (_, e) => viewModel.F001Command.Execute(e);
        ContentRendered += (_, _) => viewModel.F002Command.Execute(null);
    }

    // ── PasswordBox: WPF không support binding Password → sync thủ công ──
    private void PasswordBox_PasswordChanged(object sender, RoutedEventArgs e)
    {
        if (sender is PasswordBox pb)
        {
            viewModel.TxtPass = pb.Password;
            viewModel.F003Command.Execute(null);
        }
    }
}
