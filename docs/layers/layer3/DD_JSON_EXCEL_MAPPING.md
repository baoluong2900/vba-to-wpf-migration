# DD JSON → Excel mapping

Tài liệu dành riêng **Detail Design (DD)**: đổi JSON thiết kế chi tiết sang file Excel theo template trong `02_tools/template/`.

Implementation: **`02_tools/scripts/fill_dd_excel_macro.py`** (logic chính); helpers bảng/ghi ô dùng chung với BD từ **`fill_bd_excel.py`** (`expand_table`, `put`, `locate_template_row`, …).

Tài liệu tổng hợp BD + DD: [`BD_JSON_EXCEL_MAPPING.md`](BD_JSON_EXCEL_MAPPING.md).

---

## Chuẩn hoá giá trị (giống BD)

- `null`, chuỗi rỗng, `"N/A"` (không phân biệt hoa thường) → ô trống.
- Chuỗi bắt đầu bằng `=` được ghi như **text** (có prefix `'` trong cell) để tránh Excel coi là công thức lỗi.

---

## Scripts & đường dẫn (mặc định)

Mọi đường dẫn sau tính từ **`02_tools`** (thư mục chạy CLI khuyến nghị).

| Script | Template mặc định | Input mặc định | Output mặc định |
|--------|-------------------|----------------|----------------|
| `fill_dd_excel_frm.py` | `template/DD_Screen/dd_template.xlsx` | `inputs/DD_json/form/` | `outputs/DD_Output/form/` |
| `fill_dd_excel_module.py` | `template/DD_Screen/dd_template.xlsx` | `inputs/DD_json/module/` | `outputs/DD_Output/module/` |
| `fill_dd_excel_report.py` | `template/DD_Report/dd_report_template.xlsx` | `inputs/DD_json/report/` | `outputs/DD_Output/report/` |
| `fill_dd_excel_macro.py` | Screen: `DD_Screen/dd_template.xlsx` (`--template`, có default) | **Bắt buộc** `--input` và `--output` (một file / lần chạy) | Do người dùng chỉ định |

## Template màn hình DD (chuẩn vs gốc)

- **`template/DD_Screen/dd_template.xlsx`** — template mặc định của tool: **5 sheet** (変更履歴 · 概要仕様書 · **詳細×1** · **Sel×1** · **Upd×1**), bảng expandable đã làm trống, prefix giả **`FD010M`**. Đủ để `fill_dd_excel` nhân thêm sheet khi JSON nhiều hơn một query / module (clone từ một sheet mẫu mỗi loại).
- **`template/DD_Screen/dd_template.xlsx`** — bản legacy ~22 sheet (không sửa để tạo `standard`). Dùng `--full` khi build để giữ nguyên toàn bộ sheet.

Tạo lại bản chuẩn (ghi đè `dd_template.xlsx`):

```bat
cd 02_tools
python -X utf8 scripts/build_dd_screen_standard_template.py
```

Bản **đầy đủ sheet như legacy**:

```bat
python -X utf8 scripts/build_dd_screen_standard_template.py --full
```

---

```bat
cd 02_tools

REM Toàn bộ JSON trong thư mục form / module / report
python -X utf8 scripts/fill_dd_excel_frm.py
python -X utf8 scripts/fill_dd_excel_module.py
python -X utf8 scripts/fill_dd_excel_report.py

REM Một file cụ thể
python -X utf8 scripts/fill_dd_excel_frm.py -i "inputs/DD_json/form/F_Login 4.json"

REM Macro: template + input + output tùy ý
python -X utf8 scripts/fill_dd_excel_macro.py ^
  --input "inputs/DD_json/module/Common 1.json" ^
  --output "outputs/DD_Output/module/Common 1.xlsx"
```

Tuỳ chọn chung (CLI variant): `--mock-change-history`, `--keep-extra-sheets`. Macro tương đương có thêm `--template` nếu không dùng default screen template.

---

## Prefix sheet trong template và `screen_id`

Template gốc thường chứa tiền tố giả (**ví dụ `FD010M`**) trong tên một số sheet:

- `詳細仕様書_FD010M_01` → sau khi chạy → `詳細仕様書_{screen_id}_01`
- `FD010M_01SelQuery01` → `{screen_id}_01SelQuery01`
- `FD010M_01UpdQuery01` → `{screen_id}_01UpdQuery01`

Hàm **`_detect_template_prefix`** chọn prefix phổ biến nhất từ các tên sheet khớp regex; **`rename_sheets_to_screen_id`** thay bằng **`screen_id`** lấy từ JSON (và cắt tên sheet tối đa **31** ký tự Excel).

Tiếp theo script xử lý block detail / query theo **prefix đã đổi** (thường bằng `screen_id`).

---

## Root JSON (thiết kế DD)

Các key điển hình ở **root** của object JSON (cùng cấp các `sheet_*`):

| Key | Mục đích |
|-----|----------|
| `system_name`, `subsystem_name` | Header chung (`fill_common_header`) |
| `screen_id`, `screen_name` | Nhận dạng màn hình / báo cáo; dùng rename sheet |
| `author`, `created_date`, `updated_by`, `updated_date` | Metadata trên banner |

---

## Chuỗi sheet được fill (sau rename)

| STT | Sheet Excel (sau rename) | Khóa JSON |
|-----|--------------------------|-----------|
| 1 | `変更履歴` | `sheet_1_change_history` |
| 2 | `概要仕様書` | `sheet_2_overview` |
| 3 | `詳細仕様書_{screen_id}_{NN}` | `sheet_3_detail_specs.details[]` |
| 4 | `{screen_id}_{NN}SelQuery{MM}` | `sheet_4_sel_query_templates.sel_queries[]` |
| 5 | `{screen_id}_{NN}UpdQuery{MM}` | `sheet_5_upd_query_templates.upd_queries[]` |

Mặc định, sheet template **thừa** (không còn entry JSON tương ứng) có thể bị **xoá** (`purge_extra_sheets=True`). Dùng **`--keep-extra-sheets`** để giữ nguyên các sheet template dư.

---

## `fill_common_header` (banner 5 hàng — layout DD)

Dùng cho `変更履歴` (kèm data), `概要仕様書`, từng sheet **詳細**, và phần header chung của **SelQuery / UpdQuery**.

| Key JSON | Cell |
|----------|------|
| `system_name` | `E1` |
| `author` | `AD1` |
| `created_date` | `AK1` |
| `subsystem_name` | `E2` |
| `updated_by` | `AD2` |
| `updated_date` | `AK2` |
| `screen_id` | `E4` |
| `screen_name` | `R4` |
| `module_id` | `E5` | Chỉ khi được truyền (optional per sheet type) |
| `module_name` | `R5` |
| `test_item_count` | `AO2` | Chủ yếu sheet **詳細** |
| `test_completed_count` | `AP2` | Chủ yếu sheet **詳細** |

**Khác BD:** Sheet **`変更履歴`** với DD được gọi **`fill_common_header`** trước khi ghi các dòng `sheet_1_change_history.data`.

---

## `sheet_1_change_history`

`data[]` map vào các cột (cùng layout BD — `CH_COL`):

| Key | Cột Excel |
|-----|-----------|
| `revision` | `A` |
| `date` | `C` |
| `content` | `F` |
| `reason` | `R` |
| `updated_by` | `AD` |
| `approver` | `AI` |

Hàng template dòng dữ liệu tự dò nhờ marker 「**改訂**」 (`CH_TEMPLATE_FALLBACK` khi không tìm được).

**`--mock-change-history`:** Khi `data` rỗng, có thể chèn các dòng mẫu (`build_mock_change_history`), phục vụ preview template.

---

## `sheet_2_overview` — sheet `概要仕様書`

- `fill_common_header` với **`module_id="概要"`**.
- **`description`** → `B6`.

**`parameter_info[]`** — bảng sau section 「パラメータ情報」 (`OV_PARAM_COL`):

