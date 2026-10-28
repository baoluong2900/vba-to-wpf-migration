"""Japanese → English translation for filled Layer 4 workbooks.

The target language comes from ``common.config.TARGET_LANGUAGE`` (config.json →
``localization.target_language``, overridable with the ``TARGET_LANGUAGE`` env var).

Only template text is translated: ``snapshot_template_labels`` records the label cells of
a freshly loaded template, and ``translate_workbook`` rewrites exactly those cells plus the
template part of sheet titles once the workbook is filled. Values written by the fill
scripts and formula cells are never changed; formulas that reference a renamed sheet are
re-pointed at its new title.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

JP_REGEX = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]')

JP_EN_MAPPING = {
    # General terms / change history
    "ページ": "Page",
    "更新": "Update",
    "備    考": "Notes",
    "MONOSビルOM出荷": "MONOS Building OM Shipment",
    "補修部品": "Repair Parts",
    "出荷実績_当日": "Shipment_Result_Today",
    "出荷実績入力": "Shipment Result Input",

    "変更履歴": "Change History",
    "改訂": "Revision",
    "初版": "First Edition",
    "更新内容": "Update Content",
    "更新日": "Update Date",
    "更新者": "Updated By",
    "作成者": "Author",
    "作成日": "Created Date",
    "備考": "Notes",
    "更新理由/案件番号": "Reason for Update / Project No",
    "システム名": "System Name",
    "サブシステム名": "Sub-system Name",
    "プロジェクト名": "Project Name",
    "承認者": "Approver",

    # Common terms
    "＜レコードソース＞": "Record Source",
    "レコードソース": "Record Source",
    "レコード": "Record",
    "処理概要": "Process Overview",
    "画面項目名": "Screen Item Name",
    "項目\n属性": "Field Attribute",
    "属性\n桁数": "Length",
    "出力仕様": "Output Specification",
    "●タイミング：": "●Timing:",
    "タイミング": "Timing",
    "内容": "Content",
    "処理": "Process",
    "書式": "Format",
    "（レイアウト）": "(Layout)",
    "(レイアウト)": "(Layout)",
    "（論理名）": "(Logical)",
    "（物理名）": "(Physical)",
    "（項目編集）": "(Field Edit)",
    "（画面編集）": "(Screen Edit)",
    "転送元": "Source",
    "ﾃｰﾌﾞﾙ名/領域名": "Table Name / Region",

    # Layout Sheet
    "画面仕様書(レイアウト)": "Screen Spec (Layout)",
    "画面仕様書 （レイアウト）": "Screen Spec (Layout)",
    "帳票仕様書(レイアウト)": "Report Spec (Layout)",
    "帳票仕様書 （レイアウト）": "Report Spec (Layout)",
    "画面仕様書(画面編集)": "Screen Spec (Edit)",
    "画面仕様書 （画面編集）": "Screen Spec (Edit)",
    "帳票仕様書（項目編集）": "Report Spec (Field Edit)",
    "画面仕様書（項目編集）": "Screen Spec (Field Edit)",
    "画面ID": "Screen ID",
    "画面名": "Screen Name",
    "帳票ID": "Report ID",
    "帳票名": "Report Name",
    "イメージ": "Image",
    "●機能概要：": "●Functional Overview:",
    "●制約事項：": "●Constraints:",
    "イベントID": "Event ID",
    "名前（論理）": "Logical Name",
    "名前（物理）": "Physical Name",
    "種類": "Control Type",
    "標題": "Caption/Label",
    "イベント": "Event Trigger",
    "遷移先": "Transition Target",

    # Edit/Field Sheet
    "画面項目名 （論理名）": "Screen Item (Logical Name)",
    "画面項目名 （物理名）": "Screen Item (Physical Name)",
    "項目 属性": "Field Attribute/Type",
    "属性 桁数": "Length",
    "必須": "Required",
    "桁数": "Digits",
    "形式": "Format",
    "入力仕様": "Input Specification",
    "その他入力値チェック": "Validation Rules/Checks",
    "条  件  及  び  編  集  方  法": "Conditions & Editing Methods",
    "ﾃｰﾌﾞﾙ名／領域名": "Table Name / Region",
    "テーブル名": "Table Name",
    "項目名": "Item Name",
    "転  送  元": "Source",
    "項目名／固定値": "Field Name / Fixed Value",
    "転送元　領域名": "Source Region Name",
    "転送元　項目名/固定値": "Source Field / Fixed Value",

    # Table Update Sheet (E***)
    "画面仕様書（テーブル更新）": "Screen Spec (Table Update)",
    "テーブル名(物理名)": "Table Name (Physical)",
    "テーブル(論理名)": "Table Name (Logical)",
    "テーブルID": "Table ID",
    "項目名（物理名）": "Field Name (Physical)",
    "項目名（論理名）": "Field Name (Logical)",

    # DD specific
    "プログラム・モジュール仕様書": "Program/Module Specification",
    "詳細仕様書": "Detailed Design Spec",
    "概要仕様書": "Overview Spec",
    "画面仕様書": "Screen Spec",
    "帳票仕様書": "Report Spec",
    "ファイル仕様書": "File Spec",
    "仕様書": "Spec",
    "モジュールID": "Module ID",
    "モジュール名": "Module Name",
    "概要": "Overview",
    "処理記述": "Process Description",
    "初期処理": "Initialization Process",
    "条件解除処理": "Condition Clear Process",
    "実績確定処理": "Result Commit Process",
    "入力データ欄": "Input Data Section",
    "表示名": "Display Name",
    "カラム名": "Column Name",
    "Query名": "Query Name",
    "SELECT句": "SELECT Clause",
    "パラメータ": "Parameters",

    # Detailed mappings to fix mixed Japanese-English replacements
    "パラメータ情報": "Parameters Info",
    "引数情報": "Arguments Info",
    "項目名称": "Item Name / Label",
    "シンボル名": "Symbol Name",
    "戻り値": "Return Value",
    "全体桁": "Total Digits",
    "小数桁": "Decimal Digits",
    "特記事項": "Special Notes",
    "制約事項": "Constraints",
    "機能概要": "Functional Overview",
    "名称": "Name",
    "引数": "Arguments",
    "説明": "Description",
    "型": "Type",
    "コード": "Code",
    "タイプ": "Type",
    "サブ": "Sub",
    "情報": "Information",
}

# Longest keys first so compound labels win over their parts.
_SORTED_MAPPING = sorted(JP_EN_MAPPING.items(), key=lambda kv: len(kv[0]), reverse=True)

# Template sheet titles, and title prefixes of per-event / per-module sheets.
SHEET_TITLES = {
    "変更履歴": "Change History",
    "概要仕様書": "Overview Spec",
    "画面仕様書(レイアウト)": "Screen Spec (Layout)",
    "画面仕様書(画面編集)": "Screen Spec (Edit)",
    "画面仕様書（テーブル更新）": "Screen Spec (Table Update)",
    "帳票仕様書(レイアウト)": "Report Spec (Layout)",
    "帳票仕様書（項目編集）": "Report Spec (Field Edit)",
}
SHEET_TITLE_PREFIXES = (
    ("画面仕様書（", "Screen Spec（"),
    ("ファイル仕様書（", "File Spec（"),
    ("詳細仕様書_", "Detailed Design Spec_"),
)

_INVALID_TITLE_CHARS = re.compile(r'[\\*?:/\[\]]')


def get_target_language() -> str:
    """Target language from ``common.config`` — the single source for all of Layer 4."""
    try:
        from common.config import TARGET_LANGUAGE
    except ImportError:
        # CLI run from scripts/: make src/backend importable.
        backend_dir = Path(__file__).resolve().parents[3]
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from common.config import TARGET_LANGUAGE
    return str(TARGET_LANGUAGE or "").strip() or "en"


def is_english_target() -> bool:
    return get_target_language().lower() in ("en", "english")


def translate_text(text: str) -> str:
    """Substring-translate ``text`` with ``JP_EN_MAPPING`` (pure; ignores the target language)."""
    for jp, en in _SORTED_MAPPING:
        if jp in text:
            text = text.replace(jp, en)
    return text


def translate_label(text: str) -> str:
    """Translate a label the fill code writes itself (never use this for JSON values)."""
    return translate_text(text) if is_english_target() else text


def translate_sheet_title(title: str) -> str:
    """English title for a template-derived sheet; the JSON-supplied part stays as is."""
    if title in SHEET_TITLES:
        new = SHEET_TITLES[title]
    else:
        for jp, en in SHEET_TITLE_PREFIXES:
            if title.startswith(jp):
                new = en + title[len(jp):]
                break
        else:
            return title
    return _INVALID_TITLE_CHARS.sub("", new)[:31].strip()


def _quote_sheet(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def retarget_formula_refs(wb, renames: dict[str, str]) -> None:
    """Re-point formulas at renamed sheets (``=概要仕様書!E1`` → ``='Overview Spec'!E1``)."""
    if not renames:
        return
    subs = []
    for old, new in renames.items():
        target = _quote_sheet(new) + "!"
        subs.append((re.compile(re.escape(_quote_sheet(old)) + "!"), target))
        subs.append((re.compile(r"(?<![\w.'\]])" + re.escape(old) + "!"), target))
    for ws in wb.worksheets:
        for cell in ws._cells.values():
            value = cell.value
            if cell.data_type != "f" or not isinstance(value, str):
                continue
            new_value = value
            for pattern, target in subs:
                new_value = pattern.sub(lambda _m, t=target: t, new_value)
            if new_value != value:
                cell.value = new_value


class TemplateLabels:
    """Label cells of a freshly loaded template (see ``translate_workbook``)."""

    def __init__(self, wb) -> None:
        # Keep the sheet / cell objects alive so their ids cannot be reused.
        self._sheets = list(wb.worksheets)
        self._sheet_ids = {id(ws) for ws in self._sheets}
        self._cells: dict[int, tuple[object, str]] = {}
        self._by_coord: set[tuple[str, str]] = set()
        for ws in self._sheets:
            for cell in ws._cells.values():
                value = cell.value
                if isinstance(value, str) and cell.data_type != "f" and JP_REGEX.search(value):
                    self._cells[id(cell)] = (cell, value)
                    self._by_coord.add((cell.coordinate, value))

    def is_label(self, ws, cell) -> bool:
        """True while ``cell`` still holds template text (not a value written by the fill)."""
        entry = self._cells.get(id(cell))
        if entry is not None and entry[0] is cell:
            return cell.value == entry[1]
        if id(ws) in self._sheet_ids:
            return False
        # Sheet cloned from a template after the snapshot: same text at the same coordinate.
        return (cell.coordinate, cell.value) in self._by_coord


def snapshot_template_labels(wb) -> TemplateLabels:
    """Record the template's label cells; call right after loading, before any fill."""
    return TemplateLabels(wb)


