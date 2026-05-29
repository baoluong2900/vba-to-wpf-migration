"""
Shared utilities for mapping SQL queries to D2 Skeleton sheets.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, List, Dict, Optional

def _get_mapped_query(name: str, table_config: dict) -> Optional[str]:
    if not table_config: return None
    mappings = table_config.get("table_mappings", {})
    val = mappings.get(name)
    if val and val not in ("main", "master", "export", "temporary"):
        return val
    return None

class TableResolver:
    def __init__(self, l1_dir: Optional[Path] = None, repo: Any = None, table_config: dict = None):
        self.l1_dir = l1_dir
        self.repo = repo
        self.table_config = table_config or {}
        self.cache: Dict[str, List[str]] = {}

    def get_table_fields(self, table_name: str) -> List[str]:
        if not table_name: return []
        
        mapped_q = _get_mapped_query(table_name, self.table_config)
        effective_name = mapped_q if mapped_q else table_name
        
        if effective_name in self.cache: return self.cache[effective_name]
        
        # 1. Try local physical table JSON
        if self.l1_dir:
            file_path = self.l1_dir / f"{effective_name}.json"
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        fields = [c.get("physical_name") for c in data.get("columns", [])]
                        self.cache[table_name] = fields
                        return fields
                except Exception: pass
        
        # 2. Try database query logic via repo
        if self.repo:
            from db.query_dd import get_dd_code_json_query_raw
            try:
                q_doc = get_dd_code_json_query_raw(self.repo, effective_name)
                if q_doc:
                    # Get fields from "columns" (D4 format)
                    fields = [c.get("column_name") or c.get("physical_name") for c in q_doc.get("columns", [])]
                    if fields:
                        self.cache[table_name] = fields
                        return fields
            except Exception: pass

        self.cache[table_name] = []
        return []

    def resolve_field_to_table(self, field_name: str, tables_str: str) -> str:
        if not tables_str: return ""
        tables_list = [t.strip() for t in tables_str.split("\n") if t.strip()]
        if len(tables_list) <= 1: return tables_str
        clean_field = field_name.strip('[]')
        matches = [tbl for tbl in tables_list if clean_field in self.get_table_fields(tbl)]
        if len(matches) == 1: return matches[0]
        elif len(matches) > 1: return "\n".join(matches)
        return tables_str

SELECT_TABLE_DOT_FIELD_RE = re.compile(r"([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ\[\]一-龯ぁ-ゔァ-ヶー＜＞]+)\s*\.\s*(?:\[([^\]]+)\]|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+))")

def normalize_parameters(params: Any) -> list[dict[str, str]]:
    if not params: return []
    if isinstance(params, dict): return [{"key": str(key), "value": str(value)} for key, value in params.items()]
    if isinstance(params, list):
        res = []
        for item in params:
            if isinstance(item, dict):
                if "key" in item and "value" in item: res.append({"key": str(item["key"]), "value": str(item["value"])})
                elif len(item) == 1: k = next(iter(item)); res.append({"key": str(k), "value": str(item[k])})
        return res
    return []

def replace_query_parameters(text: str, params: list[dict[str, str]]) -> str:
    if not text: return text
    output = text
    for param in params:
        key = param.get("key", "")
        if key: output = output.replace(f"@{key}", "＜パラメータ＞." + key)
    return output

def get_params_info(sql_obj: dict, q_data: dict, screen_id: str = None):
    """
    Extract and format parameter information from query data and SQL string.
    Returns:
        detailed_str (str): A multi-line string for display in Sheet 3 blocks.
        param_list (list): A list of normalized parameter dictionaries.
    """
    # 1. Get explicit parameters from metadata
    params = sql_obj.get("parameters") or q_data.get("parameters")
    param_list = normalize_parameters(params)
    
    # 2. Extract from SQL if metadata is sparse
    raw_sql = sql_obj.get("raw_sql") or ""
    if not raw_sql and isinstance(sql_obj.get("sql_logic"), dict):
        logic = sql_obj["sql_logic"]
        raw_sql = f"{logic.get('select','')} {logic.get('from','')} {logic.get('where','')} {logic.get('set','')} {logic.get('update','')} {logic.get('values','')}"
    elif not raw_sql:
        # Fallback for old skeleton format
        raw_sql = f"{sql_obj.get('select','')} {sql_obj.get('from','')} {sql_obj.get('where','')} {sql_obj.get('set','')} {sql_obj.get('update','')} {sql_obj.get('values','')} {sql_obj.get('insert_into','')}"

    if raw_sql:
        found_p = re.findall(r'[:@]([a-zA-Z0-9_＿一-龯ぁ-ゔァ-ヶー]+)', str(raw_sql))
        found_f = re.findall(r'(?i)\[?forms\]?!\[?([^\]!]+)\]?!\[?([^\]!]+)\]?', str(raw_sql))
        
        existing_keys = {str(p.get("key", "")).lower() for p in param_list}
        for p in found_p:
            if p.lower() not in existing_keys:
                param_list.append({"key": p, "value": ""})
                existing_keys.add(p.lower())
        for f_form, f_ctrl in found_f:
            key = f"Forms!{f_form}!{f_ctrl}"
            if key.lower() not in existing_keys:
                param_list.append({"key": key, "value": f"[{f_form}]![{f_ctrl}]"})
                existing_keys.add(key.lower())

    # 3. Format for display in Sheet 3
    display_lines = []
    for p in param_list:
        key = str(p.get("key", ""))
        val = p.get("value", "")
        if val:
            fmt_val = re.sub(r"(?i)\[?forms\]?!\[?([^\]!]+)\]?!\[?([^\]!]+)\]?", r"＜パラメータ＞.\2", str(val))
            display_lines.append(f"{key}: {fmt_val}")
        else:
            if "!" in key and "forms" in key.lower():
                 fmt_key = re.sub(r"(?i)\[?forms\]?!\[?([^\]!]+)\]?!\[?([^\]!]+)\]?", r"＜パラメータ＞.\2", key)
                 display_lines.append(f"{key}: {fmt_key}")
            elif screen_id and (key.startswith("txt") or key.startswith("cmb") or key.startswith("lbl") or key.startswith("chk")):
                 display_lines.append(f"{key}: ＜パラメータ＞.{key}")
            else:
                 display_lines.append(key)
    
    detailed_str = "\n".join(display_lines)
    return detailed_str, param_list, display_lines

def generate_query_table_json(q_type_label: str, sheet_name: str, display_lines: list[str], output_items: list[str] = None) -> str:
    """
    Generates a markdown table-like string formatted for Sheet 3 event_content.
    """
    lines = []
    lines.append(f"| Query名 | {sheet_name} |")
    lines.append("| :--- | :--- |")
    lines.append("| パラメータ | I/O | 編集仕様 |")
    
    # Input parameters
    for line in display_lines:
        if ":" in line:
            parts = line.split(":", 1)
            p_name = parts[0].strip()
            p_spec = parts[1].strip()
            lines.append(f"| {p_name} | I | {p_spec} |")
        else:
            lines.append(f"| {line.strip()} | I | - |")
            
    # Output items (if any)
    if output_items:
        for item in output_items:
            lines.append(f"| {item} | O | オブジェクト |")
    elif not display_lines:
        lines.append("| なし | - | - |")
        
    return "\n".join(lines)

def get_where_conditions(where_condition: str, param_list: list[dict[str, str]]) -> list[dict[str, str]]:
    if not where_condition or where_condition == "なし": return []
    res = []
    for w in where_condition.split("AND"):
        res.append({"condition": replace_query_parameters(w, param_list).strip(), "notes": ""})
    return res

def get_table_names_from_from(from_clause: str) -> str:
    if not from_clause or from_clause == "なし": return ""
    clean = re.sub(r'(?i)\s+ON\s+.*?(?=\s+(?:INNER|LEFT|RIGHT|FULL|CROSS)\s+JOIN|\)|$)', ' ', from_clause)
    clean = re.sub(r'(?i)\b(?:INNER|LEFT|RIGHT|FULL|CROSS|OUTER)\s+JOIN\b', ' ', clean).replace('(', ' ').replace(')', ' ')
    tables = []
    # Match [brackets], "quotes", or unquoted identifiers
    for m in re.findall(r'\[([^\]]+)\]|"([^"]+)"|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+)', clean):
        tbl = (m[0] or m[1] or m[2]).strip()
        if tbl and tbl.upper() not in ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'AS', 'ON', 'IN', 'INNER', 'LEFT', 'RIGHT', 'FULL', 'JOIN', 'OUTER', 'DISTINCT', 'ALL', 'TOP', 'GROUP', 'BY', 'ORDER', 'HAVING', 'UNION']:
            tables.append(tbl)
    return "\n".join(list(dict.fromkeys(tables)))

def parse_aliases(from_clause: str) -> dict[str, str]:
    if not from_clause or from_clause == "なし": return {}
    clean = re.sub(r'(?i)\s+ON\s+.*?(?=\s+(?:INNER|LEFT|RIGHT|FULL|CROSS)\s+JOIN|\)|$)', ' ', from_clause)
    clean = re.sub(r'(?i)\b(?:INNER|LEFT|RIGHT|FULL|CROSS|OUTER)\s+JOIN\b', ' ', clean).replace('(', ' ').replace(')', ' ')
    parts = re.split(r'\s*,\s*', clean)
    aliases = {}
    for p in parts:
        # Match [brackets], "quotes", or unquoted identifiers
        tokens = re.findall(r'\[([^\]]+)\]|"([^"]+)"|([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+)', p)
        if len(tokens) >= 2:
            tbl = tokens[0][0] or tokens[0][1] or tokens[0][2]
            # Check for AS keyword
            idx = 1
            if (tokens[1][0] or tokens[1][1] or tokens[1][2]).upper() == "AS" and len(tokens) >= 3:
                idx = 2
            alias = tokens[idx][0] or tokens[idx][1] or tokens[idx][2]
            if alias.upper() not in ['ON', 'IN', 'INNER', 'LEFT', 'RIGHT', 'FULL', 'JOIN', 'OUTER', 'AS', 'SELECT', 'FROM', 'WHERE']:
                aliases[alias] = tbl
    return aliases

def extract_source_info(expression: str, default_table: str, param_list: list[dict[str, str]], table_resolver: Optional[TableResolver] = None, alias_map: dict = None) -> tuple[str, str, bool]:
    has_alias = bool(re.search(r'(?i)\s+AS\s+[^ ]+$', expression))
    expr = re.sub(r'(?i)\s+AS\s+[^ ]+$', '', expression).strip()
    
    # Handle known constants and functions
    if re.fullmatch(r"'.*?'|\".*?\"|-?\d+(\.\d+)?|SYSDATE|NULL|CURRENT_DATE|CURRENT_TIMESTAMP", expr, re.IGNORECASE):
        return "", expr, has_alias

    # Fast path for raw parameters like :登録日 or @登録日
    param_match = re.fullmatch(r'[:@]([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+)', expr)
    if param_match:
        fld = param_match.group(1)
        return "＜パラメータ＞", fld, has_alias

    dot_full_match = SELECT_TABLE_DOT_FIELD_RE.fullmatch(expr)
    if dot_full_match:
        tbl = dot_full_match.group(1).strip('[]')
        fld = dot_full_match.group(2) or dot_full_match.group(3)
        fld = fld.strip('[]')
        res_tbl = alias_map.get(tbl, tbl) if alias_map else tbl
        return res_tbl, fld, has_alias

    bracket_full_match = re.fullmatch(r"\[([^\]]+)\]", expr)
    if bracket_full_match:
        fld = bracket_full_match.group(1)
        for p in param_list:
            if p["key"] == fld:
                return "＜パラメータ＞", fld, has_alias
        
        if table_resolver:
            res_tbl = table_resolver.resolve_field_to_table(fld, default_table)
            return (alias_map.get(res_tbl, res_tbl) if alias_map else res_tbl), fld, has_alias
        return default_table, fld, has_alias

    if re.fullmatch(r'^[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+$', expr):
        for p in param_list:
            if p["key"] == expr:
                return "＜パラメータ＞", expr, has_alias
        
        if default_table:
            if table_resolver:
                res_tbl = table_resolver.resolve_field_to_table(expr, default_table)
                return (alias_map.get(res_tbl, res_tbl) if alias_map else res_tbl), expr, has_alias
            return default_table, expr, has_alias

    dot_matches = SELECT_TABLE_DOT_FIELD_RE.findall(expr)
    if dot_matches:
        tables = []
        fields = []
        for m in dot_matches:
            tbl = m[0].strip('[]')
            fld = m[1] or m[2]
            res_tbl = alias_map.get(tbl, tbl) if alias_map else tbl
            tables.append(res_tbl)
            fields.append(fld.strip('[]'))
        return "\n".join(list(dict.fromkeys(tables))), " \n ".join(list(dict.fromkeys(fields))), True

    bracket_matches = re.findall(r"\[([^\]]+)\]", expr)
    if bracket_matches:
        fields = []
        tables = []
        for fld in bracket_matches:
            is_param = False
            for p in param_list:
                if p["key"] == fld:
                    tables.append("＜パラメータ＞." + fld)
                    fields.append(fld)
                    is_param = True
                    break
            if not is_param:
                fields.append(fld)
        
        res_tables_str = "\n".join(list(dict.fromkeys(tables)))
        if not res_tables_str and fields:
            if table_resolver:
                unique_fields = list(dict.fromkeys(fields))
                resolved_tables = []
                for fld in unique_fields:
                    res_tbl = table_resolver.resolve_field_to_table(fld, default_table)
                    resolved_tables.append(alias_map.get(res_tbl, res_tbl) if alias_map else res_tbl)
                res_tables_str = "\n".join(list(dict.fromkeys(resolved_tables)))
            else:
                res_tables_str = default_table
            
        return res_tables_str, " \n ".join(list(dict.fromkeys(fields))), True

    return "", expr, True

def get_balanced_paren_content(text: str, start_idx: int) -> str:
    count = 0
    for i in range(start_idx, len(text)):
        if text[i] == '(': count += 1
        elif text[i] == ')':
            count -= 1
            if count == 0: return text[start_idx + 1:i]
    return text[start_idx + 1:]

def clean_field_notation(text: str) -> str:
    text = re.sub(r'[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+\.([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+)', r'[\1]', text)
    text = re.sub(r'[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+\.\[([^\]]+)\]', r'[\1]', text)
    text = re.sub(r'[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+\."([^"]+)"', r'[\1]', text)
    if re.fullmatch(r'[A-Za-z_＿Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー][A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]*', text):
        text = f"[{text}]"
    return text

def parse_iif_recursive(expr: str, start_idx: int = 1) -> list[str]:
    m = re.search(r'(?i)IIf\(', expr)
    if not m: return []
    content = get_balanced_paren_content(expr, m.start() + 3)
    parts, curr, p_cnt = [], "", 0
    for char in content:
        if char == '(': p_cnt += 1
        elif char == ')': p_cnt -= 1
        if char == ',' and p_cnt == 0: parts.append(curr.strip()); curr = ""
        else: curr += char
    parts.append(curr.strip())
    if len(parts) < 3: return []
    cond = re.sub(r'\[([^\]]+)\]\s*=\s*"([^"]+)"', r'[\1]が「\2」の場合', parts[0])
    cond = re.sub(r'\[([^\]]+)\]\s*=\s*([0-9A-Za-z]+)', r'[\1]が「\2」の場合', cond)
    cond = re.sub(r'[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+\.([A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+)', r'[\1]', cond)
    true_val = parts[1].strip('"')
    lines = [f"{start_idx}. {cond}、「{true_val}」を設定する"]
    if "IIf(" in parts[2].upper(): lines.extend(parse_iif_recursive(parts[2], start_idx + 1))
    else:
        else_val = parts[2].strip('" ')
        if else_val and else_val.upper() != "NULL":
            lines.append(f"{start_idx + 1}. 上記以外の場合、「{else_val}」を設定する")
    return lines

def parse_case_recursive(expr: str, start_idx: int = 1) -> list[str]:
    m = re.search(r'(?i)\bCASE\b\s+(.*?)\s+\bEND\b', expr, re.DOTALL)
    if not m: return []
    content = m.group(1).strip()
    lines, curr_idx = [], start_idx
    parts = re.split(r'(?i)\bWHEN\b', content)
    base_expr = parts[0].strip()
    for p in parts[1:]:
        if not p.strip(): continue
        tp = re.split(r'(?i)\bTHEN\b', p, maxsplit=1)
        if len(tp) < 2: continue
        cond, rest = tp[0].strip(), tp[1].strip()
        res_val = re.split(r'(?i)\bELSE\b', rest)[0].strip()
        if base_expr:
            _cond_stripped = cond.strip("'\" ")
            c_txt = f"{clean_field_notation(base_expr)}が「{_cond_stripped}」"
        else:
            c_txt = clean_field_notation(cond)
            val_pat = r'(\[[^\]]+\]|[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+)'
            c_txt = re.sub(r'\s*=\s*[\'"](.*?)[\'"]', r'が「\1」', c_txt)
            c_txt = re.sub(r'\s*<>\s*[\'"](.*?)[\'"]', r'が「\1」以外', c_txt)
            c_txt = re.sub(r'\s*>=\s*' + val_pat, r'が\1以上', c_txt)
            c_txt = re.sub(r'\s*<=\s*' + val_pat, r'が\1以下', c_txt)
            c_txt = re.sub(r'\s*<>\s*' + val_pat, r'が\1以外', c_txt)
            c_txt = re.sub(r'\s*=\s*' + val_pat, r'が\1', c_txt)
            c_txt = re.sub(r'\s*>\s*' + val_pat, r'が\1より大きい', c_txt)
            c_txt = re.sub(r'\s*<\s*' + val_pat, r'が\1より小さい', c_txt)
            c_txt = re.sub(r'\s*IS\s+NULL', r'が未設定', c_txt, flags=re.I)
            c_txt = re.sub(r'\s*IS\s+NOT\s+NULL', r'が設定されている', c_txt, flags=re.I)
        _res_stripped = res_val.strip("'\" ")
        lines.append(f"{curr_idx}. {c_txt}の場合、「{_res_stripped}」を設定する")
        curr_idx += 1
    m_else = re.search(r'(?i)\bELSE\b\s+([^END]*)$', content, re.DOTALL)
    if m_else:
        else_val = m_else.group(1).strip().strip("'\" ")
        if else_val and else_val.upper() != "NULL":
            lines.append(f"{curr_idx}. 上記以外の場合、「{else_val}」を設定する")
    return lines

def parse_decode_recursive(expr: str, start_idx: int = 1) -> list[str]:
    m = re.search(r'(?i)DECODE\(', expr)
    if not m: return []
    content = get_balanced_paren_content(expr, m.start() + 6)
    parts, curr, p_cnt = [], "", 0
    for char in content:
        if char == '(': p_cnt += 1
        elif char == ')': p_cnt -= 1
        if char == ',' and p_cnt == 0: parts.append(curr.strip()); curr = ""
        else: curr += char
    parts.append(curr.strip())
    if len(parts) < 3: return []
    base_expr, lines, curr_idx, i = clean_field_notation(parts[0]), [], start_idx, 1
    while i + 1 < len(parts):
        search, res = parts[i].strip("'\" "), parts[i+1].strip("'\" ")
        lines.append(f"{curr_idx}. {base_expr}が「{search}」の場合、「{res}」を設定する")
        curr_idx += 1; i += 2
    if i < len(parts):
        default_val = parts[i].strip("'\" ")
        if default_val and default_val.upper() != "NULL":
            lines.append(f"{curr_idx}. 上記以外の場合、「{default_val}」を設定する")
    return lines

def format_notes(expression: str) -> str:
    if not expression: return ""
    expr = re.sub(r'(?i)\s+AS\s+[^ ]+$', '', expression).strip()
    steps = []
    # 1. Aggregate
    m_sum = re.search(r'(?i)SUM\(', expr)
    m_count = re.search(r'(?i)COUNT\(', expr)
    if m_sum:
        inner = get_balanced_paren_content(expr, m_sum.start() + 3)
        steps.append(f"{len(steps)+1}. {clean_field_notation(inner.strip())}を合計する")
    elif m_count:
        inner = get_balanced_paren_content(expr, m_count.start() + 5)
        f_match = re.search(r'\[([^\]]+)\]', inner) or re.search(r'"([^"]+)"', inner) or re.search(r'[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー]+', inner)
        disp = f_match.group(0) if f_match else inner
        steps.append(f"{len(steps)+1}. {clean_field_notation(disp.strip())}の件数をカウントする")
    
    # 2. NVL / COALESCE
    if re.search(r'(?i)(NVL|COALESCE)\(', expr): steps.append(f"{len(steps)+1}. 値が Null の場合は 0 を設定する")
    
    # 3. TO_NUMBER
    if re.search(r'(?i)TO_NUMBER\(', expr): steps.append(f"{len(steps)+1}. 結果を数値として変換する")
    
    # 4. TO_CHAR
    m_fmt = re.search(r"(?i)TO_CHAR\s*\((.*),\s*'([^']*)'\)", expr)
    if m_fmt: steps.append(f"{len(steps)+1}. {clean_field_notation(m_fmt.group(1).strip('() '))}を「{m_fmt.group(2)}」形式で取得する")
    
    # 5. || (Concatenation)
    if "||" in expr:
        literals = re.findall(r"\|\|\s*'([^']*)'", expr)
        if literals:
            for lit in literals:
                steps.append(f"{len(steps)+1}. 「{lit}」を付加する")
        else:
            steps.append(f"{len(steps)+1}. 各項目を結合する")
            
    # 6. String functions (SUBSTR, INSTR)
    if re.search(r'(?i)SUBSTR\(', expr): steps.append(f"{len(steps)+1}. {clean_field_notation(expr.strip())}から文字列の一部を抽出する")
    if re.search(r'(?i)INSTR\(', expr): steps.append(f"{len(steps)+1}. {clean_field_notation(expr.strip())}から特定の文字が出現する位置を検索する")
    
    # 7. CASE / DECODE
    if re.search(r'(?i)\bCASE\b', expr): steps.extend(parse_case_recursive(expr, len(steps)+1))
    elif re.search(r'(?i)DECODE\(', expr): steps.extend(parse_decode_recursive(expr, len(steps)+1))
    
    # 8. IIf
    if re.search(r'(?i)IIf\(', expr): steps.extend(parse_iif_recursive(expr))
    
    # 9. Math functions
    if re.search(r'(?i)MOD\(', expr): 
        m = re.search(r'(?i)MOD\((.*),(.*)\)', expr)
        if m:
            dividend, divisor = m.group(1).strip(), m.group(2).strip()
            c_dividend = clean_field_notation(dividend)
            c_divisor = clean_field_notation(divisor)
            steps.append(f"{len(steps)+1}. {c_dividend} ÷ {c_divisor}の余りを計算する")
    if not steps and any(op in expr for op in ['+', '-', '*', '/']):
        cleaned = clean_field_notation(expr)
        cleaned = re.sub(r'\s*([+\-*/])\s*', r' \1 ', cleaned)
        steps.append(f"{len(steps)+1}. {cleaned.strip()}を計算する")

    return "\n".join(steps)

def split_toplevel_commas(s: str) -> list[str]:
    if not s or s == "なし": return []
    parts, curr, p_cnt, in_q = [], "", 0, False
    for char in s:
        if char in ('"', "'"):
            in_q = not in_q
            curr += char
        elif char == '(' and not in_q:
            p_cnt += 1
            curr += char
        elif char == ')' and not in_q:
            p_cnt -= 1
            curr += char
        elif char == ',' and not in_q and p_cnt == 0:
            parts.append(curr.strip())
            curr = ""
        else:
            curr += char
    if curr.strip():
        parts.append(curr.strip())
    return parts

def get_base_table_from_from(from_clause: str) -> str:
    if not from_clause or from_clause == "なし": return ""
    parts = split_toplevel_commas(from_clause)
    if not parts: return ""
    text = parts[0].strip()
    first_join_match = re.search(r"(?is)\b(?:INNER|LEFT(?:\s+OUTER)?|RIGHT(?:\s+OUTER)?|FULL(?:\s+OUTER)?|CROSS)\s+JOIN\b", text)
    if not first_join_match: return text.strip('()[]" ')
    base_part = text[:first_join_match.start()].strip('()[]" ')
    return base_part

def parse_joins(clause: str) -> list[dict[str, str]]:
    if not clause or clause == "なし": return []
    parts = split_toplevel_commas(clause)
    if not parts: return []
    
    first_part = parts[0]
    # Capture join type, table (possibly quoted/bracketed) + optional alias, and ON condition
    pat = re.compile(r'(?is)\b((?:INNER|LEFT|RIGHT|FULL|CROSS)(?:\s+OUTER)?\s+JOIN)\s+((?:\[[^\]]+\]|"[^"]+"|[^\s]+)(?:\s+(?:AS\s+)?(?:[A-Za-z0-9_＿０-９Ａ-Ｚａ-ｚ一-龯ぁ-ゔァ-ヶー\u2160-\u217b]+))?)\s+ON\s+(.*?)((?=\s+(?:INNER|LEFT|RIGHT|FULL|CROSS)\s+JOIN)|\)|$)')
    joins = [{"type": " ".join(t.upper().split()), "table": tbl.strip('[]" '), "on": " ".join(o.strip().split())} for t, tbl, o, _ in pat.findall(first_part)]
    
    for p in parts[1:]:
        joins.append({"type": ",", "table": p.strip(), "on": ""})
        
    return joins

def parse_update_clause(update_clause: str) -> tuple[str, list[dict[str, str]]]:
    if not update_clause: return "", []
    first_join_match = re.search(r"(?is)\b(?:INNER|LEFT(?:\s+OUTER)?|RIGHT(?:\s+OUTER)?|FULL(?:\s+OUTER)?|CROSS)\s+JOIN\b", update_clause)
    if not first_join_match: return update_clause.strip('()[] '), []
    target_part = update_clause[:first_join_match.start()].strip('()[] ')
    target_table = target_part.split()[-1] if target_part else ""
    return target_table, parse_joins(update_clause)

def parse_select_columns(select_clause: str, default_table: str = "", param_list: list = [], table_resolver: Optional[TableResolver] = None, alias_map: dict = None) -> list[dict[str, str]]:
    if not select_clause or select_clause == "なし": return []
    select_clause = re.sub(r'(?i)\s+INTO\s+.*$', '', select_clause)
    parts, curr, p_cnt, in_q = [], "", 0, False
    for char in select_clause:
        if char in ('"', "'"): in_q = not in_q; curr += char
        elif char == '(' and not in_q: p_cnt += 1; curr += char
        elif char == ')' and not in_q: p_cnt -= 1; curr += char
        elif char == ',' and not in_q and p_cnt == 0: parts.append(curr.strip()); curr = ""
        else: curr += char
    if curr.strip(): parts.append(curr.strip())
    cols = []
    for i, p in enumerate(parts, 1):
        m = re.search(r'(?i)\s+AS\s+([^ ]+)$', p)
        alias = m.group(1).strip('[]') if m else ""
        expr = p[:m.start()].strip() if m else p
        tbl, fld, _ = extract_source_info(expr, default_table, param_list, table_resolver, alias_map)
        cols.append({"no": str(i), "table_name": tbl, "column_name": fld, "alias": alias, "notes": format_notes(expr)})
    return cols

def format_sql_clause(s: str) -> str:
    if not s or s == "なし": return s
    result = []
    paren_level = 0
    for char in s:
        if char == '(': paren_level += 1
        elif char == ')': paren_level -= 1
        elif char == ',' and paren_level == 0: result.append('\n')
        result.append(char)
    return "".join(result).strip()

def format_raw_query(sql: str) -> str:
    for kw in ["SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "UNION ALL"]:
        sql = re.sub(rf'(?i)\b{kw}\b', f'\n{kw}\n', sql)
    lines = sql.split('\n')
    new_lines = []
    format_next = False
    for line in lines:
        line = line.strip()
        if not line: continue
        up_line = line.upper()
        if up_line in ["SELECT", "GROUP BY", "ORDER BY", "WHERE", "HAVING"]:
            new_lines.append(line)
            format_next = True
            continue
        if format_next and not any(up_line.startswith(kw) for kw in ["FROM", "UNION ALL", "WITH"]):
            new_lines.append(format_sql_clause(line))
            format_next = False
        else:
            new_lines.append(line)
            format_next = False
    return "\n".join(new_lines).strip()

def reconstruct_select(sql_obj: dict) -> str:
    if not sql_obj: return ""
    raw_sql = sql_obj.get("raw_sql")
    if isinstance(raw_sql, str) and "SELECT" in raw_sql.upper() and "INTO" not in raw_sql.upper():
        return raw_sql
    sel = sql_obj.get("select", "*")
    frm = sql_obj.get("from", "")
    sel = re.sub(r'(?i)\s+INTO\s+.*$', '', sel)
    parts = [f"SELECT {sel}"]
    if frm and frm != "なし": parts.append(f"FROM {frm}")
    joins = parse_joins(frm if frm != "なし" else "")
    if not joins and "join" in sql_obj: joins = sql_obj["join"]
    for j in joins:
        if isinstance(j, dict):
            j_type = j.get('type', 'INNER JOIN')
            j_table = j.get('table')
            j_on = j.get('on')
            if j_type == ",":
                parts.append(f", {j_table}")
            elif j_on:
                parts.append(f"{j_type} {j_table} ON {j_on}")
            else:
                parts.append(f"{j_type} {j_table}")
    if sql_obj.get("where") and sql_obj.get("where") != "なし":
        if isinstance(sql_obj["where"], list):
            parts.append(f"WHERE {' AND '.join([c['condition'] for c in sql_obj['where']])}")
        else: parts.append(f"WHERE {sql_obj['where']}")
    if sql_obj.get("group_by") and sql_obj.get("group_by") != "なし": parts.append(f"GROUP BY {sql_obj['group_by']}")
    if sql_obj.get("order_by") and sql_obj.get("order_by") != "なし": parts.append(f"ORDER BY {sql_obj['order_by']}")
    return " ".join(parts)

def get_used_tables(sql_obj: dict) -> list[str]:
    # Extract all possible table names from the entire SQL object
    tables = set()
    
    def _extract_from_text(text: str):
        if not text or text == "なし": return
        # Find everything between FROM and a following keyword or end of string/paren
        # We use a non-greedy match for the content after FROM
        for m in re.finditer(r'(?i)\bFROM\b\s+(.+?)(?=\s+\bWHERE\b|\s+\bGROUP BY\b|\s+\bORDER BY\b|\s+\bHAVING\b|\s+\bUNION\b|\)|$)', text):
            part = m.group(1)
            tables.update(get_table_names_from_from(part).split("\n"))
        
        # Also catch JOINs (simple case)
        for m in re.finditer(r'(?i)\bJOIN\b\s+([^\s()]+)', text):
            tables.add(m.group(1).strip('[]" '))

    # 1. Main clauses
    _extract_from_text(str(sql_obj.get("select", "")))
    
    # The 'from' field already contains the tables, so we use get_table_names_from_from directly
    frm = sql_obj.get("from", "")
    if frm and frm != "なし":
        tables.update(get_table_names_from_from(str(frm)).split("\n"))
    
    # 2. WHERE (subqueries)
    where = sql_obj.get("where", "")
    if isinstance(where, list):
        for w in where:
            if isinstance(w, dict): _extract_from_text(w.get("condition", ""))
            else: _extract_from_text(str(w))
    else:
        _extract_from_text(str(where))
        
    # 3. JOINs (if explicitly structured)
    if "join" in sql_obj:
        for j in sql_obj["join"]:
            if isinstance(j, dict):
                tbl = j.get("table", "")
                if tbl: tables.update(get_table_names_from_from(tbl).split("\n"))
                
    # 4. Fallback for raw SQL
    if "raw_sql" in sql_obj:
        _extract_from_text(sql_obj["raw_sql"])

    return list(set([t.strip() for t in tables if t.strip()]))

def _load_table_config(template_path: Path) -> dict:
    config_path = template_path.parent.parent / "table_config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def _get_table_type(tbl_name: str, table_config: dict) -> str:
    if not tbl_name: return "normal"
    mappings = table_config.get("table_mappings", {})
    if tbl_name in mappings: return mappings[tbl_name]
    return "normal"

def _get_target_table(sql_obj: dict) -> str:
    if sql_obj.get("update"): return parse_update_clause(sql_obj["update"])[0]
    if sql_obj.get("insert_into"): return sql_obj["insert_into"].split('(')[0].strip()
    if sql_obj.get("into"): return sql_obj["into"]
    if sql_obj.get("select") and isinstance(sql_obj["select"], str) and " INTO " in sql_obj["select"].upper():
        m = re.search(r'(?i)\s+INTO\s+(\[[^\]]+\]|[^\s,]+)', sql_obj["select"])
        if m: return m.group(1).strip('[]')
    return ""

def _parse_sql(sql_str: Any) -> dict:
    if isinstance(sql_str, dict): return sql_str
    try:
        val = json.loads(sql_str)
        if isinstance(val, dict):
            return val
        return {"raw_sql": str(val)}
    except:
        return {"raw_sql": str(sql_str)}

def _collect_export_groups(all_queries: list, table_config: dict) -> dict:
    export_groups = {}
    for q_data in all_queries:
        module_id = q_data.get("module_id", "Unknown")
        sql_obj = _parse_sql(q_data.get("sql", "{}"))
        target_table = _get_target_table(sql_obj)
        if _get_table_type(target_table, table_config) == "export":
            key = (module_id, target_table)
            if key not in export_groups:
                export_groups[key] = {"queries": [], "pattern": "", "query_name": q_data.get("query_name", f"{target_table}_Definition")}
            export_groups[key]["queries"].append({
                "sql": reconstruct_select(sql_obj),
                "query_name": q_data.get("query_name", f"{target_table}_Part"),
                "select_clause": str(sql_obj.get("select", "") or ""),
                "from_clause": str(sql_obj.get("from", "") or ""),
                "where_clause": sql_obj.get("where", "なし") or "なし",
                "group_by_clause": sql_obj.get("group_by", "なし") or "なし",
                "order_by_clause": sql_obj.get("order_by", "なし") or "なし",
                "param_list": get_params_info(sql_obj, q_data)[1]
            })
    return export_groups
    
def _get_full_alias_map(sql_obj: dict, joins: list = None) -> dict[str, str]:
    from_clause = sql_obj.get("from", "")
    if not from_clause and sql_obj.get("update"):
        from_clause = sql_obj.get("update")
    a_map = parse_aliases(from_clause)
    join_list = joins if joins is not None else sql_obj.get("join", [])
    for j in join_list:
        if isinstance(j, dict) and j.get("table"):
            # Ensure parse_aliases sees it as a table definition with an alias
            # We add a comma if it doesn't have one to separate from previous tokens
            a_map.update(parse_aliases(j["table"]))
    return a_map

def _fill_query_sheets(
    logic_items: list[dict[str, Any]],
    skeleton: dict[str, Any],
    table_resolver: TableResolver,
    table_config: dict,
    repo: Any = None,
    dd_code_json_path: Path | None = None,
) -> dict[str, Any]:
    from db.query_dd import get_dd_code_json_query_raw
    sel_queries, upd_queries = [], []
    
    # Pre-calculate screen_id
    screen_id = skeleton.get("screen_id", "")
    
    # Group queries by module_id
    module_groups: dict[str, list[dict]] = {}
    for item in logic_items:
        mid = item.get("module_id", "UnknownModule")
        if mid not in module_groups: module_groups[mid] = []
        for q in item.get("queries", []):
            q_copy = dict(q)
            q_copy["module_id"] = mid
            module_groups[mid].append(q_copy)

    # Ensure all queries in skeleton's related_queries or dd_code_json_path are mapped
    from utils.vba_utils import normalize_query_name
    processed_queries = set()
    for qs in module_groups.values():
        for q in qs:
            qname = q.get("query_name") or q.get("name")
            if qname:
                processed_queries.add(normalize_query_name(qname))

    # Read related queries from the D1 skeleton file if path is provided
    related_queries = []
    if dd_code_json_path and dd_code_json_path.exists():
        try:
            with open(dd_code_json_path, encoding="utf-8") as f:
                d1_data = json.load(f)
                related_queries = d1_data.get("related_queries", [])
        except Exception:
            pass
    if not related_queries:
        related_queries = skeleton.get("related_queries", [])

    # Find orphan queries (present in skeleton but not in any mapped module)
    orphan_queries = []
    for rq in related_queries:
        rqname = rq.get("query_name") or rq.get("name")
        if rqname and normalize_query_name(rqname) not in processed_queries:
            orphan_queries.append(rq)

    if orphan_queries:
        import logging
        local_logger = logging.getLogger(__name__)
        local_logger.info("[DD Query Mapper] Found %d orphan queries from skeleton, mapping to fallback module.", len(orphan_queries))
        # Find a suitable fallback module (e.g., F000, F002, or the first module)
        fallback_mid = "F000"
        if fallback_mid not in module_groups:
            if module_groups:
                fallback_mid = list(module_groups.keys())[0]
            else:
                fallback_mid = "F000"
                module_groups[fallback_mid] = []
        
        for oq in orphan_queries:
            q_copy = dict(oq)
            q_copy["query_name"] = oq.get("query_name") or oq.get("name")
            q_copy["module_id"] = fallback_mid
            module_groups[fallback_mid].append(q_copy)

    export_groups = _collect_export_groups([q for qs in module_groups.values() for q in qs], table_config)
    emitted_exports = set()
    query_blocks_per_module = {}
    query_mappings_per_module = {} # Store structured mapping data

    # Process each module
    for module_id, initial_queries in module_groups.items():
        sel_idx, upd_idx = 1, 1
        query_queue = list(initial_queries)
        processed_query_names = set() # To avoid redundant fetching of the same query within a module
        for q in query_queue:
            if q.get("query_name"): processed_query_names.add(q["query_name"])
            
        # Map: query_name -> sheet_name_pattern (for replacement)
        query_to_sheet_map = {}
        module_query_blocks = []

        q_idx = 0
        while q_idx < len(query_queue):
            q_data = query_queue[q_idx]
            q_idx += 1
            
            q_name_str = q_data.get("query_name") or q_data.get("name") or "UnknownQuery"
            sql_data = q_data.get("sql") or q_data.get("sql_logic") or q_data.get("query") or {"raw_sql": q_data.get("raw_sql", "")}
            # Always try to fetch description if missing in q_data
            if not q_data.get("description") and q_name_str != "UnknownQuery" and repo:
                try:
                    from db.query_dd import get_dd_code_json_query_raw
                    q_doc = get_dd_code_json_query_raw(repo, q_name_str)
                    if q_doc:
                        if not q_data.get("description"):
                            q_data["description"] = q_doc.get("description") or q_doc.get("query_purpose", "")
                        # Also fill SQL if missing
                        if not sql_data or (isinstance(sql_data, dict) and not sql_data.get("raw_sql") and not sql_data.get("select")):
                            sql_data = q_doc.get("query") or q_doc.get("sql_logic") or {"raw_sql": q_doc.get("raw_sql")}
                except: pass

            sql_obj = _parse_sql(sql_data)
            
            # Enrich sparse query object based on raw_sql if needed
            raw_sql_str = str(sql_obj.get("raw_sql") or q_data.get("raw_sql") or "").strip()
            if not any(k in sql_obj for k in ["select", "update", "insert_into", "delete", "into"]):
                if re.match(r'(?i)^\s*DELETE\b', raw_sql_str):
                    from_val = sql_obj.get("from", "")
                    if not from_val:
                        m_from = re.search(r'(?i)\bFROM\b\s+(.*?)(\bWHERE\b|$)', raw_sql_str)
                        if m_from: from_val = m_from.group(1).strip()
                    sql_obj["delete"] = from_val
                    if "from" not in sql_obj: sql_obj["from"] = from_val
                elif re.match(r'(?i)^\s*UPDATE\b', raw_sql_str):
                    upd_val = sql_obj.get("update", "")
                    if not upd_val:
                        m_upd = re.search(r'(?i)\bUPDATE\b\s+(.*?)(\bSET\b|$)', raw_sql_str)
                        if m_upd: upd_val = m_upd.group(1).strip()
                    sql_obj["update"] = upd_val
                    if "from" not in sql_obj: sql_obj["from"] = upd_val
                elif re.match(r'(?i)^\s*INSERT\b', raw_sql_str):
                    ins_val = sql_obj.get("insert_into", "")
                    if not ins_val:
                        m_ins = re.search(r'(?i)\bINSERT\s+INTO\b\s+(.*?)(\bVALUES\b|\bSELECT\b|$)', raw_sql_str)
                        if m_ins: ins_val = m_ins.group(1).strip()
                    sql_obj["insert_into"] = ins_val
            
            target_table = _get_target_table(sql_obj)
            tbl_type = _get_table_type(target_table, table_config)

            query_purpose = q_data.get("description") or q_data.get("query_purpose") or ""

            if tbl_type == "export":
                ekey = (module_id, target_table)
                if ekey not in emitted_exports:
                    for sub_q in export_groups[ekey]["queries"]:
                        pattern = f"{module_id}_SelQuery{sel_idx:02d}"
                        sub_joins = parse_joins(sub_q["from_clause"])
                        sel_queries.append({
                            "sheet_name_pattern": pattern,
                            "query_purpose": f"Partial export for {target_table}",
                            "query_name": sub_q["query_name"],
                            "parameters": "",
                            "sql": {
                                "select": format_sql_clause(re.sub(r'(?i)\s+INTO\s+.*$', '', sub_q["select_clause"])) if sub_q["select_clause"] else "",
                                "from": get_base_table_from_from(sub_q["from_clause"]) if sub_joins else (sub_q["from_clause"] or ""),
                                "join": sub_joins,
                                "where": get_where_conditions(sub_q["where_clause"], sub_q["param_list"]),
                                "group_by": format_sql_clause(sub_q["group_by_clause"] or ""),
                                "order_by": format_sql_clause(sub_q["order_by_clause"] or "")
                            },
                            "columns": parse_select_columns(sub_q["select_clause"], get_table_names_from_from(sub_q["from_clause"]), sub_q["param_list"], table_resolver),
                            "raw_sql": ""
                        })
                        sel_idx += 1
                    
                    pattern = f"{module_id}_SelQuery{sel_idx:02d}"
                    export_groups[ekey]["pattern"] = pattern
                    
                    # Store for S3 event_content block
                    _, _, param_display_lines = get_params_info(sql_obj, q_data, screen_id)
                    
                    # Add to query_mappings (no markdown table generation for event_content)
                    if module_id:
                        if module_id not in query_mappings_per_module: query_mappings_per_module[module_id] = []
                        query_mappings_per_module[module_id].append({
                            "sheet_name": pattern,
                            "logic_query_name": f"{target_table}_Combined_Export",
                            "type": "SELECT",
                            "parameters": [{"name": l.split(":")[0].strip() if ":" in l else l.strip(), "io": "I", "mapping": l.split(":")[1].strip() if ":" in l else "-"} for l in param_display_lines],
                            "outputs": [{"name": out, "io": "O", "mapping": "オブジェクト"} for out in [f"{target_table}_Data"]]
                        })

                    sel_queries.append({
                        "sheet_name_pattern": pattern,
                        "query_purpose": f"Export definition for {target_table}",
                        "query_name": f"{target_table}_Combined_Export",
                        "parameters": "", # Keep simple/empty for exports
                        "sql": {},
                        "columns": [],
                        "raw_sql": "\nUNION ALL\n".join([f"{module_id}_SelQuery{idx:02d}" for idx in range(sel_idx - len(export_groups[ekey]["queries"]), sel_idx)])
                    })
                    sel_idx += 1
                    emitted_exports.add(ekey)
                continue

            # Identify sub-queries in all clauses (FROM, JOIN, WHERE, etc.)
            used_names = get_used_tables(sql_obj)
            
            # Sub-queries found in this query
            found_subqueries = []
            if repo:
                for name in used_names:
                    # Check for mapped query
                    mapped_q = _get_mapped_query(name, table_config)
                    fetch_name = mapped_q if mapped_q else name
                    
                    # If it's not a known table, OR it's a mapped query, check if it's a query
                    if mapped_q or not table_resolver.get_table_fields(name):
                        try:
                            q_doc = get_dd_code_json_query_raw(repo, fetch_name)
                            if q_doc:
                                found_subqueries.append(fetch_name)
                                if fetch_name not in processed_query_names:
                                    # Add to queue to be processed later
                                    new_q = {
                                        "query_name": fetch_name,
                                        "sql": q_doc.get("query") or q_doc.get("sql_logic") or {"raw_sql": q_doc.get("raw_sql")},
                                        "parameters": q_doc.get("parameters", []),
                                        "module_id": module_id,
                                        "description": q_doc.get("description") or q_doc.get("query_purpose", "")
                                    }
                                    query_queue.append(new_q)
                                    processed_query_names.add(fetch_name)
                        except:
                            pass
            
            detailed_str, param_list, param_display_lines = get_params_info(sql_obj, q_data, screen_id)
            is_select = not ("update" in sql_obj or "insert_into" in sql_obj or "delete" in sql_obj)

            # Extract output columns for SELECT queries to show in table
            output_cols = []
            if is_select:
                try:
                    # Resolve table names for column extraction
                    joins = parse_joins(sql_obj.get("from", ""))
                    a_map = _get_full_alias_map(sql_obj, joins)
                    default_src = get_table_names_from_from(sql_obj.get("from", ""))
                    cols = parse_select_columns(sql_obj.get("select", ""), default_src, param_list, table_resolver, a_map)
                    output_cols = [c.get("alias") or c.get("column_name") for c in cols if c.get("alias") or c.get("column_name")]
                except: pass

            # Original simple parameters
            parameters_simple = ", ".join([str(p.get("key", "")) for p in param_list if p.get("key")])

            sheet_pattern = ""
            if is_select:
                sheet_pattern = f"{module_id}_SelQuery{sel_idx:02d}"
                sel_idx += 1
            else:
                sheet_type = "Upd"
                if sql_obj.get("insert_into"): sheet_type = "Ins"
                elif sql_obj.get("into") or (sql_obj.get("select") and isinstance(sql_obj["select"], str) and " INTO " in sql_obj["select"].upper()): sheet_type = "Make"
                elif sql_obj.get("delete"): sheet_type = "Del"
                sheet_pattern = f"{module_id}_{sheet_type}Query{upd_idx:02d}"
                upd_idx += 1
            
            query_to_sheet_map[q_name_str] = sheet_pattern

            if q_name_str != "UnknownQuery" and tbl_type != "export":
                # Add to query_mappings (no markdown table generation for event_content)
                if module_id not in query_mappings_per_module: query_mappings_per_module[module_id] = []
                query_mappings_per_module[module_id].append({
                    "sheet_name": sheet_pattern,
                    "logic_query_name": q_name_str,
                    "type": "SELECT" if is_select else "更新/追加/削除",
                    "parameters": [{"name": l.split(":")[0].strip() if ":" in l else l.strip(), "io": "I", "mapping": l.split(":")[1].strip() if ":" in l else "-"} for l in param_display_lines]
                })

            if is_select:
                joins = parse_joins(sql_obj.get("from", ""))
                used_tables = get_used_tables(sql_obj)
                ctes = [f"WITH {utbl} AS (\n {export_groups[(module_id, utbl)]['pattern']} \n)" for utbl in used_tables if (module_id, utbl) in export_groups and export_groups[(module_id, utbl)]["pattern"]]
                
                sel_queries.append({
                    "sheet_name_pattern": sheet_pattern,
                    "query_purpose": query_purpose,
                    "query_name": q_name_str,
                    "parameters": parameters_simple,
                    "sql": {
                        "select": format_sql_clause(re.sub(r'(?i)\s+INTO\s+.*$', '', sql_obj.get("select", ""))),
                        "from": get_base_table_from_from(sql_obj.get("from", "")) if joins else sql_obj.get("from", ""),
                        "join": joins,
                        "where": get_where_conditions(sql_obj.get("where", "なし"), param_list),
                        "group_by": format_sql_clause(sql_obj.get("group_by", "なし")),
                        "order_by": format_sql_clause(sql_obj.get("order_by", "なし"))
                    } if not ctes else {},
                    "columns": parse_select_columns(
                        sql_obj.get("select", ""), 
                        "\n".join(list(dict.fromkeys(
                            get_table_names_from_from(sql_obj.get("from", "")).split("\n") + 
                            [jt for j in joins if isinstance(j, dict) for jt in get_table_names_from_from(j.get("table", "")).split("\n")]
                        ))), 
                        param_list, 
                        table_resolver, 
                        _get_full_alias_map(sql_obj, joins)
                    ) if not ctes else [],
                    "raw_sql": ("\n".join(ctes) + "\n" if ctes else "") + (format_raw_query(reconstruct_select(sql_obj)) if (ctes or "raw_sql" in sql_obj) else "")
                })
            else:
                sheet_name, set_columns = "Upd", []
                joins = parse_joins(sql_obj.get("from", ""))
                a_map = _get_full_alias_map(sql_obj, joins)
                if sql_obj.get("update"):
                    target_table, joins = parse_update_clause(sql_obj["update"])
                    default_src_table = get_table_names_from_from(sql_obj["update"])
                    set_items = sql_obj.get("set", [])
                    if isinstance(set_items, str):
                        set_items = split_toplevel_commas(set_items)
                    for q_set in set_items:
                        parts = q_set.split("=", 1)
                        if len(parts) == 0: continue
                        expr = parts[0].strip().split(".")[-1]
                        val_expr = parts[1].strip() if len(parts) > 1 else ""
                        src_tbl, src_fld, _ = extract_source_info(replace_query_parameters(val_expr, param_list), default_src_table, param_list, table_resolver, a_map)
                        set_columns.append({"no": len(set_columns)+1, "column": expr, "source_table": src_tbl, "source_field_or_fixed_value": src_fld, "notes": format_notes(val_expr)})
                elif sql_obj.get("insert_into"):
                    sheet_name, target_table = "Ins", _get_target_table(sql_obj)
                    for val_item in normalize_parameters(sql_obj.get("values", "")):
                        src_tbl, src_fld, _ = extract_source_info(val_item["value"], get_table_names_from_from(sql_obj.get("from", "")), param_list, table_resolver, a_map)
                        set_columns.append({"no": len(set_columns)+1, "column": val_item["key"], "source_table": src_tbl, "source_field_or_fixed_value": src_fld, "notes": format_notes(val_item["value"])})
                elif sql_obj.get("into") or (sql_obj.get("select") and isinstance(sql_obj["select"], str) and " INTO " in sql_obj["select"].upper()):
                    sheet_name, target_table = "Make", _get_target_table(sql_obj)
                    sel_str = sql_obj.get("select", "")
                    sel_str_clean = re.sub(r'(?i)\s+INTO\s+.*$', '', sel_str).strip()
                    sql_obj["select"] = sel_str_clean
                    default_src_table = "\n".join(list(dict.fromkeys(
                        get_table_names_from_from(sql_obj.get("from", "")).split("\n") + 
                        [jt for j in joins if isinstance(j, dict) for jt in get_table_names_from_from(j.get("table", "")).split("\n")]
                    )))
                    for sc in parse_select_columns(sel_str_clean, default_src_table, param_list, table_resolver, a_map):
                        set_columns.append({"no": sc["no"], "column": sc["alias"] or sc["column_name"], "source_table": sc["table_name"], "source_field_or_fixed_value": sc["column_name"], "notes": sc["notes"]})
                else:
                    sheet_name = "Del"
                    delete_clause = sql_obj.get("delete", "").strip()
                    if delete_clause.upper().startswith("FROM"):
                        delete_clause = delete_clause[4:].strip()
                    if " FROM " in f" {delete_clause.upper()} ":
                        parts = re.split(r'(?i)\s+FROM\s+', delete_clause)
                        target_table = parts[-1].strip() if len(parts) > 1 else delete_clause
                    else:
                        target_table = delete_clause
                    if target_table:
                        target_table = target_table.split()[0].strip()
                
                joins = parse_joins(sql_obj.get("from", "")) if not (sql_obj.get("update") and joins) else joins
                if _get_table_type(target_table, table_config) == "export": continue

                upd_queries.append({
                    "sheet_name_pattern": sheet_pattern,
                    "query_purpose": query_purpose,
                    "query_name": q_name_str,
                    "parameters": parameters_simple,
                    "sql": {
                        "target_table": target_table, "set_columns": set_columns, "select": format_sql_clause(sql_obj.get("select", "")) if sql_obj.get("from", "") != "なし" else "",
                        "from": get_base_table_from_from(sql_obj.get("from", "")) if joins else (sql_obj.get("from", "") if sql_obj.get("from", "") != "なし" else target_table),
                        "join": joins, "where": get_where_conditions(sql_obj.get("where", ""), param_list), "group_by": format_sql_clause(sql_obj.get("group_by", "")), "is_temporary_table": _get_table_type(target_table, table_config) == "temporary"
                    },
                    "raw_sql": ""
                })

        query_blocks_per_module[module_id] = module_query_blocks
        query_mappings_per_module[module_id] = query_mappings_per_module.get(module_id, [])

        # Post-process: Replace sub-query names and mapped tables with sheet names/query names
        replacements = {}
        # 1. Table-to-Query mappings from config
        for tbl, target in table_config.get("table_mappings", {}).items():
            if target and target not in ("main", "master", "export", "temporary"):
                replacements[tbl] = target

        if replacements:
            sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
            def _apply_repls(text: str) -> str:
                if not text: return text
                res = text
                for k in sorted_keys:
                    v = replacements[k]
                    if not v: continue
                    res = re.sub(rf'\[{re.escape(k)}\]', f'[{v}]', res)
                    res = re.sub(rf'\b{re.escape(k)}\b', v, res)
                return res

            for q_sheet in (sel_queries + upd_queries):
                # Only process sheets belonging to this module
                if not q_sheet["sheet_name_pattern"].startswith(module_id): continue
                
                if "sql" in q_sheet and q_sheet["sql"]:
                    s = q_sheet["sql"]
                    for fld in ["select", "from", "target_table", "delete", "group_by", "order_by"]:
                        if fld in s and isinstance(s[fld], str): s[fld] = _apply_repls(s[fld])
                    if "join" in s and isinstance(s["join"], list):
                        for j in s["join"]:
                            if isinstance(j, dict):
                                if "table" in j: j["table"] = _apply_repls(j["table"])
                                if "on" in j: j["on"] = _apply_repls(j["on"])
                    if "where" in s and isinstance(s["where"], list):
                        for w in s["where"]:
                            if isinstance(w, dict) and "condition" in w: w["condition"] = _apply_repls(w["condition"])
                    if "set_columns" in s and isinstance(s["set_columns"], list):
                        for sc in s["set_columns"]:
                            if "source_table" in sc: sc["source_table"] = _apply_repls(sc["source_table"])
                
                if "columns" in q_sheet:
                    for col in q_sheet["columns"]:
                        if "table_name" in col: col["table_name"] = _apply_repls(col["table_name"])
                
                if q_sheet.get("raw_sql"):
                    q_sheet["raw_sql"] = _apply_repls(q_sheet["raw_sql"])

    s3_details = []
    if "sheet_3_detail_specs" in skeleton:
        s3 = skeleton["sheet_3_detail_specs"]
        s3_details = s3 if isinstance(s3, list) else s3.get("details", [])
    elif "sheet_2_detail" in skeleton:
        s2 = skeleton["sheet_2_detail"]
        s3_details = s2 if isinstance(s2, list) else s2.get("details", [])

    for detail in s3_details:
        mid = detail.get("module_id") or detail.get("key_id") or detail.get("report_scope_name")
        # Inject structured mappings only (no markdown table blocks in event_content)
        if mid and mid in query_mappings_per_module:
            detail["query_mappings"] = query_mappings_per_module[mid]

    if "sheet_4_sel_query_templates" in skeleton:
        skeleton["sheet_4_sel_query_templates"] = sel_queries
        if not sel_queries: skeleton.pop("sheet_4_sel_query_templates", None)
    elif "sheet_3_sel_query_templates" in skeleton:
        skeleton["sheet_4_sel_query_templates"] = sel_queries
        skeleton.pop("sheet_3_sel_query_templates", None)
        if not sel_queries: skeleton.pop("sheet_4_sel_query_templates", None)

    if "sheet_5_upd_query_templates" in skeleton:
        skeleton["sheet_5_upd_query_templates"] = upd_queries
        if not upd_queries: skeleton.pop("sheet_5_upd_query_templates", None)
    elif "sheet_4_upd_query_templates" in skeleton:
        skeleton["sheet_5_upd_query_templates"] = upd_queries
        skeleton.pop("sheet_4_upd_query_templates", None)
        if not upd_queries: skeleton.pop("sheet_5_upd_query_templates", None)

    return skeleton
