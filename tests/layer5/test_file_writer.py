"""Solution writer confinement / de-duplication and build-fix file matching (layer5/pipeline)."""
from __future__ import annotations

import pytest

from core.models import GeneratedFile
from pipeline.build_verify import BuildVerifier
from pipeline.file_writer import SolutionWriter, dedupe_generated_files


def gf(path, content="x", agent="ui"):
    return GeneratedFile(path=path, content=content, generator="test", agent=agent)


@pytest.fixture()
def writer(tmp_path):
    (tmp_path / "wpf").mkdir()
    return SolutionWriter(tmp_path / "wpf", staging_dir=tmp_path / "staging")


def test_mapped_paths_land_in_their_project(writer, tmp_path):
    assert writer.resolve_path(gf("ViewModels/FLoginViewModel.cs")) == \
        (tmp_path / "wpf" / "vba_brain.UI.Avalonia" / "ViewModels" / "FLoginViewModel.cs").resolve()
    assert writer.resolve_path(gf("Application/DTOs/Requests/X.cs")) == \
        (tmp_path / "wpf" / "vba_brain.Application" / "DTOs" / "Requests" / "X.cs").resolve()


def test_unmapped_paths_go_to_the_staging_dir(writer, tmp_path):
    assert writer.resolve_path(gf("AuthRepository.json")) == (tmp_path / "staging" / "AuthRepository.json").resolve()
    # a prefix only counts on a whole path segment
    assert writer.resolve_path(gf("ViewModelsX/A.cs")).is_relative_to((tmp_path / "staging").resolve())


@pytest.mark.parametrize("bad", [
    "ViewModels/../../../escape.cs",
    "../escape.cs",
    "/etc/passwd",
    "Views/",
])
def test_paths_escaping_their_base_are_refused(writer, bad):
    with pytest.raises(ValueError):
        writer.resolve_path(gf(bad))


def test_write_all_skips_non_code_and_unsafe_files(writer, tmp_path):
    written = writer.write_all([
        gf("Views/A.axaml", "<Window/>"),
        gf("Repo.json", "{}", agent="repo"),
        gf("../../outside.cs", "boom"),
    ])
    assert [p.name for p in written] == ["A.axaml"]
    assert not (tmp_path / "staging" / "Repo.json").exists()
    assert not (tmp_path / "outside.cs").exists()


def test_dedupe_keeps_the_last_file_per_target(writer):
    skeleton = gf("ViewModels/FLoginViewModel.cs", "skeleton", agent="ui")
    patched = gf("ViewModels\\FLoginViewModel.cs", "patched", agent="logic")
    other = gf("Views/FLoginView.axaml", "<Window/>")
    assert dedupe_generated_files([skeleton, other, patched], writer) == [other, patched]


def test_build_fix_matches_errors_by_resolved_path(tmp_path):
    sln = tmp_path / "wpf"
    sln.mkdir()
    (sln / "vba_brain.slnx").write_text("<Solution />", encoding="utf-8")
    writer = SolutionWriter(sln, staging_dir=tmp_path / "staging")
    verifier = BuildVerifier(sln)
    a = gf("Application/DTOs/Requests/F_Login/F001Request.cs", "a", agent="service")
    b = gf("Application/DTOs/Requests/F_Menu/F001Request.cs", "b", agent="service")
    targets = verifier._targets_by_path([a, b], writer)
    error_path = str(sln / "vba_brain.Application" / "DTOs" / "Requests" / "F_Menu" / "F001Request.cs")
    assert targets[verifier._error_target(error_path)] is b          # same basename, right file
    assert verifier._error_target("vba_brain.Application/X.cs") == (sln / "vba_brain.Application" / "X.cs").resolve()
