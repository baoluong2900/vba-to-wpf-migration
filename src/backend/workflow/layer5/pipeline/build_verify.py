"""
pipeline/build_verify.py — Build & Auto-Fix Cycle

Runs `dotnet build` on the solution, parses errors, sends them to LLM for fix,
then retries. Max 3 attempts per build cycle.

Flow:
    1. dotnet build vba_brain.slnx --no-restore
    2. Parse stderr → list of CompileError
    3. If errors in files we generated → LLM fix (fed the file as it is on disk) → rewrite → goto 1
    4. If clean build → return success

Generated files are matched to errors by resolved absolute path, after de-duplicating by target
(the last agent wins: Logic's patched ViewModel, not UI's skeleton).
"""
from __future__ import annotations

import re
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import vba_brain_PROJECT_DIR, MAX_RETRIES
from core.models import GeneratedFile
from llm.llm_client import L5LLMClient, extract_code_block

logger = logging.getLogger(__name__)


@dataclass
class CompileError:
    """A single C# compile error."""
    file_path: str
    line: int
    column: int
    error_code: str      # CS0246, CS0103, etc.
    message: str
    severity: str = "error"  # "error" | "warning"


@dataclass
class BuildResult:
    """Result of a dotnet build attempt."""
    success: bool
    errors: list[CompileError]
    warnings: list[CompileError]
    output: str
    attempt: int = 1


