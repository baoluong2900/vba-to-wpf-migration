"""
agents/ui/control_mapper.py — Access Control → WPF Control Mapper

Chuyển đổi Access control types → WPF control definitions.
Twips → Pixels conversion: 1 twip = 1/15 pixel.

Output structure:
  map_all_controls()  → flat list[dict]   (backward compat)
  map_sections()      → sectioned list[dict] grouped by nodekey parent
"""
from __future__ import annotations

import logging
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Access twips → WPF pixels
# ──────────────────────────────────────────────
TWIPS_PER_PIXEL = 15


def twips_to_px(twips: int | float) -> int:
    """Convert Access twips to WPF pixels (rounded)."""
    return round(twips / TWIPS_PER_PIXEL)


def access_color_to_hex(color_int: int) -> str:
    """
    Convert Access BGR integer to WPF hex color string.
    Access stores color as BGR (not RGB). WPF uses #AARRGGBB.
    Special values: -2147483633 = transparent/system, -2147483630 = button text
    """
    if color_int < 0:
        system_colors = {
            -2147483633: "Transparent",
            -2147483630: "#FF000000",
            -2147483640: "#FFF0F0F0",
        }
        return system_colors.get(color_int, "Transparent")
    # BGR → RGB
    b = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    r = color_int & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


# ──────────────────────────────────────────────
# Font name normalization: JP fullwidth → WPF English
# WPF không resolve được tên font fullwidth Unicode (ＭＳ Ｐゴシック...)
# → map sang English name để WPF load đúng font
# ──────────────────────────────────────────────
WPF_FONT_MAP: dict[str, str] = {
    # MS Gothic family
    "ＭＳ Ｐゴシック":   "MS PGothic",
    "ＭＳ ゴシック":     "MS Gothic",
    "ＭＳ Ｐ明朝":       "MS PMincho",
    "ＭＳ 明朝":         "MS Mincho",
    # Meiryo
    "メイリオ":          "Meiryo",
    "Meiryo UI":         "Meiryo",  # Map UI variant to full width variant
    # Yu Gothic
    "游ゴシック":         "Yu Gothic",
    "游明朝":            "Yu Mincho",
    # System UI variants
    "ＭＳ ＵＩ Ｇｏｔｈｉｃ": "MS Gothic",   # Map UI Gothic to MS Gothic for wider look
}


def normalize_font_family(font: str | None) -> str | None:
    """
    Convert Access/fullwidth font name → WPF-compatible English name.
    Falls back to original if not in the map.
    """
    if not font:
        return font
    return WPF_FONT_MAP.get(font.strip(), font)


def sanitize_xaml_name(name: str) -> str:
    """
    Ensure x:Name is a valid C# identifier.
    ルール:
      - 先頭が数字なら ctrl_ prefix
      - ASCII 以外の文字 là メイン名が英数字 or ASCIIなら そのまま使用
      - これ以外は Unicode code point に変換
    e.g.  「ログインID」  →  ctrl_30ed30af30a430f3ID
          「cmdLogin」 →  cmdLogin
    """
    import re
    if not name:
        return "ctrl_unnamed"
    # Check if already valid identifier (ASCII letters, digits, underscore)
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
        return name
    # Build safe name: replace non-ASCII chars with hex codepoints
    safe = ""
    for ch in name:
        if ch.isalnum() or ch == '_':
            safe += ch
        else:
            safe += f"{ord(ch):04x}"
    # Ensure starts with letter/underscore
    if safe and safe[0].isdigit():
        safe = "ctrl_" + safe
    return safe or "ctrl_unnamed"


