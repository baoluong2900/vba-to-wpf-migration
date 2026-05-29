# vba_brain — Design Documentation Standards (BD & DD Specifications)

This specification defines the strict standardization rules, naming conventions, and layout formats for Basic Design (BD) and Detail Design (DD) spreadsheets, serving as a comprehensive standard for system modernization.

---

## Table of Contents

- [1. Common Conventions](#1-common-conventions)
  - [1.1. File Naming Convention](#11-file-naming-convention)
  - [1.2. Version Control Conventions](#12-version-control-conventions)
  - [1.3. Identifier Conventions](#13-identifier-conventions)
  - [1.4. Control Naming Conventions (Physical Name)](#14-control-naming-conventions-physical-name)
  - [1.5. Documentation Header Banner](#15-documentation-header-banner)
- [2. Basic Design Screen (BD Screen) Specifications](#2-basic-design-screen-bd-screen-specifications)
  - [2.1. Change History Sheet (`変更履歴`)](#21-change-history-sheet-変更履歴)
  - [2.2. Screen Layout Sheet (`画面仕様書(レイアウト)`)](#22-screen-layout-sheet-画面仕様書レイアウト)
  - [2.3. Screen Editing Sheet (`画面仕様書(画面編集)`)](#23-screen-editing-sheet-画面仕様書画面編集)
  - [2.4. Event Database Sheet (`画面仕様書（Exxx）`)](#24-event-database-sheet-画面仕様書exxx)
  - [2.5. File Output Sheet (`ファイル仕様書（Exxx）`)](#25-file-output-sheet-ファイル仕様書exxx)
- [3. Detail Design Screen (DD Screen) Specifications](#3-detail-design-screen-dd-screen-specifications)
  - [3.1. Overview Sheet (`概要仕様書`)](#31-overview-sheet-概要仕様書)
  - [3.2. Detail Specification Sheet (`詳細仕様書_<ID>_<NN>`)](#32-detail-specification-sheet-詳細仕様書_id_nn)
  - [3.3. Select Query Specification Sheet (`SelQueryNN`)](#33-select-query-specification-sheet-selquerynn)
  - [3.4. Update Query Specification Sheet (`UpdQueryNN`)](#34-update-query-specification-sheet-updquerynn)
- [4. Basic Design Report (BD Report) Specifications](#4-basic-design-report-bd-report-specifications)
  - [4.1. Report Layout Sheet (`帳票仕様書(レイアウト)`)](#41-report-layout-sheet-帳票仕様書レイアウト)
  - [4.2. Report Field Editing Sheet (`帳票仕様書（項目編集）`)](#42-report-field-editing-sheet-帳票仕様書項目編集)
- [5. Detail Design Report (DD Report) Specifications](#5-detail-design-report-dd-report-specifications)
  - [5.1. Overview Sheet (`概要仕様書`)](#51-overview-sheet-概要仕様書)
  - [5.2. Detail Specification Sheet (`詳細仕様書_<ID>`)](#52-detail-specification-sheet-詳細仕様書_id)

---

## 1. Common Conventions

### 1.1. File Naming Convention
All design spreadsheets must follow this exact template:
```text
APP <CategoryCode>_<DocType>_<Identifier>_<JapaneseName>_<Version>.xlsx
```

| Category Code | Doc Type (種類) | Scope |
|---|---|---|
| `APP 148-03` | `画面仕様書` | BD Screen (Basic Design — Screen) |
| `APP 148-06` | `帳票仕様書` | BD Report (Basic Design — Report) |
| `APP 114` | `プログラム・モジュール仕様書` | DD Screen / DD Report (Detail Design) |

*Example:* `APP 148-03_画面仕様書_FD010M_出荷実績入力_1.2.xlsx`
- `FD010M` = Screen/Report ID
- `出荷実績入力` = Screen Name (Japanese)
- `1.2` = Current Version

### 1.2. Version Control Conventions
- `0.x` = Draft version / Under review.
- `1.x` = Approved official version. Increment the minor version (e.g., `1.1` to `1.2`) for major updates.
- Every release must add a corresponding entry to the `変更履歴` (Change History) sheet containing the update details and ticket number.

### 1.3. Identifier Conventions

| Component | Pattern | Example |
|---|---|---|
| Main Screen ID | `<Prefix><3digits>M` | `FD010M`, `FA014` |
| Subform ID | `<Prefix><3digits>S<Index>` | `FD010S1`, `FD010S2` |
| Report ID | `R<Prefix><3digits>` | `RD020`, `RS040M` |
| Event ID | `E<3digits>` | `E000` (初期処理/Load), `E001` (First Action)... |
| Module ID (DD) | `<ScreenID>_<2digits>` | `FD010M_00` (Init), `FD010M_03` (Action) |
| Query Name | `<ScreenID>_<ModuleID>SelQuery<2digits>` / `UpdQuery<2digits>` | `FD010M_00SelQuery01`, `FD010M_03UpdQuery01` |
| Message ID | `MSG_<TYPE>_<3digits>` | `MSG_ERR_020` |

### 1.4. Control Naming Conventions (Physical Name)
Physical control names on the UI must camelCase in English, matching their visual control category prefix:

| Prefix | Control Type | Example |
|---|---|---|
| `btn` | Button / command control | `btnSearch`, `btnConfirm` |
| `cmb` | ComboBox / Dropdown selection | `cmbShipmentFactory` |
| `txt` | TextBox / text input area | `txtShipmentNumber` |
| `chk` | CheckBox / toggle flag | `chkIsCompleted` |
| `tgl` | ToggleButton | `tglViewMode` |
| `uc` | UserControl / Embedded SubForm | `ucFD010S1` |

### 1.5. Documentation Header Banner
Every worksheet (except `変更履歴`) must feature a standardized metadata header banner in the upper-right section:
- **System Name (システム名):** Default is `MONOSビルOM出荷` (configurable per project).
- **Sub-System Name (サブシステム名):** Optional subcategory name.
- **Creator / Created Date (作成者 / 作成日):** Author and timestamp.
- **Updater / Updated Date (更新者 / 更新日):** Last modified author and timestamp.
- **Test Items (試験項目数 / 試験完了項目数):** Only on DD sheets to count the number of verification criteria.

---

## 2. Basic Design Screen (BD Screen) Specifications

### 2.1. Change History Sheet (`変更履歴`)
Standard table columns tracking modifications:
- **Revision (改訂):** Sequential index (`01`, `02`).
- **Date (年月日):** ISO format date.
- **Content (更新内容):** Bullet points of details.
- **Reason (更新 lý do / 案件番号):** Ticket number or trigger.
- **Author (作成・更新者) & Approver (承認者):** Sign-off logs.

### 2.2. Screen Layout Sheet (`画面仕様書(レイアウト)`)
- **Visual Mockup:** Pasted inside column range A–AC.
- **Record Sources (＜レコードソース＞):** List of queries/tables bound as data sources.
- **Process Overview (【処理概要】):** Bulleted high-level summary of the screen logic.
- **Event List Table:**
  - `E000` is reserved for `初期処理` (Form Load).
  - All events mapped top-to-bottom, left-to-right.
  - Events that execute database changes must map to a `画面仕様書（Exxx）` sheet.
  - Events exporting local files must map to a `ファイル仕様書（Exxx）` sheet.

### 2.3. Screen Editing Sheet (`画面仕様書(画面編集)`)
Maps control values, attributes, validations, and binding targets:
- **Logical Name / Physical Name:** Map Japanse labels to physical camelCase.
- **I/O Type:** `I` (Input), `O` (Output), `IO` (Both), or `-` (Static label).
- **Attribute / Digit Limits (項目属性 / 桁数):** E.g., `Text` (Varchar), `Number` (Decimal), with character limits.
- **Transfer Source (転送元テーブル名/項目名):** Reference tables bounded with bracket indicators, e.g., `[出荷実績_当日].[出荷数]`.

### 2.4. Event Database Sheet (`画面仕様書（Exxx）`)
Created for events triggering database CRUD updates:
- **Table Targets:** Identifies targeted tables (`G8`/`Y8`).
- **CRUD Steps Table:** Identifies specific targets and actions mapping input variables to table physical fields.
- **CHK Column:** Every DB update must define a test checklist index.

### 2.5. File Output Sheet (`ファイル仕様書（Exxx）`)
Similar structure to the Event Database sheet, but maps output parameters and headers to local spreadsheet templates or text exports.

---

## 3. Detail Design Screen (DD Screen) Specifications

### 3.1. Overview Sheet (`概要仕様書`)
- **Parameter Info (パラメータ情報):** Variables received at form initialization. If none, labeled `なし`.
- **Special Notes (特記事項):** General rules or security standards for the current screen.

### 3.2. Detail Specification Sheet (`詳細仕様書_<ID>_<NN>`)
- **Module ID & Name:** E.g., `FD010M_00` for Init.
- **Detailed Pseudo-code:** Written in structured hierarchical levels up to 4 levels deep (e.g., `1.`, `1.1.`, `1.1.1.`, `1.1.1.1.`).
- **SQL Call Outs:** Integrates target database procedures or queries mapped inside brackets, e.g., `[FD010M_00SelQuery01]`.
- **Message Prompts:** Defines title, buttons, ID, and localized Japanese message strings for UI prompt modals.
- **Verification Criteria (確認項目):** Checkboxes in the right-most column mapping test cases.

### 3.3. Select Query Specification Sheet (`SelQueryNN`)
- **SELECT / FROM / WHERE / GROUP BY / ORDER BY:** Divided into distinct rows. If a clause is empty, it is marked `なし`.
- **Parameters:** Prefixed with `<` and suffixed with `>.` to map parameters back to active UI control values.

### 3.4. Update Query Specification Sheet (`UpdQueryNN`)
Provides the explicit statement for `INSERT`, `UPDATE`, or `DELETE` statements with parameter mapping.

---

## 4. Basic Design Report (BD Report) Specifications

### 4.1. Report Layout Sheet (`帳票仕様書(レイアウト)`)
- **Image Mockup:** A graphic export of the print layout.
- **Groupings & Sorting (＜グループ化・並べ替え＞):** Explicit details on page breaking (改ページ) constraints and sorting headers.

### 4.2. Report Field Editing Sheet (`帳票仕様書（項目編集）`)
- Organized strictly by report layout sections: `ページヘッダー` (Page Header), `グループヘッダー` (Group Header), `詳細` (Detail Row), `グループフッター` (Group Footer), `ページフッター` (Page Footer).
- Sub-reports are clearly identified with references to their respective BD sub-reports.

---

## 5. Detail Design Report (DD Report) Specifications

### 5.1. Overview Sheet (`概要仕様書`)
Aggregates parameters, record sources, grouping settings, and linking attributes between Master and Detail reports for Sub-Report structures.

### 5.2. Detail Specification Sheet (`詳細仕様書_<ID>`)
Translates printing and sorting triggers into pseudo-code instructions, referencing corresponding queries mapped under specific `SelQuery` worksheets.
