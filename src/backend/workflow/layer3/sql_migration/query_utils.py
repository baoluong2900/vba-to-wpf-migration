"""
sql_migration/query_utils.py — Pure helpers shared by the Layer 3 router and query seeder.
"""
from __future__ import annotations

import re

# Layer 1 writes "なし" ("none") for clauses a query does not have.
_EMPTY_CLAUSE = "なし"
_SELECT_CLAUSES = (
    ("select", "SELECT"),
    ("from", "FROM"),
    ("where", "WHERE"),
    ("group_by", "GROUP BY"),
    ("order_by", "ORDER BY"),
)

# Characters allowed in a bind-variable name: ASCII word characters plus the Japanese ranges
# Access designs use (kanji, kana, 々, full-width forms) and Roman numerals such as "Ⅱ".
_NAME_CHARS = r"A-Za-z0-9_＿々぀-ゟ゠-ヿ一-鿿＀-￯Ⅰ-Ⅻ"
# ":name" — but not the PostgreSQL cast "x::type", and not the "12:30" of a time value.
_BIND_VAR_RE = re.compile(rf"(?<![:\w]):(?!:)\s*([{_NAME_CHARS}]+)")
_STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")
_DELETE_TABLE_RE = re.compile(r"\bFROM\s+(\S+)", re.IGNORECASE)


def _clause(query: dict, key: str) -> str:
    value = query.get(key)
    return "" if not value or value == _EMPTY_CLAUSE else value


def build_sql_from_parts(query: dict | None) -> str:
    """
    Rebuild Access SQL from Layer 1's structured query dict. Only a fallback for documents
    seeded before query_parser stored the original text as the top-level ``sql``.
    """
    q = query or {}
    if q.get("unparsed"):
        return q.get("sql") or ""

    lines: list[str] = []
    if _clause(q, "update"):
        sets = q.get("set") or []
        lines += [f"UPDATE {q['update']}", "SET " + (", ".join(sets) if isinstance(sets, list) else str(sets))]
    elif _clause(q, "delete"):
        lines.append(f"DELETE {q['delete'].strip()}")
    elif _clause(q, "insert_into"):
        values = q.get("values") if isinstance(q.get("values"), dict) else {}
        lines.append(f"INSERT INTO {q['insert_into']}" + (f" ({', '.join(values)})" if values else ""))
        if not _clause(q, "select"):
            lines.append(f"VALUES ({', '.join(values.values())})")
    if _clause(q, "transform"):
        lines.append(f"TRANSFORM {q['transform']}")
    lines += [f"{keyword} {_clause(q, key)}" for key, keyword in _SELECT_CLAUSES if _clause(q, key)]
    return "\n".join(lines)


def query_type_of(query: dict | None) -> str:
    """select | transform | update | delete | insert | unknown, from the structured query."""
    q = query or {}
    if q.get("unparsed"):
        return "unknown"
    for key, qtype in (("update", "update"), ("delete", "delete"), ("insert_into", "insert"), ("transform", "transform")):
        if _clause(q, key):
            return qtype
    return "select" if _clause(q, "select") else "unknown"


def target_table_of(query: dict | None) -> str | None:
    """The table an action query writes to (UPDATE / INSERT INTO / DELETE … FROM), else None."""
    q = query or {}
    if _clause(q, "update"):
        return q["update"].strip()
    if _clause(q, "insert_into"):
        return q["insert_into"].strip()
    if _clause(q, "delete"):
        match = _DELETE_TABLE_RE.search(q["delete"])
        return match.group(1) if match else None
    return None


def extract_bind_variables(sql: str | None) -> list[str]:
    """Bind variables (``:name``) outside string literals, in first-seen order, without duplicates."""
    code = _STRING_LITERAL_RE.sub("''", sql or "")
    return list(dict.fromkeys(_BIND_VAR_RE.findall(code)))
