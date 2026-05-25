namespace vba_brain.Application.Interfaces;

using vba_brain.Application.DTOs.Requests;
using vba_brain.Application.DTOs.Responses;

/// <summary>
/// Application service for F_Login.
/// </summary>
public interface IFLoginService
{
    /// <summary>F000 画面を開く時 — ユーザーのログイン情報を確認し、適切な権限を持つユーザーのみがシステムにアクセスできるようにします。</summary>
    Task<F000Response> F000Async(F000Request request);

    /// <summary>F002 フォーム読み込み後 — 現在のバージョンが最新かどうかを確認し、必要に応じて新しいバージョンをインストールします。</summary>
    Task<F002Response> F002Async(F002Request request);

    /// <summary>F003 更新後処理 — ユーザーが正しいIDとパスワードを入力した場合にのみ、システムへのアクセスを許可します。</summary>
    Task<F003Response> F003Async(F003Request request);

    /// <summary>F008 ダブルクリック時 — ログインフォームとユーザー追加フォームを閉じ、メニューバーとステータスバーを有効にし、特定のクエリを開いて最大化します。</summary>
    Task<F008Response> F008Async(F008Request request);

}
