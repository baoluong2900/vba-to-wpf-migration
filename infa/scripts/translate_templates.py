import os
import json
import asyncio
import sys
from pathlib import Path

# Add backend/layer2 to path so we can import llm_client
BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend" / "layer2"))

from llm.llm_client import LLMClient
from core.config import DEFAULT_MODEL

def translate_template(client: LLMClient, content: str, target_language: str) -> str:
    prompt = f"""
Translate the values of the following JSON template into {target_language}.
Keep the JSON structure, keys, and formatting exactly the same.
Only translate the string values (the descriptions/hints).
Do not translate the keys.
If a value is empty or not text, leave it alone.
Return ONLY valid JSON.

JSON:
{content}
"""
    try:
        response = client.chat(
            model_cfg=DEFAULT_MODEL,
            system="You are a JSON localization assistant. Output only raw JSON.",
            user=prompt
        )
        # Extract JSON if wrapped in markdown
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        
        # Verify it parses
        json.loads(response)
        return response
    except Exception as e:
        print(f"Error translating: {e}")
        return content

def main():
    target_language = "English"
    template_dir = BASE_DIR / "backend" / "layer2" / "schema" / "template"
    
    if not template_dir.exists():
        print(f"Template dir not found: {template_dir}")
        return

    client = LLMClient()
    
    for filename in ["bd_form.json", "bd_report.json", "dd_form.json", "dd_report.json", "dd_macros.json", "dd_modules.json"]:
        filepath = template_dir / filename
        if not filepath.exists():
            continue
            
        print(f"Translating {filename} to {target_language}...")
        content = filepath.read_text(encoding="utf-8")
        translated_content = translate_template(client, content, target_language)
        
        out_path = template_dir.parent / "locales" / f"{filepath.stem}_{target_language.lower()}{filepath.suffix}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(translated_content, encoding="utf-8")
        print(f"Saved to {out_path.name}")

if __name__ == "__main__":
    main()
