"""
pipeline/orchestrator.py — Layer 5 Pipeline Orchestrator

Per form, in this order:
  1. Agent Repo       → Entity, DTO, Interface, Repository
  2. Agent Service    → IService, Service, DTOs + service contract ({form}.json)
  3. Logic input refresh (Agent Logic, input_only) → inputs/{form}*.json in sync with the new DTOs
  4. Agent UI         → ViewModel skeleton (F-ID commands, DI) + AXAML + code-behind
  5. Agent Logic      → LLM method bodies patched into the UI skeleton ViewModel
  6. Agent GraphView  → review only; non-blocking (errors are logged, never fail the form)
  7. Write every generated source file into the solution → dotnet build (+ LLM auto-fix)

A form is "success" only when Repo, Service, UI and Logic succeeded and the build passed.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import AgentInput, AgentOutput, GeneratedFile  # noqa: E402
from core.config import LAYER4_INPUTS_DIR, LAYER5_DIR, vba_brain_PROJECT_DIR  # noqa: E402
from core.naming import validate_form_name  # noqa: E402
from pipeline.file_writer import SolutionWriter, dedupe_generated_files  # noqa: E402
from pipeline.build_verify import BuildVerifier  # noqa: E402
from pipeline.base_gen import ensure_base_classes  # noqa: E402

logger = logging.getLogger(__name__)

# BD/DD JSON directories
BD_SCREEN_DIR = LAYER4_INPUTS_DIR / "BD_json" / "screen"
DD_FORM_DIR = LAYER4_INPUTS_DIR / "DD_json" / "form"
AGENTS_DIR = LAYER5_DIR / "agents"

# Agents whose failure fails the form (GraphView is advisory)
REQUIRED_AGENTS = ("repo", "service", "ui", "logic")


@dataclass
class FormResult:
    """Result of pipeline execution for a single form."""
    form_name: str
    status: str = "pending"          # pending | running | success | error
    agent_results: dict[str, AgentOutput] = field(default_factory=dict)
    all_files: list[GeneratedFile] = field(default_factory=list)
    build_success: bool = False
    build_attempts: int = 0
    error: Optional[str] = None
    duration_sec: float = 0.0


@dataclass
class PipelineResult:
    """Result of the entire pipeline run."""
    forms: list[FormResult] = field(default_factory=list)
    total_files: int = 0
    total_duration_sec: float = 0.0
    base_classes_created: list[str] = field(default_factory=list)


class L5Orchestrator:
    """
    Main pipeline orchestrator.

    Usage:
        orch = L5Orchestrator()
        result = await orch.run_form("F_Login")
        result = await orch.run_all()
    """

    def __init__(self, solution_dir: Path | None = None):
        self.solution_dir = solution_dir or vba_brain_PROJECT_DIR
        self.writer = SolutionWriter(self.solution_dir)
        self.verifier = BuildVerifier(self.solution_dir)

    async def run_form(self, form_name: str) -> FormResult:
        """Run full pipeline for a single form."""
        result = FormResult(form_name=form_name, status="running")
        start = time.time()

        logger.info("=" * 60)
        logger.info("[Pipeline] 🚀 Starting pipeline for: %s", form_name)
        logger.info("=" * 60)

        try:
            validate_form_name(form_name)
            bd_json = self._load_json(BD_SCREEN_DIR / f"{form_name}.json")
            dd_json = self._load_json(DD_FORM_DIR / f"{form_name}.json")
            all_files: list[GeneratedFile] = []

            # ── 1. Repo ──────────────────────────────────────────────
            logger.info("[Pipeline] ▶ Running Agent Repo...")
            from agents.repo.agent_repo import RepoAgent
            repo_result = await RepoAgent().run(AgentInput(
                form_name=form_name, bd_json=bd_json, dd_json=dd_json,
            ))
            self._record(result, "repo", repo_result, all_files)

            # ── 2. Service ───────────────────────────────────────────
            # Pass the repo contract saved by RepoAgent (agents/repo/outputs/{form}.json)
            # so Agent Service does not need to re-query MongoDB.
            logger.info("[Pipeline] ▶ Running Agent Service...")
            from agents.service.agent_service import ServiceAgent
            svc_repo_contract = self._load_repo_contract(form_name) if repo_result.status == "success" else {}
            svc_result = await ServiceAgent().run(AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,                   # ← pass DD so service agent skips MongoDB re-load
                upstream_files=all_files.copy(),
                mongodb_data={"repo_contract": svc_repo_contract} if svc_repo_contract else {},
            ))
            self._record(result, "service", svc_result, all_files)

            from agents.logic.agent_logic import LogicAgent

            # ── 3. Refresh Logic input snapshots with the freshly generated DTOs ──
            if svc_result.status == "success":
                try:
                    refresh = await LogicAgent().run(AgentInput(
                        form_name=form_name,
                        bd_json=bd_json,
                        dd_json=dd_json,
                        upstream_files=all_files.copy(),
                        logic_event_class="all",
                    ), input_only=True)
                    if refresh.status == "success":
                        logger.info("[Pipeline]   ✅ Logic input refreshed (service_context synced with latest DTOs)")
                    else:
                        logger.warning("[Pipeline]   ⚠️  Logic input refresh failed: %s", refresh.error)
                except Exception as exc:
                    logger.warning("[Pipeline]   ⚠️  Logic input refresh failed: %s", exc)

            # ── 4. UI ────────────────────────────────────────────────
            # UI runs BEFORE Logic: it builds the full skeleton ViewModel (F-ID commands, DI,
            # SetProperty) that Agent Logic patches method bodies into.
            logger.info("[Pipeline] ▶ Running Agent UI (skeleton first)...")
            from agents.ui.agent_ui import UIAgent
            ui_result = await UIAgent().run(AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,
                upstream_files=all_files.copy(),
            ))
            self._record(result, "ui", ui_result, all_files)

            # ── 5. Logic ─────────────────────────────────────────────
            logger.info("[Pipeline] ▶ Running Agent Logic (patch methods into UI skeleton)...")
            svc_contract_path = self._service_contract_path(form_name)
            logic_result = await LogicAgent().run(AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,
                upstream_files=all_files.copy(),   # ← includes the UI skeleton files
                logic_event_class="all",
                mongodb_data={"service_contract_path": str(svc_contract_path)} if svc_contract_path else {},
            ))
            self._record(result, "logic", logic_result, all_files)

            # ── 6. GraphView (advisory, never blocks the form) ───────
            logger.info("[Pipeline] ▶ Running Agent GraphView...")
            try:
                from agents.graphview.agent_graphview import AgentGraphView
                gv_result = await AgentGraphView().run(AgentInput(
                    form_name=form_name,
                    bd_json=bd_json,
                    dd_json=dd_json,
                    upstream_files=all_files.copy(),
                ))
                result.agent_results["graphview"] = gv_result
                if gv_result.status == "success":
                    logger.info("[Pipeline]   ✅ GraphView Status: PASS")
                else:
                    logger.warning("[Pipeline]   ⚠️ GraphView Status: FAIL or Error (%s)", gv_result.error)
            except Exception as gv_err:
                logger.error("[Pipeline]   ❌ GraphView execution error: %s", gv_err, exc_info=True)

            # ── 7. Write → Build ─────────────────────────────────────
            # One file per target: the last agent wins (Logic's patched ViewModel over UI's skeleton)
            all_files = dedupe_generated_files(all_files, self.writer)
            result.all_files = all_files
            logger.info("[Pipeline] ▶ Writing %d files to solution...", len(all_files))
            self.writer.write_all(all_files, overwrite=True)

            logger.info("[Pipeline] ▶ Building solution...")
            build_result = self.verifier.build_and_fix(all_files)
            result.build_success = build_result.success
            result.build_attempts = build_result.attempt
            if build_result.success:
                logger.info("[Pipeline] ✅ Build PASSED (attempt %d)", build_result.attempt)
            else:
                logger.warning(
                    "[Pipeline] ⚠️ Build FAILED after %d attempts (%d errors)",
                    build_result.attempt, len(build_result.errors),
                )

            result.status, result.error = self._form_status(result)

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            logger.error("[Pipeline] ❌ Pipeline error: %s", e, exc_info=True)

        result.duration_sec = round(time.time() - start, 2)
        logger.info(
            "[Pipeline] 🏁 %s %s in %.1fs — %d files, build=%s",
            form_name, result.status, result.duration_sec, len(result.all_files),
            "✅" if result.build_success else "❌",
        )
        return result

    async def run_batch(self, form_names: list[str]) -> PipelineResult:
        """Run pipeline for multiple forms sequentially."""
        pipeline_result = PipelineResult()
        start = time.time()

        # Ensure base classes exist (once)
        logger.info("[Pipeline] ▶ Ensuring base classes...")
        pipeline_result.base_classes_created = ensure_base_classes(self.writer)

        for i, form_name in enumerate(form_names, 1):
            logger.info("=" * 60)
            logger.info("[Pipeline] Form %d/%d: %s", i, len(form_names), form_name)
            logger.info("=" * 60)
            form_result = await self.run_form(form_name)
            pipeline_result.forms.append(form_result)
            pipeline_result.total_files += len(form_result.all_files)

        pipeline_result.total_duration_sec = round(time.time() - start, 2)

        success = sum(1 for f in pipeline_result.forms if f.status == "success")
        logger.info(
            "[Pipeline] 📊 Batch complete: %d/%d success, %d files, %.1fs",
            success, len(pipeline_result.forms),
            pipeline_result.total_files, pipeline_result.total_duration_sec,
        )
        return pipeline_result

    async def run_all(self) -> PipelineResult:
        """Discover all forms with BD+DD JSON and run pipeline."""
        form_names = self._discover_forms()
        logger.info("[Pipeline] Discovered %d forms: %s", len(form_names), form_names)
        return await self.run_batch(form_names)

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _record(result: FormResult, name: str, output: AgentOutput, all_files: list[GeneratedFile]) -> None:
        result.agent_results[name] = output
        if output.status == "success":
            all_files.extend(output.files)
            logger.info("[Pipeline]   ✅ %s: %d files", name, len(output.files))
        else:
            logger.error("[Pipeline]   ❌ %s failed: %s", name, output.error)

    @staticmethod
    def _form_status(result: FormResult) -> tuple[str, Optional[str]]:
        """("success", None) only when every required agent succeeded and the build passed."""
        problems = [
            f"{name}: {out.error or out.status}"
            for name in REQUIRED_AGENTS
            if (out := result.agent_results.get(name)) is not None and out.status != "success"
        ]
        if not result.build_success:
            problems.append(f"build failed after {result.build_attempts} attempt(s)")
        return ("error", "; ".join(problems)) if problems else ("success", None)

    @staticmethod
    def _load_repo_contract(form_name: str) -> dict:
        path = AGENTS_DIR / "repo" / "outputs" / f"{form_name}.json"
        if not path.exists():
            return {}
        try:
            contract = json.loads(path.read_text(encoding="utf-8"))
            logger.info("[Pipeline]   Service: loaded repo contract from %s", path)
            return contract
        except Exception as exc:
            logger.warning("[Pipeline]   Service: failed to load repo ref JSON: %s", exc)
            return {}

    @staticmethod
    def _service_contract_path(form_name: str) -> Optional[Path]:
        svc_dir = AGENTS_DIR / "service" / "outputs" / form_name
        return next(
            (p for p in (svc_dir / f"{form_name}.json", svc_dir / "service_contract.json") if p.exists()),
            None,
        )

    def _discover_forms(self) -> list[str]:
        """Find forms that have both BD and DD JSON."""
        bd_forms = {f.stem for f in BD_SCREEN_DIR.glob("*.json")} if BD_SCREEN_DIR.exists() else set()
        dd_forms = {f.stem for f in DD_FORM_DIR.glob("*.json")} if DD_FORM_DIR.exists() else set()
        return sorted(bd_forms & dd_forms)

    @staticmethod
    def _load_json(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"JSON not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_report(self, result: PipelineResult, output_dir: Path | None = None) -> Path:
        """Save pipeline execution report as JSON."""
        out_dir = output_dir or LAYER5_DIR / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_forms": len(result.forms),
            "total_files": result.total_files,
            "total_duration_sec": result.total_duration_sec,
            "base_classes_created": result.base_classes_created,
            "forms": [
                {
                    "form_name": fr.form_name,
                    "status": fr.status,
                    "files_count": len(fr.all_files),
                    "build_success": fr.build_success,
                    "build_attempts": fr.build_attempts,
                    "duration_sec": fr.duration_sec,
                    "error": fr.error,
                    "files": [{"path": f.path, "generator": f.generator, "agent": f.agent} for f in fr.all_files],
                }
                for fr in result.forms
            ],
        }

        report_path = out_dir / "pipeline_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[Pipeline] Report saved: %s", report_path)
        return report_path
