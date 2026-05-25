using System;
using System.Threading.Tasks;

namespace vba_brain.UI.WPF.Services
{
    public interface IAMenuBarShowMacroWorkflow
    {
        Task ExecuteAsync();
    }

    public class AMenuBarShowMacroWorkflow : IAMenuBarShowMacroWorkflow
    {
        public async Task ExecuteAsync()
        {
            // Beep音を鳴らす
            System.Media.SystemSounds.Beep.Play();

            // メニューバーを表示する (VBA: MenuBarTrue())
            // TODO: MenuBar.MenuBarTrue() を実行 — IMenuBarService未実装のためTODO
            await System.Threading.Tasks.Task.CompletedTask;
        }
    }
}