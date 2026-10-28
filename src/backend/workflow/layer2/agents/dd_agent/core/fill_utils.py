import json
import re
from pathlib import Path
from typing import Any

from utils.vba_utils import strip_vba_comments, normalize_query_name
from utils.vba_utils import normalize_vba_name  # noqa: F401  (re-exported to the DD modules)

# VBA calls to external macros/modules → mark as [refer:xxx]
REFER_PATTERNS = [
    re.compile(r"Call\s+([\w＿一-龯ぁ-ゔァ-ヶー]+)", re.IGNORECASE),
    re.compile(r'DoCmd\.RunMacro\s+"([^"]+)"', re.IGNORECASE),
]

def convert_macro_actions_to_pseudo_code(actions: list[dict]) -> str:
    """Convert a list of macro actions into a readable pseudo-code string."""
    lines = []
    for act in actions:
        name = act.get("action", "Action")
        cond = act.get("condition", "")
        
        args_dict = {k: v for k, v in act.items() if k not in ["action", "condition"]}
        if not args_dict and "arguments" in act:
            raw_args = act.get("arguments")
            if isinstance(raw_args, dict):
                args_dict = raw_args
            elif isinstance(raw_args, list):
                args_dict = {"args": raw_args}
                
        arg_str = ", ".join(f"{k}={v}" for k, v in args_dict.items())
        
        line = f"{name}({arg_str})"
        if cond:
            line = f"If {cond} Then {line}"
        lines.append(line)
    return "\n".join(lines)

# (normalize_query_name and strip_vba_comments are now imported from utils.vba_utils)

def find_queries_for_code(code: str, all_queries: list[dict], references: dict = None, table_config: dict = None) -> list[dict]:
    """Find SQL queries that are explicitly called in this VBA code or in references."""
    from .query_mapper import _get_mapped_query
    used_qnames_map = {}
    clean_code = strip_vba_comments(code)
    # Standard DoCmd calls
    for m in re.finditer(r'DoCmd\.OpenQuery\s+"([^"]+)"', clean_code, re.IGNORECASE):
        qname = m.group(1)
        mapped_q = _get_mapped_query(qname, table_config)
        effective_qname = mapped_q if mapped_q else qname
        used_qnames_map[normalize_query_name(effective_qname)] = effective_qname

    # Domain Aggregate functions: DLookup, DCount, DSum, DMax, DMin
    # Pattern: DLookup("column", "query_or_table", "criteria")
    for m in re.finditer(r'D(?:Lookup|Count|Sum|Max|Min)\s*\(\s*"[^"]+"\s*,\s*"([^"]+)"', clean_code, re.IGNORECASE):
        qname = m.group(1)
        mapped_q = _get_mapped_query(qname, table_config)
        effective_qname = mapped_q if mapped_q else qname
        used_qnames_map[normalize_query_name(effective_qname)] = effective_qname
    
    if references and "queries" in references:
        for q_name in references["queries"]:
            used_qnames_map[normalize_query_name(q_name)] = q_name
            
    results = []
    seen_norm = set()
    for norm_name, orig_name in used_qnames_map.items():
        if norm_name in seen_norm:
            continue
        seen_norm.add(norm_name)
        found = False
        for q in all_queries:
            q_name = q.get("query_name") or q.get("name")
            if normalize_query_name(q_name) == norm_name:
                results.append({
                    "query_name": q_name,
                    "sql": q.get("sql") or q.get("sql_logic") or q.get("query") or {"raw_sql": q.get("raw_sql", "")},
                    "parameters": q.get("parameters", []),
                    "query_type": q.get("query_type", "SELECT"),
                    "description": q.get("description") or q.get("query_purpose", "")
                })
                found = True
                break
        if not found:
            results.append({"query_name": orig_name, "query_type": "UNKNOWN", "sql": {}})
    return results

