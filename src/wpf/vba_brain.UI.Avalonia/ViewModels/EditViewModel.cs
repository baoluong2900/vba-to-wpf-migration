using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using vba_brain.Application.DTOs;
using vba_brain.Application.Services;
using vba_brain.Domain.Entities;
using vba_brain.UI.Avalonia.Services;

namespace vba_brain.UI.Avalonia.ViewModels;

public partial class EditViewModel : ViewModelBase
{
    private readonly IAfterMainService _afterMainService;
    private readonly IPaymentService _paymentService;
    private readonly IPrintService _printService;
    private readonly INavigationService _navigationService;

    [ObservableProperty]
    private long _seqNo;

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
    private ObservableCollection<PaymentDto> _payments = new();

    [ObservableProperty]
    private ObservableCollection<PrintDocumentEntity> _printHistory = new();

    [ObservableProperty]
    private decimal _newPaymentAmount;

    [ObservableProperty]
    private string _newPaymentNote = string.Empty;

    [ObservableProperty]
    private string _errorMessage = string.Empty;

    [ObservableProperty]
    private bool _isBusy;

    public List<string> ServiceTypes { get; } = new() { "Paid", "Free", "Defect" };
    public List<string> PaymentFlags { get; } = new() { "Unpaid", "Paid", "PartiallyPaid" };

    public EditViewModel(
        IAfterMainService afterMainService,
        IPaymentService paymentService,
        IPrintService printService,
        INavigationService navigationService)
    {
        _afterMainService = afterMainService;
        _paymentService = paymentService;
        _printService = printService;
        _navigationService = navigationService;
    }

    public async Task InitializeAsync(long seqNo)
    {
        SeqNo = seqNo;
        IsBusy = true;
        try
        {
            var dto = await _afterMainService.GetBySeqNoAsync(seqNo);
            if (dto != null)
            {
                AfterCd = dto.AfterCd;
                CustomerNm = dto.CustomerNm;
                SelectedServiceType = dto.ServiceType;
                PaymentAmt = dto.PaymentAmt;
                SelectedPaymentFlg = dto.PaymentFlg;
                DistrictCd = dto.DistrictCd;
                ReceiveDtOffset = new DateTimeOffset(dto.ReceiveDt);
            }

            await LoadRelatedDataAsync();
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Error loading record: {ex.Message}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LoadRelatedDataAsync()
    {
        var payList = await _paymentService.GetBySeqNoAsync(SeqNo);
        Payments = new ObservableCollection<PaymentDto>(payList);

        var printList = await _printService.GetHistoryBySeqNoAsync(SeqNo);
        PrintHistory = new ObservableCollection<PrintDocumentEntity>(printList);
    }

    [RelayCommand]
    private async Task UpdateAsync()
    {
        if (string.IsNullOrWhiteSpace(AfterCd) || string.IsNullOrWhiteSpace(CustomerNm) || string.IsNullOrWhiteSpace(DistrictCd))
        {
            ErrorMessage = "Please fill in all required fields.";
            return;
        }

        ErrorMessage = string.Empty;
        IsBusy = true;

        var dto = new AfterMainDto
        {
            SeqNo = SeqNo,
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
                ErrorMessage = "Failed to update record.";
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Error saving: {ex.Message}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    [RelayCommand]
    private async Task AddPaymentAsync()
    {
        if (NewPaymentAmount <= 0)
        {
            ErrorMessage = "Payment amount must be greater than zero.";
            return;
        }

        ErrorMessage = string.Empty;
        IsBusy = true;

        var payDto = new PaymentDto
        {
            PaymentId = 0,
            SeqNo = SeqNo,
            Amount = NewPaymentAmount,
            PaymentDt = DateTime.UtcNow,
            Note = NewPaymentNote
        };

        try
        {
            var success = await _paymentService.ProcessPaymentAsync(payDto);
            if (success)
            {
                // Clear inputs
                NewPaymentAmount = 0;
                NewPaymentNote = string.Empty;

                // Reload related data
                await LoadRelatedDataAsync();

                // Recalculate payment status flag based on total payments
                decimal totalPaid = 0;
                foreach (var p in Payments)
                {
                    totalPaid += p.Amount;
                }

                if (totalPaid >= PaymentAmt)
                {
                    SelectedPaymentFlg = "Paid";
                }
                else if (totalPaid > 0)
                {
                    SelectedPaymentFlg = "PartiallyPaid";
                }
                else
                {
                    SelectedPaymentFlg = "Unpaid";
                }
            }
            else
            {
                ErrorMessage = "Failed to process payment.";
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Error adding payment: {ex.Message}";
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
