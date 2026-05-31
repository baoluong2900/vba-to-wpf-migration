"""
patch_vm_from_output.py — Patch ViewModel from vm_methods_output.json without LLM.
Reads vm_methods_output.json and re-patches the ViewModel with fixed method bodies.
Also injects missing ViewModel properties from Request DTOs.
"""
import sys, json, re, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

LAYER5_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAYER5_DIR))
sys.path.insert(0, str(LAYER5_DIR / "agents" / "logic"))

from agents.logic.gen_vm_methods import patch_vm_method, inject_vm_method, inject_vm_properties
from core.config import VIEWMODELS_DIR, AVALONIA_PROJECT_DIR


def patch_from_output(form_name: str, dry_run: bool = False):
    logic_outputs = LAYER5_DIR / "agents" / "logic" / "outputs" / form_name
    vm_output_file = logic_outputs / "vm_methods_output.json"

    if not vm_output_file.exists():
        logger.error("vm_methods_output.json not found: %s", vm_output_file)
        return

    data = json.loads(vm_output_file.read_text(encoding="utf-8"))
    feature = data.get("feature", "FLogin")
    service_name = data.get("service", "")

    # Derive ViewModel stem from IFLoginService → FLogin
    vm_stem = ""
    m = re.match(r'^I([A-Z]\w+)Service$', service_name)
    if m:
        vm_stem = m.group(1)
    else:
        vm_stem = f"F{feature}" if not feature.startswith("F") else feature

    vm_filename = f"{vm_stem}ViewModel.cs"

    # Candidate paths for ViewModel
    candidates = [
        LAYER5_DIR / "agents" / "ui" / "outputs" / form_name / "ViewModels" / vm_filename,
        LAYER5_DIR / "agents" / "logic" / "outputs" / form_name / "ViewModels" / vm_filename,
        VIEWMODELS_DIR / vm_filename,
    ]
    vm_file = next((p for p in candidates if p.exists()), None)
    if vm_file is None:
        logger.error("ViewModel not found: %s (tried %d paths)", vm_filename, len(candidates))
        for c in candidates:
            logger.error("  - %s", c)
        return

    logger.info("Patching ViewModel: %s", vm_file)

    # 1. Inject missing properties from Request DTO
    source_root = AVALONIA_PROJECT_DIR
    dto_file = source_root / "vba_brain.Application" / "DTOs" / "Requests" / f"{vm_stem}ServiceRequests.cs"
    if not dto_file.exists():
        dto_file = LAYER5_DIR / "agents" / "service" / "outputs" / form_name / "Application" / "DTOs" / "Requests" / f"{vm_stem}ServiceRequests.cs"

    if dto_file.exists():
        dto_content = dto_file.read_text(encoding="utf-8")
        bd_items = []
        seen = set()
        for pm in re.finditer(r'public\s+([\w<>?]+)\s+(\w+)\s*\{\s*get;\s*set;\s*\}', dto_content):
            prop_type, prop_name = pm.group(1), pm.group(2)
            if prop_name not in seen and prop_name not in ("Success", "Message", "Data"):
                seen.add(prop_name)
                attr = "INT" if prop_type == "int" else "BOOL" if prop_type == "bool" else "STRING"
                bd_items.append({
                    "physical_name": prop_name,
                    "logical_name": f"Request DTO property {prop_name}",
                    "item_attribute": attr
                })
        if bd_items:
            n = inject_vm_properties(vm_file=vm_file, bd_items=bd_items, dry_run=dry_run)
            logger.info("Injected %d properties: %s", n, [i["physical_name"] for i in bd_items])
    else:
        logger.warning("Request DTO file not found: %s", dto_file)

    # 2. Patch each method body from vm_methods_output.json
    patched_count = 0
    for method in data.get("methods", []):
        vm_method = method.get("vm_method", "")
        code = method.get("code", "")
        if not vm_method or not code:
            continue

        patched = patch_vm_method(vm_file, vm_method, code, dry_run=dry_run)
        if not patched:
            patched = inject_vm_method(vm_file, vm_method, code, dry_run=dry_run)

        status = "OK patched" if patched else "FAIL"
        logger.info("  %s %s", status, vm_method)
        if patched:
            patched_count += 1

    logger.info("Done: %d/%d methods patched", patched_count, len(data.get("methods", [])))


if __name__ == "__main__":
    form = sys.argv[1] if len(sys.argv) > 1 else "F_Login"
    dry = "--dry-run" in sys.argv
    patch_from_output(form, dry_run=dry)