def parse_dd_source(dd_code_json_path: Path, table_config: dict = None) -> list[dict[str, Any]]:
    """Parse D1 dd_code_json into a list of logic items for DD mapping."""
    if not dd_code_json_path.exists():
        return []
    with open(dd_code_json_path, encoding="utf-8") as f:
        dd_source = json.load(f)

    all_queries = []
    # If the file itself contains query definitions, collect them
    if "related_queries" in dd_source:
        for q in dd_source["related_queries"]:
            qname = q.get("query_name") or q.get("name")
            all_queries.append(
                {
                    "query_name": qname,
                    "query_type": q.get("query_type", "SELECT"),
                    "tables": q.get("tables", []),
                    "target_table": q.get("target_table"),
                    "form_references": q.get("form_references", []),
                    "parameters": q.get("parameters", []),
                    "sql": q.get("sql") or q.get("sql_logic") or q.get("query") or {"raw_sql": q.get("raw_sql", "")},
                    "raw_sql": q.get("raw_sql"),
                    "description": q.get("description") or q.get("query_purpose", ""),
                }
            )

    items: list[dict[str, Any]] = []

    functions = dd_source.get("procedures") or dd_source.get("vba_procedures")
    
    # Check inside form/report blocks
    if not functions:
        form_or_report = dd_source.get("form") or dd_source.get("report")
        if isinstance(form_or_report, dict):
            functions = form_or_report.get("vba_procedures") or form_or_report.get("procedures")
    
    # Check inside module block (for common modules)
    if not functions:
        module_data = dd_source.get("module")
        if isinstance(module_data, dict):
            functions = module_data.get("procedures") or module_data.get("functions")

    if isinstance(functions, dict):
        functions = [{"name": k, **v} for k, v in functions.items()]
    elif not isinstance(functions, list):
        functions = []

    for proc in functions:
        if proc.get("type", "").lower() == "declare function":
            continue
            
        code = proc.get("body", "")

        # Fallback to code if body doesn't exist
        if not code and "code" in proc:
            code = proc.get("code", "")
            
        mod_name = proc.get("name") or proc.get("handler", "")
        
        items.append({
            "module_id": mod_name,
            "title": mod_name,
            "code": code,
            "proc_type": proc.get("type", ""),
            "output_type": proc.get("output", ""),
            "queries": find_queries_for_code(code, all_queries, proc.get("references", {}), table_config),
            "references": proc.get("references", {})
        })

    return items

def extract_vba_dim_vars(code: str) -> list[dict[str, str]]:
    """Extract Dim/As declarations from VBA code as input_data_area entries."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    # Match: Dim varName As TypeName  or  Dim varName
    pattern = re.compile(
        r"Dim\s+([\w＿一-龯ぁ-ゔァ-ヶー]+)\s*(?:As\s+([\w＿一-龯ぁ-ゔァ-ヶー]+))?",
        re.IGNORECASE,
    )
    idx = 1
    for m in pattern.finditer(code):
        name = m.group(1).strip()
        dtype = (m.group(2) or "").strip()
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        results.append(
            {
                "no": str(idx),
                "name": name,
                "symbol": name,
                "io": "I",
                "type": dtype,
                "description": "",
            }
        )
        idx += 1
    return results

# (normalize_vba_name is now imported from utils.vba_utils)

def collect_pending_refers(code: str) -> list[str]:
    """Collect [refer:xxx] markers for external macro/module/form calls."""
    refers: list[str] = []
    seen: set[str] = set()
    for pat in REFER_PATTERNS:
        for m in pat.finditer(code):
            ref = m.group(1).strip().strip('"')
            key = ref.lower()
            if key not in seen:
                seen.add(key)
                refers.append(ref)
    return refers

def build_event_map(bd_final: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build module_id → event dict from bd4_bd_final."""
    event_map: dict[str, dict[str, Any]] = {}
    
    events = (bd_final.get("sheet_2_layout") or {}).get("events") or []
    for ev in events:
        mid = ev.get("module_id", "")
        if mid:
            event_map[mid] = ev
        
        # Also map by VBA procedure name if found in notes
        notes = ev.get("notes", "")
        if notes:
            # Extract first line, which is usually the VBA name
            vba_name = notes.split("\n")[0].strip()
            if vba_name and vba_name != mid:
                event_map[vba_name] = ev
                # Handle common suffixes like _Click or _AfterUpdate
                if "_Click" in vba_name:
                    event_map[vba_name.replace("_Click", "")] = ev
                if "_AfterUpdate" in vba_name:
                    event_map[vba_name.replace("_AfterUpdate", "")] = ev
    return event_map

def build_steps_placeholder(mid: str, refers: list[str]) -> list[dict[str, str]]:
    """Build a default 3-stage step list for documentation."""
    ref_text = "\n".join(f"- [refer: {r}]" for r in refers) if refers else ""
    return [
        {
            "step": "1. 初期処理",
            "detail": "なし"
        },
        {
            "step": "2. 主処理",
            "detail": ref_text if ref_text else "なし"
        },
        {
            "step": "3. 終了処理",
            "detail": "なし"
        }
    ]
