using vba_brain.UI.WPF.Services;
using System.Windows;
using System.Threading.Tasks;
using System.Linq;
using System;
using System.Windows.Input;
using vba_brain.UI.WPF.Utils;
using vba_brain.Application.Interfaces;
using vba_brain.Application.DTOs.Requests.F_ProductDetail;
using vba_brain.Application.DTOs.Responses.F_ProductDetail;

namespace vba_brain.UI.WPF.ViewModels;

/// <summary>
/// F_ProductDetailのViewModel。
/// </summary>
public class F_ProductDetailViewModel : ViewModelBase
{

    // ─ Properties ──
    // [QUERY]  from 
    private string _txtProductID = string.Empty;
    public string txtProductID { get => _txtProductID; set => SetProperty(ref _txtProductID, value); }

    // [QUERY]  from 
    private string _txtProductName = string.Empty;
    public string txtProductName { get => _txtProductName; set => SetProperty(ref _txtProductName, value); }

    // [QUERY]  from 
    private string _optStatus = string.Empty;
    public string optStatus { get => _optStatus; set => SetProperty(ref _optStatus, value); }

    /// <summary>ウィンドウを閉じる要求イベント (DoCmd.Close相当)。</summary>
    public event EventHandler? CloseRequested;

    // ─ Commands ──
    // [F000] __form__[beforeupdate]
    public ICommand F000Command { get; }
    // [F001] []
    public ICommand F001Command { get; }
    // [F002] []
    public ICommand F002Command { get; }

    private readonly IProductDetailService _productDetailService;

    public F_ProductDetailViewModel(IProductDetailService productDetailService)
    {
        _productDetailService = productDetailService;
        F000Command = Cmd(async _ => await F000Async());
        F001Command = Cmd(async _ => await F001Async());
        F002Command = Cmd(async _ => await F002Async());
    }

    #region Methods (Logic Agent implements)
        /// <summary>[F000] Form_BeforeUpdate</summary>
    public virtual async System.Threading.Tasks.Task F000Async()
    {
        var request = new F000Request();
        var response = await _productDetailService.OnF000Async(request);
        if (!response.Success)
        {
            // TODO: handle error — response.Message
        }
    }

    /// <summary>[F001] btnSave_Click</summary>
    public virtual async System.Threading.Tasks.Task F001Async()
    {
        if (sender is FrameworkElement element && element.DataContext is ViewModels.F000ViewModel vm)
            {
                var productName = vm.TxtProductName;
                if (string.IsNullOrEmpty(productName))
                {
                    MessageBox.Show("Product name cannot be empty!", "警告", MessageBoxButton.OK, MessageBoxImage.Warning);
                    e.Handled = true;
                }
            }
    }

    /// <summary>[F002] btnDelete_Click</summary>
    public virtual async System.Threading.Tasks.Task F002Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }
    #endregion
}
