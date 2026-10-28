#!/usr/bin/env python3
"""
tool_repo.py — Convert DD JSON specs → C# Entity + IRepository + Repository (Dapper)

Pure generation helpers used by agents/repo/agent_repo.py (no MongoDB / LLM access here).
"""

import json
import logging
import re
import sys
import unicodedata
from pathlib import Path

BASE_DIR   = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config" / "name_config.json"

_LAYER5_DIR = BASE_DIR.resolve().parent.parent
if str(_LAYER5_DIR) not in sys.path:
    sys.path.insert(0, str(_LAYER5_DIR))

from core.cs_text import find_matching, mask_non_code  # noqa: E402
from core.naming import cs_identifier  # noqa: E402

logger = logging.getLogger(__name__)

ENTITY_NAMESPACE = "vba_brain.Domain.Entities"
DTO_NAMESPACE_ROOT = "vba_brain.Domain.DTOs"

# ── Type mappings (DB column type → C#) ─────────────────────────────────────
# Access / DAO field types: exact match (case-insensitive, "(size)" suffix ignored).
ACCESS_TO_CS = {
    "LONG": "int", "LONG INTEGER": "int", "AUTONUMBER": "int", "AUTOINCREMENT": "int", "COUNTER": "int",
    "INTEGER": "int", "BYTE": "byte",
    "CURRENCY": "decimal", "DECIMAL": "decimal",
    "SINGLE": "float", "DOUBLE": "double",
    "YES/NO": "bool", "BOOLEAN": "bool", "BIT": "bool",
    "TEXT": "string", "SHORT TEXT": "string", "LONG TEXT": "string", "MEMO": "string", "HYPERLINK": "string",
    "DATE/TIME": "DateTime?", "DATETIME": "DateTime?", "DATE": "DateTime?",
    "OLE OBJECT": "byte[]", "ATTACHMENT": "byte[]",
    "REPLICATION ID": "Guid",
}

# PostgreSQL (+ legacy source) types: longest prefix wins (INT8 before INT, TIMESTAMP before TIME).
SQL_TO_CS = {
    "CHARACTER VARYING": "string", "VARCHAR": "string", "CHARACTER": "string", "CHAR": "string",
    "BPCHAR": "string", "TEXT": "string", "CITEXT": "string", "JSONB": "string", "JSON": "string", "XML": "string",
    "UUID": "Guid",
    "SMALLINT": "int", "INT2": "int", "INTEGER": "int", "INT4": "int", "INT": "int",
    "SMALLSERIAL": "int", "SERIAL": "int",
    "BIGINT": "long", "INT8": "long", "BIGSERIAL": "long",
    "NUMERIC": "decimal", "DECIMAL": "decimal", "MONEY": "decimal",
    "DOUBLE PRECISION": "double", "DOUBLE": "double", "FLOAT8": "double", "FLOAT4": "float",
    "REAL": "float", "FLOAT": "double",
    "BOOLEAN": "bool", "BOOL": "bool",
    "TIMESTAMPTZ": "DateTime?", "TIMESTAMP": "DateTime?", "DATE": "DateTime?",
    "TIME WITH TIME ZONE": "DateTimeOffset?", "TIMETZ": "DateTimeOffset?",
    "TIME": "TimeSpan?", "INTERVAL": "TimeSpan?",
    "BYTEA": "byte[]",
    # Legacy/source type tokens kept for backward-compat with existing JSON data
    "VARCHAR2": "string", "NVARCHAR2": "string", "NVARCHAR": "string", "NCHAR": "string",
    "CLOB": "string", "NCLOB": "string", "NUMBER": "decimal", "BLOB": "byte[]",
}
_SQL_PREFIXES = sorted(SQL_TO_CS, key=len, reverse=True)

# VBA parameter types (VBA Long is 32-bit). Other names go through the DB maps, then default to string.
VBA_TO_CS = {
    "string": "string", "str": "string", "variant": "string",
    "integer": "int", "int": "int", "long": "int", "longlong": "long", "longptr": "long",
    "byte": "byte", "boolean": "bool", "bool": "bool",
    "single": "float", "double": "double", "currency": "decimal", "decimal": "decimal",
    "date": "DateTime?", "object": "object",
}

_REQUIRED_TRUE = {"true", "yes", "y", "-1", "1"}

# Credential columns are never selected/returned; a parameterized VerifyCredentialsAsync is generated instead.
_PASSWORD_SUFFIXES = ("pass", "password", "passwd", "pwd", "パスワード", "暗証番号")
_LOGIN_ID_NAMES = {
    "id", "userid", "loginid", "accountid", "account", "username", "loginname",
    "ユーザーid", "ユーザid", "ログインid", "ユーザー名", "ユーザ名", "ログイン名",
}


# ── Config helpers ────────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"table_name": {}, "field_name": {}, "parameter_name": {}, "function_name": {}, "cte_name": {}}


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


# ── Text / name helpers ──────────────────────────────────────────────────────
def _text(value) -> str:
    """None-safe str() for DD fields."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _nfkc(value) -> str:
    return unicodedata.normalize("NFKC", _text(value)).strip()


def cs_name(name, fallback: str = "Unknown") -> str:
    """C# identifier via core.naming.cs_identifier; circled/other numbers (①②) become digits instead of '_'."""
    text = "".join(
        unicodedata.normalize("NFKC", ch) if unicodedata.category(ch) == "No" else ch
        for ch in _text(name)
    )
    return cs_identifier(text.strip(), fallback=fallback)


def make_unique(name: str, used: set, keep_suffix: str = "") -> str:
    """`name`, or name2/name3… (name_2 after a digit) when taken; `keep_suffix` stays last; registers the result."""
    stem, tail = name, ""
    if keep_suffix and name.endswith(keep_suffix) and len(name) > len(keep_suffix):
        stem, tail = name[: -len(keep_suffix)], keep_suffix
    candidate, n = name, 1
    while candidate in used:
        n += 1
        sep = "_" if stem[-1:].isdigit() else ""
        candidate = f"{stem}{sep}{n}{tail}"
    used.add(candidate)
    return candidate


def quote_ident(name: str) -> str:
    """PostgreSQL double-quoted identifier."""
    return '"' + _text(name).replace('"', '""') + '"'


def _cs_string(value: str) -> str:
    """Escape text for a regular C# string literal."""
    return _text(value).replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", " ")


def bare_column_name(name) -> str:
    """'T."列"' / '[T].[列]' / 'T.列\\n…' → '列'."""
    s = _text(name).split("\n")[0]
    s = s.split(".")[-1]
    return s.replace('"', "").strip().strip("[]").strip()


def _nfkc_lookup(mapping: dict, key: str):
    """(key, value) by exact key, else by NFKC-normalised key (full/half-width); (None, None) if absent."""
    if key in mapping:
        return key, mapping[key]
    norm = _nfkc(key)
    for k, v in mapping.items():
        if _nfkc(k) == norm:
            return k, v
    return None, None


def sanitize_identifier(name: str) -> str:
    """Convert table name → valid C# class-name identifier (PascalCase, no spaces/quotes)."""
    name = _text(name).replace('\\"', "").replace('"', "").strip()
    parts = re.split(r"_+", name)
    result = ""
    for part in parts:
        part = part.replace(" ", "")
        if not part:
            continue
        if part[0].isascii() and part[0].isalpha():
            result += part[0].upper() + part[1:]
        else:
            result += part
    result = cs_name(result, "Unknown")
    if result.startswith("_") and result[1:2].isdigit():
        result = "T" + result[1:]
    return result


def extract_primary_table(from_clause: str) -> str:
    """Extract bare table name from FROM clause (strip alias + quotes)."""
    from_clause = _text(from_clause).replace('\\"', '"').strip()
    if from_clause.startswith('"'):
        end_idx = from_clause.find('"', 1)
        if end_idx != -1:
            return from_clause[1:end_idx].strip()

    clean = from_clause.replace('"', '').strip()
    parts = clean.split()
    return parts[0].strip() if parts else clean


def find_table_key(table_name: str, config: dict) -> str:
    """Physical table → English class stem from config (exact / NFKC match only); else the name itself."""
    _, value = _nfkc_lookup(config.get("table_name", {}), table_name)
    if isinstance(value, str) and value and not value.startswith("TODO"):
        return value
    return table_name


def class_base_name(table_name: str, config: dict, used: set | None = None) -> str:
    """C# class stem for a table; a stem already taken by another table this run gets 2/3… (kept in config)."""
    base = sanitize_identifier(find_table_key(table_name, config))
    if used is None:
        return base
    if base in used:
        unique = make_unique(base, used)
        config.setdefault("table_name", {})[table_name] = unique
        logger.warning("[tool_repo] class name %s already used by another table — %s → %s", base, table_name, unique)
        return unique
    used.add(base)
    return base


def get_english_name(jp_name: str, config: dict) -> str:
    """
    Look up English name for a Japanese field name.
    Adds 'TODO' entry to config if missing.
    """
    field_map = config.setdefault("field_name", {})
    jp_clean = _text(jp_name).split("\n")[0].strip()
    if jp_clean in field_map:
        return field_map[jp_clean]
    field_map[jp_clean] = "TODO"
    return "TODO"


def get_param_english_name(jp_name: str, config: dict) -> str:
    """
    Look up English name for a VBA parameter from parameter_name config.
    Returns camelCase English name, or strips 'txt' prefix as fallback.
    Adds a TODO entry to config if missing.
    """
    param_map = config.setdefault("parameter_name", {})
    jp_clean = _text(jp_name).strip()
    if jp_clean in param_map:
        return param_map[jp_clean]
    # Fallback: register with TODO and return jp_clean
    param_map[jp_clean] = "TODO_" + jp_clean
    return "TODO_" + jp_clean


def get_csharp_prop_name(jp_raw: str, config: dict) -> str:
    """Get the final C# property name for a raw Japanese field name."""
    jp = bare_column_name(jp_raw)
    en = get_english_name(jp, config)
    if en and en != "TODO":
        return cs_name(en[0].upper() + en[1:], f"TODO_{jp}")
    return cs_name(f"TODO_{jp}", "Unknown")


def build_prop_map(names, config: dict, used: set | None = None) -> dict:
    """{bare JP column → C# property} for one class; distinct columns translating to the same name get 2/3…"""
    used = set() if used is None else used
    props: dict[str, str] = {}
    for raw in names:
        jp = bare_column_name(raw)
        if jp in props:
            continue
        props[jp] = make_unique(get_csharp_prop_name(jp, config), used)
    return props


