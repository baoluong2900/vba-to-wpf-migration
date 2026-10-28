using Avalonia.Controls;

namespace vba_brain.UI.Avalonia.Views;

/// <summary>
/// F_Login のコードビハインド — MVVM 準拠。
/// </summary>
public partial class FLoginView : Window
{
    /// <summary>Used by the XAML loader and previewer; the app builds the view with its view model.</summary>
    public FLoginView()
    {
        InitializeComponent();
    }

    public FLoginView(ViewModels.FLoginViewModel viewModel) : this()
    {
        DataContext = viewModel;
        Loaded += (_, _) => viewModel.F000Command.Execute(null);
        KeyDown += (_, e) => viewModel.F001Command.Execute(e);
        viewModel.CloseRequested += (_, _) => Close();
    }
}
