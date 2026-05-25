import os
import json
import zipfile
from pathlib import Path
from db.layer1_repo import Layer1Repo

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "excel_outputs"

L3_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = L3_DIR / "template"

BD_SCREEN_TEMPLATE = TEMPLATE_DIR / "BD_Screen" / "bd_template.xlsx"
BD_REPORT_TEMPLATE = TEMPLATE_DIR / "BD_Report" / "bd_report_template.xlsx"

DD_SCREEN_TEMPLATE = TEMPLATE_DIR / "DD_Screen" / "dd_template.xlsx"
DD_REPORT_TEMPLATE = TEMPLATE_DIR / "DD_Report" / "dd_report_template.xlsx"
DD_MACRO_TEMPLATE = TEMPLATE_DIR / "DD_Screen" / "dd_template_macro.xlsx"
DD_MODULE_TEMPLATE = TEMPLATE_DIR / "DD_Screen" / "dd_template_module.xlsx"

def get_bd_data(screen_name: str) -> dict | None:
    """Read BD JSON from layer2 output or MongoDB."""
    l2_base = Path(__file__).resolve().parent.parent / "layer2"
    path = l2_base / "output" / "bd_flow" / "s4_bd_final" / f"{screen_name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        from db.mongo_client import get_db
        db = get_db()
        doc = db["bds"].find_one({"name": screen_name})
        if doc:
            doc.pop("_id", None)
            return doc
    except Exception as e:
        print(f"[WARN] Failed to read BD from MongoDB: {e}")

    return None

def get_dd_data(screen_name: str) -> dict | None:
    """Read DD JSON from layer2 output or MongoDB."""
    l2_base = Path(__file__).resolve().parent.parent / "layer2"
    for cat in ("screen", "report", "macro", "common"):
        path = l2_base / "output" / "dd_flow" / cat / "d4_dd_final" / f"{screen_name}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass

    try:
        from db.mongo_client import get_db
        db = get_db()
        doc = db["dds"].find_one({"name": screen_name})
        if doc:
            doc.pop("_id", None)
            return doc
    except Exception as e:
        print(f"[WARN] Failed to read DD from MongoDB: {e}")

    return None

def list_items():
    repo = Layer1Repo()
    screens = repo.list_all_items()
    return {"success": True, "result": screens}

def list_outputs():
    if not OUTPUT_DIR.exists():
        return {"success": True, "files": []}
    files = []
    for f in OUTPUT_DIR.glob("**/*.*"):
        if f.suffix in (".xlsx", ".docx", ".zip"):
            files.append({
                "name": f.name,
                "path": str(f.relative_to(OUTPUT_DIR)),
                "size": f.stat().st_size
            })
    return {"success": True, "files": files}

def gen_bd(req):
    screen_name = req.screenName
    doc_type = getattr(req, "type", "screen") or "screen"

    # 1. Fetch BD data
    bd_data = get_bd_data(screen_name)
    if not bd_data:
        try:
            repo = Layer1Repo()
            bd_data = repo.get_bd_code_json_unified(screen_name)
        except Exception as e:
            return {"success": False, "error": f"BD data not ready for '{screen_name}': {e}"}

    # 2. Determine type
    is_report = False
    if doc_type == "report" or bd_data.get("type") == "report" or "report" in bd_data:
        is_report = True

    doc_type_folder = "report" if is_report else "screen"
    excel_filename = f"{screen_name}.xlsx"
    excel_path = OUTPUT_DIR / "BD" / doc_type_folder / excel_filename
    
    docx_filename = f"{screen_name}.docx"
    docx_path = OUTPUT_DIR / "BD" / doc_type_folder / docx_filename

    # 3. Generate Excel
    try:
        if is_report:
            import fill_bd_report_excel
            fill_bd_report_excel.fill_report_excel(BD_REPORT_TEMPLATE, bd_data, excel_path)
        else:
            import fill_bd_excel
            fill_bd_excel.fill_excel(BD_SCREEN_TEMPLATE, bd_data, excel_path)
    except Exception as e:
        print(f"[ERROR] BD Excel Gen Failed: {e}")
        return {"success": False, "error": f"BD Excel generation failed: {e}"}

    # 4. Generate Word
    try:
        from scripts.fill_docx import build_bd_docx
        build_bd_docx(bd_data, docx_path)
    except Exception as e:
        print(f"[ERROR] BD Word Gen Failed: {e}")

    return {
        "success": True,
        "file_info": {
            "url": f"/api/l3/download/BD/{doc_type_folder}/{excel_filename}",
            "docx_url": f"/api/l3/download/BD/{doc_type_folder}/{docx_filename}"
        }
    }

