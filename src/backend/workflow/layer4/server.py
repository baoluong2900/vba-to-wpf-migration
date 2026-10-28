import json
import time
from pathlib import Path
from urllib.parse import quote

L4_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = L4_DIR.parents[2] / "excel_outputs"          # src/excel_outputs
L2_OUTPUT_DIR = L4_DIR.parent / "layer2" / "output"       # Layer 2 BD/DD JSON

TEMPLATE_DIR = L4_DIR / "template"

BD_SCREEN_TEMPLATE = TEMPLATE_DIR / "BD_Screen" / "bd_template.xlsx"
BD_REPORT_TEMPLATE = TEMPLATE_DIR / "BD_Report" / "bd_report_template.xlsx"

DD_SCREEN_TEMPLATE = TEMPLATE_DIR / "DD_Screen" / "dd_template.xlsx"
DD_REPORT_TEMPLATE = TEMPLATE_DIR / "DD_Report" / "dd_report_template.xlsx"
DD_MACRO_TEMPLATE = TEMPLATE_DIR / "DD_Screen" / "dd_template_macro.xlsx"
DD_MODULE_TEMPLATE = TEMPLATE_DIR / "DD_Screen" / "dd_template_module.xlsx"

DD_CATEGORIES = ("screen", "report", "macro", "common")   # layer2/output/dd_flow/<cat>


class Layer2DataError(Exception):
    """Layer 2 BD/DD JSON is missing or unreadable; reported as a failed generation."""


def _confine(base: Path, *parts: str) -> Path:
    """``base/parts...`` resolved; raises ValueError if it would leave ``base``."""
    root = base.resolve()
    path = root.joinpath(*parts).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"Path escapes {root}: {'/'.join(parts)!r}")
    return path


def _child(base: Path, filename: str) -> Path:
    """``base/filename`` for a name built from request data: a direct child of ``base``."""
    path = _confine(base, filename)
    if path.parent != base.resolve():
        raise ValueError(f"Path escapes {base.resolve()}: {filename!r}")
    return path


def _read_layer2_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:   # JSONDecodeError is a ValueError
        raise Layer2DataError(f"Cannot read Layer 2 output {path.name}: {e}") from e
    if not isinstance(data, dict):
        raise Layer2DataError(f"Layer 2 output {path.name} is not a JSON object")
    return data


def _find_in_mongo(collection: str, screen_name: str) -> tuple[dict | None, str | None]:
    """(document, None) / (None, None) when absent / (None, error text) when MongoDB failed."""
    try:
        from db.mongo_client import get_db
        doc = get_db()[collection].find_one({"name": screen_name})
    except Exception as e:
        print(f"[WARN] Failed to read '{screen_name}' from MongoDB '{collection}': {e}")
        return None, f"MongoDB lookup failed: {e}"
    if doc:
        doc.pop("_id", None)
        return doc, None
    return None, None


def _not_generated(kind: str, screen_name: str, collection: str, mongo_error: str | None) -> str:
    msg = (
        f"{kind} for '{screen_name}' is not generated yet: no Layer 2 output file and no "
        f"MongoDB '{collection}' document. Run the Layer 2 {kind} flow first."
    )
    return f"{msg} ({mongo_error})" if mongo_error else msg


def get_bd_data(screen_name: str) -> dict:
    """BD JSON from Layer 2 output, else MongoDB 'bds'. Raises Layer2DataError."""
    path = _child(L2_OUTPUT_DIR / "bd_flow" / "bd4_bd_final", f"{screen_name}.json")
    if path.exists():
        return _read_layer2_json(path)
    doc, mongo_error = _find_in_mongo("bds", screen_name)
    if doc:
        return doc
    raise Layer2DataError(_not_generated("BD", screen_name, "bds", mongo_error))


def get_dd_data(screen_name: str) -> dict:
    """DD JSON from Layer 2 output, else MongoDB 'dds'. Raises Layer2DataError."""
    for cat in DD_CATEGORIES:
        path = _child(L2_OUTPUT_DIR / "dd_flow" / cat / "dd4_dd_final", f"{screen_name}.json")
        if path.exists():
            return _read_layer2_json(path)
    doc, mongo_error = _find_in_mongo("dds", screen_name)
    if doc:
        return doc
    raise Layer2DataError(_not_generated("DD", screen_name, "dds", mongo_error))


def list_items():
    from db.layer1_repo import Layer1Repo
    repo = Layer1Repo()
    screens = repo.list_all_items()
    return {"success": True, "result": screens}


def _download_url(doc_kind: str, doc_type: str, filename: str) -> str:
    return f"/api/v1/layer4/download/{quote(doc_kind)}/{quote(doc_type)}/{quote(filename)}"


def list_outputs():
    if not OUTPUT_DIR.exists():
        return {"success": True, "files": []}
    files = []
    for f in OUTPUT_DIR.glob("**/*.*"):
        if f.suffix in (".xlsx", ".docx", ".zip"):
            rel = f.relative_to(OUTPUT_DIR).parts
            doc_kind = rel[0] if len(rel) > 1 else ""
            doc_type = rel[1] if len(rel) > 2 else ""
            files.append({
                "filename": f.name,
                "doc_kind": doc_kind,
                "doc_type": doc_type,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "download_url": _download_url(doc_kind, doc_type, f.name),
            })
    return {"success": True, "files": files}


def _build_docx(builder: str, data: dict, docx_path: Path) -> str | None:
    """Write the Word rendition; return the error text instead of raising."""
    docx_path.unlink(missing_ok=True)      # never serve a stale copy
    try:
        import fill_docx
        getattr(fill_docx, builder)(data, docx_path)
    except Exception as e:
        print(f"[ERROR] Word generation failed for {docx_path.name}: {e}")
        return f"Word generation failed: {e}"
    return None


