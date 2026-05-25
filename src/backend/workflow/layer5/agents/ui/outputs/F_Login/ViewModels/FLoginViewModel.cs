using System.Windows;
using System.Threading.Tasks;
using System.Linq;
using System;
using System.Windows.Input;
using vba_brain.UI.WPF.Utils;
using vba_brain.UI.WPF.Services;
using vba_brain.Application.Interfaces;
using vba_brain.Application.DTOs.Requests;
using vba_brain.Application.DTOs.Responses;

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

    private string _txtID = string.Empty;
    public string TxtID { get => _txtID; set => SetProperty(ref _txtID, value); }

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
    // [F004] cmdClose[onclick]
    public ICommand F004Command { get; }
    // [F005] lblShopInfo[ondblclick]
    public ICommand F005Command { get; }
    // [F006] lbl142[onclick]
    public ICommand F006Command { get; }
    // [F007] lbl142[ondblclick]
    public ICommand F007Command { get; }
    // [F008] lblOpenPasswordTable[ondblclick]
    public ICommand F008Command { get; }
    // [F009] lblEndProcess[ondblclick]
    public ICommand F009Command { get; }

    private readonly IFLoginService _fLoginService;
    private readonly IAMenuBarShowMacroWorkflow _aMenuBarShow;
    private readonly IM300SplashMOpenMacroWorkflow _m300SplashMOpen;

    public FLoginViewModel(
        IFLoginService fLoginService,
        IAMenuBarShowMacroWorkflow aMenuBarShow,
        IM300SplashMOpenMacroWorkflow m300SplashMOpen)
    {
        _fLoginService = fLoginService;
        _aMenuBarShow = aMenuBarShow;
        _m300SplashMOpen = m300SplashMOpen;
        F000Command = Cmd(async _ => await F000Async());
        F001Command = Cmd(async p => await F001Async(p as System.Windows.Input.KeyEventArgs));
        F002Command = Cmd(async _ => await F002Async());
        F003Command = Cmd(async _ => await F003Async());
        F004Command = Cmd(async _ => await F004Async());
        F005Command = Cmd(async _ => await F005Async());
        F006Command = Cmd(async _ => await F006Async());
        F007Command = Cmd(async _ => await F007Async());
        F008Command = Cmd(async _ => await F008Async());
        F009Command = Cmd(async _ => await F009Async());
    }

    #region Methods (Logic Agent implements)
        /// <summary>[F000] Form_Open</summary>
    public virtual async System.Threading.Tasks.Task F000Async()
    {
        // DD 2.1: ユーザー名を取得し、TxtIDに設定
            TxtID = System.Environment.UserName;

            // DD 2.2: txtIDの内容をクリップボードにコピー
            System.Windows.Clipboard.SetText(TxtID);

            // DD 2.3, 2.4: サービス呼び出し（F000_SelQuery01）
            var request = new F000Request { TxtID = TxtID };
            var response = await _fLoginService.F000Async(request);

            if (!response.Success)
            {
                // DD 3.1: エラー発生時はメッセージ表示
                MessageBox.Show(response.Message ?? "ログイン情報の取得に失敗しました。", "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // TODO: ログイン成功時の遷移処理 — 画面遷移先を確認してください
    }

    /// <summary>[F001] Form_KeyDown</summary>
    public virtual async System.Threading.Tasks.Task F001Async(System.Windows.Input.KeyEventArgs? e = null)
    {
        if (e == null) { await System.Threading.Tasks.Task.CompletedTask; return; }
            switch (e.Key)
            {
                case System.Windows.Input.Key.F11:
                    e.Handled = true;
                    MessageBox.Show("ファンクション【F11】キーは無効に設定されてます！！",
                        "警告", MessageBoxButton.OK, MessageBoxImage.Warning);
                    break;
                case System.Windows.Input.Key.F12:
                    e.Handled = true;
                    MessageBox.Show("ファンクション【F12】キーは無効に設定されてます！！",
                        "警告", MessageBoxButton.OK, MessageBoxImage.Warning);
                    break;
            }
            await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F002] Form_Load</summary>
    public virtual async System.Threading.Tasks.Task F002Async()
    {
        var request = new F002Request();
        var response = await _fLoginService.F002Async(request);
        if (!response.Success)
        {
            // TODO: handle error — response.Message
        }
    }

    /// <summary>[F003] txtPass_AfterUpdate</summary>
    public virtual async System.Threading.Tasks.Task F003Async()
    {
        // DD 2.1: IDフィールドが空の場合、ユーザーにIDの入力を促す
            if (string.IsNullOrWhiteSpace(TxtID))
            {
                MessageBox.Show("IDを入力してください。", "入力エラー", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // DD 2.2: パスワードフィールドが空の場合、ユーザーにパスワードの入力を促す
            if (string.IsNullOrWhiteSpace(TxtPass))
            {
                MessageBox.Show("パスワードを入力してください。", "入力エラー", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // DD 1.1, 2.3以降: サービス呼び出し
            var request = new F003Request { TxtID = TxtID, TxtPass = TxtPass };
            var response = await _fLoginService.F003Async(request);

            // DD 3.1: 通信エラー時の処理
            if (!response.Success)
            {
                MessageBox.Show(response.Message ?? "通信エラーが発生しました。", "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // 認証結果の取得（NULLチェック付き）
            var auth = response.AuthEntity?.FirstOrDefault();
            if (auth == null)
            {
                MessageBox.Show("認証情報が取得できませんでした。", "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // DD 2.5: 管理者フラグが0の場合、ログイン不可
            if (auth.AdminFlag == "0")
            {
                MessageBox.Show("このユーザーではログインできません。", "権限エラー", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // DD 2.7: パスワード不一致時
            if (!string.Equals(auth.Pass, TxtPass, StringComparison.Ordinal))
            {
                MessageBox.Show("パスワードが一致しません。", "認証エラー", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // DD 2.9: ログイン成功時はフォームを閉じる
            CloseRequested?.Invoke(this, EventArgs.Empty);

            // DD 2.10以降: T023_地区CD設定テーブルのレコード数を確認し、処理分岐
            var t022List = response.T022PrefectureEntity ?? Enumerable.Empty<T022PrefectureEntity>();
            if (!t022List.Any())
            {
                // TODO: マクロ『AutoExec_Restart』相当処理を実装 — 要件確認
            }
            else
            {
                // TODO: タイマーを開くモジュールを呼び出す — 実装方法要確認
            }

            // DD 2.13: マクロ『AutoExec_A』を実行 — TODOとして残す
            // TODO: マクロ『AutoExec_A』を実行 — 処理内容要確認
    }

    /// <summary>[F004] 閉じる_Click</summary>
    public virtual async System.Threading.Tasks.Task F004Async()
    {
        var result = MessageBox.Show(
                "アプリケーションを終了しますか？",
                "確認", MessageBoxButton.YesNo, MessageBoxImage.Question);
            if (result == MessageBoxResult.Yes)
                System.Windows.Application.Current.Shutdown();
            await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F005] 施工店情報_DblClick</summary>
    public virtual async System.Threading.Tasks.Task F005Async()
    {
        // TODO: open 施工店情報 form — verify View class name before instantiating
            await System.Threading.Tasks.Task.CompletedTask;
    }

    /// <summary>[F006] ラベル142_Click</summary>
    public virtual async System.Threading.Tasks.Task F006Async()
    {
        await _aMenuBarShow.ExecuteAsync();
    }

    /// <summary>[F007] ラベル142_Dblclick</summary>
    public virtual async System.Threading.Tasks.Task F007Async()
    {
        await _m300SplashMOpen.ExecuteAsync();
    }

    /// <summary>[F008] パスワードテーブルを開く_DblClick</summary>
    public virtual async System.Threading.Tasks.Task F008Async()
    {
        var request = new F008Request();
        var response = await _fLoginService.F008Async(request);
        if (!response.Success)
        {
            // TODO: handle error — response.Message
        }
    }

    /// <summary>[F009] プロセス終了_DblClick</summary>
    public virtual async System.Threading.Tasks.Task F009Async()
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
    #endregion
}
