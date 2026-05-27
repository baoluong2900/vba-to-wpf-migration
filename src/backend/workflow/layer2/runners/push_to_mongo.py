"""
push_to_mongo.py — Push Layer 2 final outputs to MongoDB

Reads all JSON files from:
  - output/dd_flow/screen/d4_dd_final/  → collection: dds
  - output/bd_flow/s4_bd_final/         → collection: bds

Each file is upserted using `name` = stem of the filename (without .json) as the
primary key so re-running layer2 always keeps the DB up-to-date (no duplicates).

Usage:
    python push_to_mongo.py                     # push both dd + bd
    python push_to_mongo.py --only dd           # push dd only
    python push_to_mongo.py --only bd           # push bd only
    python push_to_mongo.py --dry-run           # list files without writing

Environment (reads .env in this directory):
    MONGO_URI  — e.g. mongodb://vba_brain:vba_brain2024@:27017/vba_brain_core?authSource=admin
    MONGO_DB   — e.g. vba_brain_core
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── ensure layer2/ and runners/ are on path when run directly ────────────────
_RUNNERS_DIR = os.path.dirname(os.path.abspath(__file__))
_LAYER2_DIR = os.path.dirname(_RUNNERS_DIR)
if _LAYER2_DIR not in sys.path:
    sys.path.insert(0, _LAYER2_DIR)
if _RUNNERS_DIR not in sys.path:
    sys.path.insert(0, _RUNNERS_DIR)

# ── Load .env from the layer2 directory ──────────────────────────────────────
_ENV_FILE = Path(_LAYER2_DIR) / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.environ.get("MONGO_DB",  "vba_brain_core")

# ── Directories ───────────────────────────────────────────────────────────────
BASE_DIR = Path(_LAYER2_DIR)

BD_FINAL_DIR = BASE_DIR / "output" / "bd_flow" / "s4_bd_final"

# All DD categories that produce d4_dd_final output
_DD_CATEGORIES = ("screen", "report", "macro", "common")

COL_DDS = "dds"   # target collection for DD final docs
COL_BDS = "bds"   # target collection for BD final docs

# ── Backup Directories ────────────────────────────────────────────────────────
DATABASE_JSON_DIR = BASE_DIR.parent.parent.parent.parent / "data"
DDS_BACKUP_DIR = DATABASE_JSON_DIR / "dds"
BDS_BACKUP_DIR = DATABASE_JSON_DIR / "bds"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_json_files(directory: Path) -> list[tuple[str, dict, Path]]:
    """Return list of (name, doc, path) for every *.json in *directory*."""
    if not directory.exists():
        logger.warning("Directory not found: %s", directory)
        return []

    results: list[tuple[str, dict, Path]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            name = path.stem          # filename without .json extension
            results.append((name, doc, path))
        except Exception as exc:
            logger.error("Failed to load %s: %s", path.name, exc)
    return results


def _detect_item_type_from_l1(name: str) -> str:
    """
    Look up the item type from Layer 1 MongoDB collections.
    Returns "form" | "report" | "module" | "macro".

    Note: Layer 1 parser sometimes stores Reports inside the `forms` collection
    with a `type` field value of "Reports". We check this field to correctly
    classify them as "report".
    """
    L1_CHECKS = [
        ("forms",   "form"),
        ("reports", "report"),
        ("modules", "module"),
        ("macros",  "macro"),
    ]
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[MONGO_DB]
        for coll, type_label in L1_CHECKS:
            doc = db[coll].find_one({"name": name}, {"_id": 0, "type": 1})
            if doc is not None:
                client.close()
                # L1 parser stores reports in forms collection with type="Reports"
                doc_type = str(doc.get("type", "")).lower()
                if doc_type in ("reports", "report"):
                    return "report"
                # modules and macros are always correct from collection name
                return type_label
        client.close()
    except Exception:
        pass
    # Fallback: name-prefix heuristic
    if name.upper().startswith("R"):
        return "report"
    return "form"


def _upsert_docs(
    collection_name: str,
    docs: list[tuple[str, dict, Path]],
    *,
    dry_run: bool = False,
    extra_fields: dict | None = None,
) -> tuple[int, int, int]:
    """
    Upsert *docs* into MongoDB collection *collection_name*.

    Each document is stored with:
        - ``name``       = stem of the source file  (primary key for upsert)
        - ``type``       = item type (form/report/module/macro) from L1 or extra_fields
        - ``updated_at`` = current UTC timestamp
        - all original JSON fields merged in

    Returns (inserted, updated, failed) counts.
    """
    if not docs:
        logger.info("[%s] No documents to push.", collection_name)
        return 0, 0, 0

    if dry_run:
        for name, _, _ in docs:
            logger.info("[DRY-RUN] [%s] Would upsert: %s", collection_name, name)
        return 0, 0, 0

    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError
    except ImportError:
        logger.error("pymongo is not installed. Run: pip install pymongo")
        sys.exit(1)

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db     = client[MONGO_DB]
        col    = db[collection_name]
    except Exception as exc:
        logger.error("Cannot connect to MongoDB: %s", exc)
        sys.exit(1)

    inserted = updated = failed = 0
    now = datetime.now(tz=timezone.utc).isoformat()

    for name, raw_doc, _ in docs:
        # Determine type — priority:
        #   1. extra_fields["type"] — caller biết chắc (macro/module category folder)
        #   2. raw_doc["type"] — chỉ tin nếu là "macro" hoặc "module" (không thể sai)
        #      "form"/"report" trong file cũ có thể sai → luôn verify lại qua L1
        #   3. L1 lookup — nguồn chính xác nhất
        _extra_type = (extra_fields or {}).get("type")
        _doc_type   = raw_doc.get("type", "")
        if _extra_type:
            item_type = _extra_type
        elif _doc_type in ("macro", "module"):
            item_type = _doc_type   # macro/module không thể nhầm với form/report
        else:
            item_type = _detect_item_type_from_l1(name)
        doc = {
            **raw_doc,          # original JSON fields first
            "name": name,       # always set / overwrite with the canonical key
            "type": item_type,  # authoritative type field
            "updated_at": now,
            **(extra_fields or {}),
        }
        try:
            result = col.update_one(
                {"name": name},
                {"$set": doc},
                upsert=True,
            )
            if result.upserted_id is not None:
                inserted += 1
                logger.info("[%s] INSERTED: %s (type=%s)", collection_name, name, item_type)
            else:
                updated += 1
                logger.info("[%s] UPDATED : %s (type=%s)", collection_name, name, item_type)
        except Exception as exc:
            failed += 1
            logger.error("[%s] FAILED  : %s — %s", collection_name, name, exc)

    client.close()
    return inserted, updated, failed


def _copy_to_backup(docs: list[tuple[str, dict, Path]], backup_dir: Path, dry_run: bool = False) -> None:
    """Copy JSON files to the corresponding backup directory in database_json."""
    if not docs:
        return

    if dry_run:
        for name, _, path in docs:
            logger.info("[DRY-RUN] [BACKUP] Would copy %s to %s", path.name, backup_dir)
        return

    backup_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name, _, path in docs:
        try:
            dest = backup_dir / path.name
            shutil.copy2(path, dest)
            copied += 1
            logger.debug("[BACKUP] Copied %s", dest.name)
        except Exception as exc:
            logger.error("[BACKUP] Failed to copy %s: %s", path.name, exc)
    logger.info("   Backup Result: copied=%d to %s", copied, backup_dir.name)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def push_dd(dry_run: bool = False) -> None:
    """Push D4 DD final output from ALL categories (screen, report, macro, common) into MongoDB."""
    # Map category directory → item type
    _CAT_TO_TYPE = {
        "screen": None,     # will be resolved per-item via L1 lookup (form or report)
        "report": "report",
        "macro":  "macro",
        "common": "module",
    }
    total_ins = total_upd = total_fail = 0
    for cat in _DD_CATEGORIES:
        cat_dir = BASE_DIR / "output" / "dd_flow" / cat / "d4_dd_final"
        if not cat_dir.exists():
            logger.debug("[DD] Skipping missing dir: %s", cat_dir)
            continue
        logger.info("── DD Final [%s] → collection '%s' (%s)", cat, COL_DDS, cat_dir)
        docs = _load_json_files(cat_dir)
        logger.info("   Found %d file(s)", len(docs))
        # For non-screen categories we can set type directly; screen items need L1 lookup
        forced_type = _CAT_TO_TYPE.get(cat)
        extra = {"type": forced_type} if forced_type else {}
        ins, upd, fail = _upsert_docs(COL_DDS, docs, dry_run=dry_run, extra_fields=extra or None)
        logger.info("   Mongo Result: inserted=%d  updated=%d  failed=%d", ins, upd, fail)
        _copy_to_backup(docs, DDS_BACKUP_DIR, dry_run=dry_run)
        total_ins += ins; total_upd += upd; total_fail += fail
    logger.info("── DD Total: inserted=%d  updated=%d  failed=%d", total_ins, total_upd, total_fail)


def push_bd(dry_run: bool = False) -> None:
    """Push BD Final to MongoDB (Forms and Reports only)."""
    logger.info("── BD Final → collection '%s' (%s)", COL_BDS, BD_FINAL_DIR)
    raw_docs = _load_json_files(BD_FINAL_DIR)
    logger.info("   Found %d file(s) in BD directory", len(raw_docs))
    
    docs = []
    for name, doc, path in raw_docs:
        itype = doc.get("type") or _detect_item_type_from_l1(name)
        if itype in ("form", "report"):
            docs.append((name, doc, path))
        else:
            logger.info("[BD Push] Skipping non-form/report item: %s (type=%s)", name, itype)
            
    ins, upd, fail = _upsert_docs(COL_BDS, docs, dry_run=dry_run)
    logger.info("   Mongo Result: inserted=%d  updated=%d  failed=%d", ins, upd, fail)
    _copy_to_backup(docs, BDS_BACKUP_DIR, dry_run=dry_run)


def push_bd_one(screen_name: str, dry_run: bool = False) -> bool:
    """Upsert một S4 file cụ thể vào MongoDB bds — dùng sau khi BD flow hoàn thành."""
    s4_file = BD_FINAL_DIR / f"{screen_name}.json"
    if not s4_file.exists():
        logger.warning("[push_bd_one] S4 file not found: %s", s4_file)
        return False

    try:
        doc = json.loads(s4_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("[push_bd_one] Failed to load %s: %s", s4_file.name, exc)
        return False

    docs = [(screen_name, doc, s4_file)]
    ins, upd, fail = _upsert_docs(COL_BDS, docs, dry_run=dry_run)
    _copy_to_backup(docs, BDS_BACKUP_DIR, dry_run=dry_run)
    logger.info("[push_bd_one] %s → inserted=%d updated=%d failed=%d", screen_name, ins, upd, fail)
    return fail == 0


def push_dd_one(screen_name: str, dry_run: bool = False) -> bool:
    """Upsert một D4 file cụ thể vào MongoDB dds — dùng sau khi DD flow hoàn thành."""
    # Map category → forced type (None = cần L1 lookup)
    _CAT_TO_TYPE = {
        "screen": None,    # form hoặc report — cần L1 lookup
        "report": "report",
        "macro":  "macro",
        "common": "module",
    }

    d4_file: Path | None = None
    category: str = ""
    for cat in ("screen", "report", "macro", "common"):
        candidate = BASE_DIR / "output" / "dd_flow" / cat / "d4_dd_final" / f"{screen_name}.json"
        if candidate.exists():
            d4_file = candidate
            category = cat
            break

    if d4_file is None:
        logger.warning("[push_dd_one] D4 file not found for: %s", screen_name)
        return False

    try:
        doc = json.loads(d4_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("[push_dd_one] Failed to load %s: %s", d4_file.name, exc)
        return False

    forced_type = _CAT_TO_TYPE.get(category)
    extra = {"type": forced_type} if forced_type else None

    docs = [(screen_name, doc, d4_file)]
    ins, upd, fail = _upsert_docs(COL_DDS, docs, dry_run=dry_run, extra_fields=extra)
    _copy_to_backup(docs, DDS_BACKUP_DIR, dry_run=dry_run)
    logger.info("[push_dd_one] %s (category=%s) → inserted=%d updated=%d failed=%d",
                screen_name, category, ins, upd, fail)
    return fail == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push Layer 2 d4_dd_final + s4_bd_final outputs into MongoDB.",
    )
    parser.add_argument(
        "--only",
        choices=["dd", "bd"],
        default=None,
        help="Push only 'dd' (dds collection) or only 'bd' (bds collection). "
             "Default: push both.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files to be pushed without writing to MongoDB.",
    )
    args = parser.parse_args()

    logger.info("MongoDB: %s / db=%s", MONGO_URI, MONGO_DB)
    logger.info("Dry-run: %s", args.dry_run)

    if args.only == "dd":
        push_dd(dry_run=args.dry_run)
    elif args.only == "bd":
        push_bd(dry_run=args.dry_run)
    else:
        push_dd(dry_run=args.dry_run)
        push_bd(dry_run=args.dry_run)

    logger.info("Done.")


if __name__ == "__main__":
    main()
