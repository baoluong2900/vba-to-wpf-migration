"""
bd/bd_service.py — Orchestration BD flow

Service layer: prompt → agent → validate → return output.
Handles retry loop on validation failure.
"""
from __future__ import annotations

from typing import Any
import json
import copy
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import MAX_RETRIES
from utils.logger import get_logger

logger = get_logger(__name__)


class BDService:
    """Orchestrates the BD pipeline for one item."""

    def __init__(self, stage: str = "") -> None:
        self._stage = stage

    def run_logic_analysis(
        self, screen_name: str, mapped_data: dict[str, Any], bd_code_json: dict[str, Any], repo: Any, model_id: str | None, out_dir: Path, force: bool = False
    ) -> tuple[list[dict], Path, Path]:
        """Runs the LLM analysis for VBA logic items in batches with multithreading and caching."""
        from .core.bd_logic_graph import BDLogicGraph
        
        # Extract logic items
        vba_items, macro_results = self._get_vba_logic_items(mapped_data, bd_code_json, repo)
        
        if not vba_items and not macro_results:
            logger.warning(f"No logic items found for {screen_name}")
            return [], Path(), Path()

        # Files for persistence
        jsonl_path = out_dir / f"input_{screen_name}.jsonl"
        result_path = out_dir / f"result_{screen_name}.json"
        
        # 1. Save inputs for tracking
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for item in vba_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        # 2. Check for existing results (simple cache)
        results = []
        if force and result_path.exists():
            result_path.unlink()
            logger.info(f"Force run: cache cleared for {screen_name}")

        if result_path.exists():
            try:
                with open(result_path, "r", encoding="utf-8") as f:
                    results = json.load(f)
                if len(results) == len(vba_items):
                    logger.info(f"Using cached results for {screen_name} ({len(results)} items)")
                    # Combine with macro results
                    return results + macro_results, jsonl_path, result_path
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        # 3. Parallel Processing
        agent = BDLogicGraph()
        llm_results = [None] * len(vba_items)
        batch_size = 5
        
        def process_batch(start_idx):
            end_idx = min(start_idx + batch_size, len(vba_items))
            batch = vba_items[start_idx:end_idx]
            logger.info(f"[BD Service] [D3] Processing batch {start_idx//batch_size + 1}")
            
            batch_results = agent.run_logic_batch(batch, model_id=model_id)
            
            for i, res in enumerate(batch_results):
                llm_results[start_idx + i] = res

        if vba_items:
            with ThreadPoolExecutor(max_workers=3) as executor:
                batch_starts = range(0, len(vba_items), batch_size)
                executor.map(process_batch, batch_starts)

        # 4. Save results (VBA results only for the result.json)
        final_vba_results = [r for r in llm_results if r is not None]
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(final_vba_results, f, ensure_ascii=False, indent=2)
            
        # Combine with macro results for the final return
        return final_vba_results + macro_results, jsonl_path, result_path

    def run_ui_formula_analysis(self, formulas: list[dict], model_id: str | None = None) -> list[dict]:
        """Runs the LLM translation for UI formulas in batches."""
        from .core.bd_ui_graph import BDUIFormulaGraph
        
        agent = BDUIFormulaGraph()
        results = []
        batch_size = 10
        
        for i in range(0, len(formulas), batch_size):
            batch = formulas[i : i + batch_size]
            logger.info(f"[BD Service] Translating UI formulas batch {i // batch_size + 1}/{(len(formulas) + batch_size - 1) // batch_size} ({len(batch)} items)")
            
            batch_results = agent.run_ui_batch(batch, model_id=model_id)
            results.extend(batch_results)
            
            if i + batch_size < len(formulas):
                time.sleep(5)
                
        return results

    def _get_out_dirs(self) -> dict[str, Path]:
        proj_root = Path(__file__).resolve().parent.parent.parent
        out_dirs = {
            "s1": proj_root / "output" / "bd_flow" / "s1_bd_form",
            "s2": proj_root / "output" / "bd_flow" / "s2_bd_mapping",
            "s3": proj_root / "output" / "bd_flow" / "s3_bd_logic",
            "s4": proj_root / "output" / "bd_flow" / "s4_bd_final"
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
        out_dirs = self._get_out_dirs()
        logger.info(f"--- Starting BD Extraction Phase for {screen_name} ---")
        
        s1_file = self._process_s1_raw_data(bd_code_json, out_dirs["s1"], screen_name)
        mapped_data, s2_file = self._process_s2_mapping(repo, screen_name, bd_code_json, out_dirs["s2"])
        
        logger.info(f"--- BD Extraction Phase for {screen_name} completed ---")
        return {
            "mapped_data": mapped_data,
            "s1_source_file": str(s1_file),
            "s2_mapping_file": str(s2_file)
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
    ) -> dict[str, Any]:
        """Runs Step 3 (Logic analysis) and Step 4 (Assembly)."""
        out_dirs = self._get_out_dirs()
        logger.info(f"--- Starting BD Analysis Phase for {screen_name} ---")

        # 1. Step 3a: Analyze Business Logic (with multithreading & caching)
        logic_results, jsonl_path, result_path = self.run_logic_analysis(
            screen_name, mapped_data, bd_code_json, repo, model_id, out_dirs["s3"], force=force
        )

        # 2. Step 3b: Extract and Translate UI Formulas
        ui_formulas_translated = self._process_s3_ui_formulas(
            mapped_data, out_dirs["s3"], screen_name, model_id
        )

        # 3. Step 4: Assemble Final Document (S4)
        s4_file = self._process_s4_assembly(
            mapped_data, logic_results, ui_formulas_translated, bd_code_json, out_dirs["s4"], screen_name, model_id,
            item_type=item_type,
        )

        logger.info(f"--- BD Analysis Phase for {screen_name} completed ---")
        return {
            "logic_results": logic_results,
            "s3_logic_jsonl": str(jsonl_path),
            "s3_logic_result": str(result_path),
            "s4_final_file": str(s4_file),
            "logic_items_processed": len(logic_results),
        }

    def run_full_flow(
        self,
        screen_name: str,
        bd_code_json: dict[str, Any],
        item_type: str,
        repo: Any,
        model_id: str | None = None,
        force: bool = False,
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
        )

        return {
            "s1_input_type": item_type,
            "s1_source_file": extract_res["s1_source_file"],
            "s2_mapping_file": extract_res["s2_mapping_file"],
            "s3_logic_jsonl": analysis_res["s3_logic_jsonl"],
            "s3_logic_result": analysis_res["s3_logic_result"],
            "s3_logic_summary": "",
            "s4_final_file": analysis_res["s4_final_file"],
            "logic_items_processed": analysis_res.get("logic_items_processed", len(analysis_res.get("logic_results", [])))
        }

    def _process_s1_raw_data(self, bd_code_json: dict, s1_dir: Path, screen_name: str) -> Path:
        logger.info("[Step 1] Saving raw DB data (s1_bd_form)...")
        s1_file = s1_dir / f"{screen_name}.json"
        with open(s1_file, "w", encoding="utf-8") as f:
            json.dump(bd_code_json, f, ensure_ascii=False, indent=2)
        return s1_file

    def _process_s2_mapping(self, repo: Any, screen_name: str, bd_code_json: dict, s2_dir: Path) -> tuple[dict, Path]:
        logger.info("[Step 2] Generating mapping (s2_bd_mapping)...")
        from .core.core import get_bd_mapping_dict
        mapped_data = get_bd_mapping_dict(repo, screen_name, bd_code_json)
        s2_file = s2_dir / f"{screen_name}.json"
        return mapped_data, s2_file

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
        form_procs = bd_code_json.get("form", {}).get("vba_procedures", [])
        if not form_procs:
            form_procs = bd_code_json.get("form", {}).get("procedures", [])
            
        for mod_id in module_ids:
            title = ""
            notes_handler = ""
            for ev in events:
                if ev.get("module_id") == mod_id:
                    title = ev.get("title", "")
                    notes_handler = ev.get("notes", "")
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

    def _process_s3_vba_logic(self, mapped_data: dict, bd_code_json: dict, s3_dir: Path, screen_name: str, repo: Any, model_id: str) -> tuple[list, list, str, str]:
        """Legacy helper for s3 phase, now consolidated into run_logic_analysis."""
        vba_items, macro_results = self._get_vba_logic_items(mapped_data, bd_code_json, repo)
        return vba_items, macro_results, "", ""

        if vba_logic_items:
            logger.info(f"Running logic analysis on {len(vba_logic_items)} VBA items...")
            llm_results = self.run_logic_analysis(
                screen_name, {"logic_items": vba_logic_items},
                model_id=model_id,
                out_dir=s3_dir,
            )[0]  # run_logic_analysis returns (results, jsonl_path, result_path)

        # ── Merge: LLM results + synthetic macro/module results ──────────────
        all_results = llm_results + macro_module_results

        if not all_results:
            logger.info(f"No logic items found for {screen_name}, skipping logic analysis.")
            return [], [], str(jsonl_path), ""

        result_path = s3_dir / f"logic_{screen_name}_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        all_items = vba_logic_items + [{"module_id": r["module_id"], "title": r.get("event_content", ""), "code": "", "queries": []} for r in macro_module_results]
        return all_results, all_items, str(jsonl_path), str(result_path)




    def _process_s3_ui_formulas(self, mapped_data: dict, s3_dir: Path, screen_name: str, model_id: str) -> list[dict]:
        logger.info(f"Extracting UI formulas for {screen_name}...")
        from utils.extract_ui_formulas import find_all_formulas
        
        ui_formulas = []
        find_all_formulas(mapped_data, ui_formulas)
        
        ui_formulas_translated = []
        if ui_formulas:
            # Save input to JSONL before sending to LLM to track context
            input_jsonl_path = s3_dir / f"ui_formulas_{screen_name}.jsonl"
            with open(input_jsonl_path, "w", encoding="utf-8") as f:
                for item in ui_formulas:
                    f.write(json.dumps({
                        "item_no": item.get("item_no", ""),
                        "formula": item.get("formula", "")
                    }, ensure_ascii=False) + "\n")

            logger.info(f"Translating {len(ui_formulas)} UI formulas...")
            ui_formulas_translated = self.run_ui_formula_analysis(ui_formulas, model_id=model_id)
            
            # Save LLM output as JSONL
            output_jsonl_path = s3_dir / f"ui_formulas_{screen_name}_result.jsonl"
            with open(output_jsonl_path, "w", encoding="utf-8") as f:
                for item in ui_formulas_translated:
                    f.write(json.dumps({
                        "item_no": item.get("item_no", ""),
                        "translated_description": item.get("translated_description", "")
                    }, ensure_ascii=False) + "\n")
                
        return ui_formulas_translated

    def _process_s4_assembly(self, mapped_data: dict, logic_results: list, ui_formulas_translated: list, bd_code_json: dict, s4_dir: Path, screen_name: str, model_id: str | None = None, *, item_type: str = "") -> Path:
        logger.info("[Step 4] Merging S2 mapping and S3 logic into S4 final output...")
        
        logic_dict = {item.get("module_id"): item for item in logic_results}
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
        
        # 2. Inject event_content
        for ev in final_data.get("sheet_2_layout", {}).get("events", []):
            mod_id = ev.get("module_id")
            if mod_id in logic_dict:
                ev["event_content"] = logic_dict[mod_id].get("event_content", "")
                ev["action_type"] = logic_dict[mod_id].get("action_type", "")
                llm_notes = logic_dict[mod_id].get("notes", "")
                if llm_notes.startswith("参照マクロ:") or llm_notes.startswith("[モジュール参照:"):
                    ev["notes"] = llm_notes
                else:
                    orig_notes = ev.get("notes", "")
                    if llm_notes and llm_notes != orig_notes:
                        ev["notes"] = f"{orig_notes}\n{llm_notes}" if orig_notes else llm_notes

        # 3. Generate Screen Summary
        try:
            from .core.bd_logic_graph import BDScreenSummaryGraph
            summary_agent = BDScreenSummaryGraph()
            summary = summary_agent.run_summary(screen_name, logic_results, model_id=model_id, mapped_data=final_data, ui_formulas_translated=ui_formulas_translated)
            
            if "sheet_2_layout" not in final_data:
                final_data["sheet_2_layout"] = {}
            
            s2_layout = final_data["sheet_2_layout"]
            s2_layout["description"] = summary.get("description", "")
            s2_layout["timing"] = summary.get("timing", "")
            s2_layout["constraints"] = summary.get("constraints", "")
            s2_layout["process_overview"] = summary.get("process_overview", [])
        except Exception as e:
            logger.error(f"Failed to generate screen summary: {e}")

        # 4. Extract record_source from S1
        rs = bd_code_json.get("form", {}).get("properties", {}).get("data", {}).get("recordsource", "")
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


        # Save S4
        # ── Inject type vào final_data để push_to_mongo.py đọc đúng ────────
        # Nếu item_type chưa có → detect từ L1 (macro/module/report/form)
        if not item_type:
            item_type = (
                "macro"  if "macro"  in bd_code_json else
                "module" if "module" in bd_code_json else
                "report" if screen_name.upper().startswith("R") else
                "form"
            )
        final_data["type"] = item_type
        final_data["name"] = screen_name

        s4_file = s4_dir / f"{screen_name}.json"
        with open(s4_file, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)

        return s4_file
