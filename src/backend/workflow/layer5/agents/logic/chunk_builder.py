"""
agents/logic/chunk_builder.py — Build Event Chunks for LLM Processing

Ghép BD event + DD steps → chunk JSON cho từng event.
Mỗi chunk = 1 LLM call. Chỉ VALID chunks mới gọi LLM.

Event Classification:
  - UI_ONLY:      events chỉ xử lý UI/navigation/validation message.
                  → Prompt 1: gen ViewModel command/method only.
  - WITH_SERVICE: events có gọi query/DLookup/table → cần service layer.
                  → Prompt 2: gen ViewModel + IService + Service method.

Ref: Agent_Logic.md — "Strategy: Chunk per Event"
Ref: UIAgent._chunk_sections() — same chunking pattern
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

AGENT_DIR    = Path(__file__).parent
INPUTS_DIR   = AGENT_DIR / "inputs"

# Avalonia Views output dir — single source of truth in core.config
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from core.config import VIEWS_DIR as WPF_VIEWS_DIR, AVALONIA_PROJECT_DIR, UI_EVENT_MAP_PATH
from core.fid_resolver import macro_name


class ChunkBuilder:
    """
    Build event chunks from BD events + DD specs.
    Each chunk = 1 BD event + matching DD steps.
    """

    def build_chunks(
        self,
        bd_events: list[dict],
        dd_specs: list[dict],
        mapped_events: list[dict],
        bd_items: list[dict] = None,
        service_interface: str = "",
        xaml_bindings: dict | None = None,
    ) -> list[dict]:
        """
        Build chunks from BD events + DD specs + mapped event info.

        Args:
            bd_events: list from BD JSON sheet_2_layout.events[]
            dd_specs: list from DD JSON sheet_3_detail_specs[]
            mapped_events: output from EventMapper.map_all_events()
            bd_items: list from BD JSON sheet_3_screen_edit.items[]
            service_interface: IService interface code (optional)
            xaml_bindings: dict with properties + commands from XAML (optional)

        Returns:
            list of chunk dicts, one per event
        """
        if not bd_events:
            logger.warning("[ChunkBuilder] No BD events provided")
            return []

        # Build DD spec lookup: module_id → spec
        dd_lookup = self._build_dd_lookup(dd_specs)

        total = len(bd_events)
        chunks: list[dict] = []

        for idx, (bd_event, mapped) in enumerate(zip(bd_events, mapped_events)):
            event_id  = bd_event.get("event_id", f"E{idx:03d}")
            module_id = bd_event.get("module_id", f"F{idx:03d}")

            # Find matching DD spec
            dd_steps = dd_lookup.get(module_id, dd_lookup.get(event_id, {}))

            # Group related items for this event (based on notes like "E008, E009")
            related_items = []
            if bd_items:
                for item in bd_items:
                    notes = str(item.get("notes", ""))
                    # Split by comma and strip whitespace
                    event_refs = [r.strip() for r in notes.split(",") if r.strip()]
                    if event_id in event_refs:
                        related_items.append(item)

            chunk = {
                "form_name":       bd_event.get("form_name", ""),
                "chunk_idx":       idx,
                "total_chunks":    total,
                "chunk":           f"{idx}/{total - 1}",
                "bd_event":        bd_event,
                "related_items":   related_items,  # Specific items for this event
                "bd_items":        bd_items or [], # Full list for context
                "dd_steps":        dd_steps,
                "mapped_command":  mapped,
                "service_context": service_interface,
                "property_list":   (xaml_bindings or {}).get("properties", []),
                "command_list":    (xaml_bindings or {}).get("commands", []),
            }
            chunks.append(chunk)

            logger.debug(
                "[ChunkBuilder] Chunk %d/%d: %s %s (%s) dd_steps=%s",
                idx, total - 1,
                event_id, mapped.get("vba_event", ""),
                mapped.get("action_type", "?"),
                "YES" if dd_steps else "EMPTY",
            )

        # Summary
        valid = sum(1 for c in chunks if c["mapped_command"].get("is_main_logic") or c.get("cs_stub") is not None)
        logger.info(
            "[ChunkBuilder] Built %d chunks → %d VALID (need LLM), %d skip",
            len(chunks), valid, len(chunks) - valid,
        )
        return chunks

    def filter_valid_chunks(self, chunks: list[dict]) -> list[dict]:
        """
        Filter only VALID chunks that need LLM processing.
        An event is valid for logic generation if it is marked as main logic
        or has a cs_stub defined (mapped in ui_event_map.json).
        """
        valid = [
            c for c in chunks
            if c["mapped_command"].get("is_main_logic")
        ]
        logger.info(
            "[ChunkBuilder] Filtered %d/%d chunks as VALID",
            len(valid), len(chunks),
        )
        return valid

    def get_sys_chunks(self, chunks: list[dict]) -> list[dict]:
        """Get SYS-type chunks for deterministic handling."""
        return [
            c for c in chunks
            if c["mapped_command"].get("action_type") == "SYS"
        ]

    # ──────────────────────────────────────────
    # Event Classification: UI_ONLY vs WITH_SERVICE
    # ──────────────────────────────────────────

    @staticmethod
    def classify_event_class(event: dict) -> str:
        """
        Phân loại event thành UI hoặc SERVICE.

        SERVICE nếu:
          - logic_detail.references.queries không rỗng
          - logic_detail.references.tables không rỗng
          - VBA code chứa DLookup / DCount / DoCmd.OpenQuery / OpenRecordset
          - dd_steps chứa pattern [Fxxx_xxxQuery]

        Ngược lại → UI.
        """
        # 1. Check references.queries / tables
        references = event.get("logic_detail", {}).get("references", {})
        if references.get("queries") or references.get("tables"):
            return "SERVICE"

        # 2. Check VBA code for data-access patterns
        code = event.get("logic_detail", {}).get("code", "")
        service_patterns = [
            r"DLookup", r"DCount", r"DSum", r"DFirst", r"DLast",
            r"DoCmd\.OpenQuery", r"DoCmd\.OpenForm",
            r"OpenRecordset", r"Execute",
            r"CurrentDb", r"DAO\.", r"ADODB\.",
        ]
        for pattern in service_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return "SERVICE"

        # 3. Check dd_steps for query references [Fxxx_xxxQuery]
        dd_steps = event.get("dd_steps", {})
        dd_text = json.dumps(dd_steps, ensure_ascii=False)
        if re.search(r'\[F\d+_\w*[Qq]uery\w*\]', dd_text):
            return "SERVICE"

        return "UI"

    def save_split_inputs(self, form_name: str, all_events: list[dict]) -> tuple[str, str]:
        """
        Phân loại events thành 2 nhóm, và lưu ra 2 files:
          - inputs/FormName_ui.json      → events chỉ xử lý UI
          - inputs/FormName_service.json → events có xử lý data/service (TEMPORARILY DISABLED)

        Thêm field "event_class" vào mỗi event_meta.

        Returns:
            (ui_filepath, service_filepath) as strings.
        """
        INPUTS_DIR.mkdir(parents=True, exist_ok=True)

        # Fetch BDS from Mongo for descriptions
        from layer2.db.mongo_client import get_db
        db = get_db()
        bd_doc = db["bds"].find_one({"name": form_name}) or {}
        
        screen_desc = ""
        events_ref_map = {} # event_id -> event_content
        if "sheet_2_layout" in bd_doc:
            layout = bd_doc["sheet_2_layout"]
            screen_desc = layout.get("description", "")
            for revt in layout.get("events", []):
                eid = revt.get("event_id")
                if eid:
                    events_ref_map[eid] = revt.get("event_content", "")

        # Load C# stubs from xaml.cs
        cs_stubs = self._load_cs_stubs(form_name)
        logger.info("[ChunkBuilder] Loaded %d C# stubs for %s", len(cs_stubs), form_name)

        # trigger → C# suffix mapping
        trigger_map = {
            "クリック時":       "Click",
            "ダブルクリック時":  "DblClick",
            "更新後処理":       "AfterUpdate",
            "キー押下時":       "KeyDown",
            "画面を開く時":     "Open",
            "フォーム読み込み後": "Load",
        }

        ui_events: list[dict] = []
        service_events: list[dict] = []

        for event in all_events:
            # 1. Classify event (UI vs SERVICE)
            event_class = self.classify_event_class(event)

            # 2. Inject event_class and description vào event_meta
            meta = event.setdefault("event_meta", {})
            meta["event_class"] = event_class
            
            event_id = meta.get("event_id")
            event_desc = events_ref_map.get(event_id, meta.get("event_content", ""))
            meta["event_description_mapping"] = event_desc

            # Match C# stub từ notes (VBA handler name)
            meta     = event.get("event_meta", {})
            notes    = meta.get("notes", "")
            cs_stub  = cs_stubs.get(notes)

            if not cs_stub:
                # Fallback: physical_name + trigger suffix
                physical = meta.get("physical_name", "")
                trigger  = meta.get("event_trigger", "")
                suffix   = trigger_map.get(trigger, "")
                if physical and suffix:
                    cs_stub = cs_stubs.get(f"{physical}_{suffix}")

            # Inject cs_stub — chỉ giữ fields LLM cần, bỏ internal parser fields
            if cs_stub:
                event["cs_stub"] = {
                    "signature":   cs_stub["signature"],
                    "cs_name":     cs_stub["cs_name"],
                    "module_id":   cs_stub.get("module_id", ""),
                    "vba_handler": cs_stub.get("vba_handler", ""),
                }
            else:
                event["cs_stub"] = None

            if cs_stub:
                logger.debug("[ChunkBuilder] ✅ Stub matched %s → %s",
                             meta.get("event_id"), cs_stub["signature"])
            else:
                logger.debug("[ChunkBuilder] ⚠️  No stub for %s (notes=%s)",
                             meta.get("event_id"), notes)

            if event_class == "UI":
                ui_events.append(event)
            else:
                service_events.append(event)

        try:
            from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
            _name_map = _load_form_name_map()
            view_file_stem, _ = _resolve_wpf_names(form_name, _name_map)
        except ImportError:
            view_file_stem = form_name

        ui_data = {
            "form_name":    form_name,
            "input_type":   "UI",
            "screen_description": screen_desc,
            "description":  "Events chỉ xử lý UI/navigation/validation. Gen C# method body cho WPF code-behind.",
            "total_events": len(ui_events),
            "cs_file":      f"{view_file_stem}.axaml.cs",
            "events":       ui_events,
        }
        service_data = {
            "form_name":    form_name,
            "input_type":   "SERVICE",
            "screen_description": screen_desc,
            "description":  "Events có xử lý data/query. Gen ViewModel + IService + Service method.",
            "total_events": len(service_events),
            "cs_file":      f"{view_file_stem}.axaml.cs",
            "events":       service_events,
        }

        ui_path      = INPUTS_DIR / f"{form_name}_ui.json"
        service_path = INPUTS_DIR / f"{form_name}_service.json"

        ui_path.write_text(json.dumps(ui_data, ensure_ascii=False, indent=2), encoding="utf-8")
        service_path.write_text(json.dumps(service_data, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(
            "[ChunkBuilder] Split inputs saved:\n"
            "  UI          (%d events, %d with stub) → %s\n"
            "  SERVICE     (%d events, %d with stub) → %s",
            len(ui_events),
            sum(1 for e in ui_events if e.get("cs_stub")),
            ui_path.name,
            len(service_events),
            sum(1 for e in service_events if e.get("cs_stub")),
            service_path.name,
        )
        return str(ui_path), str(service_path)

    def _load_cs_stubs(self, form_name: str) -> dict[str, dict]:
        """
        Build cs_stub mapping từ ui_event_map.json (KHÔNG phụ thuộc vào xaml.cs đang tồn tại).

        ui_event_map.json là canonical source — được tạo trước khi UI agent chạy.
        Nếu xaml.cs tồn tại → bổ sung thêm body từ file để LLM có context.

        Returns:
            dict: { vba_handler: { "signature": str, "cs_name": str, "module_id": str } }
        """
        _UI_EVENT_MAP = UI_EVENT_MAP_PATH

        stubs: dict[str, dict] = {}

        if not _UI_EVENT_MAP.exists():
            logger.warning("[ChunkBuilder] ui_event_map.json not found — cs_stubs will be empty")
            return stubs

        try:
            registry: dict = json.loads(_UI_EVENT_MAP.read_text(encoding="utf-8"))
            form_entries: dict = registry.get(form_name, {})
        except Exception as exc:
            logger.warning("[ChunkBuilder] Failed to load ui_event_map.json: %s", exc)
            return stubs

        # VBA event name → C# WPF event suffix (matches gen_codebehind naming)
        _VBA_TO_WPF_SUFFIX: dict[str, str] = {
            "onclick":      "Click",
            "ondblclick":   "DblClick",
            "afterupdate":  "AfterUpdate",
            "beforeupdate": "BeforeUpdate",
            "onkeydown":    "PreviewKeyDown",
            "onkeyup":      "KeyUp",
            "onopen":       "Loaded",
            "onload":       "ContentRendered",
            "onclose":      "Closed",
            "ongotfocus":   "GotFocus",
            "onlostfocus":  "LostFocus",
        }

        # Arg type per WPF event
        _WPF_EVENT_ARGS: dict[str, str] = {
            "Click":          "RoutedEventArgs",
            "DblClick":       "MouseButtonEventArgs",
            "AfterUpdate":    "RoutedEventArgs",
            "PreviewKeyDown": "KeyEventArgs",
            "KeyUp":          "KeyEventArgs",
            "Loaded":         "RoutedEventArgs",
            "ContentRendered":"EventArgs",
            "Closed":         "EventArgs",
            "GotFocus":       "RoutedEventArgs",
            "LostFocus":      "RoutedEventArgs",
        }

        for module_id, entry in form_entries.items():
            if not isinstance(entry, dict) or not re.match(r'^F\d{3}$', module_id):
                continue

            vba_handler: str = entry.get("vba_handler", "")
            vba_event:   str = entry.get("event", "").lower()
            control:     str = entry.get("control", "")

            if not vba_handler or not module_id:
                continue

            # Derive C# method name: F001_PreviewKeyDown, F004_Click, etc.
            wpf_suffix = _VBA_TO_WPF_SUFFIX.get(vba_event, "")
            if not wpf_suffix:
                # Fallback: capitalise event name
                wpf_suffix = vba_event.replace("on", "").capitalize() if vba_event else "Event"
            cs_method_name = f"{module_id}_{wpf_suffix}"

            # Determine sender type (nullable for ContentRendered etc.)
            _NULLABLE = {"ContentRendered", "Closed", "Deactivated", "Activated"}
            sender_type = "object?" if wpf_suffix in _NULLABLE else "object"
            args_type   = _WPF_EVENT_ARGS.get(wpf_suffix, "RoutedEventArgs")

            # Form-level vs control-level
            if control == "__form__":
                signature = f"private async void {cs_method_name}({sender_type} sender, {args_type} e)"
            else:
                signature = f"private async void {cs_method_name}(object sender, {args_type} e)"

            vm_method = f"{module_id}Async"
            body = (
                f"    if (DataContext is ViewModels.{form_name.replace('_','')}ViewModel vm)\n"
                f"        await vm.{vm_method}();"
            )

            stubs[vba_handler] = {
                "signature":   signature,
                "full_stub":   f"{signature}\n{{\n{body}\n}}",
                "cs_name":     cs_method_name,
                "module_id":   module_id,
                "vba_handler": vba_handler,
                "vm_method":   vm_method,
                "body_empty":  False,
            }
            logger.debug("[ChunkBuilder] cs_stub from map: %s → %s", vba_handler, cs_method_name)

        logger.info(
            "[ChunkBuilder] Built %d cs_stubs from ui_event_map.json for %s",
            len(stubs), form_name,
        )

        # ── Optional: enrich with body from xaml.cs if file exists ──────────
        try:
            from agents.ui.agent_ui import _load_form_name_map, _resolve_wpf_names
            _name_map = _load_form_name_map()
            view_file_stem, _ = _resolve_wpf_names(form_name, _name_map)
        except ImportError:
            view_file_stem = form_name

        cs_file = WPF_VIEWS_DIR / f"{view_file_stem}.axaml.cs"
        if not cs_file.exists():
            cs_file = WPF_VIEWS_DIR / f"{view_file_stem}.xaml.cs"
        if not cs_file.exists():
            # Also check agent ui outputs folder (try .axaml.cs then .xaml.cs)
            ui_views = Path(__file__).resolve().parent.parent / "ui" / "outputs" / form_name / "Views"
            for _ext in (".axaml.cs", ".xaml.cs"):
                _cand = ui_views / f"{view_file_stem}{_ext}"
                if _cand.exists():
                    cs_file = _cand
                    break

        if cs_file.exists():
            try:
                content = cs_file.read_text(encoding="utf-8")
                sig_pattern = re.compile(
                    r'private\s+(?:async\s+)?void\s+(F\d{3}_\w+)\s*\([^)]*\)',
                )
                for m in sig_pattern.finditer(content):
                    cs_name = m.group(1)
                    # Update any matching stub with real body from file
                    for vba_h, stub in stubs.items():
                        if stub.get("cs_name") == cs_name:
                            # Find body from file
                            brace_start = content.find('{', m.end())
                            if brace_start != -1:
                                depth = 0
                                for i in range(brace_start, len(content)):
                                    if content[i] == '{': depth += 1
                                    elif content[i] == '}':
                                        depth -= 1
                                        if depth == 0:
                                            body = content[brace_start+1:i].strip()
                                            stub["full_stub"] = f"{stub['signature']}\n{{\n{body}\n}}"
                                            stub["body_empty"] = not body
                                            break
                logger.info("[ChunkBuilder] Enriched stubs from %s", cs_file.name)
            except Exception as exc:
                logger.debug("[ChunkBuilder] xaml.cs enrichment failed: %s", exc)

        return stubs

    def save_full_input(self, form_name: str, chunks: list[dict], suffix: str = "") -> None:
        """Save a single JSON containing all chunks in the user's requested review format."""
        INPUTS_DIR.mkdir(parents=True, exist_ok=True)
        
        filename = f"{form_name}{suffix}.json"
        filepath = INPUTS_DIR / filename
        
        # Fetch BDS and DDS from Mongo directly
        from layer2.db.mongo_client import get_db
        db = get_db()
        # Extract Screen Description (sheet_2_layout)
        from layer2.db.mongo_client import get_db
        db = get_db()
        bd_doc = db["bds"].find_one({"name": form_name}) or {}
        screen_desc = bd_doc.get("sheet_2_layout", {}).get("description", "")

        # Transform chunks into the requested "events" format
        formatted_events = self._build_formatted_events(form_name, chunks)

        full_data = {
            "form_name": form_name,
            "screen_description": screen_desc, # Root level description
            "total_events": len(chunks),
            "events": formatted_events
        }
        
        filepath.write_text(
            json.dumps(full_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[ChunkBuilder] Saved user-friendly snapshot to %s", filename)

    def _build_formatted_events(self, form_name: str, chunks: list[dict]) -> list[dict]:
        """Transform chunks into the requested user-friendly review format."""
        from layer2.db.mongo_client import get_db
        db = get_db()
        bd_doc = db["bds"].find_one({"name": form_name}) or {}
        dd_doc = db["dds"].find_one({"name": form_name}) or {}

        # Extract events_ref_map for descriptions
        events_ref_map = {}
        if "sheet_2_layout" in bd_doc:
            for revt in bd_doc["sheet_2_layout"].get("events", []):
                eid = revt.get("event_id")
                if eid:
                    events_ref_map[eid] = revt.get("event_content", "")

        # Extract FULL bd_items from DB
        bd_items_full = bd_doc.get("sheet_3_screen_edit", {}).get("items", []) or bd_doc.get("items", [])

        # Extract dd_specs from DB
        dd_specs = dd_doc.get("sheet_3_detail_specs", [])
        dd_lookup = {}
        for spec in dd_specs:
            mid = spec.get("module_id", "")
            steps = spec.get("steps", [])
            if mid:
                dd_lookup[mid] = steps

        formatted_events = []
        _form_functions_cache: dict | None = None  # cache Mongo forms functions per form_name
        for chunk in chunks:
            bd_event = chunk.get("bd_event", {})
            mapped = chunk.get("mapped_command", {})
            event_id = bd_event.get("event_id", "")
            module_id = bd_event.get("module_id") or event_id
            
            # 1. Transform dd_steps
            raw_steps = dd_lookup.get(module_id, [])
            dd_steps_obj = {}
            for i, step in enumerate(raw_steps):
                if isinstance(step, dict):
                    dd_steps_obj[f"step_{i+1}"] = {
                        "step": step.get("step", f"{i+1}. Step"),
                        "detail": step.get("detail", "")
                    }
                else:
                    dd_steps_obj[f"step_{i+1}"] = {
                        "step": f"{i+1}. Step",
                        "detail": str(step)
                    }

            # 2. Extract references
            queries = []
            if "record_sources" in bd_event:
                queries = [q.get("query_name") or q.get("query_display") for q in bd_event["record_sources"] if q]
            
            content_str = str(bd_event.get("event_content", "")) + " " + str(raw_steps)
            found_queries = re.findall(r'\[(SelQuery\w+|Query\w+|F\d+_\w+)\]', content_str)
            queries = list(set(queries + found_queries))

            # Extract macro references from notes ("参照マクロ: MacroName.xlsx")
            # and from dd_steps [refer: MacroName]
            notes_field = bd_event.get("notes", "")
            macros: list[str] = []
            modules_ref: list[str] = []
            macro_ref = macro_name(notes_field)   # "macro.X" / "参照マクロ: X.xlsx"
            if macro_ref:
                macros.append(macro_ref)

            # ── Priority 1: đọc references trực tiếp từ VBA code trong Mongo ──────
            # forms collection đã được aggregator layer1 phân loại đúng:
            #   modules = ["Common.Judge_Inst", "Module1.タイマーを開く"]  (VBA Call xxx)
            #   macros  = ["AutoExec_Restart", "AutoExec_A"]              (DoCmd.RunMacro "xxx")
            vba_handler_name = mapped.get("vba_event") or notes_field
            raw_vba_refs: dict = {}
            if vba_handler_name and not macro_ref:
                # Cache form functions để tránh query Mongo lại mỗi chunk
                if _form_functions_cache is None:
                    try:
                        from layer2.db.mongo_client import get_db as _get_db
                        _db = _get_db()
                        _form_doc = _db["forms"].find_one({"name": form_name}, {"functions": 1}) or {}
                        _form_functions_cache = {
                            fn.get("handler"): fn.get("references", {})
                            for fn in _form_doc.get("functions", [])
                            if fn.get("handler")
                        }
                    except Exception:
                        _form_functions_cache = {}
                raw_vba_refs = _form_functions_cache.get(vba_handler_name, {})

            if raw_vba_refs:
                # Dùng references từ Mongo — đã phân loại đúng bởi aggregator
                for m in raw_vba_refs.get("macros", []):
                    if m and m not in macros:
                        macros.append(m)
                for m in raw_vba_refs.get("modules", []):
                    if m and m not in modules_ref:
                        modules_ref.append(m)
            else:
                # Fallback: scan dd_steps [refer: xxx] và phân loại theo format
                # Pattern "XxxName.SomeName" (bất kể ASCII hay Japanese) → module
                # Pattern không có dấu "." → macro
                dd_text = json.dumps(raw_steps, ensure_ascii=False)
                # Regex nhận dạng "Module.Proc" kể cả Japanese: phần trước "." không chứa space/bracket
                _module_ref_pat = re.compile(r'^[^\s\(\)\.]+\.[^\s\(\)\.]+$')
                for ref_match_fb in re.finditer(r'\[refer:\s*([^\]]+)\]', dd_text):
                    ref_val = ref_match_fb.group(1).strip()
                    if _module_ref_pat.match(ref_val):
                        # "Common.Judge_Inst" / "Module1.タイマーを開く" → module
                        if ref_val not in modules_ref:
                            modules_ref.append(ref_val)
                    else:
                        # "AutoExec_Restart" / "MenuBarTrue" → macro
                        if ref_val not in macros:
                            macros.append(ref_val)

            # 3. Build logic_detail
            logic_detail = {
                "code": chunk.get("generated_code", "// Code not generated yet"),
                "references": {
                    "forms": raw_vba_refs.get("forms", []),
                    "reports": raw_vba_refs.get("reports", []),
                    "queries": queries,
                    "macros": macros,
                    "modules": modules_ref,
                    "tables": raw_vba_refs.get("tables", []),
                }
            }

            # 4. Extract VBA code
            # For macro-reference events (notes "macro.X" / "参照マクロ: X.xlsx") no VBA Sub exists.
            # Use macro name as the handler key; if not found, build a descriptive comment.
            vba_handler = mapped.get("vba_event") or notes_field
            is_macro_ref = bool(macro_ref)

            if is_macro_ref:
                macro_label = macros[0] if macros else notes_field
                logic_detail["code"] = (
                    f"// This event runs Access macro: 「{macro_label}」\n"
                    f"// No VBA Sub — triggered directly via DoCmd.RunMacro or macro action.\n"
                    f"// WPF equivalent: implement the macro logic in the corresponding C# method."
                )
            else:
                vba_code = self._extract_vba_code(form_name, vba_handler)
                logic_detail["code"] = vba_code if vba_code else "// Original VBA code not found"
            
            # 5. Extract related items
            related_items = []
            for item in bd_items_full:
                notes = str(item.get("notes", ""))
                if event_id in [r.strip() for r in notes.split(",") if r.strip()]:
                    related_items.append(item)

            # 6. Inject Description
            bd_event["event_description_mapping"] = events_ref_map.get(event_id, bd_event.get("event_content", ""))
            
            # Inject cs_stub — chỉ giữ fields LLM cần
            raw_stub = chunk.get("cs_stub")
            if raw_stub:
                cs_stub = {
                    "signature":   raw_stub["signature"],
                    "cs_name":     raw_stub.get("cs_name", raw_stub.get("cs_method_name", "")),
                    "module_id":   raw_stub.get("module_id", ""),
                    "vba_handler": raw_stub.get("vba_handler", ""),
                }
            else:
                cs_stub = None

            # service_context chỉ cần cho SERVICE events
            # UI events không gọi service → bỏ hoàn toàn khỏi JSON
            event_class = bd_event.get("event_class") or self.classify_event_class(chunk)
            service_ctx = None
            if event_class == "SERVICE":
                service_ctx = self._build_structured_service_context(
                    raw_ctx=chunk.get("service_context", ""),
                    module_id=module_id,
                    form_name=form_name,
                )

            event_entry = {
                "event_meta":   bd_event,
                "logic_detail": logic_detail,
                "bd_items":     related_items,
                "dd_steps":     dd_steps_obj,
                "cs_stub":      cs_stub,
            }
            # Chỉ thêm service_context khi có giá trị
            if service_ctx:
                event_entry["service_context"] = service_ctx

            formatted_events.append(event_entry)
        return formatted_events

    def _build_structured_service_context(self, raw_ctx: str, module_id: str, form_name: str = "") -> dict | None:
        """
        Build structured service context cho LLM từ service_contract.json (priority)
        hoặc parse blob C# text (fallback).

        Output (mỗi event chỉ thấy đúng phần của mình):
        {
          "interface_method": "Task<F003Response> F003Async(F003Request request);",
          "request": {
            "class":      "F003Request",
            "properties": [
              { "name": "TxtID",   "type": "string",  "nullable": false },
              { "name": "TxtPass", "type": "string",  "nullable": false }
            ]
          },
          "response": {
            "class":      "F003Response",
            "properties": [
              { "name": "Success",  "type": "bool",   "nullable": false },
              { "name": "Message",  "type": "string", "nullable": true  }
            ]
          },
          "vm_method":          "F003Async",
          "service_field_hint": "_fLoginService"
        }
        """
        # ── Priority 1: service contract ({form_name}.json or legacy service_contract.json) ──
        _form = form_name
        if _form and module_id:
            try:
                from agents.ui.tool_skeleton import load_service_contract
                _contract = load_service_contract(_form)
                if _contract:
                    _methods  = _contract.get("methods", {})
                    _entry    = _methods.get(module_id)
                    if _entry:
                        svc_field = _contract.get("service_field", "_service")
                        iface     = _contract.get("iface_class", "")
                        req_props = _entry.get("request_props", [])
                        method_name = _entry.get("method_name", f"{module_id}Async")
                        req_class   = _entry.get("request_class", f"{module_id}Request")
                        res_class   = _entry.get("response_class", f"{module_id}Response")

                        # Priority: response_props từ contract (vừa gen bởi Agent Service)
                        # Fallback: đọc từ source file (để resolve entity_shapes)
                        contract_res_props = _entry.get("response_props", [])
                        if contract_res_props:
                            # Convert to standard format với nullable detection
                            res_props = [
                                {
                                    "name": p["name"],
                                    "type": p["type"],
                                    "nullable": p["type"].endswith("?") or "?" in p["type"],
                                }
                                for p in contract_res_props
                            ]
                            # Resolve entity_shapes for IEnumerable<XEntity> props
                            source_root = AVALONIA_PROJECT_DIR
                            for prop in res_props:
                                inner_m = re.search(r'(?:IEnumerable|List|IList)<([A-Za-z]\w+)>', prop.get("type", ""))
                                if inner_m:
                                    entity_fields = self._resolve_entity_fields(inner_m.group(1), source_root)
                                    if entity_fields:
                                        prop["entity_shape"] = {"class": inner_m.group(1), "fields": entity_fields}
                        else:
                            # Fallback: đọc từ source file (resolves entity_shapes tự động)
                            res_props = self._read_response_dto_props(res_class, _form)

                        result = {
                            "interface_method": (
                                f"{_entry['return_type']} {method_name}({req_class} request);"
                            ),
                            "request": {
                                "class": req_class,
                                "properties": [
                                    {"name": p["name"], "type": p["type"], "nullable": False}
                                    for p in req_props
                                ],
                            },
                            "response": {
                                "class": res_class,
                                "properties": res_props,
                            },
                            "vm_method":          _entry.get("vm_method_name", f"{module_id}Async"),
                            "service_field_hint": svc_field,
                            "iface_class":        iface,
                        }
                        logger.debug(
                            "[ChunkBuilder] service_context from contract for %s/%s: %s",
                            _form, module_id, method_name,
                        )
                        return result
            except Exception as _ce:
                logger.debug("[ChunkBuilder] contract lookup failed for %s/%s: %s", _form, module_id, _ce)

        # ── Priority 2: fallback — already-structured dict ───────────────
        if isinstance(raw_ctx, dict):
            return raw_ctx

        if not raw_ctx:
            return None

        # ── Priority 3: parse blob C# text ───────────────────────────────
        # ── Parse "// File: xxx.cs" blocks ─────────────────────────────
        file_blocks: dict[str, str] = {}
        current_file: str | None = None
        current_lines: list[str] = []

        for line in raw_ctx.splitlines():
            m = re.match(r'^//\s*File:\s*(\S+\.cs)\s*$', line)
            if m:
                if current_file and current_lines:
                    file_blocks[current_file] = "\n".join(current_lines).strip()
                current_file = m.group(1)
                current_lines = []
            else:
                if current_file is not None:
                    current_lines.append(line)
        if current_file and current_lines:
            file_blocks[current_file] = "\n".join(current_lines).strip()

        if not file_blocks:
            return {"raw": raw_ctx[:300]} if raw_ctx else None

        # ── Detect feature prefix (IFLoginService.cs → "FLogin") ───────
        feature_prefix = ""
        for fname in file_blocks:
            feat_match = re.match(r'^I(\w+)Service\.cs$', fname, re.IGNORECASE)
            if feat_match and "public interface" in file_blocks.get(fname, ""):
                feature_prefix = feat_match.group(1)
                break

        def _pick_file(role_keywords: list[str]) -> tuple[str, str] | None:
            candidates = [
                (f, c) for f, c in file_blocks.items()
                if any(kw in f.lower() for kw in role_keywords)
            ]
            if not candidates:
                return None
            if feature_prefix:
                pref = [c for c in candidates if c[0].lower().startswith(feature_prefix.lower())]
                if pref:
                    return pref[0]
            return candidates[0]

        def _parse_properties(content: str, class_name: str) -> list[dict]:
            class_start = re.search(
                r'public\s+class\s+' + re.escape(class_name) + r'\b[^{]*\{',
                content,
            )
            if not class_start:
                return []
            start = class_start.end()
            depth = 1
            pos = start
            while pos < len(content) and depth > 0:
                if content[pos] == '{':
                    depth += 1
                elif content[pos] == '}':
                    depth -= 1
                pos += 1
            body = content[start:pos - 1]
            props = []
            prop_pattern = re.compile(
                r'public\s+([\w<>?\[\].]+)\s+(\w+)\s*\{[^}]*get[^}]*\}'
            )
            for m in prop_pattern.finditer(body):
                raw_type = m.group(1)
                name = m.group(2)
                if name in ("get", "set", "init"):
                    continue
                nullable = raw_type.endswith("?")
                clean_type = raw_type.rstrip("?")
                props.append({"name": name, "type": clean_type, "nullable": nullable})
            return props

        def _extract_interface_method(content: str, mid: str) -> str:
            pattern = re.compile(
                r'Task<\w+>\s+' + re.escape(mid) + r'Async\s*\([^)]*\)\s*;'
            )
            m = pattern.search(content)
            return m.group(0).strip() if m else f"Task<{mid}Response> {mid}Async({mid}Request request);"

        interface_method = ""
        for fname, content in file_blocks.items():
            if re.match(r'^I\w+Service\.cs$', fname, re.IGNORECASE) and "public interface" in content:
                interface_method = _extract_interface_method(content, module_id)
                break

        req_result = None
        req_pick = _pick_file(["servicerequests", "request"])
        if req_pick:
            req_fname, req_content = req_pick
            class_name = f"{module_id}Request"
            props = _parse_properties(req_content, class_name)
            req_result = {"class": class_name, "properties": props}

        res_result = None
        res_pick = _pick_file(["serviceresponses", "response"])
        if res_pick:
            res_fname, res_content = res_pick
            class_name = f"{module_id}Response"
            props = _parse_properties(res_content, class_name)
            # Resolve entity shapes for IEnumerable<XEntity> properties
            source_root = AVALONIA_PROJECT_DIR
            for prop in props:
                raw_t = prop.get("type", "")
                inner_m = re.search(r'(?:IEnumerable|List|IList|IReadOnlyList)<([A-Za-z]\w+)>', raw_t)
                if inner_m:
                    inner_type = inner_m.group(1)
                    entity_fields = self._resolve_entity_fields(inner_type, source_root)
                    if entity_fields:
                        prop["entity_shape"] = {"class": inner_type, "fields": entity_fields}
            res_result = {"class": class_name, "properties": props}

        service_field = (
            f"_{feature_prefix[0].lower()}{feature_prefix[1:]}Service"
            if feature_prefix else "_service"
        )

        result: dict = {}
        if interface_method:
            result["interface_method"] = interface_method
        if req_result:
            result["request"] = req_result
        if res_result:
            result["response"] = res_result
        result["vm_method"]          = f"{module_id}Async"
        result["service_field_hint"] = service_field

        return result if (interface_method or req_result or res_result) else None

    def _read_response_dto_props(self, res_class: str, form_name: str) -> list[dict]:
        """
        Read actual Response DTO properties from source file.
        Also resolves entity/DTO shapes for IEnumerable<XEntity> / XDto properties
        so LLM knows the exact field names instead of hallucinating.
        Fallback to default [Success, Message] if file not found.
        """
        source_root = AVALONIA_PROJECT_DIR
        feature = re.sub(r"_", "", (form_name or "").replace("F_", "F")) or "Default"
        responses_file = source_root / "vba_brain.Application" / "DTOs" / "Responses" / f"{feature}ServiceResponses.cs"

        default_props = [
            {"name": "Success", "type": "bool",   "nullable": False},
            {"name": "Message", "type": "string?", "nullable": True},
        ]

        if not responses_file.exists():
            return default_props

        try:
            content = responses_file.read_text(encoding="utf-8")
            class_pat = re.compile(
                r'public\s+class\s+' + re.escape(res_class) + r'\b[^{]*\{',
            )
            m = class_pat.search(content)
            if not m:
                return default_props

            start = m.end()
            depth, end = 1, start
            for i in range(start, len(content)):
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            body = content[start:end]

            prop_pat = re.compile(
                r'public\s+((?:[\w<>?,\s])+?)\s+(\w+)\s*\{\s*get;\s*set;\s*\}'
            )
            props = []
            for pm in prop_pat.finditer(body):
                ptype = pm.group(1).strip()
                pname = pm.group(2).strip()
                nullable = ptype.endswith("?") or "?" in ptype
                prop_entry: dict = {"name": pname, "type": ptype, "nullable": nullable}

                # ── Resolve entity/DTO shapes for collection types ───────────────
                # Pattern: IEnumerable<AuthEntity>? / List<GetUserInfoDto>? / IEnumerable<T022PrefectureEntity>?
                inner_match = re.search(r'(?:IEnumerable|List|IList|IReadOnlyList)<([A-Za-z]\w+)>', ptype)
                if inner_match:
                    inner_type = inner_match.group(1)
                    entity_fields = self._resolve_entity_fields(inner_type, source_root)
                    if entity_fields:
                        prop_entry["entity_shape"] = {
                            "class": inner_type,
                            "fields": entity_fields,
                        }
                        logger.debug(
                            "[ChunkBuilder] Resolved entity shape: %s → %d fields",
                            inner_type, len(entity_fields),
                        )

                props.append(prop_entry)

            return props if props else default_props
        except Exception as exc:
            logger.debug("[ChunkBuilder] Failed to read response DTO %s: %s", res_class, exc)
            return default_props

    def _resolve_entity_fields(self, class_name: str, source_root: Path) -> list[dict]:
        """
        Tìm và đọc fields của một Entity / DTO class từ source tree.
        Tìm trong:
          - vba_brain.Domain/Entities/**/{class_name}.cs
          - vba_brain.Domain/DTOs/**/{class_name}.cs
          - vba_brain.Application/DTOs/**/{class_name}.cs
        Returns list of {"name": str, "type": str, "column": str (optional)}
        """
        search_dirs = [
            source_root / "vba_brain.Domain" / "Entities",
            source_root / "vba_brain.Domain" / "DTOs",
            source_root / "vba_brain.Application" / "DTOs",
        ]
        for base_dir in search_dirs:
            if not base_dir.exists():
                continue
            for cs_file in base_dir.rglob(f"{class_name}.cs"):
                try:
                    content = cs_file.read_text(encoding="utf-8")
                    # Find class body
                    cls_m = re.search(
                        r'public\s+class\s+' + re.escape(class_name) + r'\b[^{]*\{',
                        content,
                    )
                    if not cls_m:
                        continue
                    start = cls_m.end()
                    depth, end = 1, start
                    for i in range(start, len(content)):
                        if content[i] == '{':
                            depth += 1
                        elif content[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i
                                break
                    body = content[start:end]

                    fields = []
                    # Extract [Column("xxx")] + public TYPE NAME
                    col_prop_pat = re.compile(
                        r'(?:\[Column\("([^"]+)"\)\]\s*)?'
                        r'public\s+([\w<>?\[\]]+)\s+(\w+)\s*\{[^}]*get[^}]*\}',
                        re.DOTALL,
                    )
                    for fm in col_prop_pat.finditer(body):
                        col_name  = fm.group(1) or ""   # e.g. "管理者FLG"
                        prop_type = fm.group(2).strip()
                        prop_name = fm.group(3).strip()
                        if prop_name in ("get", "set", "init"):
                            continue
                        entry: dict = {"name": prop_name, "type": prop_type}
                        if col_name:
                            entry["column"] = col_name
                        fields.append(entry)

                    if fields:
                        return fields
                except Exception as exc:
                    logger.debug("[ChunkBuilder] Failed to parse entity %s: %s", class_name, exc)
        return []

    def _extract_vba_code(self, form_name: str, handler: str) -> str:
        """Find the VBA code for the given handler from the MongoDB forms collection."""
        try:
            from layer2.db.mongo_client import get_db
            db = get_db()
            form_doc = db["forms"].find_one({"name": form_name})
            
            if not form_doc:
                return ""
                
            functions = form_doc.get("functions", [])
            for func in functions:
                if func.get("handler") == handler:
                    visibility = str(func.get("visibility", "Private")).capitalize()
                    func_type = str(func.get("type", "Sub"))
                    func_input = func.get("input", "")
                    code_body = func.get("code", "")
                    
                    header = f"{visibility} {func_type} {handler}({func_input})"
                    
                    if "Declare" in func_type:
                        return header
                    
                    # Reconstruct the full block
                    end_keyword = "Function" if "Function" in func_type else "Sub"
                    footer = f"End {end_keyword}"
                    
                    return f"{header}\n{code_body}\n{footer}"
                    
            return ""
        except Exception as e:
            logger.warning(f"Failed to fetch VBA code from MongoDB for {form_name}.{handler}: {e}")
            return ""

    # ──────────────────────────────────────────
    # DD Spec Lookup
    # ──────────────────────────────────────────

    @staticmethod
    def _build_dd_lookup(dd_specs: list[dict]) -> dict[str, dict]:
        """
        Build lookup dict: module_id/event_id → DD steps.

        DD specs can have different structures:
        1. sheet_3_detail_specs[].module_id → match BD event.module_id
        2. sheet_3_detail_specs[].event_id → match BD event.event_id
        3. Flat dict with step_1_init, step_2_main, step_3_error
        """
        lookup: dict[str, dict] = {}

        for spec in dd_specs:
            # Try module_id first
            mid = spec.get("module_id", "")
            eid = spec.get("event_id", "")

            # Extract DD steps (may be nested or flat)
            steps = {}
            for key in ("step_1_init", "step_2_main", "step_3_error",
                        "step_1", "step_2", "step_3",
                        "init", "main", "error"):
                if key in spec and spec[key]:
                    steps[key] = spec[key]

            # If spec itself IS the steps (flat structure)
            if not steps and any(k.startswith("step_") for k in spec):
                steps = {k: v for k, v in spec.items()
                         if k.startswith("step_") and v}

            # If spec has a nested "steps" or "detail" key
            if not steps:
                nested = spec.get("steps") or spec.get("detail") or spec.get("logic")
                if isinstance(nested, dict):
                    steps = nested
                elif isinstance(nested, list):
                    # Convert list of steps to dict for easier prompting
                    steps = {f"step_{i+1}": s for i, s in enumerate(nested)}

            if mid:
                lookup[mid] = steps
            if eid:
                lookup[eid] = steps

        logger.info(
            "[ChunkBuilder] DD lookup: %d entries from %d specs",
            len(lookup), len(dd_specs),
        )
        return lookup
