"""
pipeline/base_gen.py — Shared Base Class Generator

Creates foundational classes that all agents depend on.
Only generates if file doesn't already exist (idempotent).

Files:
  - Domain/Common/BaseEntity.cs
  - UI.Avalonia/ViewModels/ViewModelBase.cs
  - UI.Avalonia/Utils/RelayCommand.cs
"""
from __future__ import annotations

import logging
from core.models import GeneratedFile
from pipeline.file_writer import SolutionWriter

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Base class templates
# ──────────────────────────────────────────────

BASE_ENTITY_CS = '''\
namespace vba_brain.Domain.Common;

/// <summary>
/// Base class for all domain entities.
/// Provides common audit fields for future use.
/// </summary>
public abstract class BaseEntity
{
    // Reserved: CreatedAt, UpdatedAt, CreatedBy, UpdatedBy
}
'''

VIEWMODEL_BASE_CS = '''\
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
'''

RELAY_COMMAND_CS = '''\
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
'''

# ──────────────────────────────────────────────
# File definitions
# ──────────────────────────────────────────────

BASE_FILES: list[GeneratedFile] = [
    GeneratedFile(
        path="Domain/Common/BaseEntity.cs",
        content=BASE_ENTITY_CS,
        generator="deterministic",
        agent="pipeline",
    ),
    GeneratedFile(
        path="ViewModels/ViewModelBase.cs",
        content=VIEWMODEL_BASE_CS,
        generator="deterministic",
        agent="pipeline",
    ),
    GeneratedFile(
        path="Utils/RelayCommand.cs",
        content=RELAY_COMMAND_CS,
        generator="deterministic",
        agent="pipeline",
    ),
]


def ensure_base_classes(writer: SolutionWriter | None = None) -> list[str]:
    """
    Generate shared base classes if they don't exist.

    Returns:
        List of file paths that were created (empty if all exist).
    """
    if writer is None:
        writer = SolutionWriter()

    created: list[str] = []

    for gf in BASE_FILES:
        if not writer.file_exists(gf.path):
            writer.write(gf)
            created.append(gf.path)
            logger.info("[BaseGen] Created: %s", gf.path)
        else:
            logger.info("[BaseGen] Already exists: %s", gf.path)

    if created:
        logger.info("[BaseGen] ✅ Created %d base classes", len(created))
    else:
        logger.info("[BaseGen] All base classes already exist")

    return created