def sql_to_cs_type(sql_type: str) -> str:
    """DB column type → C# type (Access names exact, then PostgreSQL by longest prefix; unknown → object)."""
    text = re.sub(r"\s+", " ", _text(sql_type)).strip().upper()
    base = re.sub(r"\s*\(.*\)$", "", text)
    if base in ACCESS_TO_CS:
        return ACCESS_TO_CS[base]
    for key in _SQL_PREFIXES:
        if text.startswith(key):
            return SQL_TO_CS[key]
    return "object"


def vba_to_cs_type(vba_type: str) -> str:
    """Parameter type: VBA names, then DB/Access names; control types ('Text Box') and unknowns → string."""
    key = _text(vba_type).strip().lower()
    if key in VBA_TO_CS:
        return VBA_TO_CS[key]
    mapped = sql_to_cs_type(key)
    return "string" if mapped == "object" else mapped


def is_required(value) -> bool:
    """Schema 'required' flag: True / 'True' / 'yes' / 'y' / -1 / 1."""
    return str(value).strip().lower() in _REQUIRED_TRUE


def _column_key(name) -> str:
    return re.sub(r"[\s_]+", "", unicodedata.normalize("NFKC", bare_column_name(name))).lower()


def is_password_column(name) -> bool:
    """True for password-like columns (Pass, Password, PWD, パスワード, 暗証番号 …)."""
    key = _column_key(name)
    return bool(key) and key.endswith(_PASSWORD_SUFFIXES)


def is_login_id_column(name) -> bool:
    """True for login-id-like columns (ID, UserId, LoginId, ユーザーID …)."""
    return _column_key(name) in _LOGIN_ID_NAMES


# ── Parse VBA args ────────────────────────────────────────────────────────────
def parse_vba_args(args: list[str], config: dict = None) -> list[dict]:
    """
    ["txt連番: string", ...] →
    [{"vba": "txt連番", "cs_name": "seqNo", "cs_type": "string"}, ...]

    Uses parameter_name config for English cs_name if available.
    """
    result = []
    for arg in args:
        if ":" in arg:
            name, typ = arg.split(":", 1)
        else:
            name, typ = arg, "string"
        name = name.strip()
        cs_type = vba_to_cs_type(typ)
        # strip leading 'txt' prefix to get Japanese param key
        jp_key = name[3:] if name.startswith("txt") else name
        # Look up English name from parameter_name config
        if config is not None:
            cs = cs_name(get_param_english_name(jp_key, config), "param")
        else:
            cs = cs_name(jp_key, "param")
        result.append({"vba": name, "jp_key": jp_key, "cs_name": cs, "cs_type": cs_type})
    return result


# ── SQL text helpers ──────────────────────────────────────────────────────────
def _skip_quoted(text: str, i: int) -> int:
    """Index just past the quoted run starting at text[i] (', \" or [)."""
    close = "]" if text[i] == "[" else text[i]
    j, n = i + 1, len(text)
    while j < n:
        if text[j] == close:
            if close != "]" and j + 1 < n and text[j + 1] == close:
                j += 2
                continue
            return j + 1
        j += 1
    return n


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split on `sep` outside parentheses, quotes and [brackets]."""
    parts, depth, start, i, n = [], 0, 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ("'", '"', "["):
            i = _skip_quoted(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


def _top_level_keyword_positions(text: str, keyword: str) -> list[int]:
    """Offsets of a whole-word, case-insensitive `keyword` at paren depth 0, outside quotes."""
    kw, k = keyword.upper(), len(keyword)
    out, depth, i, n = [], 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ("'", '"', "["):
            i = _skip_quoted(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and text[i:i + k].upper() == kw:
            before = text[i - 1] if i else " "
            after = text[i + k] if i + k < n else " "
            if not _is_word_char(before) and not _is_word_char(after):
                out.append(i)
                i += k
                continue
        i += 1
    return out


def bind_variables(sql: str) -> list[str]:
    """Named binds (:name / @name) in order, outside literals/quoted identifiers; '::' casts skipped."""
    text = _text(sql)
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ("'", '"', "["):
            i = _skip_quoted(text, i)
            continue
        if ch == ":" and i + 1 < n and text[i + 1] == ":":
            i += 2
            while i < n and _is_word_char(text[i]):
                i += 1
            continue
        if ch in ":@" and i + 1 < n and _is_word_char(text[i + 1]) and not (i and _is_word_char(text[i - 1])):
            j = i + 1
            while j < n and _is_word_char(text[j]):
                j += 1
            name = text[i + 1:j]
            if not name.isdigit() and name not in out:
                out.append(name)
            i = j
            continue
        i += 1
    return out


def select_item_name(item: str) -> str:
    """Output column of one SELECT item: its alias, else the bare column of a plain column reference."""
    expr = _text(item).strip()
    as_pos = _top_level_keyword_positions(expr, "AS")
    if as_pos:
        return expr[as_pos[-1] + 2:].strip().strip('[]"').strip()
    ident = r'(?:\[[^\]]+\]|"[^"]+"|[^\s.()\[\]"\',*]+)'
    if re.fullmatch(rf"(?:{ident}\.)*{ident}", expr):
        return bare_column_name(expr)
    return ""


def _with_alias(item: str, alias: str) -> str:
    expr = _text(item).strip()
    as_pos = _top_level_keyword_positions(expr, "AS")
    if as_pos:
        expr = expr[:as_pos[-1]].rstrip()
    return f'{expr} AS "{alias}"'


def rewrite_select_items(items, alias_map: dict | None = None, expand_fields=None) -> list[str]:
    """
    Alias each SELECT item to its C# property (Dapper maps columns by name, not [Column]),
    drop password columns, and expand '*' into the given (column, property) pairs.
    """
    out = []
    for item in items:
        expr = _text(item).strip()
        if not expr:
            continue
        if expr == "*" or expr.endswith(".*"):
            if expand_fields:
                out.extend(f'{quote_ident(col)} AS "{prop}"' for col, prop in expand_fields)
            else:
                out.append(expr)
            continue
        name = select_item_name(expr)
        if name and is_password_column(name):
            continue
        prop = (alias_map or {}).get(name) if name else None
        out.append(_with_alias(expr, prop) if prop else expr)
    return out


def _select_bounds(sql: str):
    """(start, end) of the first top-level SELECT list in `sql`, or None."""
    text = _text(sql)
    sel = _top_level_keyword_positions(text, "SELECT")
    if not sel:
        return None
    start = sel[0] + len("SELECT")
    froms = [p for p in _top_level_keyword_positions(text, "FROM") if p > start]
    return start, (froms[0] if froms else len(text))


def _select_prefix(segment: str) -> str:
    m = re.match(r"\s*(?:(?:DISTINCTROW|DISTINCT|ALL)\s+)?(?:TOP\s+\d+(?:\s+PERCENT)?\s+)?", segment, re.I)
    return m.group(0) if m else ""


def select_items_of_sql(sql: str) -> list[str]:
    """SELECT-list items of a SQL text ([] when it has no top-level SELECT)."""
    bounds = _select_bounds(sql)
    if not bounds:
        return []
    start, end = bounds
    segment = _text(sql)[start:end]
    return [p.strip() for p in split_top_level(segment[len(_select_prefix(segment)):]) if p.strip()]


def has_top_level_from(sql: str) -> bool:
    bounds = _select_bounds(sql)
    return bool(bounds) and bounds[1] < len(_text(sql))


def rewrite_select_sql(sql: str, alias_map: dict | None = None, expand_fields=None):
    """rewrite_select_items applied to the first top-level SELECT list; None when nothing is left to select."""
    text = _text(sql)
    bounds = _select_bounds(text)
    if not bounds:
        return text
    start, end = bounds
    segment = text[start:end]
    prefix = _select_prefix(segment)
    items = [p for p in split_top_level(segment[len(prefix):]) if p.strip()]
    new_items = rewrite_select_items(items, alias_map, expand_fields)
    if items and not new_items:
        return None
    head = text[:start] + (" " + prefix.strip() if prefix.strip() else "")
    tail = text[end:].lstrip()
    return head + "\n  " + "\n, ".join(new_items) + ("\n" + tail if tail else "")


def _from_is_single_table(from_text: str, table_name: str) -> bool:
    """True when a FROM clause is exactly `table_name` (optionally aliased) — no joins or comma lists."""
    clause = re.split(r"(?i)\b(?:WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|UNION|LIMIT)\b", _text(from_text))[0].strip()
    if not clause or "," in clause or re.search(r"(?i)\bJOIN\b", clause):
        return False
    return _nfkc(extract_primary_table(clause).strip("[]")) == _nfkc(table_name)


def infer_bind_types(sql: str, field_types: dict) -> dict:
    """{bind → C# type} for `column <op> :bind` comparisons whose column type is known."""
    col = r'((?:\[[^\]]+\]|"[^"]+"|[^\s()=<>!,\'"\[\]]+)(?:\.(?:\[[^\]]+\]|"[^"]+"|[^\s()=<>!,\'"\[\]]+))*)'
    ops = r"\s*(?:=|<>|!=|<=|>=|<|>|\bLIKE\b)\s*"
    found = {}
    for m in re.finditer(col + ops + r"[:@](\w+)", _text(sql), re.I):
        found.setdefault(m.group(2), bare_column_name(m.group(1)))
    for m in re.finditer(r"[:@](\w+)" + ops + col, _text(sql), re.I):
        found.setdefault(m.group(1), bare_column_name(m.group(2)))
    out = {}
    for bind, column in found.items():
        cs_type = field_types.get(column)
        if cs_type and cs_type not in ("string", "object"):
            out[bind] = cs_type
    return out


# ── DD query normalisation ────────────────────────────────────────────────────
def _param_names(value) -> list[str]:
    """DD 'parameters' as names: 'a, b' | [{'name': …}] | ['a'] | {'a': …}."""
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, dict):
        items = list(value.keys())
    elif isinstance(value, list):
        items = [(p.get("name") or p.get("key") or "") if isinstance(p, dict) else p for p in value]
    else:
        items = []
    return [_text(p).strip() for p in items if _text(p).strip()]


def _where_list(value) -> list[dict]:
    """DD where as [{'condition': …}] from a list of dicts/strings, a single string or sheet-5 where_condition."""
    if isinstance(value, dict):
        value = value.get("condition") or value.get("key_column") or ""
    if isinstance(value, str):
        value = value.strip()
        return [{"condition": value}] if value and value != "なし" else []
    out = []
    for w in value or []:
        cond = _text(w.get("condition") if isinstance(w, dict) else w).strip()
        if cond and cond != "なし":
            out.append({"condition": cond})
    return out


