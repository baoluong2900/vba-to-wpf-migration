"""
pipeline/orchestrator.py — Layer 5 Pipeline Orchestrator

Pipeline thứ tự chuẩn:
  1. Agent Repo    → Entity, DTO, Interface, Repository
  2. Agent Service → IService, Service, service_contract.json
  3. Agent UI      → ViewModel skeleton (F000→F009 Commands, DI, SetProperty) + XAML + code-behind
  4. Agent Logic   → LLM gen method bodies → patch vào UI skeleton ViewModel
  5. Write to WPF source → dotnet build

GraphView tạm thời disabled.
"""
from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import AgentInput, AgentOutput, GeneratedFile
from core.config import vba_brain_PROJECT_DIR
from pipeline.file_writer import SolutionWriter
from pipeline.build_verify import BuildVerifier
from pipeline.base_gen import ensure_base_classes

logger = logging.getLogger(__name__)

LAYER4_DIR    = Path(__file__).parent.parent.parent / "layer4" / "inputs"
BD_SCREEN_DIR = LAYER4_DIR / "BD_json" / "screen"
DD_FORM_DIR   = LAYER4_DIR / "DD_json" / "form"

AGENTS_DIR = Path(__file__).parent.parent / "agents"


@dataclass
class FormResult:
    form_name: str
    status: str = "pending"
    agent_results: dict[str, AgentOutput] = field(default_factory=dict)
    all_files: list[GeneratedFile] = field(default_factory=list)
    build_success: bool = False
    build_attempts: int = 0
    error: Optional[str] = None
    duration_sec: float = 0.0


@dataclass
class PipelineResult:
    forms: list[FormResult] = field(default_factory=list)
    total_files: int = 0
    total_duration_sec: float = 0.0
    base_classes_created: list[str] = field(default_factory=list)


