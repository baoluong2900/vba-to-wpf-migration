from __future__ import annotations
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

EVENT_TRIGGER_JA: dict[str, str] = {
    "onopen": "On Open",
    "onload": "On Load",
    "onclose": "On Close",
    "onunload": "On Unload",
    "onclick": "On Click",
    "ondblclick": "On Double Click",
    "oncurrent": "On Current",
    "beforeinsert": "Before Insert",
    "afterinsert": "After Insert",
    "beforeupdate": "Before Update",
    "afterupdate": "After Update",
    "ondelete": "On Delete",
    "beforedelete": "Before Delete",
    "afterdelconfirm": "After Delete Confirm",
    "onerror": "On Error",
    "onfilter": "On Filter",
    "ongotfocus": "On Got Focus",
    "onlostfocus": "On Lost Focus",
    "onchange": "On Change",
    "onkeypress": "On Key Press",
    "onkeydown": "On Key Down",
    "onkeyup": "On Key Up",
    "onmousedown": "On Mouse Down",
}

ACCESS_FORMAT_MAP: dict[str, str] = {
    "Short Date": "YYYY/MM/DD",
    "Long Date": "YYYY年MM月DD日",
    "Medium Date": "DD-MM-YY",
    "General Date": "YYYY/MM/DD HH:MM:SS",
    "Long Time": "HH:MM:SS",
    "Medium Time": "HH:MM AM/PM",
    "Short Time": "HH:MM",
    "General Number": "###0.000",
    "Currency": "¥#,##0",
    "Euro": "€#,##0",
    "Fixed": "0.00",
    "Standard": "#,##0.00",
    "Percent": "0.00%",
    "Scientific": "0.00E+00",
    "True/False": "True/False",
    "Yes/No": "Yes/No",
    "On/Off": "On/Off",
}

STRUCT_TYPES = frozenset({"formheader", "section", "formfooter"})
SKIP_TYPES_SHEET3 = frozenset({"Rectangle", "Line", "Image", "PageBreak"})
FILE_QUERY_HINTS = ("excel", "csv", "出力", "エクスポート", "吐き出し", "import", "export")
TABLE_UPDATE_HINTS = ("更新", "削除", "追加", "作成", "変更", "リセット", "insert", "update", "delete")
OUTPUT_TO_RE = re.compile(
    r"DoCmd\.OutputTo\s+([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*(.+)",
    re.IGNORECASE,
)
TRANSFER_SPREADSHEET_RE = re.compile(
    r"DoCmd\.TransferSpreadsheet\s+([^,]*)\s*,\s*([^,]*)\s*,\s*([^,]+)\s*,\s*([^,]+)",
    re.IGNORECASE,
)
TRANSFER_TEXT_RE = re.compile(
    r"DoCmd\.TransferText\s+([^,]*)\s*,\s*([^,]*)\s*,\s*([^,]+)\s*,\s*([^,]+)",
    re.IGNORECASE,
)
FILE_EXT_MAP = {
    "acformatpdf": ".pdf",
    "acformatxls": ".xls",
    "acformatxlsx": ".xlsx",
    "acformatxlsb": ".xlsb",
    "acformattext": ".txt",
    "acformattxt": ".txt",
    "acformatcsv": ".csv",
}

SUBFORM_DOC_MAP: dict[str, str] = {
    "F021_NavigationButtons": "Form.F021_NavigationButtons",
}

TYPE_MAP = {
    "Form": "Form",
    "CommandButton": "Command Button",
    "TextBox": "Text Box",
    "ComboBox": "Combo Box",
    "Label": "Label",
    "Subform": "Subform",
    "OptionGroup": "Option Group",
    "CheckBox": "Check Box",
    "ListBox": "List Box",
    "Image": "Image",
    "Line": "Line",
    "Rectangle": "Rectangle",
    "PageBreak": "Page Break",
    "TabControl": "Tab Control",
    "OptionButton": "Option Button",
    "ToggleButton": "Toggle Button",
    "Tab": "Tab",
    "Chart": "Chart",
}

ATTR_PREFIX = {
    "TextBox": "txt",
    "CommandButton": "cmd",
    "Label": "lbl",
    "ComboBox": "cmb",
    "ListBox": "lst",
    "CheckBox": "chk",
    "OptionGroup": "grp",
    "Subform": "sub",
    "Image": "img",
    "OptionButton": "opt",
    "ToggleButton": "tgb",
    "Tab": "tab",
    "TabControl": "tabctrl",
    "Line": "line",
    "Rectangle": "rect",
    "PageBreak": "pagebreak",
    "Chart": "chart",
}

ACTION_TYPES = [
    {"key": "READ", "description": "Read data from DB, search."},
    {"key": "CREATE", "description": "Insert new data."},
    {"key": "UPDATE", "description": "Update data."},
    {"key": "DELETE", "description": "Delete data."},
    {"key": "NAV", "description": "Navigate screen, close/open form."},
    {"key": "UI", "description": "Change display, hide/show, UI colors."},
    {"key": "VALID", "description": "Validation, input error messages."},
    {"key": "FILE", "description": "Excel/CSV file operations (Import/Export)."},
    {"key": "SYS", "description": "System operations (Clipboard, Registry, Taskkill)."},
    {"key": "ETC", "description": "Other logic processing."}
]
