"""
extract_modules_export.py
-------------------------
Parse toàn bộ file .bas trong VBA_Export_All/Modules thành JSON
(mỗi file .bas → 1 file JSON riêng tại output/schema/modules/<ModuleName>.json)
theo schema:

{
  "module_name": "...",
  "source_file": "....bas",
  "options": { "compare": "Database|Text|Binary|null", "explicit": bool,
                "base": 0|1 (optional), "private_module": bool (optional) },
  "user_types":  [ { "name", "kind": "struct|enum", "visibility", "fields"|"members" } ],
  "constants":   [ { "name", "type", "visibility", "value" } ],
  "functions":   [ { "handler", "visibility", "type", "input", "output", "code" } ],
  "variables":   [ { "name", "type", "visibility", "comment"? } ]
}

Chạy:  python script/extract_modules_export.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[5]
vba_dir = ROOT / "src" / "vba" / "vba_source"
if not vba_dir.exists():
    vba_dir = ROOT / "VBA_Export_All"

MOD_DIR = vba_dir / "Modules"
OUT_DIR = ROOT / "data" / "modules"


# ---------- encoding helpers ----------
def read_bas(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ---------- line preprocessing ----------
def split_lines(text: str) -> list[str]:
    # giữ nguyên \r\n để khi emit body giữ đúng format cũ
    return text.replace("\r\n", "\n").split("\n")


def strip_inline_comment(line: str) -> str:
    """Bỏ comment ' ở cuối dòng (không bên trong chuỗi)."""
    out = []
    in_str = False
    for ch in line:
        if ch == '"':
            in_str = not in_str
            out.append(ch)
        elif ch == "'" and not in_str:
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def is_blank_or_comment(line: str) -> bool:
    s = line.strip()
    return s == "" or s.startswith("'")


def join_continuation(lines: list[str], idx: int) -> tuple[str, int]:
    """Gom dòng bắt đầu tại idx + các dòng nối bằng ' _'. Trả (logical_line, next_idx)."""
    buf = lines[idx]
    i = idx
    # Trong VBA, dấu nối là '_ ' ở cuối dòng (sau khoảng trắng). Phải loại comment trước.
    while True:
        code = strip_inline_comment(buf).rstrip()
        if code.endswith(" _"):
            # bỏ dấu nối
            buf = code[:-2].rstrip() + " "
            i += 1
            if i >= len(lines):
                break
            buf += lines[i]
        else:
            break
    return buf, i


# ---------- regex patterns ----------
RE_OPT_COMPARE = re.compile(r"^\s*Option\s+Compare\s+(Binary|Text|Database)\s*$", re.I)
RE_OPT_EXPLICIT = re.compile(r"^\s*Option\s+Explicit\s*$", re.I)
RE_OPT_BASE = re.compile(r"^\s*Option\s+Base\s+(\d+)\s*$", re.I)
RE_OPT_PRIVATE_MODULE = re.compile(r"^\s*Option\s+Private\s+Module\s*$", re.I)

RE_TYPE_START = re.compile(r"^\s*(Public|Private)?\s*Type\s+(\w+)\s*$", re.I)
RE_TYPE_END = re.compile(r"^\s*End\s+Type\s*$", re.I)

RE_ENUM_START = re.compile(r"^\s*(Public|Private)?\s*Enum\s+(\w+)\s*$", re.I)
RE_ENUM_END = re.compile(r"^\s*End\s+Enum\s*$", re.I)

# Const: `[Public|Private|Global] Const NAME [As TYPE] = VALUE`
RE_CONST = re.compile(
    r"^\s*(Public|Private|Global)?\s*Const\s+(\w+)\s*(?:As\s+([\w\.]+))?\s*=\s*(.+?)\s*$",
    re.I,
)

# Declare: `[Public|Private] Declare [PtrSafe] Function|Sub NAME Lib "..." [Alias "..."] (params) [As RET]`
RE_DECLARE = re.compile(
    r"^\s*(Public|Private)?\s*Declare\s+(?:PtrSafe\s+)?(Function|Sub)\s+"
    r"(\w+)\s+Lib\s+\"([^\"]+)\""
    r"(?:\s+Alias\s+\"([^\"]+)\")?"
    r"\s*\((.*)\)"
    r"(?:\s+As\s+([\w\.\(\)]+(?:\s*\*\s*\d+)?))?\s*$",
    re.I,
)

