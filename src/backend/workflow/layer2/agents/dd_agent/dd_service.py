"""
dd_agent/dd_service.py — Orchestration for full DD flow (D1 → D4)

Mirrors bd_service.py pattern.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import threading
from concurrent.futures import ThreadPoolExecutor
from .core.fill_utils import normalize_vba_name
from utils.logger import get_logger
from utils.paths import bd3_result_path, safe_child_path, validate_item_name

logger = get_logger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_LAYER2_DIR = Path(__file__).resolve().parent.parent.parent
_SCHEMA_DIR  = _LAYER2_DIR / "schema" / "template"
_OUTPUT_BASE = _LAYER2_DIR / "output"


class DDService:
    """Orchestrates the DD pipeline D1→D4 for one screen."""

    def __init__(self, stage: str = "") -> None:
        self._stage = stage

    # ── Internal: push single DD4 file to MongoDB + backup ─────────────────
    def _push_dd4_to_mongo(self, screen_name: str, doc: dict, dd4_file: Path, category: str = "") -> None:
        """
        Upsert *doc* into the ``dds`` MongoDB collection and copy the JSON file
        to the database_json/dds/ backup directory.

        Mirrors the logic in push_to_mongo._upsert_docs / _copy_to_backup but
        operates on a single document so it can be called inline after DD4.

        Adds ``type`` field: macro → "macro", common → "module",
        screen + R-prefix → "report", screen → "form".
        """
        import shutil
        from datetime import datetime, timezone

        # ── Determine item type ───────────────────────────────────────────
        _CAT_TO_TYPE = {"macro": "macro", "common": "module", "report": "report"}
        if category in _CAT_TO_TYPE:
            item_type = _CAT_TO_TYPE[category]
        else:
            # screen: look up Layer 1 for form vs report
            item_type = None
            try:
                from db.layer1_repo import Layer1Repo
                from config import L1_COLLECTION_REPORTS
                repo = Layer1Repo()
                if repo._find_one(L1_COLLECTION_REPORTS, screen_name):
                    item_type = "report"
                else:
                    item_type = "form"
            except Exception:
                item_type = "report" if screen_name.upper().startswith("R") else "form"

        # ── MongoDB upsert (shared cached client — nothing to close or leak) ──
        try:
            from db.mongo_client import get_db

            now = datetime.now(tz=timezone.utc).isoformat()
            payload = {
                **doc,
                "name": screen_name,
                "type": item_type,
                "updated_at": now,
            }

            col = get_db()["dds"]
            result = col.update_one({"name": screen_name}, {"$set": payload}, upsert=True)

            if result.upserted_id is not None:
                logger.info("[DD Service] [PUSH] INSERTED  dds ← %s", screen_name)
            else:
                logger.info("[DD Service] [PUSH] UPDATED   dds ← %s", screen_name)
        except Exception as exc:
            logger.error("[DD Service] [PUSH] MongoDB upsert failed for %s: %s", screen_name, exc)

        # ── File backup ───────────────────────────────────────────────────
        try:
            backup_dir = _LAYER2_DIR.parent.parent.parent.parent / "data" / "dds"
            backup_dir.mkdir(parents=True, exist_ok=True)
            dest = backup_dir / dd4_file.name
            shutil.copy2(dd4_file, dest)
            logger.info("[DD Service] [BACKUP] Copied %s → %s", dd4_file.name, backup_dir)
        except Exception as exc:
            logger.error("[DD Service] [BACKUP] File backup failed for %s: %s", screen_name, exc)

    def run_full_flow(
        self,
        screen_name: str,
        model_id: str | None = None,
        skip_llm: bool = False,
        stop_step: int = 4,
        force: bool = False,
        complexity_level: str | None = None,
    ) -> dict[str, Any]:


        """
        Run full DD flow:
          DD1: Fetch dd_code_json from DB -> dd1_dd_source
          DD2: Parse dd1_dd_source + bd4_bd_final → skeleton (no LLM) -> dd2_dd_mapping
          DD3: LLM fill detail steps per module -> dd3_dd_logic/logic_{screen_name}.jsonl
          DD4: Merge DD2 + DD3 → final JSON -> dd4_dd_final

        Reads:
          output/bd_flow/bd4_bd_final/{screen_name}.json

        Writes:
          output/dd_flow/dd1_dd_source/{screen_name}.json
          output/dd_flow/dd2_dd_mapping/{screen_name}.json
          output/dd_flow/dd3_dd_logic/logic_{screen_name}.jsonl
          output/dd_flow/dd4_dd_final/{screen_name}.json

        Returns:
          dict with paths and stats
        """
        validate_item_name(screen_name)

        # ── Detect Category ──────────────────────────────────────────────
        from db.layer1_repo import Layer1Repo
        from config import L1_COLLECTION_FORMS, L1_COLLECTION_REPORTS, L1_COLLECTION_MODULES, L1_COLLECTION_MACROS
        repo = Layer1Repo()
        
        category = "common" # Default (Modules)
        if repo._find_one(L1_COLLECTION_FORMS, screen_name):
            category = "screen"
        elif repo._find_one(L1_COLLECTION_REPORTS, screen_name):
            category = "report"
        elif repo._find_one(L1_COLLECTION_MODULES, screen_name):
            category = "common" # Module is common
        elif repo._find_one(L1_COLLECTION_MACROS, screen_name):
            category = "macro"  # Macro is separate


        # ── Paths ──────────────────────────────────────────────────────────
        bd_final_dir = _OUTPUT_BASE / "bd_flow" / "bd4_bd_final"
        
        # New structure: dd_flow/{category}/dd{n}_...
        category_dir = _OUTPUT_BASE / "dd_flow" / category
        dd1_dir = category_dir / "dd1_dd_skeleton"
        dd2_dir = category_dir / "dd2_dd_mapping"
        dd3_dir = category_dir / "dd3_dd_logic"
        dd4_dir = category_dir / "dd4_dd_final"

        bd_final_path    = safe_child_path(bd_final_dir, screen_name)
        if category == "macro":
            dd_form_sample = _SCHEMA_DIR / "dd_macros.json"
        elif category == "common":
            dd_form_sample = _SCHEMA_DIR / "dd_modules.json"
        else:
            dd_form_sample = _SCHEMA_DIR / "dd_form.json"

        dd_form_jsonl    = _SCHEMA_DIR / "dd_form.jsonl"


        # Validate inputs
        # BD final is optional for standalone Modules/Macros
        bd_exists = bd_final_path.exists()
        if not bd_exists:
            logger.warning("[DD Service] BD final not found: %s. Proceeding with dummy BD context.", bd_final_path)

        if not dd_form_sample.exists():
            raise FileNotFoundError(f"dd_form.json template not found: {dd_form_sample}")

        # ── D1: Extract Source (Deep) from DB ────────────────────────────
        logger.info("[DD Service] [DD1] Fetching dd_code_json from DB for %s ...", screen_name)
        
        # Load BD source for dependency hints
        bd_source_path = safe_child_path(_OUTPUT_BASE / "bd_flow" / "bd1_bd_form", screen_name)
        bd_source = None
        if bd_source_path.exists():
            try:
                bd_source = json.loads(bd_source_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("[DD Service] Failed to load BD source: %s", e)

        # from db.layer1_repo import Layer1Repo
        # repo = Layer1Repo()
        dd_source = repo.get_dd_code_json_unified(screen_name, bd_source=bd_source)
        _src_root = dd_source.get("form") or dd_source.get("report") or dd_source.get("module") or {}
        complexity = complexity_level or str(_src_root.get("complexity_level") or "medium")
        
        dd1_dir.mkdir(parents=True, exist_ok=True)
        dd1_file = safe_child_path(dd1_dir, screen_name)
        dd1_file.write_text(json.dumps(dd_source, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[DD Service] [DD1] Source saved: %s", dd1_file)

        if stop_step == 1:
            return {"screen_name": screen_name, "dd1_source_file": str(dd1_file), "status": "stopped_at_dd1"}


        # ── D2: Skeleton & Mapping ─────────────────────────────────────────
        logger.info("[DD Service] [DD2] Building mapping skeleton for %s ...", screen_name)
        
        if category == "screen":
            from .screen.fill_dd_form import get_dd_skeleton
        elif category == "report":
            from .report.fill_dd_report import get_dd_skeleton
        elif category == "macro":
            from .macro.fill_dd_macro import get_dd_skeleton
        else:
            from .module.fill_dd_module import get_dd_skeleton

        skeleton, logic_items = get_dd_skeleton(
            screen_name=screen_name,
            dd_code_json_path=dd1_file,
            bd_final_path=bd_final_path,
            template_path=dd_form_sample,
            output_dir=dd2_dir,
            category=category,
        )
        dd2_file = safe_child_path(dd2_dir, screen_name)
        logger.info("[DD Service] [DD2] Mapping saved: %s", dd2_file)

        if stop_step == 2:
            return {
                "screen_name": screen_name,
                "dd1_source_file": str(dd1_file),
                "dd2_mapping_file": str(dd2_file),
                "status": "stopped_at_dd2"
            }



        # ── D3: LLM detail steps per module ───────────────────────────────
        logger.info("[DD Service] [DD3] Running LLM detail generation ...")
        from .core.dd_agent import DDAgent

        dd_schema_template = ""
        if dd_form_jsonl.exists():
            dd_schema_template = dd_form_jsonl.read_text(encoding="utf-8")

        bd_events_map: dict[str, dict] = {}
        if bd_exists:
            bd_final = json.loads(bd_final_path.read_text(encoding="utf-8"))
            for ev in (bd_final.get("sheet_2_layout") or {}).get("events") or []:
                mid = ev.get("module_id", "")
                if mid:
                    bd_events_map[mid] = ev

        else:
            bd_final = {"screen_id": screen_name, "screen_name": screen_name}

        # ── Load BD3 BD Logic result (event_content per module_id) ─────────
        s3_logic_map: dict[str, dict] = {}
        s3_logic_path = bd3_result_path(screen_name)
        if s3_logic_path.exists():
            try:
                s3_results = json.loads(s3_logic_path.read_text(encoding="utf-8"))
                for r in s3_results:
                    mid = r.get("module_id", "")
                    if mid:
                        s3_logic_map[mid] = r
                logger.info("[DD Service] [DD3] Loaded BD3 BD logic result: %d entries", len(s3_logic_map))
            except Exception as e:
                logger.warning("[DD Service] [DD3] Could not load BD3 logic result: %s", e)


        # logic_items is already populated and modified (RecordSource, Merges) by get_dd_skeleton
        # Build map for quick lookup by module_id. For screens, map VBA name to Fxxx using BD events notes
        vba_to_f_map = {}
        if category == "screen":
            for mid, ev in bd_events_map.items():
                notes = ev.get("notes")
                if notes:
                    vba_name = notes.split("\n")[0].strip()
                    if vba_name:
                        norm_name = normalize_vba_name(vba_name)
                        vba_to_f_map[norm_name] = mid
                        vba_to_f_map[vba_name] = mid
                        # Handle common suffixes
                        if "_Click" in vba_name:
                            vba_to_f_map[vba_name.replace("_Click", "")] = mid
                        if "_AfterUpdate" in vba_name:
                            vba_to_f_map[vba_name.replace("_AfterUpdate", "")] = mid
                    
        logic_items_map = {}
        for li in logic_items:
            vba_id = li.get("module_id", "")
            f_id = vba_to_f_map.get(normalize_vba_name(vba_id), vba_to_f_map.get(vba_id, vba_id))
            logic_items_map[f_id] = li
        
        logger.info("[DD Service] [DD3] logic_items_map keys: %s", list(logic_items_map.keys()))
        if "F000" in logic_items_map:
            f000_code = logic_items_map["F000"].get("code", "")
            logger.info("[DD Service] [DD3] F000 code snippet (first 100 chars): %s", f000_code[:100].replace("\n", " "))
        agent = DDAgent()
        d3_results: dict[str, dict] = {}
        
        dd3_dir.mkdir(parents=True, exist_ok=True)
        input_file_json = safe_child_path(dd3_dir, screen_name, prefix="input_")
        output_file_json = safe_child_path(dd3_dir, screen_name, prefix="output_")
        
        # ── DD3 cache: clear if force=True ────────────────────────────────
        if force:
            for _f in [input_file_json, output_file_json]:
                if _f.exists():
                    _f.unlink()
                    logger.info("[DD Service] [DD3] Force: cleared cache %s", _f.name)

        # Load existing input entries to avoid duplicates
        existing_input_modules = set()
        existing_inputs = []
        if input_file_json.exists():
            try:
                existing_inputs = json.loads(input_file_json.read_text(encoding="utf-8"))
                for obj in existing_inputs:
                    if "module_id" in obj:
                        existing_input_modules.add(obj["module_id"])
            except Exception:
                existing_inputs = []
        
        # Load cached results from output file
        if output_file_json.exists():
            try:
                cached_results = json.loads(output_file_json.read_text(encoding="utf-8"))
                for obj in cached_results:
                    if "module_id" in obj:
                        d3_results[obj["module_id"]] = obj
            except Exception:
                pass


        failed_modules: list[str] = []
        if skip_llm:
            logger.info("[DD Service] [D3] Skipping LLM as requested.")
        else:
            # For screen category: iterate over D2 skeleton details (BD-event-driven)
            # For macro/common: iterate over logic_items as before
            if category in ["screen", "report", "macro", "common"]:
                # Use skeleton details as the source of truth for all categories
                if category in ("screen", "report"):
                    details = skeleton.get("sheet_3_detail_specs", [])
                else:
                    details = skeleton.get("sheet_2_detail", [])
                iter_items = details if isinstance(details, list) else details.get("details", [])
            else:
                iter_items = logic_items

            d3_lock = threading.Lock()

            def _persist_d3() -> None:
                """Write DD3 inputs/outputs; callers hold d3_lock."""
                input_file_json.write_text(
                    json.dumps(existing_inputs, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                output_results = [{**result, "module_id": mid} for mid, result in d3_results.items()]
                output_file_json.write_text(
                    json.dumps(output_results, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

            def process_module(idx_item):
                idx, item = idx_item
                # Handle both module_id and key_id for diverse module types
                mid = item.get("key_id") or item.get("module_id") or item.get("module_name", "")
                
                # Lookup actual code/logic from logic_items using multiple fallback keys
                li = logic_items_map.get(item.get("module_id"), {}) or \
                     logic_items_map.get(item.get("key_id"), {}) or \
                     logic_items_map.get(item.get("module_name"), {}) or \
                     logic_items_map.get(mid, {})
                code = li.get("code") or item.get("code", "")

                # ── Skip LLM if no real VBA / macro code exists ─────────────
                # Markers that indicate the code slot is a placeholder, not real logic.
                _NO_CODE_MARKERS = (
                    "// Original VBA code not found",
                    "// No VBA Sub",
                    "// This event runs Access macro",
                    "' No logic found",
                    "' Original VBA code not found",
                )

                # Macro is considered empty if it contains only basic headers/structures.
                _macro_xml_is_empty = False
                if category == "macro":
                    macro_raw = item.get("macro_raw") or code
                    _macro_xml_is_empty = (
                        not macro_raw
                        or not macro_raw.strip()
                        or "<Action" not in macro_raw
                    )

                # Also respect explicit flag set by fill_dd_form_report stub builder
                _flagged_no_code = li.get("_no_real_code", False) or item.get("_no_real_code", False)

                _code_is_missing = (
                    not code
                    or not code.strip()
                    or any(code.strip().startswith(m) for m in _NO_CODE_MARKERS)
                    or _macro_xml_is_empty
                    or _flagged_no_code
                )

                # Apply skip for screen, report, common (module), and macro.
                # (Previously only "screen" was covered.)
                _categories_with_skip = ("screen", "report", "common", "macro")
                if _code_is_missing and category in _categories_with_skip:
                    logger.info(
                        "[DD Service] [DD3] Skipping LLM for %s/%s — no real code/macro (placeholder). "
                        "Writing 'なし' placeholder steps.",
                        category, mid,
                    )
                    with d3_lock:
                        if mid not in d3_results:
                            d3_results[mid] = {
                                "module_id": mid,
                                "steps": [
                                    {"step": "1. 初期処理", "detail": "なし"},
                                    {"step": "2. 主処理",   "detail": "なし"},
                                    {"step": "3. 終了処理", "detail": "なし"},
                                ],
                                "event_detail": "",
                                "_skipped": "no_real_code",
                            }
                    return

                # Legacy guard: skip genuinely empty common/module items that have
                # no code AND no macro XML (catches edge cases not covered above).
                if not code and category not in ("screen", "macro", "report"):
                    logger.info("[DD Service] [DD3] Skipping empty module: %s", mid)
                    return

                with d3_lock:
                    if mid in d3_results:
                        logger.info("[DD Service] [DD3] %d/%d module=%s (Cached)", idx + 1, len(iter_items), mid)
                        return

                bd_event = bd_events_map.get(mid, {})
                # For screens/reports, BD events provide high-level context
                if category in ("screen", "report"):
                    bd_event = {
                        **bd_event,
                        "event_trigger": item.get("event_trigger", ""),
                        "event_content": item.get("event_content", ""),
                        "action_type": item.get("action_type", ""),
                    }

                logger.info("[DD Service] [DD3] %d/%d module=%s (Starting parallel)", idx + 1, len(iter_items), mid)

                # Unified merging logic: item (skeleton) + li (extracted logic)
                merged = {**item, **{k: v for k, v in li.items() if v and k not in item}}
                
                # Standard cleaning logic for all categories
                clean_item = {k: v for k, v in merged.items() if v not in [None, "", [], {}] and not k.startswith("_")}
                
                # Optimization: strip large/irrelevant fields before sending to LLM
                _is_report_screen = str(mid).upper().startswith("R") or str(bd_final.get("screen_id", "")).upper().startswith("R")
                strip_keys = ["steps", "action_type", "form_controls", "event_trigger"]
                if not _is_report_screen and category == "screen":
                    strip_keys += ["event_content", "input_data_area", "output_data_area"]
                
                for key in strip_keys:
                    clean_item.pop(key, None)
                
                clean_bd_event = {k: v for k, v in bd_event.items() if v not in [None, "", [], {}]}

                # Prepare tracking item for LLM input - OPTIMIZED
                input_item = {
                    "module_id": mid,
                    "event_id": clean_bd_event.get("event_id", ""),
                    "title": item.get("title", item.get("module_name", "")),
                    "type": clean_bd_event.get("type", ""),
                    "logical_name": clean_bd_event.get("logical_name", ""),
                    "physical_name": clean_bd_event.get("physical_name", ""),
                    "event_trigger": item.get("event_trigger", ""),
                    "notes": clean_bd_event.get("notes", ""),
                    "category": category
                }
                
                # Add S3 event_content (highest priority)
                s3_entry = s3_logic_map.get(mid, {})
                if s3_entry and s3_entry.get("event_content"):
                    input_item["event_content"] = s3_entry["event_content"]
                elif item.get("event_content"):
                    input_item["event_content"] = item["event_content"]
                
                # Add code if available
                if clean_item.get("code"):
                    input_item["code"] = clean_item["code"]
                
                # Add query_mappings from skeleton (SELECT query sheets)
                if item.get("query_mappings"):
                    input_item["query_mappings"] = item["query_mappings"]

                # Also add any VBA-referenced queries from D1 logic item (DoCmd.OpenQuery, DLookup, etc.)
                li_queries = li.get("queries", [])
                if li_queries:
                    existing_qm_names = {qm.get("logic_query_name", "") for qm in input_item.get("query_mappings", [])}
                    extra_queries = []
                    for q in li_queries:
                        # parse_dd_source uses "name" key, query_mapper uses "query_name"
                        q_name = q.get("name") or q.get("query_name", "")
                        if q_name and q_name not in existing_qm_names:
                            entry = {"query_name": q_name}
                            # Include SQL if available (stored as sql_logic or raw_sql)
                            sql = q.get("sql_logic") or q.get("raw_sql") or q.get("sql")
                            if sql:
                                entry["sql"] = sql
                            extra_queries.append(entry)
                    if extra_queries:
                        input_item["vba_queries"] = extra_queries

                # Add references + commands from D1 for LLM context
                li_refs = li.get("references", {})
                li_commands = li.get("commands", [])
                refs_block = {}
                if li_refs:
                    refs_block.update({k: v for k, v in li_refs.items() if v})
                if li_commands:
                    refs_block["commands"] = li_commands
                if refs_block:
                    input_item["references"] = refs_block

                # Hint: queries in query_mappings but NOT explicitly in code → initialization (step 1)
                code_body = clean_item.get("code", "")
                init_queries = []
                for qm in input_item.get("query_mappings", []):
                    qname = qm.get("logic_query_name", "")
                    if qname and qname not in code_body:
                        init_queries.append(qm.get("sheet_name", qname))
                for vq in input_item.get("vba_queries", []):
                    qname = vq.get("query_name", "")
                    if qname and qname not in code_body:
                        init_queries.append(qname)
                if init_queries:
                    input_item["_hint"] = (
                        f"クエリ {init_queries} はコード内に直接記述がないため、"
                        "初期化処理（ステップ1）として扱うこと。"
                    )

                if clean_item.get("output_data_area"):
                    def _is_empty(v):
                        return v in (None, [], {}) or (isinstance(v, str) and not v.strip())
                    cleaned_oda = []
                    for it in clean_item["output_data_area"]:
                        row = {k: v for k, v in it.items() if not _is_empty(v)}
                        cleaned_oda.append(row)
                    input_item["output_data_area"] = cleaned_oda


                # Save input tracking payload
                with d3_lock:
                    if mid not in existing_input_modules:
                        existing_inputs.append(input_item)
                        existing_input_modules.add(mid)

                # Inject enriched context into clean_item so the LLM prompt actually sees it
                if input_item.get("vba_queries"):
                    clean_item["vba_queries"] = input_item["vba_queries"]
                if input_item.get("references"):
                    clean_item["references"] = input_item["references"]
                if input_item.get("_hint"):
                    clean_item["_hint"] = input_item["_hint"]

                # Call LLM Agent (a failing module must not discard the others' paid-for results)
                try:
                    result = agent.run(
                        logic_item=clean_item,
                        bd_event=clean_bd_event,
                        dd_schema_template=dd_schema_template,
                        category=category,
                        model_id=model_id,
                        stage=self._stage or None,
                        complexity_level=complexity,
                    )
                except Exception as exc:
                    logger.error("[DD Service] [DD3] module=%s failed: %s", mid, exc)
                    with d3_lock:
                        failed_modules.append(mid)
                    return

                # Save results to JSON array (persisted after every module)
                with d3_lock:
                    d3_results[mid] = result
                    _persist_d3()
                    logger.info("[DD Service] [DD3] %d/%d module=%s (Parallel Done)", idx + 1, len(iter_items), mid)

            max_workers = 5
            logger.info("[DD Service] [DD3] Starting parallel processing with %d workers...", max_workers)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                list(executor.map(process_module, enumerate(iter_items)))
            
            # Save all inputs and outputs to JSON files (not JSONL)
            with d3_lock:
                _persist_d3()
            logger.info("[DD Service] [DD3] Saved input JSON: %s", input_file_json)
            logger.info("[DD Service] [DD3] Saved output JSON: %s", output_file_json)
            if failed_modules:
                logger.warning("[DD Service] [DD3] %d module(s) failed: %s", len(failed_modules), failed_modules)




        logger.info("[DD Service] [DD3] Done — %d modules processed.", len(d3_results))

        # ── D4: Merge D1+D2 skeleton with D3 steps ────────────────────────
        logger.info("[DD Service] [DD4] Merging into final output ...")
        final = copy.deepcopy(skeleton)

        if category in ("screen", "report"):
            sheet_3 = final.get("sheet_3_detail_specs", [])
            if isinstance(sheet_3, list):
                details = sheet_3
            elif isinstance(sheet_3, dict):
                details = sheet_3.get("details", [])
            else:
                details = []
        elif category == "common":
            sheet_2 = final.get("sheet_2_detail", [])
            if isinstance(sheet_2, list):
                details = sheet_2
            elif isinstance(sheet_2, dict):
                details = sheet_2.get("details", [])
            else:
                details = []

        elif category == "macro":
            sheet_2 = final.get("sheet_2_detail", [])
            if isinstance(sheet_2, list):
                details = sheet_2
            elif isinstance(sheet_2, dict):
                details = sheet_2.get("details", [])
            else:
                details = []
        else:
            details = final.get("sheet_2_overview", {}).get("details", [])


        for detail in details:
            mid = detail.get("module_id") or detail.get("report_scope_name", "")
            if category in ["macro", "common"]:
                mid = detail.get("key_id")
            if mid in d3_results:
                d3 = d3_results[mid]
                # Inject LLM-generated steps
                if d3.get("steps"):
                    detail["steps"] = d3["steps"]
            # Remove private helper keys (not for final output)
            for pk in ["_screen_edit_items", "_record_sources"]:
                detail.pop(pk, None)
            
            # Preserve query_mappings from skeleton if present
            # (orig_detail comes from final copy of skeleton)
            # Preserve event_content from BD if present, otherwise use LLM summary
            if "event_content" in detail:
                orig_content = detail.get("event_content", "")
                if mid in d3_results:
                    d3 = d3_results[mid]
                    if d3.get("event_detail"):
                        # Preserve any query call block from the skeleton
                        q_call_block = ""
                        if "【クエリ呼び出し】" in orig_content:
                            q_call_block = "\n\n【クエリ呼び出し】" + orig_content.split("【クエリ呼び出し】")[-1]
                        
                        # Strictly preserve BD content if it's not absolutely empty
                        if not orig_content or orig_content.strip() == "":
                            detail["event_content"] = d3["event_detail"] + q_call_block
                        else:
                            # User wants BD content. We keep it as is.
                            detail["event_content"] = orig_content
                    else:
                        detail["event_content"] = orig_content
                else:
                    detail["event_content"] = orig_content

        # For report, merge all details into a single item in the final JSON structure
        if category == "screen":
            is_report = (
                bd_final.get("type") == "report"
                or final.get("category") == "report"
                or screen_name.upper().startswith("R")
            )
            if is_report and details:
                combined_steps = []
                for item in details:
                    mod_id = item.get("module_id", "")
                    stps = item.get("steps", [])
                    if mod_id and len(details) > 1:
                        combined_steps.append({"step": f"■ {mod_id}", "detail": ""})
                    combined_steps.extend(stps)

                merged_detail = dict(details[0])
                merged_detail["steps"] = combined_steps
                merged_detail["module_id"] = screen_name

                # Propagate event_content → sheet_2_overview.special_notes for reports
                event_content_val = merged_detail.get("event_content", "")
                if event_content_val and isinstance(final.get("sheet_2_overview"), dict):
                    final["sheet_2_overview"]["special_notes"] = event_content_val

                # Remove output_data_area from final detail (same as forms)
                merged_detail.pop("output_data_area", None)


                if "sheet_3_detail_specs" in final:
                    s3 = final["sheet_3_detail_specs"]
                    if isinstance(s3, list):
                        # list of detail dicts — replace entire list
                        final["sheet_3_detail_specs"] = [merged_detail]
                    elif isinstance(s3, dict):
                        s3["details"] = [merged_detail]
        # Save DD4
        # ── Inject type + name into final so push_dd_one() reads correct type ──
        _CAT_TO_TYPE_SAVE = {"macro": "macro", "common": "module", "report": "report"}
        if category in _CAT_TO_TYPE_SAVE:
            _item_type = _CAT_TO_TYPE_SAVE[category]
        else:
            # screen: lookup L1 to distinguish form vs report
            try:
                from db.layer1_repo import Layer1Repo
                from config import L1_COLLECTION_REPORTS
                _repo = Layer1Repo()
                _item_type = "report" if _repo._find_one(L1_COLLECTION_REPORTS, screen_name) else "form"
            except Exception:
                _item_type = "report" if screen_name.upper().startswith("R") else "form"
        final["type"] = _item_type
        final["name"] = screen_name

        dd4_dir.mkdir(parents=True, exist_ok=True)
        dd4_file = safe_child_path(dd4_dir, screen_name)
        final_str = json.dumps(final, ensure_ascii=False, indent=2)
        dd4_file.write_text(
            final_str, encoding="utf-8"
        )
        logger.info("[DD Service] [DD4] Final saved: %s (type=%s)", dd4_file, _item_type)

        # ── Auto Push to MongoDB + Backup (macro / common only) ───────────
        # screen/report are pushed via main.py → push_to_mongo.push_dd() after
        # the full pipeline finishes. For standalone macro/module runs (which
        # bypass main.py), we push immediately after DD4 so the DB stays in sync.
        if category in ("macro", "common"):
            self._push_dd4_to_mongo(screen_name, final, dd4_file, category=category)

        return {
            "screen_name": screen_name,
            "dd1_source_file": str(dd1_file),
            "dd2_mapping_file": str(dd2_file),
            "dd3_input_json": str(input_file_json),
            "dd3_output_json": str(output_file_json),
            "dd4_final_file": str(dd4_file),
            "logic_items_total": len(logic_items),
            "dd3_modules_processed": len(d3_results),
            "auto_pushed": category in ("macro", "common"),
            "dd3_failed_modules": failed_modules,
        }
