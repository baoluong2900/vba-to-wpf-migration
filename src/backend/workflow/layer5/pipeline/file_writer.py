"""
pipeline/file_writer.py — Solution File Writer

Maps GeneratedFile output from agents → correct C# project path in src/wpf/.
Handles:
  - Path mapping (Domain/Entities/X.cs → vba_brain.Domain/Entities/X.cs)
  - Confinement: a target must stay inside its project folder (or the staging dir)
  - Only source files are written (contract/snapshot JSON stays in agents/*/outputs/)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

from core.config import OUTPUT_DIR, vba_brain_PROJECT_DIR
from core.models import GeneratedFile

logger = logging.getLogger(__name__)

# Files that belong in the .NET solution; anything else (e.g. Agent Repo's {Repo}.json) is skipped.
CODE_SUFFIXES = (".cs", ".axaml", ".xaml")

# ──────────────────────────────────────────────
# Path mapping: agent output path → C# project
# ──────────────────────────────────────────────
PROJECT_MAP: dict[str, str] = {
    "Domain/Entities":                    "vba_brain.Domain/Entities",
    "Domain/Interfaces":                  "vba_brain.Domain/Interfaces",
    "Domain/DTOs":                        "vba_brain.Domain/DTOs",
    "Domain/Common":                      "vba_brain.Domain/Common",
    "Domain/Exceptions":                  "vba_brain.Domain/Exceptions",
    "Application/DTOs":                   "vba_brain.Application/DTOs",
    "Application/Interfaces":             "vba_brain.Application/Interfaces",
    "Application/Services":               "vba_brain.Application/Services",
    "Application/Validators":             "vba_brain.Application/Validators",
    "Application/Mappers":                "vba_brain.Application/Mappers",
    "Infrastructure/Persistence/Repositories": "vba_brain.Infrastructure/Persistence/Repositories",
    "Infrastructure/Persistence/UnitOfWork":   "vba_brain.Infrastructure/Persistence/UnitOfWork",
    "Infrastructure/Helpers":             "vba_brain.Infrastructure/Helpers",
    "Views":                              "vba_brain.UI.Avalonia/Views",
    "ViewModels":                         "vba_brain.UI.Avalonia/ViewModels",
    "Models":                             "vba_brain.UI.Avalonia/Models",
    "Services":                           "vba_brain.UI.Avalonia/Services",
    "Utils":                              "vba_brain.UI.Avalonia/Utils",
    "Resources":                          "vba_brain.UI.Avalonia/Resources",
    "Tests/Unit":                         "vba_brain.Tests/Unit",
    "Tests/Integration":                  "vba_brain.Tests/Integration",
}


def is_code_file(gen_file: GeneratedFile) -> bool:
    return gen_file.path.replace("\\", "/").lower().endswith(CODE_SUFFIXES)


def _confined(base: Path, rel: str) -> Path:
    """base / rel, refusing absolute paths and anything that resolves outside `base`."""
    if Path(rel).is_absolute() or (len(rel) > 1 and rel[1] == ":"):
        raise ValueError(f"absolute path in generated file: {rel!r}")
    root = base.resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError(f"generated file escapes {root}: {rel!r}")
    return target


class SolutionWriter:
    """
    Writes generated files into the correct C# project directories.

    Usage:
        writer = SolutionWriter()
        writer.write(gen_file)
        writer.write(gen_file, overwrite=False)  # skip if exists
    """

    def __init__(self, solution_dir: Path | None = None, staging_dir: Path | None = None):
        self.solution_dir = solution_dir or vba_brain_PROJECT_DIR
        self.staging_dir = staging_dir or OUTPUT_DIR
        if not self.solution_dir.exists():
            raise FileNotFoundError(
                f"Solution directory not found: {self.solution_dir}\n"
                f"Expected: src/wpf/ with vba_brain.slnx"
            )
        logger.info("[FileWriter] Solution dir: %s", self.solution_dir)

    def resolve_path(self, gen_file: GeneratedFile) -> Path:
        """
        Map agent output path to absolute C# project path.

        Example:
            "Domain/Entities/IdPassEntity.cs" → <solution>/vba_brain.Domain/Entities/IdPassEntity.cs
        Unmapped paths go to the Layer 5 staging dir (core.config.OUTPUT_DIR).
        Raises ValueError for absolute paths or paths escaping their base directory.
        """
        rel = gen_file.path.replace("\\", "/")
        if not rel or rel.endswith("/"):
            raise ValueError(f"generated file has no file name: {gen_file.path!r}")

        # Longest prefix first, on whole path segments ("ViewModelsX/..." is not "ViewModels")
        for agent_prefix, project_prefix in sorted(
            PROJECT_MAP.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if rel.startswith(agent_prefix + "/"):
                filename = rel[len(agent_prefix) + 1:]
                if filename:
                    return _confined(self.solution_dir / project_prefix, filename)

        logger.warning("[FileWriter] No mapping for: %s — writing to %s", rel, self.staging_dir)
        return _confined(self.staging_dir, rel)

    def write(
        self,
        gen_file: GeneratedFile,
        overwrite: bool = True,
    ) -> Path:
        """
        Write a generated file to the solution.

        Args:
            gen_file: The generated file with path + content.
            overwrite: If False, skip if file already exists.

        Returns:
            Absolute path where file was written.
        """
        target = self.resolve_path(gen_file)

        if not overwrite and target.exists():
            logger.info("[FileWriter] SKIP (exists): %s", target.name)
            return target

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(gen_file.content, encoding="utf-8")
        try:
            rel_path = target.relative_to(self.solution_dir.resolve())
        except ValueError:
            rel_path = target
        logger.info(
            "[FileWriter] ✅ WROTE: %s (%d bytes, agent=%s, gen=%s)",
            rel_path,
            len(gen_file.content),
            gen_file.agent,
            gen_file.generator,
        )
        return target

    def write_all(
        self,
        files: list[GeneratedFile],
        overwrite: bool = True,
    ) -> list[Path]:
        """Write the source files among `files` (last one wins per target); unsafe paths are logged and skipped."""
        paths = []
        for gf in dedupe_generated_files(files, self):
            if not is_code_file(gf):
                logger.debug("[FileWriter] Not a source file, not deployed: %s", gf.path)
                continue
            try:
                paths.append(self.write(gf, overwrite=overwrite))
            except ValueError as exc:
                logger.error("[FileWriter] ❌ Refused %s (agent=%s): %s", gf.path, gf.agent, exc)
        return paths

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file already exists in the solution."""
        dummy = GeneratedFile(path=relative_path, content="", generator="", agent="")
        target = self.resolve_path(dummy)
        return target.exists()

    def read_existing(self, relative_path: str) -> Optional[str]:
        """Read content of an existing file in the solution."""
        dummy = GeneratedFile(path=relative_path, content="", generator="", agent="")
        target = self.resolve_path(dummy)
        if target.exists():
            return target.read_text(encoding="utf-8")
        return None

    def list_generated(self, extension: str = ".cs") -> list[Path]:
        """List all generated files in the solution."""
        files = []
        for project_dir in PROJECT_MAP.values():
            full = self.solution_dir / project_dir
            if full.exists():
                files.extend(full.rglob(f"*{extension}"))
        return files


def dedupe_generated_files(files: Iterable[GeneratedFile], writer: SolutionWriter) -> list[GeneratedFile]:
    """
    One GeneratedFile per target path, keeping the LAST one (later agents refine earlier output,
    e.g. Agent Logic's patched ViewModel replaces Agent UI's skeleton), ordered by that last
    occurrence. Files whose path cannot be resolved are kept so the caller reports them.
    """
    by_target: dict[str, GeneratedFile] = {}
    for gf in files:
        try:
            key = str(writer.resolve_path(gf))
        except ValueError:
            key = f"<unsafe>:{gf.path}"
        if key in by_target:
            del by_target[key]  # re-insert so the last version's position wins
        by_target[key] = gf
    return list(by_target.values())
