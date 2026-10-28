#!/usr/bin/env python3
"""
Export danh sách Forms / Queries / Macros từ MongoDB Layer 1.

Quy tắc mapping tên (normalize, bảng thay thế, Pascal, unique): xem
`EXPORT_FORMS_LAYER1_MAPPING_RULES.md` cùng thư mục.

Chạy từ gốc `03_agents/workflow/`:
    python -X utf8 backend/layer5/agents/graphview/inputs/export_forms_layer1.py

    Output (backend/layer5/agents/graphview/outputs/forms/):
        listFormJp.json, listFormJpToEn.json
    backend/layer5/agents/graphview/outputs/queries/
        listQueryJp.json, listQueryJpToEn.json
    backend/layer5/agents/graphview/outputs/macros/
        listMacroJp.json, listMacroJpToEn.json
    backend/layer5/agents/graphview/outputs/events/
        listEventJp.json, listEventJpToEn.json

File raw (`*_layer1.json`): mảng **chỉ tên** (`string[]`). Không ghi `_id` MongoDB ra file.

Trùng `name`: **forms** vẫn đọc `_id` trong code để chọn một document khi trùng; **queries/macros** chỉ lấy field `name` từ MongoDB, dedupe bằng tập hợp tên + báo tên xuất hiện > 1 lần.

Kết nối MongoDB qua `pymongo` + `backend/layer5/core/config.py` (đọc `workflow/config.json`), **không** import từ `backend/layer2`.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)
logging.getLogger("pymongo.command").setLevel(logging.WARNING)

INPUT_DIR = Path(__file__).resolve().parent
GRAPHVIEW_DIR = INPUT_DIR.parent
LAYER5_ROOT = GRAPHVIEW_DIR.parent.parent
WORKSPACE_ROOT = LAYER5_ROOT.parent.parent.parent.parent
OUT_ROOT = GRAPHVIEW_DIR / "outputs"
OUT_FORMS = OUT_ROOT / "forms"
OUT_QUERIES = OUT_ROOT / "queries"
OUT_MACROS = OUT_ROOT / "macros"
OUT_EVENTS = OUT_ROOT / "events"
OUT_MODULES = OUT_ROOT / "modules"

sys.path.insert(0, str(LAYER5_ROOT))
from core.config import (  # noqa: E402
    COL_FORMS,
    COL_MACROS,
    COL_MODULES,
    COL_QUERIES,
    MONGO_DB,
    MONGO_URI,
)
from pymongo import MongoClient  # noqa: E402



def _fetch_forms(db) -> list[dict]:
    """Giống Layer1Repo.list_forms: key = str(_id), name."""
    return [
        {"key": str(d["_id"]), "name": d["name"]}
        for d in db[COL_FORMS].find({}, {"name": 1, "_id": 1})
        if d.get("name") is not None
    ]


def _fetch_query_names(db) -> list[str]:
    return [d["name"] for d in db[COL_QUERIES].find({}, {"name": 1}) if d.get("name") is not None]


def _fetch_macro_names(db) -> list[str]:
    return [d["name"] for d in db[COL_MACROS].find({}, {"name": 1}) if d.get("name") is not None]


def _fetch_module_names(db) -> list[str]:
    return [d["name"] for d in db[COL_MODULES].find({}, {"name": 1}) if d.get("name") is not None]


def _normalize_event_key_display(key: str) -> str:
    k = str(key).strip()
    if not k:
        return ""
    return k[0].upper() + k[1:] if len(k) > 1 else k.upper()


def _extract_events_from_properties(
    form_name: str, control_name: str, props: object
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(props, dict):
        return out
    ev = props.get("Event") or props.get("event")
    if not isinstance(ev, dict):
        return out
    ctrl = (control_name or "").strip()
    for raw_key, val in ev.items():
        if val is None:
            continue
        s = str(val).strip()
        if not s:
            continue
        ek = _normalize_event_key_display(str(raw_key))
        out.append(
            {
                "form": str(form_name).strip(),
                "scope": "Control" if ctrl else "Form",
                "control": ctrl,
                "event_key": ek,
                "handler_hint": s,
            }
        )
    return out


def _walk_form_items_for_events(form_name: str, items: object) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    if not isinstance(items, list):
        return events
    for it in items:
        if not isinstance(it, dict):
            continue
        cname = str(it.get("name") or "").strip()
        props = it.get("properties")
        events.extend(_extract_events_from_properties(form_name, cname, props))
        nested = it.get("items")
        if nested is not None:
            events.extend(_walk_form_items_for_events(form_name, nested))
    return events


def _fetch_form_events(db) -> list[dict[str, str]]:
    """Trích Event từ bucket properties.Event / event của form + controls (Layer1)."""
    all_e: list[dict[str, str]] = []
    proj = {"name": 1, "properties": 1, "items": 1}
    for doc in db[COL_FORMS].find({}, proj):
        fname = str(doc.get("name") or "").strip()
        if not fname:
            continue
        all_e.extend(_extract_events_from_properties(fname, "", doc.get("properties")))
        all_e.extend(_walk_form_items_for_events(fname, doc.get("items")))
    # Dedupe (form, control, event_key, handler_hint)
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, str]] = []
    for row in all_e:
        t = (row["form"], row["control"], row["event_key"], row["handler_hint"])
        if t in seen:
            continue
        seen.add(t)
        unique.append(row)
    unique.sort(key=lambda r: (r["form"], r["scope"], r["control"], r["event_key"], r["handler_hint"]))
    return unique

# Thay thế theo chuỗi dài trước. Tách riêng theo object type.
_COMMON_REPLACEMENTS: list[tuple[str, str]] = [
    ("のコピー", "Copy"),
    ("ReadMe", "ReadMe"),
    ("＆", "And"),
    ("Ｑ", "Q"),
    ("ＤＢ", "DB"),
    ("を", ""),
    ("と", "And"),
    ("へ", "To"),
    ("改", "Rev"),
    ("新", "New"),
    ("管理", "Management"),
    ("終了", "Exit"),
    ("ビル", "Building"),
    ("回収", "Collection"),
    ("版", ""),
    ("から", "From"),
    ("メイン", "Main"),
    ("に", "To"),
]

_FORM_REPLACEMENTS: list[tuple[str, str]] = [
    ("請求先抽出_修正用", "BillingPartyExtractForCorrection"),
    ("未入金_前期", "UnpaidPriorPeriod"),
    ("入金_前期", "ReceiptPriorPeriod"),
    ("アフターMAINto編集Ⅱ", "AfterMainToEdit2"),
    ("アフターMAINto複製Ⅱ", "AfterMainToDuplicate2"),
    ("MAINto編集", "MainToEdit"),
    ("MAINto複製", "MainToDuplicate"),
    ("作業依頼書報告書合体", "WorkRequestReportMerge"),
    ("メンテナンスの保証について", "MaintenanceWarrantyInfo"),
    ("依頼の情報のみ", "RequestInfoOnly"),
    ("依頼情報のみ", "RequestInfoOnly"),
    ("お客様控え", "CustomerCopy"),
    ("弊社控え", "CompanyCopy"),
    ("メモ用紙なし", "NoMemoSheet"),
    ("宮下部長案", "MiyashitaChiefDraft"),
    ("(未使用)", "Unused"),
    ("アフター登録Ⅱ", "AfterRegister2"),
    ("アフター修正Ⅱ", "AfterAmend2"),
    ("アフター照会Ⅱ", "AfterInquiry2"),
    ("印刷設定Ⅱ", "PrintSettings2"),
    ("支店選択フォーム", "BranchSelectForm"),
    ("管理ホーム", "ManagementHome"),
    ("メモ用方眼紙", "MemoGridPaper"),
    ("作業依頼書", "WorkRequest"),
    ("作業報告書", "WorkReport"),
    ("回収不能報告書", "UncollectibleReport"),
    ("窓付き宛先", "WindowAddress"),
    ("白紙出力メニュー", "BlankOutputMenu"),
    ("入金情報一括入力", "ReceiptBatchEntry"),
    ("責任区分＆金額", "LiabilitySplitAmount"),
    ("有償無償瑕疵", "PaidFreeDefect"),
    ("都道府県抽出用", "PrefectureExtract"),
    ("支店抽出用", "BranchExtract"),
    ("提出元", "SubmissionSource"),
    ("タイトル", "Title"),
    ("合体", "Merge"),
    ("アフター", "After"),
    ("見積書Ⅱ", "Estimate2"),
    ("請求書Ⅱ", "Invoice2"),
    ("納品書Ⅱ", "DeliveryNote2"),
    ("送付状Ⅱ", "CoverLetter2"),
    ("画面明細Ⅱ", "CaseLine2"),
    ("画面Ⅱ", "CaseScreen2"),
    ("完了届Ⅱ", "CompletionNotice2"),
    ("メンテナンス作業報告書", "MaintenanceWorkReport"),
    ("メンテナンス受付", "MaintenanceReception"),
    ("依頼", "Request"),
    ("保管", "Custody"),
    ("保証", "Warranty"),
    ("報告書", "Report"),
    ("施工", "Construction"),
    ("見積書", "Estimate"),
    ("請求書", "Invoice"),
    ("納品書", "DeliveryNote"),
    ("送付状", "CoverLetter"),
    ("画面明細", "CaseLine"),
    ("画面", "CaseScreen"),
    ("完了届", "CompletionNotice"),
    ("照会", "Inquiry"),
    ("登録", "Register"),
    ("修正用", "ForCorrection"),
    ("修正", "Amend"),
    ("編集", "Edit"),
    ("印刷", "Print"),
    ("連続", "Batch"),
    ("白紙", "Blank"),
    ("消費税無", "ExcludingTax"),
    ("受付日空白", "BlankReceiptDate"),
    ("フィルター", "Filter"),
    ("仮連番", "TempSerial"),
    ("連番", "Serial"),
    ("集計", "Summary"),
    ("担当者", "ByStaff"),
    ("先月", "PrevMonth"),
    ("当月", "CurMonth"),
    ("累計", "Cumulative"),
    ("有償", "Paid"),
    ("無償", "Free"),
    ("瑕疵", "Defect"),
    ("回収額実績", "CollectionAmountActual"),
    ("回収件数", "CollectionCount"),
    ("MAIN", "Main"),
    ("SubF", "SubForm"),
    ("サブ", "Sub"),
    ("請求先抽出", "BillingPartyExtract"),
    ("未入金", "Unpaid"),
    ("入金", "Receipt"),
    ("前期", "PriorPeriod"),
]

_QUERY_REPLACEMENTS: list[tuple[str, str]] = [
    ("報告ID照合", "ReportIdMatch"),
    ("表示設定更新", "DisplaySettingUpdate"),
    ("設定更新", "SettingUpdate"),
    ("テーブル作成", "TableCreate"),
    ("テーブル追加", "TableAppend"),
    ("ログインユーザー設定", "LoginUserSetting"),
    ("ログインユーザー", "LoginUser"),
    ("有償無償瑕疵", "PaidFreeDefect"),
    ("請求先抽出", "BillingPartyExtract"),
    ("アフター", "After"),
    ("期設定", "TermSetting"),
    ("期算出", "TermCalc"),
    ("配信日", "DeliveryDate"),
    ("コメント", "Comment"),
    ("抽出", "Extract"),
    ("照合", "Match"),
    ("更新", "Update"),
    ("変更", "Change"),
    ("表示", "Display"),
    ("合体", "Merge"),
    ("報告", "Report"),
    ("受付", "Reception"),
    ("施工", "Construction"),
    ("未登録", "Unregistered"),
    ("登録", "Register"),
    ("空白", "Blank"),
    ("先月", "PrevMonth"),
    ("当月", "CurMonth"),
    ("累計", "Cumulative"),
    ("有償", "Paid"),
    ("無償", "Free"),
    ("瑕疵", "Defect"),
    ("前期", "PriorPeriod"),
    ("入金", "Receipt"),
    ("未入金", "Unpaid"),
    ("集計", "Summary"),
    ("MAIN", "Main"),
]

_MACRO_REPLACEMENTS: list[tuple[str, str]] = [
    ("メニューバーを非表示", "MenuBarHide"),
    ("メニューバーを表示", "MenuBarShow"),
    ("一週間前算出", "OneWeekAgoCalc"),
    ("再起動", "Restart"),
    ("アフター", "After"),
    ("照会", "Inquiry"),
    ("編集", "Edit"),
    ("登録", "Register"),
    ("仮登録", "TempRegister"),
    ("MAIN", "Main"),
    ("Menu", "Menu"),
    ("戻す", "Restore"),
    ("作成", "Create"),
    ("表示設定更新", "DisplaySettingUpdate"),
    ("設定更新", "SettingUpdate"),
    ("更新", "Update"),
    ("変更", "Change"),
    ("解除", "Clear"),
    ("再クエリ", "Requery"),
    ("検索", "Search"),
    ("実行する", "Execute"),
    ("合体", "Merge"),
    ("報告", "Report"),
    ("受付", "Reception"),
    ("店所", "Office"),
    ("地区", "Area"),
    ("責任区分", "LiabilityCategory"),
    ("請求区分", "BillingCategory"),
    ("入金フラグ", "ReceiptFlag"),
    ("見積フラグ", "EstimateFlag"),
    ("請求フラグ", "InvoiceFlag"),
    ("登録状況", "RegistrationStatus"),
    ("管理リスト", "ManagementList"),
    ("担当者氏名", "StaffName"),
    ("登録者氏名", "RegistrantName"),
    ("新アフター管理ＤＢ", "NewAfterManagementDb"),
    ("全コンボ", "AllCombo"),
    ("コンボ", "Combo"),
    ("管理ホーム", "ManagementHome"),
    ("開く", "Open"),
    ("戻る", "Back"),
    ("表示", "Display"),
]

_MODULE_REPLACEMENTS: list[tuple[str, str]] = [
    ("Common", "Common"),
    ("Main", "Main"),
]

_ROMAN_NUMERAL_COMPAT = str.maketrans(
    {
        "\u2160": "1",
        "\u2161": "2",
        "\u2162": "3",
        "\u2163": "4",
        "\u2164": "5",
        "\u2165": "6",
        "\u2166": "7",
        "\u2167": "8",
        "\u2168": "9",
        "\u2169": "10",
    }
)


def _dedupe_by_name(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Forms: giữ một document mỗi `name`; trùng thì giữ bản có mongo `key` lexicographic lớn hơn."""
    best: dict[str, dict] = {}
    dup_names: set[str] = set()
    for r in rows:
        n = str(r.get("name", "")).strip()
        if not n:
            continue
        k = str(r.get("key", ""))
        if n not in best:
            best[n] = r
            continue
        dup_names.add(n)
        prev_k = str(best[n].get("key", ""))
        if k > prev_k:
            best[n] = r
    out = sorted(best.values(), key=lambda x: str(x["name"]))
    return out, sorted(dup_names)