# Function/Sub start: `[Public|Private|Friend|Static] Function|Sub NAME (params) [As RET]`
RE_FUNC_START = re.compile(
    r"^\s*(Public|Private|Friend|Static)?\s*(?:Static\s+)?(Function|Sub)\s+"
    r"([^\s(]+)"
    r"\s*\((.*)\)"
    r"(?:\s+As\s+([\w\.\(\)]+(?:\s*\*\s*\d+)?))?\s*$",
    re.I,
)
RE_FUNC_END = re.compile(r"^\s*End\s+(Function|Sub)\s*$", re.I)

# Type/Enum field: `NAME [(bounds)] As TYPE` hoặc enum member: `NAME [= VALUE]`
RE_TYPE_FIELD = re.compile(
    r"^\s*(\w+)(?:\s*\(\s*([^)]*?)\s*\))?\s+As\s+([\w\.]+(?:\s*\*\s*\d+)?)\s*$",
    re.I,
)
RE_ENUM_MEMBER = re.compile(r"^\s*(\w+)\s*(?:=\s*(.+?))?\s*$")

# Module-level variable: `[Public|Private|Dim|Global] NAME As TYPE`
RE_MOD_VAR = re.compile(
    r"^\s*(Public|Private|Dim|Global)\s+(\w+)\s+As\s+([\w\.]+(?:\s*\*\s*\d+)?)\s*$",
    re.I,
)


