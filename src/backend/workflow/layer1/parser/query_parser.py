#!/usr/bin/env python3
"""
query_parser.py

Parse Access-exported .sql.sql queries into JSON matching query_example.json shape:

  query_name, description, tables (deduped table/query names), parameters ([] or {name: source}), query: { clauses }

  INSERT … SELECT: column→expression map under query.values (not fields).

  Crosstab: TRANSFORM ... SELECT ... PIVOT ... → query.transform, query.pivot, plus select/from/where/group_by/order_by.

Input: a folder containing *.sql.sql files, or a single .sql.sql file.

Usage:
    python query_parser.py <queries_folder> [--output-dir <dir>] [--recursive]
    python query_parser.py <one.sql.sql> [--name ...] [-o out.json] [--stdout]

By default writes each query to output/query_json/<query_stem>.json under the project root.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
vba_dir = ROOT / "src" / "VBA" / "vba_source"
if not vba_dir.exists():
    vba_dir = ROOT / "VBA_Export_All"

DEFAULT_INPUT_DIR = vba_dir / "Queries"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "queries"

_RE_FROM = re.compile(r"FROM\b", re.I)
_RE_WHERE = re.compile(r"WHERE\b", re.I)
_RE_GROUP = re.compile(r"GROUP\s+BY\b", re.I)
_RE_ORDER = re.compile(r"ORDER\s+BY\b", re.I)
_RE_SET = re.compile(r"SET\b", re.I)
_RE_SELECT = re.compile(r"SELECT\b", re.I)
_RE_PIVOT = re.compile(r"PIVOT\b", re.I)

_FORMS_REF = re.compile(r"\[[Ff]orms\](?:\!\[[^\]]*\])+")


def read_query_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if encoding.startswith("utf") and "\ufffd" in text:
            continue
        return text
    return raw.decode("utf-8", errors="replace")


def normalize_raw_sql(sql: str) -> str:
    s = sql.strip()
    s = re.sub(r"\s+", " ", s)
    if s and not s.endswith(";"):
        s += ";"
    return s


def split_top_level_commas(s: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    in_str: str | None = None
    while i < len(s):
        ch = s[i]
        if in_str:
            if ch == in_str:
                if in_str == '"' and i + 1 < len(s) and s[i + 1] == '"':
                    buf.append(ch)
                    buf.append(s[i + 1])
                    i += 2
                    continue
                if in_str == "'" and i + 1 < len(s) and s[i + 1] == "'":
                    buf.append(ch)
                    buf.append(s[i + 1])
                    i += 2
                    continue
                in_str = None
            buf.append(ch)
            i += 1
            continue
        if ch == "[":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == "]":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if ch in "'\"":
            in_str = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def strip_outer_brackets(ident: str) -> str:
    t = ident.strip()
    if t.startswith("[") and t.endswith("]") and len(t) >= 2:
        return t[1:-1]
    return t


def strip_leading_sql_ws(s: str) -> str:
    return s.lstrip(" \t\r\n\ufeff\u3000\u00a0\v\f")


def find_keyword_at_depth_zero(
    s: str, pattern: re.Pattern[str], start: int = 0
) -> tuple[int, int]:
    depth = 0
    i = start
    n = len(s)
    in_str: str | None = None
    while i < n:
        ch = s[i]
        if in_str:
            if ch == in_str:
                if in_str == '"' and i + 1 < n and s[i + 1] == '"':
                    i += 2
                    continue
                if in_str == "'" and i + 1 < n and s[i + 1] == "'":
                    i += 2
                    continue
                in_str = None
            i += 1
            continue
        if ch in "'\"":
            in_str = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            i += 1
            continue
        if ch == "[":
            depth += 1
            i += 1
            continue
        if ch == "]":
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0:
            m = pattern.match(s, i)
            if m:
                return i, m.end()
        i += 1
    return -1, -1


def strip_leading_parameters(sql: str) -> str:
    s = sql.strip()
    m = re.match(r"(?is)^PARAMETERS\s+.+?;\s*", s)
    if m:
        return s[m.end() :].strip()
    return s


def _forms_param_name(forms_rhs: str) -> str:
    segs = [x for x in re.findall(r"\[([^\]]*)\]", forms_rhs) if x]
    return segs[-1] if segs else "param"


def collect_forms_parameters(sql: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _FORMS_REF.finditer(sql):
        ref = m.group(0)
        pname = _forms_param_name(ref)
        out[pname] = ref
    return out


def normalize_forms_to_at(fragment: str) -> str:
    out = fragment
    for m in list(_FORMS_REF.finditer(fragment))[::-1]:
        ref = m.group(0)
        pname = _forms_param_name(ref)
        out = out[: m.start()] + ":" + pname + out[m.end() :]
    return out


def parse_set_clause(set_clause: str) -> tuple[list[str], dict[str, str]]:
    params: dict[str, str] = {}
    lines: list[str] = []
    for part in split_top_level_commas(set_clause):
        part = part.strip()
        if "=" not in part:
            lines.append(part)
            continue
        lhs, rhs = part.split("=", 1)
        lhs_s = lhs.strip()
        rhs_s = rhs.strip()
        if _FORMS_REF.search(rhs_s):
            pname = _forms_param_name(rhs_s)
            if not pname:
                pname = strip_outer_brackets(lhs_s.split(".")[-1])
            params[pname] = rhs_s
            lines.append(f"{lhs_s} = :{pname}")
        else:
            lines.append(part)
    return lines, params


def _na(s: str | None) -> str:
    t = (s or "").strip()
    return t if t else "なし"


def _skip_sql_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def _matching_paren_end(s: str, open_i: int) -> int:
    if open_i >= len(s) or s[open_i] != "(":
        return -1
    depth = 1
    i = open_i + 1
    n = len(s)
    in_str: str | None = None
    while i < n:
        ch = s[i]
        if in_str:
            if ch == in_str:
                if in_str == '"' and i + 1 < n and s[i + 1] == '"':
                    i += 2
                    continue
                if in_str == "'" and i + 1 < n and s[i + 1] == "'":
                    i += 2
                    continue
                in_str = None
            i += 1
            continue
        if ch in "'\"":
            in_str = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _strip_all_outer_balanced_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and _matching_paren_end(s, 0) == len(s) - 1:
        s = s[1:-1].strip()
    return s


_RE_ON = re.compile(r"ON\b", re.I)


def _split_join_segments_at_depth_zero(s: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(s)
    depth = 0
    in_str: str | None = None
    while i < n:
        ch = s[i]
        if in_str:
            if ch == in_str:
                if in_str == '"' and i + 1 < n and s[i + 1] == '"':
                    buf.append(ch)
                    buf.append(s[i + 1])
                    i += 2
                    continue
                if in_str == "'" and i + 1 < n and s[i + 1] == "'":
                    buf.append(ch)
                    buf.append(s[i + 1])
                    i += 2
                    continue
                in_str = None
            buf.append(ch)
            i += 1
            continue
        if ch in "'\"":
            in_str = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if depth == 0:
            m = re.match(r"(?is)(INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+)?JOIN\s+", s[i:])
            if m:
                parts.append("".join(buf).strip())
                buf = []
                i += m.end()
                continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def _segment_before_on_at_depth_zero(seg: str) -> str:
    pos, _ = find_keyword_at_depth_zero(seg, _RE_ON, 0)
    if pos >= 0:
        return seg[:pos].strip()
    return seg.strip()


def _first_table_atoms(seg: str) -> list[str]:
    s = _strip_all_outer_balanced_parens(seg.strip())
    if not s:
        return []
    if re.match(r"(?is)^SELECT\b", s):
        return extract_tables_from_full_select(s)
    if s[0] == "(":
        e = _matching_paren_end(s, 0)
        if e < 0:
            return []
        inner = s[1:e].strip()
        return _first_table_atoms(inner)
    i = _skip_sql_ws(s, 0)
    if i >= len(s):
        return []
    if s[i] == "[":
        j = s.find("]", i)
        if j < 0:
            return []
        return [s[i : j + 1]]
    j = i
    while j < len(s) and s[j] not in " \t\r\n":
        j += 1
    tok = s[i:j].strip()
    return [tok] if tok else []


def extract_tables_from_access_from(from_clause: str) -> list[str]:
    if not from_clause or from_clause.strip() == "なし":
        return []
    s = _strip_all_outer_balanced_parens(from_clause.strip())
    segs = _split_join_segments_at_depth_zero(s)
    if not segs:
        return []
    out: list[str] = []
    out.extend(_first_table_atoms(segs[0]))
    for seg in segs[1:]:
        out.extend(_first_table_atoms(_segment_before_on_at_depth_zero(seg)))
    return out


def extract_tables_from_full_select(sel: str) -> list[str]:
    q = parse_select_statement(sel.strip())
    if not q:
        return []
    out: list[str] = []
    f = q.get("from", "")
    if f and f != "なし":
        out.extend(extract_tables_from_access_from(f))
    w = q.get("where", "")
    if w and w != "なし":
        out.extend(extract_tables_from_where_str(w))
    return out


def _read_tables_after_from_keyword(s: str, j: int) -> tuple[list[str], int]:
    j = _skip_sql_ws(s, j)
    if j >= len(s):
        return [], j
    if s[j] == "(":
        e = _matching_paren_end(s, j)
        if e < 0:
            return [], j + 1
        inner = s[j + 1 : e].strip()
        if re.match(r"(?is)^SELECT\b", inner):
            tabs = extract_tables_from_full_select(inner)
            return tabs, e + 1
        tabs = extract_tables_from_access_from(inner)
        return tabs, e + 1
    if s[j] == "[":
        e = s.find("]", j)
        if e < 0:
            return [], j + 1
        name = s[j : e + 1]
        return [name], e + 1
    k = j
    while k < len(s) and s[k] not in " \t\r\n,)":
        k += 1
    name = s[j:k].strip()
    return ([name] if name else []), k


def extract_tables_from_where_str(where: str) -> list[str]:
    if not where or where == "なし":
        return []
    out: list[str] = []
    i = 0
    n = len(where)
    depth = 0
    in_str: str | None = None
    while i < n:
        ch = where[i]
        if in_str:
            if ch == in_str:
                if in_str == '"' and i + 1 < n and where[i + 1] == '"':
                    i += 2
                    continue
                if in_str == "'" and i + 1 < n and where[i + 1] == "'":
                    i += 2
                    continue
                in_str = None
            i += 1
            continue
        if ch in "'\"":
            in_str = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            i += 1
            continue
        m = re.match(r"(?is)FROM\s+", where[i:])
        if m:
            tabs, next_i = _read_tables_after_from_keyword(where, i + m.end())
            out.extend(tabs)
            i = next_i
            continue
        i += 1
    return out


def extract_delete_from_tables(body: str) -> list[str]:
    b = body.strip().rstrip(";").strip()
    if not b.upper().startswith("DELETE"):
        return []
    from_pos, from_end = find_keyword_at_depth_zero(b, _RE_FROM, 0)
    if from_pos < 0:
        return []
    rest = b[from_end:].lstrip()
    where_pos, _ = find_keyword_at_depth_zero(rest, _RE_WHERE, 0)
    table_expr = rest[:where_pos].strip() if where_pos >= 0 else rest.strip()
    return extract_tables_from_access_from(table_expr)


def merge_tables_ordered(groups: list[list[str]]) -> list[str]:
    out: list[str] = []
    seen_set: set[str] = set()
    for g in groups:
        for t in g:
            t = t.strip()
            if not t:
                continue
            key = strip_outer_brackets(t).casefold()
            if key not in seen_set:
                seen_set.add(key)
                out.append(t)
    return out


def compute_query_tables(qtype: str, q: dict, body: str) -> list[str]:
    if q.get("unparsed"):
        return []
    groups: list[list[str]] = []
    if qtype == "insert":
        ins = (q.get("insert_into") or "").strip()
        if ins:
            groups.append([ins])
        f = q.get("from", "")
        if f and f != "なし":
            groups.append(extract_tables_from_access_from(f))
        w = q.get("where", "")
        if w and w != "なし":
            groups.append(extract_tables_from_where_str(w))
        return merge_tables_ordered(groups)
    if qtype in ("select", "transform"):
        if q.get("from") and q["from"] != "なし":
            groups.append(extract_tables_from_access_from(q["from"]))
        w = q.get("where", "")
        if w and w != "なし":
            groups.append(extract_tables_from_where_str(w))
        return merge_tables_ordered(groups)
    if qtype == "update":
        u = (q.get("update") or "").strip()
        if u:
            groups.append(extract_tables_from_access_from(u))
        w = q.get("where", "")
        if w and w != "なし":
            groups.append(extract_tables_from_where_str(w))
        return merge_tables_ordered(groups)
    if qtype == "delete":
        groups.append(extract_delete_from_tables(body))
        w = q.get("where", "")
        if w and w != "なし":
            groups.append(extract_tables_from_where_str(w))
        return merge_tables_ordered(groups)
    return []


def _split_from_tail_when_no_where(tail: str) -> tuple[str, str]:
    """
    After the FROM keyword, when there is no WHERE clause, the 'tail' may still
    contain GROUP BY / ORDER BY. Only the table/join expression belongs in from;
    split at the first GROUP BY or ORDER BY at depth 0.
    """
    gb0, _ = find_keyword_at_depth_zero(tail, _RE_GROUP, 0)
    ob0, _ = find_keyword_at_depth_zero(tail, _RE_ORDER, 0)
    candidates = [p for p in (gb0, ob0) if p >= 0]
    if not candidates:
        return tail.strip(), ""
    end = min(candidates)
    return tail[:end].strip(), tail[end:].lstrip()


def parse_select_statement(body: str) -> dict[str, str]:
    b = body.strip().rstrip(";").strip()
    m_sel = re.match(r"(?is)^SELECT\s+", b)
    if not m_sel:
        return {}
    start_cols = m_sel.end()
    from_pos, from_end = find_keyword_at_depth_zero(b, _RE_FROM, start_cols)
    if from_pos < 0:
        return {}
    select_list = b[start_cols:from_pos].strip()
    tail = b[from_end:].lstrip()

    where_pos, where_end = find_keyword_at_depth_zero(tail, _RE_WHERE, 0)
    if where_pos >= 0:
        from_clause = tail[:where_pos].strip()
        r2 = tail[where_end:].lstrip()
    else:
        from_clause, r2 = _split_from_tail_when_no_where(tail)

    pivot_sql = ""
    gb_pos, gb_end = find_keyword_at_depth_zero(r2, _RE_GROUP, 0)
    if gb_pos >= 0:
        where_only = r2[:gb_pos].strip()
        r3 = r2[gb_end:].lstrip()
        pivot_pos, pivot_end = find_keyword_at_depth_zero(r3, _RE_PIVOT, 0)
        if pivot_pos >= 0:
            r3_core = r3[:pivot_pos].strip()
            pivot_sql = r3[pivot_end:].strip()
        else:
            r3_core = r3
        ob_pos, ob_end = find_keyword_at_depth_zero(r3_core, _RE_ORDER, 0)
        if ob_pos >= 0:
            group_by = r3_core[:ob_pos].strip()
            order_by = r3_core[ob_end:].strip()
        else:
            group_by = r3_core.strip()
            order_by = ""
    else:
        ob_pos, ob_end = find_keyword_at_depth_zero(r2, _RE_ORDER, 0)
        if ob_pos >= 0:
            where_only = r2[:ob_pos].strip()
            tail_ord = r2[ob_end:].lstrip()
        else:
            where_only = r2.strip()
            tail_ord = ""
        group_by = ""
        pivot_pos, pivot_end = find_keyword_at_depth_zero(tail_ord, _RE_PIVOT, 0)
        if pivot_pos >= 0:
            order_section = tail_ord[:pivot_pos].strip()
            pivot_sql = tail_ord[pivot_end:].strip()
        else:
            order_section = tail_ord
        order_by = order_section

    out: dict[str, str] = {
        "select": select_list,
        "from": from_clause,
        "where": _na(where_only),
        "group_by": _na(group_by),
        "order_by": _na(order_by),
    }
    if pivot_sql:
        out["pivot"] = pivot_sql
    return out


def parse_select_without_from(select_tail: str) -> dict[str, str] | None:
    """
    Access INSERT…SELECT with no FROM (expression-only SELECT list).
    Entire tail after SELECT is the comma-separated select list.
    """
    t = strip_leading_sql_ws(select_tail).rstrip(";").strip()
    if not t:
        return None
    from_pos, _ = find_keyword_at_depth_zero(t, _RE_FROM, 0)
    if from_pos >= 0:
        return None
    return {
        "select": t,
        "from": "なし",
        "where": "なし",
        "group_by": "なし",
        "order_by": "なし",
    }


def parse_transform_statement(body: str) -> dict[str, str]:
    b = body.strip().rstrip(";").strip()
    m_t = re.match(r"(?is)^TRANSFORM\s+", b)
    if not m_t:
        return {}
    t_end = m_t.end()
    sel_pos, _ = find_keyword_at_depth_zero(b, _RE_SELECT, start=t_end)
    if sel_pos < 0:
        return {}
    transform_expr = b[t_end:sel_pos].strip()
    remainder = b[sel_pos:].lstrip()
    inner = parse_select_statement(remainder)
    if not inner:
        return {}
    return {"transform": transform_expr, **inner}


def merge_forms_params_into_where(q: dict[str, str]) -> None:
    w = q.get("where")
    if w and w != "なし":
        q["where"] = normalize_forms_to_at(w)


def parse_delete_statement(body: str) -> dict[str, str]:
    b = body.strip().rstrip(";").strip()
    if not b.upper().startswith("DELETE"):
        return {}
    from_pos, from_end = find_keyword_at_depth_zero(b, _RE_FROM, 0)
    if from_pos < 0:
        return {}
    delete_cols = b[6:from_pos].strip()
    rest = b[from_end:].lstrip()
    where_pos, where_end = find_keyword_at_depth_zero(rest, _RE_WHERE, 0)
    if where_pos >= 0:
        table_part = rest[:where_pos].strip()
        where_raw = rest[where_end:].strip()
    else:
        table_part = rest.strip()
        where_raw = ""
    delete_blob = f"{delete_cols} FROM {table_part} "
    return {
        "delete": delete_blob,
        "where": _na(normalize_forms_to_at(where_raw) if where_raw else ""),
    }


def parse_update_statement(body: str) -> tuple[dict[str, str], dict[str, str]]:
    b = body.strip().rstrip(";").strip()
    extra_params: dict[str, str] = {}
    if not b.upper().startswith("UPDATE"):
        return {}, extra_params
    set_pos, set_end = find_keyword_at_depth_zero(b, _RE_SET, 0)
    if set_pos < 0 or set_pos <= 6:
        return {}, extra_params
    where_pos, where_end = find_keyword_at_depth_zero(b, _RE_WHERE, start=set_end)
    table = b[6:set_pos].strip()
    if where_pos >= 0:
        set_clause = b[set_end:where_pos].strip()
        where_raw = b[where_end:].strip()
    else:
        set_clause = b[set_end:].strip()
        where_raw = ""
    set_lines, set_params = parse_set_clause(set_clause)
    extra_params.update(set_params)
    return (
        {
            "update": table,
            "set": set_lines,
            "where": normalize_forms_to_at(where_raw) if where_raw else "なし",
        },
        extra_params,
    )


def extract_insert_target_columns_rest(body: str) -> tuple[str, str, str] | None:
    m = re.match(r"(?is)^INSERT\s+INTO\s+", body)
    if not m:
        return None
    i = m.end()
    open_paren = body.find("(", i)
    if open_paren < 0:
        return None
    target_table = body[i:open_paren].strip()
    depth = 0
    j = open_paren
    in_str: str | None = None
    while j < len(body):
        ch = body[j]
        if in_str:
            if ch == in_str:
                if in_str == '"' and j + 1 < len(body) and body[j + 1] == '"':
                    j += 2
                    continue
                if in_str == "'" and j + 1 < len(body) and body[j + 1] == "'":
                    j += 2
                    continue
                in_str = None
            j += 1
            continue
        if ch in "'\"":
            in_str = ch
            j += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                cols = body[open_paren + 1 : j]
                rest = strip_leading_sql_ws(body[j + 1 :])
                return target_table, cols, rest
        j += 1
    return None


def extract_values_tuple_inner(rest: str) -> str | None:
    r = rest.lstrip()
    vm = re.match(r"(?is)^VALUES\s*\(", r)
    if not vm:
        return None
    j = vm.end() - 1
    depth = 0
    k = j
    n = len(r)
    in_str: str | None = None
    while k < n:
        ch = r[k]
        if in_str:
            if ch == in_str:
                if in_str == '"' and k + 1 < n and r[k + 1] == '"':
                    k += 2
                    continue
                if in_str == "'" and k + 1 < n and r[k + 1] == "'":
                    k += 2
                    continue
                in_str = None
            k += 1
            continue
        if ch in "'\"":
            in_str = ch
            k += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return r[j + 1 : k]
        k += 1
    return None


def parse_insert_statement(body: str) -> dict[str, str]:
    b = strip_leading_sql_ws(body.strip().rstrip(";").strip())
    hit = extract_insert_target_columns_rest(b)
    if not hit:
        return {}
    target_table, cols_inside, rest = hit
    field_names = [
        strip_outer_brackets(x.strip()) for x in split_top_level_commas(cols_inside)
    ]
    rest_s = strip_leading_sql_ws(rest)
    if rest_s.upper().startswith("SELECT"):
        select_tail = strip_leading_sql_ws(rest_s[6:])
        inner = parse_select_statement("SELECT " + select_tail)
        if not inner:
            inner = parse_select_without_from(select_tail)
        if not inner:
            return {}
        sel_exprs = split_top_level_commas(inner["select"])
        values_map: dict[str, str] = {}
        for idx in range(min(len(field_names), len(sel_exprs))):
            values_map[field_names[idx]] = normalize_forms_to_at(
                sel_exprs[idx].strip()
            )
        out: dict[str, str] = {
            "insert_into": target_table,
            "select": inner["select"],
            "from": inner["from"],
        }
        if values_map:
            out["values"] = values_map
        ob = inner.get("order_by", "なし")
        if ob != "なし":
            out["order_by"] = ob
        gb = inner.get("group_by", "なし")
        if gb != "なし":
            out["group_by"] = gb
        w = inner.get("where", "なし")
        if w != "なし":
            out["where"] = normalize_forms_to_at(w)
        return out

    vals_inner = extract_values_tuple_inner(rest)
    if vals_inner is None:
        return {}
    val_exprs = split_top_level_commas(vals_inner)
    values_map: dict[str, str] = {}
    for idx in range(min(len(field_names), len(val_exprs))):
        values_map[field_names[idx]] = normalize_forms_to_at(val_exprs[idx].strip())
    out = {"insert_into": target_table}
    if values_map:
        out["values"] = values_map
    return out


def detect_statement_type(sql: str) -> str:
    head = sql.lstrip()[:32].upper()
    if head.startswith("TRANSFORM"):
        return "transform"
    if head.startswith("SELECT"):
        return "select"
    if head.startswith("INSERT"):
        return "insert"
    if head.startswith("UPDATE"):
        return "update"
    if head.startswith("DELETE"):
        return "delete"
    return "unknown"


def query_name_from_path(path: Path, override: str | None) -> str:
    if override:
        return override
    stem = path.name
    for suf in (".sql.sql", ".sql"):
        if stem.lower().endswith(suf):
            stem = stem[: -len(suf)]
            break
    return stem


def safe_json_filename(name: str) -> str:
    forbidden = '\\/:*?"<>|'
    cleaned = "".join("_" if c in forbidden else c for c in name.strip())
    return cleaned if cleaned else "query"


def collect_sql_sql_paths(root: Path, recursive: bool) -> list[Path]:
    pattern = "*.sql.sql"
    if recursive:
        return sorted({p.resolve() for p in root.rglob(pattern)})
    return sorted({p.resolve() for p in root.glob(pattern)})


def unique_output_name(base: str, used_counts: dict[str, int]) -> str:
    used_counts[base] = used_counts.get(base, 0) + 1
    n = used_counts[base]
    if n == 1:
        return f"{base}.json"
    return f"{base}_{n}.json"


def _strip_sql_comments(sql: str) -> str:
    # Strip block comments
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    # Strip single-line comments
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        idx = 0
        n = len(line)
        in_str = False
        str_char = None
        while idx < n:
            ch = line[idx]
            if in_str:
                if ch == str_char:
                    if str_char == '"' and idx + 1 < n and line[idx+1] == '"':
                        idx += 2
                        continue
                    if str_char == "'" and idx + 1 < n and line[idx+1] == "'":
                        idx += 2
                        continue
                    in_str = False
                idx += 1
                continue
            if ch in ('"', "'"):
                in_str = True
                str_char = ch
                idx += 1
                continue
            if ch == "-" and idx + 1 < n and line[idx+1] == "-":
                line = line[:idx].rstrip()
                break
            idx += 1
        lines.append(line)
    return "\n".join(lines).strip()


def parse_query_file(path: Path, name_override: str | None = None) -> dict:
    text = read_query_text(path)
    text = _strip_sql_comments(text)
    body = strip_leading_parameters(text)
    qtype = detect_statement_type(body)
    qname = query_name_from_path(path, name_override)
    result: dict = {
        "query_name": qname,
        "description": "",
        "tables": [],
        "parameters": [],
        "query": {},
    }
    params: dict[str, str] = {}

    if qtype == "transform":
        q = parse_transform_statement(body)
        if q:
            merge_forms_params_into_where(q)
            params = collect_forms_parameters(body)
            result["query"] = q
        else:
            result["query"] = {"unparsed": True, "sql": body}
    elif qtype == "select":
        q = parse_select_statement(body)
        if q:
            merge_forms_params_into_where(q)
            params = collect_forms_parameters(body)
            result["query"] = q
        else:
            result["query"] = {"unparsed": True, "sql": body}
    elif qtype == "delete":
        q = parse_delete_statement(body)
        if q:
            params = collect_forms_parameters(body)
            result["query"] = q
        else:
            result["query"] = {"unparsed": True, "sql": body}
    elif qtype == "update":
        q, extra = parse_update_statement(body)
        if q:
            params = collect_forms_parameters(body)
            params.update(extra)
            result["query"] = q
        else:
            result["query"] = {"unparsed": True, "sql": body}
    elif qtype == "insert":
        q = parse_insert_statement(body)
        if q:
            inner_params = collect_forms_parameters(body)
            for k, v in inner_params.items():
                params[k] = v
            w = q.get("where")
            if w:
                q["where"] = normalize_forms_to_at(w)
            result["query"] = q
        else:
            result["query"] = {"unparsed": True, "sql": body}
    else:
        result["query"] = {"unparsed": True, "sql": body}

    result["parameters"] = [] if not params else params
    result["tables"] = compute_query_tables(qtype, result["query"], body)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Parse Access .sql.sql to query_example.json-shaped output."
    )
    ap.add_argument(
        "input_path",
        type=Path,
        nargs="?",
        default=DEFAULT_INPUT_DIR,
        help=f"Folder containing *.sql.sql files, or one .sql.sql file (default: {DEFAULT_INPUT_DIR})",
    )
    ap.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="When input is a folder, include subfolders",
    )
    ap.add_argument("--name", help="Single-file only: override query name in JSON")
    ap.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Single-file only: exact output path (use --output-dir for batch)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for JSON files (default: {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "--stdout",
        action="store_true",
        help="Single-file only: print JSON to stdout instead of writing a file",
    )
    args = ap.parse_args()
    inp = args.input_path
    if not inp.exists():
        print(f"Not found: {inp}", file=sys.stderr)
        return 1

    if inp.is_dir():
        sql_paths = collect_sql_sql_paths(inp, args.recursive)
        if not sql_paths:
            print(f"No .sql.sql files under {inp}", file=sys.stderr)
            return 1
        if args.stdout:
            print("--stdout requires a single .sql.sql file, not a folder", file=sys.stderr)
            return 2
        if args.output:
            print(
                "-o requires a single .sql.sql file; use --output-dir for a folder",
                file=sys.stderr,
            )
            return 2
        if args.name:
            print("--name applies only to a single .sql.sql file", file=sys.stderr)
            return 2
        out_dir: Path = args.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        used: dict[str, int] = {}
        failures = 0
        for path in sql_paths:
            try:
                data = parse_query_file(path, None)
                out = json.dumps(data, ensure_ascii=False, indent=4)
                base = safe_json_filename(query_name_from_path(path, None))
                fname = unique_output_name(base, used)
                out_path = out_dir / fname
                out_path.write_text(out + "\n", encoding="utf-8")
                print(f"Wrote {out_path.resolve()}", file=sys.stderr)
            except OSError as e:
                failures += 1
                print(f"Error writing {path}: {e}", file=sys.stderr)
            except Exception as e:
                failures += 1
                print(f"Error parsing {path}: {e}", file=sys.stderr)
        if failures:
            print(f"Done with {failures} error(s).", file=sys.stderr)
            return 1
        return 0

    if not inp.is_file():
        print(f"Not a file or folder: {inp}", file=sys.stderr)
        return 1
    if not inp.name.lower().endswith(".sql.sql"):
        print(f"Expected .sql.sql file: {inp}", file=sys.stderr)
        return 1

    path = inp
    data = parse_query_file(path, args.name)
    out = json.dumps(data, ensure_ascii=False, indent=4)
    if args.stdout:
        try:
            print(out)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((out + "\n").encode("utf-8"))
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out + "\n", encoding="utf-8")
        print(f"Wrote {args.output.resolve()}", file=sys.stderr)
    else:
        out_dir = args.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        base = safe_json_filename(query_name_from_path(path, args.name))
        out_path = out_dir / f"{base}.json"
        out_path.write_text(out + "\n", encoding="utf-8")
        print(f"Wrote {out_path.resolve()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