def _dedupe_name_list(names: list[str]) -> tuple[list[str], list[str]]:
    """Query/Macro: danh sách chỉ tên — unique đã sort; trả về tên xuất hiện > 1 lần trong raw."""
    cleaned = [str(n).strip() for n in names if str(n).strip()]
    c = Counter(cleaned)
    dups = sorted(n for n, k in c.items() if k > 1)
    unique = sorted(c.keys())
    return unique, dups


def _normalize_access_name(access_name: str) -> str:
    """NFKC + trim. NFKC maps Unicode Roman Ⅱ (U+2161) to Latin letters II — restore Ⅱ for phrase tables."""
    s = unicodedata.normalize("NFKC", access_name.strip())
    s = re.sub(
        r"(?<=[A-Za-z\u3040-\u30ff\u3400-\u9fff_])II(?=[_\s]|$)",
        "\u2161",
        s,
    )
    return s


def _get_replacements(object_type: str) -> list[tuple[str, str]]:
    if object_type == "form":
        reps = _FORM_REPLACEMENTS + _COMMON_REPLACEMENTS
    elif object_type == "query":
        reps = _QUERY_REPLACEMENTS + _COMMON_REPLACEMENTS
    elif object_type == "macro":
        reps = _MACRO_REPLACEMENTS + _COMMON_REPLACEMENTS
    elif object_type == "module":
        reps = _MODULE_REPLACEMENTS + _COMMON_REPLACEMENTS
    else:
        reps = _COMMON_REPLACEMENTS
    return sorted(reps, key=lambda x: len(x[0]), reverse=True)


