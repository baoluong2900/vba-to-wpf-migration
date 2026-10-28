"""
agents/report/agent_report.py — Agent Report: Coordinate WPF Report UserControl and ViewModel generation
"""
from __future__ import annotations

import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from core.models import BaseAgent, AgentInput, AgentOutput, GeneratedFile
from core.config import MONGO_URI, MONGO_DB, AVAILABLE_MODELS
from core.naming import validate_form_name

# Import tool_report functions
import tool_report as tr

logger = logging.getLogger(__name__)


class ReportAgent(BaseAgent):
    """
    Agent Report — Coordinates the generation of a pixel-perfect WPF UserControl representing the report 
    and its ViewModel using a fully deterministic Twips-to-Pixels absolute canvas generator.
    """

    @property
    def name(self) -> str:
        return "report"

    async def run(self, input: AgentInput) -> AgentOutput:
        form_name = input.form_name

        logger.info("[Agent Report] Starting deterministic pixel-perfect pipeline for report form: %s", form_name)

        try:
            validate_form_name(form_name)

            # ── Step 1: Load data sources via tool_report ─────────────────
            dd_json = input.dd_json or tr.load_dd_json(form_name, MONGO_URI, MONGO_DB)
            bd_json = input.bd_json or tr.load_bd_json(form_name, MONGO_URI, MONGO_DB)
            # mongodb_data carries the forms document under "form" (same convention as Agent Service)
            mongodb_data = input.mongodb_data or {}
            mongo_form = mongodb_data.get("form") or (mongodb_data if "items" in mongodb_data else None) \
                or tr.load_mongo_form(form_name, MONGO_URI, MONGO_DB)

            # Extract details
            bd_items = bd_json.get("items")
            if not bd_items and "sheet_3_screen_edit" in bd_json:
                bd_items = bd_json["sheet_3_screen_edit"].get("items", [])

            mongo_items = mongo_form.get("items", [])
            mongo_props = mongo_form.get("properties", {})
            mongo_procedures = mongo_form.get("functions", mongo_form.get("vba_procedures", []))

            dd_specs = dd_json.get("sheet_3_detail_specs", [])
            dd_queries = dd_json.get("sheet_4_sel_query_templates", [])

            logger.info("[Agent Report] Data loaded: BD items=%d, Mongo items=%d, DD specs=%d, DD queries=%d, Mongo procedures=%d",
                        len(bd_items or []), len(mongo_items), len(dd_specs), len(dd_queries), len(mongo_procedures))

            # Save input snapshot for debugging
            tr.save_input_snapshot(form_name, {
                "form_name": form_name,
                "bd_items": bd_items,
                "mongo_items": mongo_items,
                "mongo_properties": mongo_props,
                "mongo_procedures": mongo_procedures,
                "dd_specs": dd_specs,
                "dd_queries": dd_queries
            })

            # ── Step 2: Deterministic UserControl & ViewModel Generation ──
            # Routed on the Layer 1 document type (forms.type "Reports"), not the "R" name prefix
            if tr.is_report_document(form_name, mongo_form, dd_json):
                logger.info("[Agent Report] Identified as REPORT. Generating Microsoft RDLC static layout...")

                # ── LLM translation of Japanese control names ───────────────────
                try:
                    import re
                    import json
                    from llm.llm_client import L5LLMClient, extract_code_block

                    # Load name config
                    name_map = tr.load_name_config()
                    raw_config = tr.load_raw_config()
                    control_map = raw_config.setdefault("control_name", {})

                    # Extract all control names from mongo_items (except sections)
                    candidates = set()
                    for item in mongo_items:
                        itype = item.get("type", "")
                        if itype == "section":
                            continue
                        name = item.get("name")
                        if name:
                            # Candidate if it contains Japanese/non-ASCII characters
                            if re.search(r'[^a-zA-Z0-9_]', name):
                                # Skip standard Access auto-generated patterns
                                if not re.match(r'^(テキスト|ラベル|直線|フレーム|チェック|コマンド)(\d+)$', name):
                                    candidates.add(name)

                    # Update raw config with missing candidates as "TODO" and clean standard ones
                    updated_config = False
                    
                    # Clean up existing auto-generated names from control_map
                    to_remove = [k for k in control_map if re.match(r'^(テキスト|ラベル|直線|フレーム|チェック|コマンド)(\d+)$', k)]
                    if to_remove:
                        for k in to_remove:
                            del control_map[k]
                        updated_config = True

                    for cand in candidates:
                        # Check both the flattened map and the specific raw category
                        if cand not in name_map or control_map.get(cand) in [None, "TODO"] or (isinstance(control_map.get(cand), str) and control_map.get(cand).startswith("TODO_")):
                            if cand not in control_map or control_map[cand] == "TODO":
                                control_map[cand] = "TODO"
                                updated_config = True

                    if updated_config:
                        tr.save_raw_config(raw_config)

                    # Gather todos for control_name
                    todos_to_translate = {
                        k: v for k, v in control_map.items()
                        if k in candidates and (v == "TODO" or (isinstance(v, str) and v.startswith("TODO_")))
                    }

                    if todos_to_translate:
                        logger.info("[Agent Report] Found 'TODO' control names in config. Translating via LLM...")
                        llm = L5LLMClient()
                        
                        prompt_path = Path(__file__).parent.parent / "repo" / "prompts" / "agent_translate.md"
                        if prompt_path.exists():
                            system_prompt = prompt_path.read_text(encoding="utf-8")
                        else:
                            system_prompt = "You are an expert translator. Translate Japanese report control names to English PascalCase with a clean suffix like Label or Textbox."

                        user_prompt = f"Translate the following JSON object containing 'TODO' values:\n```json\n{json.dumps({'control_name': todos_to_translate}, ensure_ascii=False, indent=2)}\n```"
                        
                        # Set up model override if available
                        model_override = input.model_override
                        if isinstance(model_override, str):
                            from core.config import AVAILABLE_MODELS
                            model_override = AVAILABLE_MODELS.get(model_override)

                        raw_response = llm.generate_code(
                            task_type="translate_config",
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            model=model_override,
                        )
                        json_raw = extract_code_block(raw_response, language="json")
                        translated = json.loads(json_raw)

                        updated_count = 0
                        if "control_name" in translated:
                            for k, v in translated["control_name"].items():
                                if v and v != "TODO" and not v.startswith("TODO_"):
                                    control_map[k] = v
                                    updated_count += 1

                        if updated_count > 0:
                            tr.save_raw_config(raw_config)
                            logger.info("[Agent Report] Successfully translated %d control names and updated config.", updated_count)
                except Exception as translation_err:
                    logger.error("[Agent Report] ⚠️ Translation of control names failed, continuing with available config. Error: %s", translation_err, exc_info=True)

                english_form_name = tr.get_english_report_name(form_name)
                rdlc_code = tr.generate_report_rdlc(form_name, mongo_items)
                generated_files = [
                    GeneratedFile(
                        path=f"Views/Reports/{english_form_name}Report.rdlc",
                        content=rdlc_code,
                        generator="rdlc",
                        agent="report"
                    )
                ]
            else:
                logger.info("[Agent Report] Identified as FORM. Patching existing WPF View & ViewModel...")
                mongo_procedures = mongo_form.get("functions", mongo_form.get("vba_procedures", []))
                generated_files = tr.patch_existing_ui(form_name, mongo_procedures)

            # ── Step 3: Save snapshot & WPF source via tool_report ──
            tr.save_outputs(form_name, generated_files)

            output = AgentOutput(
                agent="report",
                form_name=form_name,
                files=generated_files,
                status="success",
                metadata={
                    "files_count": len(generated_files),
                    "generated_paths": [f.path for f in generated_files]
                }
            )
            logger.info("[Agent Report] ✅ Successfully generated %d files for report form: %s",
                        len(generated_files), form_name)
            return output

        except Exception as e:
            logger.error("[Agent Report] ❌ Failed for %s: %s", form_name, e, exc_info=True)
            return AgentOutput(
                agent="report",
                form_name=form_name,
                status="error",
                error=str(e),
            )


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────
async def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Agent Report CLI")
    parser.add_argument("form_name", help="Name of report form (e.g. AM依頼_印刷_PDF)")
    parser.add_argument("--model", default=None, help="Model override support")
    args = parser.parse_args()

    model_override = AVAILABLE_MODELS.get(args.model) if args.model else None

    agent = ReportAgent()
    result = await agent.run(AgentInput(form_name=args.form_name, model_override=model_override))

    if result.status == "success":
        print(f"\n✅ Successfully generated {len(result.files)} files:")
        for f in result.files:
            print(f"   → {f.path} ({f.generator})")
    else:
        print(f"\n❌ Error: {result.error}")
        raise SystemExit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
