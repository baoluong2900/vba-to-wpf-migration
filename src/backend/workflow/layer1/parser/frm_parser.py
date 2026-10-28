#!/usr/bin/env python3
"""
frm_parser.py

Converts Access .frm exports to structured JSON (Format / Data / Event / Other).

Usage:
    python frm_parser.py <input_dir> <output_dir> [--config PATH]   # batch
    python frm_parser.py <file.frm> [--output OUT.json] [--config PATH]  # single file

Replaces the former frm_parser_all_no_comment.py and frm_parser_one_no_comment.py.
"""

import argparse
import fnmatch
import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
vba_dir = ROOT / "src" / "vba" / "vba_source"
if not vba_dir.exists():
    vba_dir = ROOT / "VBA_Export_All"

DEFAULT_INPUT_DIR = vba_dir / "Forms"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "forms"


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# File-level metadata lines that exist before Begin Report/Form - skip all
TOP_LEVEL_SKIP = frozenset(
    {"Version", "VersionRequired", "PublishOption", "Checksum"}
)

# Properties with no analysis value - skip them everywhere
ALWAYS_SKIP = frozenset(
    {
        "RecSrcDt",
        "LayoutCachedLeft",
        "LayoutCachedTop",
        "LayoutCachedWidth",
        "LayoutCachedHeight",
        "TabularCharSet",
        "NoSaveCTIWhenDisabled",
        "DatasheetGridlinesBehavior",
        "DatasheetFontHeight",
        "DatasheetFontName",
        "DatasheetAlternateBackColor",
        "DatasheetGridlinesColor12",
        "DatasheetGridlinesColor",
        "PrtMip",
        "PrtDevMode",
        "PrtDevNames",
        "PrtDevModeW",
        "PrtDevNamesW",
        "PictureData",
    }
)

# Access control block-type names that represent actual UI controls
CONTROL_TYPES = frozenset(
    {
        "Subform",
        "PageBreak",
        "Label",
        "TextBox",
        "ComboBox",
        "ListBox",
        "CheckBox",
        "OptionButton",
        "CommandButton",
        "Image",
        "Line",
        "Rectangle",
        "OptionGroup",
        "ObjectFrame",
        "BoundObjectFrame",
        "Attachment",
        "CustomControl",
        "ToggleButton",
        "UnboundObjectFrame",
    }
)

# Form/Report layout bands: controls under these blocks get item["nodekey"] (lowercase type).
LAYOUT_BAND_TYPES = frozenset(
    {
        "FormHeader",
        "FormFooter",
        "PageHeader",
        "PageFooter",
        "Section",
        "ReportHeader",
        "ReportFooter",
    }
)

_HEURISTIC_MACRO_NAME = re.compile(r"^M\d+_", re.I)


def _guid_blob_to_canonical_string(guid_val: object) -> str | None:
    """Access GUID blob (0x + 32 hex digits) to standard UUID string."""
    if not isinstance(guid_val, str):
        return None
    h = guid_val.strip()
    if h.lower().startswith("0x"):
        h = h[2:]
    h = h.replace(" ", "")
    if len(h) != 32:
        return None
    try:
        return str(uuid.UUID(bytes_le=bytes.fromhex(h)))
    except ValueError:
        return None


def item_key_from_guid_or_name(props: dict, access_name: str) -> str:
    """JSON item key: design-time GUID when present, else control Name."""
    g = _guid_blob_to_canonical_string(props.get("GUID"))
    if g:
        return g
    return access_name if access_name else ""


# --------------------------------------------------------------------------- #
# Value conversion
# --------------------------------------------------------------------------- #


def _notdefaults_value_for_key(prop_key: str, notdefaults: dict | None) -> str | None:
    """Return config string for property key; keys match case-insensitively."""
    if not notdefaults or not prop_key:
        return None
    if prop_key in notdefaults:
        v = notdefaults[prop_key]
        return v if isinstance(v, str) else str(v)
    low = prop_key.lower()
    for k, v in notdefaults.items():
        if isinstance(k, str) and k.lower() == low:
            return v if isinstance(v, str) else str(v)
    return None


def _coerce_notdefault_replacement(mapped: str) -> str | bool:
    """Map NotDefaults string to bool or keep non-empty literal; '' stays ''."""
    s = mapped.strip()
    if s == "":
        return "NotDefault"
    sl = s.lower()
    if sl == "true":
        return True
    if sl == "false":
        return False
    return mapped


def parse_value(
    raw: str,
    prop_key: str | None = None,
    notdefaults: dict | None = None,
):
    """
    Convert a raw FRM property value string to a typed Python value.

    NotDefault uses parser_config.json "NotDefaults" when provided
    (case-insensitive key); missing keys become the literal "notdefault". Access -1 is True.
    """
    v = raw.strip()

    if v == "NotDefault":
        mapped = _notdefaults_value_for_key(prop_key or "", notdefaults)
        if mapped is not None:
            return _coerce_notdefault_replacement(mapped)
        return "notdefault"
    if v == "True":
        return True
    if v == "False":
        return False
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1].replace('""', '"')
    if v == "-1":
        return True

    try:
        if "." in v and not v.startswith("0x"):
            return float(v)
        return int(v)
    except ValueError:
        return v


# --------------------------------------------------------------------------- #
# Adjacent VBA string literals (split across .frm lines)
# --------------------------------------------------------------------------- #


