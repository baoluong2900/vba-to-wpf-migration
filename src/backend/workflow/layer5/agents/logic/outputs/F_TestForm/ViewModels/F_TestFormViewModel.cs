using vba_brain.UI.WPF.Services;
using System.Windows;
using System.Threading.Tasks;
using System.Linq;
using System;
using System.Windows.Input;
using vba_brain.UI.WPF.Utils;
using vba_brain.Application.Interfaces;
using vba_brain.Application.DTOs.Requests.F_TestForm;
using vba_brain.Application.DTOs.Responses.F_TestForm;

namespace vba_brain.UI.WPF.ViewModels;

/// <summary>
/// F_TestFormのViewModel。
/// </summary>
public class F_TestFormViewModel : ViewModelBase
{

    // ─ Properties ──
    // [QUERY]  from 
    private string _txtUserName = string.Empty;
    public string txtUserName { get => _txtUserName; set => SetProperty(ref _txtUserName, value); }

    /// <summary>ウィンドウを閉じる要求イベント (DoCmd.Close相当)。</summary>
    public event EventHandler? CloseRequested;

    // ─ Commands ──
    // [F000] __form__[onopen]
    public ICommand F000Command { get; }
    // [F001] txtUserName[afterupdate]
    public ICommand F001Command { get; }
    // [F002] []
    public ICommand F002Command { get; }

    private readonly ITestFormService _testFormService;

    public F_TestFormViewModel(ITestFormService testFormService)
    {
        _testFormService = testFormService;
        F000Command = Cmd(async _ => await F000Async());
        F001Command = Cmd(async _ => await F001Async());
        F002Command = Cmd(async _ => await F002Async());
    }

    #region Methods (Logic Agent implements)
        /// <summary>[F000] Form_Open</summary>
    public virtual async System.Threading.Tasks.Task F000Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F001] txtUserName_AfterUpdate</summary>
    public virtual async System.Threading.Tasks.Task F001Async()
    {
        if (DataContext is ViewModels.FLoginViewModel vm)
                await vm.F001Async();
    }

    /// <summary>[F002] btnSubmit_Click</summary>
    public virtual async System.Threading.Tasks.Task F002Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }
    #endregion
}
