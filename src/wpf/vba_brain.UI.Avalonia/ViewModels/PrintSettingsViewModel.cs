using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using vba_brain.Application.DTOs;
using vba_brain.Application.Services;
using vba_brain.UI.Avalonia.Services;

namespace vba_brain.UI.Avalonia.ViewModels;

public partial class PrintSettingsViewModel : ViewModelBase
{
    private readonly IPrintService _printService;
    private readonly INavigationService _navigationService;

    [ObservableProperty]
    private long _seqNo;

    [ObservableProperty]
    private string _selectedDocType = "Invoice";

    [ObservableProperty]
    private string _operatorName = "System Operator";

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    [ObservableProperty]
    private bool _isPrinting;

    public List<string> DocumentTypes { get; } = new() { "Quote", "Invoice", "Delivery" };

    public PrintSettingsViewModel(IPrintService printService, INavigationService navigationService)
    {
        _printService = printService;
        _navigationService = navigationService;
    }

    public void Initialize(long seqNo)
    {
        SeqNo = seqNo;
        StatusMessage = string.Empty;
    }

    [RelayCommand]
    private async Task PrintAsync()
    {
        if (string.IsNullOrWhiteSpace(OperatorName))
        {
            StatusMessage = "Operator Name is required.";
            return;
        }

        StatusMessage = "Simulating layout generation and printing...";
        IsPrinting = true;
        await Task.Delay(1200); // Simulate printing time

        var request = new PrintRequestDto
        {
            SeqNo = SeqNo,
            DocType = SelectedDocType,
            OperatorName = OperatorName
        };

        try
        {
            var success = await _printService.PrintDocumentAsync(request);
            if (success)
            {
                StatusMessage = $"Successfully printed {SelectedDocType} document and logged print history!";
            }
            else
            {
                StatusMessage = "Failed to log printing history. Document simulated but database record failed.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error during printing operation: {ex.Message}";
        }
        finally
        {
            IsPrinting = false;
        }
    }

    [RelayCommand]
    private void Cancel()
    {
        _navigationService.NavigateTo<MainViewModel>();
    }
}