def _gen_result(doc_kind: str, doc_type: str, excel_path: Path, docx_path: Path,
                docx_error: str | None, start_time: float) -> dict:
    url = _download_url(doc_kind, doc_type, excel_path.name)
    file_info = {"url": url}
    if docx_error is None and docx_path.exists():
        file_info["docx_url"] = _download_url(doc_kind, doc_type, docx_path.name)
    result = {
        "success": True,
        "filename": excel_path.name,
        "size_kb": round(excel_path.stat().st_size / 1024, 1) if excel_path.exists() else 0,
        "duration_sec": round(time.time() - start_time, 2),
        "download_url": url,
        "file_info": file_info,
    }
    if docx_error:
        result["docx_error"] = docx_error
    return result


def gen_bd(req):
    start_time = time.time()
    screen_name = req.screenName
    doc_type = getattr(req, "type", "screen") or "screen"

    # 1. Fetch BD data (Layer 2 output only — never raw Layer 1 extraction data)
    try:
        bd_data = get_bd_data(screen_name)
    except Layer2DataError as e:
        return {"success": False, "error": str(e)}
    if not bd_data.get("screen_id"):
        bd_data["screen_id"] = screen_name      # report BD JSON leaves it empty

    # 2. Determine type
    is_report = doc_type == "report" or bd_data.get("type") == "report" or "report" in bd_data
    doc_type_folder = "report" if is_report else "screen"
    excel_path = _child(OUTPUT_DIR / "BD" / doc_type_folder, f"{screen_name}.xlsx")
    docx_path = _child(OUTPUT_DIR / "BD" / doc_type_folder, f"{screen_name}.docx")

    # 3. Generate Excel (no sample change history; no Excel COM from a server thread)
    try:
        if is_report:
            import fill_bd_report_excel
            fill_bd_report_excel.fill_report_excel(
                BD_REPORT_TEMPLATE, bd_data, excel_path, mock_change_history=False,
            )
        else:
            import fill_bd_excel
            fill_bd_excel.fill_excel(
                BD_SCREEN_TEMPLATE, bd_data, excel_path,
                mock_change_history=False, draw_layout_shapes=False,
            )
    except Exception as e:
        print(f"[ERROR] BD Excel Gen Failed: {e}")
        excel_path.unlink(missing_ok=True)
        return {"success": False, "error": f"BD Excel generation failed: {e}"}

    # 4. Generate Word
    docx_error = _build_docx("build_bd_docx", bd_data, docx_path)
    return _gen_result("BD", doc_type_folder, excel_path, docx_path, docx_error, start_time)


def gen_dd(req):
    start_time = time.time()
    screen_name = req.screenName
    doc_type = getattr(req, "type", "screen") or "screen"

    # 1. Fetch DD data (Layer 2 output only — never raw Layer 1 extraction data)
    try:
        dd_data = get_dd_data(screen_name)
    except Layer2DataError as e:
        return {"success": False, "error": str(e)}
    if not dd_data.get("screen_id"):
        dd_data["screen_id"] = screen_name      # report DD JSON leaves it empty

    # 2. Determine type
    item_type = doc_type
    if dd_data.get("type"):
        item_type = dd_data["type"]
    elif "report" in dd_data:
        item_type = "report"
    elif "macro" in dd_data:
        item_type = "macro"
    elif "module" in dd_data:
        item_type = "module"

    if item_type not in ("screen", "report", "macro", "module"):
        item_type = "screen"

    # screen / report: sheet_3_detail_specs, one detail sheet per item;
    # macro / module: sheet_2_detail.
    detail_profile = "module_macro" if item_type in ("macro", "module") else "form"

    excel_path = _child(OUTPUT_DIR / "DD" / item_type, f"{screen_name}.xlsx")
    docx_path = _child(OUTPUT_DIR / "DD" / item_type, f"{screen_name}.docx")

    # 3. Generate Excel
    try:
        if item_type == "report":
            import fill_dd_excel_report as filler
            template = DD_REPORT_TEMPLATE
        elif item_type == "macro":
            import fill_dd_excel_macro as filler
            template = DD_MACRO_TEMPLATE
        elif item_type == "module":
            import fill_dd_excel_module as filler
            template = DD_MODULE_TEMPLATE
        else:
            import fill_dd_excel_frm as filler
            template = DD_SCREEN_TEMPLATE
        filler.fill_excel(
            template, dd_data, excel_path,
            mock_change_history=False, detail_profile=detail_profile,
        )
    except Exception as e:
        print(f"[ERROR] DD Excel Gen Failed: {e}")
        excel_path.unlink(missing_ok=True)
        return {"success": False, "error": f"DD Excel generation failed: {e}"}

    # 4. Generate Word
    docx_error = _build_docx("build_dd_docx", dd_data, docx_path)
    return _gen_result("DD", item_type, excel_path, docx_path, docx_error, start_time)


def gen_all(req):
    # Run both generations without zipping
    res_bd = gen_bd(req)
    res_dd = gen_dd(req)

    return {
        "success": bool(res_bd.get("success") and res_dd.get("success")),
        "bd": res_bd,
        "dd": res_dd
    }


class MockFileResponse:
    def __init__(self, path, media_type):
        self.path = path
        self.media_type = media_type


def download_file(doc_kind, doc_type, filename):
    # Confine the resolved path to OUTPUT_DIR to prevent path traversal (e.g. "../../etc/passwd")
    try:
        file_path = _confine(OUTPUT_DIR, doc_kind, doc_type, filename)
    except ValueError:
        raise ValueError("Invalid download path") from None

    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix == ".zip":
        media_type = "application/zip"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return MockFileResponse(str(file_path), media_type)