def _pascal_identifier_from_access(access_name: str, default_stem: str, object_type: str) -> str:
    s = _normalize_access_name(access_name)
    for jp, en in _get_replacements(object_type):
        s = s.replace(jp, en)
    s = s.translate(_ROMAN_NUMERAL_COMPAT)
    s = re.sub(r"\s+", "_", s)
    parts = re.split(r"[_\s]+", s)
    pascal: list[str] = []
    for p in parts:
        if not p:
            continue
        chunk = re.sub(r"[^0-9A-Za-z]+", "", p)
        if not chunk:
            continue
        if chunk.isdigit():
            pascal.append(chunk)
        else:
            pascal.append(chunk[0].upper() + chunk[1:])
    return "".join(pascal) if pascal else default_stem


def _suggest_wpf_view_name(access_name: str) -> str:
    base = _pascal_identifier_from_access(access_name, "Form", "form")
    if not base.endswith("View"):
        base = base + "View"
    return base


def _suggest_viewmodel(view: str) -> str:
    if view.endswith("View"):
        return view[:-4] + "ViewModel"
    return view + "ViewModel"


def _suggest_dotnet_query_type(access_name: str) -> str:
    base = _pascal_identifier_from_access(access_name, "Query", "query")
    if base.lower().endswith("query"):
        return base + "Definition"
    return base + "AccessQuery"


