from __future__ import annotations
import functools
import json
import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .constants import *

_logger = logging.getLogger(__name__)

# Access string literals ("..." or '...'); dotted tokens inside them are not field references
_STRING_LITERAL_RE = re.compile(r'"[^"]*"|\'[^\']*\'')


def normalize_vba_path_expression(expr: str) -> str:
    """Heuristic to convert VBA path expr to readable string."""
    s = expr.strip()
    # 1. Replace Format(Now, "...") with placeholders
    def format_repl(m):
        fmt = m.group(1).upper()
        # Simple replacements for common date formats
        fmt = fmt.replace("YYYY", "YYYY").replace("MM", "MM").replace("DD", "DD")
        fmt = fmt.replace("HH", "HH").replace("NN", "NN").replace("SS", "SS")
        return fmt

    s = re.sub(
        r"Format\s*\(\s*Now\s*,\s*\"([^\"]+)\"\s*\)", format_repl, s, flags=re.IGNORECASE
    )

    # 2. Split by & and process parts
    parts = s.split("&")
    clean_parts = []
    for p in parts:
        p = p.strip()
        if p.startswith('"') and p.endswith('"'):
            clean_parts.append(p[1:-1])
        elif p.lower().startswith("me."):
            clean_parts.append(f"[{p[3:]}]")
        elif p:
            # Handle variables/functions
            # Remove any trailing commas or stray args if regex was too greedy
            if "," in p:
                p = p.split(",")[0].strip()
            if not p.startswith("[") and not p.endswith("]"):
                clean_parts.append(f"[{p}]")
            else:
                clean_parts.append(p)

    res = "".join(clean_parts).replace("\\\\", "\\")
    return res
# TableName.field or TableName.[field] in Access SELECT (for mock query JSON resolution)
SELECT_TABLE_DOT_FIELD_RE = re.compile(
    r"(?:\[([^\]]+)\]|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+))\s*\.\s*(?:\[([^\]]+)\]|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+))"
)


