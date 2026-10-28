using System.Windows.Input;
using vba_brain.UI.Avalonia.Utils;
using vba_brain.Application.Interfaces;
using vba_brain.Application.DTOs.Requests.F_Login;
using vba_brain.Application.DTOs.Responses.F_Login;

namespace vba_brain.UI.Avalonia.ViewModels;

/// <summary>
/// F_LoginのViewModel。
/// </summary>
public class FLoginViewModel : ViewModelBase
{

    // ─ Properties ──
    private string _txtPass = string.Empty;
    public string TxtPass { get => _txtPass; set => SetProperty(ref _txtPass, value); }

    private string _txtID = string.Empty;
    public string TxtID { get => _txtID; set => SetProperty(ref _txtID, value); }

    private string _comment1 = string.Empty;
    public string Comment1 { get => _comment1; set => SetProperty(ref _comment1, value); }

    /// <summary>ウィンドウを閉じる要求イベント (DoCmd.Close相当)。</summary>
    public event EventHandler? CloseRequested;

    // ─ Commands ──
    // [F000] __form__[onopen]
    public ICommand F000Command { get; }
    // [F001] __form__[onkeydown]
    public ICommand F001Command { get; }
    // [F003] txtPass[afterupdate]
    public ICommand F003Command { get; }
    // [F010] []
    public ICommand F010Command { get; }
    public ICommand F011Command { get; }

    private readonly IFLoginService _fLoginService;

    public FLoginViewModel(IFLoginService fLoginService)
    {
        _fLoginService = fLoginService;
        F000Command = Cmd(async _ => await F000Async());
        F001Command = Cmd(async _ => await F001Async());
        F003Command = Cmd(async _ => await F003Async());
        F010Command = Cmd(async _ => await F010Async());
        F011Command = Cmd(_ => CloseRequested?.Invoke(this, EventArgs.Empty));
    }

    #region Methods (Logic Agent implements)
        /// <summary>[F000] Form_Open</summary>
    public virtual async System.Threading.Tasks.Task F000Async()
    {
        var request = new F000Request();
        var response = await _fLoginService.F000Async(request);
        if (!response.Success)
        {
            // TODO: handle error — response.Message
        }
    }

    /// <summary>[F001] Form_KeyDown</summary>
    public virtual async System.Threading.Tasks.Task F001Async()
    {
        var request = new F001Request();
        var response = await _fLoginService.F001Async(request);
        if (!response.Success)
        {
            // TODO: handle error — response.Message
        }
    }

    /// <summary>[F003] txtPass_AfterUpdate</summary>
    public virtual async System.Threading.Tasks.Task F003Async()
    {
        var request = new F003Request();
        var response = await _fLoginService.F003Async(request);
        if (!response.Success)
        {
            // TODO: handle error — response.Message
        }
    }

    /// <summary>[F010] cmdLogin_Click</summary>
    public virtual async System.Threading.Tasks.Task F010Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }
    #endregion
}