def normalize_query(q: dict) -> dict:
    """None-safe copy of a DD query in the shape the generators expect (both layer-2 DD producers)."""
    q = dict(q or {})
    sql = dict(q.get("sql")) if isinstance(q.get("sql"), dict) else {}
    select = sql.get("select")
    if not isinstance(select, (list, str)):
        select = ""
    set_columns = []
    for sc in sql.get("set_columns") or []:
        if isinstance(sc, dict):
            sc = dict(sc)
            if not sc.get("source_field_or_fixed_value") and sc.get("value_expression"):
                sc["source_field_or_fixed_value"] = sc["value_expression"]
            set_columns.append(sc)
    where_src = sql.get("where") or sql.get("where_condition")
    sql.update({
        "select": select,
        "from": _text(sql.get("from")).strip(),
        "target_table": _text(sql.get("target_table") or sql.get("update_table") or q.get("target_table")).strip(),
        "join": [j for j in (sql.get("join") or []) if isinstance(j, dict)],
        "where": _where_list(where_src),
        "group_by": _text(sql.get("group_by")),
        "order_by": _text(sql.get("order_by")),
        "set_columns": set_columns,
    })
    q.update({
        "query_name": _text(q.get("query_name") or q.get("name")).strip(),
        "sheet_name_pattern": _text(q.get("sheet_name_pattern")).strip(),
        "query_purpose": _text(q.get("query_purpose")),
        "parameters": ", ".join(_param_names(q.get("parameters"))),
        "raw_sql": _text(q.get("raw_sql")),
        "target_sql": _text(q.get("target_sql")),
        "columns": [c for c in (q.get("columns") or []) if isinstance(c, dict)],
        "sql": sql,
    })
    return q


def _structured_select_items(sql_block: dict) -> list[str]:
    sel_raw = sql_block.get("select")
    if isinstance(sel_raw, list):
        items = []
        for item in sel_raw:
            expr = (item.get("expression") or item.get("column") or "") if isinstance(item, dict) else _text(item)
            if _text(expr).strip():
                items.append(_text(expr).strip())
        return items
    text = _text(sel_raw).strip()
    return [p.strip() for p in split_top_level(text) if p.strip()] if text else []


# ── SQL builder ───────────────────────────────────────────────────────────────
def build_sql(sql_block: dict, default_table: str = "", alias_map: dict | None = None, expand_fields=None) -> str:
    """
    Reconstruct full SQL string from the structured sql block.
    SELECT items are aliased to C# property names (alias_map) and password columns dropped;
    returns "" when nothing would be left to select.
    """
    sql_block = sql_block or {}
    target_table = _text(sql_block.get("target_table")).replace('\\"', '"').strip()
    items = _structured_select_items(sql_block)

    from_    = _text(sql_block.get("from")).replace('\\"', '"').strip()
    if not from_ and default_table:
        from_ = default_table
    joins    = sql_block.get("join", []) or []
    wheres   = _where_list(sql_block.get("where"))
    group_by = _text(sql_block.get("group_by"))
    order_by = _text(sql_block.get("order_by"))

    lines = []
    if target_table:
        sel = "\n, ".join(items)
        # Action Query: INSERT, UPDATE, or DELETE
        if sel:
            # INSERT INTO ... SELECT ...
            set_cols = sql_block.get("set_columns") or []
            target_cols = []
            for sc in set_cols:
                col_raw = _text(sc.get("column")).strip()
                if not col_raw:
                    continue
                # "expr AS col" → col (whole-word AS only)
                col_clean = re.split(r"\s+AS\s+", col_raw, flags=re.I)[-1].strip()

                # Wrap in double quotes if not already quoted
                if col_clean and not (col_clean.startswith('"') and col_clean.endswith('"')):
                    col_clean = f'"{col_clean}"'
                if col_clean:
                    target_cols.append(col_clean)

            if target_cols:
                lines.append(f"INSERT INTO {target_table}")
                lines.append("(")
                for idx, col in enumerate(target_cols):
                    if idx == 0:
                        lines.append(f"  {col}")
                    else:
                        lines.append(f", {col}")
                lines.append(")")
            else:
                lines.append(f"INSERT INTO {target_table}")

            lines.append(f"SELECT {sel}")
            if from_:
                lines.append(f"FROM {from_}")
        elif sql_block.get("set_columns"):
            # UPDATE ... SET ...
            lines.append(f"UPDATE {target_table}")
            lines.append("SET")
            set_clauses = []
            for sc in sql_block["set_columns"]:
                col = re.split(r"\s+AS\s+", _text(sc.get("column")), flags=re.I)[0].strip()
                val = _text(sc.get("source_field_or_fixed_value") or sc.get("value"))
                if col and val:
                    set_clauses.append(f"    {col} = {val}")
            if set_clauses:
                lines.append(",\n".join(set_clauses))
            else:
                # Fallback placeholder if set_columns mapping failed to find names
                lines.append("    /* TODO: set values */")
            if from_:
                lines.append(f"FROM {from_}")
        else:
            # DELETE FROM ...
            lines.append(f"DELETE FROM {target_table}")
            if from_:
                lines.append(f"FROM {from_}")
    else:
        # Standard SELECT Query
        new_items = rewrite_select_items(items or ["*"], alias_map, expand_fields)
        if not new_items:
            return ""
        lines.append("SELECT " + "\n, ".join(new_items))
        if from_:
            lines.append(f"FROM {from_}")

    for j in joins:
        jtype  = _text(j.get("type") or "LEFT JOIN")
        jtable = _text(j.get("table"))
        jon    = _text(j.get("on"))
        if jtable:
            if jtype.strip() == ",":
                lines.append(f"{jtype} {jtable}")
            else:
                lines.append(f"{jtype} {jtable} ON {jon}")

    conditions = [w["condition"] for w in wheres if w.get("condition")]
    if conditions:
        lines.append("WHERE " + "\n    AND ".join(conditions))

    if group_by and group_by != "なし":
        lines.append(f"GROUP BY {group_by}")
    if order_by and order_by != "なし":
        lines.append(f"ORDER BY {order_by}")

    return "\n".join(lines)


# ── Method name heuristics ────────────────────────────────────────────────────
def derive_method_name(query: dict, index: int, total: int, config: dict) -> str:
    sheet = query.get("sheet_name_pattern", "")
    if "RecordSource" in sheet or "Sel" in sheet.lower():
        base = "SearchAsync" if total == 1 else f"Search{index + 1}Async"
    elif "Upd" in sheet:
        base = f"Update{index + 1}Async"
    elif "Del" in sheet:
        base = f"Delete{index + 1}Async"
    elif "Ins" in sheet:
        base = f"Insert{index + 1}Async"
    else:
        base = f"ExecuteAsync{index + 1}"

    q_name = query.get("query_name", "").strip()
    if q_name:
        func_map = config.setdefault("function_name", {})
        if q_name in func_map:
            val = func_map[q_name]
            if val and val != "TODO" and not str(val).startswith("TODO"):
                val = cs_name(val, base[:-5] if base.endswith("Async") else base)
                return val if val.endswith("Async") else val + "Async"
        else:
            func_map[q_name] = "TODO"
        return f"TODO_{base}"
    return base


# ── Derive fields from query columns (fallback when schema.fields is empty) ──
def derive_fields_from_queries(queries: list[dict], config: dict) -> list[dict]:
    """
    When table_schemas has no field definitions, build a synthetic fields list
    from the columns declared in dd_queries.
    Each unique effective_name (alias or first line of column_name) becomes one field.
    """
    seen: set[str] = set()
    fields: list[dict] = []
    for q in queries:
        for col in q.get("columns", []) or []:
            alias = _text(col.get("alias")).strip()
            col_name_raw = _text(col.get("column_name"))
            # Use alias if present, else first line of column_name
            effective = alias if alias else col_name_raw.split("\n")[0].strip()
            if not effective or effective in seen:
                continue
            seen.add(effective)
            fields.append({"name": effective, "type": "VARCHAR2", "raw_column_name": col_name_raw})
    return fields


def fields_from_select_items(items) -> list[dict]:
    """Synthetic fields from SELECT items (alias or plain column); '*' and unnamed expressions are skipped."""
    seen, fields = set(), []
    for item in items:
        name = select_item_name(item)
        if name and name not in seen:
            seen.add(name)
            fields.append({"name": name, "type": "VARCHAR2", "raw_column_name": name})
    return fields


# ── Code generators ───────────────────────────────────────────────────────────
def _property_lines(fields: list[dict], prop_map: dict, config: dict) -> list[str]:
    lines, seen = [], set()
    for field in fields:
        jp = bare_column_name(field.get("name", ""))
        prop = prop_map.get(jp)
        if not prop or prop in seen:
            continue
        seen.add(prop)
        cs_type = field.get("csharp_type") or sql_to_cs_type(field.get("type") or "VARCHAR2")
        en = get_english_name(jp, config)
        raw_col = field.get("raw_column_name", "")
        jp_comment = bare_column_name(raw_col) if raw_col else jp
        if en and en != "TODO":
            comment = f"  // {jp_comment}" if jp_comment and en != jp_comment else ""
        else:
            comment = f"  // TODO: translate '{jp_comment}'"
        default = ' = string.Empty;' if cs_type == "string" else ""

        if is_required(field.get("required")):
            lines.append("    [Required]")

        max_len = field.get("length")
        if max_len:
            try:
                max_len_int = int(max_len)
                if max_len_int > 0:
                    lines.append(f"    [MaxLength({max_len_int})]")
            except (ValueError, TypeError):
                pass

        # [Column] documents the source column; SQL aliases (rewrite_select_items) do the Dapper mapping.
        lines.append(f"    [Column(\"{_cs_string(jp)}\")]")
        lines.append(f"    public {cs_type} {prop} {{ get; set; }}{default}{comment}")
    return lines


def gen_input_dto(dto_name: str, fields: list[dict], namespace_suffix: str = "") -> str:
    """Input DTO from resolved [{"name", "type", "description"}] (names already unique C# identifiers)."""
    lines = []
    for f in fields:
        typ = f.get("type") or "string"
        default = ' = string.Empty;' if typ == "string" else ""
        desc = f.get("description") or ""
        comment = f" // {desc}" if desc else ""
        lines.append(f"    public {typ} {f['name']} {{ get; set; }}{default}{comment}")

    body = "\n".join(lines)
    suffix = f".{namespace_suffix}" if namespace_suffix else ""
    return (
        f"namespace {DTO_NAMESPACE_ROOT}{suffix};\n\n"
        f"public class {dto_name}\n"
        f"{{\n{body}\n}}\n"
    )


def gen_dto_class(class_name: str, fields: list[dict], config: dict, namespace_suffix: str = "",
                  prop_map: dict | None = None) -> str:
    prop_map = prop_map if prop_map is not None else build_prop_map([f.get("name", "") for f in fields], config)
    body = "\n".join(_property_lines(fields, prop_map, config))
    suffix = f".{namespace_suffix}" if namespace_suffix else ""
    return (
        f"using System.ComponentModel.DataAnnotations;\n"
        f"using System.ComponentModel.DataAnnotations.Schema;\n\n"
        f"namespace {DTO_NAMESPACE_ROOT}{suffix};\n\n"
        f"public class {class_name}\n"
        f"{{\n{body}\n}}\n"
    )


