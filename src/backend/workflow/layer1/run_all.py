#!/usr/bin/env python3
"""
run_all.py — Batch pipeline: parse the Access export → seed MongoDB → Layer 2 BD/DD →
Layer 3 PostgreSQL tables.

Usage:
    python run_all.py                       # every step, in order
    python run_all.py --list                # show the step keys
    python run_all.py --from seed           # resume from a step
    python run_all.py --only tables,queries # run just these steps
    python run_all.py --skip layer2         # everything except these
    python run_all.py --dry-run             # print the plan, run nothing
    python run_all.py --keep-going          # continue after a failed step

The step descriptions are matched by the web console (src/frontend/src/app/api/v1/layer1/
extract/route.ts) to drive its progress bar — keep them stable.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LAYER1_DIR = Path(__file__).parent.resolve()

# (key, command relative to LAYER1_DIR, description)
STEPS = [
    ("tables", ["parser/table_parser.py"], "Parsing Tables"),
    ("queries", ["parser/query_parser.py"], "Parsing Queries"),
    ("forms", ["parser/frm_parser.py"], "Parsing Forms"),
    ("macros", ["parser/macro_parser.py"], "Parsing Macros"),
    ("modules", ["parser/modules_parser.py"], "Parsing Modules"),
    ("aggregate", ["aggregator.py"], "Aggregating References"),
    ("seed", ["seed_db.py"], "Seeding MongoDB"),
    # Layer 2 reads query context from queries_v2, so it must exist before BD/DD generation.
    ("seed-queries", ["../layer3/sql_migration/seed_queries_v2.py"], "Seeding Query Review Collection (queries_v2)"),
    ("layer2", ["../layer2/runners/main.py", "--all", "--stage", "dev"], "Generating BD & DD Specifications (Layer 2)"),
    ("layer3", ["../layer3/sql_migration/postgres_migrator.py"], "Migrating Tables to PostgreSQL Database"),
]
STEP_KEYS = [key for key, _, _ in STEPS]


def _keys(value: str) -> list[str]:
    keys = [k.strip() for k in value.split(",") if k.strip()]
    unknown = [k for k in keys if k not in STEP_KEYS]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown step(s) {unknown}; choose from {STEP_KEYS}")
    return keys


def select_steps(only: list[str] | None, start: str | None, skip: list[str] | None) -> list[tuple]:
    steps = STEPS
    if start:
        steps = steps[STEP_KEYS.index(start):]
    if only:
        steps = [s for s in steps if s[0] in only]
    if skip:
        steps = [s for s in steps if s[0] not in skip]
    return steps


def run_step(cmd_args: list[str]) -> int:
    script_path = LAYER1_DIR / cmd_args[0]
    if not script_path.exists():
        print(f"[ERROR] Script not found: {cmd_args[0]}", flush=True)
        return 1
    process = subprocess.Popen(
        [sys.executable, "-X", "utf8", str(script_path), *cmd_args[1:]],
        cwd=str(LAYER1_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in iter(process.stdout.readline, ""):
        print(line, end="", flush=True)
    return process.wait()


def run(steps: list[tuple], keep_going: bool = False) -> int:
    print("[WORKFLOW] Starting full migration pipeline...", flush=True)
    failed: list[str] = []
    for idx, (key, cmd_args, desc) in enumerate(steps, 1):
        print(f"\n[STEP {idx}/{len(steps)}] {desc}...", flush=True)
        try:
            code = run_step(cmd_args)
        except Exception as e:
            print(f"[ERROR] Failed to run {cmd_args[0]}: {e}", flush=True)
            code = 1
        if code != 0:
            print(f"[ERROR] {cmd_args[0]} failed with exit code {code}", flush=True)
            failed.append(key)
            if not keep_going:
                return code
            continue
        print(f"[DONE] {desc} completed successfully.", flush=True)
        time.sleep(1)  # small pause so the console's progress view can follow

    if failed:
        print(f"\n[ERROR] Pipeline finished with failed step(s): {', '.join(failed)}", flush=True)
        return 1
    print("\n[SUCCESS] Full Workflow Pipeline completed successfully!", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the vba_brain batch pipeline.")
    parser.add_argument("--list", action="store_true", help="list the step keys and exit")
    parser.add_argument("--from", dest="start", choices=STEP_KEYS, help="start at this step")
    parser.add_argument("--only", type=_keys, help="comma-separated steps to run")
    parser.add_argument("--skip", type=_keys, help="comma-separated steps to leave out")
    parser.add_argument("--dry-run", action="store_true", help="print the selected steps without running them")
    parser.add_argument("--keep-going", action="store_true", help="continue after a failed step")
    args = parser.parse_args(argv)

    if args.list:
        for key, cmd, desc in STEPS:
            print(f"{key:<13} {desc}  ({' '.join(cmd)})")
        return 0

    steps = select_steps(args.only, args.start, args.skip)
    if not steps:
        print("[WORKFLOW] No steps selected.")
        return 0
    if args.dry_run:
        for idx, (key, cmd, desc) in enumerate(steps, 1):
            print(f"[PLAN {idx}/{len(steps)}] {key}: {desc}  ({' '.join(cmd)})")
        return 0
    return run(steps, keep_going=args.keep_going)


if __name__ == "__main__":
    sys.exit(main())
