
"""
agents/repo/agent_repo.py — Agent Repo: Gen Entity + DTO + Interface + Repository using tool_repo
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from core.models import BaseAgent, AgentInput, AgentOutput, GeneratedFile
from core.config import MONGO_URI, MONGO_DB, L5_ROUTING, AVAILABLE_MODELS
from llm.llm_client import L5LLMClient, extract_code_block

# Import tool_repo functions
import tool_repo as tr
import fill_json

logger = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).parent
INPUTS_DIR = AGENT_DIR / "inputs"
OUTPUTS_DIR = AGENT_DIR / "outputs"


class RepoAgent(BaseAgent):
    """
    Agent Repo — Gen Entity + DTO + Interface + Repository using tool_repo logic.
    """

    @property
    def name(self) -> str:
        return "repo"

    async def run(self, input: AgentInput) -> AgentOutput:
        form_name = input.form_name
        
        # ── Setup LLM config based on override ──────────────────────────
        model_override = input.model_override
        if isinstance(model_override, str):
            model_override = AVAILABLE_MODELS.get(model_override)
            
        logger.info("[Agent Repo] Starting for form: %s using tool_repo (model: %s)", 
                    form_name, getattr(model_override, 'model_id', 'default'))

        try:
            # ── Step 1: Load data ────────────────────────
            dd_json = input.dd_json or self._load_dd_json(form_name)
            bd_json = input.bd_json or self._load_bd_json(form_name)
            tables_schemas_mongo = self._load_table_schemas_mongo()

            dd_queries = tr.extract_valid_queries(dd_json)

            config = tr.load_config()

            param_map = tr.extract_parameters(dd_json, dd_queries)
            vba_args_raw = [f"{k}: {v}" for k, v in param_map.items()]
            parsed_args = tr.parse_vba_args(vba_args_raw, config)
            
            tr.register_query_columns(dd_queries, config)

            # ── Phase 2: Translate "TODO" values via LLM ─────────────────────
            def is_todo(v: Any) -> bool:
                return isinstance(v, str) and (v == "TODO" or v.startswith("TODO_"))

            todos = {
                "table_name": {k: "TODO" for k, v in config.get("table_name", {}).items() if is_todo(v)},
                "field_name": {k: "TODO" for k, v in config.get("field_name", {}).items() if is_todo(v)},
                "parameter_name": {k: "TODO" for k, v in config.get("parameter_name", {}).items() if is_todo(v)},
                "function_name": {k: "TODO" for k, v in config.get("function_name", {}).items() if is_todo(v)},
                "cte_name": {k: "TODO" for k, v in config.get("cte_name", {}).items() if is_todo(v)}
            }
            has_todo = any(todos.values())
            if has_todo:
                logger.info("[Agent Repo] Phase 2: Found 'TODO' values in config. Translating via LLM...")
                try:
                    llm = L5LLMClient()
                    system_prompt = self.load_prompt("agent_translate.md")
                    user_prompt = f"Translate the following JSON object containing 'TODO' values:\n```json\n{json.dumps(todos, ensure_ascii=False, indent=2)}\n```"
                    
                    raw_response = llm.generate_code(
                        task_type="translate_config",
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model=model_override,
                    )
                    json_raw = extract_code_block(raw_response, language="json")
                    translated = json.loads(json_raw)
                    
                    updated_count = 0
                    for cat in ["table_name", "field_name", "parameter_name", "function_name", "cte_name"]:
                        if cat in translated:
                            for k, v in translated[cat].items():
                                if v and v != "TODO":
                                    config.setdefault(cat, {})[k] = v
                                    updated_count += 1
                    
                    if updated_count > 0:
                        tr.save_config(config)
                        logger.info(f"[Agent Repo] Phase 2: Successfully translated {updated_count} keys and updated config.")
                        # Re-evaluate parsed_args with newly updated config
                        parsed_args = tr.parse_vba_args(vba_args_raw, config)
                except Exception as translation_err:
                    logger.error("[Agent Repo] Phase 2 ⚠️: Failed during translation but continuing with available config. Error: %s", translation_err, exc_info=True)

            # ── Dependency analysis ────────────────────────
            table_queries, query_map, deps_map = tr.build_dependency_graph(dd_queries, config)

            generated_files: list[GeneratedFile] = []

            # Combine local table_schemas from dd_json and tables_schemas_mongo
            table_schemas = dd_json.get("table_schemas", [])
            schema_map = {}

            for s in table_schemas:
                tname = s.get("table_name", "")
                if tname:
                    schema_map[tname] = tr.unify_schema_fields(s)
            
            # fallback to mongo
            for k, v in tables_schemas_mongo.items():
                if k not in schema_map:
                    schema_map[k] = tr.unify_schema_fields(v)

            # ── Step 4: Generate files per table ────────────────
            for table_name, queries in table_queries.items():
                schema = schema_map.get(table_name)
                if not schema:
                    for k, v in schema_map.items():
                        if k in table_name or table_name in k:
                            schema = v
                            break
                
                # Fallback: robust dynamic MongoDB query for specific table
                if not schema or not schema.get("fields"):
                    mongo_doc = self._load_single_table_schema_mongo(table_name)
                    if mongo_doc:
                        schema = tr.unify_schema_fields(mongo_doc)
                        schema_map[table_name] = schema  # Cache for future use
                        logger.info("[Agent Repo] Dynamically resolved schema for table: %s", table_name)
                            
                table_files = tr.generate_files_for_table(
                    table_name, queries, schema, query_map, deps_map, parsed_args, config, dd_json
                )
                
                for f in table_files:
                    generated_files.append(GeneratedFile(
                        path=f["path"],
                        content=f["content"],
                        generator="tool_repo",
                        agent="repo",
                    ))


            # Save final config back
            tr.save_config(config)

            # ── Step 6: Save snapshots ───────────────────────────
            self._save_outputs(form_name, generated_files)
            
            # ── Step 7: Generate and save repository reference JSON ──────────
            try:
                fill_json.generate_reference_json(form_name)
            except Exception as e:
                logger.warning("[Agent Repo] Failed to generate repository reference JSON: %s", e)

            output = AgentOutput(
                agent="repo",
                form_name=form_name,
                files=generated_files,
                status="success",
                metadata={
                    "tables": list(table_queries.keys()),
                    "files_count": len(generated_files),
                },
            )
            logger.info(
                "[Agent Repo] ✅ Generated %d files for %s (tables: %s)",
                len(generated_files), form_name, ", ".join(table_queries.keys()),
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

            return output

        except Exception as e:
            logger.error("[Agent Repo] ❌ Failed for %s: %s", form_name, e, exc_info=True)
            return AgentOutput(
                agent="repo",
                form_name=form_name,
                status="error",
                error=str(e),
            )

    # ──────────────────────────────────────────
    # Data Loaders
    # ──────────────────────────────────────────

    def _load_dd_json(self, form_name: str) -> dict:
        """Load DD JSON from MongoDB 'dds' collection."""
        try:
            from pymongo import MongoClient
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DB]
            doc = db["dds"].find_one({"$or": [{"form_name": form_name}, {"screen_name": form_name}]}, {"_id": 0})
            client.close()
            if doc:
                return doc
        except Exception as e:
            logger.warning("[Agent Repo] MongoDB load_dd_json failed for %s: %s", form_name, e)
            
        # Fallback fallback to local inputs dir if Mongo is unavailable or document missing
        alt = INPUTS_DIR / f"{form_name}.json"
        if alt.exists():
            return json.loads(alt.read_text(encoding="utf-8"))
        alt2 = INPUTS_DIR / f"{form_name}_dd.json"
        if alt2.exists():
            return json.loads(alt2.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"DD JSON for '{form_name}' not found in MongoDB or local inputs folder.")

    def _load_bd_json(self, form_name: str) -> dict:
        """Load BD JSON from MongoDB 'bds' collection."""
        try:
            from pymongo import MongoClient
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DB]
            doc = db["bds"].find_one({"$or": [{"form_name": form_name}, {"screen_name": form_name}]}, {"_id": 0})
            client.close()
            if doc:
                return doc
        except Exception as e:
            logger.warning("[Agent Repo] MongoDB load_bd_json failed for %s: %s", form_name, e)
            
        alt = INPUTS_DIR / f"{form_name}_bd.json"
        if alt.exists():
            return json.loads(alt.read_text(encoding="utf-8"))
        return {}

    def _load_table_schemas_mongo(self) -> dict[str, dict]:
        """Load table schemas from MongoDB."""
        try:
            from pymongo import MongoClient
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DB]
            tables = {}
            for doc in db["tables"].find():
                name = doc.get("name", doc.get("table_name", ""))
                if name:
                    tables[name] = doc
            client.close()
            return tables
        except Exception as e:
            logger.warning("[Agent Repo] MongoDB tables load failed: %s. Proceeding with query inference.", e)
            return {}

    def _load_single_table_schema_mongo(self, table_name: str) -> dict | None:
        """Load a specific table schema from MongoDB with robust matching (exact + NFKC)."""
        try:
            from pymongo import MongoClient
            import unicodedata
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DB]
            
            # 1. Try exact match by 'name'
            doc = db["tables"].find_one({"name": table_name}, {"_id": 0})
            if doc:
                client.close()
                return doc
            
            # 2. Try by 'table_name' field
            doc = db["tables"].find_one({"table_name": table_name}, {"_id": 0})
            if doc:
                client.close()
                return doc
                
            # 3. Fallback: Robust Fullwidth/Halfwidth NFKC matching
            norm_input = unicodedata.normalize('NFKC', table_name)
            all_tables = db["tables"].find({}, {"name": 1, "table_name": 1, "_id": 0})
            actual_name = None
            for item in all_tables:
                cand = item.get("name") or item.get("table_name", "")
                if cand and unicodedata.normalize('NFKC', cand) == norm_input:
                    actual_name = cand
                    break
            
            if actual_name:
                doc = db["tables"].find_one({"$or": [{"name": actual_name}, {"table_name": actual_name}]}, {"_id": 0})
                client.close()
                return doc
                
            client.close()
            return None
        except Exception as e:
            logger.warning("[Agent Repo] Single MongoDB table fetch failed for %s: %s", table_name, e)
            return None


    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _form_to_clean_name(form_name: str) -> str:
        """F_Login → Login, C000_MAINⅡ → C000Main"""
        name = form_name
        if name.startswith("F_"):
            name = name[2:]
        # Remove Japanese
        name = re.sub(r"[^\w]", "", name)
        return name

    def _save_outputs(self, form_name: str, files: list[GeneratedFile]) -> None:
        """Save output snapshots for review and write into actual source code directories."""
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Robust logic to find source or src/wpf directories dynamically
        curr = Path(__file__).resolve().parent
        source_root = None
        for _ in range(10):
            cand_source = curr / "source"
            cand_wpf = curr / "src" / "wpf"
            if cand_wpf.exists():
                source_root = cand_wpf
                break
            elif cand_source.exists():
                source_root = cand_source
                break
            if curr.parent == curr:
                break
            curr = curr.parent
            
        if not source_root:
            # Fallback path dynamically mapped relative to workspace root
            _LAYER5_DIR = Path(__file__).resolve().parent.parent.parent
            source_root = _LAYER5_DIR.parent.parent / "src" / "wpf"

        # Aggregate generated files by path to prevent overwriting within the same run
        merged_files = {} # path -> content
        for gf in files:
            path = gf.path
            if path in merged_files:
                if Path(path).suffix == ".cs":
                    merged_files[path] = tr.merge_csharp_code(merged_files[path], gf.content)
                elif Path(path).suffix == ".json":
                    merged_files[path] = tr.merge_repository_json(merged_files[path], gf.content)
                else:
                    merged_files[path] = gf.content
            else:
                merged_files[path] = gf.content

        for path, content in merged_files.items():
            # 1. Snapshot save (flatly)
            filename = Path(path).name
            if Path(path).suffix == ".json":
                out = OUTPUTS_DIR / "repo" / filename
            else:
                out = OUTPUTS_DIR / form_name / filename
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                if out.suffix == ".cs":
                    existing = out.read_text(encoding="utf-8")
                    content_to_write = tr.merge_csharp_code(existing, content)
                elif out.suffix == ".json":
                    existing = out.read_text(encoding="utf-8")
                    content_to_write = tr.merge_repository_json(existing, content)
                else:
                    content_to_write = content
            else:
                content_to_write = content
            out.write_text(content_to_write, encoding="utf-8")
            
            # 2. Source code generation save (hierarchical)
            if source_root.exists():
                path_parts = Path(path).parts
                if len(path_parts) > 1:
                    layer = path_parts[0]  # e.g., 'Domain' or 'Infrastructure'
                    rest = path_parts[1:]
                    mapped_layer = f"vba_brain.{layer}"
                    dest_path = source_root / mapped_layer / Path(*rest)
                    try:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        if dest_path.exists():
                            if dest_path.suffix == ".cs":
                                existing_source = dest_path.read_text(encoding="utf-8")
                                content_for_source = tr.merge_csharp_code(existing_source, content)
                            elif dest_path.suffix == ".json":
                                existing_source = dest_path.read_text(encoding="utf-8")
                                content_for_source = tr.merge_repository_json(existing_source, content)
                            else:
                                content_for_source = content
                        else:
                            content_for_source = content
                        dest_path.write_text(content_for_source, encoding="utf-8")
                    except Exception as e:
                        logger.warning("[Agent Repo] Failed to save to source %s: %s", dest_path, e)

        # 3. Post-generation Cleanup Phase
        cleanup_legacy_todo_files(source_root, form_name, merged_files)


def cleanup_legacy_todo_files(source_root: Path, form_name: str, merged_files: dict):
    """
    Scans for legacy TODO_ DTO or Entity files that share the exact same schema
    ([Column] set or property types set) as any newly generated DTO/Entity in the same directory, and removes them.
    """
    generated_schemas = {}
    
    def get_schema_signature(content: str) -> frozenset:
        # Try to get [Column] attributes first
        cols = re.findall(r'\[Column\("([^"]+)"\)\]', content)
        if cols:
            return frozenset(cols)
        # If no Columns, extract property types to build a structural signature
        props = re.findall(r'public\s+([^\s]+)\s+([^\s\{\}]+)\s*\{\s*get;\s*set;\s*\}', content)
        sig = [p[0] for p in props]
        if sig:
            return frozenset([("props_sig", len(sig), tuple(sorted(sig)))])
        return frozenset()

    # Extract schema sets from newly merged file contents
    for path, content in merged_files.items():
        if "DTOs" not in path and "Entities" not in path:
            continue
            
        col_set = get_schema_signature(content)
        if not col_set:
            continue
            
        if source_root and source_root.exists():
            path_parts = Path(path).parts
            if len(path_parts) > 1:
                layer = path_parts[0]
                rest = path_parts[1:-1] # target parent directory
                mapped_layer = f"vba_brain.{layer}"
                dest_dir = source_root / mapped_layer / Path(*rest)
                
                if dest_dir not in generated_schemas:
                    generated_schemas[dest_dir] = []
                generated_schemas[dest_dir].append(col_set)

    # Process each active directory to remove legacy TODO files
    for dest_dir, clean_schemas in generated_schemas.items():
        if not dest_dir.exists():
            continue
            
        for existing_file in dest_dir.glob("TODO_*.cs"):
            try:
                todo_content = existing_file.read_text(encoding="utf-8")
                todo_cols = get_schema_signature(todo_content)
                if todo_cols and todo_cols in clean_schemas:
                    logger.info("[Agent Repo] 🧹 Deleting redundant legacy TODO file: %s", existing_file.name)
                    existing_file.unlink(missing_ok=True)
            except Exception as e:
                logger.warning("[Agent Repo] Failed to check/delete legacy TODO file %s: %s", existing_file, e)

    # Also clean up snapshot outputs folder
    snapshot_dir = OUTPUTS_DIR / form_name
    if snapshot_dir.exists():
        snapshot_schemas = []
        for f in snapshot_dir.glob("*.cs"):
            if not f.name.startswith("TODO_"):
                try:
                    c = f.read_text(encoding="utf-8")
                    cols = get_schema_signature(c)
                    if cols:
                        snapshot_schemas.append(cols)
                except Exception:
                    pass
                    
        for todo_f in snapshot_dir.glob("TODO_*.cs"):
            try:
                todo_c = todo_f.read_text(encoding="utf-8")
                todo_cols = get_schema_signature(todo_c)
                if todo_cols and todo_cols in snapshot_schemas:
                    logger.info("[Agent Repo] 🧹 Deleting snapshot legacy TODO file: %s", todo_f.name)
                    todo_f.unlink(missing_ok=True)
            except Exception:
                pass


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────
async def main():
    import argparse
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Agent Repo — Gen Entity + DTO + Repository using tool_repo")
    parser.add_argument("form_name", help="Form name (e.g., F_Login)")
    parser.add_argument("--model", default=None, help="Unused, legacy override support")
    args = parser.parse_args()

    model_override = AVAILABLE_MODELS.get(args.model) if args.model else None

    agent = RepoAgent()
    result = await agent.run(AgentInput(form_name=args.form_name, model_override=model_override))

    if result.status == "success":
        print(f"\n✅ Generated {len(result.files)} files:")
        for f in result.files:
            print(f"   → {f.path} ({f.generator})")
    else:
        print(f"\n❌ Error: {result.error}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())