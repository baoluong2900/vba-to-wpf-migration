using Avalonia.Controls;
using System.Windows.Input;

namespace vba_brain.UI.Avalonia.Views;

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
        KeyDown += (_, e) => viewModel.F001Command.Execute(e);
    }
}