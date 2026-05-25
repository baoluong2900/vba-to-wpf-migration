import asyncio
import sys
from pathlib import Path

# Fix sys.path to include workspace root
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.ui.agent_ui import UIAgent
from core.models import AgentInput

async def full_regen(form_name: str):
    print(f"Full regeneration for: {form_name}")
    agent = UIAgent()
    input_obj = AgentInput(form_name=form_name)
    
    # This will run the whole pipeline: Mongo -> Map -> Save Input -> LLM -> Save Preview -> Save XAML
    result = await agent.run(input_obj)
    
    if result.status == "success":
        print(f"[OK] Full regeneration complete: {form_name}")
    else:
        print(f"[ERR] Regeneration failed: {result.error}")

if __name__ == "__main__":
    form_name = "F_Login"
    asyncio.run(full_regen(form_name))
