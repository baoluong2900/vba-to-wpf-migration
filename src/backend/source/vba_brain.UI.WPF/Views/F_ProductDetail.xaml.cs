using System.Windows;
using System.Windows.Controls;

namespace vba_brain.UI.WPF.Views;

/// <summary>
/// F_ProductDetail のコードビハインド — MVVM 準拠。
/// </summary>
public partial class F_ProductDetail : Window
{
    private readonly ViewModels.F_ProductDetailViewModel viewModel;

    public F_ProductDetail(ViewModels.F_ProductDetailViewModel viewModel)
    {
        InitializeComponent();
        this.viewModel = viewModel;
        DataContext = viewModel;
        beforeupdate += (_, _) => viewModel.F000Command.Execute(null);
    }
}
