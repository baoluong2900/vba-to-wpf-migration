#!/usr/bin/env python3
"""
tool_repo.py — Convert DD JSON specs → C# Entity + IRepository + Repository (Dapper)

Usage:
    python tool_repo.py              # process all files in inputs/
    python tool_repo.py --file xxx   # process a single file
"""

import json
import re
import sys
from pathlib import Path

BASE_DIR   = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config" / "name_config.json"
INPUTS_DIR  = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"

# ── Type mappings ────────────────────────────────────────────────────────────
ORACLE_TO_CS = {
    "VARCHAR2": "string", "NVARCHAR2": "string", "CHAR": "string",
    "NCHAR": "string", "CLOB": "string", "NCLOB": "string",
    "NUMBER": "decimal", "INTEGER": "int", "INT": "int",
    "FLOAT": "double", "BINARY_FLOAT": "float", "BINARY_DOUBLE": "double",
    "DATE": "DateTime?", "TIMESTAMP": "DateTime?",
    "BLOB": "byte[]", "RAW": "byte[]",
}

VBA_TO_CS = {
    "string": "string", "str": "string",
    "int": "int", "integer": "int", "long": "long",
    "bool": "bool", "boolean": "bool",
    "double": "double", "single": "float",
    "date": "DateTime?", "object": "object",
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


# ── Name helpers ─────────────────────────────────────────────────────────────
def sanitize_identifier(name: str) -> str:
    """Convert table name → valid C# class-name identifier (PascalCase, no spaces/quotes)."""
    name = name.replace('\\"', "").replace('"', "").strip()
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
    # remove chars that are not word-chars (keeps Unicode / Japanese)
    result = re.sub(r"[^\w]", "", result)
    if result and result[0].isdigit():
        result = "T" + result
    return result or "Unknown"


def extract_primary_table(from_clause: str) -> str:
    """Extract bare table name from FROM clause (strip alias + quotes)."""
    from_clause = from_clause.replace('\\"', '"').strip()
    if from_clause.startswith('"'):
        end_idx = from_clause.find('"', 1)
        if end_idx != -1:
            return from_clause[1:end_idx].strip()
    
    clean = from_clause.replace('"', '').strip()
    parts = clean.split()
    return parts[0].strip() if parts else clean


def find_table_key(table_name: str, config: dict) -> str:
    """
    Map a table name → table_name config key.
    """
    table_map = config.get("table_name", {})
    if table_name in table_map:
        return table_map[table_name]
    for key, value in table_map.items():
        if key in table_name or table_name in key:
            return value
    # Not found → return as-is
    return table_name


def get_english_name(jp_name: str, config: dict) -> str:
    """
    Look up English name for a Japanese field name.
    Adds 'TODO' entry to config if missing.
    """
    field_map = config.setdefault("field_name", {})
    jp_clean = jp_name.split("\n")[0].strip()
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
    jp_clean = jp_name.strip()
    if jp_clean in param_map:
        return param_map[jp_clean]
    # Fallback: register with TODO and return jp_clean
    param_map[jp_clean] = "TODO_" + jp_clean
    return "TODO_" + jp_clean


def get_csharp_prop_name(jp_raw: str, config: dict) -> str:
    """Get the final C# property name for a raw Japanese field name."""
    jp = jp_raw.split('.')[-1].replace('"', '').strip() if jp_raw else ""
    en = get_english_name(jp, config)
    if en and en != "TODO":
        return en[0].upper() + en[1:]
    return f"TODO_{jp}"


def oracle_to_cs_type(oracle_type: str) -> str:
    for k, v in ORACLE_TO_CS.items():
        if oracle_type.upper().startswith(k):
            return v
    return "object"


def vba_to_cs_type(vba_type: str) -> str:
    return VBA_TO_CS.get(vba_type.lower().strip(), "string")


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
            cs_name = get_param_english_name(jp_key, config)
        else:
            cs_name = jp_key
        result.append({"vba": name, "jp_key": jp_key, "cs_name": cs_name, "cs_type": cs_type})
    return result




# ── SQL builder ───────────────────────────────────────────────────────────────
def build_sql(sql_block: dict, default_table: str = "") -> str:
    """Reconstruct full Oracle SQL string from the structured sql block."""
    target_table = (sql_block.get("target_table") or "").replace('\\"', '"').strip()
    
    # Safely handle select which can be string or list of dicts
    sel_raw = sql_block.get("select")
    if isinstance(sel_raw, list):
        exprs = []
        for item in sel_raw:
            if isinstance(item, dict):
                expr = item.get("expression") or item.get("column") or ""
                if expr:
                    exprs.append(expr)
            elif isinstance(item, str):
                exprs.append(item)
        sel = "\n, ".join(exprs) if exprs else ""
    else:
        sel = (sel_raw or "").strip()

    from_    = (sql_block.get("from") or "").replace('\\"', '"').strip()
    if not from_ and default_table:
        from_ = default_table
    joins    = sql_block.get("join", []) or []
    wheres   = sql_block.get("where", []) or []
    group_by = sql_block.get("group_by", "") or ""
    order_by = sql_block.get("order_by", "") or ""

    lines = []
    if target_table:
        # Action Query: INSERT, UPDATE, or DELETE
        if sel:
            # INSERT INTO ... SELECT ...
            set_cols = sql_block.get("set_columns") or []
            target_cols = []
            for sc in set_cols:
                col_raw = sc.get("column") or ""
                if not col_raw:
                    continue
                # Handle AS casing
                if "AS" in col_raw:
                    col_clean = col_raw.split("AS")[-1].strip()
                elif "as" in col_raw:
                    col_clean = col_raw.split("as")[-1].strip()
                else:
                    col_clean = col_raw.strip()
                
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
                col = (sc.get("column") or "").split("AS")[0].strip()
                val = sc.get("source_field_or_fixed_value") or sc.get("value") or ""
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
        if not sel:
            sel = "*"
        lines.append(f"SELECT {sel}")
        if from_:
            lines.append(f"FROM {from_}")

    for j in joins:
        jtype  = j.get("type", "LEFT JOIN")
        jtable = j.get("table", "")
        jon    = j.get("on", "")
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
            if val and val != "TODO":
                return val + "Async" if not val.endswith("Async") else val
        else:
            func_map[q_name] = "TODO"
        return f"TODO_{base}"
    return base


# ── Return-type heuristics ────────────────────────────────────────────────────
def derive_return_type(type_name: str, query: dict) -> str:
    sheet = query.get("sheet_name_pattern", "")
    if "Upd" in sheet or "Del" in sheet or "Ins" in sheet:
        return "int"
    if "RecordSource" in sheet or "Sel" in sheet.lower():
        return f"IEnumerable<{type_name}>"
    return f"IEnumerable<{type_name}>"


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
        for col in q.get("columns", []):
            alias = col.get("alias", "").strip()
            col_name_raw = col.get("column_name", "")
            # Use alias if present, else first line of column_name
            effective = alias if alias else col_name_raw.split("\n")[0].strip()
            if not effective or effective in seen:
                continue
            seen.add(effective)
            fields.append({"name": effective, "type": "VARCHAR2", "raw_column_name": col_name_raw})
    return fields


def gen_input_dto(dto_name: str, args: list[dict], namespace_suffix: str = "") -> str:
    lines = []
    for a in args:
        typ = a['cs_type']
        name = a['cs_name']
        prop = name[0].upper() + name[1:] if name else "Unknown"
        default = ' = string.Empty;' if typ == "string" else ""
        jp_desc = a.get("vba") or ""
        comment = f" // {jp_desc}" if jp_desc else ""
        lines.append(f"    public {typ} {prop} {{ get; set; }}{default}{comment}")
    
    body = "\n".join(lines)
    suffix = f".{namespace_suffix}" if namespace_suffix else ""
    return (
        f"namespace vba_brain.Domain.DTOs{suffix};\n\n"
        f"public class {dto_name}\n"
        f"{{\n{body}\n}}\n"
    )

def gen_dto_class(class_name: str, fields: list[dict], config: dict, namespace_suffix: str = "") -> str:
    lines = []
    seen = set()
    for field in fields:
        jp_raw  = field.get("name", "")
        jp = jp_raw.split('.')[-1].replace('"', '').strip() if jp_raw else ""
        cs_type = field.get("csharp_type") or oracle_to_cs_type(field.get("type", "VARCHAR2"))
        prop = get_csharp_prop_name(jp_raw, config)
        if prop in seen:
            continue
        seen.add(prop)
        en = get_english_name(jp, config)
        raw_col = field.get("raw_column_name", "")
        jp_comment_raw = raw_col.split("\n")[0].split('.')[-1].replace('"', '').strip() if raw_col else jp
        
        if en and en != "TODO":
            comment = f"  // {jp_comment_raw}" if jp_comment_raw else ""
        else:
            comment = f"  // TODO: translate '{jp_comment_raw}'"
        default = ' = string.Empty;' if cs_type == "string" else ""

        if str(field.get("required")).lower() == "y":
            lines.append("    [Required]")

        max_len = field.get("length")
        if max_len:
            try:
                max_len_int = int(max_len)
                if max_len_int > 0:
                    lines.append(f"    [MaxLength({max_len_int})]")
            except (ValueError, TypeError):
                pass
                
        lines.append(f"    [Column(\"{jp}\")]")
        lines.append(f"    public {cs_type} {prop} {{ get; set; }}{default}{comment}")

    body = "\n".join(lines)
    suffix = f".{namespace_suffix}" if namespace_suffix else ""
    return (
        f"using System.ComponentModel.DataAnnotations;\n"
        f"using System.ComponentModel.DataAnnotations.Schema;\n\n"
        f"namespace vba_brain.Domain.DTOs{suffix};\n\n"
        f"public class {class_name}\n"
        f"{{\n{body}\n}}\n"
    )


# ── Code generators ───────────────────────────────────────────────────────────
def gen_csharp_class(class_name: str, fields: list[dict], config: dict, base_class: str = "BaseEntity", jp_table_name: str = "") -> str:
    lines = []
    for field in fields:
        jp_raw  = field.get("name", "")
        jp = jp_raw.split('.')[-1].replace('"', '').strip() if jp_raw else ""
        cs_type = field.get("csharp_type") or oracle_to_cs_type(field.get("type", "VARCHAR2"))
        prop = get_csharp_prop_name(jp_raw, config)
        en = get_english_name(jp, config)
        # Property name: English if translated, TODO_JapaneseName otherwise
        if en and en != "TODO":
            comment = f"  // {jp}" if en != jp else ""
        else:
            comment = f"  // TODO: translate '{jp}'"
        default = ' = string.Empty;' if cs_type == "string" else ""

        if str(field.get("required")).lower() == "y":
            lines.append("    [Required]")

        max_len = field.get("length")
        if max_len:
            try:
                max_len_int = int(max_len)
                if max_len_int > 0:
                    lines.append(f"    [MaxLength({max_len_int})]")
            except (ValueError, TypeError):
                pass

        lines.append(f"    [Column(\"{jp}\")]")
        lines.append(f"    public {cs_type} {prop} {{ get; set; }}{default}{comment}")

    body = "\n".join(lines)
    base_decl = f" : {base_class}" if base_class else ""
    jp_comment = f"/// <summary>\n/// {jp_table_name}\n/// </summary>\n" if jp_table_name else ""
    return (
        f"using System.ComponentModel.DataAnnotations;\n"
        f"using System.ComponentModel.DataAnnotations.Schema;\n\n"
        f"namespace vba_brain.Domain.Entities;\n\n"
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
        dto_usings.append("using vba_brain.Domain.DTOs;")
        if namespace_suffix:
            dto_usings.append(f"using vba_brain.Domain.DTOs.{namespace_suffix};")
            
    dto_usings_str = "\n".join(dto_usings) + "\n" if dto_usings else ""
    
    jp_comment = f"/// <summary>\n/// {jp_table_name}\n/// </summary>\n" if jp_table_name else ""
            
    return (
        f"using vba_brain.Domain.Entities;\n"
        f"{dto_usings_str}\n"
        f"namespace vba_brain.Domain.Interfaces;\n\n"
        f"{jp_comment}"
        f"public interface I{entity_name}Repository\n"
        f"{{\n{sigs_str}\n}}\n"
    )


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
        for raw_line in sql_frag.splitlines():
            line_escaped = raw_line.replace('"', '""')
            builder_lines.append(f'        sql.AppendLine(@"{line_escaped}");')
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
        cmt    = m.get("comment", "")

        # Extract inner return type
        inner_ret = ret
        if "IEnumerable<" in ret:
            inner_ret = ret.split("<")[1].split(">")[0]
        elif ret.endswith("?"):
            inner_ret = ret.rstrip("?")

        # Choose Dapper call
        is_action = m.get("is_action", False)
        if is_action:
            dapper_call = "ExecuteAsync"
        elif "IEnumerable" in ret:
            dapper_call = f"QueryAsync<{inner_ret}>"
        elif ret in ("int", "long", "decimal"):
            dapper_call = f"ExecuteScalarAsync<{ret}>"
        else:
            dapper_call = f"QueryFirstOrDefaultAsync<{inner_ret}>"

        # Build anonymous param object from explicit dapper mapping or fallback
        dapper_inner = m.get("dapper_params", "")
        if not dapper_inner:
            param_names = [p.split()[-1] for p in params.split(",") if p.strip()] if params else []
            dapper_inner = ", ".join(param_names)
        
        param_obj = f", new {{ {dapper_inner} }}" if dapper_inner else ""

        # Build concatenated SQL
        base_sql = m.get("base_sql", "")
        deps = m.get("deps", [])
        
        base_lines = base_sql.splitlines()
        
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

        cmt_line = f"{cmt}" if cmt else ""
        is_fallback_stub = m.get("is_fallback_stub", False)
        if is_fallback_stub:
            if "IEnumerable<" in ret:
                inner_t = ret.split("<")[1].split(">")[0]
                body_content = f"        return await Task.FromResult(Enumerable.Empty<{inner_t}>());"
            else:
                body_content = f"        return await Task.FromResult<{ret}>(default);"
            impls.append(
                f"{cmt_line}"
                f"    public async Task<{ret}> {name}({params})\n"
                f"    {{\n"
                f"{body_content}\n"
                f"    }}"
            )
        else:
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
        dto_usings.append("using vba_brain.Domain.DTOs;")
        if namespace_suffix:
            dto_usings.append(f"using vba_brain.Domain.DTOs.{namespace_suffix};")
            
    dto_usings_str = "\n".join(dto_usings) + "\n" if dto_usings else ""
    
    jp_comment = f"/// <summary>\n/// {jp_table_name}\n/// </summary>\n" if jp_table_name else ""

    return (
        f"using System.Text;\n"
        f"using vba_brain.Domain.Entities;\n"
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
def extract_valid_queries(dd_json: dict) -> list[dict]:
    dd_queries = []
    
    # 1. Load standard Select queries
    sheet4 = dd_json.get("sheet_4_sel_query_templates", [])
    if isinstance(sheet4, list):
        dd_queries.extend(sheet4)
        
    # 2. Load Action (Insert/Update/Delete) queries
    sheet5 = dd_json.get("sheet_5_upd_query_templates", [])
    if isinstance(sheet5, list):
        dd_queries.extend(sheet5)
        
    # 3. Fallback to legacy generic array
    if not dd_queries:
        dd_queries = dd_json.get("dd_queries", [])

    valid_queries = []
    seen_names = set()
    for q in dd_queries:
        sql = q.get("sql", {})
        # A query is valid if it has at least one important clause or is not empty (has raw_sql or query_name)
        has_select = isinstance(sql.get("select"), list) or (isinstance(sql.get("select"), str) and sql.get("select").strip())
        has_from = bool(sql.get("from", "").strip())
        has_target = bool(sql.get("target_table", "").strip())
        has_cols = bool(q.get("columns", []))
        has_raw_sql = bool(q.get("raw_sql", "").strip())
        
        if not has_select and not has_from and not has_target and not has_cols and not has_raw_sql:
            continue
            
        q_name = (q.get("query_name") or "").strip()
        if q_name:
            if q_name in seen_names:
                continue
            seen_names.add(q_name)
            
        valid_queries.append(q)
    return valid_queries


def extract_parameters(dd_json: dict, dd_queries: list[dict]) -> dict:
    param_map = {}
    param_info = dd_json.get("sheet_2_overview", {}).get("parameter_info", [])
    if param_info:
        for p in param_info:
            item_name = p.get("item_name", "")
            d_type = p.get("data_type", "") or "string"
            if item_name:
                param_map[item_name] = d_type

    # Extract from detail_specs query_mappings
    detail_specs = dd_json.get("sheet_3_detail_specs", [])
    for spec in detail_specs:
        for qmap in spec.get("query_mappings", []):
            for p in qmap.get("parameters", []):
                pname = p.get("name")
                if pname:
                    param_map.setdefault(pname, "string")

    legacy_vba = dd_json.get("vba_function_args", [])
    for entry in legacy_vba:
        if ":" in entry:
            k, v = entry.split(":", 1)
            param_map.setdefault(k.strip(), v.strip())
        else:
            param_map.setdefault(entry.strip(), "string")

    for q in dd_queries:
        for w in q.get("sql", {}).get("where", []):
            cond = w.get("condition", "")
            if cond:
                for m in re.finditer(r":(\w+)", cond):
                    p_name = m.group(1)
                    param_map.setdefault(p_name, "string")
    return param_map


def register_query_columns(dd_queries: list[dict], config: dict):
    for q in dd_queries:
        for col in q.get("columns", []):
            alias = col.get("alias", "").strip()
            col_name_raw = col.get("column_name", "")
            jp_raw = alias if alias else col_name_raw.split("\n")[0].strip()
            if jp_raw:
                jp = jp_raw.split('.')[-1].replace('"', '').strip()
                get_english_name(jp, config)


def resolve_physical_table_name(name: str, config: dict) -> str:
    """
    Resolve a query or table name to the actual physical table name in config,
    using robust normalization.
    """
    if not config:
        return name
    table_map = config.get("table_name", {})
    if name in table_map:
        return name
        
    def normalize(s: str) -> str:
        s = s.lower().replace('_', '')
        while True:
            next_s = re.sub(r'^[qct]\d*', '', s)
            if next_s == s:
                break
            s = next_s
        return s

    norm_name = normalize(name)
    if norm_name:
        for key in table_map.keys():
            if normalize(key) == norm_name:
                return key
                
    return name


def build_dependency_graph(dd_queries: list[dict], config: dict = None):
    query_map = {q.get("query_name", ""): q for q in dd_queries if q.get("query_name")}
    all_query_names = set(query_map.keys())

    def find_refs(q_obj):
        refs = []
        s = q_obj.get("sql", {})
        f = s.get("from", "")
        if f:
            t = extract_primary_table(f)
            if t in all_query_names: refs.append(t)
        for j in s.get("join", []):
            jt = j.get("table", "")
            if jt:
                t = extract_primary_table(jt)
                if t in all_query_names: refs.append(t)
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
        s = query_map[name].get("sql", {})
        target = s.get("target_table", "")
        if target:
            return extract_primary_table(target)
            
        # Otherwise fallback to FROM clause
        f = s.get("from", "")
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


def get_recursive_deps(name: str, deps_map: dict, collected=None):
    if collected is None: collected = []
    for d in deps_map.get(name, []):
        if d not in collected:
            get_recursive_deps(d, deps_map, collected)
            collected.append(d)
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


def generate_files_for_table(
    table_name: str, 
    queries: list[dict], 
    schema: dict, 
    query_map: dict, 
    deps_map: dict, 
    parsed_args: list[dict], 
    config: dict,
    dd_json: dict = None
) -> list[dict]:
    files = []
    
    table_en = find_table_key(table_name, config)
    base_name = sanitize_identifier(table_en)
    
    entity_class_name = f"{base_name}Entity"
    repo_class_name   = f"{base_name}Repository"
    
    repo_dtos = []
    repo_functions = []
    
    schema = schema or {"table_name": table_name, "fields": []}
    entity_fields = schema.get("fields", [])
    
    # Pre-build all_fields map from all schemas for full resolution across joins
    global_fields = []
    if dd_json:
        for s in dd_json.get("table_schemas", []):
            flds = s.get("fields") or s.get("columns") or []
            for col in flds:
                cname = col.get("name") or col.get("physical_name") or col.get("column_name") or ""
                if cname:
                    c_dict = dict(col)
                    c_dict["name"] = cname
                    global_fields.append(c_dict)
    for ef in entity_fields:
        global_fields.append(ef)

    entity_prop_names = {get_csharp_prop_name(f.get("name", ""), config) for f in entity_fields}
    
    methods: list[dict] = []
    repo_ctes = {}
    dto_files_data = []
    
    # Deduplication caches for DTOs
    output_dto_cache = {} # signature -> class_name
    input_dto_cache = {}  # signature -> class_name
    
    def to_pascal(s):
        return s[0].upper() + s[1:] if s else "Unknown"

    for i, q in enumerate(queries):
        q_name = q.get("query_name")
        all_deps = get_recursive_deps(q_name, deps_map)
        for dep_name in all_deps:
            if dep_name not in repo_ctes:
                dep_q = query_map[dep_name]
                dep_sql = build_sql(dep_q.get("sql", {}))
                indented = "\n".join("    " + line for line in dep_sql.split("\n"))
                
                cte_map = config.setdefault("cte_name", {})
                if dep_name in cte_map:
                    cte_en = cte_map[dep_name]
                    if cte_en == "TODO" or not cte_en:
                        cte_id = "Cte_" + sanitize_identifier(dep_name)
                    else:
                        cte_id = "Cte_" + cte_en
                else:
                    cte_map[dep_name] = "TODO"
                    cte_id = "Cte_" + sanitize_identifier(dep_name)
                    
                repo_ctes[dep_name] = {
                    "id": cte_id,
                    "jp_name": dep_name,
                    "sql_frag": f'"{dep_name}" AS (\n{indented}\n)',
                    "query_purpose": dep_q.get("query_purpose", "")
                }
                
        method_name = derive_method_name(q, i, len(queries), config)
        method_base_name = method_name[:-5] if method_name.endswith("Async") else method_name
        
        # Determine if query needs a custom DTO
        query_fields = derive_fields_from_queries([q], config)
        
        def get_real_cs_type(f: dict) -> str:
            df_name = f.get("name", "").split('.')[-1].replace('"', '').strip()
            raw_col_name = f.get("raw_column_name", "").split("\n")[0].split('.')[-1].replace('"', '').strip()
            search_names = [n for n in [raw_col_name, df_name] if n]
            
            for search_name in search_names:
                for e_f in global_fields:
                    if e_f.get("name") == search_name:
                        return e_f.get("csharp_type") or oracle_to_cs_type(e_f.get("type", "VARCHAR2"))
            return f.get("csharp_type") or oracle_to_cs_type(f.get("type", "VARCHAR2"))

        if len(query_fields) == 1:
            final_return_type = get_real_cs_type(query_fields[0])
            has_extra_fields = False
        else:
            q_dto_extra = []
            q_seen_props = set()
            
            for f in query_fields:
                pname = get_csharp_prop_name(f.get("name", ""), config)
                if pname not in entity_prop_names and pname not in q_seen_props:
                    q_dto_extra.append(f)
                    q_seen_props.add(pname)
                    
            has_extra_fields = len(q_dto_extra) > 0
            
            if has_extra_fields:
                # Make sure DTO fields have real types and constraints
                for df in query_fields:
                    df["csharp_type"] = get_real_cs_type(df)
                    df_name = df.get("name", "").split('.')[-1].replace('"', '').strip()
                    raw_col_name = df.get("raw_column_name", "").split("\n")[0].split('.')[-1].replace('"', '').strip()
                    search_names = [n for n in [raw_col_name, df_name] if n]
                    
                    # Pull max_length and required from entity fields if match
                    found_match = False
                    for search_name in search_names:
                        for e_f in global_fields:
                            if e_f.get("name") == search_name:
                                for key in ["required", "length"]:
                                    if key in e_f and key not in df:
                                        df[key] = e_f[key]
                                found_match = True
                                break
                        if found_match:
                            break
                
                # Build unique signature for this output DTO
                dto_fields_sig_list = []
                dto_fields_resolved = []
                seen_props = set()
                for f in query_fields:
                    jp_raw = f.get("name", "")
                    jp = jp_raw.split('.')[-1].replace('"', '').strip() if jp_raw else ""
                    cs_type = f.get("csharp_type")
                    pname = get_csharp_prop_name(jp_raw, config)
                    if pname in seen_props:
                        continue
                    seen_props.add(pname)
                    dto_fields_sig_list.append((jp, cs_type))
                    dto_fields_resolved.append({
                        "name": pname,
                        "type": cs_type,
                        "description": jp
                    })
                
                dto_sig = tuple(sorted(dto_fields_sig_list))
                
                if dto_sig in output_dto_cache:
                    final_return_type = output_dto_cache[dto_sig]
                else:
                    dto_class_name = f"{method_base_name}Dto"
                    output_dto_cache[dto_sig] = dto_class_name
                    final_return_type = dto_class_name
                    
                    dto_cs = gen_dto_class(dto_class_name, query_fields, config, namespace_suffix=base_name)
                    dto_files_data.append({
                        "path": f"Domain/DTOs/{base_name}/{dto_class_name}.cs",
                        "content": dto_cs,
                    })
                
                if not any(d["dto_name"] == final_return_type for d in repo_dtos):
                    repo_dtos.append({
                        "dto_name": final_return_type,
                        "fields": dto_fields_resolved
                    })
            else:
                final_return_type = entity_class_name
        
        raw_p = q.get("parameters", "")
        q_param_names = {p.strip() for p in raw_p.split(",") if p.strip()}
        for w in q.get("sql", {}).get("where", []):
            cond = w.get("condition", "")
            if cond:
                for m in re.finditer(r":(\w+)", cond):
                    q_param_names.add(m.group(1))

        if dd_json:
            detail_specs = dd_json.get("sheet_3_detail_specs", [])
            q_name = q.get("query_name", "")
            for spec in detail_specs:
                for qmap in spec.get("query_mappings", []):
                    if qmap.get("logic_query_name") == q_name or qmap.get("sheet_name") == q.get("sheet_name_pattern"):
                        for p in qmap.get("parameters", []):
                            pname = p.get("name")
                            if pname:
                                q_param_names.add(pname)
                    
        method_args = [
            a for a in parsed_args 
            if a['vba'] in q_param_names or a['jp_key'] in q_param_names or a['cs_name'] in q_param_names
        ]
        
        use_method_input_dto = len(method_args) > 3
        
        resolved_input_dto_name = ""
        if use_method_input_dto:
            # Build unique signature for Input DTO
            input_sig_list = []
            input_fields_resolved = []
            for a in method_args:
                typ = a['cs_type']
                name = a['cs_name']
                prop = name[0].upper() + name[1:] if name else "Unknown"
                input_sig_list.append((prop, typ))
                input_fields_resolved.append({
                    "name": prop,
                    "type": typ,
                    "description": a.get("jp_key", "")
                })
            input_sig = tuple(sorted(input_sig_list))
            
            if input_sig in input_dto_cache:
                resolved_input_dto_name = input_dto_cache[input_sig]
            else:
                resolved_input_dto_name = f"{method_base_name}InputDto"
                input_dto_cache[input_sig] = resolved_input_dto_name
                
                input_cs = gen_input_dto(resolved_input_dto_name, method_args, namespace_suffix=base_name)
                dto_files_data.append({
                    "path": f"Domain/DTOs/{base_name}/{resolved_input_dto_name}.cs",
                    "content": input_cs,
                })
                
            if not any(d["dto_name"] == resolved_input_dto_name for d in repo_dtos):
                repo_dtos.append({
                    "dto_name": resolved_input_dto_name,
                    "fields": input_fields_resolved
                })
                
            params_str = f"{resolved_input_dto_name} request"
            dapper_params_str = ", ".join(f"{a['vba']} = request.{to_pascal(a['cs_name'])}" for a in method_args)
        else:
            params_str  = ", ".join(f"{a['cs_type']} {a['cs_name']}" for a in method_args)
            dapper_params_str = ", ".join(f"{a['vba']} = {a['cs_name']}" for a in method_args)
            
        return_type = derive_return_type(final_return_type, q)
        
        sql_block = q.get("sql", {})
        has_select = isinstance(sql_block.get("select"), list) or (isinstance(sql_block.get("select"), str) and sql_block.get("select").strip())
        has_from = bool(sql_block.get("from", "").strip())
        has_target = bool(sql_block.get("target_table", "").strip())
        has_cols = bool(q.get("columns", []))
        is_fallback_stub = not has_select and not has_from and not has_target and not has_cols

        base_sql = build_sql(sql_block, default_table=table_name)
        
        cmt_line = ""
        jp_query_name = q.get("query_name", "")
        if jp_query_name:
            query_purpose = q.get("query_purpose", "").strip()
            param_comments = []
            if "request" in params_str:
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

        sheet = q.get("sheet_name_pattern", "")
        is_action = "Upd" in sheet or "Del" in sheet or "Ins" in sheet
        
        methods.append({
            "name":          method_name,
            "return_type":   return_type,
            "params":        params_str,
            "dapper_params": dapper_params_str,
            "base_sql":      base_sql,
            "deps":          all_deps,
            "comment":       cmt_line,
            "is_action":     is_action,
            "is_fallback_stub": is_fallback_stub,
        })
        
        # Resolve Input list for repository JSON
        inputs_list = []
        if use_method_input_dto:
            inputs_list.append({
                "name": resolved_input_dto_name,
                "type": "dto",
                "description": ""
            })
        else:
            for a in method_args:
                inputs_list.append({
                    "name": a["cs_name"],
                    "type": a["cs_type"],
                    "description": a.get("jp_key", "")
                })

        # Resolve Output list for repository JSON
        outputs_list = []
        if is_action:
            outputs_list.append({
                "name": "",
                "type": "int",
                "description": ""
            })
        elif len(query_fields) == 1:
            outputs_list.append({
                "name": "",
                "type": get_real_cs_type(query_fields[0]),
                "description": ""
            })
        elif len(query_fields) > 1:
            if has_extra_fields:
                outputs_list.append({
                    "name": final_return_type,
                    "type": "dto",
                    "description": ""
                })
            else:
                outputs_list.append({
                    "name": entity_class_name,
                    "type": "entity",
                    "description": ""
                })

        repo_functions.append({
            "function_name": method_name,
            "query_name": q_name or "",
            "sheet_query_name": q.get("sheet_name_pattern", ""),
            "description": q.get("query_purpose", "").strip(),
            "input": inputs_list,
            "output": outputs_list
        })
        
    entity_cs = gen_csharp_class(entity_class_name, entity_fields, config, base_class="BaseEntity", jp_table_name=table_name)
    iface_cs  = gen_interface(base_name, methods, namespace_suffix=base_name, jp_table_name=table_name)
    repo_cs   = gen_repository(base_name, entity_class_name, methods, repo_ctes, namespace_suffix=base_name, jp_table_name=table_name) # NOTE: final_return_type varies by method now
    
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
        jp_raw  = field.get("name", "")
        jp = jp_raw.split('.')[-1].replace('"', '').strip() if jp_raw else ""
        cs_type = field.get("csharp_type") or oracle_to_cs_type(field.get("type", "VARCHAR2"))
        prop = get_csharp_prop_name(jp_raw, config)
        entity_fields_resolved.append({
            "name": prop,
            "type": cs_type,
            "description": jp
        })
    repo_entities = [
        {
            "entity_name": entity_class_name,
            "fields": entity_fields_resolved
        }
    ]

    repo_json = {
        "repository_name": repo_class_name,
        "table_name": table_name,
        "function": repo_functions,
        "dto": repo_dtos,
        "entity": repo_entities
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
def merge_csharp_code(existing_code: str, new_code: str) -> str:
    """
    Merge new_code into existing_code.
    Replaces existing CTEs and methods if their Japanese query name matches.
    Otherwise, appends them.
    """
    # Normalize all line endings to standard \n to guarantee 100% regex reliability
    existing_code = existing_code.replace('\r\n', '\n')
    new_code = new_code.replace('\r\n', '\n')

    # Auto-heal missing braces in existing_code
    open_braces = existing_code.count('{')
    close_braces = existing_code.count('}')
    if open_braces > close_braces:
        existing_code += "\n}\n"

    match_new = re.search(r'^(.*?(?:public\s+(?:class|interface|record)\s+\w+(?:\s*:\s*[a-zA-Z0-9_<>]+)?\s*\{))(.*?)(\}\s*)$', new_code, flags=re.DOTALL)
    if not match_new:
        return new_code
    _, new_body, _ = match_new.groups()

    # Extract blocks from new_code
    pattern = re.compile(
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
    
    matches = list(pattern.finditer(new_body))
    new_blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i + 1 < len(matches) else len(new_body)
        block_code = new_body[start:end].rstrip()
        # Preserve indentation, only strip leading newlines
        block_code = re.sub(r'^\r?\n+', '', block_code)
        if not block_code.strip():
            continue
        
        name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
        new_blocks.append({
            "code": block_code,
            "name": name,
            "type": "prop" if m.group(1) else "iface" if m.group(2) else "cte" if m.group(3) else "method"
        })

    final_code = existing_code

    # Function to find end of balanced braces
    def find_balanced_block_end(text, start_search_idx):
        open_brace_idx = text.find('{', start_search_idx)
        if open_brace_idx == -1:
            return -1
        braces = 1
        curr = open_brace_idx + 1
        while curr < len(text) and braces > 0:
            if text[curr] == '{':
                braces += 1
            elif text[curr] == '}':
                braces -= 1
            curr += 1
        return curr if braces == 0 else -1

    # ──────────────────────────────────────────
    # Pre-cleanup Phase: Explicitly remove legacy TODO methods/interfaces
    # if a new block is about to generate them.
    # ──────────────────────────────────────────
    for block in new_blocks:
        b_type = block["type"]
        code = block["code"]
        if b_type in ("method", "iface"):
            jp_match = re.search(r'///\s*<summary>\s*\n\s*///\s*([^\n]+)\s*\n', code)
            if jp_match:
                jp_name = jp_match.group(1).strip()
                if b_type == "method":
                    todo_pattern = (
                        r'^[ \t]*///\s*<summary>\s*\n'
                        r'[ \t]*///\s*' + re.escape(jp_name) + r'\s*\n'
                        r'(?:[ \t]*///[^\n]*\n)*'
                        r'[ \t]*///\s*</summary>\s*\n'
                        r'(?:[ \t]*///[^\n]*\n)*'
                        r'[ \t]*public\s+(?:async\s+)?Task<(?:[^\(]+)>\s+TODO_[^\s\(\)\;]+\s*\('
                    )
                    m_match = re.search(todo_pattern, final_code, re.MULTILINE)
                    if m_match:
                        start_idx = m_match.start()
                        end_idx = find_balanced_block_end(final_code, start_idx)
                        if end_idx != -1:
                            final_code = final_code[:start_idx] + final_code[end_idx:]
                
                elif b_type == "iface":
                    todo_pattern = (
                        r'^[ \t]*///\s*<summary>\s*\n'
                        r'[ \t]*///\s*' + re.escape(jp_name) + r'\s*\n'
                        r'(?:[ \t]*///[^\n]*\n)*'
                        r'[ \t]*///\s*</summary>\s*\n'
                        r'(?:[ \t]*///[^\n]*\n)*'
                        r'[ \t]*Task<(?:[^\(]+)>\s+TODO_[^\s\(\)\;]+\s*\(.*?\);'
                    )
                    m_match = re.search(todo_pattern, final_code, re.MULTILINE)
                    if m_match:
                        start_idx = m_match.start()
                        end_sig = re.search(r';[ \t]*(?:\n|$)', final_code[start_idx:])
                        if end_sig:
                            end_idx = start_idx + end_sig.end()
                            final_code = final_code[:start_idx] + final_code[end_idx:]

    blocks_to_append = []

    for block in new_blocks:
        code = block["code"]
        name = block["name"]
        b_type = block["type"]
        is_replaced = False

        if b_type == "cte":
            # Unified search for existing CTE: either by JP name in comment or Fallback by identifier name
            target_idx = -1
            jp_name_match = re.search(r'^[ \t]*///\s*([^\n]+)\s*\n(?:[ \t]*///[^\n]*\n)*\s*(?:private\s+const\s+string|private\s+string)', code, re.MULTILINE)
            if jp_name_match:
                jp_name = jp_name_match.group(1).strip()
                # Find the existing CTE starting from its JP Name comment line
                c_match = re.search(
                    r'^[ \t]*///\s*' + re.escape(jp_name) + r'\s*\n'
                    r'(?:[ \t]*///[^\n]*\n)*\s*'
                    r'(?:private\s+const\s+string\s+[^\s\(\)\;=]+\s*=|private\s+string\s+[^\s\(\)\;=]+\s*\(\s*\))',
                    final_code, re.MULTILINE
                )
                if c_match:
                    target_idx = c_match.start()
            
            # Fallback to matching by raw name if JP Name match fails
            if target_idx == -1 and name:
                # Match either raw private string OR raw private const string
                m_match = re.search(
                    r'^[ \t]*(?:private\s+const\s+string\s+|private\s+string\s+)' + re.escape(name) + r'(?:\s*=|\s*\(\s*\))',
                    final_code, re.MULTILINE
                )
                if m_match:
                    target_idx = m_match.start()
                    
            if target_idx != -1:
                # Back up from the anchor to include ALL preceding comments (cleans up duplicates)
                start_idx = target_idx
                prev_newline = final_code.rfind('\n', 0, start_idx)
                while prev_newline != -1:
                    prev_prev = final_code.rfind('\n', 0, prev_newline)
                    line_start = 0 if prev_prev == -1 else prev_prev + 1
                    line_content = final_code[line_start:prev_newline].strip()
                    if line_content.startswith('///'):
                        start_idx = line_start
                        prev_newline = prev_prev
                    else:
                        break
                
                # Determine block end depending on if it is a const string or a function
                anchor_text = final_code[target_idx:]
                is_const = re.match(r'^[ \t]*private\s+const\s+string', anchor_text, re.MULTILINE)
                
                if is_const:
                    const_pattern = r'^[ \t]*private\s+const\s+string\s+\w+\s*=\s*@".*?";'
                    c_end_match = re.search(const_pattern, anchor_text, re.DOTALL | re.MULTILINE)
                    if c_end_match:
                        end_idx = target_idx + c_end_match.end()
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True
                else:
                    end_idx = find_balanced_block_end(final_code, target_idx)
                    if end_idx != -1:
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True

        elif b_type == "method":
            # Extract JP query name from summary
            jp_name_match = re.search(r'///\s*<summary>\s*\n\s*///\s*([^\n]+)\s*\n(?:\s*///[^\n]*\n)*\s*///\s*</summary>', code)
            if jp_name_match:
                jp_name = jp_name_match.group(1).strip()
                # Search for comment in existing code
                c_match = re.search(r'^[ \t]*///\s*<summary>\s*\n\s*///\s*' + re.escape(jp_name) + r'\s*\n(?:[ \t]*///[^\n]*\n)*\s*///\s*</summary>', final_code, re.MULTILINE)
                if c_match:
                    start_idx = c_match.start()
                    end_idx = find_balanced_block_end(final_code, start_idx)
                    if end_idx != -1:
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True
            
            # Fallback to matching method name
            if not is_replaced and name:
                # Pattern for signature: public async Task<...> SearchAsync(
                m_match = re.search(r'^[ \t]*public\s+async\s+Task<(?:[^\(]+)>\s+' + re.escape(name) + r'\s*\(', final_code, re.MULTILINE)
                if m_match:
                    # Include preceding summary comments if any
                    start_idx = m_match.start()
                    # Search backward for comments
                    prev_newline = final_code.rfind('\n', 0, start_idx)
                    while prev_newline != -1:
                        prev_prev = final_code.rfind('\n', 0, prev_newline)
                        line_start = 0 if prev_prev == -1 else prev_prev + 1
                        line_content = final_code[line_start:prev_newline].strip()
                        if line_content.startswith('///') or line_content.startswith('['):
                            start_idx = line_start
                            prev_newline = prev_prev
                        else:
                            break
                    
                    end_idx = find_balanced_block_end(final_code, m_match.start())
                    if end_idx != -1:
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True
                        
        elif b_type == "prop":
            # 1. Try to match existing property by [Column("JP")] attribute
            col_match = re.search(r'\[Column\("([^"]+)"\)\]', code)
            if col_match:
                jp_col = col_match.group(1)
                # Match any existing property block with the same Japanese Column Name
                # This handles both matching identifiers and replacing old TODO properties!
                col_pattern = (
                    r'(?:^[ \t]*///[^\n]*\n)*'
                    r'(?:^[ \t]*\[[^\]]+\]\n)*'
                    r'(?:^[ \t]*\[Column\("' + re.escape(jp_col) + r'"\)\]\n)'
                    r'(?:^[ \t]*\[[^\]]+\]\n)*'
                    r'^[ \t]*public\s+[\w\<\>\[\]\?\s]+\s+[^\s\{\}\;]+\s*\{\s*get;\s*set;\s*\}.*'
                )
                replaced, count = re.subn(col_pattern, code, final_code, count=1, flags=re.MULTILINE)
                if count > 0:
                    final_code = replaced
                    is_replaced = True
            
            # 2. Try to match by comment (fallback for legacy TODO cleanup)
            if not is_replaced:
                comment_match = re.search(r'//\s*(.*?)(?:\r?\n|$)', code)
                if comment_match:
                    jp_cmt = comment_match.group(1).strip()
                    # Clean typical wrappers if any
                    search_term = jp_cmt.replace("TODO: translate '", "").rstrip("'")
                    if search_term:
                        # Pattern matches an existing property that contains TODO and the term in either name or comment
                        todo_patterns = [
                            # Property with TODO_ prefix and same text in its comment
                            r'(?:^[ \t]*///[^\n]*\n)*(?:^[ \t]*\[[^\]]+\]\n)*[ \t]*public\s+[\w\<\>\[\]\?\s]+\s+TODO_[^\s\{\}\;]+\s*\{\s*get;\s*set;\s*\}.*?//.*?' + re.escape(search_term) + r'.*',
                            # Property with any name but its comment explicitly states 'TODO' and contains the term
                            r'(?:^[ \t]*///[^\n]*\n)*(?:^[ \t]*\[[^\]]+\]\n)*[ \t]*public\s+[\w\<\>\[\]\?\s]+\s+[^\s\{\}\;]+\s*\{\s*get;\s*set;\s*\}.*?//.*?TODO.*?' + re.escape(search_term) + r'.*'
                        ]
                        for p in todo_patterns:
                            replaced, count = re.subn(p, code, final_code, count=1, flags=re.MULTILINE)
                            if count > 0:
                                final_code = replaced
                                is_replaced = True
                                break
            
            # 3. Standard Fallback: match by property identifier name
            if not is_replaced and name:
                find_pattern = r'(?:^[ \t]*///[^\n]*\n)*(?:^[ \t]*\[[^\]]+\]\n)*[ \t]*public\s+[\w\<\>\[\]\?\s]+\s+' + re.escape(name) + r'\s*\{\s*get;\s*set;\s*\}.*'
                replaced, count = re.subn(find_pattern, code, final_code, count=1, flags=re.MULTILINE)
                if count > 0:
                    final_code = replaced
                    is_replaced = True

        elif b_type == "iface":
            # 1. Try to match by JP query name in summary (if it has one)
            jp_name_match = re.search(r'///\s*<summary>\s*\n\s*///\s*([^\n]+)\s*\n(?:\s*///[^\n]*\n)*\s*///\s*</summary>', code)
            if jp_name_match:
                jp_name = jp_name_match.group(1).strip()
                c_match = re.search(r'^[ \t]*///\s*<summary>\s*\n\s*///\s*' + re.escape(jp_name) + r'\s*\n(?:[ \t]*///[^\n]*\n)*\s*///\s*</summary>', final_code, re.MULTILINE)
                if c_match:
                    start_idx = c_match.start()
                    after_comments = final_code[start_idx:]
                    match_sig = re.search(r'^(?:[ \t]*///[^\n]*\n)*[ \t]*Task<(?:[^\(]+)>\s+\w+\s*\(.*?\);', after_comments, re.MULTILINE)
                    if match_sig:
                        end_idx = start_idx + match_sig.end()
                        final_code = final_code[:start_idx] + code + final_code[end_idx:]
                        is_replaced = True
            
            # 2. Fallback to matching by identifier
            if not is_replaced and name:
                find_pattern = r'(?:^[ \t]*///[^\n]*\n)*[ \t]*Task<(?:[^\(]+)>\s+' + re.escape(name) + r'\(.*?\);'
                replaced, count = re.subn(find_pattern, code, final_code, count=1, flags=re.MULTILINE)
                if count > 0:
                    final_code = replaced
                    is_replaced = True

        if not is_replaced:
            # If it was never replaced, append it
            blocks_to_append.append(code)

    if blocks_to_append:
        last_brace_idx = final_code.rfind('}')
        if last_brace_idx != -1:
            insertion = "\n\n" + "\n\n".join(blocks_to_append) + "\n"
            final_code = final_code[:last_brace_idx] + insertion + final_code[last_brace_idx:]

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




# ── Main processor ────────────────────────────────────────────────────────────
def process_file(input_path: Path, config: dict):
    print(f"  📄 {input_path.name}")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    dd_json = data
    form_name = dd_json.get("form_name") or dd_json.get("screen_name") or "Default"
    
    dd_queries = extract_valid_queries(dd_json)
    param_map = extract_parameters(dd_json, dd_queries)
    vba_args_raw = [f"{k}: {v}" for k, v in param_map.items()]
    parsed_args = parse_vba_args(vba_args_raw, config)

    table_schemas = dd_json.get("table_schemas", [])
    schema_map = {}
    for s in table_schemas:
        unified = unify_schema_fields(s)
        tname = unified["table_name"]
        if tname:
            schema_map[tname] = unified

    register_query_columns(dd_queries, config)
    
    table_queries, query_map, deps_map = build_dependency_graph(dd_queries)

    OUTPUTS_DIR.mkdir(exist_ok=True)
    
    for table_name, queries in table_queries.items():
        # Find schema
        schema = schema_map.get(table_name)
        if not schema:
            for k, v in schema_map.items():
                if k in table_name or table_name in k:
                    schema = v
                    break
                    
        files = generate_files_for_table(
            table_name, queries, schema, query_map, deps_map, parsed_args, config, dd_json
        )
        
        for file_info in files:
            file_path = Path(file_info["path"])
            file_name = file_path.name
            if file_path.suffix == ".json":
                out_path = OUTPUTS_DIR / "repo" / file_name
            else:
                out_path = OUTPUTS_DIR / file_name
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if out_path.exists():
                if out_path.suffix == ".cs":
                    existing = out_path.read_text(encoding="utf-8")
                    content_to_write = merge_csharp_code(existing, file_info["content"])
                elif out_path.suffix == ".json":
                    existing = out_path.read_text(encoding="utf-8")
                    content_to_write = merge_repository_json(existing, file_info["content"])
                else:
                    content_to_write = file_info["content"]
            else:
                content_to_write = file_info["content"]
            out_path.write_text(content_to_write, encoding="utf-8")
            print(f"      ✓  {file_name}")


def main():
    args = sys.argv[1:]
    config = load_config()

    if "--file" in args:
        idx = args.index("--file")
        target = Path(args[idx + 1])
        files = [target] if target.exists() else []
    else:
        files = [f for f in INPUTS_DIR.glob("*.json") if f.name != ".gitkeep"]

    if not files:
        print("❌ No input files found.")
        sys.exit(1)

    print(f"\n🔧 Processing {len(files)} file(s)...\n")
    for f in files:
        try:
            process_file(f, config)
        except Exception as exc:
            import traceback
            print(f"  ❌ Error in {f.name}: {exc}")
            traceback.print_exc()

    save_config(config)
    print(f"\n✅ config.json updated  → {CONFIG_FILE}")
    print(f"✅ C# files written     → {OUTPUTS_DIR}\n")


if __name__ == "__main__":
    main()