def _suggest_dotnet_macro_type(access_name: str) -> str:
    base = _pascal_identifier_from_access(access_name, "Macro", "macro")
    if base.lower().endswith("macro"):
        return base + "Workflow"
    return base + "MacroWorkflow"


def _suggest_dotnet_module_type(access_name: str) -> str:
    base = _pascal_identifier_from_access(access_name, "Module", "module")
    if base.lower().endswith("module"):
        return base[:-6] + "Service"
    if base.lower().endswith("service"):
        return base
    return base + "Service"

_EVENT_ACTION_REPLACEMENTS: list[tuple[str, str]] = [
    ("PDF出力", "ExportPdf"),
    ("PDF出力2", "ExportPdf"),
    ("EXCELに書き出し", "ExportExcel"),
    ("エクセルに書き出し", "ExportExcel"),
    ("印刷する", "Print"),
    ("閉じる", "Close"),
    ("プロセス終了", "ExitApplication"),
    ("パスワードテーブルを開く", "OpenPasswordTable"),
    ("MAINデータを開く", "OpenMainData"),
    ("SMBCエクスポート", "ExportSmbcData"),
    ("ZOOM遠隔", "OpenZoomRemote"),
    ("施工店情報", "OpenConstructionShopInfo"),
    ("並替解除ラベル", "ClearSort"),
    ("並替解除", "ClearSort"),
    ("再クエリ", "Refresh"),
    ("入金解除", "ClearReceiptFlag"),
    ("見積解除", "ClearEstimateFlag"),
    ("請求解除", "ClearInvoiceFlag"),
    ("地区CD解除", "ClearAreaCode"),
    ("コンボ1を実行する", "ExecuteCombo1"),
    ("管理ホームに戻る", "NavigateToManagementHome"),
    ("メニューバーを非表示", "HideMenuBar"),
    ("メニューバーを表示", "ShowMenuBar"),
    ("受付日", "ReceptionDate"),
    ("入金完了日", "ReceiptCompletedDate"),
    ("作業完了日", "WorkCompletedDate"),
    ("請求合計額", "InvoiceTotalAmount"),
    ("責任区分_当月", "ApplyCurrentMonthLiabilityCategory"),
    ("責任区分", "ApplyLiabilityCategory"),
]

