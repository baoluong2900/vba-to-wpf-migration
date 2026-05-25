"""
fill_docx.py
------------
Generate beautifully designed English Word specifications (.docx) for BD (Basic Design) and DD (Detail Design) 
from their respective JSON data.
"""
from __future__ import annotations
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
except ImportError:
    raise ImportError("Missing python-docx package. Install it using: pip install python-docx")

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


def build_bd_docx(bd_data: dict, output_path: Path):
    """Build a Basic Design Word document from BD JSON."""
    screen_id = bd_data.get("screen_id") or bd_data.get("form_id") or "BD_Document"
    screen_name = bd_data.get("screen_name") or bd_data.get("form_name") or "Unnamed Screen"
    
    # Quick cleanup and english headers
    gen = DocxGenerator(
        title=f"Basic Design Specification",
        subtitle=f"{screen_id} - {screen_name}"
    )
    gen.add_cover_page()

    # Section 1: Overview
    gen.add_heading_1("1. Functional Overview")
    
    overview_data = bd_data.get("sheet_2_system_overview", {}) or {}
    overview_text = overview_data.get("system_overview") or bd_data.get("system_overview") or ""
    constraints_text = overview_data.get("constraints") or bd_data.get("constraints") or ""

    if overview_text:
        gen.doc.add_paragraph(overview_text)
    else:
        gen.doc.add_paragraph("No system overview provided.")

    if constraints_text:
        gen.add_heading_2("1.1. Constraints and Validation Rules")
        gen.doc.add_paragraph(constraints_text)

    # Section 2: Screen Items and Controls
    gen.add_heading_1("2. Screen Items and Layout Specifications")
    
    edit_data = bd_data.get("sheet_3_screen_edit", {}) or {}
    items = edit_data.get("items", []) or []
    
    if items:
        headers = ["No", "Item Name (Logical)", "Item Name (Physical)", "Control Type", "Caption / Label", "Transitions / Events"]
        rows = []
        for it in items:
            item_no = it.get("item_no") or it.get("no") or ""
            logical_name = it.get("item_name_logical") or it.get("logical_name") or ""
            physical_name = it.get("item_name_physical") or it.get("physical_name") or ""
            control_type = it.get("item_attribute") or it.get("control_type") or ""
            caption = it.get("caption") or ""
            
            # Events
            event_method = it.get("event_method_editing_method") or it.get("transition_destination") or ""
            rows.append([
                str(item_no),
                str(logical_name),
                str(physical_name),
                str(control_type),
                str(caption),
                str(event_method)
            ])
        gen.add_table(headers, rows, col_widths=[0.6, 1.4, 1.4, 1.0, 1.2, 2.0])
    else:
        gen.doc.add_paragraph("No screen control items defined.")

    # Section 3: Event Handlers and Transitions
    gen.add_heading_1("3. Screen Event Flows & Logic")
    events = bd_data.get("sheet_4_table_update", {}) or {}
    # S4 BD often has sheets under "events" or events list
    # Let's check for any event handlers
    event_list = bd_data.get("events") or []
    if not event_list and isinstance(events, dict):
        event_list = events.get("events") or []

    if event_list:
        for ev in event_list:
            ev_id = ev.get("event_id") or ""
            ev_name = ev.get("event_name") or ""
            ev_desc = ev.get("overview") or ev.get("description") or ""
            gen.add_heading_2(f"Event: {ev_id} - {ev_name}")
            if ev_desc:
                gen.doc.add_paragraph(ev_desc)
            
            # Table updates
            table_updates = ev.get("table_updates") or []
            if table_updates:
                gen.add_heading_3("Table Updates:")
                tbl_headers = ["Table Name", "Update Mode", "Conditions / Methods"]
                tbl_rows = [[t.get("table_name", ""), t.get("mode", ""), t.get("description", "")] for t in table_updates]
                gen.add_table(tbl_headers, tbl_rows, col_widths=[2.0, 1.5, 3.5])
    else:
        gen.doc.add_paragraph("No explicit event logic documented.")

    gen.save(output_path)
    print(f"[INFO] BD Word doc generated: {output_path}")


