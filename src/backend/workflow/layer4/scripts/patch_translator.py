import os
import glob
from pathlib import Path
import re

scripts_dir = Path("/Users/baoluong0209/GitTool/vba_mirgation/workflow/src/backend/workflow/layer4/scripts")

# 1. Update excel_translator.py
translator_path = scripts_dir / "excel_translator.py"
with open(translator_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add missing mappings
missing_mappings = """
    "ページ": "Page",
    "更新": "Update",
    "備    考": "Notes",
    "MONOSビルOM出荷": "MONOS Building OM Shipment",
    "補修部品": "Repair Parts",
    "出荷実績_当日": "Shipment_Result_Today",
    "出荷実績入力": "Shipment Result Input",
"""
content = content.replace('"変更履歴": "Change History",', missing_mappings + '\n    "変更履歴": "Change History",')

# Replace TARGET_LANGUAGE logic
target_lang_logic = """
def get_target_language():
    try:
        import json
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f).get("localization", {}).get("target_language", "en")
    except Exception:
        pass
    return "en"

def translate_workbook(wb: Workbook):
    TARGET_LANGUAGE = get_target_language()
"""

# The existing translate_workbook has:
# def translate_workbook(wb: Workbook):
#     try:
#         from config import TARGET_LANGUAGE
# ...

content = re.sub(
    r"def translate_workbook\(wb: Workbook\):.*?if TARGET_LANGUAGE\.lower\(\) not in \(\"en\", \"english\"\):",
    target_lang_logic.strip() + '\n    if TARGET_LANGUAGE.lower() not in ("en", "english"):',
    content,
    flags=re.DOTALL
)

with open(translator_path, "w", encoding="utf-8") as f:
    f.write(content)

# 2. Update all fill_*.py files to dynamically append sys.path if needed
import_fix = """
    try:
        import sys
        from pathlib import Path
        _scripts_dir = Path(__file__).resolve().parent
        if str(_scripts_dir) not in sys.path:
            sys.path.insert(0, str(_scripts_dir))
        from excel_translator import translate_workbook
        translate_workbook(wb)
    except Exception as e:
        print(f"[WARN] Failed to translate workbook: {e}")
"""

old_import_regex = re.compile(r"    try:\n        try:\n            from excel_translator import translate_workbook.*?translate_workbook\(wb\)\n    except Exception as e:\n        print\(f\"\[WARN\] Failed to translate workbook: \{e\}\"\)", re.DOTALL)

for file_path in glob.glob(str(scripts_dir / "fill_*.py")):
    with open(file_path, "r", encoding="utf-8") as f:
        f_content = f.read()
    
    if "from excel_translator import translate_workbook" in f_content:
        new_content = old_import_regex.sub(import_fix.strip('\n'), f_content)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Patched {file_path}")

