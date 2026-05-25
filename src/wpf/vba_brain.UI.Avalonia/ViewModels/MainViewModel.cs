using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Extensions.DependencyInjection;
using vba_brain.Application.DTOs;
using vba_brain.Application.Services;
using vba_brain.UI.Avalonia.Services;

namespace vba_brain.UI.Avalonia.ViewModels;

public partial class MainViewModel : ViewModelBase
{
    private readonly IAfterMainService _afterMainService;
    private readonly INavigationService _navigationService;
    private readonly IServiceProvider _serviceProvider;

    [ObservableProperty]
    private ObservableCollection<AfterMainDto> _items = new();

    [ObservableProperty]
    private AfterMainDto? _selectedItem;

    [ObservableProperty]
    private string _searchText = string.Empty;

    [ObservableProperty]
    private string _selectedServiceTypeFilter = "All";

    [ObservableProperty]
    private string _selectedPaymentFlagFilter = "All";

    [ObservableProperty]
    private bool _isBusy;

    public List<string> ServiceTypeFilters { get; } = new() { "All", "Paid", "Free", "Defect" };
    public List<string> PaymentFlagFilters { get; } = new() { "All", "Unpaid", "Paid", "PartiallyPaid" };

    private List<AfterMainDto> _allCachedItems = new();

    public MainViewModel(
        IAfterMainService afterMainService,
        INavigationService navigationService,
        IServiceProvider serviceProvider)
    {
        _afterMainService = afterMainService;
        _navigationService = navigationService;
        _serviceProvider = serviceProvider;
    }

    [RelayCommand]
    public async Task LoadDataAsync()
    {
        IsBusy = true;
        try
        {
            var data = await _afterMainService.GetAllAsync();
            _allCachedItems = data.ToList();
            ApplyFilters();
        }
        catch (Exception ex)
        {
            // In a production app, log this using Serilog or display a dialog
            System.Diagnostics.Debug.WriteLine($"Error loading data: {ex.Message}");
        }
        finally
        {
            IsBusy = false;
        }
    }

    [RelayCommand]
    private void ApplyFilters()
    {
        var filtered = _allCachedItems.AsEnumerable();

        if (!string.IsNullOrWhiteSpace(SearchText))
        {
            filtered = filtered.Where(i => 
                i.CustomerNm.Contains(SearchText, StringComparison.OrdinalIgnoreCase) || 
                i.AfterCd.Contains(SearchText, StringComparison.OrdinalIgnoreCase));
        }

        if (SelectedServiceTypeFilter != "All")
        {
            filtered = filtered.Where(i => i.ServiceType == SelectedServiceTypeFilter);
        }

        if (SelectedPaymentFlagFilter != "All")
        {
            filtered = filtered.Where(i => i.PaymentFlg == SelectedPaymentFlagFilter);
        }

        Items = new ObservableCollection<AfterMainDto>(filtered);
    }

    [RelayCommand]
    private void NavigateToRegister()
    {
        var vm = _serviceProvider.GetRequiredService<RegistrationViewModel>();
        _navigationService.NavigateTo(vm);
    }

    [RelayCommand]
    private async Task NavigateToEditAsync()
    {
        if (SelectedItem == null) return;
        
        var vm = _serviceProvider.GetRequiredService<EditViewModel>();
        await vm.InitializeAsync(SelectedItem.SeqNo);
        _navigationService.NavigateTo(vm);
    }

    [RelayCommand]
    private void NavigateToPrint()
    {
        if (SelectedItem == null) return;

        var vm = _serviceProvider.GetRequiredService<PrintSettingsViewModel>();
        vm.Initialize(SelectedItem.SeqNo);
        _navigationService.NavigateTo(vm);
    }

    [RelayCommand]
    private void NavigateToAnalytics()
    {
        var vm = _serviceProvider.GetRequiredService<AnalyticsViewModel>();
        _navigationService.NavigateTo(vm);
    }

    [RelayCommand]
    private void Logout()
    {
        _navigationService.NavigateTo<LoginViewModel>();
    }
}
