"""
agents/report/tool_report.py — Report tool: High-fidelity MS Access to Microsoft RDLC XML generator and WPF MVVM controllers.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from core.models import GeneratedFile

logger = logging.getLogger(__name__)

# Base Directories
BASE_DIR = Path(__file__).parent
INPUTS_DIR = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Avalonia source vba_brain.UI.Avalonia folder
WPF_PROJECT_DIR = (
    BASE_DIR.parent.parent.parent.parent.parent  # → src/
    / "wpf" / "vba_brain.UI.Avalonia"
)

# ──────────────────────────────────────────
# Data & Config Loaders
# ──────────────────────────────────────────

def load_dd_json(form_name: str, mongo_uri: str, mongo_db: str) -> dict:
    """Load DD JSON from MongoDB or local inputs."""
    try:
        from pymongo import MongoClient
        client = MongoClient(mongo_uri)
        db = client[mongo_db]
        doc = db["dds"].find_one({"$or": [{"form_name": form_name}, {"screen_name": form_name}, {"name": form_name}]}, {"_id": 0})
        client.close()
        if doc:
            return doc
    except Exception as e:
        logger.warning("[tool_report] MongoDB load_dd_json failed: %s", e)

    alt = INPUTS_DIR / f"{form_name}.json"
    if alt.exists():
        return json.loads(alt.read_text(encoding="utf-8"))
    alt2 = INPUTS_DIR / f"{form_name}_dd.json"
    if alt2.exists():
        return json.loads(alt2.read_text(encoding="utf-8"))
    return {}


def load_bd_json(form_name: str, mongo_uri: str, mongo_db: str) -> dict:
    """Load BD JSON from MongoDB or local inputs."""
    try:
        from pymongo import MongoClient
        client = MongoClient(mongo_uri)
        db = client[mongo_db]
        doc = db["bds"].find_one({"$or": [{"form_name": form_name}, {"screen_name": form_name}, {"name": form_name}]}, {"_id": 0})
        client.close()
        if doc:
            return doc
    except Exception as e:
        logger.warning("[tool_report] MongoDB load_bd_json failed: %s", e)

    alt = INPUTS_DIR / f"{form_name}_bd.json"
    if alt.exists():
        return json.loads(alt.read_text(encoding="utf-8"))
    return {}


def load_mongo_form(form_name: str, mongo_uri: str, mongo_db: str) -> dict:
    """Load MongoDB forms collection item."""
    try:
        from pymongo import MongoClient
        client = MongoClient(mongo_uri)
        db = client[mongo_db]
        doc = db["forms"].find_one({"name": form_name}, {"_id": 0})
        client.close()
        if doc:
            return doc
    except Exception as e:
        logger.warning("[tool_report] MongoDB forms load failed: %s", e)
    return {}


def load_name_config() -> dict:
    """Load flat dictionary of Japanese -> English name mappings from name_config.json."""
    config_paths = [
        BASE_DIR.parent / "repo" / "config" / "name_config.json",
        BASE_DIR.parent.parent.parent / "layer5" / "agents" / "repo" / "config" / "name_config.json"
    ]
    for path in config_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    mapping = {}
                    for cat in ["parameter_name", "function_name", "cte_name", "control_name", "table_name", "field_name"]:
                        if cat in data and isinstance(data[cat], dict):
                            mapping.update(data[cat])
                    for k, v in data.items():
                        if isinstance(v, dict) and k not in ["parameter_name", "function_name", "cte_name", "control_name", "table_name", "field_name"]:
                            mapping.update(v)
                    return mapping
            except Exception as e:
                logger.warning("[tool_report] Failed to load name_config from %s: %s", path, e)
    return {}


def load_raw_config() -> dict:
    """Load raw (nested) name_config.json."""
    config_paths = [
        BASE_DIR.parent / "repo" / "config" / "name_config.json",
        BASE_DIR.parent.parent.parent / "layer5" / "agents" / "repo" / "config" / "name_config.json"
    ]
    for path in config_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("[tool_report] Failed to load raw name_config from %s: %s", path, e)
    return {"table_name": {}, "field_name": {}, "parameter_name": {}, "function_name": {}, "cte_name": {}, "control_name": {}}


def save_raw_config(config: dict) -> None:
    """Save raw (nested) name_config.json."""
    config_paths = [
        BASE_DIR.parent / "repo" / "config" / "name_config.json",
        BASE_DIR.parent.parent.parent / "layer5" / "agents" / "repo" / "config" / "name_config.json"
    ]
    for path in config_paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
                logger.info("[tool_report] Saved raw name_config to %s", path)
                return
        except Exception as e:
            logger.warning("[tool_report] Failed to save raw name_config to %s: %s", path, e)


# ──────────────────────────────────────────
# Helpers for Twips-to-Pixels Layout Translation
# ──────────────────────────────────────────

def twips_to_pixels(twips: Any) -> float:
    """Convert twips to device-independent pixels (1 twip = 1/15 pixels)."""
    try:
        return round(float(twips) / 15.0, 1)
    except:
        return 0.0


def access_color_to_hex(color_int: int) -> str:
    """Convert Access color integer (BGR) to hex color string."""
    if color_int < 0:
        system_colors = {
            -2147483633: "Transparent",
            -2147483630: "#000000",
            -2147483640: "#F0F0F0",
            -2147483617: "#A6A6A6",
        }
        return system_colors.get(color_int, "#A6A6A6")
    b = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    r = color_int & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"

def fontweight_mapping(weight: Any) -> str:
    """Map Access fontweight value to standard C# FontWeight."""
    try:
        w = int(weight)
        return "Bold" if w >= 700 else "Normal"
    except:
        return "Normal"


def textalign_mapping(align: Any) -> str:
    """Map Access textalign to WPF TextAlignment."""
    try:
        a = int(align)
        if a == 1: return "Left"
        if a == 2: return "Center"
        if a == 3: return "Right"
        return "Default"
    except:
        return "Default"


def access_color_to_hex(color_val: Any, backstyle: Any = 1) -> str:
    """Convert Access OLE Color (decimal) to Hex format (#RRGGBB). Returns Transparent if backstyle is 0."""
    if backstyle == 0:
        return "Transparent"
    if color_val is None:
        return "#000000"
    try:
        val = int(color_val)
        # OLE color is BGR format
        r = val & 0xFF
        g = (val >> 8) & 0xFF
        b = (val >> 16) & 0xFF
        return f"#{r:02X}{g:02X}{b:02X}"
    except:
        return "#000000"


