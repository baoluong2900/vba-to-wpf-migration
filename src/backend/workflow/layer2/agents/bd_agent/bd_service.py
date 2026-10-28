"""
bd/bd_service.py — Orchestration BD flow

Service layer: prompt → agent → validate → return output.
Handles retry loop on validation failure.
"""
from __future__ import annotations

from typing import Any
import hashlib
import json
import copy
import time
import threading
from pathlib import Path

from utils.cost_tracker import ContextThreadPoolExecutor
from utils.logger import get_logger
from utils.paths import BD_FLOW_DIR, bd3_result_path, safe_child_path, validate_item_name

logger = get_logger(__name__)


def _logic_item_hash(item: dict[str, Any]) -> str:
    """Fingerprint of what the LLM sees for one logic item; a cached BD3 result is reused only if it matches."""
    payload = json.dumps(
        {"title": item.get("title", ""), "code": item.get("code", ""), "queries": item.get("queries", [])},
        ensure_ascii=False, sort_keys=True, default=str,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _without_hash(results: list) -> list[dict]:
    return [{k: v for k, v in r.items() if k != "_code_hash"} for r in results if isinstance(r, dict)]


def _complexity_of(bd_code_json: dict[str, Any], complexity_level: str | None = None) -> str:
    """Explicit complexity, else the one Layer 1 stored on the form/report, else "low"."""
    if complexity_level:
        return complexity_level
    root = bd_code_json.get("form") or bd_code_json.get("report") or {}
    return str(root.get("complexity_level") or "low")


class BDService:
    """Orchestrates the BD pipeline for one item."""

    def __init__(self, stage: str = "") -> None:
        self._stage = stage

    def run_logic_analysis(
        self, screen_name: str, mapped_data: dict[str, Any], bd_code_json: dict[str, Any], repo: Any, model_id: str | None, out_dir: Path, force: bool = False,
        complexity_level: str = "low",
    ) -> tuple[list[dict], Path, Path]:
        """Runs the LLM analysis for VBA logic items in batches with multithreading and caching."""
        from .core.bd_logic_graph import BDLogicGraph
        
        # Extract logic items
        vba_items, macro_results = self._get_vba_logic_items(mapped_data, bd_code_json, repo)
        
        # Files for persistence
        jsonl_path = safe_child_path(out_dir, screen_name, ".jsonl", prefix="input_")
        result_path = bd3_result_path(screen_name, out_dir)

        if not vba_items and not macro_results:
            logger.warning(f"No logic items found for {screen_name}")
            return [], jsonl_path, result_path
        
        # 1. Save inputs for tracking
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for item in vba_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        # 2. Check for existing results: reusable only for the same module_ids with unchanged code
        expected = {item["module_id"]: _logic_item_hash(item) for item in vba_items}
        if force and result_path.exists():
            result_path.unlink()
            logger.info(f"Force run: cache cleared for {screen_name}")

        if result_path.exists():
            try:
                with open(result_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                cached_hashes = {r.get("module_id"): r.get("_code_hash") for r in cached if isinstance(r, dict)}
                if cached_hashes == expected:
                    logger.info(f"Using cached results for {screen_name} ({len(cached)} items)")
                    # Combine with macro results
                    return _without_hash(cached) + macro_results, jsonl_path, result_path
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        # 3. Parallel Processing — results are keyed by module_id, never by position
        agent = BDLogicGraph()
        by_id: dict[str, dict] = {}
        lock = threading.Lock()
        batch_size = 5
        stage = self._stage or None
        
        def process_batch(start_idx):
            batch = vba_items[start_idx:start_idx + batch_size]
            logger.info(f"[BD Service] [BD3] Processing batch {start_idx//batch_size + 1}")
            
            batch_results = agent.run_logic_batch(
                batch, model_id=model_id, stage=stage, complexity_level=complexity_level
            )
            with lock:
                for res in batch_results:
                    by_id[res["module_id"]] = res

        if vba_items:
            with ContextThreadPoolExecutor(max_workers=3) as executor:
                batch_starts = range(0, len(vba_items), batch_size)
                # list() re-raises a worker's exception instead of silently dropping its batch
                list(executor.map(process_batch, batch_starts))

        # 4. Save results (VBA results only for the result.json), in vba_items order
        final_vba_results = [{**by_id[mid], "_code_hash": h} for mid, h in expected.items() if mid in by_id]
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(final_vba_results, f, ensure_ascii=False, indent=2)
            
        # Combine with macro results for the final return
        return _without_hash(final_vba_results) + macro_results, jsonl_path, result_path

    def run_ui_formula_analysis(
        self, formulas: list[dict], model_id: str | None = None, *, complexity_level: str = "low"
    ) -> list[dict]:
        """Runs the LLM translation for UI formulas in batches."""
        from .core.bd_ui_graph import BDUIFormulaGraph
        
        agent = BDUIFormulaGraph()
        results = []
        batch_size = 10
        
        for i in range(0, len(formulas), batch_size):
            batch = formulas[i : i + batch_size]
            logger.info(f"[BD Service] Translating UI formulas batch {i // batch_size + 1}/{(len(formulas) + batch_size - 1) // batch_size} ({len(batch)} items)")
            
            batch_results = agent.run_ui_batch(
                batch, model_id=model_id, stage=self._stage or None, complexity_level=complexity_level
            )
            results.extend(batch_results)
            
            if i + batch_size < len(formulas):
                time.sleep(5)
                
        return results

    def _get_out_dirs(self) -> dict[str, Path]:
        out_dirs = {
            "bd1": BD_FLOW_DIR / "bd1_bd_form",
            "bd2": BD_FLOW_DIR / "bd2_bd_mapping",
            "bd3": BD_FLOW_DIR / "bd3_bd_logic",
            "bd4": BD_FLOW_DIR / "bd4_bd_final"
        }
        for d in out_dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return out_dirs

    def run_extract_phase(
        self,
        screen_name: str,
        bd_code_json: dict[str, Any],
        repo: Any,
    ) -> dict[str, Any]:
        """Runs Step 1 (Source) and Step 2 (Mapping)."""
        validate_item_name(screen_name)
        out_dirs = self._get_out_dirs()
        logger.info(f"--- Starting BD Extraction Phase for {screen_name} ---")
        
        bd1_file = self._process_bd1_raw_data(bd_code_json, out_dirs["bd1"], screen_name)
        mapped_data, bd2_file = self._process_bd2_mapping(repo, screen_name, bd_code_json, out_dirs["bd2"])
        
        logger.info(f"--- BD Extraction Phase for {screen_name} completed ---")
        return {
            "mapped_data": mapped_data,
            "bd1_source_file": str(bd1_file),
            "bd2_mapping_file": str(bd2_file)
        }

    def run_analysis_phase(
        self,
        screen_name: str,
        bd_code_json: dict[str, Any],
        mapped_data: dict[str, Any],
        repo: Any,
        model_id: str | None = None,
        force: bool = False,
        item_type: str = "",
        complexity_level: str | None = None,
    ) -> dict[str, Any]:
        """Runs Step 3 (Logic analysis) and Step 4 (Assembly)."""
        validate_item_name(screen_name)
        out_dirs = self._get_out_dirs()
        complexity = _complexity_of(bd_code_json, complexity_level)
        logger.info(f"--- Starting BD Analysis Phase for {screen_name} ---")

        # 1. Step 3a: Analyze Business Logic (with multithreading & caching)
        logic_results, jsonl_path, result_path = self.run_logic_analysis(
            screen_name, mapped_data, bd_code_json, repo, model_id, out_dirs["bd3"], force=force,
            complexity_level=complexity,
        )

        # 2. Step 3b: Extract and Translate UI Formulas
        ui_formulas_translated = self._process_bd3_ui_formulas(
            mapped_data, out_dirs["bd3"], screen_name, model_id, complexity_level=complexity
        )

        # 3. Step 4: Assemble Final Document (S4)
        bd4_file, summary_error = self._process_bd4_assembly(
            mapped_data, logic_results, ui_formulas_translated, bd_code_json, out_dirs["bd4"], screen_name, model_id,
            item_type=item_type, complexity_level=complexity,
        )

        logger.info(f"--- BD Analysis Phase for {screen_name} completed ---")
        return {
            "logic_results": logic_results,
            "bd3_logic_jsonl": str(jsonl_path),
            "bd3_logic_result": str(result_path),
            "bd4_final_file": str(bd4_file),
            "logic_items_processed": len(logic_results),
            "summary_error": summary_error,
        }

    def run_full_flow(
        self,
        screen_name: str,
        bd_code_json: dict[str, Any],
        item_type: str,
        repo: Any,
        model_id: str | None = None,
        force: bool = False,
        complexity_level: str | None = None,
    ) -> dict[str, Any]:
        """
        Executes the full 4-step BD Flow cleanly.
        """
        extract_res = self.run_extract_phase(screen_name, bd_code_json, repo)
        analysis_res = self.run_analysis_phase(
            screen_name, 
            bd_code_json, 
            extract_res["mapped_data"], 
            repo, 
            model_id,
            force=force,
            item_type=item_type,
            complexity_level=complexity_level,
        )

        return {
            "bd1_input_type": item_type,
            "bd1_source_file": extract_res["bd1_source_file"],
            "bd2_mapping_file": extract_res["bd2_mapping_file"],
            "bd3_logic_jsonl": analysis_res["bd3_logic_jsonl"],
            "bd3_logic_result": analysis_res["bd3_logic_result"],
            "bd3_logic_summary": "",
            "bd4_final_file": analysis_res["bd4_final_file"],
            "logic_items_processed": analysis_res.get("logic_items_processed", len(analysis_res.get("logic_results", []))),
            "summary_error": analysis_res.get("summary_error", ""),
        }

    def _process_bd1_raw_data(self, bd_code_json: dict, bd1_dir: Path, screen_name: str) -> Path:
        logger.info("[BD1] Saving raw DB data (bd1_bd_form)...")
        bd1_file = safe_child_path(bd1_dir, screen_name)
        with open(bd1_file, "w", encoding="utf-8") as f:
            json.dump(bd_code_json, f, ensure_ascii=False, indent=2)
        return bd1_file

    def _process_bd2_mapping(self, repo: Any, screen_name: str, bd_code_json: dict, bd2_dir: Path) -> tuple[dict, Path]:
        logger.info("[BD2] Generating mapping (bd2_bd_mapping)...")
        from .core.core import get_bd_mapping_dict
        mapped_data = get_bd_mapping_dict(repo, screen_name, bd_code_json)
        bd2_file = safe_child_path(bd2_dir, screen_name)
        with open(bd2_file, "w", encoding="utf-8") as f:
            json.dump(mapped_data, f, ensure_ascii=False, indent=2)
        return mapped_data, bd2_file

    def _get_vba_logic_items(self, mapped_data: dict, bd_code_json: dict, repo: Any) -> tuple[list[dict], list[dict]]:
        """Extract module_ids from mapped_data and find corresponding VBA code."""
        module_ids = []
        events = mapped_data.get("sheet_2_layout", {}).get("events", [])
        for ev in events:
            mod_id = ev.get("module_id")
            if mod_id and mod_id not in module_ids:
                module_ids.append(mod_id)
                
        vba_logic_items = []
        macro_module_results = []
        form_root = bd_code_json.get("form") or bd_code_json.get("report") or {}
        form_procs = form_root.get("vba_procedures", [])
        if not form_procs:
            form_procs = form_root.get("procedures", [])
            
        for mod_id in module_ids:
            title = ""
            notes_handler = ""
            for ev in events:
                if ev.get("module_id") == mod_id:
                    title = str(ev.get("title") or "")
                    notes_handler = str(ev.get("notes") or "")
                    break

            if notes_handler.startswith("macro."):
                ref_name = notes_handler.split(".", 1)[1]
                from .macro.macro_resolver import resolve_macro_module_info
                synth = resolve_macro_module_info(repo, ref_name, "macro", mod_id, title)
                if synth:
                    macro_module_results.append(synth)
                continue

            if notes_handler.startswith("module."):
                ref_name = notes_handler.split(".", 1)[1]
                from .module.module_resolver import find_module_function_code
                func_code, func_queries = find_module_function_code(repo, ref_name)
                if func_code:
                    vba_logic_items.append({
                        "module_id": mod_id,
                        "title": title,
                        "code": func_code,
                        "queries": func_queries,
                        "notes": f"[モジュール参照: {ref_name}.xlsx]"
                    })
                else:
                    macro_module_results.append({
                        "module_id": mod_id,
                        "event_content": f"{ref_name}の処理を呼び出す",
                        "action_type": "SYS",
                        "notes": f"[モジュール参照: {ref_name}.xlsx]",
                    })
                continue

            proc_code, proc_queries = "", []
            for proc in form_procs:
                if proc.get("handler") == notes_handler:
                    proc_code = proc.get("code", "")
                    refs = proc.get("references", {})
                    for q_name in refs.get("queries", []):
                        proc_queries.append({"query_name": q_name})
                    break
            
            if proc_code and proc_code.strip():
                vba_logic_items.append({"module_id": mod_id, "title": title, "code": proc_code, "queries": proc_queries})

        return vba_logic_items, macro_module_results

    def _process_bd3_ui_formulas(
        self, mapped_data: dict, bd3_dir: Path, screen_name: str, model_id: str, complexity_level: str = "low"
    ) -> list[dict]:
        logger.info(f"Extracting UI formulas for {screen_name}...")
        from utils.extract_ui_formulas import find_all_formulas
        
        ui_formulas = []
        find_all_formulas(mapped_data, ui_formulas)
        
        ui_formulas_translated = []
        if ui_formulas:
            # Save input to JSONL before sending to LLM to track context
            input_jsonl_path = safe_child_path(bd3_dir, screen_name, ".jsonl", prefix="ui_formulas_")
            with open(input_jsonl_path, "w", encoding="utf-8") as f:
                for item in ui_formulas:
                    f.write(json.dumps({
                        "item_no": item.get("item_no", ""),
                        "formula": item.get("formula", "")
                     }, ensure_ascii=False) + "\n")

            logger.info(f"Translating {len(ui_formulas)} UI formulas...")
            ui_formulas_translated = self.run_ui_formula_analysis(
                ui_formulas, model_id=model_id, complexity_level=complexity_level
            )
            
            # Save LLM output as JSONL
            output_jsonl_path = safe_child_path(bd3_dir, screen_name, "_result.jsonl", prefix="ui_formulas_")
            with open(output_jsonl_path, "w", encoding="utf-8") as f:
                for item in ui_formulas_translated:
                    f.write(json.dumps({
                        "item_no": item.get("item_no", ""),
                        "translated_description": item.get("translated_description", "")
                    }, ensure_ascii=False) + "\n")
                
        return ui_formulas_translated

    def _process_bd4_assembly(self, mapped_data: dict, logic_results: list, ui_formulas_translated: list, bd_code_json: dict, bd4_dir: Path, screen_name: str, model_id: str | None = None, *, item_type: str = "", complexity_level: str = "low") -> tuple[Path, str]:
        """Writes BD4 and returns (bd4_file, summary_error); summary_error is "" when the summary succeeded."""
        logger.info("[BD4] Merging BD2 mapping and BD3 logic into BD4 final output...")
        
        logic_dict = {item.get("module_id"): item for item in logic_results if isinstance(item, dict)}
        final_data = copy.deepcopy(mapped_data)
        
        # 1. Inject UI formulas recursively
        if ui_formulas_translated:
            ui_dict = {item.get("physical_name"): item for item in ui_formulas_translated if item.get("physical_name")}
            
            def inject_ui_formulas_recursive(node):
                if isinstance(node, dict):
                    # Check and inject source_field_or_fixed_value
                    src_id = node.pop("_formula_id_src", None)
                    if src_id and src_id in ui_dict:
                        source_val = node.get("source_field_or_fixed_value", "")
                        translated = ui_dict[src_id].get("translated_description", "")
                        if translated and translated != source_val:
                            node["source_field_or_fixed_value"] = translated
                            
                    # Check and inject condition_and_format
                    cond_id = node.pop("_formula_id_cond", None)
                    if cond_id and cond_id in ui_dict:
                        cond_val = node.get("condition_and_format", "")
                        translated = ui_dict[cond_id].get("translated_description", "")
                        if translated and translated != cond_val:
                            node["condition_and_format"] = translated
                    
                    for key, value in node.items():
                        inject_ui_formulas_recursive(value)
                elif isinstance(node, list):
                    for item in node:
                        inject_ui_formulas_recursive(item)
            
            inject_ui_formulas_recursive(final_data)
        
        # 2. Inject event_content (LLM fields are coerced to str: a null must not reach .startswith)
        for ev in final_data.get("sheet_2_layout", {}).get("events", []):
            mod_id = ev.get("module_id")
            if mod_id in logic_dict:
                logic = logic_dict[mod_id]
                ev["event_content"] = str(logic.get("event_content") or "")
                ev["action_type"] = str(logic.get("action_type") or "")
                llm_notes = str(logic.get("notes") or "")
                if llm_notes.startswith("参照マクロ:") or llm_notes.startswith("[モジュール参照:"):
                    ev["notes"] = llm_notes
                else:
                    orig_notes = str(ev.get("notes") or "")
                    if llm_notes and llm_notes != orig_notes:
                        ev["notes"] = f"{orig_notes}\n{llm_notes}" if orig_notes else llm_notes

        # 3. Generate Screen Summary (on failure keep the mapping's fields and report the error)
        summary_error = ""
        try:
            from .core.bd_logic_graph import BDScreenSummaryGraph
            summary_agent = BDScreenSummaryGraph()
            summary = summary_agent.run_summary(
                screen_name, logic_results, model_id=model_id, mapped_data=final_data,
                ui_formulas_translated=ui_formulas_translated,
                stage=self._stage or None, complexity_level=complexity_level,
            )
            if summary.get("error"):
                summary_error = str(summary["error"])
                logger.error(f"Failed to generate screen summary for {screen_name}: {summary_error}")
            else:
                if "sheet_2_layout" not in final_data:
                    final_data["sheet_2_layout"] = {}
            
                s2_layout = final_data["sheet_2_layout"]
                s2_layout["description"] = summary.get("description", "")
                s2_layout["timing"] = summary.get("timing", "")
                s2_layout["constraints"] = summary.get("constraints", "")
                s2_layout["process_overview"] = summary.get("process_overview", [])
        except Exception as e:
            summary_error = str(e)
            logger.error(f"Failed to generate screen summary: {e}")

        # 4. Extract record_source from S1
        root = bd_code_json.get("form") or bd_code_json.get("report") or {}
        rs = ((root.get("properties") or {}).get("data") or {}).get("recordsource", "")
        if rs and "sheet_2_layout" in final_data:
            final_data["sheet_2_layout"]["record_sources"] = [{"query_name": rs}]
                
        # 5. Normalize source_table: strip whitespace-only values (e.g. "\n", "\n\n\n")
        #    and annotate computed/missing-table fields in notes
        for spec in final_data.get("sheet_5_file_spec", []):
            for item in spec.get("items", []):
                src_tbl = item.get("source_table", "")
                if isinstance(src_tbl, str) and not src_tbl.strip() and src_tbl != "":
                    field_name = item.get("output_field_name", "")
                    if field_name.endswith("f"):
                        computed_note = "計算フィールド（乗算）" if src_tbl == "\n" else "計算フィールド"
                    else:
                        computed_note = "要確認: ソーステーブル不明"
                    existing_note = item.get("notes", "")
                    item["notes"] = (computed_note + "　" + existing_note).strip() if existing_note else computed_note
                    item["source_table"] = ""


        # Save BD4
        # ── Inject type into final_data so push_to_mongo.py reads it correctly ──
        # If item_type not set → detect from L1 (macro/module/report/form)
        if not item_type:
            item_type = (
                "macro"  if "macro"  in bd_code_json else
                "module" if "module" in bd_code_json else
                "report" if "report" in bd_code_json or screen_name.upper().startswith("R") else
                "form"
            )
        final_data["type"] = item_type
        final_data["name"] = screen_name

        bd4_file = safe_child_path(bd4_dir, screen_name)
        with open(bd4_file, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)

        return bd4_file, summary_error
