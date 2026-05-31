using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace vba_brain.UI.Avalonia.ViewModels;

/// <summary>
/// Base class for all ViewModels — provides INotifyPropertyChanged.
/// </summary>
public abstract class ViewModelBase : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;

    /// <summary>
    /// Set property value and raise PropertyChanged if changed.
    /// </summary>
    protected bool SetProperty<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
            return false;

        field = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    /// <summary>
    /// Raise PropertyChanged event.
    /// </summary>
    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }

    // ── Command factory helpers (used by generated ViewModels) ──
    protected static global::vba_brain.UI.Avalonia.Utils.RelayCommand Cmd(Func<object?, Task> execute, Func<object?, bool>? canExecute = null)
        => new global::vba_brain.UI.Avalonia.Utils.RelayCommand(execute, canExecute);

    protected static global::vba_brain.UI.Avalonia.Utils.RelayCommand Cmd(Action<object?> execute, Func<object?, bool>? canExecute = null)
        => new global::vba_brain.UI.Avalonia.Utils.RelayCommand(execute, canExecute);

    protected static global::vba_brain.UI.Avalonia.Utils.RelayCommand Cmd(Func<Task> execute)
        => new global::vba_brain.UI.Avalonia.Utils.RelayCommand(_ => execute());

    protected static global::vba_brain.UI.Avalonia.Utils.RelayCommand Cmd(Action execute)
        => new global::vba_brain.UI.Avalonia.Utils.RelayCommand(_ => execute());
}
