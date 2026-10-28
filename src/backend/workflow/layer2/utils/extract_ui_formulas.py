import json
import uuid
from pathlib import Path

def find_all_formulas(node, results_list):
    if isinstance(node, dict):
        source_val = node.get("source_field_or_fixed_value", "")
        if isinstance(source_val, str) and source_val.strip().startswith("="):
            formula_id = f"src_{uuid.uuid4().hex[:8]}"
            node["_formula_id_src"] = formula_id
            results_list.append({
                "item_no": node.get("item_no", node.get("no", "")),
                "logical_name": node.get("logical_name", node.get("output_field_name", "")),
                "physical_name": formula_id,
                "item_attribute": node.get("item_attribute", "source_field_or_fixed_value"),
                "formula": source_val.strip()
            })
            
        cond_val = node.get("condition_and_format", "")
        if isinstance(cond_val, str) and cond_val.strip().startswith("="):
            formula_id = f"cond_{uuid.uuid4().hex[:8]}"
            node["_formula_id_cond"] = formula_id
            results_list.append({
                "item_no": node.get("item_no", node.get("no", "")),
                "logical_name": node.get("logical_name", node.get("output_field_name", "")),
                "physical_name": formula_id,
                "item_attribute": node.get("item_attribute", "condition_and_format"),
                "formula": cond_val.strip()
            })
            
        for key, value in node.items():
            find_all_formulas(value, results_list)
    elif isinstance(node, list):
        for item in node:
            find_all_formulas(item, results_list)

def extract_formulas(s2_dir_path, output_path, target_screen=None):
    """
    Extracts all UI formulas (source_field_or_fixed_value starting with '=')
    from S2 mapping JSON files and saves them to a structured JSON output.
    """
    s2_dir = Path(s2_dir_path)
    if not s2_dir.exists():
        print(f"Error: Directory {s2_dir} does not exist.")
        return

    results = {}
    total_formulas = 0
    
    for file_path in s2_dir.glob("*.json"):
        if target_screen and target_screen not in file_path.stem:
            continue
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            screen_name = data.get("screen_name", file_path.stem)
            formulas_in_file = []
            
            # Recursively find all formulas in the entire JSON file
            find_all_formulas(data, formulas_in_file)
            
            if formulas_in_file:
                total_formulas += len(formulas_in_file)
                results[screen_name] = {
                    "file_name": file_path.name,
                    "formulas": formulas_in_file
                }
                
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")
            
    # Save to output
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"[SUCCESS] Extracted {total_formulas} formulas from {len(results)} screens.")
    print(f"[OUTPUT] Saved to: {out_file}")

if __name__ == "__main__":
    import sys
    
    # Resolve Layer 2 directory dynamically
    _LAYER2_DIR = Path(__file__).resolve().parent.parent
    
    # Default paths mapped dynamically to the Layer 2 output folder structure
    DEFAULT_S2_DIR = str(_LAYER2_DIR / "output" / "bd_flow" / "bd2_bd_mapping")
    DEFAULT_OUT_FILE = str(_LAYER2_DIR / "output" / "bd_flow" / "bd3_bd_logic" / "ui_formulas_extracted.json")
    
    s2_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_S2_DIR
    out_file = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT_FILE
    target_screen = sys.argv[3] if len(sys.argv) > 3 else None
    
    extract_formulas(s2_dir, out_file, target_screen)