def sanitize_class_name(name: str) -> str:
    """
    Ensure a window/class name is a valid C# class identifier.
    Replaces any invalid characters (like parentheses, spaces, hyphens, dots) with underscores,
    collapses multiple underscores, and ensures it doesn't start with a digit.
    Keep Japanese/Unicode letters intact since C# fully supports them in class names.
    """
    import unicodedata
    import re
    if not name:
        return "Window"

    chars = []
    for i, ch in enumerate(name):
        cat = unicodedata.category(ch)
        is_letter = cat.startswith('L') or cat == 'Nl' or ch == '_'
        is_digit = cat == 'Nd'
        
        if i == 0:
            if is_letter:
                chars.append(ch)
            elif is_digit:
                chars.append('_' + ch)
            else:
                chars.append('_')
        else:
            if is_letter or is_digit:
                chars.append(ch)
            else:
                chars.append('_')
                
    sanitized = "".join(chars)
    sanitized = re.sub(r'_+', '_', sanitized)
    if len(sanitized) > 1 and sanitized.endswith('_'):
        sanitized = sanitized[:-1]
    return sanitized






def _fmt_to_wpf(fmt: dict) -> dict:
    """
    Convert a raw MongoDB format dict into clean WPF-ready properties.
    Returns ALL converted format fields (no filtering).
    """
    out: dict[str, Any] = {}

    # Position & size (twips → px)
    for key in ("left", "top", "width", "height"):
        if key in fmt:
            out[key] = twips_to_px(fmt[key])

    # Caption / text (Normalize to NFKC: converts half-width Katakana to full-width)
    if fmt.get("caption") is not None:
        caption = fmt["caption"]
        if isinstance(caption, str):
            caption = unicodedata.normalize('NFKC', caption)
        out["caption"] = caption

    # Font
    if fmt.get("fontname"):
        out["font_family"] = normalize_font_family(fmt["fontname"])

    if fmt.get("fontsize"):
        out["font_size"] = fmt["fontsize"]
    if fmt.get("fontweight", 0) >= 700:
        out["font_weight"] = "Bold"
    if fmt.get("textfontcharset"):
        # 128=Japanese, 177=Hebrew, 0=ANSI
        out["font_charset"] = fmt["textfontcharset"]
    if fmt.get("textfontfamily") is not None:
        out["font_family_code"] = fmt["textfontfamily"]

    # Colors
    if "forecolor" in fmt:
        out["foreground"] = access_color_to_hex(fmt["forecolor"])
    if "backcolor" in fmt:
        backstyle = fmt.get("backstyle", 1)
        out["background"] = "Transparent" if backstyle == 0 else access_color_to_hex(fmt["backcolor"])
    if "bordercolor" in fmt:
        out["border_color"] = access_color_to_hex(fmt["bordercolor"])

    # Border
    if fmt.get("borderlinestyle") == 0:
        out["border_style"] = "None"

    # Text alignment (Access VBA): 0=General, 1=Left, 2=Center, 3=Right, 4=Distribute/Justify
    textalign_map = {0: "Left", 1: "Left", 2: "Center", 3: "Right", 4: "Justify"}
    if fmt.get("textalign") in textalign_map:
        out["text_align"] = textalign_map[fmt["textalign"]]

    # Padding (twips → px), skip 0
    for src, dst in [
        ("leftpadding",   "padding_left"),
        ("toppadding",    "padding_top"),
        ("rightpadding",  "padding_right"),
        ("bottompadding", "padding_bottom"),
        ("leftmargin",    "margin_left"),
        ("topmargin",     "margin_top"),
    ]:
        if fmt.get(src):
            out[dst] = twips_to_px(fmt[src])

    # Visibility
    if fmt.get("visible") is False or fmt.get("visible") == 0:
        out["visible"] = False

    # Picture / Image
    if fmt.get("picture"):
        out["picture"] = fmt["picture"]

    # Theme / grid line colors (kept as-is for reference)
    for key in (
        "backthemecolorindex", "backtint", "gridlinecolor",
        "forethemecolorindex", "gridlinethemecolorindex", "gridlineshade",
        "borderthemecolorindex", "bordershade", "themefontindex",
        "overlapflags",
    ):
        if key in fmt:
            out[key] = fmt[key]

    # [NEW] Universal Mapping: Include all other properties from MongoDB format that were not explicitly handled
    # This ensures LLM has maximum context.
    for k, v in fmt.items():
        if k not in out:
            out[k] = v

    return out


