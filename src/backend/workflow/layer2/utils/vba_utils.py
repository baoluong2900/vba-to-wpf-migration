import re
import unicodedata

def strip_vba_comments(code: str) -> str:
    """Strip comments from VBA code line by line, preserving structure."""
    if not code:
        return ""
    cleaned: list[str] = []
    for raw_line in code.splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()
        if not stripped:
            cleaned.append("")
            continue
        if stripped.startswith("'") or re.match(r"Rem(\s|$)", stripped, re.I):
            cleaned.append("")
            continue
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
                line = line[:i].rstrip()
                break
            rem = line[i : i + 3]
            if rem.lower() == "rem":
                prev_char = line[i - 1] if i > 0 else " "
                next_char = line[i + 3] if i + 3 < n else " "
                if (not (prev_char.isalnum() or prev_char == "_")) and (
                    next_char.isspace() or i + 3 >= n
                ):
                    line = line[:i].rstrip()
                    break
            i += 1
        cleaned.append(line)
    return "\n".join(cleaned)

_REQUIRED_TRUE_VALUES = frozenset({"true", "1", "yes", "on", "required", "y", "-1"})


def is_required_flag(value) -> bool:
    """Layer 1 stores a column's 'required' flag as text ("True"/"False"); only affirmative values count."""
    return str(value).strip().lower() in _REQUIRED_TRUE_VALUES


def normalize_query_name(name: str) -> str:
    """Normalize MS Access query names for consistent mapping and search."""
    if not name:
        return ""
    return unicodedata.normalize("NFKC", str(name)).lower().strip()

def normalize_vba_name(name: str) -> str:
    """Normalize VBA handler/macro names for consistent mapping."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", str(name))
    # If the name contains multiple lines (e.g. LLM/system comments), take the first line
    if "\n" in name:
        name = name.splitlines()[0].strip()
    # Enforce lowercase and strip extensions/prefixes
    name = name.lower().strip()
    name = name.replace("参照マクロ: ", "").replace(".xlsx", "").replace("マクロ: ", "").strip()
    if name.startswith("macro."):
        name = name[6:]
    return name
