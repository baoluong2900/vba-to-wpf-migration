using CommunityToolkit.Mvvm.ComponentModel;

namespace vba_brain.UI.Avalonia.ViewModels;

public partial class MainWindowViewModel : ViewModelBase
{
    [ObservableProperty]
    private ViewModelBase? _currentPage;

    public MainWindowViewModel()
    {
    }
}