def clean_field_name(source: str) -> str:
    """Clean the raw Japanese control source string into a clean field name, extracting from Format/Nz functions."""
    if not source:
        return ""
    
    cleaned = source.strip().lstrip('=')
    
    # 1. Try to extract from standard function wrappers Format(field, ...) or Nz(field, ...)
    format_match = re.match(r'(?i)Format\(\s*\[?([^,\)]+)\]?\s*,\s*[^)]+\)', cleaned)
    if format_match:
        cleaned = format_match.group(1)
    else:
        nz_match = re.match(r'(?i)Nz\(\s*\[?([^,\)]+)\]?\s*,\s*[^)]+\)', cleaned)
        if nz_match:
            cleaned = nz_match.group(1)
            
    # 2. Extract first bracketed field if multiple brackets or concatenated expression (e.g. [Field] & "様")
    brackets = re.findall(r'\[([^\]]+)\]', cleaned)
    if brackets:
        cleaned = brackets[0]
        
    # 3. Strip remaining brackets and quotes
    cleaned = cleaned.replace('[', '').replace(']', '').replace('"', '').replace("'", "")
    
    # 4. Remove any table alias prefix (e.g. T_Table.Field -> Field)
    cleaned = cleaned.split('.')[-1]
    
    return cleaned.strip()

# ──────────────────────────────────────────
# Microsoft RDLC XML Layout Generator (Report)
# ──────────────────────────────────────────