# ──────────────────────────────────────────────
# Access type → WPF control mapping
# ──────────────────────────────────────────────
ACCESS_TO_WPF: dict[str, str] = {
    "TextBox":       "TextBox",
    "Label":         "Label",
    "CommandButton": "Button",
    "ComboBox":      "ComboBox",
    "CheckBox":      "CheckBox",
    "OptionButton":  "RadioButton",
    "ListBox":       "ListBox",
    "SubForm":       "ContentControl",
    "TabControl":    "TabControl",
    "Image":         "Image",
    "Line":          "Separator",
    "Rectangle":     "Border",
    "ToggleButton":  "ToggleButton",
}


def map_control(mongo_item: dict) -> dict:
    """
    Map a single MongoDB forms.items[] entry to a WPF control dict.
    Includes ALL format properties (converted to WPF units/values).
    """
    access_type = mongo_item.get("type", "")
    name        = mongo_item.get("name", "")
    props       = mongo_item.get("properties", {})
    fmt         = props.get("format", {})
    data        = props.get("data", {})
    other       = props.get("other", {})
    events      = props.get("event", {})

    # WPF control type
    wpf_type = ACCESS_TO_WPF.get(access_type, "TextBlock")
    # PasswordBox detection: raw MongoDB = "inputmask", processed = "input_mask"
    input_mask = data.get("inputmask") or data.get("input_mask", "")
    if str(input_mask).lower() == "password":
        wpf_type = "PasswordBox"

    # Build result: identity fields first
    result: dict[str, Any] = {
        "name":        name,
        "access_type": access_type,
        "wpf_type":    wpf_type,
        "nodekey":     mongo_item.get("nodekey", ""),
    }

    # Merge ALL format properties (twips→px, BGR→hex, etc.)
    wpf_fmt = _fmt_to_wpf(fmt)
    
    # Handle Picture / ImageData logic
    # RULE: Use MongoDB format.picture as-is when it has a file extension (e.g., "終了.bmp").
    # Only fallback to {control_name}.bmp when there is no picture filename but imagedata exists.
    orig_pic = wpf_fmt.get("picture")
    if orig_pic and "." in str(orig_pic):
        # Keep original — MongoDB picture field is the authoritative filename
        wpf_fmt["picture"] = str(orig_pic)
    elif other.get("imagedata") or other.get("picture"):
        # Has image data but no filename → use control name (extractor naming convention)
        wpf_fmt["picture"] = f"{name}.bmp"
    
    # [NEW] Normalize enterkeybehavior -> accepts_return
    if other.get("enterkeybehavior") == "New Line in Field":
        wpf_fmt["accepts_return"] = True

    result["format"] = wpf_fmt

    # data.* fields
    data_out: dict[str, Any] = {}
    # is_readonly: raw MongoDB = "locked", processed format = "is_readonly"
    if data.get("locked") or data.get("is_readonly"):
        data_out["is_readonly"] = True
    if data.get("controlsource") or data.get("control_source"):
        data_out["control_source"] = data.get("controlsource") or data.get("control_source")
    if data.get("inputmask") or data.get("input_mask"):
        data_out["input_mask"] = data.get("inputmask") or data.get("input_mask")
    if data_out:
        result["data"] = data_out
    
    # [NEW] Merge all remaining data fields
    for k, v in data.items():
        if k not in result.get("data", {}):
            if "data" not in result: result["data"] = {}
            result["data"][k] = v

    # other.* useful fields (label pairing, tab order...)
    other_out: dict[str, Any] = {}
    if other.get("labelname"):
        other_out["label_name"] = other["labelname"]
    if other.get("tabindex") is not None:
        other_out["tab_index"] = other["tabindex"]
    if other.get("tag"):
        other_out["tag"] = other["tag"]
    if other_out:
        result["other"] = other_out
    
    # [NEW] Merge all remaining other fields
    for k, v in other.items():
        if k not in result.get("other", {}):
            if "other" not in result: result["other"] = {}
            result["other"][k] = v

    # Events (for command binding)
    if events:
        result["events"] = events

    return result


