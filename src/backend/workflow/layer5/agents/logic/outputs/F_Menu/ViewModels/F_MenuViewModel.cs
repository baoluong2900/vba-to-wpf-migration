using vba_brain.UI.WPF.Services;
using System.Windows;
using System.Threading.Tasks;
using System.Linq;
using System;
using System.Windows.Input;
using vba_brain.UI.WPF.Utils;
using vba_brain.Application.Interfaces;
using vba_brain.Application.DTOs.Requests.F_Menu;
using vba_brain.Application.DTOs.Responses.F_Menu;

namespace vba_brain.UI.WPF.ViewModels;

/// <summary>
/// F_MenuのViewModel。
/// </summary>
public class F_MenuViewModel : ViewModelBase
{

    /// <summary>ウィンドウを閉じる要求イベント (DoCmd.Close相当)。</summary>
    public event EventHandler? CloseRequested;

    // ─ Commands ──
    // [F000] __form__[onopen]
    public ICommand F000Command { get; }
    // [F001] []
    public ICommand F001Command { get; }
    // [F002] []
    public ICommand F002Command { get; }
    // [F003] []
    public ICommand F003Command { get; }

    private readonly IMenuService _menuService;

    public F_MenuViewModel(IMenuService menuService)
    {
        _menuService = menuService;
        F000Command = Cmd(async _ => await F000Async());
        F001Command = Cmd(async _ => await F001Async());
        F002Command = Cmd(async _ => await F002Async());
        F003Command = Cmd(async _ => await F003Async());
    }

    #region Methods (Logic Agent implements)
        /// <summary>[F000] Form_Open</summary>
    public virtual async System.Threading.Tasks.Task F000Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F001] btnProductList_Click</summary>
    public virtual async System.Threading.Tasks.Task F001Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F002] btnOrderEntry_Click</summary>
    public virtual async System.Threading.Tasks.Task F002Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F003] Macro.M_CloseSystem</summary>
    public virtual async System.Threading.Tasks.Task F003Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }
    #endregion
}
