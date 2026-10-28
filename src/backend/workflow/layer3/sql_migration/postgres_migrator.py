#!/usr/bin/env python3
"""
postgres_migrator.py
--------------------
Create PostgreSQL tables from the Access schemas Layer 1 stored in MongoDB (``tables``).

For each table it runs ``DROP TABLE IF EXISTS … CASCADE`` followed by the CREATE TABLE from
table_converter.py, in one ``psql -c`` call (one implicit transaction, so a failed CREATE also
rolls back its DROP). Connection settings come from src/backend/common/config.py
(env → config.json → default).

Usage:
    python postgres_migrator.py                         # migrate every table
    python postgres_migrator.py --dry-run               # print the SQL, execute nothing
    python postgres_migrator.py --dry-run --output schema.sql
    python postgres_migrator.py --table TBL_Users       # one table only
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
for _path in (BACKEND_DIR, BACKEND_DIR / "workflow", BACKEND_DIR / "workflow" / "layer2"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from common.config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASS, POSTGRES_PORT, POSTGRES_USER
from db.mongo_client import get_db

from layer3.sql_migration.table_converter import POSTGRESQL, convert_table_to_ddl, quote_identifier

# Table names end up inside psql commands: allow only word characters of the scripts Access
# designs use (ASCII, kana, kanji) — no quotes, semicolons or whitespace.
_SAFE_TABLE_NAME = re.compile(r"[A-Za-z0-9_぀-ゟ゠-ヿ一-龯]+")
_JAPANESE = re.compile(r"[぀-ゟ゠-ヿ一-龯]")


def _psql(sql: str) -> None:
    env = os.environ.copy()
    if POSTGRES_PASS:
        env["PGPASSWORD"] = POSTGRES_PASS
    subprocess.run(
        ["psql", "-h", POSTGRES_HOST, "-p", str(POSTGRES_PORT), "-U", POSTGRES_USER, "-d", POSTGRES_DB, "-c", sql],
        env=env, capture_output=True, text=True, check=True,
    )


def migrate_to_postgres(dry_run: bool = False, only_table: str | None = None, output: Path | None = None) -> int:
    """Migrate the tables; return how many failed (0 means everything that was attempted succeeded)."""
    tables = list(get_db()["tables"].find({"table_name": only_table} if only_table else {}, {"_id": 0}))
    if not tables:
        print("[POSTGRES MIGRATOR] No matching tables in the MongoDB 'tables' collection. Nothing to do.")
        return 0
    if not dry_run and shutil.which("psql") is None:
        print("[POSTGRES MIGRATOR] 'psql' is not on PATH — install the PostgreSQL client tools or use --dry-run.")
        return len(tables)

    target = "DRY RUN, nothing is executed" if dry_run else f"{POSTGRES_USER}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    print(f"[POSTGRES MIGRATOR] {len(tables)} table(s) → {target}")

    script: list[str] = []
    migrated = skipped = failed = 0
    for table in tables:
        name = table.get("table_name")
        if not name:
            continue
        if not _SAFE_TABLE_NAME.fullmatch(name):
            print(f"[SKIP] '{name}': unsafe table name.")
            skipped += 1
            continue

        if _JAPANESE.search(name):
            # Japanese-named tables are not migrated; remove leftovers from earlier runs.
            drop = f'DROP TABLE IF EXISTS "{name.lower()}" CASCADE;'
            script.append(f"-- {name}: skipped (Japanese table name)\n{drop}")
            print(f"[SKIP] '{name}': Japanese table names are not migrated to PostgreSQL.")
            skipped += 1
            if not dry_run:
                try:
                    _psql(drop)
                except subprocess.CalledProcessError as e:
                    print(f"[WARN] Could not drop leftover table '{name}': {e.stderr.strip()}")
            continue

        try:
            ddl = convert_table_to_ddl(table, POSTGRESQL)
        except ValueError as e:
            print(f"[ERROR] '{name}': {e}")
            failed += 1
            continue

        sql = f"DROP TABLE IF EXISTS {quote_identifier(name, POSTGRESQL)} CASCADE;\n\n{ddl}"
        script.append(f"-- {name}\n{sql}")
        print(f"\n--- {name} ---\n{ddl}")
        if dry_run:
            continue
        try:
            _psql(sql)
            print(f"[OK] '{name}' migrated.")
            migrated += 1
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] '{name}': psql failed\n{e.stderr.strip()}")
            failed += 1

    if output:
        output.write_text("\n\n".join(script) + "\n", encoding="utf-8")
        print(f"[POSTGRES MIGRATOR] SQL script written to {output}")
    print(f"[POSTGRES MIGRATOR] Done: {migrated} migrated, {skipped} skipped, {failed} failed.")
    return failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create PostgreSQL tables from the Access schemas in MongoDB.")
    parser.add_argument("--dry-run", action="store_true", help="print the SQL without executing anything")
    parser.add_argument("--table", help="migrate a single table by name")
    parser.add_argument("--output", type=Path, help="also write the generated SQL script to this file")
    args = parser.parse_args(argv)
    return 1 if migrate_to_postgres(dry_run=args.dry_run, only_table=args.table, output=args.output) else 0


if __name__ == "__main__":
    sys.exit(main())
