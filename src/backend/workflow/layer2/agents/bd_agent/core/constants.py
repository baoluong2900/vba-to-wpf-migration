from __future__ import annotations
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

EVENT_TRIGGER_JA: dict[str, str] = {
    "onopen": "画面を開く時",
    "onload": "フォーム読み込み後",
    "onclose": "フォームを閉じる時",
    "onunload": "アンロード時",
    "onclick": "クリック時",
    "ondblclick": "ダブルクリック時",
    "oncurrent": "レコード変更時",
    "beforeinsert": "レコード挿入前",
    "afterinsert": "レコード挿入後",
    "beforeupdate": "更新直前処理",
    "afterupdate": "更新後処理",
    "ondelete": "削除時",
    "beforedelete": "削除前",
    "afterdelconfirm": "削除確認後",
    "onerror": "エラー発生時",
    "onfilter": "フィルタ時",
    "ongotfocus": "フォーカス取得時",
    "onlostfocus": "フォーカス喪失時",
    "onchange": "変更時",
    "onkeypress": "キー入力時",
    "onkeydown": "キー押下時",
    "onkeyup": "キー離上時",
    "onmousedown": "マウス押下時",
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
    "Form": "フォーム",
    "CommandButton": "コマンドボタン",
    "TextBox": "テキストボックス",
    "ComboBox": "コンボボックス",
    "Label": "ラベル",
    "Subform": "サブフォーム",
    "OptionGroup": "オプショングループ",
    "CheckBox": "チェックボックス",
    "ListBox": "リストボックス",
    "Image": "イメージ",
    "Line": "ライン",
    "Rectangle": "矩形",
    "PageBreak": "改ページ",
    "TabControl": "タブコントロール",
    "OptionButton": "オプョンボタン",
    "ToggleButton": "トグルボタン",
    "Tab": "タブ",
    "Chart": "チャート",
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
    {"key": "READ", "description": "Đọc dữ liệu từ DB, tìm kiếm."},
    {"key": "CREATE", "description": "Thêm mới dữ liệu."},
    {"key": "UPDATE", "description": "Cập nhật dữ liệu."},
    {"key": "DELETE", "description": "Xóa dữ liệu."},
    {"key": "NAV", "description": "Chuyển màn hình, đóng/mở form."},
    {"key": "UI", "description": "Thay đổi hiển thị, ẩn/hiện, màu sắc UI."},
    {"key": "VALID", "description": "Kiểm tra hợp lệ, thông báo lỗi nhập liệu."},
    {"key": "FILE", "description": "Thao tác File Excel/CSV (Import/Export)."},
    {"key": "SYS", "description": "Thao tác hệ thống (Clipboard, Registry, Taskkill)."},
    {"key": "ETC", "description": "Các xử lý logic khác."}
]
