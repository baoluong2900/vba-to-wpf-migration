"""
main.py — Layer 2 Entrypoint

Usage:
    python main.py --item C000_MAINⅡ --type form --stage dev
    python main.py --all-forms --stage dev
    python main.py --all --stage production

Environment variables:
    L2_STAGE          = dev | pilot | production  (default: dev)
    MONGO_URI         = mongodb://...
    GOOGLE_API_KEY    = ...
    ANTHROPIC_API_KEY = ...
    OPENAI_API_KEY    = ...
    L2_HUMAN_REVIEW   = 0 | 1   (1 = interactive CLI review)
"""
from __future__ import annotations

import argparse
import sys
import os

# ── ensure layer2/ and runners/ are on path when run directly ────────────────
_RUNNERS_DIR = os.path.dirname(os.path.abspath(__file__))
_LAYER2_DIR = os.path.dirname(_RUNNERS_DIR)
if _LAYER2_DIR not in sys.path:
    sys.path.insert(0, _LAYER2_DIR)
if _RUNNERS_DIR not in sys.path:
    sys.path.insert(0, _RUNNERS_DIR)

from config import STAGE, OUTPUT_DIR
from pipeline import build_pipeline
from state import PipelineState
from db.layer1_repo import Layer1Repo
from utils.cost_tracker import get_tracker
from utils.logger import get_logger
import push_to_mongo

logger = get_logger(__name__)


def run_item(
    item_name: str,
    item_type: str,
    stage: str,
    repo: Layer1Repo,
) -> None:
    """Run the BD→DD pipeline for one item."""
    logger.info("=" * 60)
    logger.info("Processing %s '%s' [stage=%s]", item_type, item_name, stage)

    # ── Query Layer 1 ──
    if item_type == "form":
        bd_code = repo.get_bd_code_json_form(item_name)
        dd_code = repo.get_dd_code_json_form(item_name)
        complexity = bd_code["form"].get("complexity_level", "low")
    elif item_type == "report":
        bd_code = repo.get_bd_code_json_report(item_name)
        dd_code = repo.get_dd_code_json_report(item_name)
        complexity = "medium"
    elif item_type == "module":
        bd_code = repo.get_bd_code_json_module(item_name)
        dd_code = repo.get_dd_code_json_module(item_name)
        complexity = "low"
    else:
        raise ValueError(f"Unknown item_type: {item_type}")

    # ── Build initial state ──
    initial_state: PipelineState = {
        "item_name": item_name,
        "screen_name": item_name,       # alias used by BDService
        "item_type": item_type,
        "complexity_level": complexity,
        "bd_code_json": bd_code,
        "dd_code_json": dd_code,
        "bd_docs_json": None,
        "dd_docs_json": None,
        "bd_review": None,
        "dd_review": None,
        "attempt_bd": 0,
        "attempt_dd": 0,
        "errors": [],
        "stage": stage,
        "repo": repo,                   # passed through so pipeline doesn't re-create
        "model_id": None,               # uses stage default
    }

    # ── Run pipeline ──
    pipeline = build_pipeline()
    final_state = pipeline.invoke(initial_state)

    logger.info("Completed '%s' → bd_docs + dd_docs saved to %s", item_name, OUTPUT_DIR)
    
    # ── Auto push to MongoDB & Backup ──
    try:
        push_to_mongo.push_bd()
        push_to_mongo.push_dd()
    except Exception as exc:
        logger.error("Auto-backup failed for '%s': %s", item_name, exc)
        
    return final_state


def main() -> None:
    parser = argparse.ArgumentParser(description="vba_brain Layer 2 — LLM BD/DD Generator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item", help="Item name (form/report/module name)")
    group.add_argument("--all-forms", action="store_true", help="Process all forms from Layer 1")
    group.add_argument("--all-reports", action="store_true", help="Process all reports")
    group.add_argument("--all-modules", action="store_true", help="Process all modules")
    group.add_argument("--all", action="store_true", help="Process all items (forms + reports + modules)")

    parser.add_argument(
        "--type",
        choices=["form", "report", "module"],
        help="Item type (required when --item is used)",
    )
    parser.add_argument(
        "--stage",
        choices=["dev", "pilot", "production"],
        default=os.getenv("L2_STAGE", "dev"),
        help="LLM model stage (default: dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List items to process without running LLM",
    )

    args = parser.parse_args()
    stage = args.stage

    repo = Layer1Repo()
    tracker = get_tracker()

    items: list[tuple[str, str]] = []

    if args.item:
        if not args.type:
            parser.error("--type is required when --item is specified")
        items = [(args.item, args.type)]
    elif args.all_forms:
        items = [(n["name"] if isinstance(n, dict) else n, "form") for n in repo.list_forms()]
    elif args.all_reports:
        items = [(n, "report") for n in repo.list_reports()]
    elif args.all_modules:
        items = [(n, "module") for n in repo.list_modules()]
    elif args.all:
        items = (
            [(n["name"] if isinstance(n, dict) else n, "form") for n in repo.list_forms()]
            + [(n, "report") for n in repo.list_reports()]
            + [(n, "module") for n in repo.list_modules()]
        )

    logger.info("Items to process: %d", len(items))

    if args.dry_run:
        for name, itype in items:
            print(f"  [{itype}] {name}")
        return

    success = 0
    failed = []

    for item_name, item_type in items:
        try:
            run_item(item_name, item_type, stage, repo)
            success += 1
        except Exception as exc:
            logger.error("FAILED '%s': %s", item_name, exc, exc_info=True)
            failed.append((item_name, str(exc)))

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"Layer 2 Complete")
    print(f"  Success : {success}")
    print(f"  Failed  : {len(failed)}")
    print(f"  Total   : {len(items)}")
    if failed:
        print("\nFailed items:")
        for name, err in failed:
            print(f"  ✗ {name}: {err}")

    cost_path = tracker.save_report()
    print(f"\nCost Report → {cost_path}")
    print(f"Total cost  : ${tracker.total_cost:.4f}")
    print(f"Total tokens: {tracker.total_tokens}")


if __name__ == "__main__":
    main()