def gen_csharp_class(class_name: str, fields: list[dict], config: dict, base_class: str = "BaseEntity",
                     jp_table_name: str = "", prop_map: dict | None = None) -> str:
    prop_map = prop_map if prop_map is not None else build_prop_map([f.get("name", "") for f in fields], config)
    body = "\n".join(_property_lines(fields, prop_map, config))
    base_decl = f" : {base_class}" if base_class else ""
    base_using = "using vba_brain.Domain.Common;\n" if base_class else ""
    jp_comment = f"/// <summary>\n/// {jp_table_name}\n/// </summary>\n" if jp_table_name else ""
    return (
        f"using System.ComponentModel.DataAnnotations;\n"
        f"using System.ComponentModel.DataAnnotations.Schema;\n"
        f"{base_using}\n"
        f"namespace {ENTITY_NAMESPACE};\n\n"
        f"{jp_comment}"
        f"public class {class_name}{base_decl}\n"
        f"{{\n{body}\n}}\n"
    )


def gen_interface(entity_name: str, methods: list[dict], namespace_suffix: str = "", jp_table_name: str = "") -> str:
    sigs = []
    for m in methods:
        method_sig = f"    Task<{m['return_type']}> {m['name']}({m['params']});"
        if m.get("comment"):
            sigs.append(m["comment"] + method_sig)
        else:
            sigs.append(method_sig)

    sigs_str = "\n\n".join(sigs)

    has_dtos = any("Dto" in m['return_type'] or "Dto" in m['params'] for m in methods)
    dto_usings = []
    if has_dtos:
        dto_usings.append(f"using {DTO_NAMESPACE_ROOT};")
        if namespace_suffix:
            dto_usings.append(f"using {DTO_NAMESPACE_ROOT}.{namespace_suffix};")

    dto_usings_str = "\n".join(dto_usings) + "\n" if dto_usings else ""

    jp_comment = f"/// <summary>\n/// {jp_table_name}\n/// </summary>\n" if jp_table_name else ""

    return (
        f"using {ENTITY_NAMESPACE};\n"
        f"{dto_usings_str}\n"
        f"namespace vba_brain.Domain.Interfaces;\n\n"
        f"{jp_comment}"
        f"public interface I{entity_name}Repository\n"
        f"{{\n{sigs_str}\n}}\n"
    )


def _append_lines(builder_lines: list[str], sql_text: str) -> None:
    for raw_line in sql_text.splitlines():
        line_escaped = raw_line.replace('"', '""')
        builder_lines.append(f'        sql.AppendLine(@"{line_escaped}");')


def gen_repository(repo_name: str, return_type_name: str, methods: list[dict], repo_ctes: dict = None, namespace_suffix: str = "", jp_table_name: str = "") -> str:
    repo_ctes = repo_ctes or {}
    cte_lines = []
    for name, cte_obj in repo_ctes.items():
        cid = cte_obj["id"]
        method_name = f"Get{cid}"
        jp_name = cte_obj["jp_name"]
        purpose = cte_obj.get("query_purpose", "").strip()
        sql_frag = cte_obj["sql_frag"]

        builder_lines = ["        var sql = new StringBuilder();"]
        _append_lines(builder_lines, sql_frag)
        builder_lines.append("        return sql.ToString();")

        cte_body = "\n".join(builder_lines)
        purpose_line = f"    /// {purpose}\n" if purpose else ""
        cte_lines.append(
            f"    /// {jp_name}\n"
            f"{purpose_line}"
            f"    private string {method_name}()\n"
            f"    {{\n"
            f"{cte_body}\n"
            f"    }}"
        )

    cte_section = "\n\n".join(cte_lines) + ("\n\n" if cte_lines else "")

    impls = []
    for m in methods:
        ret    = m["return_type"]
        name   = m["name"]
        params = m["params"]
        cmt_line = m.get("comment", "") or ""

        if m.get("stub_reason"):
            # No SQL could be resolved: fail loudly instead of returning an empty result.
            impls.append(
                f"{cmt_line}"
                f"    public async Task<{ret}> {name}({params})\n"
                f"    {{\n"
                f"        await Task.CompletedTask;\n"
                f"        throw new NotImplementedException(\"{_cs_string(m['stub_reason'])}\");\n"
                f"    }}"
            )
            continue

        dapper_inner = m.get("dapper_params", "")
        param_obj = f", new {{ {dapper_inner} }}" if dapper_inner else ""

        if m.get("kind") == "credential_check":
            builder_lines = ["        var sql = new StringBuilder();"]
            _append_lines(builder_lines, m.get("base_sql", ""))
            impls.append(
                f"{cmt_line}"
                f"    public async Task<{ret}> {name}({params})\n"
                f"    {{\n"
                + "\n".join(builder_lines) + "\n"
                f"        using var conn = _context.CreateConnection();\n"
                f"        var count = await conn.ExecuteScalarAsync<long>(sql.ToString(){param_obj});\n"
                f"        return count > 0;\n"
                f"    }}"
            )
            continue

        # Extract inner return type
        inner_ret = ret
        if "IEnumerable<" in ret:
            inner_ret = ret.split("<", 1)[1].rsplit(">", 1)[0]
        elif ret.endswith("?"):
            inner_ret = ret.rstrip("?")

        # Choose Dapper call
        if m.get("is_action", False):
            dapper_call = "ExecuteAsync"
        elif "IEnumerable" in ret:
            dapper_call = f"QueryAsync<{inner_ret}>"
        elif ret in ("int", "long", "decimal"):
            dapper_call = f"ExecuteScalarAsync<{ret}>"
        else:
            dapper_call = f"QueryFirstOrDefaultAsync<{inner_ret}>"

        # Build concatenated SQL
        base_lines = (m.get("base_sql", "") or "").splitlines()
        deps = m.get("deps", [])

        # Determine if it is INSERT ... SELECT and find the main SELECT line
        is_insert_select = False
        select_line_idx = -1
        for i, line in enumerate(base_lines):
            clean = line.strip().upper()
            if not clean:
                continue
            if clean.startswith("INSERT INTO"):
                is_insert_select = True
            if clean.startswith("SELECT") and select_line_idx == -1:
                select_line_idx = i

        sql_builder_lines = ["        var sql = new StringBuilder();"]

        def append_ctes():
            sql_builder_lines.append('        sql.Append("WITH ");')
            for idx, dep_name in enumerate(deps):
                cid = repo_ctes[dep_name]["id"]
                if idx > 0:
                    sql_builder_lines.append('        sql.Append(",\\n");')
                sql_builder_lines.append(f'        sql.Append(Get{cid}());')
            sql_builder_lines.append('        sql.Append("\\n");')

        # If not insert_select, or if select line not found, inject at the very beginning
        inject_at_select = is_insert_select and select_line_idx != -1
        if deps and not inject_at_select:
            append_ctes()

        # Append SQL line-by-line using AppendLine
        for i, raw_line in enumerate(base_lines):
            # Inject CTEs right before the main SELECT statement in INSERT INTO ... SELECT
            if deps and inject_at_select and i == select_line_idx:
                append_ctes()

            line_escaped = raw_line.replace('"', '""')
            sql_builder_lines.append(f'        sql.AppendLine(@"{line_escaped}");')
        sql_decl = "\n".join(sql_builder_lines)

        impls.append(
            f"{cmt_line}"
            f"    public async Task<{ret}> {name}({params})\n"
            f"    {{\n"
            f"{sql_decl}\n"
            f"        using var conn = _context.CreateConnection();\n"
            f"        return await conn.{dapper_call}(sql.ToString(){param_obj});\n"
            f"    }}"
        )

    body = "\n\n".join(impls)

    has_dtos = any("Dto" in m['return_type'] or "Dto" in m['params'] for m in methods)
    dto_usings = []
    if has_dtos:
        dto_usings.append(f"using {DTO_NAMESPACE_ROOT};")
        if namespace_suffix:
            dto_usings.append(f"using {DTO_NAMESPACE_ROOT}.{namespace_suffix};")

    dto_usings_str = "\n".join(dto_usings) + "\n" if dto_usings else ""

    jp_comment = f"/// <summary>\n/// {jp_table_name}\n/// </summary>\n" if jp_table_name else ""

    return (
        f"using System.Text;\n"
        f"using {ENTITY_NAMESPACE};\n"
        f"using vba_brain.Domain.Interfaces;\n"
        f"{dto_usings_str}\n"
        f"using vba_brain.Infrastructure.Persistence;\n"
        f"using Dapper;\n\n"
        f"namespace vba_brain.Infrastructure.Persistence.Repositories;\n\n"
        f"{jp_comment}"
        f"public class {repo_name}Repository : I{repo_name}Repository\n"
        f"{{\n"
        f"    private readonly DapperContext _context;\n"
        f"    public {repo_name}Repository(DapperContext context) => _context = context;\n\n"
        f"{cte_section}"
        f"{body}\n"
        f"}}\n"
    )


# ── Orchestration Helpers ─────────────────────────────────────────────────────
def raw_query_names(dd_json: dict) -> list[str]:
    """Names of every DD query (used to look up Layer-3 PostgreSQL target_sql)."""
    names = []
    for key in ("sheet_4_sel_query_templates", "sheet_5_upd_query_templates", "dd_queries"):
        for q in dd_json.get(key) or []:
            if isinstance(q, dict):
                name = _text(q.get("query_name") or q.get("name")).strip()
                if name and name not in names:
                    names.append(name)
    return names


def extract_valid_queries(dd_json: dict, target_sql_map: dict | None = None) -> list[dict]:
    dd_queries = []
    # 1. Standard Select queries  2. Action (Insert/Update/Delete) queries
    for key in ("sheet_4_sel_query_templates", "sheet_5_upd_query_templates"):
        sheet = dd_json.get(key)
        if isinstance(sheet, list):
            dd_queries.extend(q for q in sheet if isinstance(q, dict))

    # 3. Fallback to legacy generic array
    if not dd_queries:
        dd_queries = [q for q in (dd_json.get("dd_queries") or []) if isinstance(q, dict)]

    valid_queries = []
    seen_names = set()
    for raw in dd_queries:
        q = normalize_query(raw)
        if target_sql_map and not q["target_sql"].strip():
            q["target_sql"] = _text(target_sql_map.get(q["query_name"]))
        sql = q["sql"]
        # A query is valid if it has at least one important clause or some SQL text
        has_select = bool(_structured_select_items(sql))
        if not (has_select or sql["from"] or sql["target_table"] or q["columns"]
                or q["raw_sql"].strip() or q["target_sql"].strip()):
            continue

        q_name = q["query_name"]
        if q_name:
            if q_name in seen_names:
                continue
            seen_names.add(q_name)

        valid_queries.append(q)
    return valid_queries


