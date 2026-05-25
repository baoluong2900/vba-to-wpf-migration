# Layer 1 — Access Parser & Aggregator

Thư mục này chứa toàn bộ các script parser và aggregator dùng để chuyển đổi, làm giàu dữ liệu và nạp cấu trúc Access thô (VBA code, SQL queries, Macro XML, UI Layout) từ thư mục `database_json/` vào MongoDB và tạo ra các file tham chiếu cục bộ.

---

## 1. Các Script Chính

| File | Chức năng |
|------|-----------|
| [frm_parser.py](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/frm_parser.py) | Parse Form/Report JSON (trích xuất control, event, mã nguồn VBA). |
| [query_parser.py](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/query_parser.py) | Parse câu lệnh SQL (SELECT, UPDATE, INSERT, crosstab) thành cấu trúc JSON. |
| [macro_parser.py](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/macro_parser.py) | Parse cấu trúc Macro XML và các điều kiện/action tương ứng. |
| [table_parser.py](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/table_parser.py) | Parse schema bảng dữ liệu (fields, data types, primary keys). |
| [aggregator.py](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/aggregator.py) | **Orchestrator**: Điều phối chạy các parser, phân tích liên kết VBA chéo, sinh file `reference_map.json` tĩnh. |
| [seed_db.py](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/seed_db.py) | Python utility dùng để seed các file JSON sau khi parse từ `database_json/` vào MongoDB. |
| [property_category_config.json](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/property_category_config.json) | File config ánh xạ các thuộc tính UI của MS Access sang categories chuẩn. |

---

## 2. Hướng dẫn chạy

### Bước 1: Trích xuất và làm giàu tham chiếu (Aggregator)
Chạy script `aggregator.py` để xử lý các file JSON thô trong `database_json/` và làm giàu các thuộc tính tham chiếu (references) của forms, reports, macros:

```bash
python3 -X utf8 backend/layer1/aggregator.py
```

- **Mục tiêu**: Script sẽ ghi các file JSON đã làm giàu vào thư mục `output/forms_report_json_refs/` (chia thành `forms_json`, `macro_json`...).
- **Tập tin tham chiếu tĩnh**: Đồng thời script sẽ tự động tạo ra file bản đồ tham chiếu chéo toàn diện tại:
  `output/forms_report_json_refs/reference_map.json`

### Bước 2: Seed dữ liệu vào MongoDB
Chạy script `seed_db.py` để nạp các file JSON từ `database_json/` vào MongoDB phục vụ cho các layer tiếp theo (Layer 2 & Layer 5):

```bash
python3 backend/layer1/seed_db.py
```

---

## 3. Cấu trúc File Bản đồ Tham chiếu (reference_map.json)

Tập tin `reference_map.json` được tổ chức như sau:

```json
{
    "forms": {
        "Tên_Form": {
            "forms": ["Danh sách các form tham chiếu tới"],
            "reports": ["Danh sách các report tham chiếu tới"],
            "queries": ["Danh sách các query tham chiếu tới"],
            "macros": ["Danh sách các macro được gọi"],
            "modules": ["Danh sách các module được gọi"],
            "tables": ["Danh sách các bảng được sử dụng"]
        }
    },
    "reports": { ... },
    "macros": { ... },
    "modules": { ... },
    "queries": { ... },
    "tables": { ... }
}
```
