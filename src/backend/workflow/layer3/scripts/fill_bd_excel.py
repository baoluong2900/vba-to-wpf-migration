"""
fill_bd_excel.py
----------------
Fill BD (Basic Design) docs JSON into the Excel screen specification template.

Project template (this repo):
    02_tools/template/BD_Screen/bd_template.xlsx

Default batch I/O (when run without --input):
    input : 02_tools/inputs/BD_json/screen/*.json
    output: 02_tools/outputs/BD_Output/screen/*.xlsx

Cell layout is the same family as the original FD010M-derived file:
    APP 148-03_画面仕様書_FD010M_出荷実績入力_1.2.xlsx

Supported sheets inside the template:
    - 変更履歴                    (Change History)
    - 画面仕様書(レイアウト)       (Screen Specification — Layout)
    - 画面仕様書(画面編集)         (Screen Specification — Edit)
    - 画面仕様書（E***）           (per-event Table Update)
    - ファイル仕様書（E***）       (per-event File Spec — same cell layout as E***)

The cell-mapping was derived from inspecting:
    APP 148-03_画面仕様書_FD010M_出荷実績入力_1.2.xlsx
(see 03_agents/workflow/backend/inspect_excel_template.py in this repo).

Usage (from 02_tools):

    # Batch with defaults (screen JSON → screen Excel, BD_Screen template)
    python -X utf8 scripts/fill_bd_excel.py

    cd 02_tools
    python -X utf8 scripts/fill_bd_excel.py ^
        --input    "inputs/BD_json/screen/F_Login.json" ^
        --output   "outputs/BD_Output/screen/F_Login.xlsx"

    # Optional: disable built-in 変更履歴 mock rows
    python -X utf8 scripts/fill_bd_excel.py ... --no-mock-change-history

    # Batch: override dirs only
    python -X utf8 scripts/fill_bd_excel.py `
        --input-dir  "inputs/BD_json/screen" `
        --output-dir "outputs/BD_Output/screen"
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Iterable

try:
    from openpyxl import load_workbook
    from openpyxl.cell.cell import MergedCell
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.worksheet import Worksheet
except ImportError as e:
    raise SystemExit("[ERR] Missing dependency. Run: pip install openpyxl") from e

from layer3_output_settings import get_bd_screen_output_filename_prefix  # noqa: E402


# Repo root for this tool = 02_tools (parent of scripts/)
_TOOLS_ROOT = Path(__file__).resolve().parent.parent

# Default BD screen template and batch folders (under 02_tools)
DEFAULT_BD_TEMPLATE = _TOOLS_ROOT / "template" / "BD_Screen" / "bd_template.xlsx"
DEFAULT_INPUT_DIR  = _TOOLS_ROOT / "inputs" / "BD_json" / "screen"
DEFAULT_OUTPUT_DIR = _TOOLS_ROOT / "outputs" / "BD_Output" / "screen"

# Default search dir for per-screen design images (relative to 02_tools)
DEFAULT_IMAGE_DIR = _TOOLS_ROOT / "Access_DesignView" / "Form"
IMAGE_EXTS = (".png", ".jpg", ".jpeg")

# Excel COM constants (late-binding friendly).
_MsoShapeOval = 9
_MsoShapeRoundedRectangle = 5
_MsoPictureTypes = {11, 13}  # linked picture / picture

from openpyxl.styles import Font
EXCEL_DOCUMENT_FONT_NAME = "Arial"
EXCEL_DETAIL_QUERY_EMBED_TABLE_FONT_SZ = 9

def apply_excel_document_font(cell, name=EXCEL_DOCUMENT_FONT_NAME, size=None, bold=None, italic=None, color=None):
    if not cell:
        return
    current_font = cell.font
    if current_font:
        new_name = name if name is not None else current_font.name
        new_size = size if size is not None else current_font.size
        new_bold = bold if bold is not None else current_font.bold
        new_italic = italic if italic is not None else current_font.italic
        new_color = color if color is not None else current_font.color
    else:
        new_name = name
        new_size = size
        new_bold = bold
        new_italic = italic
        new_color = color
        
    cell.font = Font(name=new_name, size=new_size, bold=new_bold, italic=new_italic, color=new_color)


def _resolve_screen_image(value: str | None,
                          screen_id: str | None,
                          search_dirs: list[Path]) -> Path | None:
    """Resolve a screen image file from JSON hints and fallback dirs.

    Priority:
      1. `value` as an existing file path (absolute or relative to CWD).
      2. `value` (bare name, with or without extension) inside each search_dir.
      3. `screen_id` + common image extensions inside each search_dir.
    Returns None if nothing matches.
    """
    if value:
        p = Path(value)
        if p.is_file():
            return p
        stem = Path(value).stem
        suffix = Path(value).suffix.lower()
        for d in search_dirs:
            if not d.is_dir():
                continue
            if suffix:
                cand = d / value
                if cand.is_file():
                    return cand
            else:
                for ext in IMAGE_EXTS:
                    cand = d / f"{stem}{ext}"
                    if cand.is_file():
                        return cand

    if screen_id:
        for d in search_dirs:
            if not d.is_dir():
                continue
            for ext in IMAGE_EXTS:
                cand = d / f"{screen_id}{ext}"
                if cand.is_file():
                    return cand
    return None


def replace_layout_screen_image(ws: Worksheet, image_path: Path,
                                default_coord: str = "A9") -> None:
    """Replace the first embedded image on the Layout sheet with `image_path`,
    preserving the existing anchor (size+position). If there's no existing
    image, anchor the new one at `default_coord`."""
    old_anchor = None
    if getattr(ws, "_images", None):
        old_anchor = copy.copy(ws._images[0].anchor)
        ws._images = []
    new_img = XLImage(str(image_path))
    new_img.anchor = old_anchor if old_anchor is not None else default_coord
    ws.add_image(new_img)


def _collect_layout_shape_labels(bd: dict) -> list[str]:
    """Collect labels for layout shapes from BD JSON (dedup, keep order)."""
    out: list[str] = []
    seen: set[str] = set()

    edit = bd.get("sheet_3_screen_edit") or {}
    items = edit.get("items") if isinstance(edit, dict) else []
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            raw = it.get("item_no")
            if raw in (None, ""):
                continue
            label = str(raw).strip()
            if not label or label in seen:
                continue
            seen.add(label)
            out.append(label)

    return out


def _is_circle_item_no(label: str) -> bool:
    s = str(label or "").strip().upper()
    if not s:
        return False
    if s.isdigit():
        return True
    return s in {"I", "II", "III"}


def _draw_layout_shapes_via_excel_com(
    output_path: Path,
    *,
    template_path: Path | None = None,
    sheet_name: str,
    labels: list[str],
) -> None:
    """Duplicate template shapes (circle/rectangle) around layout image via COM."""
    if not labels:
        return
    try:
        import win32com.client  # type: ignore[import-not-found]
    except Exception:
        print("[WARN] pywin32 is unavailable; skip layout shape drawing.")
        return

    app = None
    wb = None
    wb_tpl = None
    try:
        app = win32com.client.Dispatch("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False
        wb = app.Workbooks.Open(str(output_path.resolve()))
        ws = wb.Worksheets(sheet_name)

        # Remove previously generated shapes (if rerun on same file).
        for i in range(ws.Shapes.Count, 0, -1):
            shp = ws.Shapes(i)
            try:
                if str(shp.Name).startswith("BD_AUTO_ITEM_"):
                    shp.Delete()
            except Exception:
                pass

        # Locate shape prototypes already prepared in template.
        # Prefer explicit name hints, then text content, then AutoShapeType.
        proto_circle = None
        proto_rect = None
        for i in range(1, ws.Shapes.Count + 1):
            shp = ws.Shapes(i)
            try:
                if int(shp.Type) == _MsoPictureTypes:
                    continue
            except Exception:
                pass
            name = str(getattr(shp, "Name", "") or "").lower()
            if proto_circle is None and ("circle" in name or "oval" in name or "round" in name):
                proto_circle = shp
            if proto_rect is None and ("rect" in name or "box" in name or "event" in name):
                proto_rect = shp

        # Fallback by shape text (works for user-provided sample labels like "I", "E001").
        best_circle_area = -1.0
        best_rect_area = -1.0
        for i in range(1, ws.Shapes.Count + 1):
            shp = ws.Shapes(i)
            try:
                if int(shp.Type) in _MsoPictureTypes:
                    continue
            except Exception:
                continue
            txt = ""
            try:
                txt = str(shp.TextFrame2.TextRange.Text or "").strip()
            except Exception:
                try:
                    txt = str(shp.TextFrame.Characters().Text or "").strip()
                except Exception:
                    txt = ""
            if not txt:
                continue
            area = float(shp.Width) * float(shp.Height)
            if _is_circle_item_no(txt):
                if area > best_circle_area:
                    best_circle_area = area
                    proto_circle = shp
            else:
                if area > best_rect_area:
                    best_rect_area = area
                    proto_rect = shp

        for i in range(1, ws.Shapes.Count + 1):
            shp = ws.Shapes(i)
            try:
                typ = int(getattr(shp, "AutoShapeType", 0))
            except Exception:
                continue
            if proto_circle is None and typ == _MsoShapeOval:
                proto_circle = shp
            if proto_rect is None and typ in (_MsoShapeRoundedRectangle,):
                proto_rect = shp
            if proto_circle is not None and proto_rect is not None:
                break

        # Final fallback: if rounded-rectangle missing, use any non-oval autoshape.
        if proto_rect is None:
            for i in range(1, ws.Shapes.Count + 1):
                shp = ws.Shapes(i)
                try:
                    typ = int(getattr(shp, "AutoShapeType", 0))
                    if typ and typ != _MsoShapeOval:
                        proto_rect = shp
                        break
                except Exception:
                    continue

        if (proto_circle is None or proto_rect is None) and template_path is not None and Path(template_path).is_file():
            try:
                wb_tpl = app.Workbooks.Open(str(Path(template_path).resolve()))
                ws_tpl = wb_tpl.Worksheets(sheet_name)

                t_circle = None
                t_rect = None
                for i in range(1, ws_tpl.Shapes.Count + 1):
                    shp = ws_tpl.Shapes(i)
                    try:
                        if int(shp.Type) in _MsoPictureTypes:
                            continue
                    except Exception:
                        continue
                    txt = ""
                    try:
                        txt = str(shp.TextFrame2.TextRange.Text or "").strip()
                    except Exception:
                        try:
                            txt = str(shp.TextFrame.Characters().Text or "").strip()
                        except Exception:
                            txt = ""
                    if txt:
                        if t_circle is None and _is_circle_item_no(txt):
                            t_circle = shp
                        if t_rect is None and not _is_circle_item_no(txt):
                            t_rect = shp
                    if t_circle is not None and t_rect is not None:
                        break

                if proto_circle is None and t_circle is not None:
                    t_circle.Copy()
                    ws.Paste()
                    proto_circle = ws.Shapes(ws.Shapes.Count)
                if proto_rect is None and t_rect is not None:
                    t_rect.Copy()
                    ws.Paste()
                    proto_rect = ws.Shapes(ws.Shapes.Count)
            except Exception:
                pass

        if proto_circle is None or proto_rect is None:
            print("[WARN] Template circle/rectangle shapes not found on sheet 2; skip drawing.")
            wb.Save()
            return

        pic = None
        max_area = -1.0
        for i in range(1, ws.Shapes.Count + 1):
            shp = ws.Shapes(i)
            if int(shp.Type) not in _MsoPictureTypes:
                continue
            area = float(shp.Width) * float(shp.Height)
            if area > max_area:
                max_area = area
                pic = shp

        if pic is None:
            left = float(ws.Range("B8").Left)
            top = float(ws.Range("B8").Top)
            width = 360.0
            height = 260.0
        else:
            left = float(pic.Left)
            top = float(pic.Top)
            width = float(pic.Width)
            height = float(pic.Height)

        gap = 8.0
        top0 = top + 6.0
        slots = max(1, int(max(100.0, height - 12.0) // (30.0 + 6.0)))
        sheet_left = float(ws.Range("A1").Left)
        sheet_right = float(ws.Range("BC1").Left + ws.Range("BC1").Width)

        for idx, label in enumerate(labels):
            is_circle = _is_circle_item_no(label)
            proto = proto_circle if is_circle else proto_rect
            w = float(proto.Width)
            h = float(proto.Height)
            # Keep template style by duplication, but enforce visible minimum size.
            if is_circle:
                w = max(w, 28.0)
                h = max(h, 28.0)
            else:
                w = max(w, 56.0)
                h = max(h, 22.0)

            block = idx // (slots * 2)
            pos = idx % (slots * 2)
            on_left = pos < slots
            row_idx = pos % slots
            # Keep generated labels around the image and inside visible sheet area.
            # Additional blocks move inward toward the image (not further outside).
            x_left = left - gap - w + block * (w + gap)
            x_right = left + width + gap - block * (w + gap)
            x = x_left if on_left else x_right
            x = max(sheet_left + 2.0, min(x, sheet_right - w - 2.0))
            y = top0 + row_idx * (h + 6.0)

            dup = proto.Duplicate()
            try:
                shp = dup.Item(1)
            except Exception:
                shp = dup
            shp.Name = f"BD_AUTO_ITEM_{idx+1:04d}"
            shp.Left = x
            shp.Top = y
            shp.Width = w
            shp.Height = h
            shp.Visible = True
            try:
                shp.ZOrder(0)  # bring to front
            except Exception:
                pass
            shp.TextFrame2.TextRange.Text = str(label)
            shp.TextFrame2.TextRange.Font.Size = 9
            shp.TextFrame2.VerticalAnchor = 3  # middle
            shp.TextFrame2.TextRange.ParagraphFormat.Alignment = 2  # center

        wb.Save()
    except Exception as e:
        print(f"[WARN] Failed to draw layout shapes via Excel COM: {e}")
    finally:
        if wb_tpl is not None:
            try:
                wb_tpl.Close(SaveChanges=False)
            except Exception:
                pass
        if wb is not None:
            try:
                wb.Close(SaveChanges=True)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass


# ─────────────────────────────────────────────
# Sheet name constants
# ─────────────────────────────────────────────
SHEET_CHANGE_HISTORY = "変更履歴"
SHEET_LAYOUT         = "画面仕様書(レイアウト)"
SHEET_EDIT           = "画面仕様書(画面編集)"
SHEET_EVENT_PREFIX     = "画面仕様書（"   # + "E***）"
SHEET_FILE_SPEC_PREFIX = "ファイル仕様書（"  # + "E***）"


# ─────────────────────────────────────────────
# Cell helpers (merge-aware)
# ─────────────────────────────────────────────
def set_cell(ws: Worksheet, coord: str, value: Any) -> None:
    """Write a value to a cell. If the cell is part of a merged range,
    write to the top-left cell of the merge (the only writable one)."""
    cell = ws[coord]
    if isinstance(cell, MergedCell):
        for rng in ws.merged_cells.ranges:
            if coord in rng:
                ws.cell(rng.min_row, rng.min_col).value = value
                return
        # Fallback: merged but no range matched (shouldn't happen).
        return
    cell.value = value


def clear_cells(ws: Worksheet, coords: Iterable[str]) -> None:
    for c in coords:
        set_cell(ws, c, None)


def clear_block(ws: Worksheet, row_start: int, row_end: int,
                cols: Iterable[str]) -> None:
    for r in range(row_start, row_end + 1):
        for c in cols:
            set_cell(ws, f"{c}{r}", None)


def _norm(v: Any) -> str:
    """Convert a JSON value to a cell-friendly string.
    Treat 'N/A' / None as empty string."""
    if v is None:
        return ""
    s = str(v).strip()
    if s.upper() == "N/A":
        return ""
    return s


def put(ws: Worksheet, coord: str, value: Any) -> None:
    """Write normalised value (N/A → '') to a cell.

    Strings that start with ``=`` are interpreted by Excel as worksheet
    formulas.  BD JSON often contains **Access** expressions (e.g.
    ``=DLookUp(...)``) which are **not** valid Excel formulas — on open Excel
    removes them and logs *Removed Records: Formula*.  Prefix with a single
    ASCII apostrophe so the cell is stored as **plain text** (Excel hides the
    leading ``'`` in the UI).
    """
    s = _norm(value)
    if s.startswith("=") and not s.startswith("'"):
        s = "'" + s
    set_cell(ws, coord, s)


def template_span(ws: Worksheet, template_row: int) -> int:
    """How many physical rows the logical template row occupies, based on the
    longest vertical merge that starts at `template_row` (e.g. merge 23:24 → 2).
    """
    span = 1
    for rng in ws.merged_cells.ranges:
        if rng.min_row == template_row:
            s = rng.max_row - rng.min_row + 1
            if s > span:
                span = s
    return span


def duplicate_block(ws: Worksheet, src_row: int, dst_row: int,
                    span: int = 1) -> None:
    """Clone `span` rows of style, row height and merged ranges from
    [src_row, src_row+span-1] to [dst_row, dst_row+span-1].

    Does NOT copy cell values (callers will write their own).
    """
    for off in range(span):
        sd = ws.row_dimensions.get(src_row + off)
        if sd is not None and sd.height is not None:
            ws.row_dimensions[dst_row + off].height = sd.height

    max_col = ws.max_column or 1
    for off in range(span):
        for c in range(1, max_col + 1):
            src = ws.cell(src_row + off, c)
            dst = ws.cell(dst_row + off, c)
            if src.has_style:
                dst._style = copy.copy(src._style)

    shift = dst_row - src_row
    dst_min = dst_row
    dst_max = dst_row + span - 1

    to_merge: list[tuple[int, int, int, int]] = []
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row >= src_row and rng.max_row <= src_row + span - 1:
            to_merge.append((
                rng.min_row + shift, rng.min_col,
                rng.max_row + shift, rng.max_col,
            ))

    # Unmerge ANY existing merged range that intersects the destination
    # block. Otherwise we'd be stacking a new merge on top of a pre-existing
    # one (from the original template) - Excel rejects that on open with
    # "Removed Records: Merge cells from /xl/worksheets/sheetN.xml part".
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row > dst_max or rng.max_row < dst_min:
            continue
        try:
            ws.unmerge_cells(str(rng))
        except (KeyError, ValueError):
            pass

    for r1, c1, r2, c2 in to_merge:
        try:
            ws.merge_cells(start_row=r1, start_column=c1,
                           end_row=r2,   end_column=c2)
        except ValueError:
            pass


def expand_table(ws: Worksheet, template_row: int, n_items: int) -> list[int]:
    """Return `n_items` top-left row numbers for a template-based table.

    Logic:
    - Compute the template row's logical span (via vertical merges).
    - Item 0 uses `template_row`.
    - Item i uses `template_row + i * span`, with the template row cloned
      (style + merges + height).
    Assumes the template row is the LAST meaningful row in that table area.
    """
    if n_items <= 0:
        return []
    span = template_span(ws, template_row)
    rows = [template_row]
    for i in range(1, n_items):
        dst = template_row + i * span
        duplicate_block(ws, template_row, dst, span=span)
        rows.append(dst)
    return rows


def clear_row_cells(ws: Worksheet, row: int, cols: Iterable[str]) -> None:
    """Clear values at (row, col) for each col, merge-aware."""
    for c in cols:
        set_cell(ws, f"{c}{row}", None)


def purge_stale_data_rows(ws: Worksheet, template_row: int,
                           cols: Iterable[str], max_scan: int = 50) -> None:
    """Clear *leftover data* from previous template content located BELOW
    `template_row`, scanning up to `max_scan` rows.

    Useful when the supplied template still contains example rows from another
    screen (e.g. FD010M sample queries in the record-sources column).
    Stops as soon as it sees a row where every target column is empty AND the
    row is not part of any merged range originating there.
    """
    span = template_span(ws, template_row)
    r = template_row + span
    stop_streak = 0
    while r <= template_row + max_scan:
        had_value = False
        for c in cols:
            cell = ws.cell(r, _col_to_index(c))
            if cell.value not in (None, ""):
                had_value = True
                break
        if had_value:
            clear_row_cells(ws, r, cols)
            stop_streak = 0
        else:
            stop_streak += 1
            if stop_streak >= 2:
                break
        r += 1


def _col_to_index(col: str) -> int:
    """Convert 'A', 'B', ..., 'AA' to 1-based column index."""
    n = 0
    for ch in col.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def _display_units(text: str) -> int:
    total = 0
    for ch in text:
        total += 2 if unicodedata.east_asian_width(ch) in ("F", "W", "A") else 1
    return total


def _set_wrap_text(ws: Worksheet, row: int, col: str) -> None:
    cell = ws.cell(row, _col_to_index(col))
    al = copy.copy(cell.alignment)
    al.wrap_text = True
    if not al.vertical:
        al.vertical = "top"
    cell.alignment = al


def _auto_fit_event_row_height(ws: Worksheet, row: int, item: dict[str, Any]) -> None:
    """Auto-grow event row height from text length; does not change column widths."""
    # Conservative per-cell capacities (display units) for merged columns in EVENT_COL.
    caps: dict[str, int] = {
        "physical_name": 28,   # C:K
        "logical_name": 28,    # L:T
        "source_area": 24,     # U:AB
        "source_field": 24,    # AC:AJ
        "condition": 24,       # AK:AR
        "remark": 30,          # AU:BC
    }
    anchors: dict[str, str] = {
        "physical_name": "C",
        "logical_name": "L",
        "source_area": "U",
        "source_field": "AC",
        "condition": "AK",
        "remark": "AU",
    }
    visual_lines = 1
    for key, cap in caps.items():
        v = item.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        _set_wrap_text(ws, row, anchors[key])
        lines = max(1, math.ceil(_display_units(s) / max(1, cap)))
        visual_lines = max(visual_lines, lines)

    base_h = ws.row_dimensions[row].height or 14.25
    ws.row_dimensions[row].height = max(base_h, 14.25 * visual_lines)


# ─────────────────────────────────────────────
# Template-row auto-locator (robust to inserted/removed rows)
# ─────────────────────────────────────────────
def _cell_value_merge_aware(ws: Worksheet, row: int, col_idx: int) -> Any:
    """Return the value at (row, col) even if the cell is part of a merge
    (merges store the value only on the top-left cell)."""
    cell = ws.cell(row, col_idx)
    if cell.value is not None:
        return cell.value
    if isinstance(cell, MergedCell):
        for rng in ws.merged_cells.ranges:
            if (rng.min_row <= row <= rng.max_row
                    and rng.min_col <= col_idx <= rng.max_col):
                return ws.cell(rng.min_row, rng.min_col).value
    return None


def _merge_bounds(ws: Worksheet, row: int, col: int) -> tuple[int, int, int, int]:
    """Return (min_row, min_col, max_row, max_col) for the merge containing (row, col)."""
    for rng in ws.merged_cells.ranges:
        if rng.min_row <= row <= rng.max_row and rng.min_col <= col <= rng.max_col:
            return rng.min_row, rng.min_col, rng.max_row, rng.max_col
    return row, col, row, col


def _master_cell(ws: Worksheet, row: int, col: int):
    """Top-left writable cell when (row, col) is inside a merged range."""
    cell = ws.cell(row, col)
    if isinstance(cell, MergedCell):
        for rng in ws.merged_cells.ranges:
            if rng.min_row <= row <= rng.max_row and rng.min_col <= col <= rng.max_col:
                return ws.cell(rng.min_row, rng.min_col)
    return cell


def put_value_right_of_label(
    ws: Worksheet,
    label: str,
    value: Any,
    *,
    row_start: int = 1,
    row_end: int = 6,
    col_start: int = 1,
    col_end: int = 45,
) -> bool:
    """Find a cell whose trimmed text equals ``label``; write ``value`` to the
    first column immediately to the right of that label's merged block (same row
    as the merge top). Returns True if a label was found and written."""
    needle = (label or "").strip()
    if not needle:
        return False
    s = _norm(value)
    if s.startswith("=") and not s.startswith("'"):
        s = "'" + s
    white = PatternFill(fill_type="solid", fgColor="FFFFFF")
    for r in range(row_start, row_end + 1):
        for c in range(col_start, col_end + 1):
            v = _cell_value_merge_aware(ws, r, c)
            if v is None:
                continue
            if str(v).strip() != needle:
                continue
            mr1, _mc1, _mr2, mc2 = _merge_bounds(ws, r, c)
            tgt_row = mr1
            tgt_col = mc2 + 1
            if tgt_col > col_end:
                return False
            coord = f"{get_column_letter(tgt_col)}{tgt_row}"
            set_cell(ws, coord, s)
            mc = _master_cell(ws, tgt_row, tgt_col)
            mc.fill = white
            return True
    return False


def fill_branded_header_fields_by_label(ws: Worksheet, author: str = None) -> None:
    """Fill fixed システム名 / 作成者 / 作成日 values on any sheet that uses the banner."""
    today = date.today().strftime("%d/%m/%Y")
    creator = author or os.environ.get("L3_UPDATED_BY", "").strip() or "System"
    pairs = (
        ("システム名", "vba_brain"),
        ("作成者", creator),
        ("作成日", today),
    )
    for lbl, val in pairs:
        if not put_value_right_of_label(
            ws, lbl, val, row_start=1, row_end=15, col_start=1, col_end=80,
        ):
            print(f"[WARN] Header label not found ({ws.title}): {lbl}")


def find_row_by_cell_text(ws: Worksheet, col: str, marker: str,
                          row_start: int = 1, row_end: int = 300) -> int | None:
    """Return the 1-based row of the first cell in `col` whose trimmed text
    equals `marker`, searching within [row_start..row_end]. None if not found."""
    col_idx = _col_to_index(col)
    needle = marker.strip()
    for r in range(row_start, row_end + 1):
        v = _cell_value_merge_aware(ws, r, col_idx)
        if v is None:
            continue
        if str(v).strip() == needle:
            return r
    return None


def find_row_by_cell_contains(ws: Worksheet, col: str, substring: str,
                              row_start: int = 1, row_end: int = 300) -> int | None:
    """First row in [row_start..row_end] where `col` cell text contains `substring`."""
    col_idx = _col_to_index(col)
    sub = substring.strip()
    if not sub:
        return None
    for r in range(row_start, row_end + 1):
        v = _cell_value_merge_aware(ws, r, col_idx)
        if v is None:
            continue
        if sub in str(v).strip():
            return r
    return None


def locate_edit_template_row(ws: Worksheet, fallback: int = 10) -> int:
    """Locate the first *data* row of the 画面編集 item table.

    Two template styles exist in the wild:

    1) **Legacy** (multi-row header + category divider):
       row with ``C == "フォームヘッダー"`` → data starts on the **next** row.

    2) **Compact** (no ``フォームヘッダー`` row): find ``A == "№"`` (table header),
       then the sub-header row in ``AH`` containing ``ﾃｰﾌﾞﾙ名`` / ``テーブル名``
       (bottom of the merged header block) → data starts on the **next** row.
       If that sub-header is missing, assume a 3-row header: ``№`` row + 2.

    Falls back to ``fallback`` only if nothing matches.
    """
    r_no: int | None = None
    for marker in ("№", "No.", "NO", "No", "Ｎｏ．"):
        r_no = find_row_by_cell_text(ws, "A", marker)
        if r_no is not None:
            break

    if r_no is not None:
        r_div = find_row_by_cell_text(
            ws, "C", "フォームヘッダー",
            row_start=r_no + 1, row_end=r_no + 15,
        )
        if r_div is not None:
            return r_div + 1

        r_tbl: int | None = None
        for sub in ("ﾃｰﾌﾞﾙ名", "テーブル名"):
            cand = find_row_by_cell_contains(
                ws, "AH", sub,
                row_start=r_no + 1, row_end=r_no + 20,
            )
            if cand is not None:
                r_tbl = cand
                break
        if r_tbl is not None:
            return r_tbl + 1
        return r_no + 3

    r_div = find_row_by_cell_text(ws, "C", "フォームヘッダー")
    if r_div is not None:
        return r_div + 1
    return fallback


def locate_template_row(ws: Worksheet,
                        markers: list[tuple[str, str]],
                        offset: int = 1,
                        fallback: int | None = None) -> int:
    """Find a header row via `markers` [(col, expected_text), ...] and return
    `header_row + offset` (the data template row just below the header).

    Tries markers in order; first hit wins. If nothing matches and `fallback`
    is provided, returns `fallback` instead; otherwise raises.
    """
    for col, txt in markers:
        r = find_row_by_cell_text(ws, col, txt)
        if r is not None:
            return r + offset
    if fallback is not None:
        return fallback
    raise RuntimeError(
        f"Template header not found on sheet '{ws.title}' via markers: {markers}"
    )


# ─────────────────────────────────────────────
# Common header block (shared by Layout / Edit / Event sheets)
# ─────────────────────────────────────────────
def fill_common_header_layout(ws: Worksheet, bd: dict) -> None:
    """Header block on Layout sheet (rows 1-4)."""
    fill_branded_header_fields_by_label(ws, author=bd.get("author") or bd.get("updated_by"))
    put(ws, "G2", bd.get("subsystem_name"))
    put(ws, "G4", bd.get("screen_id"))
    put(ws, "W4", bd.get("screen_name"))
    put(ws, "AO2", bd.get("updated_by"))
    put(ws, "AX2", bd.get("updated_date"))


def fill_common_header_edit(ws: Worksheet, bd: dict) -> None:
    """Header block on Edit sheet (rows 1-4)."""
    fill_branded_header_fields_by_label(ws, author=bd.get("author") or bd.get("updated_by"))
    put(ws, "G2", bd.get("subsystem_name"))
    put(ws, "G4", bd.get("screen_id"))
    put(ws, "W4", bd.get("screen_name"))
    put(ws, "AM2", bd.get("updated_by"))
    put(ws, "AV2", bd.get("updated_date"))


def fill_common_header_event(ws: Worksheet, bd: dict) -> None:
    """Header block on Event (Table Update) sheet."""
    fill_branded_header_fields_by_label(ws, author=bd.get("author") or bd.get("updated_by"))
    put(ws, "N3", bd.get("subsystem_name"))
    put(ws, "G6", bd.get("screen_id"))
    put(ws, "T6", bd.get("screen_name"))
    put(ws, "AR3", bd.get("updated_by"))
    put(ws, "AV3", bd.get("updated_date"))


# ─────────────────────────────────────────────
# Sheet 1: 変更履歴 (Change History)
# ─────────────────────────────────────────────
# The data template row is auto-located at runtime by finding the header
# cell (column A == "改訂") and taking the row immediately below. If the
# user shifts rows in the template, the script adapts automatically.
CH_TEMPLATE_MARKERS = [("A", "改訂")]     # header cell
CH_TEMPLATE_FALLBACK = 3                   # used only if marker missing
CH_COL = {
    "revision":   "A",   # merged A:B
    "date":       "C",   # merged C:E
    "content":    "F",   # merged F:Q
    "reason":     "R",   # merged R:AC
    "updated_by": "AD",  # merged AD:AH
    "approver":   "AI",  # merged AI:AM
}

# Minimum number of data rows rendered on 変更履歴 (checklist / layout).
CH_MIN_DATA_ROWS = 10


def build_mock_change_history(bd: dict) -> list[dict]:
    """Sample rows for 変更履歴 when JSON `data` is empty (dev / layout preview).

    Returns ``CH_MIN_DATA_ROWS`` items so the sheet always shows a full stub block.
    Column keys match `CH_COL`: revision, date, content, reason, updated_by, approver.
    """
    try:
        from config import TARGET_LANGUAGE
    except ImportError:
        TARGET_LANGUAGE = "en"
    
    is_english = TARGET_LANGUAGE.lower() in ("en", "english")

    sid = (bd.get("screen_id") or bd.get("form_id") or "SCREEN").strip()
    sname = (bd.get("screen_name") or bd.get("form_name") or sid).strip()
    author = (bd.get("author") or "").strip()
    if author.upper() == "N/A":
        author = ""
    updater = os.environ.get("L3_UPDATED_BY", author or "System").strip() or "System"
        
    if is_english:
        approver = author or "(Approver not set)"
        rows: list[dict] = [
            {
                "revision": "01",
                "date": "2026-01-15",
                "content": f"First Edition: Newly created screen specification for {sid} ({sname})",
                "reason": "Generated initial template from vba_brain POC / BD JSON",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "02",
                "date": "2026-01-29",
                "content": "Reflected header information (System Name, Sub-system Name, Author)",
                "reason": "To fill empty fields in the common header during review",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "03",
                "date": "2026-02-06",
                "content": "Updated screen layout description, timing, and constraints",
                "reason": "Reflected business-side review comments",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "04",
                "date": "2026-02-13",
                "content": "Organized event list (Event ID, trigger, processing content)",
                "reason": "Unified event granularity and naming conventions",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "05",
                "date": "2026-02-21",
                "content": "Supplemented item definitions (logical name, physical name, type) in the edit sheet",
                "reason": "Resolved lack of item definitions to front-load implementation preparation",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "06",
                "date": "2026-03-04",
                "content": "Reviewed input/output item mapping in the table update sheet",
                "reason": "Corrected differences with the target update table",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "07",
                "date": "2026-03-18",
                "content": "Added file specifications (output layout, naming rules)",
                "reason": "Added information necessary for report/CSV integration testing",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "08",
                "date": "2026-03-31",
                "content": "Supported automatic detection logic for template rows",
                "reason": "To prevent layout break when adding Excel rows",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "09",
                "date": "2026-04-12",
                "content": "Unified the minimum displayed rows in the change history to 10 rows",
                "reason": "Addressed review feedback regarding insufficient history rows",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "10",
                "date": "2026-04-22",
                "content": "Always enabled change history mock (improves display quality when empty)",
                "reason": "Resolved the issue of history appearing empty during demos/reviews",
                "updated_by": updater,
                "approver": approver,
            },
        ]
    else:
        approver = author or "（承認者未設定）"
        rows: list[dict] = [
            {
                "revision": "01",
                "date": "2026-01-15",
                "content": f"初版：{sid}（{sname}）画面仕様書を新規作成",
                "reason": "vba_brain POC / BD JSON から initial template を生成",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "02",
                "date": "2026-01-29",
                "content": "ヘッダ情報（システム名・サブシステム名・作成者）を反映",
                "reason": "レビュー時に共通ヘッダの空欄を解消するため",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "03",
                "date": "2026-02-06",
                "content": "画面レイアウト説明・タイミング・制約条件を更新",
                "reason": "業務側レビューコメントを反映",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "04",
                "date": "2026-02-13",
                "content": "イベント一覧（イベントID・トリガー・処理内容）を整理",
                "reason": "イベント粒度と命名規則を統一",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "05",
                "date": "2026-02-21",
                "content": "画面編集シートの項目定義（論理名・物理名・型）を補完",
                "reason": "項目定義の不足を解消し実装準備を前倒し",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "06",
                "date": "2026-03-04",
                "content": "テーブル更新シートの入力/出力項目マッピングを見直し",
                "reason": "更新対象テーブルとの差異を修正",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "07",
                "date": "2026-03-18",
                "content": "ファイル仕様書（出力レイアウト・命名規則）を追記",
                "reason": "帳票/CSV連携テストに必要な情報を追加",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "08",
                "date": "2026-03-31",
                "content": "テンプレート行の自動検出ロジックに対応",
                "reason": "Excel行追加時にも崩れないようにするため",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "09",
                "date": "2026-04-12",
                "content": "変更履歴の最小表示行数を10行へ統一",
                "reason": "レビュー指摘（履歴行不足）への対応",
                "updated_by": updater,
                "approver": approver,
            },
            {
                "revision": "10",
                "date": "2026-04-22",
                "content": "変更履歴モックを常時有効化（空データ時の表示品質改善）",
                "reason": "デモ/レビュー時に履歴が空に見える問題を解消",
                "updated_by": updater,
                "approver": approver,
            },
        ]
    return rows[:CH_MIN_DATA_ROWS]


def _normalize_change_history_item(item: dict) -> dict:
    """Accept both legacy and standardized field names for change-history rows."""
    m = dict(item or {})
    aliases = {
        "revision": ("revision_no",),
        "date": ("updated_date",),
        "content": ("change_content",),
        "reason": ("reason_ticket",),
        "approver": ("approved_by",),
    }
    for canon, alt_keys in aliases.items():
        if canon in m:
            continue
        for k in alt_keys:
            if k in m:
                m[canon] = m[k]
                break
    return m


def fill_change_history(ws: Worksheet, data: list[dict]) -> None:
    """Fill 変更履歴; always expands to at least ``CH_MIN_DATA_ROWS`` data rows."""
    template_row = locate_template_row(
        ws, CH_TEMPLATE_MARKERS, offset=1, fallback=CH_TEMPLATE_FALLBACK,
    )
    n_data = len(data)
    n_rows = CH_MIN_DATA_ROWS if n_data == 0 else max(n_data, CH_MIN_DATA_ROWS)
    rows = expand_table(ws, template_row, n_rows)
    for i, r in enumerate(rows):
        clear_row_cells(ws, r, CH_COL.values())
        if i >= n_data:
            continue
        item = _normalize_change_history_item(
            data[i] if isinstance(data[i], dict) else {},
        )
        for key, col in CH_COL.items():
            if key in item:
                put(ws, f"{col}{r}", item[key])


# ─────────────────────────────────────────────
# Sheet 2: 画面仕様書(レイアウト)
# ─────────────────────────────────────────────
# All template-row positions are auto-located from header text so the script
# survives row-shifts when the user edits the template (adds/removes rows).
LAYOUT_EVENT_MARKERS  = [("A", "イベントID")]
LAYOUT_EVENT_FALLBACK = 63

LAYOUT_EVENT_COL = {
    "event_id":       "A",   # merged A:C
    "type":           "D",   # merged D:H
    "logical_name":   "I",   # merged I:O
    "physical_name":  "P",   # merged P:V
    "title":          "W",   # merged W:AC
    "event_trigger":  "AD",  # merged AD:AG
    "event_content":  "AH",  # merged AH:AS
    "module_id":      "AT",  # merged AT:AX
    "notes":          "AY",  # merged AY:BB
}

# Record Sources — section title "＜レコードソース＞" in column AM; data below.
LAYOUT_RECSRC_COL        = "AN"
LAYOUT_RECSRC_MARKERS    = [("AM", "＜レコードソース＞")]
LAYOUT_RECSRC_FALLBACK   = 10

# Process Overview — section title "【処理概要】" in column AM; data below.
LAYOUT_PROC_COL          = "AM"
LAYOUT_PROC_MARKERS      = [("AM", "【処理概要】")]
LAYOUT_PROC_FALLBACK     = 23


def fill_layout(ws: Worksheet, bd: dict,
                image_search_dirs: list[Path] | None = None) -> None:
    layout = bd.get("sheet_2_layout", {}) or {}

    fill_common_header_layout(ws, bd)

    # Description / Timing / Constraints
    put(ws, "E5",  layout.get("description") or bd.get("overview"))
    put(ws, "AI5", layout.get("timing"))
    put(ws, "E6",  layout.get("constraints"))

    search_dirs = list(image_search_dirs or [])
    resolved = _resolve_screen_image(
        layout.get("screen_image"),
        bd.get("screen_id"),
        search_dirs,
    )
    if resolved is not None:
        replace_layout_screen_image(ws, resolved)
        print(f"[INFO] Replaced layout screen image with: {resolved}")
    else:
        img = layout.get("screen_image")
        if img and isinstance(img, str):
            put(ws, "A9", img)

    # ── Record Sources list (1 template row → expand) ──
    recsrc_row = locate_template_row(
        ws, LAYOUT_RECSRC_MARKERS, offset=1, fallback=LAYOUT_RECSRC_FALLBACK,
    )
    rec_sources = layout.get("record_sources", []) or []
    purge_stale_data_rows(ws, recsrc_row, [LAYOUT_RECSRC_COL])
    if not rec_sources:
        clear_row_cells(ws, recsrc_row, [LAYOUT_RECSRC_COL])
    else:
        rows = expand_table(ws, recsrc_row, len(rec_sources))
        for src, r in zip(rec_sources, rows):
            clear_row_cells(ws, r, [LAYOUT_RECSRC_COL])
            val = src.get("query_display") if isinstance(src, dict) else src
            put(ws, f"{LAYOUT_RECSRC_COL}{r}", val)

    # ── Process Overview list (1 template row → expand) ──
    proc_row = locate_template_row(
        ws, LAYOUT_PROC_MARKERS, offset=1, fallback=LAYOUT_PROC_FALLBACK,
    )
    proc_list = layout.get("process_overview", []) or []
    purge_stale_data_rows(ws, proc_row, [LAYOUT_PROC_COL])
    if not proc_list:
        clear_row_cells(ws, proc_row, [LAYOUT_PROC_COL])
    else:
        rows = expand_table(ws, proc_row, len(proc_list))
        for proc, r in zip(proc_list, rows):
            clear_row_cells(ws, r, [LAYOUT_PROC_COL])
            val = proc.get("summary_line") if isinstance(proc, dict) else proc
            put(ws, f"{LAYOUT_PROC_COL}{r}", val)

    # ── Events table (1 template row → expand) ──
    events_row = locate_template_row(
        ws, LAYOUT_EVENT_MARKERS, offset=1, fallback=LAYOUT_EVENT_FALLBACK,
    )
    events = layout.get("events", []) or []
    if not events:
        clear_row_cells(ws, events_row, LAYOUT_EVENT_COL.values())
        return
    rows = expand_table(ws, events_row, len(events))
    for ev, r in zip(events, rows):
        clear_row_cells(ws, r, LAYOUT_EVENT_COL.values())
        ev_copy = dict(ev)
        ev_copy.pop("action_type", None)  # JSON metadata only — not written to Excel

        for key, col in LAYOUT_EVENT_COL.items():
            if key in ev_copy:
                put(ws, f"{col}{r}", ev_copy[key])


# ─────────────────────────────────────────────
# Sheet 3: 画面仕様書(画面編集)
# ─────────────────────────────────────────────
# Data template row is resolved at runtime via ``locate_edit_template_row``
# (supports both "フォームヘッダー" divider templates and compact 3-row headers).
EDIT_FALLBACK = 10
EDIT_COL = {
    "item_no":                     "A",   # merged A:B
    "io":                          "M",   # merged M:N
    "logical_name":                "C",   # merged C:G
    "physical_name":               "H",   # merged H:L
    "item_attribute":              "O",   # merged O:T
    "attribute_digits":            "U",   # merged U:V   (属性桁数)
    "required":                    "W",   # 必須
    "format":                      "Y",   # 形式
    "other_input_checks":          "Z",   # merged Z:AG  (その他入力値チェック)
    "source_table":                "AH",  # merged AH:AM (ﾃｰﾌﾞﾙ名/領域名)
    "source_field_or_fixed_value": "AN",  # merged AN:AV (項目名／固定値)
    "output_format":               "AW",  # merged AW:BB (書式)
    "notes":                       "AW",  # same column - BD JSON uses "notes"
}


def fill_screen_edit(ws: Worksheet, bd: dict) -> None:
    fill_common_header_edit(ws, bd)

    edit = bd.get("sheet_3_screen_edit", {}) or {}
    items = edit.get("items", []) or []

    template_row = locate_edit_template_row(ws, fallback=EDIT_FALLBACK)
    if not items:
        clear_row_cells(ws, template_row, EDIT_COL.values())
        return
    rows = expand_table(ws, template_row, len(items))
    for it, r in zip(items, rows):
        clear_row_cells(ws, r, EDIT_COL.values())
        for key, col in EDIT_COL.items():
            if key in it:
                put(ws, f"{col}{r}", it[key])


# ─────────────────────────────────────────────
# Sheet 4: 画面仕様書（E***） - per-event Table Update
# ─────────────────────────────────────────────
# Data template row sits just below the sub-header "ﾃｰﾌﾞﾙ名／領域名" / "項目名／固定値"
# (part of the 転送元 group).
EVENT_MARKERS  = [("U", "ﾃｰﾌﾞﾙ名／領域名"), ("AC", "項目名／固定値")]
EVENT_FALLBACK = 11
EVENT_COL = {
    "no":             "A",   # merged A:B
    "physical_name":  "C",   # merged C:K
    "logical_name":   "L",   # merged L:T
    "source_area":    "U",   # merged U:AB   (転送元 ﾃｰﾌﾞﾙ名／領域名)
    "source_field":   "AC",  # merged AC:AJ  (転送元 項目名／固定値)
    "condition":      "AK",  # merged AK:AR  (条件及び編集方法)
    "chk":            "AS",  # merged AS:AT  (CHK)
    "remark":         "AU",  # merged AU:BC  (備考)
}


def _event_item_value_empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not str(v).strip())


def _normalize_event_style_item(raw: dict) -> dict:
    """Map alternate BD JSON field names onto ``EVENT_COL`` keys.

    Some generators (e.g. C000_MAINⅡ) emit:
      ``target_field_physical``, ``source_field_or_fixed_value``,
      ``condition_and_format``, ``notes`` (table update)
    or
      ``output_field_name``, … (file export / sheet_5).

    The Excel template columns are unchanged; we only unify keys here.
    """
    m = dict(raw)
    # (canonical_key, tuple of alternate keys in preference order)
    aliases: list[tuple[str, tuple[str, ...]]] = [
        ("physical_name", ("target_field_physical", "output_field_name")),
        ("logical_name", ("target_field_logical", "output_field_logical")),
        ("source_area", ("source_table",)),
        ("source_field", ("source_field_or_fixed_value",)),
        ("condition", ("condition_and_format",)),
        ("remark", ("notes",)),
    ]
    for canon, alts in aliases:
        if canon not in m or _event_item_value_empty(m.get(canon)):
            for a in alts:
                if a in m and not _event_item_value_empty(m.get(a)):
                    m[canon] = m[a]
                    break
    return m


def _event_sheet_name(event_id: str) -> str:
    """Build per-event sheet title, e.g. 'E002' → '画面仕様書（E002）'."""
    return f"{SHEET_EVENT_PREFIX}{event_id}）"


def _existing_event_sheets(wb) -> list[str]:
    return [n for n in wb.sheetnames if n.startswith(SHEET_EVENT_PREFIX)]


def fill_event_style_table_sheet(ws: Worksheet, bd: dict,
                                 header: dict, items: list[dict]) -> None:
    """Fill a per-event **table-update** or **file-spec** sheet.

    Same Excel layout as ``画面仕様書（E***）``: header row uses either
    ``table_physical_name`` / ``table_logical_name`` / ``update_type``
    (sheet_4) **or** ``file_name`` / ``file_type`` (sheet_5) mapped onto
    ``G8`` / ``Y8`` / ``AO8``.
    """
    fill_common_header_event(ws, bd)

    if header:
        put(ws, "G8",  header.get("table_physical_name") or header.get("file_name"))
        put(ws, "Y8",  header.get("table_logical_name") or header.get("file_type"))
        put(ws, "AO8", header.get("update_type") or "")

    template_row = locate_template_row(
        ws, EVENT_MARKERS, offset=1, fallback=EVENT_FALLBACK,
    )
    if not items:
        clear_row_cells(ws, template_row, EVENT_COL.values())
        return
    rows = expand_table(ws, template_row, len(items))
    for it, r in zip(items, rows):
        clear_row_cells(ws, r, EVENT_COL.values())
        norm = _normalize_event_style_item(it if isinstance(it, dict) else {})
        for key, col in EVENT_COL.items():
            if key in norm:
                put(ws, f"{col}{r}", norm[key])
        _auto_fit_event_row_height(ws, r, norm)


def _clone_tpl_for_event_style(wb, *, include_file_spec: bool = True) -> str | None:
    """Pick a worksheet to clone for E-style table sheets.

    ``include_file_spec=True`` (``sheet_5``): prefer ``ファイル仕様書（`` then
    ``画面仕様書（``.

    ``include_file_spec=False`` (``sheet_4``): **only** ``画面仕様書（`` so a
    file-spec sheet is never used as clone source for table-update sheets.
    """
    if include_file_spec:
        for n in wb.sheetnames:
            if n.startswith(SHEET_FILE_SPEC_PREFIX):
                return n
    ev = [n for n in wb.sheetnames if n.startswith(SHEET_EVENT_PREFIX)]
    return ev[0] if ev else None


def _safe_sheet_title(name: str) -> str:
    """Excel worksheet title max 31 chars."""
    name = name.strip()
    return name[:31] if len(name) > 31 else name


def handle_file_spec_sheets(wb, bd: dict) -> None:
    """Fill ``sheet_5_file_spec`` — same table layout as ``画面仕様書（E***）``.

    JSON: list of ``{ "sheet_name_pattern": "ファイル仕様書（E001）",
    "header": { "file_name", "file_type", ... }, "items": [...] }``.

    Run **before** ``handle_event_sheets`` so a clone source still exists when
    ``sheet_4_table_update`` is empty (otherwise template E-sheets are removed).
    """
    raw5 = bd.get("sheet_5_file_spec")
    if isinstance(raw5, dict):
        blocks = [raw5] if raw5.get("header") is not None or raw5.get("items") is not None else []
    elif isinstance(raw5, list):
        blocks = [b for b in raw5 if isinstance(b, dict)]
    else:
        blocks = []

    existing = [n for n in wb.sheetnames if n.startswith(SHEET_FILE_SPEC_PREFIX)]

    if not blocks:
        for name in existing:
            del wb[name]
        return

    tpl_name = _clone_tpl_for_event_style(wb, include_file_spec=True)
    if tpl_name is None:
        print("[WARN] No 画面仕様書（E***） / ファイル仕様書 template — cannot fill sheet_5_file_spec")
        return

    used: set[str] = set()
    for block in blocks:
        dst = (block.get("sheet_name_pattern") or "").strip()
        if not dst:
            print("[WARN] sheet_5_file_spec block missing sheet_name_pattern — skip")
            continue
        dst = _safe_sheet_title(dst)
        if dst in wb.sheetnames:
            ws = wb[dst]
        else:
            ws = wb.copy_worksheet(wb[tpl_name])
            ws.title = dst
        fill_event_style_table_sheet(
            ws, bd,
            block.get("header") or {},
            block.get("items") or [],
        )
        used.add(dst)

    for name in list(wb.sheetnames):
        if name.startswith(SHEET_FILE_SPEC_PREFIX) and name not in used:
            del wb[name]


def handle_event_sheets(wb, bd: dict) -> None:
    """
    ``sheet_4_table_update`` supports the same **block** shape as ``sheet_5_file_spec``:

    - **dict:** ``{"header": {...}, "items": [...]}`` (legacy; rows grouped by ``event_id``)
    - **list of blocks:** ``[{"sheet_name_pattern": "画面仕様書（E004）",
      "header": {...}, "items": [...]}, ...]``
    - **flat list:** ``[{"event_id": "E004", "no": "1", ...}, ...]`` (shared header ``{}``)

    Sheets whose names start with ``画面仕様書（`` but are not in the output set
    are removed from the workbook.
    """
    raw4 = bd.get("sheet_4_table_update")
    existing = _existing_event_sheets(wb)

    workloads: list[tuple[str, dict, list]] = []

    if isinstance(raw4, dict):
        items = raw4.get("items", []) or []
        header = raw4.get("header", {}) or {}
        grouped: dict[str, list[dict]] = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            eid = str(it.get("event_id") or header.get("event_id") or "E000")
            grouped.setdefault(eid, []).append(it)
        if not grouped:
            for name in existing:
                del wb[name]
            return
        for eid, ev_items in grouped.items():
            workloads.append((_safe_sheet_title(_event_sheet_name(eid)), header, ev_items))
    elif isinstance(raw4, list):
        if not raw4:
            for name in existing:
                del wb[name]
            return
        first = raw4[0]
        if (isinstance(first, dict) and "header" in first
                and isinstance(first.get("items"), list)):
            for block in raw4:
                if not isinstance(block, dict):
                    continue
                hdr = block.get("header") or {}
                itm = block.get("items") or []
                dst = (block.get("sheet_name_pattern") or "").strip()
                if not dst:
                    eid = str(
                        hdr.get("event_id")
                        or (itm[0].get("event_id") if itm else "")
                        or "E000",
                    )
                    dst = _event_sheet_name(eid)
                workloads.append((_safe_sheet_title(dst), hdr, itm))
        else:
            grouped = {}
            for it in raw4:
                if not isinstance(it, dict):
                    continue
                eid = str(it.get("event_id") or "E000")
                grouped.setdefault(eid, []).append(it)
            if not grouped:
                for name in existing:
                    del wb[name]
                return
            for eid, ev_items in grouped.items():
                workloads.append((_safe_sheet_title(_event_sheet_name(eid)), {}, ev_items))
    else:
        for name in existing:
            del wb[name]
        return

    tpl_name = _clone_tpl_for_event_style(wb, include_file_spec=False)
    if tpl_name is None:
        print("[WARN] No template event sheet in workbook - cannot create new event sheets")
        return

    used: set[str] = set()
    for dst_name, header, ev_items in workloads:
        dst_name = _safe_sheet_title(dst_name)
        if dst_name in wb.sheetnames:
            ws = wb[dst_name]
        else:
            ws = wb.copy_worksheet(wb[tpl_name])
            ws.title = dst_name
        fill_event_style_table_sheet(ws, bd, header, ev_items)
        used.add(dst_name)

    for name in existing:
        if name not in used:
            del wb[name]


# ─────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────
def fill_excel(
    template_path: Path,
    bd: dict,
    output_path: Path,
    *,
    mock_change_history: bool = True,
    image_search_dirs: list[Path] | None = None,
    draw_layout_shapes: bool = True,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_path, output_path)

    wb = load_workbook(output_path)

    if SHEET_CHANGE_HISTORY in wb.sheetnames:
        ch_data = (bd.get("sheet_1_change_history", {}) or {}).get("data", []) or []
        if not ch_data and mock_change_history:
            ch_data = build_mock_change_history(bd)
            print("[INFO] sheet_1_change_history.data is empty - using built-in mock rows")
        fill_change_history(wb[SHEET_CHANGE_HISTORY], ch_data)
    else:
        print(f"[WARN] Sheet not found: {SHEET_CHANGE_HISTORY}")

    if SHEET_LAYOUT in wb.sheetnames:
        fill_layout(wb[SHEET_LAYOUT], bd,
                    image_search_dirs=image_search_dirs)
    else:
        print(f"[WARN] Sheet not found: {SHEET_LAYOUT}")

    if SHEET_EDIT in wb.sheetnames:
        fill_screen_edit(wb[SHEET_EDIT], bd)
    else:
        print(f"[WARN] Sheet not found: {SHEET_EDIT}")

    # File-spec sheets clone from 画面仕様書（E***） — run **before** table-update
    # so an empty sheet_4 does not delete the clone source first.
    handle_file_spec_sheets(wb, bd)
    handle_event_sheets(wb, bd)

    try:
        try:
            from excel_translator import translate_workbook
        except ImportError:
            from .excel_translator import translate_workbook
        translate_workbook(wb)
    except Exception as e:
        print(f"[WARN] Failed to translate workbook: {e}")

    wb.save(output_path)

    if draw_layout_shapes and SHEET_LAYOUT in wb.sheetnames:
        labels = _collect_layout_shape_labels(bd)
        if labels:
            _draw_layout_shapes_via_excel_com(
                output_path,
                template_path=template_path,
                sheet_name=SHEET_LAYOUT,
                labels=labels,
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill BD JSON into the Excel screen-specification template.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_BD_TEMPLATE,
        help=f"Excel template .xlsx (default: {DEFAULT_BD_TEMPLATE})",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Single BD JSON file (use with --output).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Single output .xlsx path (use with --input).",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help=f"Batch: folder of *.json (default when no --input: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Batch: output folder for .xlsx (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--no-mock-change-history",
        dest="mock_change_history",
        action="store_false",
        default=True,
        help="Disable auto-fill of 変更履歴 mock rows when JSON data is empty.",
    )
    parser.add_argument(
        "--image-dir",
        action="append",
        default=None,
        help="Directory to search for screen images (can be repeated). "
             "Default: 02_tools/Access_DesignView/Form.",
    )
    parser.add_argument(
        "--no-layout-shapes",
        action="store_true",
        help="Disable Excel COM post-processing that draws item_no shapes on sheet 2.",
    )
    args = parser.parse_args()

    template_path = Path(args.template)
    if not template_path.is_file():
        raise SystemExit(f"[ERR] Template not found: {template_path}")

    image_dirs = [Path(p) for p in args.image_dir] if args.image_dir else [DEFAULT_IMAGE_DIR]

    # Batch when --input is omitted; dirs default to screen → outputs/BD_Output/screen
    batch = args.input is None
    if batch:
        in_dir = args.input_dir or DEFAULT_INPUT_DIR
        out_dir = args.output_dir or DEFAULT_OUTPUT_DIR
        if not in_dir.is_dir():
            raise SystemExit(f"[ERR] Input directory not found: {in_dir}")

        json_files = sorted(in_dir.glob("*.json"))
        if not json_files:
            raise SystemExit(f"[ERR] No *.json files in {in_dir}")

        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] Template  : {template_path}")
        print(f"[INFO] Input dir  : {in_dir} ({len(json_files)} file(s))")
        print(f"[INFO] Output dir : {out_dir}")

        ok = 0
        failed: list[tuple[str, str]] = []
        for input_path in json_files:
            output_path = (
                out_dir / f"{get_bd_screen_output_filename_prefix()}{input_path.stem}.xlsx"
            )
            try:
                with open(input_path, "r", encoding="utf-8") as f:
                    bd = json.load(f)
                fill_excel(
                    template_path,
                    bd,
                    output_path,
                    mock_change_history=args.mock_change_history,
                    image_search_dirs=image_dirs,
                    draw_layout_shapes=not args.no_layout_shapes,
                )
                print(f"[DONE]  {input_path.name} -> {output_path.name}")
                ok += 1
            except json.JSONDecodeError as e:
                failed.append((input_path.name, f"invalid JSON — {e}"))
                print(f"[ERR]   {input_path.name}: invalid JSON — {e}")
            except Exception as e:
                failed.append((input_path.name, str(e)))
                print(f"[ERR]   {input_path.name}: {e}")

        print(f"[SUMMARY] {ok} ok, {len(failed)} failed")
        if failed:
            raise SystemExit(1)
        return

    # Single-file mode (--input was given)
    if not args.output:
        raise SystemExit("[ERR] --output is required when using --input.")

    input_path  = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_file():
        raise SystemExit(f"[ERR] Input JSON not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        bd = json.load(f)

    print(f"[INFO] Template : {template_path}")
    print(f"[INFO] Input    : {input_path}")
    print(f"[INFO] Output   : {output_path}")

    fill_excel(
        template_path,
        bd,
        output_path,
        mock_change_history=args.mock_change_history,
        image_search_dirs=image_dirs,
        draw_layout_shapes=not args.no_layout_shapes,
    )

    print(f"[DONE]  Saved -> {output_path}")


if __name__ == "__main__":
    main()