def extract_parameters(dd_json: dict, dd_queries: list[dict]) -> dict:
    param_map = {}
    overview = dd_json.get("sheet_2_overview") or {}
    for p in overview.get("parameter_info") or []:
        if not isinstance(p, dict):
            continue
        item_name = _text(p.get("item_name")).strip()
        if item_name:
            param_map[item_name] = _text(p.get("data_type")).strip() or "string"

    # Extract from detail_specs query_mappings
    for spec in dd_json.get("sheet_3_detail_specs") or []:
        for qmap in (spec or {}).get("query_mappings") or []:
            for p in (qmap or {}).get("parameters") or []:
                pname = _text(p.get("name") if isinstance(p, dict) else p).strip()
                if pname:
                    param_map.setdefault(pname, "string")

    for entry in dd_json.get("vba_function_args") or []:
        entry = _text(entry)
        if ":" in entry:
            k, v = entry.split(":", 1)
            k = k.strip()
            # An explicit VBA type beats a control type ("Text Box") from parameter_info
            if k not in param_map or vba_to_cs_type(param_map[k]) == "string":
                param_map[k] = v.strip()
        elif entry.strip():
            param_map.setdefault(entry.strip(), "string")

    for q in dd_queries:
        texts = [w.get("condition", "") for w in q.get("sql", {}).get("where", [])]
        texts += [q.get("target_sql", ""), q.get("raw_sql", "")]
        for text in texts:
            for p_name in bind_variables(text):
                param_map.setdefault(p_name, "string")
    return param_map


def _query_select_names(q: dict) -> list[str]:
    """Output column names a query declares (DD columns, else its SELECT list / SQL text)."""
    names = [f["name"] for f in derive_fields_from_queries([q], {})]
    if names:
        return names
    items = _structured_select_items(q.get("sql") or {})
    if not items:
        items = select_items_of_sql(q.get("target_sql") or q.get("raw_sql") or "")
    return [f["name"] for f in fields_from_select_items(items)]


def register_query_columns(dd_queries: list[dict], config: dict):
    for q in dd_queries:
        for jp_raw in _query_select_names(q):
            jp = bare_column_name(jp_raw)
            if jp:
                get_english_name(jp, config)


def register_schema_fields(schema: dict | None, config: dict) -> None:
    """Register table columns before the LLM translation pass so entities get English names on the first run."""
    for f in (schema or {}).get("fields") or []:
        jp = bare_column_name(f.get("name"))
        if jp and not is_password_column(jp):
            get_english_name(jp, config)


def register_query_names(dd_queries: list[dict], deps_map: dict, config: dict) -> None:
    """Register function / CTE names before the LLM translation pass."""
    func_map = config.setdefault("function_name", {})
    cte_map = config.setdefault("cte_name", {})
    referenced = {d for refs in deps_map.values() for d in refs}
    for q in dd_queries:
        name = q.get("query_name", "")
        if not name:
            continue
        if name in referenced:
            cte_map.setdefault(name, "TODO")
        else:
            func_map.setdefault(name, "TODO")


def resolve_physical_table_name(name: str, config: dict) -> str:
    """
    Resolve a query or table name to the physical table name used as config key
    (exact or NFKC-normalised match only — fuzzy prefix stripping mapped unrelated tables together).
    """
    if not config:
        return name
    key, _ = _nfkc_lookup(config.get("table_name", {}), name)
    return key if key is not None else name


def build_dependency_graph(dd_queries: list[dict], config: dict = None):
    query_map = {q.get("query_name", ""): q for q in dd_queries if q.get("query_name")}
    all_query_names = set(query_map.keys())

    def find_refs(q_obj):
        q_name = q_obj.get("query_name", "")
        refs = []
        s = q_obj.get("sql", {}) or {}
        f = _text(s.get("from"))
        if f:
            t = extract_primary_table(f)
            # A table-as-query entry (FROM its own name) is not a dependency on itself
            if t in all_query_names and t != q_name:
                refs.append(t)
        for j in s.get("join", []) or []:
            jt = _text(j.get("table"))
            if jt:
                t = extract_primary_table(jt)
                if t in all_query_names and t != q_name:
                    refs.append(t)
        return list(dict.fromkeys(refs))

    deps_map = {name: find_refs(q) for name, q in query_map.items()}
    referenced_by_others = set()
    for refs in deps_map.values():
        referenced_by_others.update(refs)

    def get_physical_root(name, visited=None):
        if visited is None: visited = set()
        if name in visited: return name
        visited.add(name)
        if name not in query_map: return name

        # Prioritize target_table for non-select queries (so the method maps to its destination table)
        s = query_map[name].get("sql", {}) or {}
        target = _text(s.get("target_table"))
        if target:
            return extract_primary_table(target)

        # Otherwise fallback to FROM clause
        f = _text(s.get("from"))
        if not f: return name
        return get_physical_root(extract_primary_table(f), visited)

    table_queries: dict[str, list] = {}
    for q in dd_queries:
        name = q.get("query_name")
        if not name or name in referenced_by_others:
            continue
        root_tbl = get_physical_root(name)
        if config:
            root_tbl = resolve_physical_table_name(root_tbl, config)
        table_queries.setdefault(root_tbl, []).append(q)

    return table_queries, query_map, deps_map


def get_recursive_deps(name: str, deps_map: dict, collected=None, _stack=None):
    """Dependencies of `name`, dependencies first; cycles are cut instead of recursing forever."""
    collected = [] if collected is None else collected
    _stack = set() if _stack is None else _stack
    _stack.add(name)
    for d in deps_map.get(name, []):
        if d in collected or d in _stack:
            continue
        get_recursive_deps(d, deps_map, collected, _stack)
        collected.append(d)
    _stack.discard(name)
    return collected


def unify_schema_fields(raw_schema: dict) -> dict:
    raw_cols = raw_schema.get("fields") or raw_schema.get("columns") or []
    flds = []
    for col in raw_cols:
        name = col.get("name") or col.get("physical_name") or col.get("column_name") or ""
        dtype = col.get("data_type") or col.get("type") or "VARCHAR2"
        fld = dict(col)
        fld.update({
            "name": name,
            "type": dtype,
            "csharp_type": col.get("csharp_type")
        })
        flds.append(fld)
    t_name = raw_schema.get("table_name") or raw_schema.get("name") or ""
    return {"table_name": t_name, "fields": flds}


def lookup_schema(schema_map: dict, table_name: str) -> dict | None:
    """Schema for a table: exact name, else NFKC-normalised (full/half-width) match — never a substring."""
    _, schema = _nfkc_lookup(schema_map, table_name)
    return schema


def _cte_entry(dep_name: str, dep_q: dict, config: dict, used_ids: set) -> dict:
    dep_sql = build_sql(dep_q.get("sql", {}))
    indented = "\n".join("    " + line for line in dep_sql.split("\n"))
    cte_map = config.setdefault("cte_name", {})
    cte_en = cte_map.get(dep_name)
    if dep_name not in cte_map:
        cte_map[dep_name] = "TODO"
    if cte_en and cte_en != "TODO" and not str(cte_en).startswith("TODO"):
        cte_id = "Cte_" + cs_name(cte_en, sanitize_identifier(dep_name))
    else:
        cte_id = "Cte_" + sanitize_identifier(dep_name)
    return {
        "id": make_unique(cte_id, used_ids),
        "jp_name": dep_name,
        "sql_frag": f'{quote_ident(dep_name)} AS (\n{indented}\n)',
        "query_purpose": dep_q.get("query_purpose", ""),
    }


def _query_text_sql(q: dict, table_name: str) -> str:
    """target_sql (Layer 3, PostgreSQL) else raw_sql; a bare 'SELECT *' of a table-as-query gets FROM <name>."""
    text = (q.get("target_sql") or "").strip() or (q.get("raw_sql") or "").strip()
    if not text:
        return ""
    if _select_bounds(text) and not has_top_level_from(text):
        q_name = q.get("query_name", "")
        if q_name and _nfkc(q_name) == _nfkc(table_name):
            return f"{text}\nFROM {quote_ident(q_name)}"
        return ""
    return text


def _is_action_sql(text: str) -> bool:
    if re.match(r"(?is)\s*(INSERT|UPDATE|DELETE)\b", text):
        return True
    bounds = _select_bounds(text)
    return bool(bounds) and bool(_top_level_keyword_positions(text[bounds[0]:bounds[1]], "INTO"))


