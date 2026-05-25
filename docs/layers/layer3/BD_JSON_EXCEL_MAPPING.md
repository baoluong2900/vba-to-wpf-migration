# BD & DD JSON → Excel mapping

Tài liệu gắn với các script trong `02_tools/scripts/`: mô tả **key JSON**, **sheet**, **ô / cột** được ghi, và luồng file (template / input / output).

Chuẩn hóa giá trị (**BD và DD**, qua helpers chung trong `fill_bd_excel.py` / `fill_dd_excel_macro.py`):

- `null`, chuỗi rỗng, và `"N/A"` (không phân biệt hoa thường) → ô hiển thị trống.
- Chuỗi **bắt đầu bằng `=`**: ghi có **một apostrophe `' `** đầu (text), tránh Excel coi là công thức không hợp lệ (Access expression trong JSON).

**Bảng lặp** (変更履歴, レコードソース, …): template có **một** hàng mẫu; script nhân/bản và **giãn merge** theo merge dọc (xem `expand_table` / `template_span` trong code).

**Lư ý ô merge:** chỉ ghi vào ô **top-left** của vùng merge (tọa độ trong bảàng là cột đó).

---

## Scripts & đường dẫn (mặc định trong repo)

| Mục đích | Script | Template mặc định | Input mặc định | Output mặc định |
|----------|--------|-------------------|----------------|-----------------|
| BD màn hình | `fill_bd_excel.py` | `template/BD_Screen/bd_template.xlsx` | `inputs/BD_json/screen/*.json` | `outputs/BD_Output/screen/*.xlsx` |
| BD báo cáo | `fill_bd_report_excel.py` | `template/BD_Report/bd_report_template.xlsx` | `inputs/BD_json/report/*.json` | `outputs/BD_Output/report/*.xlsx` |
| DD màn hình (form / module / macro) | `fill_dd_excel_frm.py`, `fill_dd_excel_module.py`, `fill_dd_excel_macro.py` | `template/DD_Screen/dd_template.xlsx` | `inputs/DD_json/form/` hoặc `module/` | `outputs/DD_Output/form/` hoặc `module/` |
| DD báo cáo | `fill_dd_excel_report.py` | `template/DD_Report/dd_report_template.xlsx` | `inputs/DD_json/report/` | `outputs/DD_Output/report/` |

Template path luôn tính relative tới thư mục **`02_tools`**.

---

## Phần 1 — BD màn hình (`fill_bd_excel.py`)

Nguồn trích dẫn code: `02_tools/scripts/fill_bd_excel.py`, template **`02_tools/template/BD_Screen/bd_template.xlsx`**.

### JSON root (Basic Design screen)

Áp dụng cho header chung trên các sheet layout / chỉnh sửa / sự kiện (ngoại trừ 変更履歴 — xem riêng).

| Key JSON | Sheet | Ô Excel | Ghi chú |
|----------|-------|---------|---------|
| `system_name` | `画面仕様書(レイアウト)` | `G1` | |
| `subsystem_name` | `画面仕様書(レイアウト)` | `G2` | |
| `screen_id` | `画面仕様書(レイアウト)` | `G4` | |
| `screen_name` | `画面仕様書(レイアウト)` | `W4` | |
| `author` | `画面仕様書(レイアウト)` | `AO1` | |
| `updated_by` | `画面仕様書(レイアウト)` | `AO2` | |
| `created_date` | `画面仕様書(レイアウト)` | `AX1` | |
| `updated_date` | `画面仕様書(レイアウト)` | `AX2` | |
| (lặp cùng semantic) | `画面仕様書(画面編集)` | `G1`, `G2`, `G4`, `W4`, `AM1`, `AM2`, `AV1`, `AV2` | |
| (lặp cùng semantic) | `画面仕様書（E***）` | `G3`, `N3`, `G6`, `T6`, `AJ3`, `AN3`, `AR3`, `AV3` | Header sheet sự kiện (table update / file spec clone cùng layout) |
| `overview` | `画面仕様書(レイアウト)` | `E5` | **Fallback** khi `sheet_2_layout.description` trống |

**Sheet `変更履歴` (BD):** script **không** ghi block header root lên sheet này — chỉ `sheet_1_change_history.data[]`.

