using vba_brain.UI.WPF.Services;
using System.Windows;
using System.Threading.Tasks;
using System.Linq;
using System;
using System.Windows.Input;
using vba_brain.UI.WPF.Utils;
using vba_brain.Application.Interfaces;
using vba_brain.Application.DTOs.Requests.F_Login;
using vba_brain.Application.DTOs.Responses.F_Login;

namespace vba_brain.UI.WPF.ViewModels;

/// <summary>
/// F_LoginのViewModel。
/// </summary>
public class FLoginViewModel : ViewModelBase
{

    // ─ Properties ──
    private string _txtPass = string.Empty;
    public string TxtPass { get => _txtPass; set => SetProperty(ref _txtPass, value); }

    // [QUERY] Comment1 from Access配信日
    private string _comment1 = string.Empty;
    public string Comment1 { get => _comment1; set => SetProperty(ref _comment1, value); }

    /// <summary>ウィンドウを閉じる要求イベント (DoCmd.Close相当)。</summary>
    public event EventHandler? CloseRequested;

    // ─ Commands ──
    // [F000] __form__[onopen]
    public ICommand F000Command { get; }
    // [F001] __form__[onkeydown]
    public ICommand F001Command { get; }
    // [F002] __form__[onload]
    public ICommand F002Command { get; }
    // [F003] txtPass[afterupdate]
    public ICommand F003Command { get; }
    // [F010] []
    public ICommand F010Command { get; }
    // [F011] []
    public ICommand F011Command { get; }
    // [F012] []
    public ICommand F012Command { get; }
    // [F013] []
    public ICommand F013Command { get; }
    // [F014] []
    public ICommand F014Command { get; }
    // [F015] []
    public ICommand F015Command { get; }
    // [F016] []
    public ICommand F016Command { get; }

    private readonly IFLoginService _fLoginService;

    public FLoginViewModel(IFLoginService fLoginService)
    {
        _fLoginService = fLoginService;
        F000Command = Cmd(async _ => await F000Async());
        F001Command = Cmd(async p => await F001Async(p as System.Windows.Input.KeyEventArgs));
        F002Command = Cmd(async _ => await F002Async());
        F003Command = Cmd(async _ => await F003Async());
        F010Command = Cmd(async _ => await F010Async());
        F011Command = Cmd(async _ => await F011Async());
        F012Command = Cmd(async _ => await F012Async());
        F013Command = Cmd(async _ => await F013Async());
        F014Command = Cmd(async _ => await F014Async());
        F015Command = Cmd(async _ => await F015Async());
        F016Command = Cmd(async _ => await F016Async());
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

    /// <summary>[F002] Form_Load</summary>
    public virtual async System.Threading.Tasks.Task F002Async()
    {
        if (DataContext is ViewModels.FLoginViewModel vm)
                await vm.F001Async(e.Key);
            e.Handled = vm.LastKeyHandled;
    }

    /// <summary>[F001] Form_KeyDown</summary>
    public virtual async System.Threading.Tasks.Task F001Async()
    {
        // 2.1 ラベルからバージョン情報を抽出
            var currentVersionPart = LblVersion?.ToString().Split('/')?.LastOrDefault()?.Substring(0, 5);

            var request = new F001Request();
            var response = await _fLoginService.F001Async(request);

            if (response.Success && !string.IsNullOrEmpty(response.Message))
            {
                // 2.3 最新バージョンと比較
                if (!string.Equals(currentVersionPart, response.Message.Trim(), StringComparison.OrdinalIgnoreCase))
                {
                    // 2.4.1.1 メッセージ表示
                    MessageBox.Show("最新版ではありません！インストールします。",
                        "確認", MessageBoxButton.OK, MessageBoxImage.Exclamation);
                    // 2.4.1.2 Judge_Instモジュール呼び出し — 実装場所に依存するため要確認
                    // TODO: Common.Judge_Inst の呼び出しを実装 — 具体的手順を確認してください
                }
            }
    }

    /// <summary>[F003] txtPass_AfterUpdate</summary>
    public virtual async System.Threading.Tasks.Task F003Async()
    {
        // DD 2.2: Validate user input
            if (string.IsNullOrWhiteSpace(TxtID))
            {
                MessageBox.Show("ユーザーIDを入力してください。", "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            if (string.IsNullOrWhiteSpace(TxtPass))
            {
                MessageBox.Show("パスワードを入力してください。", "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            var request = new F003Request { TxtID = TxtID, TxtPass = TxtPass };
            var response = await _fLoginService.F003Async(request);

            if (!response.Success)
            {
                MessageBox.Show(response.Message ?? "ユーザーIDまたはパスワードが正しくありません。", "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // DD 2.7: Login successful — close login form and proceed
            CloseRequested?.Invoke(this, EventArgs.Empty);

            // DD 2.7.3: Check record count in T023地区CD設定
            if (response.T023地区CD設定Entity == null || !response.T023地区CD設定Entity.Any())
            {
                // TODO: AutoExec_Restartマクロを実行してアプリケーションを再起動 — 具体的手順を確認
            }
            else
            {
                // TODO: タイマーを開く 及び AutoExec_Aマクロを実行 — Viewクラス名と処理内容を確認
            }
    }

    /// <summary>[F010] cmdLogin_Click</summary>
    public virtual async System.Threading.Tasks.Task F010Async()
    {
        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = "taskkill.exe",
                Arguments = "/F /IM wmplayer.exe")",
                CreateNoWindow = true,
                UseShellExecute = false
            });
            await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F011] cmdClose_Click</summary>
    public virtual async System.Threading.Tasks.Task F011Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F012] lblStoreInfo_DblClick</summary>
    public virtual async System.Threading.Tasks.Task F012Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F013] lblMenuTrigger_Click</summary>
    public virtual async System.Threading.Tasks.Task F013Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F014] lblMenuTrigger_Dblclick</summary>
    public virtual async System.Threading.Tasks.Task F014Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F015] lblOpenPasswordTable_DblClick</summary>
    public virtual async System.Threading.Tasks.Task F015Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F016] lblEndProcess_DblClick</summary>
    public virtual async System.Threading.Tasks.Task F016Async()
    {
        await System.Threading.Tasks.Task.CompletedTask;
    }
    #endregion
}
