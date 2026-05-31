using System;
// using vba_brain.UI.Avalonia.ViewModels;

namespace vba_brain.UI.Avalonia.Services;

public interface INavigationService
{
    // void Setup(MainWindowViewModel mainViewModel);
    // void NavigateTo<TViewModel>() where TViewModel : ViewModelBase;
    // void NavigateTo(ViewModelBase viewModel);
}

public class NavigationService : INavigationService
{
    /*
    private readonly Func<Type, ViewModelBase> _viewModelFactory;
    private MainWindowViewModel? _mainViewModel;

    public NavigationService(Func<Type, ViewModelBase> viewModelFactory)
    {
        _viewModelFactory = viewModelFactory;
    }

    public void Setup(MainWindowViewModel mainViewModel)
    {
        _mainViewModel = mainViewModel;
    }

    public void NavigateTo<TViewModel>() where TViewModel : ViewModelBase
    {
        if (_mainViewModel == null)
            throw new InvalidOperationException("NavigationService has not been initialized with MainWindowViewModel.");
        
        var viewModel = _viewModelFactory(typeof(TViewModel));
        _mainViewModel.CurrentPage = viewModel;
    }

    public void NavigateTo(ViewModelBase viewModel)
    {
        if (_mainViewModel == null)
            throw new InvalidOperationException("NavigationService has not been initialized with MainWindowViewModel.");
        
        _mainViewModel.CurrentPage = viewModel;
    }
    */
}