Key `sheet_name` trong mỗi section JSON **không** dùng để chọn sheet (tên sheet cố định theo template).

---

### `sheet_1_change_history`

| Sheet | `変更履歴` |

Hàng dữ liệu mẫu (**template row**) được **tự tìm**: cột `A` có text **「改訂」** (header), hàng ghi dữ liệu = hàng header + 1; nếu không tìm được thì **fallback** hàng `CH_TEMPLATE_FALLBACK` (`3` trong code — hành vi phụ thuộc template).

| Key JSON (`data[]`) | Cột Excel | Vùng merge (tham khảo) |
|---------------------|-----------|-------------------------|
| `revision` | `A` | A:B |
| `date` | `C` | C:E |
| `content` | `F` | F:Q |
| `reason` | `R` | R:AC |
| `updated_by` | `AD` | AD:AH |
| `approver` | `AI` | AI:AM |

`span` giữa các dòng logic = số hàng vật lý của một dòng template (merge dọc).

---

### `sheet_2_layout`

| Sheet | `画面仕様書(レイアウト)` |

| Key JSON | Ô Excel | Ghi chú |
|----------|---------|---------|
| `description` | `E5` | Nếu trống → dùng root `overview` |
| `timing` | `AI5` | |
| `constraints` | `E6` | |
| `screen_image` | Thay ảnh layout hoặc `A9` | Nếu resolve được file ảnh (xem `--image-dir` / `DEFAULT_IMAGE_DIR`) → chèn ảnh; nếu không, chuỗi truthy → ghi text vào `A9` |

#### `record_sources[]`

- Dò section **「＜レコードソース＞」** (cột `AM`); dữ liệu cột **`AN{row}`**.
- Phần tử object: dùng `query_name`; scalar: ghi nguyên chuỗi.

#### `process_overview[]`

- Dò **「【処理概要】」** (cột `AM`); dữ liệu **`AM{row}`**.
- Object: `summary_line`; scalar: ghi nguyên chuỗi.

#### `events[]`

- Dò hàng chứa **「イベントID」** (cột `A`); các cột trong `LAYOUT_EVENT_COL`:

| Key JSON | Cột Excel | Merge (ghi chú trong code) |
|----------|-----------|----------------------------|
| `event_id` | `A` | A:C |
| `type` | `D` | D:H |
| `logical_name` | `I` | I:O |
| `physical_name` | `P` | P:V |
| `title` | `W` | W:AC |
| `event_trigger` | `AD` | AD:AG |
| `event_content` | `AH` | AH:AS |
| `module_id` | `AT` | AT:AX |
| `notes` | `AY` | AY:BB |

**`action_type`:** **không** map sang Excel — trước khi ghi, key này bị **loại khỏi** object (**metadata JSON-only**).

---

### `sheet_3_screen_edit`

| Sheet | `画面仕様書(画面編集)` |

Đọc `sheet_3_screen_edit.items`. Hàng template **tự dò** (`locate_edit_template_row`; fallback row `10`).

| Key JSON | Cột Excel |
|----------|-----------|
| `item_no` | `A` |
| `logical_name` | `C` |
| `physical_name` | `H` |
| `io` | `M` |
| `item_attribute` | `O` |
| `attribute_digits` | `U` |
| `required` | `W` |
| `format` | `Y` |
| `other_input_checks` | `Z` |
| `source_table` | `AH` |
| `source_field_or_fixed_value` | `AN` |
| `output_format` | `AW` |
| `notes` | `AW` (**cột trùng** `output_format`) |

Trong vòng ghi JSON, **`notes` được xử lý sau `output_format`** nếu cả hai có mặt → giá trị cuối tại `AW` là `notes`.

---

### `sheet_4_table_update`

| Sheet pattern | `画面仕様書（E{n}）` |

Hỗ trợ dict `{ "header", "items" }`, danh sách các block có `sheet_name_pattern`, hoặc list flat (chi tiết trong docstring `handle_event_sheets`).

- **Không có item** trong toàn pipeline phù hợp → các sheet **`画面仕様書（…）`** không dùng sẽ bị **xóa** (logic trong `handle_event_sheets`).

