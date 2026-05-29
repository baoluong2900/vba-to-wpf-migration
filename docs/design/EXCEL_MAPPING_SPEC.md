# BD & DD JSON-to-Excel Mapping Specification

This document details the mapping contract between pipeline **JSON properties** and **Excel spreadsheet worksheets, cells, and columns** as implemented by the Python tools.

---

## 1. Pipeline Automation Tools Reference

The Excel generation scripts are executed to populate standard Microsoft Excel sheets from pipeline outputs:

| Phase | Target | Execution Script | Default Template | Mapped JSON Source | Mapped Output Target |
|---|---|---|---|---|---|
| **BD** | Screen | `fill_bd_excel.py` | `template/BD_Screen/bd_template.xlsx` | `inputs/BD_json/screen/*.json` | `outputs/BD_Output/screen/*.xlsx` |
| **BD** | Report | `fill_bd_report_excel.py` | `template/BD_Report/bd_report_template.xlsx` | `inputs/BD_json/report/*.json` | `outputs/BD_Output/report/*.xlsx` |
| **DD** | Unified | `fill_dd_excel_macro.py` | Screen: `DD_Screen/dd_template.xlsx` | Direct filepath input | Customized target |
| **DD** | Folder | `fill_dd_excel_frm.py` / `module.py` / `report.py` | Matching type template | Directory of JSONs | Directory of Excel files |

---

## 2. Global Data Normalization & Formatting Rules

The mapping helpers (such as `expand_table` and `put` inside `fill_bd_excel.py`) enforce the following data parsing standard:
- **Null & Empty Values:** Properties with value `null`, empty string `""`, or case-insensitive `"N/A"` are parsed as empty cells.
- **Access Expressions & Formulas:** String properties starting with an equals sign `=` are prefix-appended with a single apostrophe `'` to be written strictly as static text, avoiding runtime Excel validation exceptions for unsupported formulas.
- **Vertical Merged Tables (Row Expansion):** If a list of records exceeds the single placeholder row in the template, the helper script duplicates rows and automatically stretches the vertical merged regions (vertical spans) down dynamically.
- **Merged Cell Coordinates:** Values are written exclusively to the **top-left** cell of any merged cell region.

---

## 3. Basic Design Screen Mapping Rules (`fill_bd_excel.py`)

### 3.1. General Screen Metadata (Header Banner)
Applicable to metadata header banners across worksheets `画面仕様書(レイアウト)` and `画面仕様書(画面編集)`:

| JSON Key | Target Sheet | Excel Cell | Description |
|---|---|---|---|
| `system_name` | Layout / Edit | `G1` / `G1` | Name of the software system |
| `subsystem_name` | Layout / Edit | `G2` / `G2` | Name of the subsystem |
| `screen_id` | Layout / Edit | `G4` / `G4` | Screen ID prefix |
| `screen_name` | Layout / Edit | `W4` / `W4` | Name of the screen |
| `author` | Layout / Edit | `AO1` / `AM1` | Created author name |
| `updated_by` | Layout / Edit | `AO2` / `AM2` | Last updated author name |
| `created_date` | Layout / Edit | `AX1` / `AV1` | Created date timestamp |
| `updated_date` | Layout / Edit | `AX2` / `AV2` | Last updated date timestamp |
| `overview` | Layout | `E5` | High-level summary (fallback value) |

### 3.2. Change History Sheet (`変更履歴`)
Table rows are mapped dynamically by scanning columns starting below the header cell `改訂` (Revision):

| JSON Key (`data[]`) | Target Column | Merged Range |
|---|---|---|
| `revision` | `A` | A:B |
| `date` | `C` | C:E |
| `content` | `F` | F:Q |
| `reason` | `R` | R:AC |
| `updated_by` | `AD` | AD:AH |
| `approver` | `AI` | AI:AM |

### 3.3. Screen Layout Sheet (`画面仕様書(レイアウト)`)
- **Graphic Image:** Inserts the form visualization mockup image starting at cell `A9`.
- **Record Sources (`record_sources[]`):** Populates the record source list inside the vertical grid beginning at column `AN` after search marker `＜レコードソース＞`.
- **Process Overview (`process_overview[]`):** Populates bullet points under column `AM` after search marker `【処理概要】`.
- **Events List (`events[]`):** Appends rows starting below columns under search header `イベントID`:

| JSON Key | Excel Column | Merged Range |
|---|---|---|
| `event_id` | `A` | A:C |
| `type` | `D` | D:H |
| `logical_name` | `I` | I:O |
| `physical_name` | `P` | P:V |
| `title` | `W` | W:AC |
| `event_trigger` | `AD` | AD:AG |
| `event_content` | `AH` | AH:AS |
| `module_id` | `AT` | AT:AX |
| `notes` | `AY` | AY:BB |

### 3.4. Screen Editing Sheet (`画面仕様書(画面編集)`)
Appends rows mapping active controls below the row containing search header `No.`:

| JSON Key | Excel Column | Description |
|---|---|---|
| `item_no` | `A` | Item index |
| `logical_name` | `C` | Logical field title (Japanese) |
| `physical_name` | `H` | Physical control name (camelCase English) |
| `io` | `M` | Input/Output direction classification |
| `item_attribute` | `O` | Data type format |
| `attribute_digits`| `U` | Character digit constraint limits |
| `required` | `W` | Mandatory input indicator checkbox |
| `format` | `Y` | Display format mapping |
| `other_input_checks`| `Z` | Validation expressions |
| `source_table` | `AH` | Source binding table |
| `source_field_or_fixed_value`| `AN` | Source binding field |
| `output_format` | `AW` | Display output criteria |

---

## 4. Detail Design (DD) Mapping Rules (`fill_dd_excel_macro.py`)

### 4.1. General Metadata (Header Banner)
Renders metadata blocks on `概要仕様書`, `詳細仕様書_*`, and query specifications:

| JSON Key | Target Excel Cell | Description |
|---|---|---|
| `system_name` | `E1` | Unified system name |
| `author` | `AD1` | Creator name |
| `created_date`| `AK1` | Created date timestamp |
| `subsystem_name`| `E2` | Subsystem name |
| `updated_by` | `AD2` | Modifier name |
| `updated_date`| `AK2` | Last updated timestamp |
| `screen_id` | `E4` | Unique screen index identifier |
| `screen_name` | `R4` | Screen description name |
| `module_id` | `E5` | Active module identifier |
| `module_name` | `R5` | Active module name |
| `test_item_count`| `AO2` | Total criteria count |

### 4.2. Overview Sheet (`概要仕様書`)
- **Main Description:** Populated inside cell `B6`.
- **Parameter Information Table (`parameter_info[]`):** Populates fields starting below search marker `パラメータ情報`:

| JSON Key | Excel Column | Description |
|---|---|---|
| `no` | `A` | Index |
| `io` | `C` | I/O classification |
| `item_name` | `E` | Argument logical name |
| `symbol_name`| `N` | Physical variable identifier |
| `data_type` | `W` | Variable type |
| `total_digits`| `Y` | Total size allocation |
| `notes` | `AE` | Details |

- **Special Notes:** Written directly inside column `A` of the row below the marker `特記事項`.

### 4.3. Detail Specification Sheet (`詳細仕様書_{ScreenID}_{NN}`)
- Populates structural pseudo-code and testing parameters.
- **Event Orchestration:** Renders `event_trigger` and `event_content` inside cell `AO7`.

### 4.4. Select Query Specification Sheet (`SelQueryNN`)
- **Query Metadata:** `E6` maps query description, `E7` maps query name, `E8` maps parameters.
- **Columns Table (`SELECT句`):**

| JSON Key | Excel Column | Description |
|---|---|---|
| `no` | `A` | Column index |
| `table_name` | `B` | Source table name |
| `column_name`| `I` | Physical column name |
| `display_name`| `P` | Logical output label |
| `remark` | `W` | Conditions / formula |

### 4.5. Update Query Specification Sheet (`UpdQueryNN`)
- **Query Metadata:** `E9` maps physical table target, `Y9` maps logical table target.
- **Columns Table (`WHERE句`):** Maps `no`, `column_name`, `source_area`, `source_field`, and `remark` columns directly.