_EVENT_CONTROL_REPLACEMENTS: dict[str, str] = {
    "cmdFirst": "MoveFirst",
    "cmdPrevious": "MovePrevious",
    "cmdNext": "MoveNext",
    "cmdLast": "MoveLast",
    "cmdNew": "CreateNew",
    "cmdChk": "Check",
    "cmdChk1": "Check1",
    "cmdChk2": "Check2",
    "cmdFilter": "ApplyFilter",
    "cmdFilterOff": "ClearFilter",
    "cmdSelectAll": "SelectAll",
    "cmdSelectAllA": "SelectAll",
    "cmdSelectClearA": "ClearSelection",
    "cmdSelectClearB": "ClearSelection",
    "Q_A": "OpenQuestionAnswer",
    "SMBC_Q_A": "OpenSmbcQuestionAnswer",
    "txtPass": "Login",
}

def _strip_event_suffix(value: str) -> str:
    s = str(value or "").strip()
    s = re.sub(r"^(macro|Macro)\.", "", s)
    s = re.sub(r"_(Click|DblClick|AfterUpdate|KeyDown|MouseDown)$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"_(click|dblclick|afterupdate|keydown|mousedown)$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"_[0-9]+$", "", s)
    return s.strip()

def _event_action_stem(value: str, default: str = "Execute") -> str:
    s = _strip_event_suffix(value)
    if not s:
        return default
    if s in _EVENT_CONTROL_REPLACEMENTS:
        return _EVENT_CONTROL_REPLACEMENTS[s]
    for jp, en in _EVENT_ACTION_REPLACEMENTS:
        if jp in s:
            return en
    return _pascal_identifier_from_access(s, default, "form")

