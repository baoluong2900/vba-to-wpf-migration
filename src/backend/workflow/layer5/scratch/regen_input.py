import asyncio
import sys
from pathlib import Path

# Fix sys.path to include workspace root
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.ui.agent_ui import UIAgent
from core.models import AgentInput

async def regen_input(form_name: str):
    print(f"Regenerating input for: {form_name}")
    agent = UIAgent()
    
    # 1. Load mongo data
    mongo_data = agent._load_mongo_form(form_name)
    mongo_items = mongo_data.get("items", [])
    form_props  = mongo_data.get("properties", {})
    
    # 2. Map controls (this uses the updated inclusive logic)
    from agents.ui.control_mapper import map_all_controls, map_sections
    wpf_controls = map_all_controls(mongo_items)
    wpf_sections = map_sections(mongo_items)
    
    # 3. Get bindings
    input_obj = AgentInput(form_name=form_name)
    vm_bindings = agent._get_viewmodel_bindings(input_obj, form_name, wpf_controls)
    
    # 4. Form config
    form_config = agent._build_form_config(form_props)
    
    # 5. Save input snapshot
    input_snapshot = {
        "form_name":          form_name,
        "form_properties":    form_config,
        "sections":           wpf_sections,
        "viewmodel_bindings": vm_bindings,
    }
    agent._save_input(form_name, input_snapshot)
    print(f"[OK] Input snapshot updated: {form_name}_input.json")

if __name__ == "__main__":
    form_name = "C000_MAINⅡ_未入金"
    asyncio.run(regen_input(form_name))
