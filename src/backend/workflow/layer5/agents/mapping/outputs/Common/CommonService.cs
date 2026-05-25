using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace vba_brain.Domain.Common
{
    public interface ICommonService
    {
        Task JudgeInstAsync();
    }

    public class CommonService : ICommonService
    {
        // インストールできないメッセージ定数
        private const string INSTALL_ERROR_MESSAGE = "インストールできません！！" + "\r\n\r\n" + "対応時間は、【８：３０～１７：２０】　です！！";
        
        // ネットワークパス（Officeバージョンによって異なる可能性あり）
        private const string DB_PATH_OFFICE2016 = @"\\REDACTED_IP\share\99_施工管理インストーラー\★最新★_share\【新アフター管理ＤＢ_V1】_Office2016対応_20220808本番_Net.accdb";

        /// <summary>
        /// Judge_Inst - 最新版ではない場合にインストール処理を行うサブルーチン
        /// </summary>
        public async Task JudgeInstAsync()
        {
            // 最新版ではありませんメッセージ表示と確認
            var result = MessageBox.Show(
                " 最新版ではありません！！インストールします。よろしいですか？",
                "メッセイジ",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Exclamation,
                MessageBoxDefaultButton.Button2
            );

            if (result == DialogResult.No)
            {
                return; // キャンセルされた場合は終了
            }

            // インストール不可メッセージ表示
            MessageBox.Show(INSTALL_ERROR_MESSAGE, "エラー", MessageBoxButtons.OK, MessageBoxIcon.Error);

            // インストーラー自動選択確認
            var autoSelectResult = MessageBox.Show(
                "インストーラーを自動選択します。" + "\r\n\r\n" + "いいですか？",
                "確認",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Information,
                MessageBoxDefaultButton.Button2
            );

            if (autoSelectResult != DialogResult.Yes)
            {
                Environment.Exit(0); // 「いいえ」を選んだらアプリケーション終了
            }

            await Task.Run(() =>
            {
                try
                {
                    string dbPath = SelectDatabasePathByAccessVersion();

                    if (!File.Exists(dbPath))
                    {
                        MessageBox.Show("指定されたデータベースが存在しません。", "エラー", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        return;
                    }

                    // Access アプリケーション起動
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = "MSACCESS.EXE",
                        Arguments = $"\"{dbPath}\"",
                        UseShellExecute = true
                    });

                    // 現在のアプリケーションを終了する（Access VBA の DoCmd.Quit 相当）
                    Environment.Exit(0);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"インストール中にエラーが発生しました。\r\n詳細: {ex.Message}", "エラー", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            });
        }

        /// <summary>
        /// Access のバージョンに応じて適切なデータベースパスを選択します。
        /// </summary>
        /// <returns>選択されたデータベースパス</returns>
        private string SelectDatabasePathByAccessVersion()
        {
            // Application.Version を取得（ここではダミー値として 16.0 を使用）
            Version accessVersion = GetAccessApplicationVersion(); // 実際には COM オブジェクト経由で取得が必要
            
            switch (accessVersion.Major)
            {
                case 16:
                case 14:
                    return DB_PATH_OFFICE2016;
                default:
                    // 他のバージョンに対応する場合はここに追加
                    return DB_PATH_OFFICE2016; // デフォルトとして最新版を使用
            }
        }

        /// <summary>
        /// Access アプリケーションのバージョン情報を取得します。
        /// </summary>
        /// <returns>Access のバージョン情報</returns>
        private Version GetAccessApplicationVersion()
        {
            // TODO: 実際には COM オブジェクトから Access のバージョンを取得する必要があります。
            // この例ではダミーのバージョンを返しています。
            return new Version(16, 0);
        }
    }
}