#### `header`

| Key JSON | Ô Excel |
|----------|---------|
| `table_physical_name` | `G8` |
| `table_logical_name` | `Y8` |
| `update_type` | `AO8` |
| `event_id` | — | Không map vào cột bảng; dùng **nhóm** sheet trong một số mode |

#### `items[]` (sau `_normalize_event_style_item`: alias như `target_field_physical` → `physical_name`, …)

| Key JSON | Cột Excel |
|----------|-----------|
| `no` | `A` |
| `physical_name` | `C` |
| `logical_name` | `L` |
| `source_area` | `U` |
| `source_field` | `AC` |
| `condition` | `AK` |
| `chk` | `AS` |
| `remark` | `AU` |

---

### `sheet_5_file_spec`

**Được xử lý** bởi `handle_file_spec_sheets`:

- Sheets đích có tên bắt đầu bằng **`ファイル仕様書（`** (`SHEET_FILE_SPEC_PREFIX`).
- JSON: **danh sách các block dict** hoặc **một dict** có `header` / `items` (xem trong code).

Mỗi block:

| Key JSON | Mục đích |
|---------|----------|
| `sheet_name_pattern` | Tên sheet đích (**bắt buộc**), ví dụ `ファイル仕様書（E001）` |
| `header` | `{ "table_*" **hoặc** "file_name" / "file_type" … }` — map vào **`G8` / `Y8` / `AO8`** qua `fill_event_style_table_sheet` (physical→`file_name`, logical→`file_type` khi không có table fields) |
| `items[]` | Cùng layout cột **`EVENT_COL`** như sheet_4 |

Chạy **trước** `sheet_4` trong `fill_excel` để còn sheet mẫu để clone khi `sheet_4` rỗng.

---

### BD — key JSON không dùng để chọn sheet

- `sheet_1_change_history.sheet_name`
- `sheet_2_layout.sheet_name`
- `sheet_3_screen_edit.sheet_name`

Các key không liệt kê ở trên có thể bị bỏ qua.

---

## Phần 2 — BD báo cáo (`fill_bd_report_excel.py`)

- Template: **`template/BD_Report/bd_report_template.xlsx`**
- Default I/O: `inputs/BD_json/report` → `outputs/BD_Output/report`

Cấu trúc JSON **cùng họ** BD screen (`sheet_1`, `sheet_2_layout`, và các phần tùy chỉnh theo báo cáo). Khác biệt chính (xem docstring trong script):

- `sheet_5_file_spec`: ghi vào **`帳票仕様書（項目編集）`** (cùng bảng với chỉnh sửa item), không tạo thêm workbook sheet **`ファイル仕様書`** — output thường **3 worksheets**.
- Ưu tiên tra ảnh layout báo cáo: `Access_DesignView/Report` rồi `Form`; có `--image-dir`.

---

## Phần 3 — Detail Design (`fill_dd_excel_macro.py`)

Nguồn: **`02_tools/scripts/fill_dd_excel_macro.py`**; tái dùng helper từ `fill_bd_excel.py`.

### Template và prefix sheet

| Loại | Template mặc định |
|------|-------------------|
| Form / Module / Macro CLI | `template/DD_Screen/dd_template.xlsx` |
| Report CLI | `template/DD_Report/dd_report_template.xlsx` |

Trong workbook mẫu, tiền tố giả (ví dụ **`FD010M`**) được **`rename_sheets_to_screen_id`** theo **`screen_id`** trong JSON (`詳細仕様書_*`, `*SelQuery*`, `*UpdQuery*`).

### Chuỗi sheets / keys JSON được fill

| Thứ tự | Sheet (sau rename) | Nguồn JSON |
|--------|---------------------|------------|
| 1 | `変更履歴` | `sheet_1_change_history.data`; **header block** root (below) được gọi **`fill_common_header`** trên sheet này trước khi đổi dữ liệu (`fill_excel`). |
| 2 | `概要仕様書` | `sheet_2_overview` |
| 3 | `詳細仕様書_{screen_id}_{NN}` | `sheet_3_detail_specs.details[]` |
| 4 | `{screen_id}_{NN}SelQuery{MM}` | `sheet_4_sel_query_templates.sel_queries[]` |
| 5 | `{screen_id}_{NN}UpdQuery{MM}` | `sheet_5_upd_query_templates.upd_queries[]` |