class BuildVerifier:
    """
    Build the C# solution and auto-fix compile errors using LLM.

    Usage:
        verifier = BuildVerifier()
        result = verifier.build()
        if not result.success:
            result = verifier.build_and_fix(generated_files)
    """

    def __init__(self, solution_dir: Path | None = None):
        self.solution_dir = solution_dir or vba_brain_PROJECT_DIR
        self.sln_path = self.solution_dir / "vba_brain.sln"
        if not self.sln_path.exists():
            self.sln_path = self.solution_dir / "vba_brain.slnx"
        if not self.sln_path.exists():
            raise FileNotFoundError(f"Solution file not found (tried vba_brain.sln and vba_brain.slnx): {self.sln_path}")

    def build(self) -> BuildResult:
        """Run dotnet build and parse results."""
        logger.info("[Build] Running dotnet build...")

        try:
            result = subprocess.run(
                ["dotnet", "build", str(self.sln_path), "--no-restore", "--verbosity", "minimal"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                cwd=str(self.solution_dir),
            )
        except subprocess.TimeoutExpired:
            logger.error("[Build] Timeout after 120s")
            return BuildResult(
                success=False,
                errors=[CompileError("", 0, 0, "TIMEOUT", "Build timed out after 120s")],
                warnings=[],
                output="Build timed out",
            )
        except FileNotFoundError:
            logger.error("[Build] dotnet CLI not found. Is .NET SDK installed?")
            return BuildResult(
                success=False,
                errors=[CompileError("", 0, 0, "DOTNET_NOT_FOUND", "dotnet CLI not found")],
                warnings=[],
                output="dotnet not found",
            )

        full_output = result.stdout + "\n" + result.stderr
        errors, warnings = self._parse_output(full_output)

        success = result.returncode == 0 and len(errors) == 0

        if success:
            logger.info("[Build] ✅ Build succeeded (0 errors, %d warnings)", len(warnings))
        else:
            logger.warning(
                "[Build] ❌ Build failed (%d errors, %d warnings)",
                len(errors), len(warnings),
            )
            for err in errors[:5]:
                logger.warning("  → %s(%d): %s %s", err.file_path, err.line, err.error_code, err.message)

        return BuildResult(
            success=success,
            errors=errors,
            warnings=warnings,
            output=full_output,
        )

    def build_and_fix(
        self,
        generated_files: list[GeneratedFile],
        max_retries: int | None = None,
    ) -> BuildResult:
        """
        Build → if errors → LLM fix → rebuild. Up to max_retries attempts.

        Args:
            generated_files: Files we generated (can be modified for fix).
            max_retries: Override default MAX_RETRIES.

        Returns:
            Final BuildResult after all attempts.
        """
        from pipeline.file_writer import SolutionWriter, dedupe_generated_files, is_code_file

        retries = max(1, MAX_RETRIES if max_retries is None else max_retries)
        llm = L5LLMClient()
        writer = SolutionWriter(self.solution_dir)
        targets = self._targets_by_path(
            [gf for gf in dedupe_generated_files(generated_files, writer) if is_code_file(gf)], writer
        )

        for attempt in range(1, retries + 1):
            result = self.build()
            result.attempt = attempt

            if result.success:
                return result

            if attempt >= retries:
                logger.error("[Build] Max retries (%d) reached. Giving up.", retries)
                return result

            # Group errors by the generated file they belong to (resolved absolute path)
            errors_by_target: dict[Path, list[CompileError]] = {}
            seen: set[tuple] = set()  # MSBuild repeats every error in its summary
            for err in result.errors:
                target = self._error_target(err.file_path)
                key = (target, err.line, err.column, err.error_code, err.message)
                if target in targets and key not in seen:
                    seen.add(key)
                    errors_by_target.setdefault(target, []).append(err)

            if not errors_by_target:
                logger.warning("[Build] Errors in files we didn't generate. Cannot auto-fix.")
                return result

            for target, file_errors in errors_by_target.items():
                gen_file = targets[target]
                current = target.read_text(encoding="utf-8") if target.exists() else gen_file.content
                fixed_code = self._llm_fix(llm, gen_file, file_errors, current)
                if fixed_code:
                    gen_file.content = fixed_code
                    writer.write(gen_file, overwrite=True)
                    logger.info("[Build] 🔧 Fixed: %s (attempt %d)", gen_file.path, attempt)

        return result

    # ──────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────

    def _parse_output(self, output: str) -> tuple[list[CompileError], list[CompileError]]:
        """Parse dotnet build output for errors and warnings."""
        errors: list[CompileError] = []
        warnings: list[CompileError] = []

        # Pattern: path(line,col): error CS0246: message
        pattern = re.compile(
            r"(.+?)\((\d+),(\d+)\)\s*:\s*(error|warning)\s+(CS\d+)\s*:\s*(.+)"
        )

        for line in output.splitlines():
            m = pattern.search(line)
            if m:
                ce = CompileError(
                    file_path=m.group(1).strip(),
                    line=int(m.group(2)),
                    column=int(m.group(3)),
                    error_code=m.group(5),
                    message=m.group(6).strip(),
                    severity=m.group(4),
                )
                if ce.severity == "error":
                    errors.append(ce)
                else:
                    warnings.append(ce)

        return errors, warnings

    @staticmethod
    def _targets_by_path(generated_files: list[GeneratedFile], writer) -> dict[Path, GeneratedFile]:
        """Resolved solution path → GeneratedFile (unresolvable paths are skipped)."""
        targets: dict[Path, GeneratedFile] = {}
        for gf in generated_files:
            try:
                targets[writer.resolve_path(gf).resolve()] = gf
            except ValueError:
                continue
        return targets

    def _error_target(self, error_file_path: str) -> Path:
        """Absolute path of the file an MSBuild error points at (relative paths are solution-relative)."""
        path = Path(error_file_path.strip())
        if not path.is_absolute():
            path = self.solution_dir / path
        return path.resolve()

    def _llm_fix(
        self,
        llm: "L5LLMClient",
        gen_file: GeneratedFile,
        errors: list[CompileError],
        current_code: str,
    ) -> Optional[str]:
        """Ask LLM to fix compile errors in a generated file."""
        error_text = "\n".join(
            f"  Line {e.line}: {e.error_code} — {e.message}" for e in errors
        )

        system = (
            "You are a C# compiler error fixer. "
            "Fix ALL compile errors in the code below. "
            "Return ONLY the fixed C# code, no explanations. "
            "Keep the original logic and structure intact. "
            "Use standard C# file-scoped namespace declaration syntax (e.g. 'namespace vba_brain.Domain.Entities;' with a semicolon and no curly braces). Do NOT write the words 'file-scoped' in the C# code. Target: net10.0."
        )

        user = (
            f"## File: {gen_file.path}\n\n"
            f"## Compile Errors:\n{error_text}\n\n"
            f"## Current Code:\n```csharp\n{current_code}\n```\n\n"
            f"Fix all errors and return the complete fixed code."
        )

        try:
            raw = llm.generate_code(
                task_type="validator",  # use fast/cheap model for fixes
                system_prompt=system,
                user_prompt=user,
            )
            fixed = extract_code_block(raw, language="csharp")
            if fixed and len(fixed) > 50:
                return fixed
        except Exception as e:
            logger.error("[Build] LLM fix failed: %s", e)

        return None