class L5Orchestrator:
    """
    Pipeline orchestrator — thứ tự: Repo → Service → UI → Logic → Write → Build.

    UI chạy TRƯỚC Logic để tạo skeleton ViewModel đầy đủ.
    Logic patch method bodies vào skeleton đó — không tự gen ViewModel mới.
    """

    def __init__(self, solution_dir: Path | None = None):
        self.solution_dir = solution_dir or vba_brain_PROJECT_DIR
        self.writer  = SolutionWriter(self.solution_dir)
        self.verifier = BuildVerifier(self.solution_dir)

    async def run_form(self, form_name: str) -> FormResult:
        result = FormResult(form_name=form_name, status="running")
        start  = time.time()

        logger.info("=" * 60)
        logger.info("[Pipeline] 🚀 %s", form_name)
        logger.info("=" * 60)

        try:
            bd_json = self._load_json(BD_SCREEN_DIR / f"{form_name}.json")
            dd_json = self._load_json(DD_FORM_DIR   / f"{form_name}.json")
            all_files: list[GeneratedFile] = []

            # ── 1. Repo ──────────────────────────────────────────────
            logger.info("[Pipeline] ▶ [1/4] Agent Repo")
            from agents.repo.agent_repo import RepoAgent
            repo_result = await RepoAgent().run(AgentInput(
                form_name=form_name, bd_json=bd_json, dd_json=dd_json,
            ))
            result.agent_results["repo"] = repo_result
            if repo_result.status == "success":
                all_files.extend(repo_result.files)
                logger.info("[Pipeline]   ✅ Repo: %d files", len(repo_result.files))
            else:
                logger.error("[Pipeline]   ❌ Repo: %s", repo_result.error)

            # ── 2. Service ───────────────────────────────────────────
            logger.info("[Pipeline] ▶ [2/4] Agent Service")
            svc_repo_contract: dict = {}
            _repo_ref = AGENTS_DIR / "repo" / "outputs" / f"{form_name}.json"
            if _repo_ref.exists():
                try:
                    svc_repo_contract = json.loads(_repo_ref.read_text(encoding="utf-8"))
                except Exception as _e:
                    logger.warning("[Pipeline]   Service: repo ref load failed: %s", _e)

            from agents.service.agent_service import ServiceAgent
            svc_result = await ServiceAgent().run(AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,
                upstream_files=all_files.copy(),
                mongodb_data={"repo_contract": svc_repo_contract} if svc_repo_contract else {},
            ))
            result.agent_results["service"] = svc_result
            if svc_result.status == "success":
                all_files.extend(svc_result.files)
                logger.info("[Pipeline]   ✅ Service: %d files", len(svc_result.files))
            else:
                logger.error("[Pipeline]   ❌ Service: %s", svc_result.error)

            # ── 3. UI (skeleton) ─────────────────────────────────────
            # Tạo skeleton ViewModel đầy đủ trước:
            #   - F000→F009 Commands + FxxxAsync stubs
            #   - DI: IFLoginService + IAppWindowService
            #   - Properties: SetProperty backing field
            #   - XAML với Command bindings (không event handler)
            #   - code-behind MVVM thuần: chỉ inline lambda + PasswordBox
            logger.info("[Pipeline] ▶ [3/4] Agent UI  (ViewModel skeleton + XAML)")
            from agents.ui.agent_ui import UIAgent
            ui_result = await UIAgent().run(AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,
                upstream_files=all_files.copy(),
            ))
            result.agent_results["ui"] = ui_result
            if ui_result.status == "success":
                all_files.extend(ui_result.files)
                logger.info("[Pipeline]   ✅ UI: %d files", len(ui_result.files))
            else:
                logger.error("[Pipeline]   ❌ UI: %s", ui_result.error)

            # ── 4. Logic (patch) ─────────────────────────────────────
            # Đọc skeleton từ ui/outputs/ → LLM gen method bodies
            # → patch từng FxxxAsync() body vào skeleton file
            # KHÔNG gen ViewModel mới (MethodMerger fallback đã bị disabled)
            logger.info("[Pipeline] ▶ [4/4] Agent Logic (patch method bodies into skeleton)")
            _svc_dir = AGENTS_DIR / "service" / "outputs" / form_name
            _svc_contract = next((
                p for p in [_svc_dir / f"{form_name}.json", _svc_dir / "service_contract.json"]
                if p.exists()
            ), None)
            logic_result = await LogicAgent().run(AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,
                upstream_files=all_files.copy(),   # bao gồm UI skeleton files
                logic_event_class="all",
                mongodb_data={
                    "service_contract_path": str(_svc_contract)
                } if _svc_contract.exists() else {},
            ))
            result.agent_results["logic"] = logic_result
            if logic_result.status == "success":
                all_files.extend(logic_result.files)
                logger.info("[Pipeline]   ✅ Logic: %d files", len(logic_result.files))
            else:
                logger.error("[Pipeline]   ❌ Logic: %s", logic_result.error)

            # ── GraphView: disabled tạm thời ─────────────────────────
            # TODO: re-enable sau khi UI→Logic pipeline ổn định
            # logger.info("[Pipeline] ▶ Agent GraphView  (disabled)")

            result.all_files = all_files

            # ── Write → Build ────────────────────────────────────────
            logger.info("[Pipeline] ▶ Writing %d files", len(all_files))
            self.writer.write_all(all_files, overwrite=True)

            logger.info("[Pipeline] ▶ Building solution")
            build = self.verifier.build_and_fix(all_files)
            result.build_success  = build.success
            result.build_attempts = build.attempt
            if build.success:
                logger.info("[Pipeline] ✅ Build PASSED (attempt %d)", build.attempt)
            else:
                logger.warning("[Pipeline] ⚠️ Build FAILED after %d attempts", build.attempt)

            result.status = "success"

        except Exception as exc:
            result.status = "error"
            result.error  = str(exc)
            logger.error("[Pipeline] ❌ %s", exc, exc_info=True)

        result.duration_sec = round(time.time() - start, 2)
        logger.info(
            "[Pipeline] 🏁 %s  %.1fs  %d files  build=%s",
            form_name, result.duration_sec, len(result.all_files),
            "✅" if result.build_success else "❌",
        )
        return result

    async def run_batch(self, form_names: list[str]) -> PipelineResult:
        pipeline_result = PipelineResult()
        start = time.time()

        logger.info("[Pipeline] ▶ Ensuring base classes...")
        pipeline_result.base_classes_created = ensure_base_classes(self.writer)

        for i, form_name in enumerate(form_names, 1):
            logger.info("[Pipeline] Form %d/%d: %s", i, len(form_names), form_name)
            form_result = await self.run_form(form_name)
            pipeline_result.forms.append(form_result)
            pipeline_result.total_files += len(form_result.all_files)

        pipeline_result.total_duration_sec = round(time.time() - start, 2)
        success = sum(1 for f in pipeline_result.forms if f.status == "success")
        logger.info(
            "[Pipeline] 📊 Batch: %d/%d OK  %d files  %.1fs",
            success, len(pipeline_result.forms),
            pipeline_result.total_files, pipeline_result.total_duration_sec,
        )
        return pipeline_result

    async def run_all(self) -> PipelineResult:
        form_names = self._discover_forms()
        logger.info("[Pipeline] Discovered %d forms", len(form_names))
        return await self.run_batch(form_names)

    # ── helpers ──────────────────────────────────────────────────────

    def _discover_forms(self) -> list[str]:
        bd = {f.stem for f in BD_SCREEN_DIR.glob("*.json")} if BD_SCREEN_DIR.exists() else set()
        dd = {f.stem for f in DD_FORM_DIR.glob("*.json")}   if DD_FORM_DIR.exists()   else set()
        return sorted(bd & dd)

    @staticmethod
    def _load_json(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"JSON not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_report(self, result: PipelineResult, output_dir: Path | None = None) -> Path:
        out_dir = output_dir or Path(__file__).parent.parent / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "timestamp":          time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_forms":        len(result.forms),
            "total_files":        result.total_files,
            "total_duration_sec": result.total_duration_sec,
            "base_classes_created": result.base_classes_created,
            "forms": [
                {
                    "form_name":      fr.form_name,
                    "status":         fr.status,
                    "files_count":    len(fr.all_files),
                    "build_success":  fr.build_success,
                    "build_attempts": fr.build_attempts,
                    "duration_sec":   fr.duration_sec,
                    "error":          fr.error,
                    "files": [
                        {"path": f.path, "generator": f.generator, "agent": f.agent}
                        for f in fr.all_files
                    ],
                }
                for fr in result.forms
            ],
        }
        report_path = out_dir / "pipeline_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[Pipeline] Report: %s", report_path)
        return report_path


