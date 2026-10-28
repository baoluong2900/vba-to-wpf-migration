"""
Parse exported Microsoft Access macro files (.mac) into structured JSON-compatible dicts.
Skips embedded UI-macro Comment blocks (_AXL); maps common Macro actions to example schema.

Output shape matches mac_example.json (macro_name, source_file, description, steps, references).

Usage:
    python macro_parser.py <folder_or.mac> [--output-dir DIR] [-o file.json] [--stdout] [--encoding ENC]

Default output directory: <project>/output/macro_json/ (one .json per .mac when input is a folder).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
vba_dir = ROOT / "src" / "vba" / "vba_source"
if not vba_dir.exists():
    vba_dir = ROOT / "VBA_Export_All"

DEFAULT_INPUT_DIR = vba_dir / "Macros"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "macros"
FORBIDDEN_FILENAME_CHARS = '\\/:*?"<>|'


def read_mac_text(path: Path) -> str:
    raw = path.read_bytes()
    if len(raw) >= 2 and raw[0] == 0xFF and raw[1] == 0xFE:
        return raw.decode("utf-16-le")
    if len(raw) >= 2 and raw[0] == 0xFE and raw[1] == 0xFF:
        return raw.decode("utf-16-be")
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if encoding.startswith("utf") and "\ufffd" in text:
            continue
        return text
    return raw.decode("utf-8", errors="replace")


def safe_json_stem(name: str) -> str:
    cleaned = "".join(
        "_" if c in FORBIDDEN_FILENAME_CHARS else c for c in name.strip()
    )
    return cleaned if cleaned else "macro"


def unique_output_path(out_dir: Path, stem: str, used_counts: dict[str, int]) -> Path:
    used_counts[stem] = used_counts.get(stem, 0) + 1
    n = used_counts[stem]
    if n == 1:
        return out_dir / f"{stem}.json"
    return out_dir / f"{stem}_{n}.json"


def _unescape_access_string(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n in ('"', "\\"):
                out.append(n)
                i += 2
                continue
            if n in "01234567" and i + 3 < len(s):
                octal = s[i + 1 : i + 4]
                if all(c in "01234567" for c in octal):
                    out.append(chr(int(octal, 8)))
                    i += 4
                    continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _read_concatenated_string(lines: list[str], start_line: int, open_quote_col: int) -> tuple[str, int]:
    def read_until_unescaped_quote(line: str, start: int) -> tuple[str, bool, int]:
        seg: list[str] = []
        j = start
        while j < len(line):
            c = line[j]
            if c == "\\" and j + 1 < len(line):
                seg.append(line[j : j + 2])
                j += 2
                continue
            if c == '"':
                return "".join(seg), True, j
            seg.append(c)
            j += 1
        return "".join(seg), False, -1

    parts: list[str] = []
    li = start_line
    j = open_quote_col + 1
    while li < len(lines):
        line = lines[li]
        chunk, ended, end_quote_col = read_until_unescaped_quote(line, j)
        parts.append(_unescape_access_string(chunk))
        if ended:
            tail = line[end_quote_col + 1 :].strip()
            if not tail and li + 1 < len(lines):
                nxt_line = lines[li + 1]
                nxt = nxt_line.lstrip()
                if nxt.startswith('"'):
                    li += 1
                    j = nxt_line.index('"') + 1
                    continue
            return "".join(parts), li

        li += 1
        if li >= len(lines):
            break
        nxt_line = lines[li]
        nxt = nxt_line.lstrip()
        if nxt.startswith('"'):
            j = nxt_line.index('"') + 1
        else:
            j = 0
    return "".join(parts), max(0, li - 1)


def _parse_block_lines(block_lines: list[str]) -> dict[str, Any]:
    fields: dict[str, Any] = defaultdict(list)
    i = 0
    while i < len(block_lines):
        line = block_lines[i].rstrip("\r\n")
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^\s*(\w+)\s*=\s*", line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        qpos = line.find('"', m.end())
        if qpos < 0:
            i += 1
            continue
        value, end_li = _read_concatenated_string(block_lines, i, qpos)
        i = end_li + 1
        if key == "Argument":
            fields["Arguments"].append(value)
        elif key in ("Condition", "Action", "Comment"):
            fields[key] = value
        else:
            fields[key] = value
    return dict(fields)


def _split_begin_blocks(text: str) -> list[list[str]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[list[str]] = []
    cur: list[str] | None = None
    for line in lines:
        if line.strip() == "Begin":
            cur = []
            continue
        if line.strip() == "End" and cur is not None:
            blocks.append(cur)
            cur = None
            continue
        if cur is not None:
            cur.append(line)
    return blocks


_VIEW_NAMES = {"0": "Form", "1": "Design", "2": "Print Preview", "3": "Datasheet", "4": "PivotTable", "5": "PivotChart", "6": "Layout"}
_QUERY_VIEW_NAMES = {"0": "Datasheet", "1": "Design", "2": "Print Preview", "3": "PivotTable", "4": "PivotChart", "5": "SQL View"}
_WINDOW_MODE = {"0": "Normal", "1": "Hidden", "2": "Icon", "3": "Dialog"}
_OBJECT_TYPE = {"0": "Table", "1": "Query", "2": "Form", "3": "Report", "4": "Macro", "5": "Module"}
_DATA_MODE = {"0": "Add", "1": "Edit", "2": "ReadOnly"}
_SAVE = {"0": "Prompt", "1": "Yes", "2": "No"}


def _map_open_form(args: list[str]) -> dict[str, Any]:
    step: dict[str, Any] = {"action": "OpenForm"}
    if len(args) > 0:
        step["form_name"] = args[0]
    if len(args) > 1:
        step["view"] = _VIEW_NAMES.get(args[1], args[1])
    if len(args) > 5:
        step["window_mode"] = _WINDOW_MODE.get(args[5], args[5])
    return step


def _map_open_query(args: list[str]) -> dict[str, Any]:
    step: dict[str, Any] = {"action": "OpenQuery"}
    if len(args) > 0:
        step["query_name"] = args[0]
    if len(args) > 1:
        step["view"] = _QUERY_VIEW_NAMES.get(args[1], args[1])
    if len(args) > 2:
        step["data_mode"] = _DATA_MODE.get(args[2], args[2])
    return step


def _map_close(args: list[str]) -> dict[str, Any]:
    step: dict[str, Any] = {"action": "Close"}
    if len(args) > 0:
        step["object_type"] = _OBJECT_TYPE.get(args[0], args[0])
    if len(args) > 1:
        step["object_name"] = args[1]
    if len(args) > 2:
        step["save"] = _SAVE.get(args[2], args[2])
    return step


def _step_from_block(f: dict[str, Any]) -> dict[str, Any] | None:
    action = f.get("Action")
    if not action or action == "Comment":
        return None
    args: list[str] = list(f.get("Arguments") or [])
    cond = f.get("Condition")
    if action == "OpenForm":
        step = _map_open_form(args)
    elif action == "OpenQuery":
        step = _map_open_query(args)
    elif action == "RunMacro":
        step = {"action": "RunMacro", "macro_name": args[0] if args else ""}
    elif action == "RunCode":
        step = {"action": "RunCode", "function": args[0] if args else ""}
    elif action == "SetWarnings":
        v = args[0] if args else "0"
        step = {"action": "SetWarnings", "value": v not in ("0", "", "-1")}
    elif action == "Close":
        step = _map_close(args)
    elif action in ("Maximize", "Beep", "StopMacro", "Quit", "SaveRecord"):
        step = {"action": action}
    else:
        step = {"action": action}
        if args:
            step["arguments"] = args
    if cond is not None and cond != "":
        step = {"condition": cond, **step}
    return step


_TABLE_IN_EXPR = re.compile(
    r"(?:DCount|DSum|DAvg|DMin|DMax|DLookup|DFirst|DLast)\s*\(\s*"
    r'(?:"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\')\s*,\s*'
    r'"([^"]+)"',
    re.IGNORECASE,
)


def _collect_references(steps: list[dict[str, Any]]) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {
        "forms": [],
        "queries": [],
        "macros": [],
        "modules": [],
        "vba_calls": [],
        "tables": [],
    }
    seen = {k: set() for k in refs}

    def add(cat: str, val: str) -> None:
        if val and val not in seen[cat]:
            seen[cat].add(val)
            refs[cat].append(val)

    for st in steps:
        act = st.get("action")
        if act == "OpenForm":
            add("forms", str(st.get("form_name", "")))
        elif act == "OpenQuery":
            add("queries", str(st.get("query_name", "")))
        elif act == "Close":
            if str(st.get("object_type", "")) == "Form":
                add("forms", str(st.get("object_name", "")))
            if str(st.get("object_type", "")) == "Query":
                add("queries", str(st.get("object_name", "")))
        elif act == "RunMacro":
            add("macros", str(st.get("macro_name", "")))
        elif act == "RunCode":
            add("vba_calls", str(st.get("function", "")))
        cond = st.get("condition")
        if isinstance(cond, str):
            for m in _TABLE_IN_EXPR.finditer(cond):
                tbl = m.group(3)
                if tbl:
                    add("tables", tbl)
    return refs


def _strip_axl_prefix(value: str) -> str:
    return value[5:] if value.startswith("_AXL:") else value

def parse_mac_text(text: str, source_file: str, macro_name: str | None = None) -> dict[str, Any]:
    name = macro_name if macro_name else Path(source_file).stem
    blocks = _split_begin_blocks(text)
    steps: list[dict[str, Any]] = []
    raw_xml_parts: list[str] = []
    for bl in blocks:
        f = _parse_block_lines(bl)
        comment_value = f.get("Comment") or ""
        if comment_value.startswith("_AXL:"):
            raw_xml_parts.append(_strip_axl_prefix(comment_value))
        if not f.get("Action") and comment_value.startswith("_AXL:"):
            continue
        if not f.get("Action"):
            continue
        st = _step_from_block(f)
        if st:
            steps.append(st)
    return {
        "macro_name": name,
        "source_file": Path(source_file).name,
        "description": "",
        "raw_xml": "".join(raw_xml_parts),
        "steps": steps,
        "references": _collect_references(steps),
    }


def parse_mac_file(path: Path, encoding: str | None = None) -> dict[str, Any]:
    if encoding:
        raw = path.read_text(encoding=encoding, errors="replace")
    else:
        raw = read_mac_text(path)
    return parse_mac_text(raw, source_file=str(path.name), macro_name=path.stem)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert Access .mac exports to JSON (mac_example.json shape)."
    )
    ap.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=DEFAULT_INPUT_DIR,
        help=f"Path to one .mac file or a folder of .mac files (default: {DEFAULT_INPUT_DIR})",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for per-macro JSON files (default: {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Exact output path (single .mac only); overrides --output-dir",
    )
    ap.add_argument(
        "--stdout",
        action="store_true",
        help="Print JSON to stdout (single .mac only)",
    )
    ap.add_argument(
        "--encoding",
        default=None,
        help="Force text encoding; default: auto-detect (utf-8, utf-16-le BOM, cp932, …)",
    )
    args = ap.parse_args()
    inp: Path = args.input
    enc: str | None = args.encoding

    if inp.is_dir():
        items = sorted(inp.glob("*.mac"))
        if not items:
            # An Access app without macros is fine — don't fail the batch pipeline.
            print(f"[WARN] No .mac files in {inp} — nothing to parse.", file=sys.stderr)
            return 0
        out_dir: Path = args.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        if args.output:
            print("-o applies only to a single .mac file", file=sys.stderr)
            return 2
        if args.stdout:
            print("--stdout applies only to a single .mac file", file=sys.stderr)
            return 2
        used: dict[str, int] = {}
        failures = 0
        for p in items:
            try:
                data = parse_mac_file(p, enc)
                out = json.dumps(data, ensure_ascii=False, indent=4) + "\n"
                stem = safe_json_stem(p.stem)
                out_path = unique_output_path(out_dir, stem, used)
                out_path.write_text(out, encoding="utf-8")
                print(f"Wrote {out_path.resolve()}", file=sys.stderr)
            except OSError as e:
                failures += 1
                print(f"Error writing {p}: {e}", file=sys.stderr)
            except Exception as e:
                failures += 1
                print(f"Error parsing {p}: {e}", file=sys.stderr)
        return 1 if failures else 0

    if not inp.is_file():
        print(f"Not found: {inp}", file=sys.stderr)
        return 1
    if not inp.name.lower().endswith(".mac"):
        print(f"Expected .mac file: {inp}", file=sys.stderr)
        return 1

    try:
        one = parse_mac_file(inp, enc)
    except Exception as e:
        print(f"Error parsing {inp}: {e}", file=sys.stderr)
        return 1
    text = json.dumps(one, ensure_ascii=False, indent=4)
    if args.stdout:
        print(text)
        return 0
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.output.resolve()}", file=sys.stderr)
        return 0
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_json_stem(inp.stem)}.json"
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"Wrote {out_path.resolve()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
