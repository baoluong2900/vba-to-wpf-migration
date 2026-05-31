"""
agents/logic/agent_logic.py — Agent Logic: Gen ViewModel.cs

Full pipeline:
  1. Load data (BD events, DD specs, Service interface, XAML bindings)
  2. Event mapping (event_mapper.py) — deterministic
  3. Build chunks (chunk_builder.py) — 1 chunk per event
  4. Filter chunks (skip SYS/UI action_type)
  5. Save input snapshot
  6. LLM call per VALID chunk via LangGraph StateGraph (map-reduce)
  7. Merge methods → complete ViewModel.cs (deterministic)
  8. Save output (outputs/ + WPF source)

Ref: Agent_Logic.md design doc
Ref: agents/ui/agent_ui.py — same LangGraph chunked pattern
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, TypedDict, Annotated
import operator

# Add backend/layer5 to sys.path
LAYER5_DIR = Path(__file__).parent.parent.parent.resolve()
if str(LAYER5_DIR) not in sys.path:
    sys.path.append(str(LAYER5_DIR))

from pathlib import Path

# Add Layer 5 to path (for core.models, etc.)
layer5_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(layer5_dir))

# Add backend to path (for layer2.db.mongo_client)
backend_dir = layer5_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from langgraph.graph import StateGraph, START, END

from core.models import BaseAgent, AgentInput, AgentOutput, GeneratedFile
from core.config import MONGO_URI, MONGO_DB, AVAILABLE_MODELS, DEFAULT_MODEL, TARGET_LANGUAGE
from llm.llm_client import L5LLMClient, extract_code_block
from layer2.db.mongo_client import get_db
from agents.logic.mapping_ast.event_mapper import EventMapper
from agents.logic.chunk_builder import ChunkBuilder
from agents.logic.tool_method_merger import MethodMerger

logger = logging.getLogger(__name__)

AGENT_DIR   = Path(__file__).parent
INPUTS_DIR  = AGENT_DIR / "inputs"
OUTPUTS_DIR = AGENT_DIR / "outputs"

# Avalonia source ViewModels folder
WPF_VIEWMODELS_DIR = (
    AGENT_DIR.parent.parent.parent.parent.parent  # → src/
    / "wpf" / "vba_brain.UI.Avalonia" / "ViewModels"
)


# ──────────────────────────────────────────────────────────────────────────────
# LangGraph State
# ──────────────────────────────────────────────────────────────────────────────

class LogicChunkState(TypedDict):
    # ── Static inputs (set once, never mutated) ──────────────────────────────
    form_name:       str
    system_prompt:   str
    llm:             Any
    model_override:  Any

    # ── Chunk list (set by split_node) ───────────────────────────────────────
    chunks:          list[dict]   # list of chunk dicts (one per event)
    total_chunks:    int
    current_idx:     int

    # ── Outputs (accumulated via operator.add) ────────────────────────────────
    # Annotated so LangGraph merges partial lists across nodes automatically
    method_outputs:  Annotated[list[dict], operator.add]


class LogicAgent(BaseAgent):
    """
    Agent Logic — Gen ViewModel.cs from BD events + DD specs.
    Pipeline order: #3 (after Agent Service, before Agent UI).

    Key difference from old version:
    - Chunk-per-event (not single LLM call)
    - Event mapper (VBA → C# command/method)
    - Method merger (deterministic merge → zero token)
    - Full business logic (not skeleton-only)
    """

    def __init__(self):
        self._event_mapper = EventMapper()
        self._chunk_builder = ChunkBuilder()
        # MethodMerger không còn dùng — Logic Agent chỉ patch vào UI skeleton

    @property
    def name(self) -> str:
        return "logic"

    async def run(self, input: AgentInput, input_only: bool = False) -> AgentOutput:
        form_name = input.form_name

        # ── Setup LLM config based on override ──────────────────────
        model_override = input.model_override
        if isinstance(model_override, str):
            model_override = AVAILABLE_MODELS.get(model_override)

        logger.info(
            "[Agent Logic] Starting for form: %s (model: %s)",
            form_name, getattr(model_override, 'model_id', 'default'),
        )

        try:
            # ── Step 0: Resolve WPF class names (EN) ────────────────────────
            from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
            _name_map = _load_form_name_map()
            _, vm_file_stem = _resolve_wpf_names(form_name, _name_map)

            # ── Step 1: Load data sources ───────────────────────────────
            bd_json = input.bd_json or self._load_bd_json(form_name)
            dd_json = input.dd_json or self._load_dd_json(form_name)

            # Handle both flat and nested MongoDB structure (sheet_2_layout/sheet_3_screen_edit)
            bd_events = bd_json.get("events")
            if not bd_events and "sheet_2_layout" in bd_json:
                bd_events = bd_json["sheet_2_layout"].get("events", [])
            
            bd_items = bd_json.get("items")
            if not bd_items and "sheet_3_screen_edit" in bd_json:
                bd_items = bd_json["sheet_3_screen_edit"].get("items", [])
            
            dd_specs = dd_json.get("sheet_3_detail_specs", [])
            
            # Upstream context
            service_interface = self._load_service_interface(input.upstream_files, form_name)
            xaml_bindings     = self._load_xaml_bindings(form_name, input.upstream_files)
            service_name      = self._detect_service_name(service_interface)

            logger.info(
                "[Agent Logic] Data loaded: %d events, %d items, service=%s",
                len(bd_events), len(bd_items), service_name or "(none)",
            )

            # ── Step 2: Event mapping (deterministic) ───────────────────
            mapped_events = self._event_mapper.map_all_events(bd_events)

            # ── Step 3: Build chunks ────────────────────────────────────
            all_chunks = self._chunk_builder.build_chunks(
                bd_events=bd_events,
                dd_specs=dd_specs,
                mapped_events=mapped_events,
                bd_items=bd_items,
                service_interface=service_interface,
                xaml_bindings=xaml_bindings
            )
            # Inject form_name into each chunk for token tracker
            for _c in all_chunks:
                _c["form_name"] = form_name

            # ── Step 3b: Inject cs_stub + event_class + structured service_context ──
            cs_stubs = self._chunk_builder._load_cs_stubs(form_name)
            trigger_map = {
                "クリック時":        "Click",
                "ダブルクリック時":   "DblClick",
                "更新後処理":        "AfterUpdate",
                "キー押下時":        "KeyDown",
                "画面を開く時":      "Open",
                "フォーム読み込み後": "Load",
            }
            for _c in all_chunks:
                _bd    = _c.get("bd_event", {})
                _notes = _bd.get("notes", "")

                # ── cs_stub: match by VBA handler or physical_name+trigger suffix ──
                _stub = cs_stubs.get(_notes)
                if not _stub:
                    _physical = _bd.get("physical_name", "")
                    _suffix   = trigger_map.get(_bd.get("event_trigger", ""), "")
                    if _physical and _suffix:
                        _stub = cs_stubs.get(f"{_physical}_{_suffix}")
                _c["cs_stub"] = _stub or None

                # ── event_class: raw BD event có references (queries/tables) ────
                # classify_event_class() nhận {logic_detail: {code, references}, dd_steps}
                _refs = _bd.get("references", {})
                _c["event_class"] = self._chunk_builder.classify_event_class({
                    "logic_detail": {
                        "code":       _bd.get("vba_code", ""),
                        "references": _refs,
                    },
                    "dd_steps": _c.get("dd_steps", {}),
                })

                # ── structured service_context per-chunk ─────────────────────────
                # Convert blob string → compact {interface_method, request.properties, ...}
                _raw_svc = _c.get("service_context", "")
                if _raw_svc and isinstance(_raw_svc, str):
                    _module_id = _bd.get("module_id", _bd.get("event_id", ""))
                    _structured = self._chunk_builder._build_structured_service_context(
                        _raw_svc, _module_id, form_name=form_name
                    )
                    if _structured:
                        _c["service_context"] = _structured

            logger.info(
                "[Agent Logic] cs_stubs: %d loaded, %d matched | event_class: %d SERVICE, %d UI",
                len(cs_stubs),
                sum(1 for _c in all_chunks if _c.get("cs_stub")),
                sum(1 for _c in all_chunks if _c.get("event_class") == "SERVICE"),
                sum(1 for _c in all_chunks if _c.get("event_class") == "UI"),
            )

            # ── Step 4: Filter chunks ───────────────────────────────────
            valid_chunks = self._chunk_builder.filter_valid_chunks(all_chunks)
            sys_chunks   = self._chunk_builder.get_sys_chunks(all_chunks)

            logger.info(
                "[Agent Logic] Chunks: %d total → %d VALID (LLM), %d SYS (stub), %d UI (skip)",
                len(all_chunks), len(valid_chunks), len(sys_chunks),
                len(all_chunks) - len(valid_chunks) - len(sys_chunks),
            )

            # ── Step 4b: Dynamic filtering by event class configuration ─
            event_class_filter = getattr(input, "logic_event_class", "ui")
            if event_class_filter == "ui":
                valid_chunks = [c for c in valid_chunks if c.get("event_class") == "UI"]
                logger.info("[Agent Logic] Filtered to %d UI chunks for processing", len(valid_chunks))
            elif event_class_filter == "service":
                valid_chunks = [c for c in valid_chunks if c.get("event_class") == "SERVICE"]
                logger.info("[Agent Logic] Filtered to %d SERVICE chunks for processing", len(valid_chunks))
            else:
                logger.info("[Agent Logic] Processing ALL %d chunks (no event class filter)", len(valid_chunks))

            # ── Step 5: Save input snapshot ─────────────────────────────
            if input_only:
                self._chunk_builder.save_full_input(form_name, all_chunks)
                logger.info("[Agent Logic] Unified input snapshot saved to inputs/%s.json", form_name)

                # Split events thành 2 files: UI và SERVICE
                formatted_events = self._chunk_builder._build_formatted_events(form_name, all_chunks)
                ui_path, service_path = self._chunk_builder.save_split_inputs(
                    form_name, formatted_events
                )
                logger.info("[Agent Logic] Split inputs saved:")
                logger.info("  UI      → %s", ui_path)
                logger.info("  SERVICE → %s", service_path)

                logger.info("[Agent Logic] Input-only mode: stopping after saving snapshots.")
                return AgentOutput(
                    agent=self.name,
                    form_name=form_name,
                    status="success",
                    files=[],
                    metadata={
                        "input_only":   True,
                        "chunks_total": len(all_chunks),
                        "chunks_valid": len(valid_chunks),
                        "split_ui":     ui_path,
                        "split_service": service_path,
                    }
                )

            # ── Step 6: Process VALID chunks with LLM via LangGraph ─────
            llm = L5LLMClient()
            system_prompt = self.load_prompt("agent_logic.md")

            method_outputs = self._run_chunks_graph(
                chunks=valid_chunks,
                llm=llm,
                system_prompt=system_prompt,
                form_name=form_name,
                model_override=model_override,
            )

            # Sync generated_code back into chunks for output snapshot
            outputs_by_event = {m["event_id"]: m for m in method_outputs}
            for chunk in valid_chunks:
                eid = chunk["bd_event"].get("event_id", "")
                out = outputs_by_event.get(eid)
                chunk["generated_code"] = out.get("code", "// No code returned") if out else "// Skipped"

            # ── Step 6b: Deterministic SYS bodies (no LLM) ──────────────
            # Gen code for SYS events: quit dialog, taskkill, keydown stub
            sys_bodies = self._gen_sys_bodies(all_chunks)
            if sys_bodies:
                method_outputs = method_outputs + sys_bodies
                logger.info(
                    "[Agent Logic] SYS deterministic: %d bodies added (total methods: %d)",
                    len(sys_bodies), len(method_outputs),
                )

            # ── Step 7: Save final output snapshot ──────────────────────
            # Save all_chunks which now include 'generated_code' for VALID chunks
            self._chunk_builder.save_full_input(form_name, all_chunks, suffix="_output")
            logger.info("[Agent Logic] Final output snapshot with code saved to inputs/%s_output.json", form_name)

            # ── Step 8: Patch LLM method bodies vào UI skeleton ViewModel ──────
            # Design: Agent UI tạo skeleton đầy đủ (F000→F009, DI, Commands).
            # Agent Logic chỉ fill method bodies — KHÔNG gen ViewModel mới.
            vm_filename  = f"{vm_file_stem}.cs"
            # Priority 1: UI agent outputs/ (vừa được gen ở step trước trong pipeline)
            _ui_vm  = AGENT_DIR.parent / "ui" / "outputs" / form_name / "ViewModels" / vm_filename
            # Priority 2: WPF source (nếu UI agent đã write thẳng vào source)
            _src_vm = WPF_VIEWMODELS_DIR / vm_filename

            _existing_vm: Path | None = (
                _ui_vm  if _ui_vm.exists()  else
                _src_vm if _src_vm.exists() else
                None
            )

            if not _existing_vm:
                raise FileNotFoundError(
                    f"[Agent Logic] UI skeleton ViewModel not found: {vm_filename}\n"
                    f"  Expected at: {_ui_vm}\n"
                    f"  Or at:       {_src_vm}\n"
                    f"  → Run Agent UI first (pipeline order: Repo→Service→UI→Logic)"
                )

            logger.info("[Agent Logic] Patching into UI skeleton: %s", _existing_vm)
            vm_text = _existing_vm.read_text(encoding="utf-8")

            # ── Post-read skeleton repair: fix known corruption patterns ────────
            # F009-type: LLM sometimes generates Arguments = "/F /IM x.exe")"
            _vm_before = vm_text
            # Step 1: "...exe")" → "...exe""
            vm_text = re.sub(r'(Arguments\s*=\s*"[^"]*")"\)', r'\1"', vm_text)
            # Step 2: "...exe"", → "...exe",
            vm_text = re.sub(r'(Arguments\s*=\s*"[^"]*")"\s*,', r'\1,', vm_text)
            if vm_text != _vm_before:
                logger.info("[Agent Logic] 🔧 Fixed corrupted Arguments string in skeleton")

            # Ensure CloseRequested event declaration is present
            if "event EventHandler" not in vm_text:
                _close_event = (
                    "\n    /// <summary>ウィンドウを閉じる要求イベント (DoCmd.Close相当)。</summary>\n"
                    "    public event EventHandler? CloseRequested;\n"
                )
                _cmd_m = re.search(r'([ \t]*// ─+ Commands)', vm_text)
                _icmd_m = re.search(r'([ \t]*public\s+ICommand\s+)', vm_text)
                _ins = _cmd_m or _icmd_m
                if _ins:
                    vm_text = vm_text[:_ins.start()] + _close_event + "\n" + vm_text[_ins.start():]
                    logger.info("[Agent Logic] ✅ Injected CloseRequested into skeleton")
            
            # Ensure using statements for services and DTOs are present
            required_usings = [
                "using System;",
                "using System.Linq;",
                "using System.Threading.Tasks;",
                "using System.Windows;",
                "using System.Windows.Input;",
                "using vba_brain.UI.WPF.Utils;",
                "using vba_brain.UI.WPF.Services;",
                "using vba_brain.Application.Interfaces;",
                f"using vba_brain.Application.DTOs.Requests.{form_name};",
                f"using vba_brain.Application.DTOs.Responses.{form_name};",
            ]
            for ru in required_usings:
                if ru not in vm_text:
                    vm_text = ru + "\n" + vm_text

            patched_count = 0

            for mo in method_outputs:
                code = mo.get("code", "").strip()
                if not code or len(code) < 5:
                    continue

                # Resolve F-ID: từ mapped_command.module_id hoặc event_id (EXxx → FXxx)
                mid = mo.get("mapped_command", {}).get("module_id", "")
                if not mid:
                    eid = mo.get("event_id", "")
                    mid = eid.replace("E", "F", 1) if eid.startswith("E") else ""
                fxxx_async = f"{mid}Async" if mid else ""
                if not fxxx_async:
                    logger.debug("[Agent Logic] Cannot resolve F-ID for event %s — skip", mo.get("event_id"))
                    continue

                # Extract body: nếu LLM trả về full method → lấy nội dung trong braces
                body = code
                if re.search(r'(public|private|protected|internal)\s+', body):
                    brace = body.find('{')
                    if brace != -1:
                        depth, chars, in_body = 0, [], False
                        for ch in body:
                            if ch == '{':
                                depth += 1
                                if depth == 1:
                                    in_body = True
                                    continue
                            elif ch == '}':
                                depth -= 1
                                if depth == 0:
                                    break
                            if in_body:
                                chars.append(ch)
                        extracted = "".join(chars).strip()
                        if extracted:
                            body = extracted

                # Indent body sang 8 spaces (method body level)
                indented = "\n".join(
                    f"        {ln}" if ln.strip() else ""
                    for ln in body.splitlines()
                )

                # Tìm và replace body của FxxxAsync() trong skeleton
                # Pattern khớp cả method không tham số F004Async() lẫn có tham số F001Async(KeyEventArgs? e)
                sig_pat = re.compile(
                    r'(public\s+virtual\s+async\s+System\.Threading\.Tasks\.Task\s+'
                    + re.escape(fxxx_async)
                    + r'\s*\([^)]*\)\s*)\{',
                )
                sig_m = sig_pat.search(vm_text)
                if sig_m:
                    start_brace = sig_m.end() - 1
                    depth, end_brace = 0, start_brace
                    for i in range(start_brace, len(vm_text)):
                        if vm_text[i] == '{': depth += 1
                        elif vm_text[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end_brace = i
                                break
                    replacement = f"{sig_m.group(1)}{{\n{indented}\n    }}"
                    vm_text = vm_text[:sig_m.start()] + replacement + vm_text[end_brace + 1:]
                    patched_count += 1
                    logger.info("[Agent Logic] ✅ Patched %s", fxxx_async)
                else:
                    logger.debug("[Agent Logic] No match for %s in skeleton", fxxx_async)

            logger.info("[Agent Logic] Patched %d/%d methods into %s", patched_count, len(method_outputs), vm_filename)

            # Ghi lại cả hai nơi: ui/outputs/ và Avalonia source
            from pipeline.avalonia_cs import to_avalonia_cs
            vm_text = to_avalonia_cs(vm_text)
            _ui_vm.parent.mkdir(parents=True, exist_ok=True)
            _ui_vm.write_text(vm_text, encoding="utf-8")
            if _src_vm.parent.exists():
                _src_vm.write_text(vm_text, encoding="utf-8")
                logger.info("[Agent Logic] Updated Avalonia source: %s", _src_vm.name)

            gen_file = GeneratedFile(
                path=f"ViewModels/{vm_filename}",
                content=vm_text,
                generator="LogicAgent-patch",
                agent="logic",
            )

            vm_filename = f"{vm_file_stem}.cs"
            vm_code = gen_file.content

            # ── Step 9: Save & Finalize ─────────────────────────────────
            # Create a comprehensive list of all method statuses for output and frontend
            all_method_outputs = []
            outputs_by_event = {m["event_id"]: m for m in method_outputs}
            for chunk in all_chunks:
                eid = chunk["bd_event"].get("event_id", "")
                mapped = chunk.get("mapped_command", {})
                vba_event = mapped.get("vba_event", "")
                cs_method = mapped.get("cs_method", "")
                event_class = chunk.get("event_class", "UI")
                
                if eid in outputs_by_event:
                    all_method_outputs.append(outputs_by_event[eid])
                else:
                    is_sys = chunk in sys_chunks
                    status = "success" if is_sys else "skipped"
                    note = "System bound command" if is_sys else "No logic required / Skipped"
                    code = "// Command bound in XAML" if is_sys else "// Skipped"
                    
                    all_method_outputs.append({
                        "event_id": eid,
                        "mapped_command": mapped,
                        "cs_method": cs_method,
                        "code": code,
                        "status": status,
                        "phase_type": event_class.lower(),
                        "note": note
                    })

            # Optional: Save locally for debug
            self._save_outputs(
                form_name, [gen_file], all_method_outputs,
                vm_file_stem=vm_file_stem,
                all_chunks=all_chunks,
            )

            # Write directly to WPF source if folder exists
            self._write_to_wpf_source(vm_filename, vm_code)

            logger.info(
                "[Agent Logic] ✅ Generated %s — %d methods (%d LLM + %d SYS)",
                vm_filename, len(method_outputs) + len(sys_chunks),
                len(method_outputs), len(sys_chunks),
            )

            # ── Auto Backup ──
            try:
                import sys
                layer5_dir = str(Path(__file__).resolve().parent.parent.parent)
                if layer5_dir not in sys.path:
                    sys.path.insert(0, layer5_dir)
                from pipeline import backup_layer5
                backup_layer5.backup_agent(self.name)
            except Exception as exc:
                logger.error("Auto-backup failed: %s", exc)

            return AgentOutput(
                agent=self.name,
                form_name=form_name,
                files=[gen_file],
                status="success",
                metadata={
                    "viewmodel":     f"{vm_file_stem}",
                    "total_events":  len(bd_events),
                    "valid_events":  len(valid_chunks),
                    "sys_events":    len(sys_chunks),
                    "llm_calls":     len(method_outputs),
                    "output_snapshot": f"inputs/{form_name}_output.json",
                    "service_name":  service_name,
                },
            )

        except Exception as e:
            logger.error("[Agent Logic] ❌ Failed for %s: %s", form_name, e, exc_info=True)
            return AgentOutput(
                agent="logic",
                form_name=form_name,
                status="error",
                error=str(e),
            )

    # ──────────────────────────────────────────
    # Data Loaders
    # ──────────────────────────────────────────

    def _load_bd_json(self, form_name: str) -> dict:
        """Load BD JSON from MongoDB (bds collection)."""
        db = get_db()
        doc = db["bds"].find_one({"name": form_name}, {"_id": 0})
        if doc:
            logger.info("[Agent Logic] Loaded BD for %s from MongoDB (bds)", form_name)
            return doc
        
        # Fallback to local file if not in DB
        bd_dir = Path(__file__).parent.parent.parent.parent / "layer4" / "inputs" / "BD_json" / "screen"
        f = bd_dir / f"{form_name}.json"
        if f.exists():
            logger.info("[Agent Logic] Loaded BD for %s from local file", form_name)
            return json.loads(f.read_text(encoding="utf-8"))
            
        raise FileNotFoundError(f"BD JSON not found for {form_name} in MongoDB or local disk.")

    def _load_dd_json(self, form_name: str) -> dict:
        """Load DD JSON from MongoDB (dds collection)."""
        db = get_db()
        doc = db["dds"].find_one({"name": form_name}, {"_id": 0})
        if doc:
            logger.info("[Agent Logic] Loaded DD for %s from MongoDB (dds)", form_name)
            return doc

        # Fallback to local file if not in DB
        dd_dir = Path(__file__).parent.parent.parent.parent / "layer4" / "inputs" / "DD_json" / "form"
        f = dd_dir / f"{form_name}.json"
        if f.exists():
            logger.info("[Agent Logic] Loaded DD for %s from local file", form_name)
            return json.loads(f.read_text(encoding="utf-8"))

        raise FileNotFoundError(f"DD JSON not found for {form_name} in MongoDB or local disk.")

    def _load_service_interface(self, upstream_files: list[GeneratedFile], form_name: str) -> str:
        """
        Extract service context từ upstream files hoặc service_contract.json.

        Priority:
          1. service_contract.json (Agent Service output) — structured, no parse needed
          2. Upstream files (I{Feature}Service.cs + DTOs)
          3. Local disk fallback

        Chỉ lấy các file CẦN THIẾT cho LLM:
          - I{Feature}Service.cs  (interface — method signatures)
          - {Feature}ServiceRequests.cs  (Request DTOs)
          - {Feature}ServiceResponses.cs (Response DTOs)
        """
        # ── Priority 1: service_contract.json ────────────────────────────
        try:
            from agents.ui.tool_skeleton import load_service_contract
            contract = load_service_contract(form_name)
            if contract and contract.get("methods"):
                # Format contract as compact C#-style context for LLM
                iface  = contract.get("iface_class", "")
                field  = contract.get("service_field", "")
                lines  = [
                    f"// Service contract for {form_name}",
                    f"// DI field: {field} ({iface})",
                    f"// namespace: {contract.get('namespace', 'vba_brain.Application.Services')}",
                    "",
                    f"public interface {iface}",
                    "{",
                ]
                for mid, m in contract.get("methods", {}).items():
                    req_props = m.get("request_props", [])
                    props_str = "; ".join(f"{p['type']} {p['name']}" for p in req_props)
                    lines.append(f"    // [{mid}] {m.get('event_trigger', '')} — {m.get('event_content', '')[:80]}")
                    lines.append(f"    {m['return_type']} {m['method_name']}({m['request_class']} request);")
                    if req_props:
                        lines.append(f"    // Request props: {props_str}")
                lines.append("}")

                # Append compact Request DTOs
                lines.append("")
                lines.append("// Request DTOs")
                for mid, m in contract.get("methods", {}).items():
                    req_props = m.get("request_props", [])
                    lines.append(f"public class {m['request_class']} {{")
                    for p in req_props:
                        lines.append(f"    public {p['type']} {p['name']} {{ get; set; }} = default!;")
                    lines.append("}")

                ctx = "\n".join(lines)
                logger.info(
                    "[Agent Logic] service_context: loaded from service_contract.json (%d methods) for %s",
                    len(contract["methods"]), form_name,
                )
                return ctx
        except Exception as _ce:
            logger.debug("[Agent Logic] service_contract.json load failed: %s", _ce)

        # ── Priority 2+3: upstream files / disk ──────────────────────────
        from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
        try:
            _name_map = _load_form_name_map()
            _, vm_file_stem = _resolve_wpf_names(form_name, _name_map)
            feature = vm_file_stem.replace("ViewModel", "") if vm_file_stem.endswith("ViewModel") else vm_file_stem
        except Exception:
            feature = re.sub(r"[^\w]", "", form_name.replace("F_", "")) or "Default"

        # File types to include (interface + DTOs only, NOT implementation)
        def _is_relevant(filename: str) -> bool:
            n = filename.lower()
            if n.endswith("servicerequests.cs") or n.endswith("serviceresponses.cs"):
                return True
            if n.startswith("i") and n.endswith("service.cs"):
                return True
            return False

        def _priority(filename: str) -> int:
            n = filename.lower()
            feat_lower = feature.lower()
            if n.startswith(feat_lower):
                return 0
            return 1

        seen_roles: dict[str, str] = {}

        def _role_key(filename: str) -> str:
            n = filename.lower()
            if n.endswith("servicerequests.cs"):
                return "requests"
            if n.endswith("serviceresponses.cs"):
                return "responses"
            if n.startswith("i") and n.endswith("service.cs"):
                return "interface"
            return filename

        candidates: list[tuple[int, str, str]] = []

        for uf in upstream_files:
            fname = Path(uf.path).name
            if uf.path.endswith(".cs") and _is_relevant(fname):
                candidates.append((_priority(fname), fname, uf.content))

        if not candidates:
            app_dir = AGENT_DIR.parent / "service" / "outputs" / form_name / "Application"
            if app_dir.exists():
                for cs_file in sorted(app_dir.glob("**/*.cs")):
                    if _is_relevant(cs_file.name):
                        try:
                            content = cs_file.read_text(encoding="utf-8")
                            candidates.append((_priority(cs_file.name), cs_file.name, content))
                        except Exception as e:
                            logger.warning("[Agent Logic] Failed to load %s: %s", cs_file.name, e)

        for prio, fname, content in sorted(candidates, key=lambda x: x[0]):
            role = _role_key(fname)
            if role not in seen_roles:
                seen_roles[role] = f"// File: {fname}\n{content}\n"
                logger.debug("[Agent Logic] service_context: using %s for role '%s'", fname, role)

        if seen_roles:
            ordered = []
            for role in ("interface", "requests", "responses"):
                if role in seen_roles:
                    ordered.append(seen_roles[role])
            for role, content in seen_roles.items():
                if role not in ("interface", "requests", "responses"):
                    ordered.append(content)
            logger.info(
                "[Agent Logic] service_context: %d files (roles: %s) for %s",
                len(ordered), list(seen_roles.keys()), form_name,
            )
            return "\n".join(ordered)

        return ""

    def _load_xaml_bindings(
        self,
        form_name: str,
        upstream_files: list[GeneratedFile],
    ) -> dict:
        """
        Load ViewModel bindings from upstream Agent UI output.
        Priority:
          1. Upstream files (passed via pipeline)
          2. UI agent outputs/ folder (file on disk)
          3. Empty fallback
        """
        # Check upstream files for bindings JSON
        for uf in upstream_files:
            if "bindings" in uf.path.lower() and uf.path.endswith(".json"):
                try:
                    return json.loads(uf.content)
                except json.JSONDecodeError:
                    pass

        # Check UI agent outputs
        ui_outputs = AGENT_DIR.parent / "ui" / "outputs"
        bindings_file = ui_outputs / f"{form_name}_preview.json"
        if bindings_file.exists():
            try:
                preview = json.loads(bindings_file.read_text(encoding="utf-8"))
                # Extract bindings from preview JSON
                bindings = preview.get("bindings", {})
                if bindings:
                    return {
                        "properties": bindings.get("properties", []),
                        "commands":   bindings.get("commands", []),
                    }
                
                # Fallback: Extract from controls list
                props = set()
                cmds = set()
                
                def _walk(ctrls):
                    for c in ctrls:
                        if "binding" in c:
                            props.add(c["binding"])
                        if "command" in c:
                            cmds.add(c["command"])
                        if c.get("type") == "PasswordBox" or c.get("password_event"):
                            props.add("Password")
                        if "controls" in c:
                            _walk(c["controls"])
                
                _walk(preview.get("controls", []))
                return {
                    "properties": sorted(list(props)),
                    "commands":   sorted(list(cmds)),
                }
            except (json.JSONDecodeError, AttributeError, Exception):
                pass

        # Check inputs/ folder
        vm_file = INPUTS_DIR / f"{form_name}_viewmodel_bindings.json"
        if vm_file.exists():
            return json.loads(vm_file.read_text(encoding="utf-8"))

        return {"properties": [], "commands": []}

    def _detect_service_name(self, service_interface: str) -> str:
        """
        Detect service name from interface code.
        e.g. "public interface IAuthService" → "Auth"
        """
        if not service_interface:
            return ""
        match = re.search(r'interface\s+I(\w+)Service', service_interface)
        return match.group(1) if match else ""

    # ──────────────────────────────────────────
    # LLM Call per Chunk
    # ──────────────────────────────────────────

    def _call_llm_per_chunk(
        self,
        llm: L5LLMClient,
        system_prompt: str,
        chunk: dict,
        model_override: Any = None,
    ) -> dict:
        """
        Build prompt for a single event chunk and call LLM.
        Returns dict with method code and metadata.
        """
        bd_event = chunk["bd_event"]
        dd_steps = chunk["dd_steps"]
        mapped   = chunk["mapped_command"]
        idx      = chunk["chunk_idx"]
        total    = chunk["total_chunks"]

        event_id  = bd_event.get("event_id", f"E{idx:03d}")
        vba_event = mapped.get("vba_event", "")
        cs_method = mapped.get("cs_method", "")
        cs_command = mapped.get("cs_command", "")

        logger.info(
            "[Agent Logic] Chunk %d/%d — %s %s → %s (%s) ⭐",
            idx + 1, total, event_id, vba_event,
            cs_command or cs_method,
            mapped.get("action_type", "VALID"),
        )

        # Build user prompt
        user_prompt = self._build_chunk_prompt(chunk)

        # Call LLM
        raw_response = llm.generate_code(
            task_type="viewmodel",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model_override,
            agent="logic",
            form_name=chunk.get("form_name", ""),
        )

        # Extract C# code block
        code = extract_code_block(raw_response, "csharp")

        if not code or len(code.strip()) < 10:
            logger.warning(
                "[Agent Logic] ⚠️ Chunk %s returned empty/minimal code",
                event_id,
            )

        return {
            "event_id":       event_id,
            "mapped_command": mapped,
            "cs_method":      cs_method,
            "code":           code,
            "status":         "success",
            "phase_type":     chunk.get("event_class", "UI").lower(),
        }

    def _run_chunks_graph(
        self,
        chunks: list[dict],
        llm: L5LLMClient,
        system_prompt: str,
        form_name: str,
        model_override: Any = None,
    ) -> list[dict]:
        """
        Process event chunks via LangGraph StateGraph — map-reduce pattern.

        Graph:
          split_node → process_chunk_node (loop) → merge_node → END

        Mirrors agents/ui/agent_ui.py _run_chunked() pattern.
        """

        if not chunks:
            logger.info("[Agent Logic][LangGraph] No chunks to process. Skipping graph run.")
            return []

        def split_node(state: LogicChunkState) -> dict:
            logger.info(
                "[Agent Logic][LangGraph] %s — %d chunk(s) to process",
                state["form_name"], len(state["chunks"]),
            )
            return {
                "total_chunks": len(state["chunks"]),
                "current_idx":  0,
                "method_outputs": [],
            }

        def process_chunk_node(state: LogicChunkState) -> dict:
            idx   = state["current_idx"]
            chunk = state["chunks"][idx]
            event_id = chunk["bd_event"].get("event_id", f"E{idx:03d}")

            logger.info(
                "[Agent Logic][LangGraph] Chunk %d/%d — %s",
                idx + 1, state["total_chunks"], event_id,
            )

            try:
                result = self._call_llm_per_chunk(
                    llm=state["llm"],
                    system_prompt=state["system_prompt"],
                    chunk=chunk,
                    model_override=state["model_override"],
                )
                logger.info(
                    "[Agent Logic][LangGraph] ✅ Chunk %d/%d done — %s",
                    idx + 1, state["total_chunks"], event_id,
                )
                return {
                    "method_outputs": [result],
                    "current_idx":    idx + 1,
                }
            except Exception as exc:
                logger.error(
                    "[Agent Logic][LangGraph] ❌ Chunk %d/%d failed (%s): %s",
                    idx + 1, state["total_chunks"], event_id, exc,
                )
                return {
                    "method_outputs": [{
                        "event_id":       event_id,
                        "mapped_command": chunk.get("mapped_command", {}),
                        "cs_method":      chunk.get("mapped_command", {}).get("cs_method", ""),
                        "code":           f"// Error: {exc}",
                        "status":         "error",
                        "phase_type":     chunk.get("event_class", "UI").lower(),
                    }],
                    "current_idx": idx + 1,
                }

        def merge_node(state: LogicChunkState) -> dict:
            outputs = state["method_outputs"]
            done   = sum(1 for m in outputs if m.get("status") != "error")
            errors = len(outputs) - done
            logger.info(
                "[Agent Logic][LangGraph] Merge done — %d/%d OK, %d error(s)",
                done, len(outputs), errors,
            )
            return {}  # method_outputs already accumulated via operator.add

        def should_continue(state: LogicChunkState) -> str:
            if state["current_idx"] < state["total_chunks"]:
                return "process_chunk_node"
            return "merge_node"

        # ── Build Graph ──────────────────────────────────────────────────────
        builder = StateGraph(LogicChunkState)
        builder.add_node("split_node",         split_node)
        builder.add_node("process_chunk_node", process_chunk_node)
        builder.add_node("merge_node",         merge_node)

        builder.add_edge(START, "split_node")
        builder.add_edge("split_node", "process_chunk_node")
        builder.add_conditional_edges("process_chunk_node", should_continue)
        builder.add_edge("merge_node", END)

        graph = builder.compile()

        # ── Initial State ────────────────────────────────────────────────────
        initial_state: LogicChunkState = {
            "form_name":      form_name,
            "system_prompt":  system_prompt,
            "llm":            llm,
            "model_override": model_override,
            "chunks":         chunks,
            "total_chunks":   len(chunks),
            "current_idx":    0,
            "method_outputs": [],
        }

        logger.info(
            "[Agent Logic][LangGraph] Invoking graph for %s — %d chunks",
            form_name, len(chunks),
        )
        final_state = graph.invoke(initial_state)
        return final_state.get("method_outputs", [])

    def _build_chunk_prompt(self, chunk: dict) -> str:
        """Build user prompt for a single event chunk."""
        bd_event     = chunk["bd_event"]
        dd_steps     = chunk["dd_steps"]
        mapped       = chunk["mapped_command"]
        idx          = chunk["chunk_idx"]
        total        = chunk["total_chunks"]
        svc_ctx      = chunk.get("service_context", "")
        props        = chunk.get("property_list", [])
        commands     = chunk.get("command_list", [])
        cs_stub      = chunk.get("cs_stub")          # C# stub from xaml.cs
        event_class  = chunk.get("event_class", "")  # UI or SERVICE

        event_id   = bd_event.get("event_id", "")
        vba_event  = mapped.get("vba_event", "")
        cs_command = mapped.get("cs_command", "")
        cs_method  = mapped.get("cs_method", "")
        notes      = bd_event.get("notes", "")

        prompt = f"## Generate method for event: {vba_event}\n"
        prompt += f"[CHUNK {idx + 1}/{total}] | event_class: {event_class}\n\n"

        # ── JP comment reminder (busts LLM cache + enforces language rule) ─
        prompt += (
            f"> ⚠️ **必須ルール**: コメントはすべて{TARGET_LANGUAGE}で書くこと。英語コメント禁止。\n"
            "> TODOは最大1個のみ。仕様に書いてある処理にTODOを付けない。コメント行数は最大5行。\n\n"
        )

        # ── event_class instruction ──────────────────────────────────────
        module_id_for_event = bd_event.get("module_id", "")
        fxxx_async = f"{module_id_for_event}Async" if module_id_for_event else "FxxxAsync"

        if event_class == "SERVICE":
            # SERVICE → gen ViewModel async method body (NOT code-behind)
            # Chỉ gen: build request + call service + handle response
            # KHÔNG gen business logic VBA, KHÔNG dùng hàm không tồn tại

            # Lấy request_props từ service_context để chỉ đích danh tên property
            _svc_req_props: list[str] = []
            if isinstance(svc_ctx, dict):
                _req_obj = svc_ctx.get("request", {})
                _svc_req_props = [p["name"] for p in _req_obj.get("properties", [])]
            _vm_props_hint = _svc_req_props or list(props) or ["TxtID", "TxtPass"]

            prompt += (
                f"> **SERVICE — ViewModel Method**: Generate the body of `public virtual async Task {fxxx_async}()`.\n"
                f"> Rules:\n"
                f"> 1. Call the service: `await _fLoginService.{fxxx_async}(request)`\n"
                f"> 2. Build `request` using EXACT ViewModel property names: `{', '.join(_vm_props_hint)}`\n"
                f"> 3. Perform input validation before calling the service based on the VBA logic (e.g., check if properties are empty/null and use MessageBox.Show to notify the user).\n"
                f"> 4. Initialize fields if necessary (e.g., set `TxtID = System.Environment.UserName;` during Form Open/F000Async if the VBA code initialized txtID to the username).\n"
                f"> 5. Handle `response.Success == false` by displaying the error message: `MessageBox.Show(response.Message ?? \"Error description\")`.\n"
                f"> 6. Implement success actions from the VBA logic (e.g., show success message, close window, or set properties).\n"
                f"> 7. Output: ONLY code INSIDE the method braces — no method signature or surrounding braces.\n"
                f"> 8. NO direct VBA functions (SwitchShiftKey, DoCmd, etc.) — map them to C# equivalents or TODOs if they are form close/navigation.\n\n"
            )
            prompt += f"### ViewModel method to implement (output body only):\n"
            prompt += f"```csharp\npublic virtual async System.Threading.Tasks.Task {fxxx_async}()\n{{\n    // Build request and call service here\n}}\n```\n\n"
        else:
            # UI → gen code-behind handler
            prompt += (
                "> **UI**: Generate code-behind method with UI logic only.\n"
                "> No service/repository calls. Use MessageBox.Show, Application.Shutdown, e.Handled, etc.\n\n"
            )
            if cs_stub:
                signature = cs_stub.get("signature", "")
                cs_name   = cs_stub.get("cs_name", "")
                mid       = cs_stub.get("module_id", "")
                vba_hdlr  = cs_stub.get("vba_handler", notes)
                prompt += f"### C# code-behind method to implement:\n"
                prompt += f"```csharp\n{signature}\n{{\n    // TODO: implement\n}}\n```\n"
                prompt += f"**F-ID:** `{mid}` | **VBA:** `{vba_hdlr}`\n\n"
            else:
                prompt += f"### Method: `{notes or cs_method or cs_command}`\n\n"

        # ── VBA Source code — chỉ show với UI events, không show với SERVICE ──
        # VBA code phức tạp của SERVICE events confuse LLM → gen VBA logic thay vì service call
        vba_code = bd_event.get("code", "") or bd_event.get("logic_code", "")
        if vba_code and "not found" not in vba_code.lower():
            prompt += f"### Original VBA code (reference only):\n```vba\n{vba_code}\n```\n\n"

        # ── Event summary (chỉ fields cần thiết, không dump toàn bộ bd_event) ──
        event_summary = {
            k: bd_event[k] for k in (
                "event_id", "event_trigger", "event_content",
                "logical_name", "physical_name", "notes",
            ) if bd_event.get(k)
        }
        prompt += f"### Event info:\n```json\n{json.dumps(event_summary, ensure_ascii=False, indent=2)}\n```\n\n"

        # ── DD Steps ─────────────────────────────────────────────────────
        if dd_steps:
            prompt += f"### DD Steps (business logic):\n```json\n{json.dumps(dd_steps, ensure_ascii=False, indent=2)}\n```\n\n"
        else:
            prompt += "### DD Steps: (none — generate minimal stub)\n\n"

        # ── Service context (SERVICE only) ─────────────────────────────
        if svc_ctx and event_class == "SERVICE":
            if isinstance(svc_ctx, dict):
                # Structured service_context — compact format
                iface_sig  = svc_ctx.get("interface_method", "")
                req_obj    = svc_ctx.get("request", {})
                res_obj    = svc_ctx.get("response", {})
                svc_field  = svc_ctx.get("service_field_hint", "")
                vm_method  = svc_ctx.get("vm_method", "")
                req_props  = req_obj.get("properties", [])
                res_props  = res_obj.get("properties", [])

                if iface_sig:
                    prompt += f"### Service method: `{iface_sig}`\n\n"
                if svc_field:
                    prompt += f"**Service field:** `{svc_field}` | **VM method:** `{vm_method}`\n\n"
                if req_props:
                    prompt += f"### `{req_obj.get('class', 'Request')}` properties:\n"
                    for p in req_props:
                        prompt += f"- `{p['name']}`: {p['type']}{'?' if p.get('nullable') else ''}\n"
                    prompt += "\n"
                if res_props:
                    prompt += f"### `{res_obj.get('class', 'Response')}` properties:\n"
                    for p in res_props:
                        prompt += f"- `{p['name']}`: {p['type']}{'?' if p.get('nullable') else ''}\n"
                    prompt += "\n"

                    # ── Entity shape hints ─────────────────────────────────
                    for p in res_props:
                        shape = p.get("entity_shape")
                        if not shape:
                            continue
                        cls  = shape["class"]
                        flds = shape["fields"]
                        prompt += f"#### `{cls}` fields (EXACT — do NOT invent):\n"
                        for f in flds:
                            col = f" // {f['column']}" if f.get("column") else ""
                            prompt += f"- `{f['name']}`: `{f['type']}`{col}\n"
                        if any(f["name"] == "AdminFlag" for f in flds):
                            prompt += f"> 管理者判定: `{cls}.AdminFlag != \"0\"` — `IsAdmin`プロパティは存在しない\n"
                        prompt += "\n"

                # ── Pattern-specific hints from DD steps ───────────────────────────
                dd_text_flat = json.dumps(dd_steps, ensure_ascii=False) if dd_steps else ""

                # Version check pattern (F002-type)
                if any(kw in dd_text_flat for kw in ("バージョン", "最新版", "インストール", "コメント")):
                    res_class = res_obj.get("class", "Response") if isinstance(svc_ctx, dict) else "Response"
                    prompt += (
                        "### ⚠️ 実装ガイド: バージョンチェックパターン\n"
                        f"> `{res_class}.Message` にはServiceがDBから取得した最新バージョン文字列が入る。\n"
                        "> ViewModelはそのMessageを使って比較し、異なる場合はインストールメッセージを表示する。\n"
                        "> `response.Success == true` でも `response.Message` のチェックは必須。\n"
                        "> **実装例:**\n"
                        "> ```csharp\n"
                        "> var response = await _fLoginService.F002Async(request);\n"
                        "> if (response.Success && !string.IsNullOrEmpty(response.Message))\n"
                        "> {\n"
                        ">     // TODO: ラベル400から現在バージョンを取得して比較\n"
                        ">     var latestVer = response.Message;\n"
                        ">     // 現在バージョンとlatestVerが異なる場合\n"
                        '>     MessageBox.Show("最新版ではありません！\\nインストールします。",\n'
                        '>         "確認", MessageBoxButton.OK, MessageBoxImage.Exclamation);\n'
                        "> }\n"
                        "> ```\n\n"
                    )
            else:
                # Legacy string blob — pass as-is
                prompt += f"### Service interface:\n```csharp\n{svc_ctx}\n```\n\n"

        # ── ViewModel bindings (SERVICE only — UI không cần) ──
        if event_class == "SERVICE":
            if props:
                prompt += f"### ViewModel Properties:\n{', '.join(props)}\n\n"
            if commands:
                prompt += f"### ViewModel Commands:\n{', '.join(commands)}\n\n"

        prompt += "Generate the complete C# method with signature."
        return prompt

    # ──────────────────────────────────────────
    # Save & Output
    # ──────────────────────────────────────────

    def _save_input_snapshot(
        self,
        form_name: str,
        chunks: list[dict],
        mapped_events: list[dict],
        xaml_bindings: dict | None,
    ) -> None:
        """Save input snapshot for debug & replay."""
        INPUTS_DIR.mkdir(parents=True, exist_ok=True)

        # Save chunks
        self._chunk_builder.save_chunks(form_name, chunks)

        # Save mapped events summary
        summary = {
            "form_name":     form_name,
            "total_events":  len(mapped_events),
            "mapped_events": mapped_events,
            "xaml_bindings": xaml_bindings,
        }
        summary_file = INPUTS_DIR / f"{form_name}_mapping_summary.json"
        summary_file.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[Agent Logic] Input snapshot saved to inputs/")

    def _gen_sys_bodies(self, all_chunks: list[dict]) -> list[dict]:
        """
        Deterministically generate method bodies for SYS/UI events that have known WPF equivalents.
        These events are skipped by LLM but still need real implementation code.

        Patterns handled:
          - DoCmd.Quit        → confirm dialog → Application.Current.Shutdown()
          - taskkill/Shell    → Process.Start(taskkill)
          - Form_KeyDown      → stub only (key blocking stays in code-behind)
          - Others            → no body generated (keep skeleton stub)

        Returns list of {event_id, module_id, code} — same format as LLM method_outputs.
        """
        # Load service contract to skip events already handled by LLM (SERVICE events)
        from agents.ui.tool_skeleton import load_service_contract
        try:
            svc_contract = load_service_contract(
                next((c.get("form_name") or c.get("bd_event", {}).get("form_name", "")
                      for c in all_chunks if c.get("form_name") or c.get("bd_event", {}).get("form_name")), "")
            )
        except Exception:
            svc_contract = {}
        service_module_ids: set[str] = set(svc_contract.get("methods", {}).keys())

        results: list[dict] = []
        for chunk in all_chunks:
            bd     = chunk.get("bd_event", {})
            mapped = chunk.get("mapped_command", {})
            if mapped.get("is_main_logic"):
                continue  # handled by LLM
            if mapped.get("macro_ref"):
                continue  # skeleton already has ExecuteAsync

            action_type = mapped.get("action_type", "")
            if action_type not in ("SYS", "UI"):
                continue

            event_id  = bd.get("event_id", "")
            module_id = bd.get("module_id", "")
            fxxx_async = f"{module_id}Async" if module_id else ""
            if not fxxx_async:
                continue

            # Skip events already in service contract — LLM / gen_vm_methods handles them
            if module_id in service_module_ids:
                logger.debug("[Agent Logic] SYS skip %s — in service contract (LLM handled)", fxxx_async)
                continue

            # VBA code: try multiple sources
            # 1. chunk["logic_detail"]["code"] — populated by _build_formatted_events
            logic_detail = chunk.get("logic_detail") or {}
            vba_code = logic_detail.get("code", "")
            # 2. chunk["bd_event"]["vba_code"]
            if not vba_code:
                vba_code = bd.get("vba_code", "")
            # 3. Extract from MongoDB using notes (VBA handler name)
            if not vba_code or vba_code.startswith("//"):
                notes = bd.get("notes", "")
                if notes and not notes.startswith("参照マクロ"):
                    vba_code = self._chunk_builder._extract_vba_code(
                        bd.get("form_name", chunk.get("form_name", "")), notes
                    ) or vba_code

            body: str | None = None

            # ── Quit / Close application ─────────────────────────────────
            if re.search(r'DoCmd\.Quit|acQuitPrompt', vba_code, re.IGNORECASE):
                body = (
                    "public virtual async System.Threading.Tasks.Task " + fxxx_async + "()\n"
                    "{\n"
                    "    var result = MessageBox.Show(\n"
                    '        "アプリケーションを終了しますか？",\n'
                    '        "確認", MessageBoxButton.YesNo, MessageBoxImage.Question);\n'
                    "    if (result == MessageBoxResult.Yes)\n"
                    "        System.Windows.Application.Current.Shutdown();\n"
                    "    await System.Threading.Tasks.Task.CompletedTask;\n"
                    "}"
                )

            # ── Process kill (taskkill.exe) ──────────────────────────────
            elif re.search(r'taskkill', vba_code, re.IGNORECASE):
                im_match = re.search(r'/IM\s+(\S+)', vba_code, re.IGNORECASE)
                im_arg = im_match.group(1).strip('"\'') if im_match else "wmplayer.exe"
                body = (
                    "public virtual async System.Threading.Tasks.Task " + fxxx_async + "()\n"
                    "{\n"
                    "    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo\n"
                    "    {\n"
                    f'        FileName = "taskkill.exe",\n'
                    f'        Arguments = "/F /IM {im_arg}",\n'
                    "        CreateNoWindow = true,\n"
                    "        UseShellExecute = false\n"
                    "    });\n"
                    "    await System.Threading.Tasks.Task.CompletedTask;\n"
                    "}"
                )

            # ── KeyDown F11/F12 — logic in ViewModel, code-behind only sets e.Handled ──
            elif re.search(r'Form_KeyDown|vbKeyF11|vbKeyF12', vba_code, re.IGNORECASE):
                body = (
                    "public virtual async System.Threading.Tasks.Task " + fxxx_async + "(System.Windows.Input.KeyEventArgs? e = null)\n"
                    "{\n"
                    "    if (e == null) { await System.Threading.Tasks.Task.CompletedTask; return; }\n"
                    "    switch (e.Key)\n"
                    "    {\n"
                    "        case System.Windows.Input.Key.F11:\n"
                    "            e.Handled = true;\n"
                    '            MessageBox.Show("ファンクション【F11】キーは無効に設定されてます！！",\n'
                    '                "警告", MessageBoxButton.OK, MessageBoxImage.Warning);\n'
                    "            break;\n"
                    "        case System.Windows.Input.Key.F12:\n"
                    "            e.Handled = true;\n"
                    '            MessageBox.Show("ファンクション【F12】キーは無効に設定されてます！！",\n'
                    '                "警告", MessageBoxButton.OK, MessageBoxImage.Warning);\n'
                    "            break;\n"
                    "    }\n"
                    "    await System.Threading.Tasks.Task.CompletedTask;\n"
                    "}"
                )

            # ── Fallback: use event_content / notes to determine pattern ──
            else:
                event_content = bd.get("event_content", "")
                notes = bd.get("notes", "")
                # Quit pattern from event_content
                if re.search(r'終了|Quit|アプリケーション.*終了', event_content, re.IGNORECASE):
                    body = (
                        "public virtual async System.Threading.Tasks.Task " + fxxx_async + "()\n"
                        "{\n"
                        "    var result = MessageBox.Show(\n"
                        '        "アプリケーションを終了しますか？",\n'
                        '        "確認", MessageBoxButton.YesNo, MessageBoxImage.Question);\n'
                        "    if (result == MessageBoxResult.Yes)\n"
                        "        System.Windows.Application.Current.Shutdown();\n"
                        "    await System.Threading.Tasks.Task.CompletedTask;\n"
                        "}"
                    )
                # taskkill pattern from event_content
                elif re.search(r'強制終了|taskkill|wmplayer|Media Player', event_content, re.IGNORECASE):
                    body = (
                        "public virtual async System.Threading.Tasks.Task " + fxxx_async + "()\n"
                        "{\n"
                        "    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo\n"
                        "    {\n"
                        '        FileName = "taskkill.exe",\n'
                        '        Arguments = "/F /IM wmplayer.exe",\n'
                        "        CreateNoWindow = true,\n"
                        "        UseShellExecute = false\n"
                        "    });\n"
                        "    await System.Threading.Tasks.Task.CompletedTask;\n"
                        "}"
                    )
                # DblClick → open form pattern (DD steps contain "フォームを開く" or "詳細を表示")
                elif re.search(r'DblClick|ondblclick|ダブルクリック', notes + event_content, re.IGNORECASE):
                    # Extract logical name for TODO comment
                    logical_name = bd.get("logical_name", "") or bd.get("title", "")
                    comment = f"open {logical_name} form" if logical_name and logical_name not in ("-", "") else "open related form"
                    body = (
                        "public virtual async System.Threading.Tasks.Task " + fxxx_async + "()\n"
                        "{\n"
                        f"    // TODO: {comment} — verify View class name before instantiating\n"
                        "    await System.Threading.Tasks.Task.CompletedTask;\n"
                        "}"
                    )

            if body:
                results.append({
                    "event_id":       event_id,
                    "module_id":      module_id,
                    "mapped_command": mapped,
                    "cs_method":      fxxx_async,
                    "code":           body,
                    "status":         "success",
                    "phase_type":     "sys_deterministic",
                })
                logger.info("[Agent Logic] ✅ SYS deterministic body: %s (%s)", fxxx_async, event_id)
            else:
                logger.debug("[Agent Logic] SYS no pattern match: %s vba=%r content=%r",
                             fxxx_async, vba_code[:60], bd.get("event_content","")[:60])

        return results

    def _save_outputs(
        self,
        form_name: str,
        files: list[GeneratedFile],
        method_outputs: list[dict],
        *,
        vm_file_stem: str = "",
        all_chunks: list[dict] | None = None,
    ) -> None:
        """Save outputs to agent outputs/ folder AND MongoDB agent_logic collection.

        Output contract ({form_name}.json) — review-friendly, mirroring C# ViewModel structure:
        {
          "form_name":        "F_Login",
          "feature":          "FLogin",
          "viewmodel_name":   "FLoginViewModel",
          "view_name":        "FLoginView",
          "viewmodel_file":   "FLoginViewModel.cs",
          "codebehind_file":  "FLoginView.xaml.cs",
          "agent":            "logic",
          "summary": {
            "total_events": 10,
            "generated": 3,
            "skipped": 5,
            "sys_deterministic": 2
          },
          "methods": {
            "F000": {
              "order": 0,
              "event_id":        "E000",
              "module_id":       "F000",
              "event_trigger":   "画面を開く時",
              "event_content":   "...",
              "vba_handler":     "Form_Open",
              "phase_type":      "service",          ← service | ui | sys_deterministic
              "status":          "success",           ← success | skipped
              "cs_stub": {                            ← codebehind handler
                "signature":    "private async void F000_Loaded(...)",
                "cs_name":      "F000_Loaded",
              },
              "vm_method": {                          ← ViewModel method (generated)
                "name":         "F000Async",
                "signature":    "public virtual async Task F000Async()",
                "body":         "// full C# method body",
              },
              "service_call": {                       ← null nếu không gọi service
                "method":       "F000Async",
                "request":      "F000Request",
                "response":     "F000Response",
                "request_props": [{"name":"TxtID","type":"string"}]
              },
              "references": {                         ← queries/macros used (no VBA/DD detail)
                "queries":  [...],
                "macros":   [...]
              },
              "note": ""
            }
          }
        }
        """
        out_dir = OUTPUTS_DIR / form_name
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── 1. Save CS files ────────────────────────────────────────────────
        for gf in files:
            target = out_dir / gf.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(gf.content, encoding="utf-8")
            logger.info("[Agent Logic] Saved: %s", target.relative_to(OUTPUTS_DIR))
            flat_name = Path(gf.path).name
            flat_target = out_dir / flat_name
            if flat_target != target:
                flat_target.write_text(gf.content, encoding="utf-8")

        # ── 2. Resolve WPF screen names from listFormJpToEn.json ───────────
        _jp_to_en_path = (
            AGENT_DIR.parent / "graphview" / "outputs" / "forms" / "listFormJpToEn.json"
        )
        _entry: dict = {}
        if _jp_to_en_path.exists():
            try:
                _data = json.loads(_jp_to_en_path.read_text(encoding="utf-8"))
                for item in _data.get("items", []):
                    if item.get("access_form_name") == form_name:
                        _entry = item
                        break
            except Exception as _e:
                logger.warning("[Agent Logic] listFormJpToEn.json load failed: %s", _e)

        _viewmodel_name = _entry.get("wpf_viewmodel_name") or vm_file_stem or ""
        _view_name      = _entry.get("wpf_view_name") or (
            _viewmodel_name.replace("ViewModel", "View") if _viewmodel_name else ""
        )
        _feature = (
            _viewmodel_name.replace("ViewModel", "")
            if _viewmodel_name.endswith("ViewModel")
            else (_viewmodel_name or form_name)
        )
        _vm_file        = f"{_viewmodel_name}.cs"    if _viewmodel_name else ""
        _codebehind_file = f"{_view_name}.xaml.cs"  if _view_name else ""

        # ── 3. Build chunk lookup (event_id → chunk) for context enrichment ─
        chunk_by_event: dict[str, dict] = {}
        if all_chunks:
            for _c in all_chunks:
                _eid = _c.get("bd_event", {}).get("event_id", "")
                if _eid:
                    chunk_by_event[_eid] = _c

        # ── 4. Build methods map — keyed by module_id (F000, F001 …) ────────
        # Parse vm_method signature from generated ViewModel code
        _vm_content = files[0].content if files else ""
        _sig_pat = re.compile(
            r'public\s+virtual\s+async\s+System\.Threading\.Tasks\.Task\s+'
            r'(F\d{3}Async)\s*\([^)]*\)'
        )
        _vm_signatures: dict[str, str] = {
            m.group(1): m.group(0)
            for m in _sig_pat.finditer(_vm_content)
        }

        methods_map: dict[str, dict] = {}
        _counts = {"generated": 0, "skipped": 0, "sys_deterministic": 0}

        for order, mo in enumerate(method_outputs):
            _mapped  = mo.get("mapped_command") or {}
            mid      = _mapped.get("module_id") or mo.get("module_id") or mo.get("event_id", "")
            eid      = mo.get("event_id", "")
            chunk    = chunk_by_event.get(eid, {})
            bd_event = chunk.get("bd_event", {})

            # vm_method info
            cs_method_name = mo.get("cs_method", "") or _mapped.get("cs_method", "")
            fxxx_async = f"{mid}Async" if re.match(r'^F\d{3}$', mid or "") else cs_method_name
            vm_sig = _vm_signatures.get(fxxx_async, "")
            code   = mo.get("code", "")

            # cs_stub (codebehind handler)
            raw_stub = chunk.get("cs_stub")
            cs_stub_out = None
            if raw_stub and isinstance(raw_stub, dict):
                cs_stub_out = {
                    "signature": raw_stub.get("signature", ""),
                    "cs_name":   raw_stub.get("cs_name", raw_stub.get("cs_method_name", "")),
                }

            # service_call (from chunk service_context)
            svc_ctx = chunk.get("service_context")
            service_call = None
            if svc_ctx and isinstance(svc_ctx, dict):
                req = svc_ctx.get("request", {})
                service_call = {
                    "method":        svc_ctx.get("interface_method", ""),
                    "request":       req.get("class", ""),
                    "response":      svc_ctx.get("response", {}).get("class", ""),
                    "request_props": req.get("properties", []),
                }

            # references — queries/macros only (no VBA modules, no DD steps)
            ld = bd_event.get("logic_detail") or {}
            refs = ld.get("references") if isinstance(ld, dict) else {}
            if not refs:
                refs = bd_event.get("references", {})
            references = {
                "queries": refs.get("queries", []) or refs.get("query", []),
                "macros":  refs.get("macros", []),
            }

            phase = mo.get("phase_type", "")
            status = mo.get("status", "")
            if phase == "sys_deterministic":
                _counts["sys_deterministic"] += 1
            elif status == "success":
                _counts["generated"] += 1
            else:
                _counts["skipped"] += 1

            methods_map[mid] = {
                "order":         order,
                "event_id":      eid,
                "module_id":     mid,
                "event_trigger": bd_event.get("event_trigger", "")  or _mapped.get("trigger", ""),
                "event_content": bd_event.get("event_content", "")  or _mapped.get("vba_event", ""),
                "vba_handler":   _mapped.get("vba_event", ""),
                "phase_type":    phase,
                "status":        status,
                "cs_stub":       cs_stub_out,
                "vm_method": {
                    "name":      fxxx_async,
                    "signature": vm_sig,
                    "body":      code,
                },
                "service_call": service_call,
                "references":   references,
                "note":         mo.get("note", ""),
            }

        # ── 5. Build contract ───────────────────────────────────────────────
        contract = {
            "form_name":       form_name,
            "feature":         _feature,
            "viewmodel_name":  _viewmodel_name,
            "view_name":       _view_name,
            "viewmodel_file":  _vm_file,
            "codebehind_file": _codebehind_file,
            "agent":           "logic",
            "summary": {
                "total_events":     len(method_outputs),
                "generated":        _counts["generated"],
                "skipped":          _counts["skipped"],
                "sys_deterministic": _counts["sys_deterministic"],
            },
            "methods": methods_map,
        }

        # ── 6. Save {form_name}.json ────────────────────────────────────────
        contract_path = out_dir / f"{form_name}.json"
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[Agent Logic] Contract saved → %s", contract_path)

        # ── 7. Keep method_outputs.json (backward compat) ──────────────────
        (out_dir / "method_outputs.json").write_text(
            json.dumps(method_outputs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # ── 8. Upsert into MongoDB agent_logic collection ───────────────────
        try:
            from pymongo import MongoClient
            from datetime import datetime, timezone
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            _col    = _client[MONGO_DB]["agent_logic"]
            _result = _col.update_one(
                {"name": form_name},
                {"$set": {**contract, "name": form_name,
                          "updated_at": datetime.now(tz=timezone.utc).isoformat()}},
                upsert=True,
            )
            _client.close()
            _action = "INSERTED" if _result.upserted_id else "UPDATED"
            logger.info("[Agent Logic] MongoDB agent_logic %s ← %s", _action, form_name)
        except Exception as _me:
            logger.warning("[Agent Logic] MongoDB upsert failed for %s: %s", form_name, _me)

    def _write_to_wpf_source(self, filename: str, code: str) -> None:
        """Write ViewModel to WPF source directory."""
        if WPF_VIEWMODELS_DIR.parent.exists():
            WPF_VIEWMODELS_DIR.mkdir(parents=True, exist_ok=True)
            target = WPF_VIEWMODELS_DIR / filename
            target.write_text(code, encoding="utf-8")
            logger.info("[Agent Logic] Updated WPF source: %s", target.name)
        else:
            logger.warning(
                "[Agent Logic] WPF source dir not found: %s",
                WPF_VIEWMODELS_DIR.parent,
            )

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _form_to_vm_name(form_name: str) -> str:
        """Keep original name: F_Login → F_Login"""
        return re.sub(r'[^\w]', '', form_name)


async def main_cli():
    """Run Agent Logic from CLI."""
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Logic Agent CLI")
    parser.add_argument("form_name", nargs="?", help="Name of the form (required if not --all)")
    parser.add_argument("--all", action="store_true", help="Process all forms from MongoDB")
    parser.add_argument("--model", help="Override LLM model")
    parser.add_argument("--input-only", action="store_true", help="Only save input snapshots, skip LLM")
    parser.add_argument("--event-class", choices=["ui", "service", "all"], default="all", help="Filter event class to process (default: all)")

    args = parser.parse_args()

    if not args.all and not args.form_name:
        parser.error("Either form_name or --all is required")

    agent = LogicAgent()
    
    forms_to_process = []
    if args.all:
        db = get_db()
        # Get all form names from bds collection
        forms = db["bds"].find({}, {"name": 1, "_id": 0})
        forms_to_process = [f["name"] for f in forms if f.get("name")]
        logger.info(f"[Agent Logic] Found {len(forms_to_process)} forms in database.")
    else:
        forms_to_process = [args.form_name]

    for fname in forms_to_process:
        logger.info(f"\n{'='*60}\n[Agent Logic] Processing: {fname}\n{'='*60}")
        try:
            input_data = AgentInput(
                form_name=fname,
                model_override=args.model,
                logic_event_class=args.event_class,
            )
            await agent.run(input_data, input_only=args.input_only)
        except Exception as e:
            logger.error(f"[Agent Logic] Failed to process {fname}: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_cli())
