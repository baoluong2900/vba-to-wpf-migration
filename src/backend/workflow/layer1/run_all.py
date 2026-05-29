#!/usr/bin/env python3
import sys
import subprocess
import time
from pathlib import Path

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LAYER1_DIR = Path(__file__).parent.resolve()

SCRIPTS = [
    (["parser/table_parser.py"], "Parsing Tables"),
    (["parser/query_parser.py"], "Parsing Queries"),
    (["parser/frm_parser.py"], "Parsing Forms"),
    (["parser/macro_parser.py"], "Parsing Macros"),
    (["parser/modules_parser.py"], "Parsing Modules"),
    (["aggregator.py"], "Aggregating References"),
    (["seed_db.py"], "Seeding MongoDB"),
    (["../layer2/runners/main.py", "--all", "--stage", "dev"], "Generating BD & DD Specifications (Layer 2)"),
    (["../layer3/sql_migration/postgres_migrator.py"], "Migrating Tables to PostgreSQL Database")
]

def run():
    print("[WORKFLOW] Starting full migration pipeline...", flush=True)
    total = len(SCRIPTS)
    for idx, (cmd_args, desc) in enumerate(SCRIPTS):
        script = cmd_args[0]
        script_path = LAYER1_DIR / script
        if not script_path.exists():
            print(f"[ERROR] Script not found: {script}", flush=True)
            sys.exit(1)
        
        print(f"\n[STEP {idx+1}/{total}] {desc}...", flush=True)
        try:
            # We run python script synchronously and stream its output to our own stdout
            full_cmd = [sys.executable, "-X", "utf8", str(script_path)] + cmd_args[1:]
            process = subprocess.Popen(
                full_cmd,
                cwd=str(LAYER1_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            for line in iter(process.stdout.readline, ""):
                if line:
                    print(line, end="", flush=True)
            
            process.wait()
            if process.returncode != 0:
                print(f"[ERROR] {script} failed with exit code {process.returncode}", flush=True)
                sys.exit(process.returncode)
        except Exception as e:
            print(f"[ERROR] Failed to run {script}: {e}", flush=True)
            sys.exit(1)
            
        print(f"[DONE] {desc} completed successfully.", flush=True)
        time.sleep(1) # Small pause for UI effect
        
    print("\n[SUCCESS] Full Workflow Pipeline completed successfully!", flush=True)

if __name__ == "__main__":
    run()