def map_sections(mongo_items: list[dict]) -> list[dict]:
    """
    Map MongoDB forms.items[] → sectioned structure grouped by nodekey parent.

    Grouping rules:
      - nodekey=""   → container cha (bất kỳ type)
      - nodekey!=""  → con, khớp tên cha hoặc literal type (section/formheader/...)
    """
    # ── Pass 1: thu thập tất cả parent nodes (nodekey == "") ─────────────
    # nodekey="" = container cha (bất kỳ type — giống GroupBox/Grid WPF)
    # nodekey!="" = con, gom vào cha khớp theo tên hoặc literal type
    parent_map: dict[str, dict] = {}

    # last_by_type: type → tên cha gần nhất của type đó
    # VD: {"section": "詳細", "formheader": "ヘッダー", "subform": "sfOrder"}
    # Dùng để resolve Access literal nodekey (ko phải tên động)
    last_by_type: dict[str, str] = {}

    for item in mongo_items:
        if item.get("nodekey", "") != "":
            continue  # bỏ qua con ở pass 1

        name  = item.get("name", "")
        itype = item.get("type", "")
        props = item.get("properties", {})

        parent_map[name] = {
            "section_name":   name,
            "section_type":   itype,
            "section_format": _fmt_to_wpf(props.get("format", {})),
            "controls":       [],
        }
        # Track cha gần nhất theo từng type
        last_by_type[itype] = name

    # ── Pass 2: gắn con vào cha ───────────────────────────────────────────
    orphans: list[dict] = []

    for item in mongo_items:
        nodekey = item.get("nodekey", "")
        if nodekey == "":
            continue  # bỏ qua cha ở pass 2

        ctrl = map_control(item)

        if nodekey in parent_map:
            # Khớp theo tên cha (tên động: TabCtrl1, sfOrder, ...)
            parent_map[nodekey]["controls"].append(ctrl)
        elif nodekey in last_by_type:
            # Access literal nodekey = type của cha
            # "section"    → cha type=section gần nhất
            # "formheader" → cha type=formheader gần nhất
            # "formfooter" → cha type=formfooter gần nhất
            # "subform"    → cha type=subform gần nhất
            # ... v.v.
            parent_name = last_by_type[nodekey]
            parent_map[parent_name]["controls"].append(ctrl)
        else:
            logger.warning(
                "[ControlMapper] nodekey=%r không tìm được cha, item=%r → orphan",
                nodekey, item.get("name", ""),
            )
            orphans.append(ctrl)

    # ── Kết quả + Fix section heights ────────────────────────────────────
    sections = list(parent_map.values())

    # Fix section heights: use max(control.top + control.height) instead of design height
    # Access section height is "design canvas" not "visible height"
    for section in sections:
        controls = section.get("controls", [])
        if controls:
            # Calculate actual height from controls
            max_bottom = 0
            for ctrl in controls:
                ctrl_fmt = ctrl.get("format", {})
                top = ctrl_fmt.get("top", 0)
                height = ctrl_fmt.get("height", 0)
                bottom = top + height
                if bottom > max_bottom:
                    max_bottom = bottom
            
            # Update section height to actual content height (with small padding)
            if max_bottom > 0:
                section["section_format"]["height"] = max_bottom + 10  # 10px padding

    if orphans:
        sections.append({
            "section_name":   "__root__",
            "section_type":   "root",
            "section_format": {},
            "controls":       orphans,
        })

    total = sum(len(s["controls"]) for s in sections)
    logger.info(
        "[ControlMapper] %d controls / %d container(s) (orphans=%d)",
        total, len(sections), len(orphans),
    )
    return sections


def map_all_controls(mongo_items: list[dict]) -> list[dict]:
    """
    Flat list of WPF controls (backward compat).
    Skips section headers.
    """
    controls: list[dict] = []
    for item in mongo_items:
        if item.get("type") == "section" and item.get("nodekey", "") == "":
            continue
        controls.append(map_control(item))

    logger.info("[ControlMapper] Mapped %d controls (flat)", len(controls))
    return controls