def generate_files_for_table(
    table_name: str,
    queries: list[dict],
    schema: dict,
    query_map: dict,
    deps_map: dict,
    parsed_args: list[dict],
    config: dict,
    dd_json: dict = None,
    used_class_names: set | None = None,
) -> list[dict]:
    """
    Entity + interface + Dapper repository (+ DTOs) for one physical table, plus the repository
    JSON ({Repo}.json) that agent_repo aggregates into the form contract.
    """
    files = []

    base_name = class_base_name(table_name, config, used_class_names)
    entity_class_name = f"{base_name}Entity"
    repo_class_name   = f"{base_name}Repository"
    dto_namespace     = f"{DTO_NAMESPACE_ROOT}.{base_name}"

    repo_dtos = []
    repo_functions = []

    schema = schema or {"table_name": table_name, "fields": []}
    schema_fields = [f for f in schema.get("fields", []) if bare_column_name(f.get("name", ""))]
    password_fields = [f for f in schema_fields if is_password_column(f.get("name", ""))]
    entity_fields = [f for f in schema_fields if not is_password_column(f.get("name", ""))]
    if password_fields:
        logger.info("[tool_repo] %s: password column(s) %s are never selected or returned",
                    table_name, [bare_column_name(f["name"]) for f in password_fields])

    # Column → C# type across joined tables (dd table_schemas + this table)
    field_types: dict[str, str] = {}
    for s in (dd_json or {}).get("table_schemas") or []:
        for col in (s or {}).get("fields") or (s or {}).get("columns") or []:
            cname = col.get("name") or col.get("physical_name") or col.get("column_name") or ""
            if cname:
                field_types.setdefault(bare_column_name(cname), col.get("csharp_type") or sql_to_cs_type(
                    col.get("type") or col.get("data_type") or "VARCHAR2"))
    for f in schema_fields:
        field_types[bare_column_name(f["name"])] = f.get("csharp_type") or sql_to_cs_type(f.get("type") or "VARCHAR2")

    entity_props = build_prop_map([f.get("name", "") for f in entity_fields], config)
    expand_fields = [(bare_column_name(f["name"]), entity_props[bare_column_name(f["name"])]) for f in entity_fields]

    methods: list[dict] = []
    repo_ctes = {}
    dto_files_data = []
    method_names: set = set()
    cte_ids: set = set()

    # Deduplication caches for DTOs
    output_dto_cache = {} # signature -> class_name
    input_dto_cache = {}  # signature -> class_name

    def real_cs_type(f: dict) -> str:
        for name in (bare_column_name(f.get("raw_column_name", "")), bare_column_name(f.get("name", ""))):
            if name and name in field_types:
                return field_types[name]
        return f.get("csharp_type") or sql_to_cs_type(f.get("type", "VARCHAR2"))

    for i, q in enumerate(queries):
        q_name = q.get("query_name", "")
        sql_block = q.get("sql", {}) or {}
        sheet = q.get("sheet_name_pattern", "")

        method_name = make_unique(derive_method_name(q, i, len(queries), config), method_names, keep_suffix="Async")
        method_base_name = method_name[:-5] if method_name.endswith("Async") else method_name

        # ── SQL source: structured DD sql → Layer-3 target_sql → DD raw_sql ────────
        sel_items = _structured_select_items(sql_block)
        if sel_items or sql_block.get("from") or sql_block.get("target_table"):
            source, text_sql = "structured", ""
            all_deps = get_recursive_deps(q_name, deps_map)
            is_action = bool(sql_block.get("target_table"))
            items_for_fields = [] if is_action else sel_items
            single_table = not sql_block.get("join") and _from_is_single_table(sql_block.get("from") or table_name, table_name)
        else:
            text_sql = _query_text_sql(q, table_name)
            source = "text" if text_sql else ""
            all_deps = []
            is_action = bool(text_sql) and _is_action_sql(text_sql)
            items_for_fields = [] if is_action else select_items_of_sql(text_sql)
            bounds = _select_bounds(text_sql) if text_sql else None
            single_table = bool(bounds) and _from_is_single_table(text_sql[bounds[1] + len("FROM"):], table_name)
        is_action = is_action or "Upd" in sheet or "Del" in sheet or "Ins" in sheet

        for dep_name in all_deps:
            if dep_name not in repo_ctes:
                repo_ctes[dep_name] = _cte_entry(dep_name, query_map[dep_name], config, cte_ids)

        # ── Output columns → return type ───────────────────────────────────────────
        query_fields = derive_fields_from_queries([q], config) or fields_from_select_items(items_for_fields)
        selects_star = any(it.strip() == "*" or it.strip().endswith(".*") for it in items_for_fields)
        password_only = (not is_action and not selects_star and bool(query_fields)
                         and all(is_password_column(f["name"]) for f in query_fields))
        if not is_action:
            query_fields = [f for f in query_fields if not is_password_column(f["name"])]

        alias_map = None
        has_extra_fields = False
        if is_action:
            final_return_type = "int"
        elif len(query_fields) == 1 and not selects_star:
            final_return_type = real_cs_type(query_fields[0])
        else:
            has_extra_fields = any(bare_column_name(f["name"]) not in entity_props for f in query_fields)
            if has_extra_fields:
                # Make sure DTO fields have real types and constraints
                for df in query_fields:
                    df["csharp_type"] = real_cs_type(df)
                    for search_name in (bare_column_name(df.get("raw_column_name", "")), bare_column_name(df.get("name", ""))):
                        match = next((e for e in schema_fields if bare_column_name(e.get("name")) == search_name), None)
                        if match:
                            for key in ["required", "length"]:
                                if key in match and key not in df:
                                    df[key] = match[key]
                            break

                dto_props = build_prop_map([f["name"] for f in query_fields], config)
                dto_fields_sig = tuple(sorted((bare_column_name(f["name"]), f["csharp_type"]) for f in query_fields))
                if dto_fields_sig in output_dto_cache:
                    final_return_type = output_dto_cache[dto_fields_sig]
                else:
                    final_return_type = f"{method_base_name}Dto"
                    output_dto_cache[dto_fields_sig] = final_return_type
                    dto_files_data.append({
                        "path": f"Domain/DTOs/{base_name}/{final_return_type}.cs",
                        "content": gen_dto_class(final_return_type, query_fields, config, namespace_suffix=base_name, prop_map=dto_props),
                    })
                if not any(d["dto_name"] == final_return_type for d in repo_dtos):
                    repo_dtos.append({
                        "dto_name": final_return_type,
                        "namespace": dto_namespace,
                        "fields": [
                            {"name": dto_props[bare_column_name(f["name"])], "type": f["csharp_type"],
                             "description": bare_column_name(f["name"])}
                            for f in query_fields
                        ],
                    })
                alias_map = dto_props
            else:
                final_return_type = entity_class_name
                alias_map = entity_props

        # ── Final SQL text ─────────────────────────────────────────────────────────
        stub_reason = ""
        base_sql = ""
        expand = expand_fields if single_table else None
        if password_only:
            stub_reason = f"{q_name}: selects only password column(s); use VerifyCredentialsAsync instead"
        elif source == "structured":
            base_sql = build_sql(sql_block, default_table=table_name, alias_map=alias_map, expand_fields=expand) if not is_action \
                else build_sql(sql_block, default_table=table_name)
        elif source == "text":
            base_sql = text_sql if is_action else (rewrite_select_sql(text_sql, alias_map, expand) or "")
        if not base_sql and not stub_reason:
            stub_reason = f"{q_name or method_name}: no SQL in DD (sql/raw_sql empty) — fill the DD or queries_v2.target_sql"

        # ── Parameters ─────────────────────────────────────────────────────────────
        binds = bind_variables(base_sql)
        q_param_names = set(_param_names(q.get("parameters"))) | set(binds)
        for spec in (dd_json or {}).get("sheet_3_detail_specs") or []:
            for qmap in (spec or {}).get("query_mappings") or []:
                if qmap.get("logic_query_name") == q_name or (sheet and qmap.get("sheet_name") == sheet):
                    for p in qmap.get("parameters") or []:
                        pname = _text(p.get("name") if isinstance(p, dict) else p).strip()
                        if pname:
                            q_param_names.add(pname)

        method_args = [
            dict(a) for a in parsed_args
            if a['vba'] in q_param_names or a['jp_key'] in q_param_names or a['cs_name'] in q_param_names
        ]
        for b in binds:
            if not any(b in (a["vba"], a["jp_key"], a["cs_name"]) for a in method_args):
                jp_key = b[3:] if b.startswith("txt") else b
                method_args.append({"vba": b, "jp_key": jp_key, "cs_name": cs_name(get_param_english_name(jp_key, config), "param"), "cs_type": "string"})

        inferred = infer_bind_types(base_sql, field_types)
        used_params: set = set()
        for a in method_args:
            a["bind"] = next((b for b in binds if b in (a["vba"], a["jp_key"], a["cs_name"])), "")
            if a["cs_type"] == "string" and a["bind"] in inferred:
                a["cs_type"] = inferred[a["bind"]]
            a["cs_name"] = make_unique(a["cs_name"], used_params)

        def bind_member(a: dict, expr: str) -> str:
            member = a["bind"] if cs_identifier(a["bind"]) == a["bind"] else "@" + a["bind"]
            return f"{member} = {expr}"

        use_method_input_dto = len(method_args) > 3

        resolved_input_dto_name = ""
        if use_method_input_dto:
            # Build unique signature for Input DTO
            used_props: set = set()
            input_fields_resolved = []
            for a in method_args:
                a["prop"] = make_unique(cs_name(a["cs_name"][:1].upper() + a["cs_name"][1:], "Value"), used_props)
                input_fields_resolved.append({"name": a["prop"], "type": a["cs_type"], "description": a.get("jp_key", "")})
            input_sig = tuple(sorted((f["name"], f["type"]) for f in input_fields_resolved))

            if input_sig in input_dto_cache:
                resolved_input_dto_name = input_dto_cache[input_sig]
            else:
                resolved_input_dto_name = f"{method_base_name}InputDto"
                input_dto_cache[input_sig] = resolved_input_dto_name
                dto_files_data.append({
                    "path": f"Domain/DTOs/{base_name}/{resolved_input_dto_name}.cs",
                    "content": gen_input_dto(resolved_input_dto_name, input_fields_resolved, namespace_suffix=base_name),
                })

            if not any(d["dto_name"] == resolved_input_dto_name for d in repo_dtos):
                repo_dtos.append({
                    "dto_name": resolved_input_dto_name,
                    "namespace": dto_namespace,
                    "fields": input_fields_resolved,
                })

            params_str = f"{resolved_input_dto_name} request"
            dapper_params_str = ", ".join(bind_member(a, f"request.{a['prop']}") for a in method_args if a["bind"])
        else:
            params_str  = ", ".join(f"{a['cs_type']} {a['cs_name']}" for a in method_args)
            dapper_params_str = ", ".join(bind_member(a, a["cs_name"]) for a in method_args if a["bind"])

        if is_action:
            return_type = "int"
        else:
            return_type = f"IEnumerable<{final_return_type}>"

        cmt_line = ""
        jp_query_name = q.get("query_name", "")
        if jp_query_name:
            query_purpose = q.get("query_purpose", "").strip()
            param_comments = []
            if use_method_input_dto:
                param_comments.append('    /// <param name="request"></param>')
            else:
                for a in method_args:
                    param_comments.append(f'    /// <param name="{a["cs_name"]}"></param>')

            cmt_lines = [
                "    /// <summary>",
                f"    /// {jp_query_name}"
            ]
            if query_purpose:
                cmt_lines.append(f"    /// {query_purpose}")
            cmt_lines.append("    /// </summary>")
            cmt_lines.extend(param_comments)
            cmt_lines.append("    /// <returns></returns>")
            cmt_line = "\n".join(cmt_lines) + "\n"

        methods.append({
            "name":          method_name,
            "return_type":   return_type,
            "params":        params_str,
            "dapper_params": dapper_params_str,
            "base_sql":      base_sql,
            "deps":          all_deps,
            "comment":       cmt_line,
            "is_action":     is_action,
            "stub_reason":   stub_reason,
        })

        # Resolve Input list for repository JSON
        if use_method_input_dto:
            inputs_list = [{"name": resolved_input_dto_name, "type": "dto", "namespace": dto_namespace, "description": ""}]
        else:
            inputs_list = [
                {"name": a["cs_name"], "type": a["cs_type"], "description": a.get("jp_key", ""), "vba": a.get("vba", "")}
                for a in method_args
            ]

        # Resolve Output list for repository JSON
        if is_action:
            outputs_list = [{"name": "", "type": "int", "description": ""}]
        elif len(query_fields) == 1 and not selects_star:
            outputs_list = [{"name": "", "type": final_return_type, "description": ""}]
        elif has_extra_fields:
            outputs_list = [{"name": final_return_type, "type": "dto", "namespace": dto_namespace, "description": ""}]
        else:
            outputs_list = [{"name": entity_class_name, "type": "entity", "namespace": ENTITY_NAMESPACE, "description": ""}]

        repo_functions.append({
            "function_name": method_name,
            "query_name": q_name or "",
            "sheet_query_name": sheet,
            "description": q.get("query_purpose", "").strip(),
            "input": inputs_list,
            "output": outputs_list,
            "return_type": return_type,
            "implemented": not stub_reason,
        })

    # ── Parameterized credential check (password columns are never returned) ──────
    id_field = next((f for f in entity_fields if is_login_id_column(f.get("name", ""))), None)
    if password_fields and id_field:
        id_col = bare_column_name(id_field["name"])
        pw_col = bare_column_name(password_fields[0]["name"])
        id_type = field_types.get(id_col, "string").rstrip("?")
        if id_type == "object":
            id_type = "string"
        verify_name = make_unique("VerifyCredentialsAsync", method_names, keep_suffix="Async")
        verify_sql = (
            f"SELECT COUNT(1)\nFROM {quote_ident(table_name)}\n"
            f"WHERE {quote_ident(id_col)} = @id\n    AND {quote_ident(pw_col)} = @password"
        )
        methods.append({
            "name":          verify_name,
            "return_type":   "bool",
            "params":        f"{id_type} id, string password",
            "dapper_params": "id, password",
            "base_sql":      verify_sql,
            "deps":          [],
            "comment": (
                "    /// <summary>\n"
                f"    /// {table_name} 認証チェック\n"
                "    /// True when the id/password pair exists (compares the value stored by the Access app).\n"
                "    /// </summary>\n"
            ),
            "kind":          "credential_check",
        })
        repo_functions.append({
            "function_name": verify_name,
            "query_name": "",
            "sheet_query_name": "",
            "kind": "credential_check",
            "description": f"Credential check on {table_name} ({id_col}, {pw_col})",
            "input": [
                {"name": "id", "type": id_type, "description": id_col},
                {"name": "password", "type": "string", "description": pw_col},
            ],
            "output": [{"name": "", "type": "bool", "description": ""}],
            "return_type": "bool",
            "implemented": True,
        })

    entity_cs = gen_csharp_class(entity_class_name, entity_fields, config, base_class="BaseEntity",
                                 jp_table_name=table_name, prop_map=entity_props)
    iface_cs  = gen_interface(base_name, methods, namespace_suffix=base_name, jp_table_name=table_name)
    repo_cs   = gen_repository(base_name, entity_class_name, methods, repo_ctes, namespace_suffix=base_name, jp_table_name=table_name)

    files.append({
        "path": f"Domain/Entities/{entity_class_name}.cs",
        "content": entity_cs,
    })

    files.extend(dto_files_data)

    files.append({
        "path": f"Domain/Interfaces/I{repo_class_name}.cs",
        "content": iface_cs,
    })
    files.append({
        "path": f"Infrastructure/Persistence/Repositories/{repo_class_name}.cs",
        "content": repo_cs,
    })

    # Generate repository JSON
    entity_fields_resolved = []
    for field in entity_fields:
        jp = bare_column_name(field.get("name", ""))
        entity_fields_resolved.append({
            "name": entity_props[jp],
            "type": field.get("csharp_type") or sql_to_cs_type(field.get("type") or "VARCHAR2"),
            "description": jp,
        })

    repo_json = {
        "repository_name": repo_class_name,
        "interface_name": f"I{repo_class_name}",
        "table_name": table_name,
        "function": repo_functions,
        "dto": repo_dtos,
        "entity": [{"entity_name": entity_class_name, "namespace": ENTITY_NAMESPACE, "fields": entity_fields_resolved}],
    }

    files.append({
        "path": f"{repo_class_name}.json",
        "content": json.dumps(repo_json, ensure_ascii=False, indent=4),
    })

    return files


