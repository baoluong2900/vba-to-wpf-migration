"""
agents/mapping/agent_mapping.py — Agent Mapping: Gen Common Forms/Queries/Macros/Events Mappings
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Insert layer5 root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from core.models import BaseAgent, AgentInput, AgentOutput, GeneratedFile
from core.config import COL_MODULES, DOMAIN_PROJECT_DIR, SERVICES_DIR, WORKFLOW_DIR
from core.naming import cs_identifier, validate_form_name

logger = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).parent
OUTPUTS_DIR = AGENT_DIR / "outputs"
GRAPHVIEW_OUTPUTS_DIR = AGENT_DIR.parent / "graphview" / "outputs"
DOCS_MAPPINGS_DIR = WORKFLOW_DIR / "docs" / "mappings"


def _mapped_type_name(relative_path: str, name_key: str, access_name: str) -> str:
    """Suggested .NET type for an Access macro/module from graphview outputs (old and new key names)."""
    path = GRAPHVIEW_OUTPUTS_DIR / relative_path
    if not path.exists():
        return ""
    try:
        items = json.loads(path.read_text(encoding="utf-8")).get("items", [])
    except (OSError, ValueError) as ex:
        logger.warning("[Agent Mapping] Error parsing %s: %s", path.name, ex)
        return ""
    for item in items:
        if item.get(name_key) == access_name:
            mapped = (item.get("suggested_dotnet_type_name") or item.get("wpf_service_ui_name")
                      or item.get("wpf_common_name") or "")
            return cs_identifier(mapped, fallback="") if mapped else ""
    return ""


def _fallback_type_name(access_name: str, suffix: str) -> str:
    """Class name from the Access name; a short hash keeps names unique when characters had to be dropped."""
    ident = cs_identifier(access_name, fallback="Generic")
    if ident != access_name:
        ident += "_" + hashlib.sha1(access_name.encode("utf-8")).hexdigest()[:6]
    return ident + suffix


def _relpath(path: Path) -> str:
    return os.path.relpath(path, WORKFLOW_DIR)


class MappingAgent(BaseAgent):
    """
    Agent Mapping — Gen Common Forms/Queries/Macros/Events Mappings
    """

    @property
    def name(self) -> str:
        return "mapping"

    async def run(self, input: AgentInput) -> AgentOutput:
        form_name = input.form_name or "ALL"
        logger.info(f"[Agent Mapping] Starting mapping execution for target: {form_name}")

        try:
            if form_name != "ALL":
                validate_form_name(form_name)
            docs_mappings_dir = DOCS_MAPPINGS_DIR
            docs_mappings_dir.mkdir(parents=True, exist_ok=True)
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

            generated_files: list[GeneratedFile] = []

            if form_name == "ALL":
                # ── Step 1: Execute export_forms_layer1.py via subprocess ──────
                script_path = AGENT_DIR.parent / "graphview" / "inputs" / "export_forms_layer1.py"
                if not script_path.exists():
                    raise FileNotFoundError(f"Export script not found: {script_path}")

                cmd = [sys.executable, "-X", "utf8", str(script_path)]
                logger.info("[Agent Mapping] Running: %s", " ".join(cmd))
                
                res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
                if res.returncode != 0:
                    raise RuntimeError(f"export_forms_layer1 failed (exit code {res.returncode}):\n{res.stderr}")

                # Parse summary from stdout (should print JSON summary as the last line or output)
                stdout_lines = res.stdout.strip().split("\n")
                summary = {}
                for line in reversed(stdout_lines):
                    if line.strip().startswith("{") and line.strip().endswith("}"):
                        try:
                            summary = json.loads(line)
                            break
                        except Exception:
                            pass

                # ── Step 2: Establish paths and copy outputs to docs/mappings/ ──
                # Paths to generated files in graphview outputs
                gv_outputs_dir = GRAPHVIEW_OUTPUTS_DIR
                
                map_configs = [
                    # (source file in gv_outputs, dest filename in docs/mappings)
                    (gv_outputs_dir / "forms" / "listFormJp.json", "forms_layer1.json"),
                    (gv_outputs_dir / "forms" / "listFormJpToEn.json", "form_access_to_wpf.json"),
                    (gv_outputs_dir / "queries" / "listQueryJp.json", "queries_layer1.json"),
                    (gv_outputs_dir / "queries" / "listQueryJpToEn.json", "query_access_to_dotnet.json"),
                    (gv_outputs_dir / "macros" / "listMacroJp.json", "macros_layer1.json"),
                    (gv_outputs_dir / "macros" / "listMacroJpToEn.json", "macro_access_to_dotnet.json"),
                    (gv_outputs_dir / "modules" / "listModuleJp.json", "modules_layer1.json"),
                    (gv_outputs_dir / "modules" / "listModuleJpToEn.json", "module_access_to_dotnet.json"),
                    (gv_outputs_dir / "events" / "listEventJp.json", "events_layer1.json"),
                    (gv_outputs_dir / "events" / "listEventJpToEn.json", "event_access_to_dotnet.json"),
                ]

                for src_path, dest_name in map_configs:
                    if not src_path.exists():
                        logger.warning("[Agent Mapping] Expected source mapping file not found: %s", src_path)
                        continue

                    # Read content
                    content = src_path.read_text(encoding="utf-8")

                    # Copy to docs/mappings/
                    dest_path_docs = docs_mappings_dir / dest_name
                    dest_path_docs.write_text(content, encoding="utf-8")
                    logger.info("[Agent Mapping] Deployed mapping file: %s", dest_path_docs)

                    # Save flat snapshot under agent outputs/
                    dest_path_outputs = OUTPUTS_DIR / dest_name
                    dest_path_outputs.write_text(content, encoding="utf-8")

                    generated_files.append(GeneratedFile(
                        path=dest_name,
                        content=content,
                        generator="export_forms_layer1",
                        agent="mapping",
                    ))

                output = AgentOutput(
                    agent="mapping",
                    form_name=form_name,
                    files=generated_files,
                    status="success",
                    metadata={
                        "summary": summary.get("counts", {}),
                        "files_count": len(generated_files),
                    },
                )
                logger.info("[Agent Mapping] ✅ Successfully generated and deployed %d mapping files", len(generated_files))
                return output

            else:
                # ── Custom Flow for specific Macro/Module Code Gen ────────────────
                from pymongo import MongoClient
                from core.config import MONGO_URI, MONGO_DB, COL_MACROS
                from llm.llm_client import L5LLMClient, extract_code_block

                client = MongoClient(MONGO_URI)
                db = client[MONGO_DB]

                # Check if it's a Macro
                macro_doc = db[COL_MACROS].find_one({"name": form_name})
                if not macro_doc:
                    macro_doc = db[COL_MACROS].find_one({"macro_name": form_name})

                if macro_doc:
                    logger.info(f"[Agent Mapping] Found macro: {form_name}. Generating WPF C# service code...")

                    # Suggested type name (graphview macros map), else a collision-free fallback
                    class_name = (_mapped_type_name("macros/listMacroJpToEn.json", "access_macro_name", form_name)
                                  or _fallback_type_name(form_name, "MacroWorkflow"))

                    # Generate macro code using LLM
                    system_prompt = self.load_prompt("agent_mapping_macro.md")
                    user_prompt = f"""