# lazy import để tránh circular import khi orchestrator được load
def LogicAgent():  # type: ignore[override]
    from agents.logic.agent_logic import LogicAgent as _LA
    return _LA()


import json
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import AgentInput, AgentOutput, GeneratedFile
from core.config import vba_brain_PROJECT_DIR
from pipeline.file_writer import SolutionWriter
from pipeline.build_verify import BuildVerifier
from pipeline.base_gen import ensure_base_classes

logger = logging.getLogger(__name__)

# BD/DD JSON directories
LAYER4_DIR = Path(__file__).parent.parent.parent / "layer4" / "inputs"
BD_SCREEN_DIR = LAYER4_DIR / "BD_json" / "screen"
DD_FORM_DIR = LAYER4_DIR / "DD_json" / "form"


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
            # Load BD/DD JSON
            bd_json = self._load_json(BD_SCREEN_DIR / f"{form_name}.json")
            dd_json = self._load_json(DD_FORM_DIR / f"{form_name}.json")

            base_input = AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,
            )

            all_files: list[GeneratedFile] = []

            # ── Agent 1: Repo ────────────────────────
            logger.info("[Pipeline] ▶ Running Agent Repo...")
            from agents.repo.agent_repo import RepoAgent
            repo_agent = RepoAgent()
            repo_result = await repo_agent.run(base_input)
            result.agent_results["repo"] = repo_result

            if repo_result.status == "success":
                all_files.extend(repo_result.files)
                logger.info("[Pipeline]   ✅ Repo: %d files", len(repo_result.files))
            else:
                logger.error("[Pipeline]   ❌ Repo failed: %s", repo_result.error)

            # ── Agent 2: Service ─────────────────────
            logger.info("[Pipeline] ▶ Running Agent Service...")
            from agents.service.agent_service import ServiceAgent

            # Pass repo contract JSON directly from the in-memory agent_repo output
            # so Service agent does NOT need to re-query MongoDB (avoids timing issues).
            svc_repo_contract: dict = {}
            if repo_result.status == "success":
                # Prefer the fill_json reference JSON saved by RepoAgent (agents/repo/outputs/{form}.json)
                _repo_ref_path = (
                    Path(__file__).parent.parent
                    / "agents" / "repo" / "outputs" / f"{form_name}.json"
                )
                if _repo_ref_path.exists():
                    try:
                        svc_repo_contract = json.loads(_repo_ref_path.read_text(encoding="utf-8"))
                        logger.info("[Pipeline]   Service: loaded repo contract from %s", _repo_ref_path)
                    except Exception as _e:
                        logger.warning("[Pipeline]   Service: failed to load repo ref JSON: %s", _e)

            svc_input = AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,                   # ← pass DD so service agent skips MongoDB re-load
                upstream_files=all_files.copy(),
                mongodb_data={"repo_contract": svc_repo_contract} if svc_repo_contract else {},
            )
            svc_agent = ServiceAgent()
            svc_result = await svc_agent.run(svc_input)
            result.agent_results["service"] = svc_result

            if svc_result.status == "success":
                all_files.extend(svc_result.files)
                logger.info("[Pipeline]   ✅ Service: %d files", len(svc_result.files))

                # ── Refresh Logic input snapshots immediately after Service gen ──
                # Ensures F_Login_service.json has up-to-date response_props
                # (VersionComment, AuthEntity, etc.) before Logic agent runs.
                try:
                    from agents.logic.agent_logic import LogicAgent as _LARefresh
                    _la_refresh = _LARefresh()
                    _refresh_input = AgentInput(
                        form_name=form_name,
                        bd_json=bd_json,
                        dd_json=dd_json,
                        upstream_files=all_files.copy(),
                        logic_event_class="all",
                    )
                    _refresh_result = await _la_refresh.run(_refresh_input, input_only=True)
                    logger.info("[Pipeline]   ✅ Logic input refreshed (service_context synced with latest DTOs)")
                except Exception as _re:
                    logger.warning("[Pipeline]   ⚠️  Logic input refresh failed: %s", _re)
            else:
                logger.error("[Pipeline]   ❌ Service failed: %s", svc_result.error)

            # ── Agent 3: UI ──────────────────────────
            # UI phải chạy TRƯỚC Logic để tạo skeleton ViewModel đầy đủ
            # (F000→F009 Commands, DI, SetProperty pattern)
            # Logic Agent sau đó patch method bodies vào skeleton đó.
            logger.info("[Pipeline] ▶ Running Agent UI (skeleton first)...")
            from agents.ui.agent_ui import UIAgent
            ui_input = AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,
                upstream_files=all_files.copy(),
            )
            ui_agent = UIAgent()
            ui_result = await ui_agent.run(ui_input)
            result.agent_results["ui"] = ui_result

            if ui_result.status == "success":
                all_files.extend(ui_result.files)
                logger.info("[Pipeline]   ✅ UI skeleton: %d files", len(ui_result.files))
            else:
                logger.error("[Pipeline]   ❌ UI failed: %s", ui_result.error)

            # ── Agent 4: Logic ───────────────────────
            # Logic đọc UI skeleton ViewModel → LLM gen method bodies → patch vào
            logger.info("[Pipeline] ▶ Running Agent Logic (patch methods into UI skeleton)...")
            from agents.logic.agent_logic import LogicAgent

            _svc_dir2 = Path(__file__).parent.parent / "agents" / "service" / "outputs" / form_name
            _svc_contract_path = next((
                p for p in [_svc_dir2 / f"{form_name}.json", _svc_dir2 / "service_contract.json"]
                if p.exists()
            ), None)
            logic_input = AgentInput(
                form_name=form_name,
                bd_json=bd_json,
                dd_json=dd_json,
                upstream_files=all_files.copy(),   # ← bao gồm UI skeleton files
                logic_event_class="all",
                mongodb_data={
                    "service_contract_path": str(_svc_contract_path)
                } if _svc_contract_path.exists() else {},
            )
            logic_agent = LogicAgent()
            logic_result = await logic_agent.run(logic_input)
            result.agent_results["logic"] = logic_result

            if logic_result.status == "success":
                all_files.extend(logic_result.files)
                logger.info("[Pipeline]   ✅ Logic: %d files", len(logic_result.files))
            else:
                logger.error("[Pipeline]   ❌ Logic failed: %s", logic_result.error)

            # ── Agent 5: GraphView ───────────────────
            logger.info("[Pipeline] ▶ Running Agent GraphView...")
            try:
                from agents.graphview.agent_graphview import AgentGraphView
                gv_input = AgentInput(
                    form_name=form_name,
                    bd_json=bd_json,
                    dd_json=dd_json,
                    upstream_files=all_files.copy(),
                )
                gv_agent = AgentGraphView()
                gv_result = await gv_agent.run(gv_input)
                result.agent_results["graphview"] = gv_result
                if gv_result.status == "success":
                    logger.info("[Pipeline]   ✅ GraphView Status: PASS")
                else:
                    logger.warning("[Pipeline]   ⚠️ GraphView Status: FAIL or Error (%s)", gv_result.error)
            except Exception as gv_err:
                logger.error("[Pipeline]   ❌ GraphView execution error: %s", gv_err, exc_info=True)

            result.all_files = all_files

            # ── Write files to solution ──────────────
            logger.info("[Pipeline] ▶ Writing %d files to solution...", len(all_files))
            self.writer.write_all(all_files, overwrite=True)

            # ── Build & Verify ───────────────────────
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

            result.status = "success"

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            logger.error("[Pipeline] ❌ Pipeline error: %s", e, exc_info=True)

        result.duration_sec = round(time.time() - start, 2)
        logger.info(
            "[Pipeline] 🏁 %s completed in %.1fs — %d files, build=%s",
            form_name, result.duration_sec, len(result.all_files),
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
            logger.info(
                "\n{'=' * 60}\n[Pipeline] Form %d/%d: %s\n{'=' * 60}",
                i, len(form_names), form_name,
            )
            form_result = await self.run_form(form_name)
            pipeline_result.forms.append(form_result)
            pipeline_result.total_files += len(form_result.all_files)

        pipeline_result.total_duration_sec = round(time.time() - start, 2)

        # Summary
        success = sum(1 for f in pipeline_result.forms if f.status == "success")
        failed = len(pipeline_result.forms) - success
        logger.info(
            "\n[Pipeline] 📊 Batch complete: %d/%d success, %d files, %.1fs",
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

    def _discover_forms(self) -> list[str]:
        """Find forms that have both BD and DD JSON."""
        bd_forms = set()
        dd_forms = set()

        if BD_SCREEN_DIR.exists():
            for f in BD_SCREEN_DIR.glob("*.json"):
                bd_forms.add(f.stem)

        if DD_FORM_DIR.exists():
            for f in DD_FORM_DIR.glob("*.json"):
                dd_forms.add(f.stem)

        # Only forms with BOTH BD and DD
        common = sorted(bd_forms & dd_forms)
        return common

    @staticmethod
    def _load_json(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"JSON not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_report(self, result: PipelineResult, output_dir: Path | None = None) -> Path:
        """Save pipeline execution report as JSON."""
        out_dir = output_dir or Path(__file__).parent.parent / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_forms": len(result.forms),
            "total_files": result.total_files,
            "total_duration_sec": result.total_duration_sec,
            "base_classes_created": result.base_classes_created,
            "forms": [],
        }

        for fr in result.forms:
            form_report = {
                "form_name": fr.form_name,
                "status": fr.status,
                "files_count": len(fr.all_files),
                "build_success": fr.build_success,
                "build_attempts": fr.build_attempts,
                "duration_sec": fr.duration_sec,
                "error": fr.error,
                "files": [{"path": f.path, "generator": f.generator, "agent": f.agent} for f in fr.all_files],
            }
            report["forms"].append(form_report)

        report_path = out_dir / "pipeline_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[Pipeline] Report saved: %s", report_path)
        return report_path
