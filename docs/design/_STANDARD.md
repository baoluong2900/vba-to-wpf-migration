# vba_brain — Tiêu chuẩn tài liệu Thiết kế (BD/DD Screen & Report)

> Tài liệu chuẩn rút ra từ các template trong folder `Design_template/`, dùng để **review** và **áp dụng cho project khác** thuộc cùng phương pháp luận.
>
> **Nguồn tham chiếu** (file đại diện đã phân tích):
> - BD Screen: `BD_Screen/APP 148-03_画面仕様書_FD010M_出荷実績入力_1.2.xlsx`, `BD_Screen/APP 148-03_画面仕様書_FA014_配車手配_1.3.xlsx`, `BD_Screen/APP 148-03_画面仕様書_FD010S1_出荷実績入力_1.2.xlsx` (SubForm)
> - DD Screen: `DD_Screen/APP 114_プログラム・モジュール仕様書_FD010M_出荷実績入力_0.2.xlsx`, `DD_Screen/APP 114_プログラム・モジュール仕様書_FA014_配車手配_0.1.xlsx`
> - BD Report: `BD_Report/APP 148-06_帳票仕様書_RS040M_出荷物件一覧表_0.5.xlsx`, `BD_Report/APP 148-06_帳票仕様書_RD020_送り状_0.1.xlsx`
> - DD Report: `DD_Report/APP 114_プログラム・モジュール仕様書_RS040M_出荷物件一覧表_0.11.xlsx`, `DD_Report/APP 114_プログラム・モジュール仕様書_RS020_出荷予定物量_0.2.xlsx`

---

## Mục lục

