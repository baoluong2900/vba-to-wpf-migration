using System.Windows.Input;

namespace vba_brain.UI.Avalonia.Utils;

/// <summary>
/// ICommand implementation for MVVM binding.
/// Supports both sync and async execute delegates.
/// </summary>
public class RelayCommand : ICommand
{
    private readonly Func<object?, Task> _executeAsync;
    private readonly Func<object?, bool>? _canExecute;
    private bool _isExecuting;

    /// <summary>Create async RelayCommand.</summary>
    public RelayCommand(Func<object?, Task> executeAsync, Func<object?, bool>? canExecute = null)
    {
        _executeAsync = executeAsync ?? throw new ArgumentNullException(nameof(executeAsync));
        _canExecute = canExecute;
    }

    /// <summary>Create sync RelayCommand.</summary>
    public RelayCommand(Action<object?> execute, Func<object?, bool>? canExecute = null)
        : this(p => { execute(p); return Task.CompletedTask; }, canExecute) { }

    public event EventHandler? CanExecuteChanged;

    /// <summary>Receives exceptions thrown by any command's delegate (logged to stderr when unset).</summary>
    public static event Action<Exception>? UnhandledException;

    public bool CanExecute(object? parameter)
    {
        return !_isExecuting && (_canExecute?.Invoke(parameter) ?? true);
    }

    public async void Execute(object? parameter)
    {
        if (!CanExecute(parameter)) return;

        _isExecuting = true;
        RaiseCanExecuteChanged();

        try
        {
            await _executeAsync(parameter);
        }
        catch (Exception ex)
        {
            // ICommand.Execute is async void: an escaping exception (e.g. the database is down)
            // would be rethrown on the UI thread and terminate the app.
            if (UnhandledException is { } handler) handler(ex);
            else Console.Error.WriteLine($"[RelayCommand] Unhandled exception: {ex}");
        }
        finally
        {
            _isExecuting = false;
            RaiseCanExecuteChanged();
        }
    }

    public void RaiseCanExecuteChanged()
    {
        CanExecuteChanged?.Invoke(this, EventArgs.Empty);
    }
}
