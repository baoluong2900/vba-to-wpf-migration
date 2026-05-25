using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using vba_brain.Application.Services;
using vba_brain.Domain.Entities;
using vba_brain.UI.Avalonia.Services;

namespace vba_brain.UI.Avalonia.ViewModels;

public partial class AnalyticsViewModel : ViewModelBase
{
    private readonly IAnalyticsService _analyticsService;
    private readonly INavigationService _navigationService;

    [ObservableProperty]
    private string _startPeriod = DateTime.Now.AddMonths(-6).ToString("yyyy-MM");

    [ObservableProperty]
    private string _endPeriod = DateTime.Now.ToString("yyyy-MM");

    [ObservableProperty]
    private ObservableCollection<AnalyticsEntity> _data = new();

    [ObservableProperty]
    private decimal _totalAmountSum;

    [ObservableProperty]
    private int _totalCountSum;

    [ObservableProperty]
    private string _errorMessage = string.Empty;

    [ObservableProperty]
    private bool _isBusy;

    public AnalyticsViewModel(IAnalyticsService analyticsService, INavigationService navigationService)
    {
        _analyticsService = analyticsService;
        _navigationService = navigationService;
    }

    [RelayCommand]
    private async Task LoadAnalyticsAsync()
    {
        ErrorMessage = string.Empty;
        IsBusy = true;
        try
        {
            var list = await _analyticsService.GetAggregatedDataAsync(StartPeriod, EndPeriod);
            var analyticsList = list.ToList();
            Data = new ObservableCollection<AnalyticsEntity>(analyticsList);

            TotalAmountSum = analyticsList.Sum(x => x.TotalAmount);
            TotalCountSum = analyticsList.Sum(x => x.Count);
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Error loading analytics: {ex.Message}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    [RelayCommand]
    private void Cancel()
    {
        _navigationService.NavigateTo<MainViewModel>();
    }
}