- [1. Quy ước chung](#sec-common)
- [2. BD Screen — 画面仕様書 (Basic Design)](#sec-bd-screen)
  - [2.1. Sheet `変更履歴` — Lịch sử thay đổi](#sec-bd-screen-history)
  - [2.2. Sheet `画面仕様書(レイアウト)` — Layout & Event](#sec-bd-screen-layout)
  - [2.3. Sheet `画面仕様書(画面編集)` — Field/Control mapping](#sec-bd-screen-edit)
  - [2.4. Sheet `画面仕様書（Exxx）` — Table Update Spec (per Event)](#sec-bd-screen-eevent)
  - [2.5. Sheet `ファイル仕様書（Exxx）` — File Output Spec (per Event)](#sec-bd-screen-fileevent)
  - [2.6. Variant: SubForm (`*S1/S2/...`)](#sec-bd-screen-subform)
- [3. DD Screen — プログラム・モジュール仕様書 (Detail Design – Screen)](#sec-dd-screen)
  - [3.1. Sheet `変更履歴`](#sec-dd-screen-history)
  - [3.2. Sheet `概要仕様書` — Overview & Parameters](#sec-dd-screen-overview)
  - [3.3. Sheet `詳細仕様書_<画面ID>_<モジュール>` — Detail Spec per module](#sec-dd-screen-detail)
  - [3.4. Sheet `<画面ID>_<モジュール>SelQueryNN` — SELECT Query Spec](#sec-dd-screen-selquery)
  - [3.5. Sheet `<画面ID>_<モジュール>UpdQueryNN` — UPDATE/INSERT/DELETE Query Spec](#sec-dd-screen-updquery)
- [4. BD Report — 帳票仕様書 (Basic Design – Report)](#sec-bd-report)
  - [4.1. Sheet `変更履歴`](#sec-bd-report-history)
  - [4.2. Sheet `帳票仕様書(レイアウト)` — Report Layout, RecordSource, Group/Sort](#sec-bd-report-layout)
  - [4.3. Sheet `帳票仕様書（項目編集）` — Section/Field editing](#sec-bd-report-edit)
- [5. DD Report — プログラム・モジュール仕様書 (Detail Design – Report)](#sec-dd-report)
  - [5.1. Sheet `変更履歴`](#sec-dd-report-history)
  - [5.2. Sheet `概要仕様書` — Overview + Parameters + Group/Sort + SubReport link](#sec-dd-report-overview)
  - [5.3. Sheet `詳細仕様書_<帳票ID>` — Detail Spec](#sec-dd-report-detail)
  - [5.4. Sheet `<帳票ID>SelQueryNN`](#sec-dd-report-query)
  - [5.5. Sheet `QA` (tùy chọn)](#sec-dd-report-qa)
- [6. Checklist review tổng hợp](#sec-checklist)

---

<a id="sec-common"></a>
## 1. Quy ước chung

### 1.1. Convention tên file
```
APP <mã>_<種類>_<ID>_<名称>_<version>.xlsx
```
| Mã APP | 種類 (Loại tài liệu) | Phạm vi |
|--------|----------------------|---------|
| `APP 148-03` | `画面仕様書` | BD Screen (Basic Design – Screen) |
| `APP 148-06` | `帳票仕様書` | BD Report (Basic Design – Report) |
| `APP 114` | `プログラム・モジュール仕様書` | DD Screen / DD Report (Detail Design) |

Ví dụ: `APP 148-03_画面仕様書_FD010M_出荷実績入力_1.2.xlsx`
- `FD010M` = 画面ID/帳票ID
- `出荷実績入力` = 画面名/帳票名
- `1.2` = phiên bản

### 1.2. Convention version
- `0.x` → bản nháp / chưa duyệt (draft).
- `1.x` → bản chính thức đã duyệt; tăng minor mỗi lần update theo case number.
- Mỗi version phải có dòng tương ứng trong sheet `変更履歴` ghi rõ **更新内容** + **更新理由/案件番号**.

### 1.3. Convention ID
| Loại | Pattern | Ví dụ |
|------|---------|-------|
| 画面ID (Form chính / Main) | `<Prefix><3digit>M` | `FD010M`, `FA014` |
| 画面ID (SubForm) | `<Prefix><3digit>S<n>` | `FD010S1`, `FD010S2`, `FD010S3` |
| 帳票ID | `R<Prefix><3digit>` | `RD020`, `RS040M`, `RS040S` |
| イベントID (Event) | `E<3digit>` | `E000`=初期処理, `E001`=button đầu tiên... |
| モジュールID (DD) | `<画面ID>_<2digit>` | `FD010M_00`=初期処理, `FD010M_03`=実績確定 |
| Query名 | `<画面ID>_<モジュール>SelQuery<2digit>` / `UpdQuery<2digit>` | `FD010M_00SelQuery01`, `FD010M_03UpdQuery01` |
| メッセージID | `MSG_<TYPE>_<3digit>` | `MSG_ERR_020` |

### 1.4. Convention naming controls (vật lý/物理名)
- Prefix theo control type:
  - `btn` = Button (`btnSearch`, `btnClose`)
  - `cmb` = ComboBox / プルダウン (`cmbShipmentDate`)
  - `txt` = TextBox (`txtShipmentNumber`)
  - `chk` = CheckBox (`chkComplete`)
  - `tgl` = ToggleButton (`tglSelect`)
  - `uc` = UserControl/SubForm (`ucFD010S1`)
- Tên物理: camelCase tiếng Anh; tên論理: tiếng Nhật.

### 1.5. Convention header (chung cho mọi sheet trừ `変更履歴`)
Mọi sheet đều có block header thông tin tài liệu, gồm các trường:
| Trường | Vị trí điển hình | Ghi chú |
|--------|------------------|---------|
| システム名 | A1 | Fix: `MONOSビルOM出荷` (đổi theo project) |
| サブシステム名 | A2 | Có thể trống |
| プロジェクト名 | A2 (sheet `Exxx`) | Fix: `MONOS` |
| 画面ID/帳票ID/モジュールID | hàng 4-5 | Khớp với file name |
| 画面名/帳票名/モジュール名 | cạnh ID | |
| 作成者 / 作成日 | góc phải | Người tạo + ngày |
| 更新者 / 更新日 | góc phải | Cập nhật khi sửa |
| 試験項目数 / 試験完了項目数 | góc phải (chỉ DD) | Đếm số `確認項目` |

### 1.6. Văn phong & ngôn ngữ
- **Nhật là chính** cho tên trường, label, business rule.
- **Tiếng Anh** chỉ dùng cho tên物理 (controls, table fields).
- **Tiếng Việt** xuất hiện ở comment, draft (`0.x`); bản chính thức nên dịch sang Nhật.
- Trộn ngôn ngữ chỉ chấp nhận ở mục mô tả tự do, không chấp nhận trong tên trường.

### 1.7. Convention "確認項目"
- Cột ngoài cùng bên phải của các dòng có business logic, fix value = `確認項目`.
- Mỗi dòng `確認項目` = 1 test point khi IT.
- Tổng số `確認項目` trong sheet = `試験項目数` ở header.

### 1.8. Convention merge cell
- Header (hàng 1-8 tùy sheet) merge nhiều cell để tạo dạng form chuẩn.
- Vùng dữ liệu: mỗi "logical cell" merge nhiều cell theo grid (vd `A4:F4`, `G4:L4`...) để xếp cố định các trường thông tin.
- **Quy tắc review**: chiều rộng cột không được thay đổi, vì các template chuẩn dùng layout fixed-grid.

---

<a id="sec-bd-screen"></a>
## 2. BD Screen — 画面仕様書 (Basic Design)

### Cấu trúc file
1 file BD_Screen gồm **ít nhất 3 sheet bắt buộc** + N sheet sub:
| Bắt buộc | Sheet | Mô tả |
|----------|-------|-------|
| ✅ | `変更履歴` | Lịch sử thay đổi |
| ✅ | `画面仕様書(レイアウト)` | Layout + RecordSource + Event list |
| ✅ | `画面仕様書(画面編集)` | Chi tiết từng項目 (control) |
| ⚪ | `画面仕様書（Exxx）` | Spec update DB cho event có ghi DB (mỗi event ghi DB 1 sheet) |
| ⚪ | `ファイル仕様書（Exxx）` | Spec output file cho event có xuất file |

> Số lượng sheet `Exxx` = số event có cập nhật DB hoặc xuất file. Event chỉ điều hướng / hiển thị thì KHÔNG cần sheet riêng.

<a id="sec-bd-screen-history"></a>
### 2.1. Sheet `変更履歴`

**Mục đích**: Theo dõi lịch sử revision file.

**Format cố định**:
| Cột | Trường | Ghi chú |
|-----|--------|---------|
| A-B | 改訂 | Mã revision: `01`, `02`, `03` (2 chữ số, có thể là chữ Nhật khi version đặc biệt) |
| C-E | 更新日 | Ngày update (yyyy-mm-dd) |
| F-Q | 更新内容 | Mô tả nội dung sửa (nhiều dòng, line break `/`) |
| R-AC | 更新理由/案件番号 | Lý do/Số case (vd `IT案件対応/202501R076`) |
| AD-AH | 更新者 | Người update (vd `RIKKEI) Chung`) |
| AI-AM | 承認者 | Người duyệt (vd `開発三課）川合`) |

**Rule**:
- Hàng 1: title `変更履歴`.
- Hàng 2: header cố định (kèm merge).
- Hàng 3 trở đi: mỗi revision 1 dòng, không xóa, chỉ append.
- Mỗi revision `02` trở đi phải bắt đầu bằng `バージョン<x.y>:` rồi mới đến nội dung.
- Bản đầu: nội dung = `初版`.

**Ví dụ thực tế** (FA014_配車手配_1.3):
```
01 | 2025-02-04 | 初版                                                       | IT案件対応/202501R076 | RIKKEI) Chi   | 開発三課）川合
02 | 2025-05-07 | バージョン1.2: ・画面仕様書(レイアウト)の＜レコードソース＞を更新 | IT案件対応/202501R076 | RIKKEI) Chung |
03 | 2025-10-16 | バージョン1.3: 結果台帳NO57による修正 ・...                   | IT案件対応/202501R076 | RIKKEI) Giap  |
```

<a id="sec-bd-screen-layout"></a>
### 2.2. Sheet `画面仕様書(レイアウト)` — Layout & Event

**Mục đích**: Mô tả tổng quan giao diện (mock image), nguồn data, và toàn bộ event của màn hình.

**Cấu trúc**:

#### Block 1 — Header file (R1-R4)
- R1: システム名, ロゴ "画面仕様書 （レイアウト）", 作成者
- R2: サブシステム名, 更新者
- R4: 画面ID, 画面名

#### Block 2 — Tổng quan chức năng (R5-R7)
- R5: `●機能概要：` + nội dung tóm tắt + `●タイミング：` + (随時/常駐...)
- R6: `●制約事項：` + ràng buộc (có thể trống)

#### Block 3 — Image + Concept (R8-R~)
- Cột trái (A-AC): vùng dán **イメージ** (screenshot của form).
- Cột phải (AD~BC): vùng **概要** chứa:
  - `＜レコードソース＞` + danh sách query/table data source. Liệt kê 1 query/1 dòng:
    ```
    FD010M_00SelQuery01
    FD010M_00SelQuery02
    ...
    ```
  - `【処理概要】` + bullet list các luồng xử lý của màn hình (・初期処理：... ・検索：... ・実績確定処理を行う...).

#### Block 4 — Event Table (cuối sheet)
Header (1 hàng, nhiều cell merge):
| イベントID | 種類 | 名前（論理） | 名前（物理） | 標題 | イベント | イベント内容 |
|-----------|------|-------------|--------------|------|----------|---------------|

| Cột | Mô tả | Giá trị mẫu |
|-----|-------|-------------|
| イベントID | Mã sự kiện | `E000`, `E001`, ... |
| 種類 | Loại control phát sinh event | `初期処理`, `ボタン`, `プルダウン`, `トグルボタン`, `テキスト`, `チェックボックス` |
| 名前（論理） | Tên tiếng Nhật | `条件解除`, `出荷工場` |
| 名前（物理） | Tên control thực tế | `btnClearConditions`, `cmbShipmentFactory` |
| 標題 | Caption hiển thị | thường giống名前（論理） |
| イベント | Loại event trigger | `画面開く時`, `クリック時`, `更新後処理` |
| イベント内容 | Business logic (mô tả nhiều dòng, dùng `/` xuống dòng) | tham chiếu sheet con `画面仕様書（Exxx）` |

**Rule**:
- `E000` luôn là `初期処理` (page load).
- Sau đó đánh số tăng dần theo thứ tự control trên form (top-to-bottom, left-to-right).
- Khi event có logic ghi DB → bắt buộc note `「画面仕様書（Exxx）」シートを参照` trong イベント内容.
- Khi event xuất file → note `「ファイル仕様書（Exxx）」シートを参照`.
- Khi event chuyển sang form/report khác → ghi rõ tên report/form đích.

**Ví dụ ngắn** (FD010M):
```
E000 | 初期処理      | ー               | ー               | ー        | 画面開く時 | 画面の初期表示の処理 ...
E001 | ボタン        | 条件解除          | btnClearConditions | 条件解除 | クリック時 | プルダウンの値をクリア（NULL）にする
E004 | ボタン        | 確定              | btnConfirm         | 実績確定 | クリック時 | 実績確定処理を実行（「画面仕様書（E004）」シートを参照）
E007 | プルダウン    | 出荷工場           | cmbShipmentFactory | 選択した値 | 更新後処理 | 出荷実績入力明細を再検索
```

<a id="sec-bd-screen-edit"></a>
### 2.3. Sheet `画面仕様書(画面編集)` — Field/Control mapping

**Mục đích**: Liệt kê chi tiết từng item trên màn hình, ánh xạ tới data source.

**Header (2 hàng merge)**:
| № | 画面項目名（論理名） | 画面項目名（物理名） | I／O | 項目属性 | 属性/桁数 | 入力仕様 (必須/桁数/形式/その他チェック) | 出力仕様 (転送元: ﾃｰﾌﾞﾙ名/項目名) |
|---|---------------------|---------------------|------|----------|-----------|------------------------------------------|----------------------------------|

| Cột | Mô tả | Giá trị mẫu |
|-----|-------|-------------|
| № | Mã item; **đồng bộ với イベントID** ở sheet trước (`E007`, `E008`...) hoặc đánh số seq cho item display-only | `E007`, `1`, `2` |
| 論理名 | Tên hiển thị tiếng Nhật | `出荷予定日` |
| 物理名 | Tên control trong code | `cmbShipmentScheduledDate` |
| I／O | `I` (input), `O` (output), `I/O` (cả hai) | |
| 項目属性 | Loại UI control | `プルダウン`, `テキスト`, `チェックボックス`, `ボタン`, `ユーザーコントロール` |
| 属性/桁数 | Kiểu data + max length | `文字列 8`, `日付`, `数値 4` |
| 必須 | Required hay không | `o` / blank |
| 桁数 | Số ký tự cho phép | |
| 形式 | Định dạng | `yyyyMMdd`, `半角英数` |
| その他入力値チェック | Validation rule extra | |
| 転送元 ﾃｰﾌﾞﾙ名/領域名 | Source table/region | `[出荷実績_当日]` (chú ý dấu ngoặc vuông) |
| 転送元 項目名/固定値 | Tên cột nguồn hoặc giá trị cố định | `出荷予定年月日` |

**Rule grouping**:
- Phân nhóm theo section của form dùng dòng tiêu đề (Roman numeral + tên section):
  ```
  I  | フォームヘッダー
  II | FD010S1 | ucFD010S1 | ユーザーコントロール   (SubForm references)
  III| FD010S2 | ucFD010S2 | ユーザーコントロール
  ```
- Khi item là SubForm/UserControl: chỉ ghi 1 dòng tham chiếu file `*S1.xlsx` (không liệt kê control con).

**Rule fill**:
- Item Output-only (display): chỉ cần điền `転送元`.
- Item Input: phải có `必須/桁数/形式` đầy đủ.
- Trống = không có yêu cầu (không phải "chưa làm").

<a id="sec-bd-screen-eevent"></a>
### 2.4. Sheet `画面仕様書（Exxx）` — Table Update Spec

**Khi nào tạo sheet này**: 1 sheet per event có ghi/cập nhật DB (vd `E004`=実績確定, `E005`=納品書印刷後ステータス更新). Đặt tên sheet đúng định dạng `画面仕様書（E004）`.

**Cấu trúc**:

#### Header (R2-R3)
| Cột | Trường |
|-----|--------|
| A-F | プロジェクト名 / システム名 / サブシステム名 |
| G-AB | 画面仕様書（テーブル更新） |
| AC- | 作成者 / 作成日 / 更新者 |

#### Identity (R6-R8)
- R6: `画面ID` + giá trị, `画面名` + giá trị.
- R8: `テーブル名(物理名)` + `TLD_...`, `テーブル(論理名)` + `出荷実績_当日`, `備考`, `更新`.

#### Body — Field update table (R9~)
Header 2 hàng:
| № | 項目名（物理名） | 項目名（論理名） | 転送元 ﾃｰﾌﾞﾙ名／領域名 | 転送元 項目名／固定値 | 条件及び編集方法 | CHK |
|---|------------------|------------------|------------------------|-----------------------|-------------------|-----|

**Rule**:
- `№` = thứ tự cột trong DB (vd `1, 2, 3, ..., 84, 92` — không liên tục, theo số column index của table gốc).
- Khi `転送元` để trống và `項目名／固定値` ghi giá trị → fix value (vd `1固定`, `2固定`, `Now()`, `ログインしている社員番号`).
- Khi 1 field có nhiều nguồn theo điều kiện → ghi nhiều dòng cùng `№`, hoặc dùng cột `条件及び編集方法` để mô tả switch logic (vd `検索条件： [汎用マスタ].区分コード ='S00'`).
- Cột `CHK` ngoài cùng = `確認項目` cho mỗi dòng có test point.

**Mỗi event = 1 sheet riêng**. Nếu event update nhiều bảng → vẫn 1 sheet, lặp lại block "Identity + Body" cho từng bảng (cách nhau bằng vùng trống).

<a id="sec-bd-screen-fileevent"></a>
### 2.5. Sheet `ファイル仕様書（Exxx）` — File Output Spec

**Khi nào dùng**: Event xuất file (Excel/CSV/PDF) — vd `E003`=物件情報更新チェック → MONOS_配車予定リスト.xlsx.

**Cấu trúc tương tự `画面仕様書（Exxx）`** nhưng:
- R5: `ファイル名` + tên file, `ファイルタイプ` + `*.xlsx` / `*.csv` / `*.pdf`, `備考`.
- Body: liệt kê toàn bộ column của file output, mỗi row 1 column.
- Khi column lấy từ nhiều source field gộp lại (concat / compute) → ghi nhiều row cùng `№`, để trống cột "項目名" ở các dòng sau, các dòng dồn vào cột `転送元` để liệt kê field nguồn, và cuối cùng có dòng tổng kết với `条件及び編集方法` mô tả công thức.

**Ví dụ** (FA014/E003 — column `車両備考`):
```
№49 車両備考 | [VLH_配車予定] | 車両制限区分名称  |  | 「{1} & {2} & {3} & {4}」を表示する
              | [VLH_配車予定] | 車制限           |  | ＊{1}: [車両制限区分] が Null でない場合: [車両制限区分名称]...
              | [VLH_配車予定] | 車両タイプ区分     |
              | [VLH_配車予定] | 車両タイプ        |
```

<a id="sec-bd-screen-subform"></a>
### 2.6. Variant — SubForm (`*S1`, `*S2`, `*S3`...)

**Khác biệt với main form**:

| Aspect | Main (`FD010M`) | SubForm (`FD010S1`) |
|--------|-----------------|---------------------|
| File name | `..._FD010M_..._<ver>.xlsx` | `..._FD010S1_..._<ver>.xlsx` |
| Quan hệ | Parent | Reference từ `画面仕様書(画面編集)` của main bằng dòng `ユーザーコントロール` |
| Số sheet `Exxx` | 1 sheet/event | Có thể tách `Exxx_01`, `Exxx_02` (vd `画面仕様書（E004_01）`, `（E004_02）`) khi 1 event có logic cho 2 branch (vd "全完了" vs "未完了") |
| RecordSource ở レイアウト | Liệt kê query main | Thường share với main, hoặc subset |
| イベント | Event of subform itself (selection change, row click) | Có thể không có event nào, chỉ là data display row |

**Rule**:
- Khi event chính có 2 nhánh logic ghi DB khác nhau → SubForm tách `Exxx_01` + `Exxx_02`, main form note `「画面仕様書（E003_01）」を参照する / 「画面仕様書（E003_02）」を参照する`.
- File main bắt buộc liệt kê SubForm trong sheet `画面仕様書(画面編集)` theo format:
  ```
  II | FD010S1 | ucFD010S1 | ユーザーコントロール
     | ソース「FD010S1_出荷実績入力」
     | ＊APP 148-03_画面仕様書_FD010S1_出荷実績入力.xlsxを参照
  ```

---

<a id="sec-dd-screen"></a>
## 3. DD Screen — プログラム・モジュール仕様書 (Detail Design – Screen)

### Cấu trúc file
DD Screen mở rộng từ BD Screen, có nhiều sheet hơn — mỗi event lớn → 1 sheet `詳細仕様書` + 0..N sheet query (`SelQuery*`, `UpdQuery*`).

| Bắt buộc | Sheet | Mô tả |
|----------|-------|-------|
| ✅ | `変更履歴` | Lịch sử |
| ✅ | `概要仕様書` | Tổng quan: tóm tắt module + parameter table + 特記事項 |
| ✅ | `詳細仕様書_<画面ID>_00` | Module 初期処理 (page load) |
| ⚪ | `詳細仕様書_<画面ID>_<NN>` | 1 sheet/event chính (`_01`=条件解除, `_03`=実績確定, `_04`=納品明細書...) |
| ⚪ | `<画面ID>_<NN>SelQuery<MM>` | Query SELECT của module |
| ⚪ | `<画面ID>_<NN>UpdQuery<MM>` | Query UPDATE/INSERT/DELETE |

**Ví dụ list sheet thực tế** (FD010M, 22 sheets):
```
変更履歴, 概要仕様書,
詳細仕様書_FD010M_00, FD010M_00SelQuery01..06,
詳細仕様書_FD010M_01,
詳細仕様書_FD010M_03, FD010M_03SelQuery01..02, FD010M_03UpdQuery01,
詳細仕様書_FD010M_04, FD010M_04SelQuery01, FD010M_04UpdQuery02,
詳細仕様書_FD010M_05..09
```

<a id="sec-dd-screen-history"></a>
### 3.1. Sheet `変更履歴`
Giống BD Screen (xem [§2.1](#sec-bd-screen-history)). Layout merge giống hệt.

<a id="sec-dd-screen-overview"></a>
### 3.2. Sheet `概要仕様書` — Overview & Parameters

**Cấu trúc**:

#### Header (R1-R4)
- システム名 / サブシステム名 / 作成者 / 作成日 / 更新者 / 更新日.
- 画面ID + 画面名.

#### Block "概要" (R5-)
- R5: tiêu đề `概要` + cột `戻り値` / cột `型` (cuối hàng).
- R6 onwards: bullet list các luồng xử lý của màn hình; mỗi bullet 1 dòng.
- Cuối block: 1 dòng tổng kết `コード` (loại trả về của module, vd `コード`).

#### Block "パラメータ情報" (R13-)
Header:
| No | I/O | 項目名称 | シンボル名 | タイプ | 全体桁 | 小数桁 | 必須 | 説明 |
|----|-----|----------|------------|--------|--------|--------|------|------|

- Khi module không có parameter: ghi 1 dòng `なし` ở cột 項目名称.

#### Block "特記事項" (R37 ~)
- Free text mô tả assumption / hạn chế.

**Ví dụ** (FD010M — chỉ có 戻り値):
```
概要:
 - 初期処理：検索条件データを取得し、出荷実績入力の全件明細を表示する。
 - 検索：抽出条件を選択し、出荷実績入力対象明細を表示する。
 - 出荷完了入力する。 / 出荷未完了入力する。 / 実績確定処理を行う。 / 納品明細書を印刷する。
戻り値: コード
パラメータ情報: なし
```

<a id="sec-dd-screen-detail"></a>
### 3.3. Sheet `詳細仕様書_<画面ID>_<NN>` — Detail Spec per module

**Mục đích**: Pseudo-code chi tiết của 1 module/event.

**Cấu trúc**:

#### Header (R1-R5)
- Common header (system, author, page count fields).
- R4: 画面ID, 画面名.
- R5: モジュールID (vd `FD010M_03`), モジュール名 (vd `実績確定処理`).
- R5 cuối hàng: cột `試験項目数` + `試験完了項目数` (đếm `確認項目`).

#### Body (R6 ~)
Header 1 hàng:
| 入力データ欄 | 処理記述 | 出力データ欄 | 結果確認 |
|--------------|----------|--------------|----------|

- **入力データ欄** (cột A-G): liệt kê DB/Query/dữ liệu input — vd `<DB> [出荷実績_当日]`, `<DB> [汎用マスタ]`.
- **処理記述** (cột H-AF): pseudo-code theo dạng outline numbered:
  ```
  【初期表示】
  1. 初期処理
     1.1. 初期処理情報登録
        部品名:    初期処理情報登録
        パラメータ:
        画面ID  | I | FD010M
        画面名  | I | 出荷実績入力
  2. 主処理
     2.1. 出荷予定日プルダウンリストを取得する。
        2.1.1. 「FD010M_00SelQuery01」を呼び出す
              Query名: FD010M_00SelQuery01
              パラメータ:
              出荷工場     | I | NULL
              出荷番号     | I | NULL
              ...
        2.1.2. 「2.1.1」から出荷予定日プルダウンリスト値を設定する。
  3. 終了処理
     なし
  ```
- **出力データ欄** (cột AG-AM): kết quả output, có thể trống nếu chỉ ghi DB.
- **結果確認** (cột AO-AP): điền `確認項目` cho mỗi step cần test.

**Rule**:
- Section trong `【】` (vd `【初期表示】`, `【「実績確定」ボタン押下時】`) gom các module liên quan đến 1 event hoặc 1 timing.
- Numbering: `1.` → `1.1.` → `1.1.1.` → ... đến tối đa 4 cấp.
- Mỗi sub-step liên quan đến Query phải:
  1. Liệt kê DB ở cột trái (`<DB> [テーブル名]`).
  2. Ghi `Query名` + tham chiếu sang sheet `<画面ID>_<NN>SelQueryNN` riêng.
  3. Bảng parameters dạng `tên | I/O | 編集仕様` (NULL hoặc literal).
- Khi step gọi sang sheet khác (vd "条件解除ボタン押下時 → 詳細仕様書_FD010M_01 を参照") thì ghi reference, không lặp lại nội dung.
- Mỗi message hiển thị (警告/エラー) phải có block:
  ```
  タイトル:   納品書印刷
  タイプ:     エラー
  ボタン:     OK
  メッセージID: MSG_ERR_020
  メッセージ: 出荷予定日が未入力です！
  ```

<a id="sec-dd-screen-selquery"></a>
### 3.4. Sheet `<画面ID>_<モジュール>SelQuery<NN>` — SELECT Query Spec

**Mục đích**: 1 sheet per SELECT query.

**Cấu trúc**:

#### Header (R1-R8)
- Common header.
- R4: 画面ID, 画面名.
- R5: モジュールID, モジュール名.
- R6: `概要` + tóm tắt 1 dòng (vd `出荷予定日プルダウンリストを取得する。`).
- R7: `Query名` + tên query (trùng tên sheet).
- R8: `パラメータ` + danh sách parameters (vd `出荷工場、出荷番号、到着予定年月日、物件番号、便区分`).

#### Block SELECT句 (R9-)
Header:
| No | テーブル名 | カラム名 | 表示名 | 備考 | 結果確認 |
|----|------------|----------|--------|------|----------|

- Mỗi row 1 column trong SELECT clause.
- `テーブル名` đặt trong dấu `[]` (vd `[出荷実績_当日]`).
- `表示名` (alias) = `カラム名` nếu không alias; khác nếu có `AS xxx`.

#### Block FROM句 (R13-)
- Format outline:
  ```
   | FROM
   |   | [出荷実績_当日] A
   |   | LEFT JOIN [汎用マスタ] B ON ...
  ```

#### Block WHERE句 (R17-)
- Mỗi điều kiện 1 dòng.
- Note: `※ パラメータがNULL以外のみ条件に追加する` để diễn đạt dynamic SQL.
- Có thể có note đặc biệt: `※ パラメータが「XX」以外のみ条件に追加する`.

#### Block GROUP BY句 (R25-)
- Liệt kê các column group hoặc `なし`.

#### Block ORDER BY句 (R28-)
- Tương tự.

**Ví dụ** (FD010M_00SelQuery01):
```
概要:    出荷予定日プルダウンリストを取得する。
Query名: FD010M_00SelQuery01
パラメータ: 出荷工場、出荷番号、到着予定年月日、物件番号、便区分

SELECT句:
  1 | [出荷実績_当日] | 出荷予定年月日 | 出荷予定年月日

FROM句:
  FROM
    [出荷実績_当日] A

WHERE句:
  WHERE
    A.出荷工場       = ＜パラメータ＞.出荷工場       ※ パラメータがNULL以外のみ条件に追加する
    AND A.出荷番号    = ＜パラメータ＞.出荷番号    ※ ...
    AND A.到着予定年月日 = ＜パラメータ＞.到着予定年月日 ※ ...

GROUP BY句:  出荷予定年月日
ORDER BY句:  なし
```

<a id="sec-dd-screen-updquery"></a>
### 3.5. Sheet `<画面ID>_<モジュール>UpdQuery<NN>` — UPDATE/INSERT Query Spec

**Cấu trúc tương tự SelQuery, khác ở**:
- Header thêm dòng:
  - R9: `テーブル名` + 論理名 (vd `出荷実績_当日`), `テーブルID` + 物理名 (vd `TLD_SHUKKA_JISSEKI_DAY`).
- Block chính:
  | No | カラム名 | 転送元 領域名 | 転送元 項目名/固定値 | 備考 | 結果確認 |
  |----|----------|---------------|----------------------|------|----------|
- Tiếp theo là block `WHERE句` (giống SelQuery).
- Không có `SELECT/GROUP BY/ORDER BY` block (vì là update/insert).

**Ví dụ** (FD010M_03UpdQuery01):
```
概要:       Xác nhận đơn hàng
Query名:    DBA0102_出荷実績確定
パラメータ: 企業コード、物件番号、見積受注連番、...
テーブル名: 出荷実績_当日     テーブルID: TLD_SHUKKA_JISSEKI_DAY

更新項目:
  1 | 出荷日           | ＜パラメータ＞ | 出荷日
  2 | 出荷処理         |              | 2固定
  3 | 小口伝票番号     | ＜パラメータ＞ | 出荷送り状番号
  4 | 輸送会社名       | ＜パラメータ＞ | 輸送会社名
  5 | 更新利用者コード  | ＜パラメータ＞ | 利用者の社員番号
  6 | 更新日時         |              | 現在時刻

WHERE句:
  WHERE
    企業コード        = ＜パラメータ＞.企業コード
    AND 物件番号      = ＜パラメータ＞.物件番号
    ...
    AND 出荷処理      = '1'
```

---

<a id="sec-bd-report"></a>
## 4. BD Report — 帳票仕様書 (Basic Design – Report)

### Cấu trúc file
BD Report **đơn giản hơn BD Screen** (không có Event Table, không có sheet `Exxx`):
| Bắt buộc | Sheet | Mô tả |
|----------|-------|-------|
| ✅ | `変更履歴` | Lịch sử |
| ✅ | `帳票仕様書(レイアウト)` | Layout + RecordSource + Grouping/Sorting |
| ✅ | `帳票仕様書（項目編集）` | Field/Section mapping |

<a id="sec-bd-report-history"></a>
### 4.1. Sheet `変更履歴`
Giống BD Screen. Layout merge giống hệt.

<a id="sec-bd-report-layout"></a>
### 4.2. Sheet `帳票仕様書(レイアウト)`

**Cấu trúc**:

#### Block 1 — Header
- R1: システム名 / `帳票仕様書 （レイアウト）` / 作成者
- R2: サブシステム名 / 更新者
- R4: 帳票ID, 帳票名

#### Block 2 — 機能 (R6-R7)
- R6: `●機能概要：` + tóm tắt + `●タイミング：` + (随時/...)
- R7: `●制約事項：`

#### Block 3 — Image + Concept (R9-)
- Cột trái: vùng dán **イメージ** của report.
- Cột phải: `概要` chứa:
  - `＜レコードソース＞` + danh sách source (query/view/table):
    ```
    QS020_積載物量
    [VLM_便種]
    ```
  - `＜グループ化・並べ替え＞`:
    - `グループ化`: liệt kê các trường group, có note `(改ページ)` khi cần page break.
    - `並べ替え`: liệt kê field sort + chiều (`(昇順)` / `(降順)`).

**Ví dụ** (RS040M):
```
＜レコードソース＞
   QS020_積載物量
   [VLM_便種]

＜グループ化・並べ替え＞
   グループ化
       出荷予定日
       到着予定日 (改ページ)
       出荷番号
   並べ替え
       拠点コード
```

<a id="sec-bd-report-edit"></a>
### 4.3. Sheet `帳票仕様書（項目編集）`

**Cấu trúc tương tự `画面仕様書(画面編集)` nhưng phân theo Section của Report**:

#### Header (R1-R6)
- Common header + 帳票ID + 帳票名.
- R6: `テーブル名` + `テーブルID` + `備考`.

#### Body
Header 2 hàng:
| № | 項目名 | 転送元 ﾃｰﾌﾞﾙ名／領域名 | 転送元 項目名／固定値 | 条件及び編集方法 | CHK |
|---|--------|------------------------|-----------------------|-------------------|-----|

**Quan trọng — Section markers**:
- Dùng dòng tiêu đề có dấu `＜...＞` để phân vùng:
  - `＜レポートヘッダ＞` (header toàn report)
  - `＜<groupField>ヘッダー＞` (vd `＜出荷番号ヘッダー＞`)
  - `＜詳細＞`
  - `＜<groupField>フッター＞`
  - `＜ページフッター＞`
  - `＜レポートフッター＞`

**Rule**:
- Item field thông thường: ghi đủ `転送元` + (nếu có) công thức ở cột `条件及び編集方法`.
- SubReport: ghi 1 dòng dạng:
  ```
  49 | ソース「RS040S_投入管理情報」 | サブレポート
     | ＊APP 148-06_帳票仕様書_RS040S_投入管理情報.xlsxを参照
  ```
- Field tính từ nhiều nguồn: liệt kê nhiều dòng, để trống `項目名` ở các dòng phụ, công thức ghi ở dòng đầu.

**Ví dụ section ＜レポートヘッダ＞** (RS040M):
```
1  | 出荷予定日  | [VLS_投入ヘッダ] | 出荷予定日   | "( " & [出荷予定日] & " )"
2  | 出荷工場    | [VLS_投入ヘッダ] | 出荷工場     | "( " & [出荷工場] & " )"
3  | ページ番号  |                |              | (現在時間.現在ページ/ページ数) 形式: yyyy-mm-dd hh:nn:ss / 00000
4  | 到着予定日  | [VLS_投入ヘッダ] | 到着予定日   | "( " & [MAX(到着予定日)] & " )"
```

---

<a id="sec-dd-report"></a>
## 5. DD Report — プログラム・モジュール仕様書 (Detail Design – Report)

### Cấu trúc file
DD Report nằm giữa DD Screen và BD Report:
| Bắt buộc | Sheet | Mô tả |
|----------|-------|-------|
| ✅ | `変更履歴` | Lịch sử |
| ✅ | `概要仕様書` | Overview + Parameters + Group/Sort + Link với SubReport |
| ✅ | `詳細仕様書_<帳票ID>` | Pseudo-code module print/preview |
| ⚪ | `<帳票ID>SelQueryNN` | Query SELECT (thường ≥ 1 query) |
| ⚪ | `QA` | Note QA (tùy chọn, dùng khi có question với khách hàng) |

> Khác DD Screen: KHÔNG chia theo "module event" — vì report chỉ có 1 flow chính là load + render. Tên sheet detail chỉ là `詳細仕様書_<帳票ID>` (không có `_NN`).

<a id="sec-dd-report-history"></a>
### 5.1. Sheet `変更履歴`
Giống BD/DD Screen.

<a id="sec-dd-report-overview"></a>
### 5.2. Sheet `概要仕様書`

**Cấu trúc tương tự DD Screen [§3.2](#sec-dd-screen-overview)** nhưng thêm 2 block đặc biệt:

#### Block "パラメータ情報"
Header:
| No | I/O | 項目名称 | シンボル名 | タイプ | 全体桁 | 小数桁 | 必須 | 説明 |
|----|-----|----------|------------|--------|--------|--------|------|------|

**Quan trọng**: Report PHẢI có parameter (ngược DD Screen có thể không). Vd `利用者の出荷工場` (input từ login), `出荷予定日開始/終了` (input từ form gọi report), với note `説明: FA012画面から` chỉ rõ form caller.

#### Block "特記事項"
Bao gồm:

##### 特記事項 ＜グループ化・並べ替え・改ページ＞
- Lặp lại từ BD report cho convenience:
  ```
  出荷予定日   | グループ化 | （昇順）
  到着予定日   | グループ化 | （昇順）  | 改ページ | （セクションの後）
  拠点コード   | 並べ替え   | （昇順）
  出荷番号    | グループ化 | （昇順）
  ```

##### 特記事項 ＜RS040Sとリンク＞ (chỉ khi có SubReport)
- Khi report có SubReport → khai báo mapping field giữa MainReport ↔ SubReport:
  ```
  リンク親フィールド | リンク子フィールド
       出荷予定日   |    出荷予定日
       出荷番号     |    出荷番号
  ```

<a id="sec-dd-report-detail"></a>
### 5.3. Sheet `詳細仕様書_<帳票ID>` — Detail Spec

**Cấu trúc giống DD Screen [§3.3](#sec-dd-screen-detail)** nhưng đơn giản hơn:

```
【初期表示】
1. 初期処理
   なし
2. 主処理
   2.1. 出荷搬入詳細一覧を取得する。
        <DB> [VLS_投入ヘッダ]    Query名: RS040MSelQuery01
        <DB> [VLS_出荷条件]      パラメータ:
        <DB> [VLM_便種]          利用者の出荷工場   | I | ＜パラメータ＞.利用者の出荷工場
                                  出荷予定日開始     | I | ＜パラメータ＞.出荷予定日開始
                                  ...
   2.2. 注残管理及び関連する入庫保管情報を取得する。
        部品名:  RS040S_投入管理情報 (※)
        パラメータ:
        利用者の出荷工場  | I | ...
        ※ 「APP 114_プログラム・モジュール仕様書_RS040S_投入管理情報」を参照する
   2.3. 帳票を表示する。
        2.3.1. 「2.1」「2.2」の情報に基づいて、帳票を作成する
               ※APP 148-06_帳票仕様書_RS040M_出荷物件一覧表を参照
3. 終了処理
   なし
```

**Rule**:
- Mỗi sub-query → tham chiếu sheet `<帳票ID>SelQueryNN` riêng.
- Khi có SubReport → ghi dạng "Call sub module" (vd `RS040S_投入管理情報`) + tham chiếu file DD của SubReport.
- 2.3 luôn là step "render report" → tham chiếu file BD `APP 148-06_帳票仕様書_...`.

<a id="sec-dd-report-query"></a>
### 5.4. Sheet `<帳票ID>SelQueryNN`

**Cấu trúc giống hệt DD Screen [§3.4](#sec-dd-screen-selquery)**. Khác duy nhất: ID là `<帳票ID>` (không có `_モジュール`).

**Note pattern Old/New query**:
- Có thể có comment ở cột `備考` chỉ ra query gốc trong Access, vd `Old query: QS020_積載物量`. Hữu ích cho migration.
- Query phức tạp (nested) thường được tách: vd `RS040MSelQuery01` SELECT từ `RS040MSelQuery02` (subquery thành sheet riêng).

<a id="sec-dd-report-qa"></a>
### 5.5. Sheet `QA` (tùy chọn)

- Sheet ghi câu hỏi với khách hàng / vấn đề phát sinh.
- Format tự do, 2-3 cột (B-C): câu hỏi + (answer).
- **Khi review**: kiểm tra mọi câu hỏi đã có câu trả lời trước khi finalize doc.

**Ví dụ** (RS040M):
```
Ở SVF có 2 tính năng dưới như access không?
   - Group on, sort by
   - Liên kết giữa sub report và report
In cả dữ liệu từ màn hình -> dùng bảng tạm?
```

---

<a id="sec-checklist"></a>
## 6. Checklist review tổng hợp

### 6.1. Cho mọi file
- [ ] Tên file đúng pattern `APP <mã>_<種類>_<ID>_<名称>_<ver>.xlsx`.
- [ ] Sheet `変更履歴` có entry cho mọi version, không skip.
- [ ] Header sheet (システム名, 作成者, 作成日, 更新者, 更新日) điền đầy đủ ở mọi sheet (trừ `変更履歴`).
- [ ] ID trong header sheet khớp ID trong tên file.
- [ ] Văn phong nhất quán Nhật cho tên trường; tiếng Việt/Anh chỉ ở comment.

### 6.2. BD Screen
- [ ] 3 sheet bắt buộc đủ.
- [ ] Sheet `レイアウト`:
  - [ ] Có image (mock UI).
  - [ ] `＜レコードソース＞` liệt kê đủ query/table.
  - [ ] `【処理概要】` mô tả bullet ngắn gọn các flow.
  - [ ] Event Table có `E000` = 初期処理.
  - [ ] Mỗi event ghi DB / xuất file → có tham chiếu sang sheet `Exxx` / `ファイル仕様書（Exxx）`.
- [ ] Sheet `画面編集`:
  - [ ] Mỗi item có I/O, 項目属性, 転送元.
  - [ ] Input item: 必須/桁数/形式 đủ.
  - [ ] SubForm reference đúng file path.
- [ ] Sheet `Exxx`: cột CHK có `確認項目` cho row có test point.

### 6.3. DD Screen
- [ ] Sheet `概要仕様書` có パラメータ情報 (kể cả `なし`).
- [ ] Số `試験項目数` ở header = số `確認項目` thực tế.
- [ ] Mỗi event lớn → 1 sheet `詳細仕様書_<画面ID>_NN`.
- [ ] Mỗi step gọi DB → tham chiếu đúng sheet `SelQueryNN`/`UpdQueryNN`.
- [ ] Pseudo-code numbered tối đa 4 cấp, mỗi message có `タイトル/タイプ/ボタン/メッセージID/メッセージ`.
- [ ] SelQuery: SELECT/FROM/WHERE/GROUP BY/ORDER BY đủ 5 block.
- [ ] UpdQuery: có block update column list + WHERE.

### 6.4. BD Report
- [ ] 3 sheet bắt buộc.
- [ ] Sheet `レイアウト`:
  - [ ] Image của report.
  - [ ] `＜レコードソース＞` + `＜グループ化・並べ替え＞` đủ.
  - [ ] Group nào có `改ページ` đã ghi note.
- [ ] Sheet `項目編集`:
  - [ ] Section marker `＜...＞` đủ (Header/Detail/Footer + group sections).
  - [ ] SubReport tham chiếu đúng file BD của SubReport.

### 6.5. DD Report
- [ ] `概要仕様書` có `パラメータ情報` + `＜グループ化・並べ替え・改ページ＞` + (nếu có SubReport) `＜<Sub>とリンク＞`.
- [ ] `詳細仕様書_<帳票ID>` có step 2.3 tham chiếu file BD Report.
- [ ] Mỗi query → sheet riêng.
- [ ] Sheet `QA` (nếu có) đã có câu trả lời cho mọi câu hỏi.

### 6.6. Áp dụng cho project khác
Khi clone bộ template cho project mới:
1. **Replace `MONOSビルOM出荷`** → tên hệ thống mới (search-replace mọi sheet).
2. **Replace prefix ID** (`FD010M`, `RS040M`, ...) → naming convention project mới (giữ chiều dài: 6 ký tự cho 画面ID, 6 ký tự cho 帳票ID).
3. **Giữ nguyên cấu trúc sheet, merge cells, column widths** — không reformat layout.
4. **Reset `変更履歴`** về 1 dòng `01 | <today> | 初版`.
5. **Cập nhật `案件番号`** theo project number mới.
6. **Empty các vùng "image"** — chờ design layout xong mới paste.

---

> File này được sinh tự động từ phân tích các template thực tế ngày `2026-05-13`.
> Khi template gốc thay đổi, cập nhật lại các bảng format/rule tương ứng.
