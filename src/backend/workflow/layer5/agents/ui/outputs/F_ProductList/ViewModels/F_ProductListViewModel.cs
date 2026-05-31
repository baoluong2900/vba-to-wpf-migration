using vba_brain.UI.WPF.Services;
using System.Windows;
using System.Threading.Tasks;
using System.Linq;
using System;
using System.Windows.Input;
using vba_brain.UI.WPF.Utils;
using vba_brain.Application.Interfaces;
using vba_brain.Application.DTOs.Requests.F_ProductList;
using vba_brain.Application.DTOs.Responses.F_ProductList;

namespace vba_brain.UI.WPF.ViewModels;

/// <summary>
/// F_ProductListのViewModel。
/// </summary>
public class F_ProductListViewModel : ViewModelBase
{

    /// <summary>ウィンドウを閉じる要求イベント (DoCmd.Close相当)。</summary>
    public event EventHandler? CloseRequested;

    // ─ Commands ──
    // [F000] txtSearch[afterupdate]
    public ICommand F000Command { get; }
    // [F001] lstCategory[afterupdate]
    public ICommand F001Command { get; }
    // [F002] []
    public ICommand F002Command { get; }

    private readonly IProductListService _productListService;

    public F_ProductListViewModel(IProductListService productListService)
    {
        _productListService = productListService;
        F000Command = Cmd(async _ => await F000Async());
        F001Command = Cmd(async _ => await F001Async());
        F002Command = Cmd(async _ => await F002Async());
    }

    #region Methods (Logic Agent implements)
        /// <summary>[F000] txtSearch_AfterUpdate</summary>
    public virtual async System.Threading.Tasks.Task F000Async()
    {
        var request = new F000Request();
        var response = await _productListService.OnF000Async(request);
        if (!response.Success)
        {
            // TODO: handle error — response.Message
        }
    }

    /// <summary>[F001] lstCategory_AfterUpdate</summary>
    public virtual async System.Threading.Tasks.Task F001Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F002] btnOpenDetail_Click</summary>
    public virtual async System.Threading.Tasks.Task F002Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }
    #endregion
}
