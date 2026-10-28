"""
backup_layer5.py — Backup Layer 5 Agent Outputs

Copies the `.json` files under `agents/<name>/outputs/` of the specified agents
(ui, logic, service, repo) to `<repo>/data/agent_<name>/`, keeping their relative paths
(per-form files such as `<form>/method_outputs.json` must not overwrite each other).

Usage:
    python backup_layer5.py
    python backup_layer5.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

# ── Directories ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_JSON_DIR = BASE_DIR.parent.parent.parent.parent / "data"

AGENTS = ["ui", "logic", "service", "repo"]

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

def backup_agent(agent_name: str, dry_run: bool = False) -> None:
    src_dir = BASE_DIR / "agents" / agent_name / "outputs"
    dst_dir = DATABASE_JSON_DIR / f"agent_{agent_name}"

    if not src_dir.exists():
        logger.warning("Source directory does not exist: %s", src_dir)
        return

    logger.info("── Backup %s outputs to %s ──", agent_name, dst_dir.name)

    if dry_run:
        logger.info("[DRY-RUN] Would copy %s to %s", src_dir, dst_dir)
        return

    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        # Copy only .json files, keeping the outputs/ relative layout (no .cs/.cache/.xaml)
        copied = 0
        for src_file in src_dir.rglob("*.json"):
            dst_file = dst_dir / src_file.relative_to(src_dir)
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            copied += 1
        logger.info("   [BACKUP] Copied %d .json files for %s", copied, agent_name)
    except Exception as exc:
        logger.error("   [BACKUP] Failed to copy %s outputs: %s", agent_name, exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup Layer 5 Agent Outputs")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List directories to be copied without actually copying",
    )
    args = parser.parse_args()

    logger.info("Target Backup Directory: %s", DATABASE_JSON_DIR)
    
    for agent in AGENTS:
        backup_agent(agent, dry_run=args.dry_run)

    logger.info("Done.")

if __name__ == "__main__":
    main()