def merge_repository_json(existing_content: str, new_content: str) -> str:
    """
    Merge new JSON repository content into existing JSON repository content.
    Appends new functions, DTOs, and entities, overwriting existing entries with the same names.
    """
    try:
        existing_json = json.loads(existing_content)
        new_json = json.loads(new_content)
    except Exception:
        return new_content

    for key in ("repository_name", "interface_name", "table_name"):
        if new_json.get(key):
            existing_json[key] = new_json[key]

    # Merge functions
    existing_funcs = existing_json.get("function", [])
    new_funcs = new_json.get("function", [])
    func_map = {f["function_name"]: f for f in existing_funcs if "function_name" in f}
    for nf in new_funcs:
        if "function_name" in nf:
            func_map[nf["function_name"]] = nf
    existing_json["function"] = list(func_map.values())

    # Merge dtos
    existing_dtos = existing_json.get("dto", [])
    new_dtos = new_json.get("dto", [])
    dto_map = {d["dto_name"]: d for d in existing_dtos if "dto_name" in d}
    for nd in new_dtos:
        if "dto_name" in nd:
            dto_map[nd["dto_name"]] = nd
    existing_json["dto"] = list(dto_map.values())

    # Merge entities
    existing_entities = existing_json.get("entity", [])
    new_entities = new_json.get("entity", [])
    entity_map = {e["entity_name"]: e for e in existing_entities if "entity_name" in e}
    for ne in new_entities:
        if "entity_name" in ne:
            entity_map[ne["entity_name"]] = ne
    existing_json["entity"] = list(entity_map.values())

    return json.dumps(existing_json, ensure_ascii=False, indent=4)


# ── Merge C# code ─────────────────────────────────────────────────────────────
# Type declaration of a generated file (Unicode names and any base list: `: IT023地区CD設定Repository`).
_TYPE_HEADER_RE = re.compile(
    r"^[ \t]*public\s+(?:(?:sealed|abstract|static|partial)\s+)*(?:class|interface|record)\s+[^\s:{(]+"
    r"(?:\s*\([^)]*\))?(?:\s*:\s*[^{;]+?)?\s*\{",
    re.MULTILINE,
)

_MEMBER_RE = re.compile(
    r'(?:^[ \t]*///[^\n]*\n)*'
    r'(?:^[ \t]*\[[^\]]+\]\n)*'
    r'^[ \t]*'
    r'(?:'
    r'public\s+[\w\<\>\[\]\?\s]+\s+([^\s\{\}\;]+)\s*\{\s*get;\s*set;\s*\}|'  # Group 1: Property
    r'Task<(?:[^\(]+)>\s+([^\s\(\)\;]+)\(.*?\);|'  # Group 2: Interface Method
    r'(?:private\s+const\s+string\s+|private\s+string\s+)([^\s\(\)\;=]+)(?:\s*=|\s*\(\s*\))|'  # Group 3: CTE
    r'public\s+async\s+Task<(?:[^\(]+)>\s+([^\s\(\)\;]+)\s*\('  # Group 4: Repo Method
    r')',
    re.MULTILINE
)


def _split_type(code: str):
    """(head through the type's '{', member body, closing '}' + rest); None when there is no type declaration."""
    m = _TYPE_HEADER_RE.search(code)
    if not m:
        return None
    close = code.rfind("}")
    if close < m.end():
        return code[:m.end()], code[m.end():], ""
    return code[:m.end()], code[m.end():close], code[close:]


def _headerless_body(code: str) -> str:
    """Members of a file whose type declaration was lost: text after usings/namespace, minus a stray '}'."""
    lines = code.split("\n")
    i = 0
    while i < len(lines) and (not lines[i].strip() or re.match(r"\s*(?:using\s+[\w.]+\s*;|namespace\s+[\w.]+\s*;)", lines[i])):
        i += 1
    body = "\n".join(lines[i:])
    masked = mask_non_code(body)
    if masked.count("}") > masked.count("{"):
        body = body[:body.rfind("}")]
    return "\n" + body.rstrip() + "\n"


def _member_blocks(body: str) -> list[dict]:
    matches = list(_MEMBER_RE.finditer(body))
    blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block_code = body[start:end].rstrip()
        # Preserve indentation, only strip leading newlines
        block_code = re.sub(r'^\r?\n+', '', block_code)
        if not block_code.strip():
            continue
        blocks.append({
            "code": block_code,
            "name": m.group(1) or m.group(2) or m.group(3) or m.group(4),
            "type": "prop" if m.group(1) else "iface" if m.group(2) else "cte" if m.group(3) else "method",
        })
    return blocks


def _block_end(text: str, start: int) -> int:
    """End (exclusive) of the brace block that opens at/after `start`; literal/comment aware. -1 if unbalanced."""
    masked = mask_non_code(text)
    open_idx = masked.find("{", start)
    if open_idx == -1:
        return -1
    close_idx = find_matching(text, open_idx, masked)
    return close_idx + 1 if close_idx != -1 else -1


def _comment_start(text: str, idx: int, include_attributes: bool = False) -> int:
    """Back up from a member line over its preceding /// (and optionally [Attribute]) lines."""
    start_idx = idx
    prev_newline = text.rfind('\n', 0, start_idx)
    while prev_newline != -1:
        prev_prev = text.rfind('\n', 0, prev_newline)
        line_start = 0 if prev_prev == -1 else prev_prev + 1
        line_content = text[line_start:prev_newline].strip()
        if line_content.startswith('///') or (include_attributes and line_content.startswith('[')):
            start_idx = line_start
            prev_newline = prev_prev
        else:
            break
    return start_idx