def gen_dd(req):
    screen_name = req.screenName
    doc_type = getattr(req, "type", "screen") or "screen"

    # 1. Fetch DD data
    dd_data = get_dd_data(screen_name)
    if not dd_data:
        try:
            repo = Layer1Repo()
            dd_data = repo.get_dd_code_json_unified(screen_name)
        except Exception as e:
            return {"success": False, "error": f"DD data not ready for '{screen_name}': {e}"}

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

    excel_filename = f"{screen_name}.xlsx"
    excel_path = OUTPUT_DIR / "DD" / item_type / excel_filename
    
    docx_filename = f"{screen_name}.docx"
    docx_path = OUTPUT_DIR / "DD" / item_type / docx_filename

    # 3. Generate Excel
    try:
        if item_type == "report":
            import fill_dd_excel_report
            fill_dd_excel_report.fill_excel(DD_REPORT_TEMPLATE, dd_data, excel_path)
        elif item_type == "macro":
            import fill_dd_excel_macro
            fill_dd_excel_macro.fill_excel(DD_MACRO_TEMPLATE, dd_data, excel_path)
        elif item_type == "module":
            import fill_dd_excel_module
            fill_dd_excel_module.fill_excel(DD_MODULE_TEMPLATE, dd_data, excel_path)
        else:
            import fill_dd_excel_frm
            fill_dd_excel_frm.fill_excel(DD_SCREEN_TEMPLATE, dd_data, excel_path)
    except Exception as e:
        print(f"[ERROR] DD Excel Gen Failed: {e}")
        return {"success": False, "error": f"DD Excel generation failed: {e}"}

    # 4. Generate Word
    try:
        from scripts.fill_docx import build_dd_docx
        build_dd_docx(dd_data, docx_path)
    except Exception as e:
        print(f"[ERROR] DD Word Gen Failed: {e}")

    return {
        "success": True,
        "file_info": {
            "url": f"/api/l3/download/DD/{item_type}/{excel_filename}",
            "docx_url": f"/api/l3/download/DD/{item_type}/{docx_filename}"
        }
    }

def gen_all(req):
    screen_name = req.screenName

    # 1. Run both generations
    res_bd = gen_bd(req)
    res_dd = gen_dd(req)

    zip_filename = f"{screen_name}_all.zip"
    zip_path = OUTPUT_DIR / "ALL" / "screen" / zip_filename
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. Compress files
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if res_bd.get("success"):
                bd_folder = "report" if "report" in res_bd["file_info"]["url"] else "screen"
                bd_excel = OUTPUT_DIR / "BD" / bd_folder / f"{screen_name}.xlsx"
                bd_docx = OUTPUT_DIR / "BD" / bd_folder / f"{screen_name}.docx"
                if bd_excel.exists():
                    zipf.write(bd_excel, arcname=f"BD/{bd_folder}/{screen_name}.xlsx")
                if bd_docx.exists():
                    zipf.write(bd_docx, arcname=f"BD/{bd_folder}/{screen_name}.docx")

            if res_dd.get("success"):
                parts = res_dd["file_info"]["url"].split('/')
                dd_type = parts[-2] if len(parts) >= 2 else "screen"
                dd_excel = OUTPUT_DIR / "DD" / dd_type / f"{screen_name}.xlsx"
                dd_docx = OUTPUT_DIR / "DD" / dd_type / f"{screen_name}.docx"
                if dd_excel.exists():
                    zipf.write(dd_excel, arcname=f"DD/{dd_type}/{screen_name}.xlsx")
                if dd_docx.exists():
                    zipf.write(dd_docx, arcname=f"DD/{dd_type}/{screen_name}.docx")
    except Exception as e:
        print(f"[ERROR] Zip compression failed: {e}")
        return {"success": False, "error": f"Zip compression failed: {e}"}

    return {
        "success": True,
        "file_info": {
            "url": f"/api/l3/download/ALL/screen/{zip_filename}"
        }
    }

class MockFileResponse:
    def __init__(self, path, media_type):
        self.path = path
        self.media_type = media_type

def download_file(doc_kind, doc_type, filename):
    file_path = OUTPUT_DIR / doc_kind / doc_type / filename
    
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix == ".zip":
        media_type = "application/zip"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
    return MockFileResponse(str(file_path), media_type)
