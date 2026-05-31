using System.Windows;
using System.Windows.Controls;

namespace vba_brain.UI.WPF.Views;

/// <summary>
/// F_Menu のコードビハインド — MVVM 準拠。
/// </summary>
public partial class F_Menu : Window
{
    private readonly ViewModels.F_MenuViewModel viewModel;

    public F_Menu(ViewModels.F_MenuViewModel viewModel)
    {
        InitializeComponent();
        this.viewModel = viewModel;
        DataContext = viewModel;
        Loaded += (_, _) => viewModel.F000Command.Execute(null);
    }
}
