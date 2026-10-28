from __future__ import annotations
import re
from copy import deepcopy
from typing import Any

from ..core.constants import *
from ..core.utils import *
from ..core.extractors import *
def collect_sheet5(
    procs: list[dict[str, Any]],
    handler_to_event_id: dict[str, str],
    header_template: dict[str, str],
    events: list[dict[str, Any]],
    query_index: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    def strip_vba_comment(line: str) -> str:
        in_string = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"':
                if in_string and i + 1 < len(line) and line[i + 1] == '"':
                    i += 2
                    continue
                in_string = not in_string
                i += 1
                continue
            if not in_string and ch == "'":
                return line[:i]
            i += 1
        return line

    sheets: list[dict[str, Any]] = []
    for p in procs:
        handler = str(p.get("handler") or "")
        event_id = handler_to_event_id.get(handler)
        if not event_id:
            continue
        code = str(p.get("code") or "")
        if not code.strip():
            continue

        raw_lines = code.splitlines()
        cleaned_lines: list[str] = []
        current_line = ""
        for raw in raw_lines:
            s = raw.strip()
            if not s:
                continue
            if s.startswith("'") or s.lower().startswith("rem "):
                continue
            
            # Remove inline comments but keep space for continuation check
            line_content = strip_vba_comment(raw).rstrip()
            if not line_content:
                continue
            
            if current_line:
                current_line += " " + line_content.lstrip()
            else:
                current_line = line_content
            
            if current_line.endswith(" _"):
                current_line = current_line[:-2].rstrip()
            else:
                cleaned_lines.append(current_line)
                current_line = ""
        if current_line:
            cleaned_lines.append(current_line)

        if not cleaned_lines:
            continue

        cleaned_code = "\n".join(cleaned_lines)
        
        all_matches = []
        for m in OUTPUT_TO_RE.finditer(cleaned_code):
            all_matches.append(("outputto", m))
        for m in TRANSFER_SPREADSHEET_RE.finditer(cleaned_code):
            all_matches.append(("transferspreadsheet", m))
        for m in TRANSFER_TEXT_RE.finditer(cleaned_code):
            all_matches.append(("transfertext", m))

        if not all_matches:
            continue

        for idx, (m_type, m) in enumerate(all_matches, start=1):
            if m_type == "outputto":
                output_type = m.group(1).strip().strip('"')
                object_name = m.group(2).strip().strip('"')
                file_type_raw = m.group(3).strip().strip('"')
                output_path_raw = m.group(4).strip().strip('"')
            elif m_type == "transferspreadsheet":
                # DoCmd.TransferSpreadsheet [TransferType], [SpreadsheetType], [TableName], [FileName]
                object_name = m.group(3).strip().strip('"')
                output_path_raw = m.group(4).strip().strip('"')
                output_type = "transferspreadsheet"
                file_type_raw = "acformatxlsx" # Default for spreadsheet
            else: # transfertext
                # DoCmd.TransferText [TransferType], [SpecificationName], [TableName], [FileName]
                object_name = m.group(3).strip().strip('"')
                output_path_raw = m.group(4).strip().strip('"')
                output_type = "transfertext"
                file_type_raw = "acformatcsv" # Default for text

            # Map file type to extension
            file_type = FILE_EXT_MAP.get(file_type_raw.lower(), file_type_raw)
            # Normalize path
            file_name = normalize_vba_path_expression(output_path_raw)

            if output_type.lower() == "acoutputreport":
                for ev in events:
                    if ev.get("event_id") == event_id:
                        note = f"＊{object_name}を参照\n{file_name}"
                        if ev.get("notes"):
                            ev["notes"] = ev["notes"] + "\n" + note
                        else:
                            ev["notes"] = note
                continue

            sheet_header = deepcopy(header_template)
            sheet_header["file_name"] = file_name
            sheet_header["file_type"] = file_type

            items: list[dict[str, Any]] = []
            is_query_export = (output_type.lower() == "acquery" or m_type in ("transferspreadsheet", "transfertext"))
            if is_query_export and query_index and object_name in query_index:
                q_meta = query_index[object_name]
                q_obj = q_meta.get("query") or q_meta
                select_sql = str(q_obj.get("select") or "") if isinstance(q_obj, dict) else ""

                if select_sql:
                    # Simple balanced-parentheses split by comma
                    select_parts = []
                    curr_p = ""
                    p_count = 0
                    for char in select_sql:
                        if char == "(":
                            p_count += 1
                        elif char == ")":
                            p_count -= 1
                        elif char == "," and p_count == 0:
                            select_parts.append(curr_p)
                            curr_p = ""
                            continue
                        curr_p += char
                    if curr_p:
                        select_parts.append(curr_p)

                    for i, part in enumerate(select_parts, start=1):
                        part = part.strip()
                        # Find alias or field name
                        m_alias = re.search(r"\s+AS\s+\[?([^\]\s]+)\]?", part, re.IGNORECASE)
                        out_name = ""
                        if m_alias:
                            out_name = m_alias.group(1)
                        else:
                            # Use last field part: [Table].[Field] -> Field
                            m_f = re.search(r"(?:\[?[^\]\.]+(?:\]?)\.)?\[?([^\]\s]+)\]?$", part)
                            if m_f:
                                out_name = m_f.group(1)

                        if not out_name:
                            continue

                        out_name = normalize_field_token(out_name)
                        src_tbl, src_f, _ = resolve_source_table_field(
                            out_name, object_name, q_meta, query_index
                        )

                        src_tbl = format_source_table_names(src_tbl)
                        
                        items.append(
                            {
                                "no": str(i),
                                "output_field_name": out_name,
                                "source_table": src_tbl,
                                "source_field_or_fixed_value": src_f,
                                "condition_and_format": "",
                                "chk": "",
                                "notes": "",
                            }
                        )

            suffix = "" if len(all_matches) == 1 else f"_{idx}"
            sheets.append(
                {
                    "sheet_name_pattern": f"ファイル仕様書（{event_id}{suffix}）",
                    "header": sheet_header,
                    "items": items,
                }
            )
    return sheets