def _merge_members(body: str, new_blocks: list[dict]) -> str:
    """Replace/append new member blocks inside a type body (member-level, indented matches only)."""
    final_code = body

    # Pre-cleanup: remove legacy TODO_ methods/signatures that the new blocks supersede
    for block in new_blocks:
        b_type = block["type"]
        code = block["code"]
        if b_type not in ("method", "iface"):
            continue
        jp_match = re.search(r'///\s*<summary>\s*\n\s*///\s*([^\n]+)\s*\n', code)
        if not jp_match:
            continue
        jp_name = jp_match.group(1).strip()
        head = (
            r'^[ \t]+///\s*<summary>\s*\n'
            r'[ \t]+///\s*' + re.escape(jp_name) + r'\s*\n'
            r'(?:[ \t]*///[^\n]*\n)*'
            r'[ \t]*///\s*</summary>\s*\n'
            r'(?:[ \t]*///[^\n]*\n)*'
        )
        if b_type == "method":
            m_match = re.search(head + r'[ \t]*public\s+(?:async\s+)?Task<(?:[^\(]+)>\s+TODO_[^\s\(\)\;]+\s*\(',
                                final_code, re.MULTILINE)
            if m_match:
                end_idx = _block_end(final_code, m_match.start())
                if end_idx != -1:
                    final_code = final_code[:m_match.start()] + final_code[end_idx:]
        else:
            m_match = re.search(head + r'[ \t]*Task<(?:[^\(]+)>\s+TODO_[^\s\(\)\;]+\s*\(.*?\);',
                                final_code, re.MULTILINE)
            if m_match:
                end_sig = re.search(r';[ \t]*(?:\n|$)', final_code[m_match.start():])
                if end_sig:
                    final_code = final_code[:m_match.start()] + final_code[m_match.start() + end_sig.end():]

    blocks_to_append = []

    for block in new_blocks:
        code = block["code"]
        name = block["name"]
        b_type = block["type"]
        is_replaced = False

        if b_type == "cte":
            # Existing CTE: by JP name comment, else by identifier
            target_idx = -1
            jp_name_match = re.search(r'^[ \t]*///\s*([^\n]+)\s*\n(?:[ \t]*///[^\n]*\n)*\s*(?:private\s+const\s+string|private\s+string)', code, re.MULTILINE)
            if jp_name_match:
                jp_name = jp_name_match.group(1).strip()
                c_match = re.search(
                    r'^[ \t]+///\s*' + re.escape(jp_name) + r'\s*\n'
                    r'(?:[ \t]*///[^\n]*\n)*\s*'
                    r'(?:private\s+const\s+string\s+[^\s\(\)\;=]+\s*=|private\s+string\s+[^\s\(\)\;=]+\s*\(\s*\))',
                    final_code, re.MULTILINE
                )
                if c_match:
                    target_idx = c_match.start()

            if target_idx == -1 and name:
                m_match = re.search(
                    r'^[ \t]+(?:private\s+const\s+string\s+|private\s+string\s+)' + re.escape(name) + r'(?:\s*=|\s*\(\s*\))',
                    final_code, re.MULTILINE
                )
                if m_match:
                    target_idx = m_match.start()

            if target_idx != -1:
                # Back up from the anchor to include ALL preceding comments (cleans up duplicates)
                start_idx = _comment_start(final_code, target_idx)
                anchor_text = final_code[target_idx:]
                is_const = re.match(r'^[ \t]*private\s+const\s+string', anchor_text, re.MULTILINE)
                if is_const:
                    c_end_match = re.search(r'^[ \t]*private\s+const\s+string\s+\w+\s*=\s*@".*?";', anchor_text, re.DOTALL | re.MULTILINE)
                    if c_end_match:
                        end_idx = target_idx + c_end_match.end()
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True
                else:
                    end_idx = _block_end(final_code, target_idx)
                    if end_idx != -1:
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True

        elif b_type == "method":
            # Match by JP query name in the member's summary
            jp_name_match = re.search(r'///\s*<summary>\s*\n\s*///\s*([^\n]+)\s*\n(?:\s*///[^\n]*\n)*\s*///\s*</summary>', code)
            if jp_name_match:
                jp_name = jp_name_match.group(1).strip()
                c_match = re.search(r'^[ \t]+///\s*<summary>\s*\n[ \t]+///\s*' + re.escape(jp_name) + r'\s*\n(?:[ \t]*///[^\n]*\n)*[ \t]*///\s*</summary>', final_code, re.MULTILINE)
                if c_match:
                    end_idx = _block_end(final_code, c_match.start())
                    if end_idx != -1:
                        final_code = final_code[:c_match.start()] + code + final_code[end_idx:]
                        is_replaced = True

            # Fallback to matching method name
            if not is_replaced and name:
                m_match = re.search(r'^[ \t]+public\s+async\s+Task<(?:[^\(]+)>\s+' + re.escape(name) + r'\s*\(', final_code, re.MULTILINE)
                if m_match:
                    start_idx = _comment_start(final_code, m_match.start(), include_attributes=True)
                    end_idx = _block_end(final_code, m_match.start())
                    if end_idx != -1:
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True

        elif b_type == "prop":
            # 1. Match existing property by [Column("JP")] attribute (also replaces old TODO_ properties)
            col_match = re.search(r'\[Column\("([^"]+)"\)\]', code)
            if col_match:
                jp_col = col_match.group(1)
                col_pattern = (
                    r'(?:^[ \t]*///[^\n]*\n)*'
                    r'(?:^[ \t]*\[[^\]]+\]\n)*'
                    r'(?:^[ \t]*\[Column\("' + re.escape(jp_col) + r'"\)\]\n)'
                    r'(?:^[ \t]*\[[^\]]+\]\n)*'
                    r'^[ \t]*public\s+[\w\<\>\[\]\?\s]+\s+[^\s\{\}\;]+\s*\{\s*get;\s*set;\s*\}.*'
                )
                replaced, count = re.subn(col_pattern, lambda _m: code, final_code, count=1, flags=re.MULTILINE)
                if count > 0:
                    final_code = replaced
                    is_replaced = True

            # 2. Match by comment (fallback for legacy TODO cleanup)
            if not is_replaced:
                comment_match = re.search(r'//\s*(.*?)(?:\r?\n|$)', code)
                if comment_match:
                    jp_cmt = comment_match.group(1).strip()
                    search_term = jp_cmt.replace("TODO: translate '", "").rstrip("'")
                    if search_term:
                        todo_patterns = [
                            # Property with TODO_ prefix and same text in its comment
                            r'(?:^[ \t]*///[^\n]*\n)*(?:^[ \t]*\[[^\]]+\]\n)*[ \t]*public\s+[\w\<\>\[\]\?\s]+\s+TODO_[^\s\{\}\;]+\s*\{\s*get;\s*set;\s*\}.*?//.*?' + re.escape(search_term) + r'.*',
                            # Property with any name but its comment explicitly states 'TODO' and contains the term
                            r'(?:^[ \t]*///[^\n]*\n)*(?:^[ \t]*\[[^\]]+\]\n)*[ \t]*public\s+[\w\<\>\[\]\?\s]+\s+[^\s\{\}\;]+\s*\{\s*get;\s*set;\s*\}.*?//.*?TODO.*?' + re.escape(search_term) + r'.*'
                        ]
                        for p in todo_patterns:
                            replaced, count = re.subn(p, lambda _m: code, final_code, count=1, flags=re.MULTILINE)
                            if count > 0:
                                final_code = replaced
                                is_replaced = True
                                break

            # 3. Standard Fallback: match by property identifier name
            if not is_replaced and name:
                find_pattern = r'(?:^[ \t]*///[^\n]*\n)*(?:^[ \t]*\[[^\]]+\]\n)*[ \t]*public\s+[\w\<\>\[\]\?\s]+\s+' + re.escape(name) + r'\s*\{\s*get;\s*set;\s*\}.*'
                replaced, count = re.subn(find_pattern, lambda _m: code, final_code, count=1, flags=re.MULTILINE)
                if count > 0:
                    final_code = replaced
                    is_replaced = True

        elif b_type == "iface":
            # 1. Match by JP query name in the member's summary
            jp_name_match = re.search(r'///\s*<summary>\s*\n\s*///\s*([^\n]+)\s*\n(?:\s*///[^\n]*\n)*\s*///\s*</summary>', code)
            if jp_name_match:
                jp_name = jp_name_match.group(1).strip()
                c_match = re.search(r'^[ \t]+///\s*<summary>\s*\n[ \t]+///\s*' + re.escape(jp_name) + r'\s*\n(?:[ \t]*///[^\n]*\n)*[ \t]*///\s*</summary>', final_code, re.MULTILINE)
                if c_match:
                    start_idx = c_match.start()
                    match_sig = re.search(r'^(?:[ \t]*///[^\n]*\n)*[ \t]*Task<(?:[^\(]+)>\s+[^\s\(\)\;]+\s*\(.*?\);', final_code[start_idx:], re.MULTILINE)
                    if match_sig:
                        end_idx = start_idx + match_sig.end()
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True

            # 2. Fallback to matching by identifier
            if not is_replaced and name:
                find_pattern = r'(?:^[ \t]*///[^\n]*\n)*[ \t]+Task<(?:[^\(]+)>\s+' + re.escape(name) + r'\(.*?\);'
                replaced, count = re.subn(find_pattern, lambda _m: code, final_code, count=1, flags=re.MULTILINE)
                if count > 0:
                    final_code = replaced
                    is_replaced = True

        if not is_replaced:
            blocks_to_append.append(code)

    if blocks_to_append:
        final_code = final_code.rstrip() + "\n\n" + "\n\n".join(blocks_to_append) + "\n"
    return final_code


def merge_csharp_code(existing_code: str, new_code: str) -> str:
    """
    Merge new_code's members into existing_code (same generated type).
    Members are matched by their Japanese query name (member <summary>) or identifier and replaced
    in place; others are appended. Only the type body is searched, so the type declaration and its
    own <summary> are never touched.
    """
    # Normalize all line endings to standard \n to guarantee 100% regex reliability
    existing_code = existing_code.replace('\r\n', '\n')
    new_code = new_code.replace('\r\n', '\n')

    # Auto-heal missing braces in existing_code
    masked_existing = mask_non_code(existing_code)
    if masked_existing.count('{') > masked_existing.count('}'):
        existing_code += "\n}\n"

    new_parts = _split_type(new_code)
    existing_parts = _split_type(existing_code)
    if new_parts is None:
        logger.error("[merge] generated code has no type declaration — keeping the existing file, appending members")
        if existing_parts is None:
            return existing_code
        head, body, tail = existing_parts
        new_body = new_code
    elif existing_parts is None:
        logger.error("[merge] existing file has no type declaration — rebuilding it around the generated type")
        head, body, tail = new_parts[0], _headerless_body(existing_code), new_parts[2] or "}\n"
        new_body = new_parts[1]
    else:
        head, body, tail = existing_parts
        new_body = new_parts[1]

    final_code = head + _merge_members(body, _member_blocks(new_body)) + tail

    # Merge usings
    exist_usings = set(re.findall(r'^using\s+[\w\.]+;', final_code, re.MULTILINE))
    new_usings = set(re.findall(r'^using\s+[\w\.]+;', new_code, re.MULTILINE))
    missing_usings = new_usings - exist_usings

    if missing_usings:
        using_block = "\n".join(sorted(missing_usings)) + "\n"
        last_using = list(re.finditer(r'^using\s+[\w\.]+;\r?\n', final_code, re.MULTILINE))
        if last_using:
            insert_pos = last_using[-1].end()
            final_code = final_code[:insert_pos] + using_block + final_code[insert_pos:]
        else:
            final_code = using_block + "\n" + final_code

    return final_code
