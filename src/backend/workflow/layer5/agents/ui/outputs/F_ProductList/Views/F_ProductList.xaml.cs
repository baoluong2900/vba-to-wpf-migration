using System.Windows;
using System.Windows.Controls;

namespace vba_brain.UI.WPF.Views;

/// <summary>
/// F_ProductList のコードビハインド — MVVM 準拠。
/// </summary>
public partial class F_ProductList : Window
{
    private readonly ViewModels.F_ProductListViewModel viewModel;

    public F_ProductList(ViewModels.F_ProductListViewModel viewModel)
    {
        InitializeComponent();
        this.viewModel = viewModel;
        DataContext = viewModel;
    }

    // ── PasswordBox: WPF không support binding Password → sync thủ công ──
    private void PasswordBox_PasswordChanged(object sender, RoutedEventArgs e)
    {
        if (sender is PasswordBox pb)
        {
            viewModel.TxtPass = pb.Password;
            viewModel.F000Command.Execute(null);
        }
    }
}