def _split_adjacent_string_literals(s: str) -> list[str] | None:
    """
    Parse a sequence of VBA string literals separated by whitespace.
    Returns inner contents (quotes unescaped per VBA). None if the line is not
    only literals + whitespace (e.g. contains Name = ...).
    """
    s = s.strip()
    if not s:
        return None
    parts: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        if s[i] != '"':
            return None
        i += 1
        chunk: list[str] = []
        while i < n:
            if s[i] == '"':
                if i + 1 < n and s[i + 1] == '"':
                    chunk.append('"')
                    i += 2
                    continue
                i += 1
                break
            chunk.append(s[i])
            i += 1
        else:
            return None
        parts.append("".join(chunk))
    return parts


# --------------------------------------------------------------------------- #
# FRM parser
# --------------------------------------------------------------------------- #


class FrmParser:
    """Line-by-line, stack-based parser for Access .frm export files."""

    def __init__(self, text: str, notdefaults: dict | None = None) -> None:
        self.lines = text.splitlines()
        self.pos = 0
        self.notdefaults = notdefaults

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def parse(self) -> dict:
        """
        Parse the entire FRM file.

        Returns:
            {
                "root_type": "Report" | "Form",
                "root_block": { type, props, children },
                "vba": <str>
            }
        """
        root_type = None
        root_block = None
        vba_lines: list[str] = []
        in_vba = False

        while self.pos < len(self.lines):
            raw = self.lines[self.pos]
            line = raw.strip()

            if in_vba:
                vba_lines.append(raw.rstrip())
                self.pos += 1
                continue

            if not line:
                self.pos += 1
                continue

            if line == "CodeBehindForm":
                in_vba = True
                self.pos += 1
                continue

            begin_root = re.match(r"^Begin\s+(Report|Form)\s*$", line)
            if begin_root:
                root_type = begin_root.group(1)
                self.pos += 1
                root_block = self._parse_block(root_type)
                continue

            # Top-level metadata (Version, Checksum, etc.) - skip
            self.pos += 1

        return {
            "root_type": root_type,
            "root_block": root_block,
            "vba": "\n".join(vba_lines).strip(),
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _merge_adjacent_string_lines(self, first_line_val: str) -> str:
        """
        Concatenate VBA-style adjacent string literals when Access splits them
        across lines (e.g. long ControlSource). self.pos must already point to
        the line after the property line. Leaves non-quoted values unchanged.
        """
        val = first_line_val.strip()
        parts = _split_adjacent_string_literals(val)
        if parts is None:
            return val
        while self.pos < len(self.lines):
            raw = self.lines[self.pos]
            stripped = raw.strip()
            if not stripped:
                self.pos += 1
                continue
            cont = _split_adjacent_string_literals(stripped)
            if cont is None:
                break
            parts.extend(cont)
            self.pos += 1
        inner = "".join(parts)
        return '"' + inner.replace('"', '""') + '"'

    def _parse_block(self, block_type: str | None) -> dict:
        """
        Parse lines inside a Begin...End block recursively.

        Returns a dict with keys: type, props, children.
        """
        result: dict = {"type": block_type, "props": {}, "children": []}

        while self.pos < len(self.lines):
            raw = self.lines[self.pos]
            line = raw.strip()

            if not line:
                self.pos += 1
                continue

            # Close current block
            if line == "End":
                self.pos += 1
                return result

            # Named child block: Begin SomeType
            named_begin = re.match(r"^Begin\s+(\S+)\s*$", line)
            if named_begin:
                child_type = named_begin.group(1)
                self.pos += 1
                child = self._parse_block(child_type)
                result["children"].append(child)
                continue

            # Unnamed child block: Begin (alone)
            if line == "Begin":
                self.pos += 1
                child = self._parse_block(None)
                result["children"].append(child)
                continue

            # Multi-line binary blob: Key = Begin ... End
            blob_match = re.match(r"^(\w+)\s*=\s*Begin\s*$", line)
            if blob_match:
                key = blob_match.group(1)
                self.pos += 1
                hex_parts: list[str] = []
                while self.pos < len(self.lines):
                    inner = self.lines[self.pos].strip()
                    self.pos += 1
                    if inner == "End":
                        break
                    inner = inner.rstrip(" ,")
                    hex_parts.append(inner[2:] if inner.startswith("0x") else inner)

                if key not in ALWAYS_SKIP:
                    result["props"][key] = "0x" + "".join(hex_parts).upper()
                continue

            # Simple property: Key = Value (or Key =Value)
            prop_match = re.match(r"^(\w+)\s*=\s*(.*)$", line)
            if prop_match:
                key = prop_match.group(1)
                val_str = prop_match.group(2).strip()
                self.pos += 1
                if key not in ALWAYS_SKIP:
                    val_str = self._merge_adjacent_string_lines(val_str)
                    result["props"][key] = parse_value(
                        val_str, key, self.notdefaults
                    )
                continue

            # Unrecognised line - skip
            self.pos += 1

        return result


# --------------------------------------------------------------------------- #
# VBA code-behind extraction
# --------------------------------------------------------------------------- #


def _extract_routine(
    lines: list[str],
    start_idx: int,
    kind: str,
    end_marker: str,
) -> tuple[str, str, str, int] | None:
    """
    If lines[start_idx] starts a Public/Private Sub or Function, return
    (handler_name, full_source, visibility, index_after_end).

    Access form/report modules do not nest Sub inside Sub; the first
    matching end_marker closes the routine.
    """
    if kind == "Sub":
        pattern = r"^\s*(Private|Public)\s+Sub\s+(\w+)\s*\("
    else:
        pattern = r"^\s*(Private|Public)\s+Function\s+(\w+)\s*\("
    m = re.match(pattern, lines[start_idx], re.IGNORECASE)
    if not m:
        return None
    visibility = m.group(1).lower()
    handler = m.group(2)
    i = start_idx + 1
    end_re = re.compile(rf"^\s*{end_marker}\s*$", re.IGNORECASE)
    while i < len(lines):
        if end_re.match(lines[i]):
            block = "\n".join(lines[start_idx : i + 1])
            return handler, block, visibility, i + 1
        i += 1
    return handler, "\n".join(lines[start_idx:]), visibility, len(lines)


def _visibility_from_line(line: str) -> str:
    if re.match(r"^\s*Public\b", line, re.IGNORECASE):
        return "public"
    if re.match(r"^\s*Private\b", line, re.IGNORECASE):
        return "private"
    return "public"


def _declare_api_name(line: str) -> str | None:
    m = re.search(
        r"\bDeclare\s+(?:PtrSafe\s+)?(?:Sub|Function)\s+(\w+)", line, re.IGNORECASE
    )
    return m.group(1) if m else None


def _declare_handler_string(line: str) -> str:
    """Build handler label: name, Lib "dll", and optional Alias "symbol"."""
    s = line.strip()
    m = re.search(
        r"\bDeclare\s+(?:PtrSafe\s+)?(?:Sub|Function)\s+(\w+)\s+",
        s,
        re.IGNORECASE,
    )
    if not m:
        return _declare_api_name(s) or ""
    name = m.group(1)
    lib_m = re.search(r'\bLib\s+"([^"]*)"', s, re.IGNORECASE)
    lib = lib_m.group(1) if lib_m else ""
    parts = [f'{name} Lib "{lib}"']
    alias_m = re.search(r'\bAlias\s+"([^"]*)"', s, re.IGNORECASE)
    if alias_m:
        parts.append(f'Alias "{alias_m.group(1)}"')
    return " ".join(parts)


def _params_from_last_parens(line: str) -> str:
    lo = line.rfind("(")
    hi = line.rfind(")")
    if lo != -1 and hi != -1 and hi > lo:
        return line[lo + 1 : hi].strip()
    return ""


def _procedure_body_only(full_source: str, end_keyword: str) -> tuple[str, str]:
    """First line as header; body excludes header and trailing End Sub/Function."""
    lines = full_source.splitlines()
    if not lines:
        return "", ""
    header = lines[0].strip()
    end_re = re.compile(rf"^\s*{end_keyword}\s*$", re.IGNORECASE)
    end_idx: int | None = None
    for j in range(len(lines) - 1, 0, -1):
        if end_re.match(lines[j]):
            end_idx = j
            break
    if end_idx is None:
        body = "\n".join(lines[1:]).strip()
    else:
        body = "\n".join(lines[1:end_idx]).strip()
    return header, body


def _is_vba_comment_only_line(ln: str) -> bool:
    s = ln.lstrip()
    if not s:
        return True
    if s.startswith("'"):
        return True
    return bool(re.match(r"Rem(\s|$)", s, re.I))


def _strip_vba_trailing_comment(line: str) -> str:
    i = 0
    n = len(line)
    in_str = False
    while i < n:
        ch = line[i]
        if in_str:
            if ch == '"':
                if i + 1 < n and line[i + 1] == '"':
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "'":
            return line[:i].rstrip()
        i += 1
    return line


def normalize_vba_code_body(body: str) -> str:
    """
    Drop comment-only lines, strip trailing ' comments (outside " strings), trim lines,
    drop blanks, collapse leading indent to one space for non-column-0 lines.
    """
    if not body:
        return ""
    out: list[str] = []
    for ln in body.splitlines():
        ln = ln.rstrip()
        if not ln.strip():
            continue
        if _is_vba_comment_only_line(ln):
            continue
        ln = _strip_vba_trailing_comment(ln).rstrip()
        if not ln.strip():
            continue
        m = re.match(r"^[ \t]+", ln)
        if m:
            ln = " " + ln[m.end() :]
        out.append(ln)
    return "\n".join(out).strip()


def parse_vba_declaration(header: str) -> tuple[str, str, str]:
    """
    From a single-line declaration, return (type_label, input, output).

    type_label is 'Sub', 'Function', or 'Declare Sub' / 'Declare Function' for API.
    input is the parameter list; output is return type for Function/Declare Function.
    """
    h = header.strip()
    if re.search(r"\bDeclare\s+(?:PtrSafe\s+)?Sub\b", h, re.IGNORECASE):
        return "Declare Sub", _params_from_last_parens(h), ""
    if re.search(r"\bDeclare\s+(?:PtrSafe\s+)?Function\b", h, re.IGNORECASE):
        inner = _params_from_last_parens(h)
        m = re.search(r"\)\s*As\s+(.+)$", h, re.IGNORECASE)
        out = m.group(1).strip() if m else ""
        return "Declare Function", inner, out
    m = re.match(
        r"^\s*(?:Private|Public)\s+Sub\s+\w+\s*\(([^)]*)\)",
        h,
        re.IGNORECASE,
    )
    if m:
        return "Sub", m.group(1).strip(), ""
    m = re.match(
        r"^\s*(?:Private|Public)\s+Function\s+\w+\s*\(([^)]*)\)\s*(?:As\s+(.+))?",
        h,
        re.IGNORECASE,
    )
    if m:
        inner = (m.group(1) or "").strip()
        out = (m.group(2) or "").strip()
        return "Function", inner, out
    return "Sub", "", ""


def extract_vba_routines(
    vba: str,
) -> list[tuple[str, str, str, str, str, str]]:
    """
    Parse VBA module into rows:
    (handler, body_only, visibility, type_label, input, output).

    Declares are one line (body empty). Sub/Function body excludes the opening
    line and End Sub/End Function. File order is preserved.
    """
    if not vba or not vba.strip():
        return []
    lines = vba.splitlines()
    out: list[tuple[str, str, str, str, str, str]] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if stripped.startswith("Attribute ") or stripped.startswith("Option "):
            i += 1
            continue
        if stripped.startswith("'"):
            i += 1
            continue
        if not stripped:
            i += 1
            continue

        if re.match(r"^\s*(?:(Private|Public)\s+)?Declare\s+", raw, re.IGNORECASE):
            hdr = raw.strip()
            vis = _visibility_from_line(hdr)
            handler = _declare_handler_string(hdr)
            typ, inp, outp = parse_vba_declaration(hdr)
            out.append((handler, "", vis, typ, inp, outp))
            i += 1
            continue

        sub = _extract_routine(lines, i, "Sub", "End Sub")
        if sub:
            handler, full_src, vis, next_i = sub
            hdr, body = _procedure_body_only(full_src, "End Sub")
            body = normalize_vba_code_body(body)
            typ, inp, outp = parse_vba_declaration(hdr)
            out.append((handler, body, vis, typ, inp, outp))
            i = next_i
            continue

        fn = _extract_routine(lines, i, "Function", "End Function")
        if fn:
            handler, full_src, vis, next_i = fn
            hdr, body = _procedure_body_only(full_src, "End Function")
            body = normalize_vba_code_body(body)
            typ, inp, outp = parse_vba_declaration(hdr)
            out.append((handler, body, vis, typ, inp, outp))
            i = next_i
            continue

        i += 1
    return out


def _variable_visibility(scope_kw: str) -> str:
    """Map VBA declaration keyword to JSON visibility (dim/module scope → private)."""
    s = scope_kw.lower()
    if s == "public":
        return "public"
    return "private"


def extract_module_variables(vba: str) -> list[dict[str, str]]:
    """
    Collect module-level declarations: Public|Private|Dim <name> As <type> ['comment].

    Each entry includes visibility: public (Public) or private (Private, Dim).

    Skips procedure bodies, Type/Enum blocks, Declare, and Const.
    """
    if not vba or not vba.strip():
        return []
    lines = vba.splitlines()
    proc_depth = 0
    type_enum_depth = 0
    out: list[dict[str, str]] = []
    module_var_re = re.compile(
        r"^\s*(Public|Private|Dim)\s+(?:Static\s+|WithEvents\s+)?(\S+)\s+As\s+(.+)$",
        re.IGNORECASE,
    )

    for raw in lines:
        line = raw.rstrip("\r")
        stripped = line.strip()

        if stripped.startswith("Attribute ") or stripped.startswith("Option "):
            continue

        if type_enum_depth > 0:
            if re.match(r"^\s*End\s+Type\s*$", stripped, re.IGNORECASE):
                type_enum_depth -= 1
            elif re.match(r"^\s*End\s+Enum\s*$", stripped, re.IGNORECASE):
                type_enum_depth -= 1
            continue

        if re.match(r"^\s*(?:Public|Private)\s+Type\s+\w", line, re.IGNORECASE):
            type_enum_depth += 1
            continue
        if re.match(r"^\s*(?:Public|Private)\s+Enum\s+\w", line, re.IGNORECASE):
            type_enum_depth += 1
            continue

        if proc_depth > 0:
            if re.match(r"^\s*End\s+Sub\s*$", stripped, re.IGNORECASE):
                proc_depth = max(0, proc_depth - 1)
            elif re.match(r"^\s*End\s+Function\s*$", stripped, re.IGNORECASE):
                proc_depth = max(0, proc_depth - 1)
            elif re.match(r"^\s*End\s+Property\s*$", stripped, re.IGNORECASE):
                proc_depth = max(0, proc_depth - 1)
            continue

        if re.match(
            r"^\s*(?:Private|Public|Friend)?\s*(?:Static\s+)?(?:Sub|Function)\s+\w",
            line,
            re.IGNORECASE,
        ):
            proc_depth += 1
            continue
        if re.match(
            r"^\s*(?:Private|Public)?\s*(?:Static\s+)?Property\s+",
            line,
            re.IGNORECASE,
        ):
            proc_depth += 1
            continue

        if stripped.startswith("'") or not stripped:
            continue

        if re.match(r"^\s*(?:(Private|Public)\s+)?Declare\s+", line, re.IGNORECASE):
            continue

        if re.match(r"^\s*(Public|Private)\s+Const\s+", line, re.IGNORECASE):
            continue

        m = module_var_re.match(line)
        if not m:
            continue
        scope_kw = m.group(1)
        name = m.group(2)
        rest = m.group(3).strip()
        if "'" in rest:
            typ, _, comment = rest.partition("'")
            typ = typ.strip()
            comment = comment.strip()
        else:
            typ = rest.strip()
            comment = ""
        out.append(
            {
                "name": name,
                "type": typ,
                "visibility": _variable_visibility(scope_kw),
                "comment": comment,
            }
        )
    return out


def read_frm_text(frm_path: Path) -> str:
    """Load .frm as UTF-16 LE (Access export) or UTF-8 fallback."""
    raw = frm_path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        enc = "utf-16-le" if raw.startswith(b"\xff\xfe") else "utf-16-be"
        return raw.decode(enc, errors="replace")
    return raw.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# Tree traversal
# --------------------------------------------------------------------------- #


def extract_controls_under_group(group_block: dict) -> list[dict]:
    """Controls nested under an OptionGroup (recursive)."""
    out: list[dict] = []
    for child in group_block.get("children", []):
        ct = child.get("type")
        if ct in CONTROL_TYPES and "Name" in child.get("props", {}):
            out.append(child)
        else:
            out.extend(extract_controls_under_group(child))
    return out


def extract_controls_with_nodekey(
    block: dict, nodekey: str | None = None
) -> list[tuple[dict, str | None, str | None]]:
    """
    Collect controls with layout band (nodekey) and optional parent OptionGroup Name.

    Returns (control_block, nodekey, parent_option_group_name_or_none).
    Controls inside an OptionGroup are emitted after the group with the group Name as parent.
    """
    out: list[tuple[dict, str | None, str | None]] = []

    for child in block.get("children", []):
        child_type = child.get("type")
        if child_type in LAYOUT_BAND_TYPES:
            band = child_type.lower()
            out.extend(extract_controls_with_nodekey(child, band))
            continue
        if child_type in CONTROL_TYPES and "Name" in child.get("props", {}):
            out.append((child, nodekey, None))
            if child_type == "OptionGroup":
                grp_name = child["props"].get("Name", "") or ""
                for ob in extract_controls_under_group(child):
                    out.append((ob, nodekey, grp_name))
        else:
            out.extend(extract_controls_with_nodekey(child, nodekey))

    return out


def extract_attached_label_blocks(control_block: dict) -> list[dict]:
    """
    Labels nested under a control (e.g. TextBox): either direct Begin Label or
    wrapped in an unnamed Begin block (Access report/form export).
    """
    out: list[dict] = []
    for child in control_block.get("children", []):
        if child.get("type") == "Label" and "Name" in child.get("props", {}):
            out.append(child)
            continue
        if child.get("type") is not None:
            continue
        for sub in child.get("children", []):
            if sub.get("type") == "Label" and "Name" in sub.get("props", {}):
                out.append(sub)
    return out


# Form design-time section (e.g. Detail / 詳細); not a control in CONTROL_TYPES
SECTION_BLOCK_TYPE = "Section"
_DETAIL_SECTION_NAMES = frozenset({"詳細", "Detail"})


def _collect_section_blocks(block: dict, out: list[dict]) -> None:
    for child in block.get("children", []):
        if child.get("type") == SECTION_BLOCK_TYPE:
            out.append(child)
        _collect_section_blocks(child, out)


def extract_form_detail_section_props(root_block: dict) -> dict:
    """
    Flat props from the form Detail Section block (Begin Section ... Name = 詳細).
    Used to populate the synthetic section item for Forms.
    """
    sections: list[dict] = []
    _collect_section_blocks(root_block, sections)
    if not sections:
        return {}
    chosen: dict | None = None
    for s in sections:
        name = s.get("props", {}).get("Name", "")
        if name in _DETAIL_SECTION_NAMES:
            chosen = s
            break
    if chosen is None:
        chosen = sections[0]
    return dict(chosen.get("props", {}))


def find_first_block_of_type(block: dict, target_type: str) -> dict | None:
    """DFS for the first Begin <target_type> block (e.g. FormHeader, FormFooter)."""
    if block.get("type") == target_type:
        return block
    for child in block.get("children", []):
        hit = find_first_block_of_type(child, target_type)
        if hit is not None:
            return hit
    return None


def layout_band_meta_item(
    band_key: str,
    props_raw: dict,
    config: dict,
    root_type: str,
) -> dict:
    """Synthetic item for a layout band (form/page header/footer, section)."""
    props_for_cat = {k: v for k, v in props_raw.items() if k != "GUID"}
    band_properties = categorize_properties(props_for_cat, config)
    replace_event_procedure_placeholders(band_properties, root_type, None)
    apply_event_proc_prefix_overrides(band_properties)
    band_properties = lowercase_property_keys_deep(band_properties)
    access_name = props_raw.get("Name", "")
    if isinstance(access_name, str):
        access_name = access_name.strip()
    elif access_name is not None:
        access_name = str(access_name).strip()
    else:
        access_name = ""
    band_display_name = access_name if access_name else band_key
    return {
        "key": item_key_from_guid_or_name(props_raw, band_key),
        "name": band_display_name,
        "type": band_key,
        "nodekey": "",
        "properties": band_properties,
    }


def _layout_band_prefix_access_order() -> tuple[str, ...]:
    """Synthetic JSON band order: headers → detail → footers; optional bands omitted if absent."""
    seq = (
        "FormHeader",
        "PageHeader",
        "ReportHeader",
        "Section",
        "PageFooter",
        "FormFooter",
        "ReportFooter",
    )
    assert set(seq) <= LAYOUT_BAND_TYPES
    return seq


def build_layout_band_prefix(
    root_block: dict,
    config: dict,
    root_type: str,
    band_order: tuple[str, ...],
) -> list[dict]:
    """
    Leading band meta items: optional bands only if block exists; Section always
    uses extract_form_detail_section_props (may be empty).
    """
    prefix: list[dict] = []
    for access_typ in band_order:
        if access_typ == "Section":
            section_raw = extract_form_detail_section_props(root_block)
            prefix.append(
                layout_band_meta_item("section", section_raw, config, root_type)
            )
            continue
        b = find_first_block_of_type(root_block, access_typ)
        if b is not None:
            prefix.append(
                layout_band_meta_item(
                    access_typ.lower(),
                    dict(b.get("props", {})),
                    config,
                    root_type,
                )
            )
    return prefix


def extract_control_type_defaults(root_block: dict) -> dict[str, dict]:
    """
    Collect default properties from unnamed Begin Label / TextBox / ... blocks
    (Form design defaults before named controls). Instance props override these.
    """
    out: dict[str, dict] = {}
    for child in root_block.get("children", []):
        if child.get("type") is not None:
            continue
        for sub in child.get("children", []):
            st = sub.get("type")
            if st not in CONTROL_TYPES:
                continue
            if "Name" in sub.get("props", {}):
                continue
            out[st] = {**out.get(st, {}), **dict(sub.get("props", {}))}
    return out


# --------------------------------------------------------------------------- #
# Event property → VBA handler name
# --------------------------------------------------------------------------- #

EVENT_PROC_PLACEHOLDER = frozenset(
    {
        "[Event Procedure]",
        "[イベント プロシージャ]"
    }
)

# TextBox/ComboBox etc. often export as AfterUpdate / BeforeUpdate without On prefix.
CONTROL_EVENT_SHORT_NAMES = frozenset(
    {
        "AfterUpdate",
        "BeforeUpdate",
        "Enter",
        "Exit",
        "NotInList",
        "Updated",
    }
)


def _event_property_suffix(prop_key: str) -> str | None:
    if prop_key.endswith("EmMacro"):
        return None
    if prop_key.startswith("On") and len(prop_key) > 2:
        return prop_key[2:]
    if prop_key in CONTROL_EVENT_SHORT_NAMES:
        return prop_key
    return None


def handler_name_for_event_property(
    prop_key: str, root_type: str, control_name: str | None
) -> str | None:
    """
    Map an Access event property (e.g. OnOpen, OnKeyDown, AfterUpdate) to the
    default VBA procedure name (Form_Open, txtPass_AfterUpdate, Report_Load).
    """
    suffix = _event_property_suffix(prop_key)
    if not suffix:
        return None
    if control_name:
        return f"{control_name}_{suffix}"
    if root_type == "Report":
        return f"Report_{suffix}"
    return f"Form_{suffix}"


def replace_event_procedure_placeholders(
    categorized: dict, root_type: str, control_name: str | None = None
) -> None:
    """Replace '[Event Procedure]' in Event bucket with inferred handler names."""
    event = categorized.get("Event")
    if not event:
        return
    proc_prefix: str | None = None
    other = categorized.get("Other")
    if isinstance(other, dict):
        raw_pf = other.get("EventProcPrefix")
        if isinstance(raw_pf, str):
            s = raw_pf.strip()
            if s:
                proc_prefix = s
    has_control = (
        control_name is not None and str(control_name).strip() != ""
    )
    for key in list(event.keys()):
        val = event[key]
        if not isinstance(val, str) or val.strip() not in EVENT_PROC_PLACEHOLDER:
            continue
        suffix = _event_property_suffix(key)
        inferred: str | None = None
        if proc_prefix and suffix and has_control:
            inferred = f"{proc_prefix}_{suffix}"
        if inferred is None:
            inferred = handler_name_for_event_property(key, root_type, control_name)
        if inferred:
            event[key] = inferred


def _heuristic_macro_name_string(v: str) -> bool:
    s = v.strip()
    if not s:
        return False
    if s.startswith("["):
        return True
    if _HEURISTIC_MACRO_NAME.match(s):
        return True
    return s.startswith("A_") and len(s) > 2


def apply_event_proc_prefix_overrides(categorized: dict) -> None:
    """
    When Other.EventProcPrefix is set, Access stores the real VBA name as
    Prefix_EventSuffix (e.g. Q_A_Click) while the Event value may show a
    display name with invalid identifier characters (e.g. Q&A_Click).
    """
    event = categorized.get("Event")
    other = categorized.get("Other")
    if not isinstance(event, dict) or not isinstance(other, dict):
        return
    prefix = other.get("EventProcPrefix")
    if not isinstance(prefix, str):
        return
    p = prefix.strip()
    if not p:
        return
    for key in list(event.keys()):
        val = event[key]
        if not isinstance(val, str):
            continue
        v = val.strip()
        if not v or v == EVENT_PROC_PLACEHOLDER:
            continue
        if _heuristic_macro_name_string(v):
            continue
        if v.startswith("Form_") or v.startswith("Report_"):
            continue
        suffix = _event_property_suffix(key)
        if not suffix:
            continue
        tail = f"_{suffix}"
        if not v.endswith(tail):
            continue
        event[key] = f"{p}_{suffix}"


# --------------------------------------------------------------------------- #
# JSON output helpers
# --------------------------------------------------------------------------- #


def lowercase_property_keys_deep(obj: dict | list | object) -> dict | list | object:
    """Lowercase every dict key in nested structures (Access property names)."""
    if isinstance(obj, dict):
        return {
            (k.lower() if isinstance(k, str) else k): lowercase_property_keys_deep(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [lowercase_property_keys_deep(x) for x in obj]
    return obj


# --------------------------------------------------------------------------- #
# Property categorisation
# --------------------------------------------------------------------------- #


def _key_matches_config_patterns(key: str, patterns: list) -> bool:
    """True if key matches any glob in patterns (e.g. *Height*, On*, *Macro)."""
    if not patterns:
        return False
    return any(fnmatch.fnmatchcase(key, pat) for pat in patterns)


def categorize_properties(props: dict, config: dict) -> dict:
    """
    Split a flat props dict into Format / Data / Event / Other buckets.

    Categorisation order:
      1. Exact key match against Format list, or Rules.formatpatterns (glob)
      2. Data list (exact)
      3. Event list (exact), Rules.eventpatterns (glob), EmMacro suffix,
         On* with uppercase third letter
      4. Everything else → Other
    """
    format_keys = set(config.get("Format", []))
    data_keys = set(config.get("Data", []))
    event_keys = set(config.get("Event", []))
    rules = config.get("Rules") or {}
    format_patterns = (
        config.get("FormatPatterns")
        or rules.get("formatpatterns")
        or rules.get("FormatPatterns")
        or []
    )
    event_patterns = (
        config.get("EventPatterns")
        or rules.get("eventpatterns")
        or rules.get("EventPatterns")
        or []
    )

    result: dict = {"Format": {}, "Data": {}, "Event": {}, "Other": {}}

    for key, val in props.items():
        if key in format_keys or _key_matches_config_patterns(key, format_patterns):
            result["Format"][key] = val
        elif key in data_keys:
            result["Data"][key] = val
        elif (
            key in event_keys
            or _key_matches_config_patterns(key, event_patterns)
            or key.endswith("EmMacro")
            or (key.startswith("On") and len(key) > 2 and key[2].isupper())
        ):
            result["Event"][key] = val
        else:
            result["Other"][key] = val

    return result

# --------------------------------------------------------------------------- #
# Trim String
# --------------------------------------------------------------------------- #

def trim_string(string: str) -> str:
    return "\n".join(string.strip())

# --------------------------------------------------------------------------- #
# Main builder
# --------------------------------------------------------------------------- #


def build_json(frm_path: Path, config: dict) -> dict:
    """
    Read a .frm file and produce the final JSON structure.

    Root is a single object (no wrapping "forms" / "reports" array):
    {
        "key": UUID from form/report GUID when present, else "screen_frm" | "report_frm",
        "type": "Forms" | "Reports",
        "name": "...",
        "properties": { format, data, event, other }  (keys lowercased),
        "items": [ { "key", "name", "type", "nodekey"?, "properties" } ],
        "functions": [ { "handler", "visibility", "type", "input", "output", "code" } ],
        "variables": [ { "name", "type", "visibility", "comment" } ]
    }

    Leading band meta items (Forms and Reports): formheader, pageheader, reportheader
    (each if present), section (detail, always), pagefooter, formfooter, reportfooter
    (each if present). type/nodekey use lowercase Access band name.
    Other items may include nodekey for controls. Each control merges type-default props
    from unnamed Begin <Type> blocks before categorization.
    """
    text = read_frm_text(frm_path)
    notdefaults_cfg = config.get("NotDefaults")
    if not isinstance(notdefaults_cfg, dict):
        notdefaults_cfg = {}
    parser = FrmParser(text, notdefaults_cfg)
    parsed = parser.parse()

    root_block = parsed.get("root_block")
    root_type = parsed.get("root_type") or "Report"
    is_form = root_type == "Form"
    doc_fallback = "screen_frm" if is_form else "report_frm"
    doc_key = doc_fallback
    doc_type = "Forms" if is_form else "Reports"

    empty_doc = {
        "key": doc_key,
        "type": doc_type,
        "name": "",
        "properties": lowercase_property_keys_deep(
            {"Format": {}, "Data": {}, "Event": {}, "Other": {}}
        ),
        "items": [],
        "functions": [],
        "variables": [],
    }

    if not root_block:
        print(f"[WARN] No Begin Report/Form block found in {frm_path}", file=sys.stderr)
        return empty_doc

    report_name = frm_path.stem

    # --- Report/Form-level properties ---
    root_props_raw = root_block.get("props", {})
    root_props_raw.setdefault("Name", report_name)
    doc_key = item_key_from_guid_or_name(root_props_raw, doc_fallback)
    root_props_for_cat = {k: v for k, v in root_props_raw.items() if k != "GUID"}
    report_properties = categorize_properties(root_props_for_cat, config)
    replace_event_procedure_placeholders(report_properties, root_type, None)
    apply_event_proc_prefix_overrides(report_properties)
    report_properties = lowercase_property_keys_deep(report_properties)

    # --- Controls (items) ---
    type_defaults = extract_control_type_defaults(root_block)
    controls_with_nk = extract_controls_with_nodekey(root_block)
    items = []
    for ctrl, nodekey, parent_option_group in controls_with_nk:
        ctrl_type_raw = ctrl.get("type", "Unknown")
        ctrl_name = ctrl["props"].get("Name", "")
        merged_props = {
            **type_defaults.get(ctrl_type_raw, {}),
            **ctrl["props"],
        }
        if parent_option_group:
            merged_props["OptionGroupName"] = parent_option_group
        attached_labels = extract_attached_label_blocks(ctrl)
        if attached_labels:
            lbl_ref = attached_labels[0].get("props", {}).get("Name", "")
            merged_props["LabelName"] = lbl_ref if lbl_ref is not None else ""

        props_for_cat = {k: v for k, v in merged_props.items() if k != "GUID"}
        ctrl_properties = categorize_properties(props_for_cat, config)
        replace_event_procedure_placeholders(
            ctrl_properties, root_type, ctrl_name or None
        )
        apply_event_proc_prefix_overrides(ctrl_properties)
        ctrl_properties = lowercase_property_keys_deep(ctrl_properties)
        ctrl_item: dict = {
            "key": item_key_from_guid_or_name(merged_props, ctrl_name),
            "name": ctrl_name,
            "type": ctrl_type_raw,
            "properties": ctrl_properties,
        }
        if nodekey is not None:
            ctrl_item["nodekey"] = nodekey
        items.append(ctrl_item)
        for lbl_block in attached_labels:
            lbl_name = lbl_block["props"].get("Name", "")
            lbl_merged = {
                **type_defaults.get("Label", {}),
                **lbl_block["props"],
            }
            if parent_option_group:
                lbl_merged["OptionGroupName"] = parent_option_group
            lbl_props_for_cat = {k: v for k, v in lbl_merged.items() if k != "GUID"}
            lbl_properties = categorize_properties(lbl_props_for_cat, config)
            replace_event_procedure_placeholders(
                lbl_properties, root_type, lbl_name or None
            )
            apply_event_proc_prefix_overrides(lbl_properties)
            lbl_properties = lowercase_property_keys_deep(lbl_properties)
            lbl_item: dict = {
                "key": item_key_from_guid_or_name(lbl_merged, lbl_name),
                "name": lbl_name,
                "type": "Label",
                "properties": lbl_properties,
            }
            if nodekey is not None:
                lbl_item["nodekey"] = nodekey
            items.append(lbl_item)

    items = (
        build_layout_band_prefix(
            root_block,
            config,
            root_type,
            _layout_band_prefix_access_order(),
        )
        + items
    )

    vba = parsed.get("vba") or ""
    vba_clean_lines = []
    for ln in vba.splitlines():
        if _is_vba_comment_only_line(ln):
            continue
        ln_clean = _strip_vba_trailing_comment(ln).rstrip()
        if ln_clean.strip():
            vba_clean_lines.append(ln_clean)
    vba = "\n".join(vba_clean_lines).strip()

    functions = [
        {
            "handler": handler,
            "visibility": visibility,
            "type": typ,
            "input": inp,
            "output": outp,
            "code": body,
        }
        for handler, body, visibility, typ, inp, outp in extract_vba_routines(vba)
    ]

    variables = extract_module_variables(vba)

    return {
        "key": doc_key,
        "type": doc_type,
        "name": report_name,
        "properties": report_properties,
        "items": items,
        "functions": functions,
        "variables": variables,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def resolve_config_path(provided: str | None, frm_path: Path) -> Path:
    if provided:
        return Path(provided)
    # Search in Layer 1 config directory first
    layer1_dir = Path(__file__).resolve().parents[1]
    config_dir_file = layer1_dir / "config" / "parser_config.json"
    if config_dir_file.exists():
        return config_dir_file
    # Search upward from the frm file for parser_config.json
    for parent in [frm_path.parent, *frm_path.parents]:
        candidate = parent / "parser_config.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "parser_config.json not found. "
        "Specify with --config or place it in a parent directory."
    )


def run_batch(input_dir: Path, output_dir: Path, config_opt: str | None) -> int:
    if not input_dir.is_dir():
        print(f"[ERROR] Not a directory: {input_dir}", file=sys.stderr)
        return 1
    frm_paths = sorted(input_dir.glob("*.frm"))
    if not frm_paths:
        print(f"[WARN] No .frm files in {input_dir} — nothing to parse.", file=sys.stderr)
        return 0
    config_path = resolve_config_path(config_opt, frm_paths[0])
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for frm_path in frm_paths:
        result = build_json(frm_path, config)
        item_type = result.get("type", "Forms")
        if item_type == "Reports" and output_dir.name == "forms":
            actual_output_dir = output_dir.parent / "reports"
        elif item_type == "Forms" and output_dir.name == "reports":
            actual_output_dir = output_dir.parent / "forms"
        else:
            actual_output_dir = output_dir

        actual_output_dir.mkdir(parents=True, exist_ok=True)
        out_path = actual_output_dir / f"{frm_path.stem}.json"
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        print(f"[OK] {frm_path.name} -> {out_path.name} ({item_type})")
    print(f"[DONE] {len(frm_paths)} file(s) processed.")
    return 0


def run_single(frm_path: Path, output_path: Path | None, config_opt: str | None) -> int:
    if not frm_path.is_file():
        print(f"[ERROR] File not found: {frm_path}", file=sys.stderr)
        return 1
    config_path = resolve_config_path(config_opt, frm_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    result = build_json(frm_path, config)
    json_text = json.dumps(result, ensure_ascii=False, indent=4)
    if output_path is not None:
        item_type = result.get("type", "Forms")
        if item_type == "Reports" and output_path.parent.name == "forms":
            actual_output_path = output_path.parent.parent / "reports" / output_path.name
        elif item_type == "Forms" and output_path.parent.name == "reports":
            actual_output_path = output_path.parent.parent / "forms" / output_path.name
        else:
            actual_output_path = output_path

        actual_output_path.parent.mkdir(parents=True, exist_ok=True)
        actual_output_path.write_text(json_text, encoding="utf-8")
        print(f"[OK] Written to {actual_output_path} ({item_type})")
    else:
        print(json_text)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert Access .frm exports to JSON (batch directory or single file)."
    )
    ap.add_argument(
        "first",
        nargs="?",
        default=DEFAULT_INPUT_DIR,
        help=f"Directory of *.frm (batch) or one .frm file (default: {DEFAULT_INPUT_DIR})",
    )
    ap.add_argument(
        "second",
        nargs="?",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (batch) or output .json path (single, optional; default: {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "--config",
        default=None,
        help="Path to parser_config.json (auto-detected if omitted)",
    )
    ap.add_argument(
        "--output",
        "-o",
        dest="output_file",
        default=None,
        help="Single-file mode: write JSON here (overrides second positional)",
    )
    args = ap.parse_args()
    first = Path(args.first).resolve()
    if first.is_dir():
        if not args.second:
            print(
                "[ERROR] Batch mode needs an output directory as second argument.",
                file=sys.stderr,
            )
            return 2
        return run_batch(first, Path(args.second).resolve(), args.config)
    if first.is_file() and first.suffix.lower() == ".frm":
        out: Path | None = None
        if args.output_file:
            out = Path(args.output_file).resolve()
        elif args.second:
            out = Path(args.second).resolve()
        return run_single(first, out, args.config)
    print(
        f"[ERROR] Not a directory or .frm file: {first}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
