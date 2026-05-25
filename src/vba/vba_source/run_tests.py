#!/usr/bin/env python3
"""
run_tests.py — Runs Layer 1 parsers on the mock test_vba_source files and verifies outputs.
"""
import json
import subprocess
import sys
from pathlib import Path

# Paths
TEST_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = TEST_DIR.parents[2]
PARSER_DIR = WORKSPACE_ROOT / "src" / "backend" / "workflow" / "layer1" / "parser"
OUTPUT_DIR = TEST_DIR / "output"

# Define tests
TESTS = [
    {
        "name": "Forms Parser",
        "cmd": [
            sys.executable,
            str(PARSER_DIR / "frm_parser.py"),
            str(TEST_DIR / "Forms"),
            str(OUTPUT_DIR / "forms"),
            "--config",
            str(PARSER_DIR.parent / "config" / "parser_config.json")
        ],
        "expected_files": [
            OUTPUT_DIR / "forms" / "F_TestForm.json",
            OUTPUT_DIR / "forms" / "F_Menu.json",
            OUTPUT_DIR / "forms" / "F_ProductList.json",
            OUTPUT_DIR / "forms" / "F_ProductDetail.json",
            OUTPUT_DIR / "forms" / "F_Login.json"
        ],
        "verify_keys": ["key", "type", "name", "properties", "items"]
    },
    {
        "name": "Macros Parser",
        "cmd": [
            sys.executable,
            str(PARSER_DIR / "macro_parser.py"),
            str(TEST_DIR / "Macros"),
            "--output-dir",
            str(OUTPUT_DIR / "macros")
        ],
        "expected_files": [
            OUTPUT_DIR / "macros" / "M_TestMacro.json",
            OUTPUT_DIR / "macros" / "M_OpenDashboard.json"
        ],
        "verify_keys": ["macro_name", "source_file", "steps", "references"]
    },
    {
        "name": "Modules Parser",
        "cmd": [
            sys.executable,
            str(PARSER_DIR / "modules_parser.py"),
            str(TEST_DIR / "Modules"),
            str(OUTPUT_DIR / "modules")
        ],
        "expected_files": [
            OUTPUT_DIR / "modules" / "Mod_TestModule.json",
            OUTPUT_DIR / "modules" / "Mod_CommonUtils.json",
            OUTPUT_DIR / "modules" / "Common.json"
        ],
        "verify_keys": ["module_name", "constants", "functions", "variables"]
    },
    {
        "name": "Queries Parser",
        "cmd": [
            sys.executable,
            str(PARSER_DIR / "query_parser.py"),
            str(TEST_DIR / "Queries"),
            "--output-dir",
            str(OUTPUT_DIR / "queries")
        ],
        "expected_files": [
            OUTPUT_DIR / "queries" / "Q_TestQuery.json",
            OUTPUT_DIR / "queries" / "Q_GetActiveProducts.json",
            OUTPUT_DIR / "queries" / "Q_UpdateProductStock.json",
            OUTPUT_DIR / "queries" / "Q000_T_ID_PASS.json",
            OUTPUT_DIR / "queries" / "Q000_T_LoginUser.json"
        ],
        "verify_keys": ["query_name", "tables", "query"]
    },
    {
        "name": "Tables Parser",
        "cmd": [
            sys.executable,
            str(PARSER_DIR / "table_parser.py"),
            str(TEST_DIR / "Tables" / "AllColumns.csv"),
            "--output-dir",
            str(OUTPUT_DIR / "tables")
        ],
        "expected_files": [
            OUTPUT_DIR / "tables" / "TBL_Users.json"
        ],
        "verify_keys": ["table_name", "columns"]
    }
]

def run_cmd(args):
    print(f"Running command: {' '.join(args)}")
    res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(f"[FAIL] Command failed.\nStdout: {res.stdout}\nStderr: {res.stderr}")
        return False
    return True

def main():
    print("=" * 60)
    print("      Testing Layer 1 Parsers with Mock VBA Source")
    print("=" * 60 + "\n")

    # Clean previous output
    if OUTPUT_DIR.exists():
        import shutil
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    passed_count = 0
    for t in TESTS:
        print(f"--- Running Test: {t['name']} ---")
        if not run_cmd(t["cmd"]):
            continue

        test_ok = True
        for exp_file in t["expected_files"]:
            exp_file_path = Path(exp_file)
            if not exp_file_path.is_file():
                print(f"[FAIL] Expected output file not found: {exp_file_path}\n")
                test_ok = False
                continue

            try:
                data = json.loads(exp_file_path.read_text(encoding="utf-8"))
                missing_keys = [k for k in t["verify_keys"] if k not in data]
                if missing_keys:
                    print(f"[FAIL] Generated JSON ({exp_file_path.name}) missing expected keys: {missing_keys}\n")
                    test_ok = False
                    continue
                
                print(f"   [OK] Verified: {exp_file_path.name}")
            except Exception as e:
                print(f"[FAIL] Error parsing generated JSON file {exp_file_path.name}: {e}\n")
                test_ok = False

        if test_ok:
            print(f"[SUCCESS] {t['name']} test passed successfully.\n")
            passed_count += 1
        else:
            print(f"[FAIL] {t['name']} test failed.\n")

    print("=" * 60)
    if passed_count == len(TESTS):
        print(f"🎉 ALL TESTS PASSED SUCCESSFULLY! ({passed_count}/{len(TESTS)})")
        return 0
    else:
        print(f"❌ SOME TESTS FAILED. ({passed_count}/{len(TESTS)} passed)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
