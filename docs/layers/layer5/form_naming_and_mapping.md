# Quy ước đặt tên WPF và mapping Access → .NET (Forms, Queries, Macros)

## 1. Khóa nguồn (Access / MongoDB Layer 1)

| Loại | Collection | Khóa `name` |
|------|------------|-------------|
| Form | `forms` | Tên form Access / stem file `.frm` |
| Query | `queries_v2` | Tên query trong Access |
| Macro | `macros` | Tên macro (file `.mac` export) |

- **Nguồn danh sách (MongoDB):** script `scripts/export_forms_layer1.py` (mục 3).
- **Trùng `name`:** với **forms**, script vẫn dùng `_id` trong code để chọn một document khi trùng tên; với **queries** và **macros** chỉ lấy danh sách tên từ repo (`list_queries` / `list_macros`), dedupe theo tên và ghi tên trùng vào `duplicate_names_collapsed`. File raw **không** chứa `_id` — chỉ mảng tên (`string[]`).

## 2. Quy ước đặt tên WPF (MVVM)

| Thành phần | Quy ước | Ví dụ |
|------------|----------|--------|
| View (XAML) | PascalCase, hậu tố `View` | `F004AfterEstimate2InquiryView` |
| ViewModel | Cùng stem + `ViewModel` | `F004AfterEstimate2InquiryViewModel` |
| Subform / màn phụ | Hậu tố `SubForm` hoặc `SubView` thống nhất toàn dự án | `...SubFormView` |
| In báo / preview | Hậu tố `Print` hoặc tách `PrintPreview` nếu cần | `...PrintView` |
| UserControl tái sử dụng | `...Control` hoặc `...Panel` | Theo OM |

**Prefix mã màn hình:** Giữ mã `F004`, `C000`, … ở đầu tên class giúp tra cứu chéo với BD/DD và VBA `OpenForm`.

**Biến thể tiếng Nhật trong tên Access:** Map cố định (照会 → Inquiry, 編集 → Edit, 連続 → Batch, …) — bảng gợi ý nằm trong `scripts/export_forms_layer1.py` (`_REPLACEMENTS`); mở rộng khi gặp form mới.

## 3. Xuất danh sách từ MongoDB (Layer 1)

Từ thư mục `03_agents/workflow/` (có `config.json` / `backend/layer2/.env` trỏ đúng `MONGO_URI`, `MONGO_DB`):

```bash
python -X utf8 scripts/export_forms_layer1.py
```

**Output `docs/mappings/`:**

| File | Nội dung |
|------|-----------|
| `forms_layer1.json` | `forms`: mảng tên (`string[]`) + metadata + `duplicate_names_collapsed` |
| `form_access_to_wpf.json` | `access_form_name` + `wpf_view_name` / `wpf_viewmodel_name` (gợi ý, cần review) |
| `queries_layer1.json` | `queries`: mảng tên + `duplicate_names_collapsed` |
| `query_access_to_dotnet.json` | `access_query_name` + `suggested_dotnet_type_name` (cần review) |
| `macros_layer1.json` | `macros`: mảng tên + `duplicate_names_collapsed` |
| `macro_access_to_dotnet.json` | `access_macro_name` + `suggested_dotnet_type_name` (cần review) |

`--dry-run`: in tóm tắt (count + đường dẫn + trùng tên), không ghi file.

## 4. Liên hệ kiến trúc

- Forms → Views / ViewModels: `docs/architecture_vba_brain_v1.md` §3.1.
- Clean Architecture + MVVM: `docs/architecture_OM.md`.

## 5. Khác với `logical_to_physical.json`

File `backend/layer2/schema/logical_to_physical.json` map **cột bảng** (論理名 ↔ 物理名), **không** thay thế file mapping form này.