def strip_placeholder_text(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_placeholder_text(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_placeholder_text(v) for v in obj]
    if isinstance(obj, str):
        return "" if " - " in obj else obj
    return obj


def build_skeleton(sample: dict[str, Any]) -> dict[str, Any]:
    base = strip_placeholder_text(deepcopy(sample))
    base["sheet_1_change_history"]["sheet_name"] = "Change History"
    base["sheet_2_layout"]["sheet_name"] = "Screen Spec (Layout)"
    base["sheet_3_screen_edit"]["sheet_name"] = "Screen Spec (Edit)"
    base["sheet_4_table_update"]["sheet_name_pattern"] = "Screen Spec (E***)"
    base["sheet_5_file_spec"]["sheet_name_pattern"] = "File Spec (E***)"
    base["sheet_1_change_history"]["data"] = []
    base["sheet_2_layout"]["record_sources"] = []
    base["sheet_2_layout"]["process_overview"] = []
    base["sheet_2_layout"]["events"] = []
    base["sheet_3_screen_edit"]["items"] = []
    base["sheet_4_table_update"]["items"] = []
    base["sheet_5_file_spec"]["items"] = []
    return base


def caption(control: dict[str, Any]) -> str:
    fmt = (control.get("properties") or {}).get("format") or {}
    cap = fmt.get("caption")
    if isinstance(cap, str) and cap.strip():
        return clean_value(cap)
    return ""


def control_name(control: dict[str, Any]) -> str:
    other = (control.get("properties") or {}).get("other") or {}
    return str(other.get("name") or control.get("name") or "")


def roman(n: int) -> str:
    values = "I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII XIX XX".split()
    return values[n] if n < len(values) else f"S{n+1}"


def sql_to_csharp(sql_type: str, length: str) -> str:
    s = (sql_type or "").upper()
    l = (length or "").strip()
    if "VARCHAR" in s or "CHAR" in s or "TEXT" in s:
        return "string"
    if "NUMBER" in s or "DECIMAL" in s or "NUMERIC" in s:
        if "," in l:
            try:
                parts = l.split(",")
                scale = parts[1].strip()
                if scale != "0":
                    return "decimal"
                precision = int(parts[0].strip())
                if precision == 1:
                    return "bool"
                if precision <= 9:
                    return "int"
                return "long"
            except:
                return "decimal"
        if l == "1":
            return "bool"
        return "int"
    if "INT" in s:
        return "int"
    if "DATE" in s or "TIME" in s:
        return "DateTime"
    return ""


def normalize_field_token(name: str) -> str:
    s = (name or "").strip()
    if s.startswith("[") and s.endswith("]") and len(s) >= 2:
        s = s[1:-1]
    return s.strip()


def clean_field_name(name: str) -> str:
    """Removes table prefix if present: [Table].[Field] -> Field"""
    s = (name or "").strip()
    if s.startswith("[") and "]." in s:
        # Handles [Table.With.Dots].[Field]
        m = re.match(r"^\[.*?\]\.(.*)$", s)
        if m:
            return normalize_field_token(m.group(1))
    if "." in s:
        return s.split(".")[-1].strip("[] ")
    return normalize_field_token(s)


def clean_value(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    # Convert literal Access newlines to actual newlines
    s = s.replace("\\015\\012", "\n")
    # Preserve actual newlines but strip trailing/leading whitespace
    return s.strip()


def format_input_checks(data: dict[str, Any], fmt: dict[str, Any]) -> str:
    checks = []
    mask = data.get("inputmask")
    if mask:
        checks.append(f"入力マスク: {mask}")

    vtext = data.get("validationtext") or fmt.get("validationtext")
    if vtext:
        checks.append(clean_value(vtext))

    return "; ".join(checks)


def build_control_maps(controls: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    label_caption_map: dict[str, str] = {}
    optiongroup_label_map: dict[str, str] = {}

    for c in controls:
        ctype = str(c.get("type") or "")
        other = (c.get("properties") or {}).get("other") or {}
        ctrl_name = str(other.get("name") or c.get("name") or "")
        if ctype == "Label":
            cap = caption(c)
            if ctrl_name and cap:
                label_caption_map[ctrl_name] = cap

    for c in controls:
        ctype = str(c.get("type") or "")
        other = (c.get("properties") or {}).get("other") or {}
        ctrl_name = str(other.get("name") or c.get("name") or "")
        if ctype == "OptionGroup":
            labelname = str(other.get("labelname") or "")
            if labelname and labelname in label_caption_map:
                optiongroup_label_map[ctrl_name] = label_caption_map[labelname]
            elif ctrl_name:
                optiongroup_label_map[ctrl_name] = caption(c) or ctrl_name
    return label_caption_map, optiongroup_label_map


def logical_name_for_ctrl(
    ctrl: dict[str, Any],
    label_caption_map: dict[str, str],
    optiongroup_label_map: dict[str, str],
) -> str:
    ctype = str(ctrl.get("type") or "")
    if ctype == "Subform":
        subform_name = str(
            ctrl.get("properties", {}).get("data", {}).get("sourceobject") or ctrl.get("name") or ""
        )
        if subform_name in SUBFORM_DOC_MAP:
            return SUBFORM_DOC_MAP[subform_name]
    return control_name(ctrl)


def descriptive_title_for_ctrl(
    ctrl: dict[str, Any],
    label_caption_map: dict[str, str],
    optiongroup_label_map: dict[str, str],
) -> str:
    own_caption = caption(ctrl)
    if own_caption:
        return own_caption

    other = (ctrl.get("properties") or {}).get("other") or {}
    labelname = str(other.get("labelname") or "")
    optiongroupname = str(other.get("optiongroupname") or "")

    res = ""
    if labelname and labelname in label_caption_map:
        res = label_caption_map[labelname]

    if optiongroupname and optiongroupname in optiongroup_label_map:
        group_caption = optiongroup_label_map[optiongroupname]
        if group_caption:
            res = f"{group_caption}: {res}" if res else group_caption

    return res


def is_english_name(name: str) -> bool:
    return bool(re.match(r'^[A-Za-z0-9_]+$', name))


def has_type_prefix(name: str) -> bool:
    """True when *name* already starts with a Hungarian control prefix (txtX, cboX, btnX, ...)."""
    for p in KNOWN_CTRL_PREFIXES:
        if name.startswith(p) and len(name) > len(p) and not name[len(p)].islower():
            return True
    return False


@functools.lru_cache(maxsize=1)
def _name_maps() -> tuple[dict, dict]:
    """(logical_to_physical, physical_to_logical) from layer2/schema; empty dicts when absent."""
    schema_dir = Path(__file__).resolve().parent.parent.parent.parent / "schema"
    maps = []
    for file_name in ("logical_to_physical.json", "physical_to_logical.json"):
        data = {}
        path = schema_dir / file_name
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                _logger.warning("[BD] Could not read %s: %s", path, e)
        maps.append(data if isinstance(data, dict) else {})
    if not any(maps):
        _logger.warning(
            "[BD] Name maps not found in %s; logical names fall back to captions/control names.", schema_dir
        )
    return maps[0], maps[1]


def resolve_names(logical_in: str, attribute: str, fallback_logical: str = "") -> tuple[str, str]:
    if not logical_in or logical_in == "-":
        return "", logical_in

    trans_map, p2l_map = _name_maps()

    prefix = ATTR_PREFIX.get(attribute, "")

    if is_english_name(logical_in):
        physical = logical_in
        logical_out = ""
        
        # 1. Try dedicated physical_to_logical map
        logical_out = p2l_map.get(physical)
        if not logical_out and prefix and physical.lower().startswith(prefix.lower()):
            base_en = physical[len(prefix):]
            logical_out = p2l_map.get(base_en) or p2l_map.get(base_en.capitalize()) or p2l_map.get(base_en.lower())
            
        # 2. Try reverse lookup from logical_to_physical map
        if not logical_out:
            reverse_map = {v: k for k, v in trans_map.items() if not k.startswith("TODO_")}
            logical_out = reverse_map.get(physical)
            if not logical_out and prefix and physical.lower().startswith(prefix.lower()):
                base_en = physical[len(prefix):]
                logical_out = reverse_map.get(base_en) or reverse_map.get(base_en.capitalize()) or reverse_map.get(base_en.lower())
        
        # 3. Fallback: caption/label of the control, else its own name
        if not logical_out:
            logical_out = fallback_logical or physical
            
        if prefix and not physical.lower().startswith(prefix.lower()) and not has_type_prefix(physical):
            physical = f"{prefix}{physical}"
            
        return physical, logical_out

    # Default logic
    eng_name = trans_map.get(logical_in)
    if not eng_name:
        eng_name = f"TODO_{logical_in}"
    
    if prefix and eng_name.lower().startswith(prefix.lower()):
        physical = eng_name
    else:
        physical = f"{prefix}{eng_name}" if prefix else eng_name
        
    return physical, logical_in

def field_table_map_from_query_select(
    select_sql: str, alias_map: dict[str, str] | None = None
) -> dict[str, str]:
    if not select_sql:
        return {}
    out = {}
    for m in SELECT_TABLE_DOT_FIELD_RE.finditer(select_sql):
        table = m.group(1) or m.group(2)
        field = m.group(3) or m.group(4)
        if table:
            table = table.strip()
            if alias_map and normalize_field_token(table) in alias_map:
                table = alias_map[normalize_field_token(table)]
        if field:
            field = normalize_field_token(field)
            if field and field not in out:
                out[field] = table
    return out


def extract_aliases_from_sql(sql_obj: dict) -> dict[str, str]:
    alias_map = {}
    from_clause = str(sql_obj.get("from") or "")
    if not from_clause or from_clause.lower() == "none":
        return alias_map

    # Clean SQL: remove ON clauses and normalize JOINs to commas for easy tokenization
    clean = re.sub(r'(?i)\s+ON\s+.*?(?=\s+(?:INNER|LEFT|RIGHT|FULL|CROSS)\s+JOIN|\)|$)', ' ', from_clause)
    clean = re.sub(r'(?i)\b(?:INNER|LEFT|RIGHT|FULL|CROSS|OUTER)\s+JOIN\b', ' , ', clean).replace('(', ' ').replace(')', ' ')
    
    parts = re.split(r'\s*,\s*', clean)
    for p in parts:
        # Match tokens: bracketed, quoted, or unquoted identifiers
        tokens = re.findall(r'\[([^\]]+)\]|"([^"]+)"|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+)', p)
        flat = [(t[0] or t[1] or t[2]).strip() for t in tokens if (t[0] or t[1] or t[2]).strip()]
        
        i = 0
        while i < len(flat) - 1:
            tbl = flat[i]
            alias = flat[i+1]
            
            # Skip if table name looks like a keyword (unlikely after cleaning)
            if tbl.lower() in ("select", "from", "where", "and", "or", "inner", "left", "join"):
                i += 1
                continue
                
            # Handle [Table] AS [Alias]
            if alias.upper() == "AS" and i < len(flat) - 2:
                alias = flat[i+2]
                i += 1
                
            # Validate alias
            if alias.lower() not in ("on", "join", "left", "right", "inner", "where", "group", "order", "as", "outer", "cross", "select", "from", "and", "or"):
                alias_map[normalize_field_token(alias)] = normalize_field_token(tbl)
            i += 1
            
    # Also check explicit join objects if present
    joins = sql_obj.get("join") or []
    for j in joins:
        table_val = j.get("table") if isinstance(j, dict) else (j if isinstance(j, str) else "")
        if table_val:
            tokens = re.findall(r'\[([^\]]+)\]|"([^"]+)"|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+)', table_val)
            flat = [(t[0] or t[1] or t[2]).strip() for t in tokens if (t[0] or t[1] or t[2]).strip()]
            if len(flat) >= 2:
                tbl = flat[0]
                alias = flat[1]
                if alias.upper() == "AS" and len(flat) >= 3:
                    alias = flat[2]
                if alias.lower() not in ("on", "join", "left", "right", "inner", "where", "group", "order", "as", "outer", "cross"):
                    alias_map[normalize_field_token(alias)] = normalize_field_token(tbl)
    return alias_map


def extract_all_field_expressions(select_sql: str) -> dict[str, str]:
    if not (select_sql or "").strip():
        return {}
    # Split SELECT clause by top-level commas
    parts = []
    curr = ""
    paren_cnt = 0
    in_quote = False
    for char in select_sql:
        if char == '"':
            in_quote = not in_quote
            curr += char
        elif not in_quote:
            if char == "(":
                paren_cnt += 1
            elif char == ")":
                paren_cnt -= 1
            if char == "," and paren_cnt == 0:
                parts.append(curr.strip())
                curr = ""
            else:
                curr += char
        else:
            curr += char
    if curr.strip():
        parts.append(curr.strip())

    exprs = {}
    for p in parts:
        m = re.search(r"(?i)\s+AS\s+([^ ]+)$", p)
        if m:
            alias = normalize_field_token(m.group(1))
            expr = p[: m.start()].strip()
            exprs[alias] = expr
    return exprs


def primary_table_from_query_doc(raw: dict[str, Any]) -> str:
    for t in raw.get("tables") or []:
        ts = str(t)
        if "TBL" in ts or "WSTEM" in ts or ts.startswith("M_"):
            return ts
    if raw.get("tables"):
        return str(raw["tables"][0])
    from_clause = (raw.get("query") or {}).get("from") or raw.get("from") or ""
    if isinstance(from_clause, str) and from_clause.strip():
        s = from_clause.strip().lstrip("(")
        m = re.match(
            r"^(?:\[([^\]]+)\]|([A-Za-z0-9_＿一-龯ぁ-ゔァ-ヶー]+))",
            s,
        )
        if m:
            return (m.group(1) or m.group(2)).strip()
    return ""


def prepare_query_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    q = raw.get("query") or raw
    select_sql = ""
    if isinstance(q, dict):
        select_sql = str(q.get("select") or "")
    doc = {**raw}
    sql_obj = q.get("sql") or q if isinstance(q, dict) else {}
    alias_map = extract_aliases_from_sql(sql_obj)
    doc["_alias_to_table"] = alias_map
    doc["_field_to_table"] = field_table_map_from_query_select(select_sql, alias_map)
    doc["_field_expressions"] = extract_all_field_expressions(select_sql)
    doc["_primary_table"] = primary_table_from_query_doc(raw)
    
    # Extract form inputs from parameters: e.g. "[forms]![C000_MAINⅡ]![txt期]"
    inputs = {}
    params = raw.get("parameters") or {}
    for p_val in params.values():
        p_str = str(p_val)
        # Match [forms]![FormName]![FieldName] or Forms!FormName!FieldName
        m = re.search(r"(?:Forms|\[Forms\])!\[?([^!\]]+)\]?!\[?([^!\]]+)\]?", p_str, re.IGNORECASE)
        if m:
            f_name = m.group(1).strip()
            field = m.group(2).strip()
            inputs.setdefault(f_name, []).append(field)
    doc["_form_inputs"] = inputs
    return doc


def load_query_mock_index(paths: list[Path], dirs: list[Path]) -> dict[str, dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    seen_files: set[Path] = set()

    def ingest_file(p: Path) -> None:
        if not p.is_file() or p in seen_files:
            return
        seen_files.add(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        name = (data.get("name") or data.get("query_name") or p.stem.replace("raw_query_", "", 1)).strip()
        if not name:
            return
        by_name[name] = prepare_query_metadata(data)

    for p in paths:
        ingest_file(p)
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("raw_query_*.json")):
            ingest_file(p)
    return by_name


def extract_field_references(expr: str) -> list[str]:
    # Match [Field] or Table.Field or [Table].[Field]
    refs = []
    # 1. Match bracketed parts: [Table].[Field] or [Field]
    for m in re.finditer(r"\[([^\]]+)\]", expr):
        full = m.group(0)
        # Check if followed by .[Field] or .Field
        start = m.end()
        if start < len(expr) and expr[start] == ".":
            next_part = expr[start + 1 :]
            m_fld = re.match(r"^\[([^\]]+)\]|^([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+)", next_part)
            if m_fld:
                full = f"{full}.{m_fld.group(0)}"
        refs.append(full)

    # 2. Match unbracketed Table.Field (outside string literals, e.g. not Format(x,"yyyy.mm.dd"))
    for m in re.finditer(
        r"(?<![\[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b])([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+)\.([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+|\[[^\]]+\])",
        _STRING_LITERAL_RE.sub(lambda lit: " " * len(lit.group(0)), expr),
    ):
        refs.append(m.group(0))

    return list(dict.fromkeys(refs))

def resolve_source_table_field(
    control_source: str,
    recordsource: str,
    query_meta: dict[str, Any] | None,
    query_index: dict[str, Any] | None = None,
    depth: int = 0,
) -> tuple[str, str, str]:
    """
    Returns (source_table, source_field_or_value, extra_note).
    Recursively resolves query sources to find the physical table.
    """
    cs = (control_source or "").strip()
    if not cs:
        return "", "", ""

    if depth > 5:
        return "", cs, ""

    # Handle DLookUp
    dlookup_match = re.match(
        r'^=DLookUp\s*\(\s*[\\"\']+(.*?)[\\"\']+\s*,\s*[\\"\']+(.*?)[\\"\']+',
        cs,
        re.IGNORECASE,
    )
    if dlookup_match:
        fld_name = dlookup_match.group(1).strip()
        domain_name = dlookup_match.group(2).strip()
        q_meta = query_index.get(domain_name) if query_index else None
        return resolve_source_table_field(fld_name, domain_name, q_meta, query_index, depth + 1)

    def finalize(tbl: str, fld: str) -> tuple[str, str, str]:
        t_str = str(tbl).strip()
        if query_index:
            norm_t = normalize_field_token(t_str)
            if t_str in query_index:
                return resolve_source_table_field(
                    fld, t_str, query_index[t_str], query_index, depth + 1
                )
            if norm_t in query_index:
                return resolve_source_table_field(
                    fld, norm_t, query_index[norm_t], query_index, depth + 1
                )
        return t_str, fld, ""

    # Handle expressions or aliases
    expr_to_resolve = None
    if cs.startswith("="):
        expr_to_resolve = cs[1:].strip()
    elif query_meta:
        exprs = query_meta.get("_field_expressions") or {}
        if normalize_field_token(cs) in exprs:
            expr_to_resolve = exprs[normalize_field_token(cs)]

    if expr_to_resolve:
        # Check if it's just a single field reference
        if re.match(r"^\[?[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+\]?$", expr_to_resolve):
             # Simple field, just resolve it normally
             return resolve_source_table_field(expr_to_resolve, recordsource, query_meta, query_index, depth + 1)
        
        # It's a complex expression. Extract all field references.
        refs = extract_field_references(expr_to_resolve)
        if not refs:
            return "", expr_to_resolve, ""
            
        all_tbls = []
        all_flds = []
        for r in refs:
            t, f, _ = resolve_source_table_field(r, recordsource, query_meta, query_index, depth + 1)
            all_tbls.append(t if t else "")
            all_flds.append(f if f else "")
            
        # Clean expression for note: replace & with - etc.
        clean_expr = expr_to_resolve.replace("&", "-").replace('"', "").replace(" ", "").replace("[", "").replace("]", "")
        return "\n".join(all_tbls), "\n".join(all_flds), clean_expr

    # Standard field resolution
    if "." in cs:
        if cs.startswith("["):
            match = re.match(r"^(\[.*?\])\.(.*)$", cs)
            if match:
                left, right = match.group(1), match.group(2)
            else:
                left, right = "", cs
        else:
            left, right = cs.split(".", 1)
            
        left, right = left.strip(), right.strip()
        field = normalize_field_token(right)
        
        # Check alias map first (query_meta is None for table-bound or unbound forms)
        alias_map = (query_meta or {}).get("_alias_to_table") or {}
        norm_left = normalize_field_token(left)
        if norm_left in alias_map:
            return finalize(alias_map[norm_left], field)

        if query_meta and recordsource and normalize_field_token(left) == normalize_field_token(str(recordsource)):
            fmap: dict[str, str] = query_meta.get("_field_to_table") or {}
            if field in fmap:
                return finalize(fmap[field], field)
        if query_meta and recordsource:
            tables_list = {normalize_field_token(str(t)) for t in (query_meta.get("tables") or [])}
            if normalize_field_token(left) in tables_list:
                return finalize(left, field)
        return left, field, ""

    field = normalize_field_token(cs)
    if not query_meta:
        if recordsource:
            return finalize(recordsource, field)
        return "", field, ""

    fmap: dict[str, str] = query_meta.get("_field_to_table") or {}
    if field in fmap:
        return finalize(fmap[field], field)

    primary = str(query_meta.get("_primary_table") or "")
    if primary:
        return finalize(primary, field)

    if recordsource:
        return finalize(recordsource, field)

    return "", field, ""

def format_source_table_names(src_tbl: str) -> str:
    if src_tbl:
        parts = []
        for t in src_tbl.split("\n"):
            t = t.strip()
            if t and not t.startswith("["):
                parts.append(f"[{t}]")
            elif t:
                parts.append(t)
        src_tbl = "\n".join(parts)
    return src_tbl