| Key | Cột Excel |
|-----|-----------|
| `no` | `A` |
| `io` | `C` |
| `item_name` | `E` |
| `symbol_name` | `N` |
| `data_type` | `W` |
| `total_digits` | `Y` |
| `decimal_digits` | `AA` |
| `required` | `AC` |
| `notes` | `AE` |

**`special_notes`** → marker 「特記事項」, ghi vào **cột A** của hàng tìm được.

---

## `sheet_3_detail_specs` — `詳細仕様書_*`

- Theo cặp thứ tự: phần tử `details[i]` với sheet `詳細仕様書_<prefix>_NN` (sắp xếp `NN`).
- Header: **`module_id`**, **`module_name`**, **`test_item_count`**, **`test_completed_count`**.
- Nếu có **`event_trigger`** / **`event_content`**: ghép một chuỗi và ghi **`AO7`** khi ô trống.
- Body mẫu (cấu trúc 1.初期処理 …) trong file Excel **được giữ**, script không generate full tree từ JSON.

---

## `sheet_4_sel_query_templates` — SelQuery

**Header một query:**

- `E6` — `description` hoặc `overview`
- `E7` — `query_name`
- `E8` — `parameters` (danh → nối `、`)

**Cột block SELECT** (`SEL_COL`; sau marker 「SELECT句」):

| Key | Cột Excel |
|-----|-----------|
| `no` | `A` |
| `table_name` | `B` |
| `column_name` | `I` |
| `display_name` | `P` |
| `remark` | `W` |

Có thể dùng key thay thế trong JSON — xem **`fill_sel_query_sheet`** (`columns` hoặc `select_columns`).

---

## `sheet_5_upd_query_templates` — UpdQuery

**Dòng meta bảng:**

- `E9` — `table_physical_name` hoặc `table_name`
- `Y9` — `table_id` hoặc `table_logical_id`

**Vùng cột cập nhật** (`UPD_COL`, trước phần WHERE trong template):

| Key | Cột Excel |
|-----|-----------|
| `no` | `A` |
| `column_name` | `B` |
| `source_area` | `K` |
| `source_field` | `T` |
| `remark` | `AC` |

Có thể dùng `columns` hoặc `update_columns`.

**Đặt tên sheet cho từng query (ưu tiên):**

1. `sheet_name` (dùng trực tiếp, có cắt 31 ký tự).
2. `sheet_name_pattern` — thay `{screen_id}`, `{nn}`, `{mm}`.
3. Mặc định `<screen_id>_00SelQuery{N}` / `_00UpdQuery{N}` theo chỉ mục (xem **`_resolve_query_sheet_name`**).

Nếu thiếu sheet đích và còn sheet mẫu cùng loại trong workbook → **copy worksheet** và đổi tên (`copy_worksheet`).

---

## Hằng số Python (tham chiếu code)

Trong **`fill_dd_excel_macro.py`**:

| Tên | Gợi ý |
|-----|-------|
| `DD_SCREEN_TEMPLATE` | Default path screen template |
| `DD_REPORT_TEMPLATE` | Default path report template |
| `cli_fill_dd_excel_variant(...)` | CLI batch theo loại (`form` / `module` / `report`) |

---

## File liên quan

| File | Nội dung |
|------|----------|
| `scripts/fill_dd_excel_macro.py` | Logic fill + rename sheet + CLI |
| `scripts/fill_dd_excel_frm.py` · `fill_dd_excel_module.py` · `fill_dd_excel_report.py` | Entry point theo thư mục input/output |
| `template/DD_Screen/dd_template.xlsx` | Template DD màn hình/module/form (mặc định) |
| `template/DD_Screen/dd_template.xlsx` | Legacy (nguồn cho script build template chuẩn) |
| `scripts/build_dd_screen_standard_template.py` | Tạo `dd_template.xlsx` từ `dd_template.xlsx` |
| `template/DD_Report/dd_report_template.xlsx` | Template DD báo cáo |
| [`BD_JSON_EXCEL_MAPPING.md`](BD_JSON_EXCEL_MAPPING.md) | Map BD + tóm tắt DD và chuẩn hoá dùng chung |