def generate_report_rdlc(form_name: str, mongo_items: list) -> str:
    """Generate high-fidelity RDLC Report definition (.rdlc XML) in Inches."""
    name_map = load_name_config()
    
    # 1. Collect dynamic fields to declare in the DataSet
    fields = set()
    for item in mongo_items:
        itype = item.get("type", "")
        props = item.get("properties", {})
        data = props.get("data", {})
        
        is_in_group = False
        option_value = None
        if itype in ["CheckBox", "OptionButton", "ToggleButton"]:
            option_value = data.get("optionvalue")
            parent_key = item.get("parentkey")
            optiongroup_name = props.get("other", {}).get("optiongroupname")
            parent_group = None
            if parent_key or optiongroup_name:
                for x in mongo_items:
                    if x.get("type") == "OptionGroup":
                        if parent_key and x.get("key") == parent_key:
                            parent_group = x
                            break
                        if optiongroup_name and x.get("name") == optiongroup_name:
                            parent_group = x
                            break
                if parent_group:
                    is_in_group = True
                    group_data = parent_group.get("properties", {}).get("data", {})
                    source_raw = group_data.get("controlsource", "")
                    source = clean_field_name(source_raw)
                    eng_prop = name_map.get(source, source) if source else ""
                    if eng_prop:
                        fields.add(eng_prop)
                        
        if not is_in_group or itype not in ["CheckBox", "OptionButton", "ToggleButton"]:
            source_raw = data.get("controlsource", "")
            if source_raw:
                brackets = re.findall(r'\[([^\]]+)\]', source_raw)
                if brackets:
                    for b in brackets:
                        source = b.split('.')[-1].strip()
                        eng_prop = name_map.get(source, source)
                        if eng_prop: fields.add(eng_prop)
                else:
                    source = clean_field_name(source_raw)
                    eng_prop = name_map.get(source, source) if source else ""
                    if eng_prop: fields.add(eng_prop)
                
    fields_list = sorted(list(fields))
    fields_xml_list = []
    for f in fields_list:
        fields_xml_list.append(f"""        <Field Name="{f}">
          <DataField>{f}</DataField>
          <rd:TypeName>System.String</rd:TypeName>
        </Field>""")
    fields_xml = "\n".join(fields_xml_list)
    
    # 2. Build report items
    report_items = []
    
    # Calculate Detail Section Height in Inches
    body_height_in = 11.0
    for item in mongo_items:
        if item.get("type") == "section" and item.get("name") == "詳細":
            body_height_in = twips_to_pixels(item.get("properties", {}).get("format", {}).get("height", 15000)) / 96.0 # 96 DPI
            break

    # Sort items so that Z-order and Document Outline order makes sense:
    # 1. OptionGroups/Lines (Background items) first
    # 2. Top-to-bottom, grouping items within roughly the same row (band of ~60 twips)
    # 3. Left-to-right
    def get_sort_key(item):
        itype = item.get("type", "")
        # Rectangles/Lines go first in RDLC so they render at the bottom of the Z-order
        is_bg = 0 if itype in ["OptionGroup", "Frame", "Line", "Rectangle"] else 1
        fmt = item.get("properties", {}).get("format", {})
        top = fmt.get("top", 0)
        left = fmt.get("left", 0)
        # Group Y coordinates into bands of ~60 twips (approx 1mm or 4px) to handle slight misalignments
        top_band = int(top / 60)
        return (is_bg, top_band, left)

    sorted_items = sorted(mongo_items, key=get_sort_key)

    for idx, item in enumerate(sorted_items):
        itype = item.get("type", "")
        if itype in ["section"]:
            continue
            
        props = item.get("properties", {})
        fmt = props.get("format", {})
        data = props.get("data", {})
        
        # Coordinates in Inches
        left_val = fmt.get("left", 0)
        top_val = fmt.get("top", 0)
        
        # Adjust top coordinate for checkbox/option button/toggle button to align with labels
        if itype in ["CheckBox", "OptionButton", "ToggleButton"]:
            top_val = max(0, top_val - 80)

        if itype == "Line":
            width_val = fmt.get("width", 0)
            height_val = fmt.get("height", 0)
        else:
            width_val = fmt.get("width", 1440)
            height_val = fmt.get("height", 360)
        
        left_in = round(left_val / 1440.0, 4)
        top_in = round(top_val / 1440.0, 4)
        width_in = round(width_val / 1440.0, 4)
        height_in = round(height_val / 1440.0, 4)
        
        # Ensure non-zero sizes (except for Line which can be flat horizontal/vertical)
        if itype != "Line":
            if width_in <= 0: width_in = 0.25
            if height_in <= 0: height_in = 0.25
        
        name = item.get("name", f"Item_{idx}")
        mapped_name = name_map.get(name)
        if mapped_name and mapped_name != "TODO" and not mapped_name.startswith("TODO_"):
            ascii_name = re.sub(r'[^a-zA-Z0-9_]', '_', mapped_name)
        else:
            match = re.match(r'^(テキスト|ラベル|直線|フレーム|チェック|コマンド)(\d+)$', name)
            if match:
                prefix, num = match.groups()
                translations = {
                    "テキスト": "Text",
                    "ラベル": "Label",
                    "直線": "Line",
                    "フレーム": "Frame",
                    "チェック": "CheckBox",
                    "コマンド": "Command",
                }
                ascii_name = f"{translations[prefix]}{num}"
            else:
                # Clean name to be valid XML Name attribute
                ascii_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)

        
        if itype == "Label":
            caption = fmt.get("caption", "")
            # Escape XML entities
            caption = caption.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            text_align = textalign_mapping(fmt.get("textalign", 0))
            
            font_name = fmt.get("fontname", "ＭＳ Ｐゴシック")
            font_size_pt = f"{fmt.get('fontsize', 11)}pt"
            font_weight_str = "Bold" if fmt.get("fontweight", 0) >= 700 else "Normal"
            underline_xml = ""
            if fmt.get("fontunderline"):
                underline_xml = "\n                      <TextDecoration>Underline</TextDecoration>"
                
            border_style = "None" if fmt.get("oldborderstyle", 0) == 0 else "Solid"
            border_color_xml = f"<Color>{border_color_hex}</Color>" if border_style != "None" else ""
            
            report_items.append(f"""          <Textbox Name="{ascii_name}">
            <CanGrow>false</CanGrow>
            <KeepTogether>true</KeepTogether>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>{caption}</Value>
                    <Style>
                      <FontFamily>{font_name}</FontFamily>
                      <FontSize>{font_size_pt}</FontSize>
                      <FontWeight>{font_weight_str}</FontWeight>{underline_xml}
                    </Style>
                  </TextRun>
                </TextRuns>
                <Style>
                  <TextAlign>{text_align}</TextAlign>
                </Style>
              </Paragraph>
            </Paragraphs>
            <Top>{top_in}in</Top>
            <Left>{left_in}in</Left>
            <Height>{height_in}in</Height>
            <Width>{width_in}in</Width>
            <Style>
              <Border>
                <Style>{border_style}</Style>
                {border_color_xml}
              </Border>
              <PaddingLeft>0pt</PaddingLeft>
              <PaddingRight>0pt</PaddingRight>
              <PaddingTop>0pt</PaddingTop>
              <PaddingBottom>0pt</PaddingBottom>
            </Style>
          </Textbox>""")
          
        elif itype == "TextBox":
            source_raw = data.get("controlsource", "")
            inputmask = data.get("inputmask", "")
            
            text_align = textalign_mapping(fmt.get("textalign", 0))
            
            value_expr = ""
            if source_raw:
                cleaned = source_raw.strip()
                if not cleaned.startswith("="):
                    cleaned = f"[{cleaned}]"
                else:
                    cleaned = cleaned[1:]
                
                fmt_match = re.search(r'(?i)Format\(\s*\[?([^,\]]+)\]?\s*,\s*(.+)\)', cleaned)
                if fmt_match:
                    field_raw = fmt_match.group(1).split('.')[-1]
                    fmt_str_raw = fmt_match.group(2).strip()
                    fmt_str = fmt_str_raw.strip('"').strip('\\"').strip("'")
                    fmt_str = fmt_str.replace('\\', '')
                    if "yyyy" in fmt_str:
                        fmt_str = fmt_str.replace("m", "M")
                    if "nn" in fmt_str:
                        fmt_str = fmt_str.replace("nn", "mm")
                    if "h" in fmt_str:
                        fmt_str = fmt_str.replace("h", "H")
                    
                    eng_prop = name_map.get(field_raw, field_raw)
                    
                    if fmt_str == "@@@-@@@@":
                        value_expr = f'=IIF(Len(CStr(Fields!{eng_prop}.Value)) >= 7, Left(CStr(Fields!{eng_prop}.Value), 3) & "-" & Right(CStr(Fields!{eng_prop}.Value), 4), Fields!{eng_prop}.Value)'
                    elif ("#" in fmt_str or "0" in fmt_str) and "yyyy" not in fmt_str and "mm" not in fmt_str:
                        value_expr = f'=IIF(IsNumeric(Fields!{eng_prop}.Value), Format(CDbl(Fields!{eng_prop}.Value), "{fmt_str}"), Fields!{eng_prop}.Value)'
                    else:
                        value_expr = f'=IIF(IsDate(Fields!{eng_prop}.Value), Format(CDate(Fields!{eng_prop}.Value), "{fmt_str}"), Fields!{eng_prop}.Value)'
                else:
                    def replacer(match):
                        field_raw = match.group(1).split('.')[-1]
                        eng_prop = name_map.get(field_raw, field_raw)
                        return f"Trim(Fields!{eng_prop}.Value)"
                        
                    expr = re.sub(r'\[([^\]]+)\]', replacer, cleaned)
                    expr = re.sub(r'(?i)Nz\(([^,]+),\s*([^)]+)\)', r'IIF(IsNothing(\1) OR \1 = "", \2, \1)', expr)
                    value_expr = f"={expr}"
                    
                    if inputmask and "時" in inputmask and "分" in inputmask:
                        brackets = re.findall(r'\[([^\]]+)\]', source_raw)
                        if brackets:
                            field_raw = brackets[0].split('.')[-1]
                            eng_prop = name_map.get(field_raw, field_raw)
                            value_expr = f'=IIF(Len(CStr(Fields!{eng_prop}.Value)) >= 3, Left(Right("0000" & CStr(Fields!{eng_prop}.Value), 4), 2) & "時" & Right(CStr(Fields!{eng_prop}.Value), 2) & "分", Fields!{eng_prop}.Value)'

            value_expr = value_expr.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            font_name = fmt.get("fontname", "ＭＳ Ｐゴシック")
            font_size_pt = f"{fmt.get('fontsize', 11)}pt"
            font_weight_str = "Bold" if fmt.get("fontweight", 0) >= 700 else "Normal"
            underline_xml = ""
            if fmt.get("fontunderline"):
                underline_xml = "\n                      <TextDecoration>Underline</TextDecoration>"
            
            border_style = "None" if fmt.get("oldborderstyle") == 0 else "Solid"
            border_color = fmt.get("bordercolor", -2147483617)
            border_color_hex = access_color_to_hex(border_color)
            border_color_xml = f"<Color>{border_color_hex}</Color>" if border_style != "None" else ""
            pad_pt = "0pt"
            
            report_items.append(f"""          <Textbox Name="{ascii_name}">
            <CanGrow>true</CanGrow>
            <KeepTogether>true</KeepTogether>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>{value_expr}</Value>
                    <Style>
                      <FontFamily>{font_name}</FontFamily>
                      <FontSize>{font_size_pt}</FontSize>
                      <FontWeight>{font_weight_str}</FontWeight>{underline_xml}
                    </Style>
                  </TextRun>
                </TextRuns>
                <Style>
                  <TextAlign>{text_align}</TextAlign>
                </Style>
              </Paragraph>
            </Paragraphs>
            <Top>{top_in}in</Top>
            <Left>{left_in}in</Left>
            <Height>{height_in}in</Height>
            <Width>{width_in}in</Width>
            <Style>
              <Border>
                <Style>{border_style}</Style>
                {border_color_xml}
              </Border>
              <PaddingLeft>{pad_pt}</PaddingLeft>
              <PaddingRight>{pad_pt}</PaddingRight>
              <PaddingTop>{pad_pt}</PaddingTop>
              <PaddingBottom>{pad_pt}</PaddingBottom>
            </Style>
          </Textbox>""")
          
        elif itype == "OptionGroup":
            border_style = "None" if fmt.get("oldborderstyle") == 0 else "Solid"
            border_color = fmt.get("bordercolor", -2147483617)
            border_color_hex = access_color_to_hex(border_color)
            border_color_xml = f"<Color>{border_color_hex}</Color>" if border_style != "None" else ""
            
            report_items.append(f"""          <Rectangle Name="{ascii_name}">
            <Top>{top_in}in</Top>
            <Left>{left_in}in</Left>
            <Height>{height_in}in</Height>
            <Width>{width_in}in</Width>
            <Style>
              <Border>
                <Style>{border_style}</Style>
                {border_color_xml}
              </Border>
            </Style>
          </Rectangle>""")
          
        elif itype in ["CheckBox", "OptionButton", "ToggleButton"]:
            # Handle option button/checkbox bound to parent group or standalone
            option_value = data.get("optionvalue")
            parent_key = item.get("parentkey")
            optiongroup_name = props.get("other", {}).get("optiongroupname")
            parent_group = None
            is_in_group = False
            
            if parent_key or optiongroup_name:
                for x in mongo_items:
                    if x.get("type") == "OptionGroup":
                        if parent_key and x.get("key") == parent_key:
                            parent_group = x
                            break
                        if optiongroup_name and x.get("name") == optiongroup_name:
                            parent_group = x
                            break
                if parent_group:
                    is_in_group = True
                    group_data = parent_group.get("properties", {}).get("data", {})
                    source_raw = group_data.get("controlsource", "")
                    source = clean_field_name(source_raw)
                    eng_prop = name_map.get(source, source) if source else ""
                    
            if not is_in_group:
                source_raw = data.get("controlsource", "")
                source = clean_field_name(source_raw)
                eng_prop = name_map.get(source, source) if source else ""
                
            # If dynamic checkbox, render Unicode checked/unchecked box
            if eng_prop:
                if is_in_group and option_value is not None:
                    value_expr = f'=IIF(CStr(Fields!{eng_prop}.Value) = "{option_value}", "☑", "☐")'
                else:
                    value_expr = f'=IIF(CStr(Fields!{eng_prop}.Value) = "☑" Or (CStr(Fields!{eng_prop}.Value) <> "☐" And CStr(Fields!{eng_prop}.Value) <> "" And CStr(Fields!{eng_prop}.Value) <> "0" And CStr(Fields!{eng_prop}.Value) <> "False" And CStr(Fields!{eng_prop}.Value) <> "false"), "☑", "☐")'
            else:
                value_expr = "☐"
                
            border_style = "None" if fmt.get("oldborderstyle", 0) == 0 and fmt.get("borderlinestyle", 0) == 0 else "Solid"
            border_color = fmt.get("bordercolor")
            if border_color is not None:
                border_color_hex = access_color_to_hex(border_color)
            else:
                border_color_hex = "#000000"
            border_color_xml = f"<Color>{border_color_hex}</Color>" if border_style != "None" else ""

            symbol_color_hex = border_color_hex

            font_size_pt = f"{fmt.get('fontsize', 11)}pt"
            font_weight_str = "Bold" if fmt.get("fontweight", 0) >= 700 else "Normal"
            underline_xml = ""
            if fmt.get("fontunderline"):
                underline_xml = "\n                      <TextDecoration>Underline</TextDecoration>"
            
            report_items.append(f"""          <Textbox Name="{ascii_name}">
            <CanGrow>true</CanGrow>
            <KeepTogether>true</KeepTogether>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>{value_expr}</Value>
                    <Style>
                      <FontFamily>Segoe UI Symbol</FontFamily>
                      <FontSize>{font_size_pt}</FontSize>
                      <FontWeight>{font_weight_str}</FontWeight>{underline_xml}
                      <Color>{symbol_color_hex}</Color>
                    </Style>
                  </TextRun>
                </TextRuns>
                <Style>
                  <TextAlign>Left</TextAlign>
                </Style>
              </Paragraph>
            </Paragraphs>
            <Top>{top_in}in</Top>
            <Left>{left_in}in</Left>
            <Height>{height_in}in</Height>
            <Width>{width_in}in</Width>
            <Style>
              <Border>
                <Style>{border_style}</Style>
                {border_color_xml}
              </Border>
              <PaddingLeft>0pt</PaddingLeft>
              <PaddingRight>0pt</PaddingRight>
              <PaddingTop>0pt</PaddingTop>
              <PaddingBottom>0pt</PaddingBottom>
              <VerticalAlign>Top</VerticalAlign>
            </Style>
          </Textbox>""")
          
        elif itype == "Line":
            border_width = fmt.get("borderwidth", 1)
            border_color = fmt.get("bordercolor")
            if border_color is not None:
                border_color_hex = access_color_to_hex(border_color)
            else:
                border_color_hex = "#000000"
            report_items.append(f"""          <Line Name="{ascii_name}">
            <Top>{top_in}in</Top>
            <Left>{left_in}in</Left>
            <Height>{height_in}in</Height>
            <Width>{width_in}in</Width>
            <Style>
              <Border>
                <Style>Solid</Style>
                <Width>{border_width}pt</Width>
                <Color>{border_color_hex}</Color>
              </Border>
            </Style>
          </Line>""")
          
    report_items_str = "\n".join(report_items)
    
    rdlc_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition" xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">
  <Language>ja-JP</Language>
  <AutoRefresh>0</AutoRefresh>
  <DataSources>
    <DataSource Name="ReportDS">
      <ConnectionProperties>
        <DataProvider>System.Data.DataSet</DataProvider>
        <ConnectString>/* Local Connection */</ConnectString>
      </ConnectionProperties>
      <rd:DataSourceID>563fa767-b334-4166-86c8-dcb1629c2b6c</rd:DataSourceID>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="ReportDataSet">
      <Query>
        <DataSourceName>ReportDS</DataSourceName>
        <CommandText>/* Local Query */</CommandText>
      </Query>
      <Fields>
{fields_xml}
      </Fields>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body>
        <Height>{body_height_in:.4f}in</Height>
        <ReportItems>
{report_items_str}
        </ReportItems>
        <Style>
          <Border>
            <Style>None</Style>
          </Border>
        </Style>
      </Body>
      <Width>7.87in</Width>
      <Page>
        <PageHeight>11.69in</PageHeight>
        <PageWidth>8.27in</PageWidth>
        <LeftMargin>0.2in</LeftMargin>
        <RightMargin>0.2in</RightMargin>
        <TopMargin>0.2in</TopMargin>
        <BottomMargin>0.2in</BottomMargin>
        <Style/>
      </Page>
    </ReportSection>
  </ReportSections>
  <rd:ReportUnitType>Inch</rd:ReportUnitType>
