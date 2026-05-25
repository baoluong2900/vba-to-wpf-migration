import json
from pathlib import Path
import config

def load_template(template_name: str) -> dict:
    """
    Loads a JSON schema template.
    If TARGET_LANGUAGE is not 'ja', attempts to load the localized version from locales/ directory.
    Fallback to the original template if not found.
    """
    proj_root = Path(__file__).resolve().parent.parent.parent.parent
    template_dir = proj_root / "backend" / "layer2" / "schema" / "template"
    locales_dir = proj_root / "backend" / "layer2" / "schema" / "locales"
    
    # 1. Base template
    base_path = template_dir / template_name
    if not base_path.exists():
        # Fallback for some callers that might be in different CWD
        base_path = Path("schema/template") / template_name
        template_dir = Path("schema/template")
        locales_dir = Path("schema/locales")
        
    if not base_path.exists():
        return {}

    target_lang = getattr(config, "TARGET_LANGUAGE", "ja").lower()
    
    # 2. Check localized template
    if target_lang not in ["ja", "japanese"]:
        # Try to load from locales/en/bd_form.json
        lang_code = "en" if target_lang == "english" else target_lang
        loc_path = locales_dir / lang_code / template_name
        if loc_path.exists():
            return json.loads(loc_path.read_text(encoding="utf-8"))
            
        # Try to load from template/bd_form_en.json
        stem = base_path.stem
        ext = base_path.suffix
        loc_path2 = template_dir / f"{stem}_{lang_code}{ext}"
        if loc_path2.exists():
            return json.loads(loc_path2.read_text(encoding="utf-8"))

    # 3. Fallback to base
    return json.loads(base_path.read_text(encoding="utf-8"))