Nếu `purge_extra_sheets` (default): các sheet chi tiết / query không còn mục JSON tương ứng có thể bị **xoá**.

---

### Header DD chung — `fill_common_header`  
(Các sheet 概要・詳細・Sel/Upd đều dùng các ô sau; không giống tọa độ BD screen.)

| Key JSON | Ô Excel |
|----------|---------|
| `system_name` | `E1` |
| `author` | `AD1` |
| `created_date` | `AK1` |
| `subsystem_name` | `E2` |
| `updated_by` | `AD2` |
| `updated_date` | `AK2` |
| `screen_id` | `E4` |
| `screen_name` | `R4` |
| `module_id` | `E5` | Chỉ ghi khi tham số không `None`; trên **`概要`** script truyền `"概要"` |
| `module_name` | `R5` |
| `test_item_count` | `AO2` | Chỉ trên các sheet có truyền (detail specs) |
| `test_completed_count` | `AP2` |

### `変更履歴` (DD vs BD)

Giống cột **`CH_COL`** BD (`revision`→`A`, `date`→`C`, …).

**Điểm khác BD:** trước khi điền các dòng `data`, sheet **`変更履歴`** nhận **header root** DD qua `fill_common_header` (xem bảng trên).

### `sheet_2_overview` — `概要仕様書`

- Sau `fill_common_header` với **`module_id="概要"`**.
- **`description`** → `B6`.
- **`parameter_info[]`**: các cột **`OV_PARAM_COL`** (`no`→`A`, `io`→`C`, `item_name`→`E`, `symbol_name`→`N`, `data_type`→`W`, `total_digits`→`Y`, `decimal_digits`→`AA`, `required`→`AC`, `notes`→`AE`). Hàng template tìm sau section 「パラメータ情報」, fallback có trong code (`OV_PARAM_FALLBACK`).
- **`special_notes`** → hàng được dò sau marker 「特記事項」 (**cột A** của hàng đó).

### `sheet_3_detail_specs` — các sheet **`詳細仕様書_*`**

Mỗi phần tử `details[i]` ghép sheet thứ *i* cùng thứ tự số (sau rename prefix).

Header: **`module_id` / `module_name` / test counts** như **`fill_detail_sheet`**; nếu có **`event_trigger`** hoặc **`event_content`** → gộp chuỗi và (khi ô trống) ghi **`AO7`**.

Body template (cây 1.初期処理…) **không** generate lại toàn phần — giữ khối trong file Excel.

### `sheet_4_sel_query_templates` — SelQuery

- Header query: **`E6`** mô tả (`description`/`overview`), **`E7`** `query_name`, **`E8`** `parameters` (list → nối bằng `、`).

- Bảng cột (**`SEL_COL`** sau marker 「SELECT句」): `no`/`table_name`/`column_name`/`display_name`/`remark` (`A`,`B`,`I`,`P`,`W` …).

### `sheet_5_upd_query_templates` — UpdQuery

- **`E9` / `Y9`**: `table_physical_name` hoặc `table_name`; `table_id` hoặc `table_logical_id`.

- Rows dưới header **`UPD_COL`**: `no`, `column_name`, `source_area`, `source_field`, `remark` (dò quanh **`WHERE句`** trong template để không phá cụm WHERE).

Đặt tên sheet query: ưu tiên **`sheet_name`**, rồi **`sheet_name_pattern`** (`{screen_id}`, `{nn}`, `{mm}`), mặc định theo **`{screen_id}_NN{Sel|Upd}QueryMM`**.

---

## Script tham chiếu

| Area | Scripts |
|------|---------|
| BD screen | `fill_bd_excel.py` · template `BD_Screen/bd_template.xlsx` |
| BD report | `fill_bd_report_excel.py` · `BD_Report/bd_report_template.xlsx` |
| DD macro (CLI đầy đủ) | `fill_dd_excel_macro.py` |
| DD per folder | `fill_dd_excel_frm.py`, `fill_dd_excel_module.py`, `fill_dd_excel_report.py` |