# ---------- parser ----------
def parse_module(module_name: str, source_file: str, src: str) -> dict:
    lines = split_lines(src)

    options: dict = {"compare": None, "explicit": False}
    user_types: list[dict] = []
    constants: list[dict] = []
    functions: list[dict] = []
    variables: list[dict] = []

    i = 0
    n = len(lines)

    def norm_vis(v: Optional[str], default: str = "public") -> str:
        return (v or default).lower()

    while i < n:
        raw_line = lines[i]
        stripped = strip_inline_comment(raw_line).strip()

        # bỏ dòng trống / comment
        if is_blank_or_comment(raw_line) or stripped == "":
            i += 1
            continue

        # --- Options ---
        m = RE_OPT_COMPARE.match(stripped)
        if m:
            options["compare"] = m.group(1).capitalize()
            i += 1
            continue
        if RE_OPT_EXPLICIT.match(stripped):
            options["explicit"] = True
            i += 1
            continue
        m = RE_OPT_BASE.match(stripped)
        if m:
            options["base"] = int(m.group(1))
            i += 1
            continue
        if RE_OPT_PRIVATE_MODULE.match(stripped):
            options["private_module"] = True
            i += 1
            continue

        # --- Type ... End Type ---
        m = RE_TYPE_START.match(stripped)
        if m:
            vis = norm_vis(m.group(1), "private")
            tname = m.group(2)
            fields: list[dict] = []
            i += 1
            while i < n and not RE_TYPE_END.match(strip_inline_comment(lines[i]).strip()):
                line = strip_inline_comment(lines[i]).strip()
                if line and not line.startswith("'"):
                    fm = RE_TYPE_FIELD.match(line)
                    if fm:
                        field: dict = {"name": fm.group(1), "type": fm.group(3).strip()}
                        if fm.group(2):
                            field["array_bounds"] = fm.group(2).strip()
                        fields.append(field)
                i += 1
            user_types.append(
                {
                    "name": tname,
                    "kind": "struct",
                    "visibility": vis,
                    "fields": fields,
                }
            )
            i += 1
            continue

        # --- Enum ... End Enum ---
        m = RE_ENUM_START.match(stripped)
        if m:
            vis = norm_vis(m.group(1), "public")
            ename = m.group(2)
            members: list[dict] = []
            i += 1
            while i < n and not RE_ENUM_END.match(strip_inline_comment(lines[i]).strip()):
                line = strip_inline_comment(lines[i]).strip()
                if line and not line.startswith("'"):
                    em = RE_ENUM_MEMBER.match(line)
                    if em:
                        member = {"name": em.group(1)}
                        if em.group(2) is not None:
                            member["value"] = em.group(2).strip()
                        members.append(member)
                i += 1
            user_types.append(
                {
                    "name": ename,
                    "kind": "enum",
                    "visibility": vis,
                    "members": members,
                }
            )
            i += 1
            continue

        # --- logical line (join continuation) for multi-line statements ---
        logical, last_idx = join_continuation(lines, i)
        logical_code = strip_inline_comment(logical).strip()

        # --- Const (must check before var because `Const X As Y = Z`)---
        m = RE_CONST.match(logical_code)
        if m:
            vis_raw = m.group(1)
            vis = "public" if (vis_raw or "").lower() == "global" else norm_vis(vis_raw, "private")
            const_item = {
                "name": m.group(2),
                "type": (m.group(3) or "Variant"),
                "visibility": vis,
                "value": m.group(4).strip(),
            }
            constants.append(const_item)
            i = last_idx + 1
            continue

        # --- Declare Function/Sub ---
        m = RE_DECLARE.match(logical_code)
        if m:
            vis = norm_vis(m.group(1), "public")
            decl_kind = m.group(2).capitalize()  # Function | Sub
            fname = m.group(3)
            lib = m.group(4)
            alias = m.group(5)
            params = (m.group(6) or "").strip()
            ret = (m.group(7) or "").strip() if decl_kind == "Function" else ""
            handler = f'{fname} Lib "{lib}"'
            if alias:
                handler += f' Alias "{alias}"'
            functions.append(
                {
                    "handler": handler,
                    "visibility": vis,
                    "type": f"Declare {decl_kind}",
                    "input": params,
                    "output": ret,
                    "code": "",
                }
            )
            i = last_idx + 1
            continue

        # --- Function/Sub ... End Function/Sub ---
        m = RE_FUNC_START.match(logical_code)
        if m:
            vis = norm_vis(m.group(1), "public")
            ftype = m.group(2).capitalize()
            fname = m.group(3)
            params = (m.group(4) or "").strip()
            ret = (m.group(5) or "").strip() if ftype == "Function" else ""

            # collect body: các dòng RAW từ last_idx+1 đến End Function/Sub
            body_lines: list[str] = []
            j = last_idx + 1
            while j < n:
                if RE_FUNC_END.match(strip_inline_comment(lines[j]).strip()):
                    break
                body_lines.append(lines[j])
                j += 1
            # join giữ \r\n theo original
            body = "\r\n".join(body_lines).rstrip("\r\n ")
            # bỏ dòng trống thuần ở đầu/cuối
            body = body.strip("\r\n")

            functions.append(
                {
                    "handler": fname,
                    "visibility": vis,
                    "type": ftype,
                    "input": params,
                    "output": ret,
                    "code": body,
                }
            )
            i = j + 1
            continue

        # --- Module-level variable ---
        m = RE_MOD_VAR.match(logical_code)
        if m:
            vis_raw = m.group(1).lower()
            vis = "public" if vis_raw in ("public", "global") else "private"
            variables.append(
                {
                    "name": m.group(2),
                    "type": m.group(3).strip(),
                    "visibility": vis,
                }
            )
            i = last_idx + 1
            continue

        # dòng chưa khớp pattern nào -> bỏ qua (attribute, comment lạ, v.v.)
        i = last_idx + 1

    mod: dict = {
        "module_name": module_name,
        "source_file": source_file,
        "options": options,
        "user_types": user_types,
        "constants": constants,
        "functions": functions,
        "variables": variables,
    }
    return mod


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Convert Access .bas exports to JSON.")
    ap.add_argument("input_dir", nargs="?", type=Path, default=MOD_DIR, help=f"Source modules dir (default: {MOD_DIR})")
    ap.add_argument("output_dir", nargs="?", type=Path, default=OUT_DIR, help=f"Output modules JSON dir (default: {OUT_DIR})")
    args = ap.parse_args()

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    bas_files = sorted(input_dir.glob("*.bas"))
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output dir: {output_dir}")
    for p in bas_files:
        src = read_bas(p)
        mod = parse_module(p.stem, p.name, src)
        out_path = output_dir / f"{p.stem}.json"
        out_path.write_text(
            json.dumps(mod, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"  - {mod['module_name']:25s} -> {out_path.name:30s} "
            f"types={len(mod['user_types']):2d}  "
            f"const={len(mod['constants']):2d}  "
            f"funcs={len(mod['functions']):3d}  "
            f"vars={len(mod['variables']):2d}"
        )
    print(f"Parsed {len(bas_files)} modules.")


if __name__ == "__main__":
    main()
