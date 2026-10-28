"""clean_generated_files.py — deletes deployed Layer 5 output, keeps the files the pipeline needs."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "clean_generated_files", Path(__file__).resolve().parents[2] / "clean_generated_files.py"
)
cleaner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cleaner)


@pytest.fixture
def wpf(tmp_path, monkeypatch):
    views = tmp_path / "vba_brain.UI.Avalonia" / "Views"
    view_models = tmp_path / "vba_brain.UI.Avalonia" / "ViewModels"
    dtos = tmp_path / "vba_brain.Application" / "DTOs"
    for path in (
        views / "FLoginView.axaml",
        views / ".gitkeep",
        view_models / "FLoginViewModel.cs",
        view_models / "ViewModelBase.cs",
        dtos / "Requests" / "F_Login" / "FLoginServiceRequests.cs",
        dtos / "README.md",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    monkeypatch.setattr(cleaner, "WPF_ROOT", tmp_path)
    monkeypatch.setattr(cleaner, "GENERATED_DIRS", [views, view_models, dtos, tmp_path / "missing"])
    return tmp_path


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_deletes_generated_files_and_keeps_base_class_and_markers(wpf):
    assert cleaner.clean_generated_files() == 3
    assert _files(wpf) == {
        "vba_brain.UI.Avalonia/Views/.gitkeep",
        # Only a full orchestrator run recreates it; single-agent deploys need it to build.
        "vba_brain.UI.Avalonia/ViewModels/ViewModelBase.cs",
        "vba_brain.Application/DTOs/README.md",
    }


def test_dry_run_deletes_nothing(wpf):
    before = _files(wpf)
    assert cleaner.clean_generated_files(dry_run=True) == 3
    assert _files(wpf) == before