def build_dd_docx(dd_data: dict, output_path: Path):
    """Build a Detailed Design Word document from DD JSON."""
    screen_id = dd_data.get("module_id") or dd_data.get("screen_id") or dd_data.get("form_id") or "DD_Document"
    screen_name = dd_data.get("module_name") or dd_data.get("screen_name") or dd_data.get("form_name") or "Unnamed Module"
    
    gen = DocxGenerator(
        title=f"Detailed Design Specification",
        subtitle=f"{screen_id} - {screen_name}"
    )
    gen.add_cover_page()

    # Section 1: Overview
    gen.add_heading_1("1. Overview & System Scope")
    overview_text = dd_data.get("overview") or dd_data.get("description") or ""
    if overview_text:
        gen.doc.add_paragraph(overview_text)
    else:
        gen.doc.add_paragraph("No detailed overview available.")

    # Section 2: Detailed Specs / Procedures
    gen.add_heading_1("2. Program Procedures & Logic Processing")
    
    details = dd_data.get("details", []) or []
    if details:
        for detail in details:
            proc_name = detail.get("procedure_name") or detail.get("name") or "Unnamed Procedure"
            proc_type = detail.get("type") or "Sub"
            proc_desc = detail.get("overview") or detail.get("description") or ""
            
            gen.add_heading_2(f"2.N. Procedure: {proc_name} ({proc_type})")
            if proc_desc:
                gen.doc.add_paragraph(proc_desc)

            # Processing steps
            steps = detail.get("processing_steps") or detail.get("logic_steps") or []
            if steps:
                gen.add_heading_3("Processing Logic:")
                for s_idx, step in enumerate(steps):
                    step_text = step.get("description") or step.get("text") or str(step)
                    gen.add_bullet(step_text, bold_prefix=f"Step {s_idx + 1}: ")

            # Variables
            vars_list = detail.get("local_variables") or detail.get("variables") or []
            if vars_list:
                gen.add_heading_3("Local Variables:")
                var_headers = ["Variable Name", "Data Type", "Scope / Description"]
                var_rows = [[v.get("name", ""), v.get("type", ""), v.get("description", "")] for v in vars_list]
                gen.add_table(var_headers, var_rows, col_widths=[2.0, 1.5, 3.5])
    else:
        gen.doc.add_paragraph("No procedures defined in this detailed specification.")

    # Section 3: SQL Queries
    gen.add_heading_1("3. Database Queries Details")
    queries = dd_data.get("queries") or dd_data.get("db_queries") or []
    if queries:
        for q in queries:
            q_name = q.get("query_name") or q.get("name") or "Unnamed Query"
            q_sql = q.get("sql") or q.get("query_text") or ""
            q_desc = q.get("description") or q.get("overview") or ""
            
            gen.add_heading_2(f"Query: {q_name}")
            if q_desc:
                gen.doc.add_paragraph(q_desc)
                
            if q_sql:
                # Add SQL block format
                p_sql = gen.doc.add_paragraph()
                p_sql.paragraph_format.left_indent = Inches(0.2)
                p_sql.paragraph_format.right_indent = Inches(0.2)
                run_sql = p_sql.add_run(q_sql.strip())
                run_sql.font.name = 'Consolas'
                run_sql.font.size = Pt(9.0)
                gen._set_cell_background(p_sql, HEX_LIGHT_BG) # Using custom shading for paragraphs is complex, normal block is fine.
                
            params = q.get("parameters") or []
            if params:
                gen.add_heading_3("Query Parameters:")
                param_headers = ["Parameter Name", "Type", "Source Value"]
                param_rows = [[p.get("name", ""), p.get("type", ""), p.get("source", "")] for p in params]
                gen.add_table(param_headers, param_rows, col_widths=[2.0, 1.5, 3.5])
    else:
        gen.doc.add_paragraph("No SQL queries referenced in this module.")

    gen.save(output_path)
    print(f"[INFO] DD Word doc generated: {output_path}")