</Report>"""
    return rdlc_xml

# ──────────────────────────────────────────
# Dynamic Companion Report Resolver
# ──────────────────────────────────────────

def get_english_report_name(form_name: str) -> str:
    """Read mapping from graphview listFormJpToEn.json to get English report name."""
    mapping_path = BASE_DIR.parent / "graphview" / "outputs" / "forms" / "listFormJpToEn.json"
    if mapping_path.exists():
        try:
            mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
            for item in mapping_data.get("items", []):
                if item.get("access_form_name") == form_name:
                    v_name = item.get("wpf_view_name")
                    if v_name:
                        return v_name[:-4] if v_name.endswith("View") else v_name
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("[tool_report] Failed to parse listFormJpToEn.json: %s", e)
    return form_name

def find_companion_report_name(form_name: str) -> str:
    """Scan the input JSON files dynamically to discover the companion report name (e.g. R005_...) for this Form."""
    json_path = INPUTS_DIR / f"{form_name}_report_input.json"
    if not json_path.exists():
        json_path = INPUTS_DIR / f"{form_name}.json"
    
    raw_text = ""
    if json_path.exists():
        raw_text = json_path.read_text(encoding="utf-8")
        
    # Match [refer: R...] pattern
    pattern = r'\[refer:\s*(R[a-zA-Z0-9_\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\uFF00-\uFFEF\u4E00-\u9FAF_]+)\]'
    matches = re.findall(pattern, raw_text)
    
    if matches:
        extracted = matches[0].strip()
        
        # Try to resolve actual report file in inputs/ folder
        for p in INPUTS_DIR.glob("R*.json"):
            stem = p.stem.replace("_report_input", "").replace("_dd", "").replace("_bd", "")
            if stem == extracted:
                return stem
            
        return extracted
        
    return "R005_作業報告書_支店施工管理_依頼情報のみ"


def parse_pdf_output_vba(vba_code: str) -> dict:
    """Parse VBA code for PDF output to extract metadata."""
    msg = ""
    folder_name = "AMカード（作業依頼書、作業報告書）"
    report_name = ""
    filename_pattern = ""
    
    # Extract MsgBox message
    msg_match = re.search(r'MsgBox\s+"([^"]+)"', vba_code, re.IGNORECASE)
    if msg_match:
        msg = msg_match.group(1)
        
    # Extract FolderName
    folder_match = re.search(r'FolderName\s*=\s*"([^"]+)"', vba_code, re.IGNORECASE)
    if folder_match:
        folder_name = folder_match.group(1)
        
    # Extract Report Name
    report_match = re.search(r'acOutputReport\s*,\s*"([^"]+)"', vba_code, re.IGNORECASE)
    if report_match:
        report_name = report_match.group(1)
        
    # Extract Filename pattern, e.g. FolderName & "\" & Format(Now, "yyyymmdd-hhnn") & "_作業報告書_支店施工管理" & ".pdf"
    pattern_match = re.search(r'FolderName\s*&\s*"\\"\s*&\s*(.*?)\s*&\s*"\.pdf"', vba_code, re.IGNORECASE)
    if pattern_match:
        filename_pattern = pattern_match.group(1).strip()
        
    return {
        "msg": msg,
        "folder_name": folder_name,
        "report_name": report_name,
        "filename_pattern": filename_pattern
    }


def generate_pdf_click_csharp(vba_code: str, form_name: str, handler_name: str, english_companion_report: str) -> str:
    meta = parse_pdf_output_vba(vba_code)
    
    # Resolve the companion/target report name to English
    target_report = meta["report_name"] or form_name
    english_report = get_english_report_name(target_report) if target_report else english_companion_report
    
    # Translate MsgBox message
    msg_box_code = ""
    if meta["msg"]:
        msg_box_code = f'System.Windows.MessageBox.Show("{meta["msg"]}", "通知", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information);'
        
    # Translate FolderName
    folder_name = meta["folder_name"]
    
    # Format pattern mapping:
    # Format(Now, "yyyymmdd-hhnn") & "_作業報告書_支店施工管理" -> $"{DateTime.Now:yyyyMMdd-HHmm}_作業報告書_支店施工管理.pdf"
    csharp_filename = ""
    pattern = meta["filename_pattern"]
    if "Format(Now" in pattern:
        fmt_match = re.search(r'Format\(Now\s*,\s*"([^"]+)"\)', pattern)
        if fmt_match:
            vba_fmt = fmt_match.group(1)
            # Map vba format to C# datetime format
            cs_fmt = vba_fmt.replace("yyyy", "yyyy").replace("mm", "MM").replace("dd", "dd").replace("hh", "HH").replace("nn", "mm").replace("ss", "ss")
            
            # Extract suffix
            suffix_match = re.search(r'&\s*"([^"]+)"', pattern)
            suffix = suffix_match.group(1) if suffix_match else ""
            csharp_filename = f'{{System.DateTime.Now.ToString("{cs_fmt}")}}{suffix}.pdf'
        else:
            csharp_filename = f'{{System.DateTime.Now.ToString("yyyyMMdd-HHmm")}}_作業報告書.pdf'
    else:
        csharp_filename = f'{{System.DateTime.Now.ToString("yyyyMMdd-HHmm")}}_作業報告書.pdf'
        
    return f"""    /// <summary>[{handler_name}] {handler_name}</summary>
    public virtual async System.Threading.Tasks.Task {handler_name}Async()
    {{
        try
        {{
            {msg_box_code}
            string desktopPath = System.IO.Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop), "{folder_name}");
            if (!System.IO.Directory.Exists(desktopPath))
            {{
                System.IO.Directory.CreateDirectory(desktopPath);
            }}
            string fileName = $"{csharp_filename}";
            string fullPath = System.IO.Path.Combine(desktopPath, fileName);

            var report = new Microsoft.Reporting.WinForms.LocalReport();
            report.ReportPath = System.IO.Path.Combine(System.AppContext.BaseDirectory, "Views/Reports/{english_report}Report.rdlc");
            report.DataSources.Add(new Microsoft.Reporting.WinForms.ReportDataSource("ReportDataSet", ReportData));
            byte[] fileBytes = report.Render("PDF");
            await System.IO.File.WriteAllBytesAsync(fullPath, fileBytes);
            System.Windows.MessageBox.Show($"📂 PDFファイルを保存しました:\\n{{fullPath}}", "通知", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information);
        }}
        catch (System.Exception ex)
        {{
            System.Windows.MessageBox.Show($"❌ PDF出力に失敗しました: {{ex.Message}}", "エラー", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error);
        }}
    }}"""

def replace_csharp_method(content: str, method_signature_regex: str, new_method_content: str) -> str:
    """Robustly replace a C# method by counting braces to capture the entire method body."""
    match = re.search(method_signature_regex, content)
    if not match:
        return content
    
    start_idx = match.start()
    brace_start = content.find('{', match.end() - 1)
    if brace_start == -1:
        return content
        
    brace_count = 1
    end_idx = brace_start + 1
    while brace_count > 0 and end_idx < len(content):
        if content[end_idx] == '{':
            brace_count += 1
        elif content[end_idx] == '}':
            brace_count -= 1
        end_idx += 1
        
    if brace_count == 0:
        old_method = content[start_idx:end_idx]
        return content.replace(old_method, new_method_content)
    return content