def _event_name_with_kind(stem: str, event_key: str, handler_hint: str) -> str:
    ek = re.sub(r"[^0-9A-Za-z]", "", str(event_key or "")).lower()
    hh = str(handler_hint or "")
    if ek in {"onclick", "ondblclick"} or hh.lower().endswith(("_click", "_dblclick")):
        return f"{stem}Command"
    if ek == "afterupdate" or hh.lower().endswith("_afterupdate"):
        if stem == "Login":
            return "LoginCommand"
        if stem.startswith(("Apply", "Update", "Validate", "Clear")):
            return stem
        return f"Update{stem}"
    if ek == "onkeydown" or hh.lower().endswith("_keydown"):
        return f"Handle{stem}KeyDown"
    if ek == "onmousedown" or hh.lower().endswith("_mousedown"):
        return f"Handle{stem}MouseDown"
    return stem

def _suggest_dotnet_event_handler(row: dict[str, str]) -> str:
    form = str(row.get("form", ""))
    ctrl = str(row.get("control") or "").strip()
    ek_raw = str(row.get("event_key") or "").strip()
    hint = str(row.get("handler_hint") or "").strip()
    hint_lower = hint.lower()

    if hint in {"Form_Open", "Report_Open"} or hint_lower.endswith("_open"):
        return "OnOpened"
    if hint in {"Form_Load", "Report_Load"} or hint_lower.endswith("_load"):
        return "OnLoaded"
    if hint in {"Form_KeyDown", "Report_KeyDown"}:
        return "HandleFormKeyDown"
    if re.sub(r"[^0-9A-Za-z]", "", ek_raw).lower() == "timerinterval":
        return "OnTimerTick"

    source = ctrl or hint
    if hint.startswith("macro."):
        source = hint
    stem = _event_action_stem(source, _pascal_identifier_from_access(form, "Execute", "form"))
    return _event_name_with_kind(stem, ek_raw, hint)

def _event_mapping_items(form_events: list[dict[str, str]]) -> list[dict]:
    return [
        {
            "access_form_name": r["form"],
            "access_control_name": r["control"],
            "access_event_key": r["event_key"],
            "handler_hint": r["handler_hint"],
            "suggested_dotnet_handler_name": _suggest_dotnet_event_handler(r),
        }
        for r in form_events
    ]


