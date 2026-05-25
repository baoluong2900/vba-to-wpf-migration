using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using vba_brain.UI.Avalonia.Services;

namespace vba_brain.UI.Avalonia.ViewModels;

public partial class LoginViewModel : ViewModelBase
{
    private readonly INavigationService _navigationService;

    [ObservableProperty]
    private string _username = string.Empty;

    [ObservableProperty]
    private string _password = string.Empty;

    [ObservableProperty]
    private string _errorMessage = string.Empty;

    [ObservableProperty]
    private bool _isBusy;

    public LoginViewModel(INavigationService navigationService)
    {
        _navigationService = navigationService;
    }

    [RelayCommand]
    private async Task LoginAsync()
    {
        ErrorMessage = string.Empty;
        IsBusy = true;

        // Simulate network/database authentication delay
        await Task.Delay(800);

        if (string.IsNullOrWhiteSpace(Username) || string.IsNullOrWhiteSpace(Password))
        {
            ErrorMessage = "Please enter both username and password.";
            IsBusy = false;
            return;
        }

        // Standard mock authentication for demonstration
        if (Username.ToLower() == "admin" && Password == "admin")
        {
            IsBusy = false;
            _navigationService.NavigateTo<MainViewModel>();
        }
        else
        {
            ErrorMessage = "Invalid credentials. Try admin / admin.";
            IsBusy = false;
        }
    }
}