Access Macro Name: {form_name}
Suggested Dotnet Class Name: {class_name}

References:
{json.dumps(macro_doc.get("references", {}), ensure_ascii=False, indent=2)}

Parsed Steps:
{json.dumps(macro_doc.get("steps", []), ensure_ascii=False, indent=2)}

Raw XML Definition:
```xml
{macro_doc.get("raw_xml", "")}
```
"""
                    llm = L5LLMClient()
                    raw_code = llm.generate_code(
                        task_type="service",
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        agent="mapping",
                        form_name=form_name
                    )
                    csharp_code = extract_code_block(raw_code, "csharp")

                    # ── Post-gen validation: fix undeclared injected interfaces ──────
                    import re as _re
                    _injected = _re.findall(r'private\s+readonly\s+(I\w+)\s+(\w+)', csharp_code)
                    _declared = set(_re.findall(r'public\s+interface\s+(I\w+)', csharp_code))
                    for _iface, _field in _injected:
                        if _iface not in _declared:
                            logger.warning("[Agent Mapping] ⚠️ Undeclared '%s' — removing from %s", _iface, class_name)
                            _param = _field.lstrip('_')
                            csharp_code = _re.sub(r'\n\s*private\s+readonly\s+' + _re.escape(_iface) + r'\s+' + _re.escape(_field) + r';', '', csharp_code)
                            csharp_code = _re.sub(r',?\s*' + _re.escape(_iface) + r'\s+' + _re.escape(_param) + r'\s*,?', '', csharp_code)
                            csharp_code = _re.sub(r'\n\s*' + _re.escape(_field) + r'\s*=\s*' + _re.escape(_param) + r'\s*;', '', csharp_code)
                            csharp_code = _re.sub(
                                r'[^\n]*' + _re.escape(_field) + r'\.\w+\([^)]*\)\s*;[^\n]*',
                                '            // TODO: ' + _iface + ' 未宣言 — 実装後に差し替え\n'
                                '            await System.Threading.Tasks.Task.CompletedTask;',
                                csharp_code
                            )

                    # Target paths
                    target_filename = f"{class_name}.cs"
                    dest_path_wpf = SERVICES_DIR / target_filename
                    dest_path_wpf.parent.mkdir(parents=True, exist_ok=True)
                    dest_path_wpf.write_text(csharp_code, encoding="utf-8")
                    logger.info(f"[Agent Mapping] Deployed macro service to WPF Services: {dest_path_wpf}")

                    # Mirror path under agent outputs
                    outputs_form_dir = OUTPUTS_DIR / form_name
                    outputs_form_dir.mkdir(parents=True, exist_ok=True)
                    dest_path_outputs = outputs_form_dir / target_filename
                    dest_path_outputs.write_text(csharp_code, encoding="utf-8")

                    generated_files.append(GeneratedFile(
                        path=target_filename,
                        content=csharp_code,
                        generator="llm",
                        agent="mapping",
                    ))

                    output = AgentOutput(
                        agent="mapping",
                        form_name=form_name,
                        files=generated_files,
                        status="success",
                        metadata={
                            "type": "macro",
                            "class_name": class_name,
                            "dest": _relpath(dest_path_wpf),
                        },
                    )
                    logger.info(f"[Agent Mapping] ✅ Successfully generated and deployed Macro service: {class_name}")
                    return output

                # Check if it's a Module
                module_doc = db[COL_MODULES].find_one({"name": form_name})
                if not module_doc:
                    module_doc = db[COL_MODULES].find_one({"module_name": form_name})

                if module_doc:
                    logger.info(f"[Agent Mapping] Found module: {form_name}. Generating Domain Common service code...")

                    class_name = (_mapped_type_name("modules/listModuleJpToEn.json", "access_module_name", form_name)
                                  or _fallback_type_name(form_name, "Service"))

                    # Generate module code using LLM
                    system_prompt = self.load_prompt("agent_mapping_module.md")
                    user_prompt = f"""
