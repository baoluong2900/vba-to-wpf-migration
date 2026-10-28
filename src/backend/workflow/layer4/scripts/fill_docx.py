"""
fill_docx.py
------------
Word (.docx) renditions of the BD (Basic Design) and DD (Detail Design) documents,
built from the same Layer 2 JSON the Excel fillers use:

- BD: ``sheet_2_layout`` (description / timing / constraints / process overview /
  record sources / events), ``sheet_3_screen_edit.items``, ``sheet_4_table_update``
  and ``sheet_5_file_spec`` blocks.
- DD: ``sheet_2_overview``, ``sheet_3_detail_specs`` or ``sheet_2_detail`` (``steps[]``),
  ``sheet_4_sel_query_templates`` / ``sheet_5_upd_query_templates`` (SQL from the
  structured ``sql`` object, or ``raw_sql``).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
except ImportError as e:
    raise ImportError("Missing python-docx package. Install it using: pip install python-docx") from e

from dd_common import compose_sel_query_sql_text  # noqa: E402
from fill_bd_excel import record_source_label  # noqa: E402

# Color palette (Modern Slate & Corporate Navy)
COLOR_PRIMARY = RGBColor(31, 78, 121)    # Deep Navy (#1F4E79)
COLOR_SECONDARY = RGBColor(143, 170, 188) # Slate Blue (#8FAADC)
COLOR_TEXT = RGBColor(51, 51, 51)        # Dark Gray/Charcoal (#333333)
COLOR_MUTED = RGBColor(128, 128, 128)    # Gray (#808080)

HEX_PRIMARY = "1F4E79"
HEX_LIGHT_BG = "F2F4F7"
HEX_BORDER = "D3D3D3"

class DocxGenerator:
    def __init__(self, title: str, subtitle: str, doc_version: str = "1.0"):
        self.doc = Document()
        self.title = title
        self.subtitle = subtitle
        self.doc_version = doc_version
        self._setup_page()
        self._set_default_styles()

    def _setup_page(self):
        for section in self.doc.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)
            # Add simple header & footer
            header = section.header
            hp = header.paragraphs[0]
            hp.text = f"{self.title} - {self.subtitle}"
            hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            hp.style.font.name = 'Arial'
            hp.style.font.size = Pt(8.5)
            hp.style.font.color.rgb = COLOR_MUTED

            footer = section.footer
            fp = footer.paragraphs[0]
            fp.text = "Confidential - For Internal Use Only"
            fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
            fp.style.font.name = 'Arial'
            fp.style.font.size = Pt(8.5)
            fp.style.font.color.rgb = COLOR_MUTED

    def _set_default_styles(self):
        style = self.doc.styles['Normal']
        font = style.font
        font.name = 'Arial'
        font.size = Pt(10.5)
        font.color.rgb = COLOR_TEXT

    def _set_cell_background(self, cell: Any, hex_color: str):
        shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading_elm)

    def _set_cell_margins(self, cell: Any, top: int = 120, bottom: int = 120, left: int = 150, right: int = 150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{m}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    def _set_table_borders(self, table: Any):
        tblPr = table._tbl.tblPr
        borders_xml = f"""
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>
            <w:bottom w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>
            <w:left w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>
            <w:right w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>
            <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>
            <w:insideV w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>
        </w:tblBorders>
        """
        borders_elm = parse_xml(borders_xml)
        tblPr.append(borders_elm)

    def add_cover_page(self):
        # Space
        for _ in range(3):
            self.doc.add_paragraph()

        # Title
        p_title = self.doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run_title = p_title.add_run(self.title)
        run_title.font.name = 'Arial'
        run_title.font.size = Pt(28)
        run_title.font.bold = True
        run_title.font.color.rgb = COLOR_PRIMARY

        # Accent Line
        p_line = self.doc.add_paragraph()
        p_line.paragraph_format.space_before = Pt(6)
        p_line.paragraph_format.space_after = Pt(18)
        run_line = p_line.add_run("―" * 38)
        run_line.font.size = Pt(14)
        run_line.font.bold = True
        run_line.font.color.rgb = COLOR_SECONDARY

        # Subtitle
        p_sub = self.doc.add_paragraph()
        run_sub = p_sub.add_run(self.subtitle)
        run_sub.font.size = Pt(16)
        run_sub.font.color.rgb = COLOR_TEXT

        for _ in range(8):
            self.doc.add_paragraph()

        # Metadata table block
        p_meta = self.doc.add_paragraph()
        p_meta.paragraph_format.line_spacing = 1.3
        
        run_meta = p_meta.add_run("DOCUMENT CONTROL\n")
        run_meta.font.bold = True
        run_meta.font.size = Pt(10)
        run_meta.font.color.rgb = COLOR_PRIMARY

        p_meta.add_run(f"Version: {self.doc_version}\n")
        p_meta.add_run(f"Date: {datetime.now().strftime('%B %d, %Y')}\n")
        p_meta.add_run("Author: VBA Brain Auto-Migration Suite\n")
        p_meta.add_run("Language: English (Converted from Japanese)\n")

        self.doc.add_page_break()

    def add_heading_1(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Arial'
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY

    def add_heading_2(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Arial'
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY

    def add_heading_3(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Arial'
        run.font.size = Pt(11.5)
        run.font.bold = True
        run.font.color.rgb = COLOR_TEXT

    def add_bullet(self, text: str, bold_prefix: str = ""):
        p = self.doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        if bold_prefix:
            run_bold = p.add_run(bold_prefix)
            run_bold.font.bold = True
        p.add_run(text)

    def add_text(self, text: str):
        """One paragraph per line (JSON text keeps its line breaks)."""
        for line in str(text).splitlines() or [""]:
            self.doc.add_paragraph(line)

    def add_code_block(self, text: str):
        """Monospace block for SQL."""
        p = self.doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.right_indent = Inches(0.2)
        lines = str(text).strip().splitlines()
        for i, line in enumerate(lines):
            run = p.add_run(line)
            run.font.name = 'Consolas'
            run.font.size = Pt(9.0)
            if i < len(lines) - 1:
                run.add_break()

    def add_table(self, headers: List[str], rows: List[List[str]], col_widths: List[float] = None) -> Any:
        table = self.doc.add_table(rows=len(rows) + 1, cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        self._set_table_borders(table)

        # Style header row
        hdr_cells = table.rows[0].cells
        for idx, text in enumerate(headers):
            hdr_cells[idx].text = text
            self._set_cell_background(hdr_cells[idx], HEX_PRIMARY)
            self._set_cell_margins(hdr_cells[idx], top=140, bottom=140)
            
            # Formatting text in header
            p = hdr_cells[idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.size = Pt(9.5)

        # Style body rows
        for r_idx, row_data in enumerate(rows):
            row_cells = table.rows[r_idx + 1].cells
            bg_color = HEX_LIGHT_BG if r_idx % 2 == 1 else "FFFFFF"
            for c_idx, val in enumerate(row_data):
                row_cells[c_idx].text = str(val or "")
                self._set_cell_background(row_cells[c_idx], bg_color)
                self._set_cell_margins(row_cells[c_idx], top=100, bottom=100)
                p = row_cells[c_idx].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in p.runs:
                    run.font.size = Pt(9.0)

        # Apply column widths if provided
        if col_widths:
            for row in table.rows:
                for idx, width in enumerate(col_widths):
                    if idx < len(row.cells):
                        row.cells[idx].width = Inches(width)

        p_after = self.doc.add_paragraph()
        p_after.paragraph_format.space_before = Pt(6)
        p_after.paragraph_format.space_after = Pt(6)
        return table

    def save(self, filepath: Path):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(filepath))


# ─────────────────────────────────────────────
# JSON helpers
# ─────────────────────────────────────────────
def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.upper() == "N/A" else s


def _dicts(value: Any) -> List[dict]:
    return [x for x in _as_list(value) if isinstance(x, dict)]


def _bd_blocks(raw: Any) -> List[dict]:
    """``sheet_4_table_update`` / ``sheet_5_file_spec``: one dict block, a list of
    ``{sheet_name_pattern, header, items}`` blocks, or a flat item list (by event_id)."""
    if isinstance(raw, dict):
        return [raw] if raw.get("items") or raw.get("header") else []
    blocks: List[dict] = []
    grouped: dict[str, List[dict]] = {}
    for x in _dicts(raw):
        if isinstance(x.get("items"), list):
            blocks.append(x)
        else:
            grouped.setdefault(_text(x.get("event_id")) or "E000", []).append(x)
    blocks += [{"sheet_name_pattern": eid, "header": {}, "items": its} for eid, its in grouped.items()]
    return blocks


def _dd_details(dd: dict) -> List[dict]:
    """Detail specs: ``sheet_3_detail_specs`` (form/report) or ``sheet_2_detail`` (module/macro)."""
    for key in ("sheet_3_detail_specs", "sheet_2_detail"):
        raw = dd.get(key)
        items = _dicts(raw.get("details") if isinstance(raw, dict) else raw)
        if items:
            return items
    items = _dicts(_as_dict(dd.get("sheet_2_overview")).get("details"))
    return items or _dicts(dd.get("details"))


def _dd_queries(dd: dict) -> List[dict]:
    """SELECT queries first, then UPDATE / INSERT queries (same shapes the Excel fillers read)."""
    out: List[dict] = []
    for key, list_key, single in (
        ("sheet_4_sel_query_templates", "sel_queries", "sel_query"),
        ("sheet_5_upd_query_templates", "upd_queries", "upd_query"),
    ):
        raw = dd.get(key)
        if isinstance(raw, dict):
            queries = raw.get(list_key) or ([raw[single]] if isinstance(raw.get(single), dict) else [])
            if not queries and single == "upd_query":
                queries = raw.get("ins_queries") or []
        else:
            queries = raw
        out += _dicts(queries)
    return out + _dicts(dd.get("queries") or dd.get("db_queries"))


def _query_sql_text(q: dict) -> str:
    if isinstance(q.get("sql"), str):          # legacy flat SQL string
        return q["sql"].strip()
    return compose_sel_query_sql_text(q) or _text(q.get("query_text"))


# ─────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────
def build_bd_docx(bd_data: dict, output_path: Path):
    """Build a Basic Design Word document from the Layer 2 BD JSON."""
    screen_id = _text(bd_data.get("screen_id") or bd_data.get("form_id") or bd_data.get("name")) or "BD_Document"
    screen_name = _text(bd_data.get("screen_name") or bd_data.get("form_name")) or screen_id

    gen = DocxGenerator(
        title="Basic Design Specification",
        subtitle=f"{screen_id} - {screen_name}"
    )
    gen.add_cover_page()

    layout = _as_dict(bd_data.get("sheet_2_layout"))
    legacy = _as_dict(bd_data.get("sheet_2_system_overview"))

    # Section 1: Overview
    gen.add_heading_1("1. Functional Overview")
    overview_text = (
        _text(layout.get("description"))
        or _text(legacy.get("system_overview"))
        or _text(bd_data.get("overview"))
        or _text(bd_data.get("system_overview"))
    )
    gen.add_text(overview_text or "No functional overview provided.")

    sub = 0
    constraints = layout.get("constraints") or legacy.get("constraints") or bd_data.get("constraints")
    for title, value in (("Timing", layout.get("timing")), ("Constraints", constraints)):
        if _text(value):
            sub += 1
            gen.add_heading_2(f"1.{sub}. {title}")
            gen.add_text(_text(value))

    process = [
        _text(p.get("summary_line") if isinstance(p, dict) else p)
        for p in _as_list(layout.get("process_overview"))
    ]
    process = [p for p in process if p]
    if process:
        sub += 1
        gen.add_heading_2(f"1.{sub}. Process Overview")
        for line in process:
            gen.add_bullet(line)

    sources = [_text(record_source_label(s)) for s in _as_list(layout.get("record_sources"))]
    sources = [s for s in sources if s]
    if sources:
        sub += 1
        gen.add_heading_2(f"1.{sub}. Record Sources")
        for name in sources:
            gen.add_bullet(name)

    # Section 2: Screen items
    gen.add_heading_1("2. Screen Items")
    items = _dicts(_as_dict(bd_data.get("sheet_3_screen_edit")).get("items"))
    if items:
        headers = ["No", "Item (Logical)", "Item (Physical)", "I/O", "Attribute", "Required", "Source", "Notes"]
        rows = []
        for it in items:
            attribute = _text(it.get("item_attribute") or it.get("control_type"))
            digits = _text(it.get("attribute_digits"))
            source = ".".join(
                x for x in (_text(it.get("source_table")), _text(it.get("source_field_or_fixed_value"))) if x
            )
            rows.append([
                _text(it.get("item_no") or it.get("no")),
                _text(it.get("logical_name") or it.get("item_name_logical")),
                _text(it.get("physical_name") or it.get("item_name_physical")),
                _text(it.get("io")),
                f"{attribute} ({digits})" if attribute and digits else attribute or digits,
                _text(it.get("required")),
                source,
                _text(it.get("notes") or it.get("other_input_checks")),
            ])
        gen.add_table(headers, rows, col_widths=[0.4, 1.0, 1.0, 0.4, 0.8, 0.5, 1.2, 1.2])
    else:
        gen.doc.add_paragraph("No screen items defined.")

    # Section 3: Events
    gen.add_heading_1("3. Events")
    events = _dicts(layout.get("events") or bd_data.get("events"))
    if events:
        headers = ["Event ID", "Control", "Type", "Trigger", "Processing", "Module ID"]
        rows = [[
            _text(ev.get("event_id")),
            _text(ev.get("physical_name") or ev.get("logical_name") or ev.get("title")),
            _text(ev.get("type")),
            _text(ev.get("event_trigger")),
            _text(ev.get("event_content") or ev.get("overview") or ev.get("description")),
            _text(ev.get("module_id")),
        ] for ev in events]
        gen.add_table(headers, rows, col_widths=[0.7, 1.2, 0.9, 1.0, 2.0, 0.7])
    else:
        gen.doc.add_paragraph("No events documented.")

    # Section 4: Table updates / file specifications
    blocks = _bd_blocks(bd_data.get("sheet_4_table_update")) + _bd_blocks(bd_data.get("sheet_5_file_spec"))
    if blocks:
        gen.add_heading_1("4. Table Updates and File Specifications")
        for i, block in enumerate(blocks, 1):
            header = _as_dict(block.get("header"))
            target = _text(header.get("table_physical_name") or header.get("file_name"))
            gen.add_heading_2(f"4.{i}. {_text(block.get('sheet_name_pattern')) or target or f'Block {i}'}")
            summary = " / ".join(x for x in (
                target,
                _text(header.get("table_logical_name") or header.get("file_type")),
                _text(header.get("update_type")),
            ) if x)
            if summary:
                gen.doc.add_paragraph(summary)
            rows = [[
                _text(it.get("no")),
                _text(it.get("physical_name") or it.get("target_field_physical") or it.get("output_field_name")),
                _text(it.get("logical_name") or it.get("target_field_logical") or it.get("output_field_logical")),
                _text(it.get("source_area") or it.get("source_table")),
                _text(it.get("source_field") or it.get("source_field_or_fixed_value")),
                _text(it.get("condition") or it.get("condition_and_format")),
                _text(it.get("remark") or it.get("notes")),
            ] for it in _dicts(block.get("items"))]
            if rows:
                gen.add_table(
                    ["No", "Field (Physical)", "Field (Logical)", "Source", "Source Field / Value", "Condition", "Notes"],
                    rows, col_widths=[0.4, 1.1, 1.1, 0.9, 1.1, 1.2, 0.8],
                )

    gen.save(output_path)
    print(f"[INFO] BD Word doc generated: {output_path}")


def build_dd_docx(dd_data: dict, output_path: Path):
    """Build a Detailed Design Word document from the Layer 2 DD JSON."""
    screen_id = _text(
        dd_data.get("screen_id") or dd_data.get("module_id") or dd_data.get("form_id") or dd_data.get("name")
    ) or "DD_Document"
    screen_name = _text(
        dd_data.get("screen_name") or dd_data.get("module_name") or dd_data.get("form_name")
    ) or screen_id

    gen = DocxGenerator(
        title="Detailed Design Specification",
        subtitle=f"{screen_id} - {screen_name}"
    )
    gen.add_cover_page()

    # Section 1: Overview
    overview = _as_dict(dd_data.get("sheet_2_overview"))
    gen.add_heading_1("1. Overview")
    overview_text = (
        _text(overview.get("description"))
        or _text(dd_data.get("overview"))
        or _text(dd_data.get("description"))
    )
    gen.add_text(overview_text or "No overview provided.")

    params = _dicts(overview.get("parameter_info"))
    if params:
        gen.add_heading_2("1.1. Parameters")
        gen.add_table(
            ["No", "I/O", "Item Name", "Symbol", "Type", "Digits", "Required", "Description"],
            [[
                _text(p.get("no")), _text(p.get("io")), _text(p.get("item_name")),
                _text(p.get("symbol_name")), _text(p.get("data_type")),
                ".".join(x for x in (_text(p.get("total_digits")), _text(p.get("decimal_digits"))) if x),
                _text(p.get("required")), _text(p.get("notes")),
            ] for p in params],
            col_widths=[0.4, 0.4, 1.2, 1.1, 0.7, 0.6, 0.6, 1.5],
        )
    if _text(overview.get("special_notes")):
        gen.add_heading_2("1.2. Special Notes" if params else "1.1. Special Notes")
        gen.add_text(_text(overview.get("special_notes")))

    # Section 2: Processing details (one entry per detail sheet)
    gen.add_heading_1("2. Processing Details")
    details = _dd_details(dd_data)
    if details:
        for i, detail in enumerate(details, 1):
            name = " ".join(x for x in (
                _text(detail.get("module_id")),
                _text(detail.get("module_name") or detail.get("procedure_name") or detail.get("name")),
            ) if x) or f"Module {i}"
            gen.add_heading_2(f"2.{i}. {name}")
            for label, key in (("Trigger", "event_trigger"), ("Processing", "event_content")):
                if _text(detail.get(key)):
                    gen.add_bullet(_text(detail.get(key)), bold_prefix=f"{label}: ")
            desc = _text(detail.get("overview") or detail.get("description"))
            if desc:
                gen.add_text(desc)

            steps = _as_list(detail.get("steps") or detail.get("processing_steps") or detail.get("logic_steps"))
            for s_idx, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    title = _text(step.get("step")) or f"Step {s_idx}"
                    body = _text(step.get("detail") or step.get("description") or step.get("text"))
                else:
                    title, body = f"Step {s_idx}", _text(step)
                gen.add_heading_3(title)
                if body:
                    gen.add_text(body)

            vars_list = _dicts(detail.get("local_variables") or detail.get("variables"))
            if vars_list:
                gen.add_heading_3("Local Variables:")
                gen.add_table(
                    ["Variable Name", "Data Type", "Scope / Description"],
                    [[_text(v.get("name")), _text(v.get("type")), _text(v.get("description"))] for v in vars_list],
                    col_widths=[2.0, 1.5, 3.5],
                )
    else:
        gen.doc.add_paragraph("No processing details defined.")

    # Section 3: Queries
    gen.add_heading_1("3. Queries")
    queries = _dd_queries(dd_data)
    if queries:
        for i, q in enumerate(queries, 1):
            title = _text(
                q.get("sheet_name") or q.get("sheet_name_pattern") or q.get("query_name") or q.get("name")
            ) or f"Query {i}"
            gen.add_heading_2(f"3.{i}. {title}")
            purpose = _text(q.get("query_purpose") or q.get("description") or q.get("overview"))
            if purpose:
                gen.add_text(purpose)
            query_name = _text(q.get("query_name"))
            if query_name and query_name != title:
                gen.add_bullet(query_name, bold_prefix="Query: ")
            params = q.get("parameters")
            if isinstance(params, list):
                params = ", ".join(
                    _text(p.get("name") if isinstance(p, dict) else p) for p in params
                    if _text(p.get("name") if isinstance(p, dict) else p)
                )
            if _text(params):
                gen.add_bullet(_text(params), bold_prefix="Parameters: ")
            sql_text = _query_sql_text(q)
            if sql_text:
                gen.add_code_block(sql_text)
            columns = _dicts(q.get("columns"))
            if columns:
                keys = [k for k in ("no", "table_name", "column_name", "display_name",
                                    "source_area", "source_field", "remark")
                        if any(_text(c.get(k)) for c in columns)]
                if keys:
                    gen.add_table(
                        [k.replace("_", " ").title() for k in keys],
                        [[_text(c.get(k)) for k in keys] for c in columns],
                    )
    else:
        gen.doc.add_paragraph("No queries referenced in this module.")

    gen.save(output_path)
    print(f"[INFO] DD Word doc generated: {output_path}")