def translate_workbook(wb, labels: TemplateLabels) -> None:
    """Translate template labels and sheet titles when the target language is English."""
    if not is_english_target():
        return
    for ws in wb.worksheets:
        for cell in list(ws._cells.values()):
            value = cell.value
            if not isinstance(value, str) or cell.data_type == "f" or not JP_REGEX.search(value):
                continue
            if labels.is_label(ws, cell):
                cell.value = translate_text(value)

    renames: dict[str, str] = {}
    for ws in list(wb.worksheets):
        new_title = translate_sheet_title(ws.title)
        if new_title != ws.title and new_title not in wb.sheetnames:
            renames[ws.title] = new_title
            ws.title = new_title
    retarget_formula_refs(wb, renames)


def _restore_prefixed_title(name: str) -> str | None:
    for en, jp in (("Screen Spec", "画面仕様書"), ("File Spec", "ファイル仕様書")):
        for opener in ("（", " ("):
            prefix = en + opener
            if name.startswith(prefix) and name.endswith((")", "）")):
                return f"{jp}（{name[len(prefix):-1]}）"
    if name.startswith("Detailed Design Spec_"):
        return "詳細仕様書_" + name[len("Detailed Design Spec_"):]
    return None


def restore_japanese_sheet_names(wb) -> None:
    """Rename English titles of an already-translated template back to the Japanese ones."""
    reverse = {en: jp for jp, en in SHEET_TITLES.items()}
    renames: dict[str, str] = {}
    for ws in list(wb.worksheets):
        name = ws.title
        new_name = reverse.get(name) or _restore_prefixed_title(name)
        if not new_name or new_name == name:
            continue
        if new_name in wb.sheetnames:
            print(f"[WARN] Cannot restore sheet name '{name}': '{new_name}' already exists")
            continue
        ws.title = new_name
        renames[name] = new_name
    retarget_formula_refs(wb, renames)