# ──────────────────────────────────────────
# Form UI Post-processing Patch Engine
# ──────────────────────────────────────────

def patch_existing_ui(form_name: str, mongo_procedures: list[dict] | None = None) -> list[GeneratedFile]:
    """Read and patch the existing WPF View, Codebehind, and ViewModel files generated by agent_ui to wire up RDLC preview & export actions."""
    generated_files = []
    
    companion_report = find_companion_report_name(form_name)
    english_companion_report = get_english_report_name(companion_report)
    logger.info("[tool_report] Dynamically matched companion report: %s -> %s for %s", companion_report, english_companion_report, form_name)
    
    # Read mapping from graphview
    mapping_path = BASE_DIR.parent / "graphview" / "outputs" / "forms" / "listFormJpToEn.json"
    view_name_stem = form_name
    vm_name_stem = form_name
    if mapping_path.exists():
        try:
            mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
            for item in mapping_data.get("items", []):
                if item.get("access_form_name") == form_name:
                    v_name = item.get("wpf_view_name")
                    if v_name:
                        view_name_stem = v_name
                    vm_name = item.get("wpf_viewmodel_name")
                    if vm_name:
                        vm_name_stem = vm_name
                    break
        except Exception as e:
            logger.warning("[tool_report] Failed to parse listFormJpToEn.json: %s", e)
    
    # 1. Resolve paths (support both {form_name} and {form_name}View naming conventions)
    xaml_candidates = [
        WPF_PROJECT_DIR / "Views" / f"{view_name_stem}.xaml",
    ]
    cs_candidates = [
        WPF_PROJECT_DIR / "Views" / f"{view_name_stem}.xaml.cs",
    ]
    vm_candidates = [
        WPF_PROJECT_DIR / "ViewModels" / f"{vm_name_stem}.cs",
    ]

    xaml_path = next((p for p in xaml_candidates if p.exists()), xaml_candidates[0])
    cs_path = next((p for p in cs_candidates if p.exists()), cs_candidates[0])
    vm_path = next((p for p in vm_candidates if p.exists()), vm_candidates[0])
    
    # Load previous patch state for idempotency
    patch_state_file = OUTPUTS_DIR / "patch_state.json"
    patch_state = {}
    if patch_state_file.exists():
        try:
            patch_state = json.loads(patch_state_file.read_text(encoding="utf-8"))
        except:
            pass
    if form_name not in patch_state:
        patch_state[form_name] = {}
    
    # 2. Patch XAML View
    if xaml_path.exists():
        content = xaml_path.read_text(encoding="utf-8")
        if 'reportHost' in content:
            # Revert the XAML patch to restore original clean layout
            pattern = r'(?s)<Grid.RowDefinitions>\s*<RowDefinition Height="Auto"/>\s*<RowDefinition Height="\*"/>\s*</Grid.RowDefinitions>\s*<!-- Control buttons row -->\s*<Border Grid\.Row="0"[^>]*>\s*<Grid>\s*(.*?)\s*</Grid>\s*</Border>\s*<!-- Preview panel hosting WindowsFormsHost and ReportViewer -->\s*<Border Grid\.Row="1"[^>]*>\s*<WindowsFormsHost x:Name="reportHost"[^>]*/>\s*</Border>'
            content = re.sub(pattern, r'\1', content)
            content = content.replace('\n        xmlns:rv="clr-namespace:Microsoft.Reporting.WinForms;assembly=Microsoft.ReportViewer.WinForms"', '')
            content = content.replace('Width="850" Height="700"', 'SizeToContent="WidthAndHeight"')
            
            generated_files.append(GeneratedFile(
                path=f"Views/{xaml_path.name}",
                content=content,
                generator="patch_view_xaml",
                agent="report"
            ))

    # 3. Patch Codebehind
    if cs_path.exists():
        content = cs_path.read_text(encoding="utf-8")
        loaded_sig = r'private (?:async )?void F000_Loaded\s*\(\s*object\s+sender\s*,\s*RoutedEventArgs\s+e\s*\)'
        if re.search(loaded_sig, content):
            vm_class_name = form_name
            if vm_path.exists():
                vm_content = vm_path.read_text(encoding="utf-8")
                class_match = re.search(r'public\s+class\s+(\w+)', vm_content)
                if class_match:
                    vm_class_name = class_match.group(1)

            patched_method = f"""private async void F000_Loaded(object sender, RoutedEventArgs e)
    {{
        if (!System.ComponentModel.DesignerProperties.GetIsInDesignMode(this))
        {{
            if (this.DataContext is ViewModels.{vm_class_name} viewModel)
            {{
                // 1. Fetch data from service
                await viewModel.F000Async();

                // 2. Open preview window in a separate window
                var reportPath = System.IO.Path.Combine(
                    System.AppContext.BaseDirectory,
                    "Views/Reports/{english_companion_report}Report.rdlc"
                );
                var previewWin = new Views.Reports.ReportPreviewWindow(reportPath, viewModel.ReportData);
                previewWin.Owner = System.Windows.Window.GetWindow(this);
                previewWin.Show();
            }}
        }}
    }}"""
            content = replace_csharp_method(content, loaded_sig, patched_method)
            
        generated_files.append(GeneratedFile(
            path=f"Views/{cs_path.name}",
            content=content,
            generator="patch_codebehind",
            agent="report"
        ))

    # 4. Patch ViewModel
    if vm_path.exists():
        content = vm_path.read_text(encoding="utf-8")
        
        # Load state
        state_file = OUTPUTS_DIR / "patch_state.json"
        patch_state = {}
        if state_file.exists():
            try:
                patch_state = json.loads(state_file.read_text(encoding="utf-8"))
            except:
                pass
        
        if form_name not in patch_state:
            patch_state[form_name] = {}

        def safe_replace(c, old_s, new_s):
            if old_s in c:
                return c.replace(old_s, new_s)
            old_rn = old_s.replace('\n', '\r\n')
            new_rn = new_s.replace('\n', '\r\n')
            if old_rn in c:
                return c.replace(old_rn, new_rn)
            return c

        content = content.replace('PDF出力Command = Cmd(_ => { });', 'PDF出力Command = Cmd(async _ => await PDF出力_ClickAsync());')
        content = content.replace('印刷するCommand = Cmd(_ => { });', '印刷するCommand = Cmd(async _ => await 印刷する_ClickAsync());')
        content = content.replace('閉じるCommand = Cmd(_ => { });', '閉じるCommand = Cmd(async _ => await 閉じる_ClickAsync());')

        # ── Inject IR005 service into constructor & add ReportData field ──────────
        # Replace parameterless constructor with service-injected version
        import re as _re
        # Add using / field declarations before class body opening if not already present
        service_usings = (
            "using System.Collections.Generic;\r\n"
            "using System.Windows;\r\n"
            "using vba_brain.Application.Interfaces;\r\n"
            "using vba_brain.Domain.DTOs.BuildingAfterCollection;\r\n"
        )
        if "IR005_作業報告書_支店施工管理Service" not in content:
            # Prepend service usings at top (after existing usings)
            content = service_usings + content
            # Add private field + RegistrationNumberBf property after class opening brace
            class_open_pat = _re.compile(r'(public class \S+ : ViewModelBase\s*\{)', _re.DOTALL)
            field_block = (
                "\r\n    private readonly IR005_作業報告書_支店施工管理Service _r005Service;\r\n"
                "\r\n    /// <summary>登録番号 (caller sets this before opening window)</summary>\r\n"
                "    public string RegistrationNumberBf { get; set; } = string.Empty;\r\n"
                "\r\n    /// <summary>Report data retrieved from service on Form_Open</summary>\r\n"
                "    public List<GenerateConstructionReportDto> ReportData { get; set; } = new();\r\n"
            )
            content = class_open_pat.sub(lambda m: m.group(0) + field_block, content)
            # Inject service param into constructor and assign field
            ctor_pat = _re.compile(r'public (\w+)\(\)\s*\{', _re.DOTALL)
            content = ctor_pat.sub(
                lambda m: f'public {m.group(1)}(IR005_作業報告書_支店施工管理Service r005Service)\r\n    {{\r\n        _r005Service = r005Service;',
                content
            )

        # ── Patch F000Async ───────────────────────────────────────────────────────
        f000_placeholder = """    /// <summary>[F000] Form_Open</summary>
    public virtual async System.Threading.Tasks.Task F000Async()
    {
    }"""
        f000_implementation = """    /// <summary>[F000] Form_Open — load report data from service</summary>
    public virtual async System.Threading.Tasks.Task F000Async()
    {
        try
        {
            // 1. Call service to fetch construction report data
            var result = await _r005Service.OnClickAsync(RegistrationNumberBf);

            // 2. Handle result
            if (!result.Success)
            {
                System.Windows.MessageBox.Show(result.Message ?? "データの取得に失敗しました。",
                    "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // 3. Store data for use in PDF/Print actions
            ReportData = result.Data ?? new List<GenerateConstructionReportDto>();
        }
        catch (System.Exception ex)
        {
            System.Windows.MessageBox.Show($"データ取得中にエラーが発生しました：{ex.Message}",
                "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }"""
        prev_f000 = patch_state[form_name].get("F000Async", f000_placeholder)
        content = safe_replace(content, prev_f000, f000_implementation)
        content = safe_replace(content, f000_placeholder, f000_implementation)
        patch_state[form_name]["F000Async"] = f000_implementation

        # ── Patch PDF click handlers ───────────────────────────────────────────────
        pdf_procs = []
        if mongo_procedures:
            for proc in mongo_procedures:
                handler = proc.get("handler", "")
                if "PDF出力" in handler and handler.endswith("_Click"):
                    pdf_procs.append(proc)

        if pdf_procs:
            for proc in pdf_procs:
                handler = proc.get("handler")
                vba_code = proc.get("code", "")
                
                pdf_click_placeholder = f"""    /// <summary>[{handler}] {handler}</summary>
    public virtual async System.Threading.Tasks.Task {handler}Async()
    {{
    }}"""
                pdf_click_implementation = generate_pdf_click_csharp(vba_code, form_name, handler, english_companion_report)
                
                prev_pdf = patch_state[form_name].get(f"{handler}Async", pdf_click_placeholder)
                content = safe_replace(content, prev_pdf, pdf_click_implementation)
                content = safe_replace(content, pdf_click_placeholder, pdf_click_implementation)
                patch_state[form_name][f"{handler}Async"] = pdf_click_implementation
        else:
            # Fallback to default PDF出力_ClickAsync
            pdf_click_placeholder = """    /// <summary>[PDF出力_Click] PDF出力_Click</summary>
    public virtual async System.Threading.Tasks.Task PDF出力_ClickAsync()
    {
    }"""
            pdf_click_implementation = """    /// <summary>[PDF出力_Click] PDF出力_Click</summary>
    public virtual async System.Threading.Tasks.Task PDF出力_ClickAsync()
    {
        try
        {
            var report = new Microsoft.Reporting.WinForms.LocalReport();
            report.ReportPath = System.IO.Path.Combine(System.AppContext.BaseDirectory, "Views/Reports/{companion_report}Report.rdlc");

            // Bind real data fetched in F000Async via service
            report.DataSources.Add(new Microsoft.Reporting.WinForms.ReportDataSource("ReportDataSet", ReportData));

            byte[] fileBytes = report.Render("PDF");
            var desktopPath = System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop);
            var fullPath = System.IO.Path.Combine(desktopPath, "{companion_report}.pdf");
            await System.IO.File.WriteAllBytesAsync(fullPath, fileBytes);

            System.Windows.MessageBox.Show($"✅ PDFをデスクトップに出力しました:\\n{fullPath}", "通知", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information);
        }
        catch (System.Exception ex)
        {
            System.Windows.MessageBox.Show($"❌ PDF出力に失敗しました: {ex.Message}", "エラー", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error);
        }
    }""".replace('{companion_report}', english_companion_report)
            prev_pdf = patch_state[form_name].get("PDF出力_ClickAsync", pdf_click_placeholder)
            content = safe_replace(content, prev_pdf, pdf_click_implementation)
            content = safe_replace(content, pdf_click_placeholder, pdf_click_implementation)
            patch_state[form_name]["PDF出力_ClickAsync"] = pdf_click_implementation


        # ── Patch 印刷する_ClickAsync ─────────────────────────────────────────────
        print_click_placeholder = """    /// <summary>[印刷する_Click] 印刷する_Click</summary>
    public virtual async System.Threading.Tasks.Task 印刷する_ClickAsync()
    {
    }"""
        print_click_implementation = """    /// <summary>[印刷する_Click] 印刷する_Click</summary>
    public virtual async System.Threading.Tasks.Task 印刷する_ClickAsync()
    {
        try
        {
            var report = new Microsoft.Reporting.WinForms.LocalReport();
            report.ReportPath = System.IO.Path.Combine(System.AppContext.BaseDirectory, "Views/Reports/{companion_report}Report.rdlc");

            // Bind real data fetched in F000Async via service
            report.DataSources.Add(new Microsoft.Reporting.WinForms.ReportDataSource("ReportDataSet", ReportData));

            byte[] fileBytes = report.Render("PDF");
            var tempFile = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "Print_Temp.pdf");
            await System.IO.File.WriteAllBytesAsync(tempFile, fileBytes);

            var printProcess = new System.Diagnostics.Process
            {
                StartInfo = new System.Diagnostics.ProcessStartInfo
                {
                    FileName = tempFile,
                    UseShellExecute = true,
                    Verb = "print"
                }
            };
            printProcess.Start();
        }
        catch (System.Exception ex)
        {
            System.Windows.MessageBox.Show($"❌ 印刷に失敗しました: {ex.Message}", "エラー", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error);
        }
    }""".replace('{companion_report}', english_companion_report)
        prev_print = patch_state[form_name].get("印刷する_ClickAsync", print_click_placeholder)
        content = safe_replace(content, prev_print, print_click_implementation)
        content = safe_replace(content, print_click_placeholder, print_click_implementation)
        patch_state[form_name]["印刷する_ClickAsync"] = print_click_implementation

        # ── Patch 閉じる_ClickAsync ───────────────────────────────────────────────
        close_click_placeholder = """    /// <summary>[閉じる_Click] 閉じる_Click</summary>
    public virtual async System.Threading.Tasks.Task 閉じる_ClickAsync()
    {
    }"""
        close_click_implementation = """    /// <summary>[閉じる_Click] 閉じる_Click</summary>
    public virtual async System.Threading.Tasks.Task 閉じる_ClickAsync()
    {
        foreach (System.Windows.Window window in System.Windows.Application.Current.Windows)
        {
            if (window.DataContext == this)
            {
                window.Close();
                break;
            }
        }
    }"""
        prev_close = patch_state[form_name].get("閉じる_ClickAsync", close_click_placeholder)
        content = safe_replace(content, prev_close, close_click_implementation)
        content = safe_replace(content, close_click_placeholder, close_click_implementation)
        patch_state[form_name]["閉じる_ClickAsync"] = close_click_implementation

        # Save state
        state_file.write_text(json.dumps(patch_state, ensure_ascii=False, indent=2), encoding="utf-8")

        generated_files.append(GeneratedFile(
            path=f"ViewModels/{vm_path.name}",
            content=content,
            generator="patch_viewmodel",
            agent="report"
        ))
    # Ensure ReportPreviewWindow is added
    preview_xaml_content = """<Window x:Class="vba_brain.UI.WPF.Views.Reports.ReportPreviewWindow"
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        xmlns:wfi="clr-namespace:System.Windows.Forms.Integration;assembly=WindowsFormsIntegration"
        Title="印刷プレビュー" Width="850" Height="900"
        WindowStartupLocation="CenterOwner">
    <Grid>
        <wfi:WindowsFormsHost x:Name="reportHost" Margin="0"/>
    </Grid>
</Window>"""

    preview_cs_content = """using System;
using System.Collections.Generic;
using System.Windows;

namespace vba_brain.UI.WPF.Views.Reports
{
    public partial class ReportPreviewWindow : Window
    {
        public ReportPreviewWindow(string reportPath, object reportData)
        {
            InitializeComponent();
            
            if (!System.ComponentModel.DesignerProperties.GetIsInDesignMode(this))
            {
                var reportViewer = new Microsoft.Reporting.WinForms.ReportViewer();
                reportViewer.SetDisplayMode(Microsoft.Reporting.WinForms.DisplayMode.PrintLayout);
                reportViewer.ZoomMode = Microsoft.Reporting.WinForms.ZoomMode.PageWidth;
                reportViewer.ZoomPercent = 100;
                reportHost.Child = reportViewer;

                reportViewer.LocalReport.ReportPath = reportPath;
                reportViewer.LocalReport.DataSources.Clear();
                reportViewer.LocalReport.DataSources.Add(
                    new Microsoft.Reporting.WinForms.ReportDataSource("ReportDataSet", reportData)
                );
                reportViewer.RefreshReport();
            }
        }
    }
}"""
    
    generated_files.append(GeneratedFile(
        path="Views/Reports/ReportPreviewWindow.xaml",
        content=preview_xaml_content,
        generator="report_preview_window_xaml",
        agent="report"
    ))
    generated_files.append(GeneratedFile(
        path="Views/Reports/ReportPreviewWindow.xaml.cs",
        content=preview_cs_content,
        generator="report_preview_window_cs",
        agent="report"
    ))

    return generated_files