def _ensure_unique_form_mapping(items: list[dict]) -> list[dict]:
    """
    Đảm bảo wpf_view_name duy nhất; ViewModel đồng bộ. Chèn số trước hậu tố View
    (vd. FooView, Foo2View) để _suggest_viewmodel vẫn đúng.
    """
    seen: dict[str, int] = {}
    out: list[dict] = []
    for item in items:
        cur = str(item["wpf_view_name"])
        if cur not in seen:
            seen[cur] = 1
            out.append(dict(item))
            continue
        seen[cur] += 1
        n = seen[cur]
        new_item = dict(item)
        if cur.endswith("View"):
            stem = cur[:-4]
            new_view = f"{stem}{n}View"
        else:
            new_view = f"{cur}{n}"
        new_item["wpf_view_name"] = new_view
        new_item["wpf_viewmodel_name"] = _suggest_viewmodel(new_view)
        out.append(new_item)
    return out


def _ensure_unique(items: list[dict], field_name: str) -> list[dict]:
    """
    Ensure generated names are unique and deterministic.
    If duplicates appear, append numeric suffix based on appearance order.
    """
    seen: dict[str, int] = {}
    out: list[dict] = []
    for item in items:
        cur = str(item[field_name])
        if cur not in seen:
            seen[cur] = 1
            out.append(item)
            continue
        seen[cur] += 1
        new_item = dict(item)
        new_item[field_name] = f"{cur}{seen[cur]}"
        out.append(new_item)
    return out


