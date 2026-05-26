#!/usr/bin/env python3
"""
table_parser.py

Read VBA_Export_All/Tables/AllColumns.csv and emit one JSON file per table,
matching table_example.json: table_name, description, columns[].

Column mapping (AllColumns.csv → JSON): CSV PhysicalName holds Japanese labels → logical_name;
CSV LogicalName holds English / physical identifiers → physical_name.

Usage:
    python table_parser.py [AllColumns.csv] [--output-dir <dir>]

Default CSV: <project>/VBA_Export_All/Tables/AllColumns.csv
Default out: <project>/output/table_json/
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
vba_dir = ROOT / "src" / "VBA" / "vba_source"
if not vba_dir.exists():
    vba_dir = ROOT / "VBA_Export_All"

DEFAULT_CSV = vba_dir / "Tables" / "AllColumns.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "tables"

FORBIDDEN_FILENAME = '\\/:*?"<>|'


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if encoding.startswith("utf") and "\ufffd" in text:
            continue
        break
    else:
        text = raw.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], []
    fieldnames = [h.strip() for h in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for row in reader:
        norm = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        rows.append(norm)
    return fieldnames, rows


def safe_json_stem(name: str) -> str:
    cleaned = "".join("_" if c in FORBIDDEN_FILENAME else c for c in name.strip())
    return cleaned if cleaned else "table"


def unique_output_path(out_dir: Path, stem: str, used: dict[str, int]) -> Path:
    used[stem] = used.get(stem, 0) + 1
    n = used[stem]
    if n == 1:
        return out_dir / f"{stem}.json"
    return out_dir / f"{stem}_{n}.json"


def group_rows_by_table(rows: list[dict[str, str]]) -> "OrderedDict[str, list[dict[str, str]]]":
    groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in rows:
        tname = (row.get("TableName") or "").strip()
        if not tname:
            continue
        groups.setdefault(tname, []).append(row)
    return groups


def row_to_column(row: dict[str, str]) -> dict[str, str]:
    return {
        "logical_name": (row.get("LogicalName") or "").strip(),
        "physical_name": (row.get("PhysicalName") or "").strip(),
        "data_type": (row.get("DataType") or "").strip(),
        "length": (row.get("Length") or "").strip(),
        "required": (row.get("Required") or "").strip(),
    }


def build_table_json(table_name: str, table_rows: list[dict[str, str]]) -> dict:
    return {
        "table_name": table_name,
        "description": "",
        "columns": [row_to_column(r) for r in table_rows],
    }


def parse_all_columns_csv(csv_path: Path, out_dir: Path) -> int:
    fieldnames, rows = read_csv_rows(csv_path)
    expected = {"TableName", "LogicalName", "PhysicalName", "DataType", "Length", "Required"}
    keys = set(fieldnames)
    if not keys >= expected:
        missing = expected - keys
        print(f"CSV missing columns: {sorted(missing)}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    groups = group_rows_by_table(rows)
    used_stems: dict[str, int] = {}
    errors = 0
    for tname, trows in groups.items():
        data = build_table_json(tname, trows)
        stem = safe_json_stem(tname)
        out_path = unique_output_path(out_dir, stem, used_stems)
        try:
            out_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=4) + "\n",
                encoding="utf-8",
            )
            print(f"Wrote {out_path.resolve()}", file=sys.stderr)
        except OSError as e:
            errors += 1
            print(f"Error writing {out_path}: {e}", file=sys.stderr)
    if errors:
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Split AllColumns.csv into per-table JSON files.")
    ap.add_argument(
        "csv_path",
        type=Path,
        nargs="?",
        default=DEFAULT_CSV,
        help=f"Path to AllColumns.csv (default: {DEFAULT_CSV})",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = ap.parse_args()
    if not args.csv_path.is_file():
        print(f"Not found: {args.csv_path}", file=sys.stderr)
        return 1
    return parse_all_columns_csv(args.csv_path, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
