using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using vba_brain.Application.DTOs;
using vba_brain.Application.Services;
using vba_brain.UI.Avalonia.Services;

namespace vba_brain.UI.Avalonia.ViewModels;

public partial class RegistrationViewModel : ViewModelBase
{
    private readonly IAfterMainService _afterMainService;
    private readonly INavigationService _navigationService;

    [ObservableProperty]
    private string _afterCd = string.Empty;

    [ObservableProperty]
    private string _customerNm = string.Empty;

    [ObservableProperty]
    private string _selectedServiceType = "Paid";

    [ObservableProperty]
    private decimal _paymentAmt;

    [ObservableProperty]
    private string _selectedPaymentFlg = "Unpaid";

    [ObservableProperty]
    private string _districtCd = string.Empty;

    [ObservableProperty]
    private DateTimeOffset _receiveDtOffset = DateTimeOffset.Now;

    [ObservableProperty]
    private string _errorMessage = string.Empty;

    [ObservableProperty]
    private bool _isBusy;

    public List<string> ServiceTypes { get; } = new() { "Paid", "Free", "Defect" };
    public List<string> PaymentFlags { get; } = new() { "Unpaid", "Paid", "PartiallyPaid" };

    public RegistrationViewModel(IAfterMainService afterMainService, INavigationService navigationService)
    {
        _afterMainService = afterMainService;
        _navigationService = navigationService;
    }

    [RelayCommand]
    private async Task SaveAsync()
    {
        if (string.IsNullOrWhiteSpace(AfterCd) || string.IsNullOrWhiteSpace(CustomerNm) || string.IsNullOrWhiteSpace(DistrictCd))
        {
            ErrorMessage = "Please fill in all required fields (After Code, Customer Name, District Code).";
            return;
        }

        ErrorMessage = string.Empty;
        IsBusy = true;

        var dto = new AfterMainDto
        {
            SeqNo = 0,
            AfterCd = AfterCd,
            CustomerNm = CustomerNm,
            ServiceType = SelectedServiceType,
            PaymentAmt = PaymentAmt,
            PaymentFlg = SelectedPaymentFlg,
            DistrictCd = DistrictCd,
            ReceiveDt = ReceiveDtOffset.DateTime
        };

        try
        {
            var success = await _afterMainService.SaveAsync(dto);
            if (success)
            {
                _navigationService.NavigateTo<MainViewModel>();
            }
            else
            {
                ErrorMessage = "Failed to save registration record.";
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Error: {ex.Message}";
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