def _build_payload(
    *,
    collection: str,
    count: int,
    duplicate_names: list[str],
) -> dict:
    return {
        "source": "mongodb_layer1",
        "mongo_uri_redacted": MONGO_URI.split("@")[-1] if "@" in MONGO_URI else "(local)",
        "database": MONGO_DB,
        "collection": collection,
        "count": count,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "duplicate_names_collapsed": duplicate_names,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export Forms, Queries, Macros, Modules từ MongoDB Layer 1 + Events (trích từ forms) + mapping gợi ý .NET."
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ in tóm tắt (count + trùng tên), không ghi file.",
    )
    args = ap.parse_args()

    try:
        with MongoClient(MONGO_URI, serverSelectionTimeoutMS=30_000) as client:
            db = client[MONGO_DB]
            raw_forms = _fetch_forms(db)
            raw_queries = _fetch_query_names(db)
            raw_macros = _fetch_macro_names(db)
            raw_modules = _fetch_module_names(db)
            form_events = _fetch_form_events(db)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    forms, dup_f = _dedupe_by_name(raw_forms)
    query_names, dup_q = _dedupe_name_list(raw_queries)
    macro_names, dup_m = _dedupe_name_list(raw_macros)
    module_names, dup_mod = _dedupe_name_list(raw_modules)

    ts = datetime.now(timezone.utc).isoformat()

    payload_forms = _build_payload(collection=COL_FORMS, count=len(forms), duplicate_names=dup_f)
    payload_forms["forms"] = [str(r["name"]) for r in forms]
    payload_forms["exported_at"] = ts

    payload_queries = _build_payload(collection=COL_QUERIES, count=len(query_names), duplicate_names=dup_q)
    payload_queries["queries"] = query_names
    payload_queries["exported_at"] = ts

    payload_macros = _build_payload(collection=COL_MACROS, count=len(macro_names), duplicate_names=dup_m)
    payload_macros["macros"] = macro_names
    payload_macros["exported_at"] = ts
    
    payload_modules = _build_payload(collection="modules", count=len(module_names), duplicate_names=dup_mod)
    payload_modules["modules"] = module_names
    payload_modules["exported_at"] = ts

    payload_events = _build_payload(
        collection=f"{COL_FORMS} (event properties)",
        count=len(form_events),
        duplicate_names=[],
    )
    payload_events["events"] = form_events
    payload_events["exported_at"] = ts

    form_items: list[dict] = []
    for r in forms:
        vn = _suggest_wpf_view_name(str(r["name"]))
        form_items.append(
            {
                "access_form_name": r["name"],
                "wpf_view_name": vn,
                "wpf_viewmodel_name": _suggest_viewmodel(vn),
            }
        )

    map_forms = {
        "source": "derived_from_forms_layer1",
        "note": "wpf_* là GỢI Ý — review theo docs/form_naming_and_mapping.md",
        "exported_at": ts,
        "count": len(forms),
        "items": _ensure_unique_form_mapping(form_items),
    }

    map_queries = {
        "source": "derived_from_queries_layer1",
        "note": "dotnet_* là GỢI Ý (class/spec query) — thường map sang Repository + SQL const; phải review.",
        "exported_at": ts,
        "count": len(query_names),
        "items": _ensure_unique([
            {
                "access_query_name": n,
                "suggested_dotnet_type_name": _suggest_dotnet_query_type(str(n)),
            }
            for n in query_names
        ], "suggested_dotnet_type_name"),
    }

    map_macros = {
        "source": "derived_from_macros_layer1",
        "note": "dotnet_* là GỢI Ý (workflow / orchestration) — phải review.",
        "exported_at": ts,
        "count": len(macro_names),
        "items": _ensure_unique([
            {
                "access_macro_name": n,
                "suggested_dotnet_type_name": _suggest_dotnet_macro_type(str(n)),
            }
            for n in macro_names
        ], "suggested_dotnet_type_name"),
    }

    map_modules = {
        "source": "derived_from_modules_layer1",
        "note": "dotnet_* là GỢI Ý (module / service) — phải review.",
        "exported_at": ts,
        "count": len(module_names),
        "items": _ensure_unique([
            {
                "access_module_name": n,
                "suggested_dotnet_type_name": _suggest_dotnet_module_type(str(n)),
            }
            for n in module_names
        ], "suggested_dotnet_type_name"),
    }

    map_events = {
        "source": "derived_from_forms_layer1_events",
        "note": "Trích từ properties.Event / event trên form + controls. suggested_dotnet_handler_name là GỢI Ý — phải review.",
        "exported_at": ts,
        "count": len(form_events),
        "items": _event_mapping_items(form_events),
    }

    summary = {
        "ok": True,
        "exported_at": ts,
        "counts": {
            "forms": len(forms),
            "queries": len(query_names),
            "macros": len(macro_names),
            "modules": len(module_names),
            "events": len(form_events),
        },
        "duplicates_collapsed": {
            "forms": dup_f,
            "queries": dup_q,
            "macros": dup_m,
            "modules": dup_mod,
        },
        "outputs": {
            "listFormJp": str(OUT_FORMS / "listFormJp.json"),
            "listFormJpToEn": str(OUT_FORMS / "listFormJpToEn.json"),
            "listQueryJp": str(OUT_QUERIES / "listQueryJp.json"),
            "listQueryJpToEn": str(OUT_QUERIES / "listQueryJpToEn.json"),
            "listMacroJp": str(OUT_MACROS / "listMacroJp.json"),
            "listMacroJpToEn": str(OUT_MACROS / "listMacroJpToEn.json"),
            "listModuleJp": str(OUT_MODULES / "listModuleJp.json"),
            "listModuleJpToEn": str(OUT_MODULES / "listModuleJpToEn.json"),
            "listEventJp": str(OUT_EVENTS / "listEventJp.json"),
            "listEventJpToEn": str(OUT_EVENTS / "listEventJpToEn.json"),
        },
    }

    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    OUT_FORMS.mkdir(parents=True, exist_ok=True)
    OUT_QUERIES.mkdir(parents=True, exist_ok=True)
    OUT_MACROS.mkdir(parents=True, exist_ok=True)
    OUT_MODULES.mkdir(parents=True, exist_ok=True)
    OUT_EVENTS.mkdir(parents=True, exist_ok=True)
    
    (OUT_FORMS / "listFormJp.json").write_text(
        json.dumps(payload_forms, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_FORMS / "listFormJpToEn.json").write_text(
        json.dumps(map_forms, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_QUERIES / "listQueryJp.json").write_text(
        json.dumps(payload_queries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_QUERIES / "listQueryJpToEn.json").write_text(
        json.dumps(map_queries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_MACROS / "listMacroJp.json").write_text(
        json.dumps(payload_macros, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_MACROS / "listMacroJpToEn.json").write_text(
        json.dumps(map_macros, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_MODULES / "listModuleJp.json").write_text(
        json.dumps(payload_modules, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_MODULES / "listModuleJpToEn.json").write_text(
        json.dumps(map_modules, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_EVENTS / "listEventJp.json").write_text(
        json.dumps(payload_events, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_EVENTS / "listEventJpToEn.json").write_text(
        json.dumps(map_events, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