Access Module Name: {form_name}
Suggested Dotnet Class Name: {class_name}

Constants:
{json.dumps(module_doc.get("constants", []), ensure_ascii=False, indent=2)}

User Defined Types:
{json.dumps(module_doc.get("user_types", []), ensure_ascii=False, indent=2)}

Variables:
{json.dumps(module_doc.get("variables", []), ensure_ascii=False, indent=2)}

Options:
{json.dumps(module_doc.get("options", {}), ensure_ascii=False, indent=2)}

Functions and Procedures:
{json.dumps(module_doc.get("functions", []), ensure_ascii=False, indent=2)}
"""
                    llm = L5LLMClient()
                    raw_code = llm.generate_code(
                        task_type="service",
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        agent="mapping",
                        form_name=form_name
                    )
                    csharp_code = extract_code_block(raw_code, "csharp")

                    # Target paths
                    target_filename = f"{class_name}.cs"
                    dest_path_domain = DOMAIN_PROJECT_DIR / "Common" / target_filename
                    dest_path_domain.parent.mkdir(parents=True, exist_ok=True)
                    dest_path_domain.write_text(csharp_code, encoding="utf-8")
                    logger.info(f"[Agent Mapping] Deployed module service to Domain Common: {dest_path_domain}")

                    # Mirror path under agent outputs
                    outputs_form_dir = OUTPUTS_DIR / form_name
                    outputs_form_dir.mkdir(parents=True, exist_ok=True)
                    dest_path_outputs = outputs_form_dir / target_filename
                    dest_path_outputs.write_text(csharp_code, encoding="utf-8")

                    generated_files.append(GeneratedFile(
                        path=target_filename,
                        content=csharp_code,
                        generator="llm",
                        agent="mapping",
                    ))

                    output = AgentOutput(
                        agent="mapping",
                        form_name=form_name,
                        files=generated_files,
                        status="success",
                        metadata={
                            "type": "module",
                            "class_name": class_name,
                            "dest": _relpath(dest_path_domain),
                        },
                    )
                    logger.info(f"[Agent Mapping] ✅ Successfully generated and deployed Module service: {class_name}")
                    return output

                # Neither macro nor module found
                raise ValueError(f"Target '{form_name}' not found in macros or modules collections.")

        except Exception as e:
            logger.error("[Agent Mapping] ❌ Failed mapping generation: %s", e, exc_info=True)
            return AgentOutput(
                agent="mapping",
                form_name=form_name,
                status="error",
                error=str(e),
            )


# ── CLI ──
async def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Agent Mapping — Gen Common Mapping to Source docs")
    parser.add_argument("form_name", nargs="?", default="ALL", help="Form name or ALL (default)")
    parser.add_argument("--model", default=None, help="Unused override")
    args = parser.parse_args()

    agent = MappingAgent()
    result = await agent.run(AgentInput(form_name=args.form_name))

    if result.status == "success":
        print(f"\n[OK] Generated and deployed {len(result.files)} files:")
        for f in result.files:
            print(f"   -> docs/mappings/{f.path}")
    else:
        print(f"\n[ERROR] Error: {result.error}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