# ──────────────────────────────────────────
# File Writers & Output Coordinator
# ──────────────────────────────────────────

def save_input_snapshot(form_name: str, data: dict) -> None:
    """Save input data snapshot for debugging."""
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = INPUTS_DIR / f"{form_name}_report_input.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_outputs(form_name: str, files: list[GeneratedFile]) -> None:
    """Save generated output files locally and into the C# source directory."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    
    for gf in files:
        # Convert generated C# from WPF → Avalonia (namespaces, usings, MessageBox)
        if gf.path.endswith(".cs"):
            try:
                from pipeline.avalonia_cs import to_avalonia_cs
                gf.content = to_avalonia_cs(gf.content)
            except Exception:
                pass
        # 1. Save locally flatly under outputs/{form_name}/
        local_filename = Path(gf.path).name
        local_path = OUTPUTS_DIR / form_name / local_filename
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(gf.content, encoding="utf-8")
        
        # 2. Write to C# project source
        if WPF_PROJECT_DIR.exists():
            dest_path = WPF_PROJECT_DIR / gf.path
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_text(gf.content, encoding="utf-8")
                logger.info("[tool_report] Saved to C# source: %s", dest_path)
            except Exception as ex:
                logger.warning("[tool_report] Failed to write to source %s: %s", dest_path, ex)
        else:
            logger.warning("[tool_report] C# WPF project source dir not found: %s", WPF_PROJECT_DIR)
