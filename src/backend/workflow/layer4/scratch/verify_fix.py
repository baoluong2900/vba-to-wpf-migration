
import sys
import os
from pathlib import Path

# Add the backend and layer4/sql_migration directory to sys.path dynamically
backend_path = Path(__file__).resolve().parent.parent.parent.parent
layer2_path = backend_path / "workflow" / "layer2"
layer4_path = backend_path / "workflow" / "layer4"
sys.path.append(str(backend_path))
sys.path.append(str(layer2_path))
sys.path.append(str(layer4_path))

try:
    from sql_migration.router import _parse_sql_components
    import re
    
    # Test string with various Japanese character types in bind variables
    test_sql = """
    SELECT * FROM TABLE 
    WHERE field1 = :txt工事名称 
    AND field2 = :txt店所コード 
    AND field3 = :txtⅡ型
    AND field4 = :ひらがな
    """
    
    print("--- Testing Regex Extraction ---")
    # Simulate the findall logic used in update_query
    bind_vars = list(set(re.findall(r':\s*([a-zA-Z0-9_＿\u4e00-\u9fa5\u3040-\u309F\u30A0-\u30FF\uFF00-\uFFEF\u2160-\u216B]+)', test_sql)))
    print(f"Extracted Bind Variables: {bind_vars}")
    
    expected = ['txt工事名称', 'txt店所コード', 'txtⅡ型', 'ひらがな']
    missing = [e for e in expected if e not in bind_vars]
    
    if not missing:
        print("SUCCESS: All Japanese parameters extracted correctly.")
    else:
        print(f"FAILURE: Missing parameters: {missing}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
