# BD/DD Review Checklist

> Checklist kiểm tra tính tuân thủ của các file BD/DD Excel với tiêu chuẩn định nghĩa trong `_STANDARD.md`.
> Nguồn gốc: Section 6 "Checklist review tổng hợp" + các quy ước section 1–5.

---

## 1. Checklist chung (mọi file)

| # | Hạng mục | BD Screen | DD Screen | BD Report | DD Report |
|---|----------|-----------|-----------|-----------|-----------|
| 1.1 | Tên file đúng pattern `APP <mã>_<種類>_<ID>_<名称>_<ver>.xlsx` | ✓ | ✓ | ✓ | ✓ |
| 1.2 | Sheet `変更履歴` có entry cho mọi version, không skip | ✓ | ✓ | ✓ | ✓ |
| 1.3 | Header sheet (システム名, 作成者, 作成日, 更新者, 更新日) điền đầy đủ ở mọi sheet (trừ `変更履歴`) | ✓ | ✓ | ✓ | ✓ |
| 1.4 | ID trong header sheet khớp ID trong tên file | ✓ | ✓ | ✓ | ✓ |
| 1.5 | Tên trường, label dùng tiếng Nhật; tên vật lý (controls, fields) dùng tiếng Anh | ✓ | ✓ | ✓ | ✓ |
| 1.6 | Phiên bản `0.x` = bản nháp; `1.x` = bản chính thức đã duyệt | ✓ | ✓ | ✓ | ✓ |

**Pattern tên file:**
- BD Screen: `APP 148-03_画面仕様書_<ID>_<名称>_<ver>.xlsx`
- DD Screen/Report: `APP 114_プログラム・モジュール仕様書_<ID>_<名称>_<ver>.xlsx`
- BD Report: `APP 148-06_帳票仕様書_<ID>_<名称>_<ver>.xlsx`

---

## 2. BD Screen — 画面仕様書

### 2.1. Cấu trúc file

- [ ] Đủ 3 sheet bắt buộc: `変更履歴`, `画面仕様書(レイアウト)`, `画面仕様書(画面編集)`.
- [ ] Với mỗi event có ghi DB → có sheet `画面仕様書（Exxx）` tương ứng.
- [ ] Với mỗi event xuất file → có sheet `ファイル仕様書（Exxx）` tương ứng.

### 2.2. Sheet `画面仕様書(レイアウト)`

- [ ] Có image (mock UI / screenshot) dán vào vùng cột A–AC.
- [ ] `＜レコードソース＞` liệt kê đủ tất cả query/table data source (1 dòng/1 query).
- [ ] `【処理概要】` mô tả bullet ngắn gọn các flow chính của màn hình.
- [ ] Event Table có `E000` = 初期処理 (page load).
- [ ] Event đánh số tăng dần, theo thứ tự top-to-bottom/left-to-right trên form.
- [ ] Mỗi event ghi DB → có ghi `「画面仕様書（Exxx）」シートを参照` trong イベント内容.
- [ ] Mỗi event xuất file → có ghi `「ファイル仕様書（Exxx）」シートを参照`.
- [ ] Tên物理 (cột 名前（物理）) dùng prefix đúng: `btn`, `cmb`, `txt`, `chk`, `tgl`, `uc`.

### 2.3. Sheet `画面仕様書(画面編集)`

- [ ] Mỗi item có đủ: I/O, 項目属性, 転送元ﾃｰﾌﾞﾙ名/項目名.
- [ ] Item Input: 必須/桁数/形式 điền đầy đủ (trống = không có yêu cầu).
- [ ] SubForm/UserControl: chỉ ghi 1 dòng tham chiếu file `*S1.xlsx`, không liệt kê control con.
- [ ] Tên vùng transfer source dùng dấu `[ ]`: ví dụ `[出荷実績_当日]`.

### 2.4. Sheet `画面仕様書（Exxx）`

- [ ] 1 sheet per event có ghi DB; tên sheet đúng định dạng `画面仕様書（E004）`.
- [ ] Mỗi row cập nhật DB có `確認項目` ở cột CHK.
- [ ] Số `確認項目` trong sheet = `試験項目数` ở header.
- [ ] Fix value được ghi rõ trong cột `転送元 項目名／固定値` (vd: `1固定`, `Now()`, `ログインしている社員番号`).

---

## 3. DD Screen — プログラム・モジュール仕様書 (Screen)

### 3.1. Cấu trúc file

- [ ] Đủ sheet: `変更履歴`, `概要仕様書`, `詳細仕様書_<画面ID>_NN` (1 sheet/module lớn), `SelQueryNN`/`UpdQueryNN`.

### 3.2. Sheet `概要仕様書`

- [ ] Có `パラメータ情報` (kể cả khi = `なし`).
- [ ] Module list khớp số lượng sheet `詳細仕様書`.
- [ ] `試験項目数` ở header = tổng số `確認項目` thực tế trong toàn file.

### 3.3. Sheet `詳細仕様書_<画面ID>_NN`

- [ ] 1 sheet per module/event lớn.
- [ ] Pseudo-code numbered tối đa 4 cấp (1. → 1.1. → 1.1.1. → 1.1.1.1.).
- [ ] Mỗi step gọi DB → tham chiếu đúng tên sheet `[<画面ID>_NNSelQueryMM]` hoặc `[<画面ID>_NNUpdQueryMM]`.
- [ ] Mỗi message error/confirm có đủ: タイトル / タイプ / ボタン / メッセージID / メッセージ.
- [ ] Cột ngoài cùng ghi `確認項目` cho mỗi step có test point.

### 3.4. Sheet `SelQueryNN` (SELECT)

- [ ] Có đủ 5 block: SELECT / FROM / WHERE / GROUP BY / ORDER BY.
- [ ] WHERE, GROUP BY, ORDER BY ghi `なし` nếu không dùng.
- [ ] Tên query đúng pattern: `<画面ID>_<module>SelQuery<2digit>` (vd: `FD010M_00SelQuery01`).
- [ ] Tham số đầu vào ghi dạng `<パラメータ名>.` (vd: `<cmbShipmentFactory>.`).

### 3.5. Sheet `UpdQueryNN` (UPDATE/INSERT/DELETE)

- [ ] Có block danh sách column cập nhật + điều kiện WHERE.
- [ ] Tên query đúng pattern: `<画面ID>_<module>UpdQuery<2digit>`.

---

## 4. BD Report — 帳票仕様書

### 4.1. Cấu trúc file

- [ ] Đủ 3 sheet bắt buộc: `変更履歴`, `帳票仕様書(レイアウト)`, `帳票仕様書（項目編集）`.

### 4.2. Sheet `帳票仕様書(レイアウト)`

- [ ] Có image của report layout.
- [ ] `＜レコードソース＞` liệt kê đủ query/table.
- [ ] `＜グループ化・並べ替え＞` ghi rõ group fields và sort order.
- [ ] Group nào có `改ページ` (page break) → ghi chú rõ.

### 4.3. Sheet `帳票仕様書（項目編集）`

- [ ] Section marker `＜...＞` đủ cho mọi section: ヘッダー/詳細/フッター + group header/footer.
- [ ] SubReport tham chiếu đúng file BD của SubReport.
- [ ] Mỗi field có đủ: 転送元テーブル名/項目名, 条件及び編集方法.

---

## 5. DD Report — プログラム・モジュール仕様書 (Report)

### 5.1. Cấu trúc file

- [ ] Đủ sheet: `変更履歴`, `概要仕様書`, `詳細仕様書_<帳票ID>`, `SelQueryNN`, (nếu có) `QA`.

### 5.2. Sheet `概要仕様書`

- [ ] Có `パラメータ情報`.
- [ ] Có `＜グループ化・並べ替え・改ページ＞`.
- [ ] Nếu có SubReport → có mục `＜<Sub>とリンク＞` với mapping field.

### 5.3. Sheet `詳細仕様書_<帳票ID>`

- [ ] Step 2.3 có tham chiếu file BD Report tương ứng.
- [ ] Mỗi query → có sheet SelQueryNN riêng.
- [ ] Cột `確認項目` đủ cho mọi step có test point.

### 5.4. Sheet `QA` (nếu có)

- [ ] Mọi câu hỏi trong sheet QA đã có câu trả lời.

---

## 6. Quy ước naming convention

### Control prefix (BD Screen — tên vật lý)

| Prefix | Loại control |
|--------|-------------|
| `btn` | Button |
| `cmb` | ComboBox / プルダウン |
| `txt` | TextBox |
| `chk` | CheckBox |
| `tgl` | ToggleButton |
| `uc` | UserControl / SubForm |

### ID pattern

| Loại | Pattern | Ví dụ |
|------|---------|-------|
| 画面ID (Main) | `<Prefix><3digit>M` | `FD010M`, `FA014` |
| 画面ID (SubForm) | `<Prefix><3digit>S<n>` | `FD010S1`, `FD010S2` |
| 帳票ID | `R<Prefix><3digit>` | `RD020`, `RS040M` |
| EventID | `E<3digit>` | `E000` (初期処理), `E001`... |
| ModuleID (DD) | `<画面ID>_<2digit>` | `FD010M_00`, `FD010M_03` |
| QueryName | `<画面ID>_<module>SelQuery<2digit>` | `FD010M_00SelQuery01` |
| MessageID | `MSG_<TYPE>_<3digit>` | `MSG_ERR_020` |

---

## 7. Ghi chú áp dụng cho project khác

Khi clone bộ template cho project mới:

1. **Replace tên hệ thống** `MONOSビルOM出荷` → tên hệ thống mới (search-replace mọi sheet).
2. **Replace prefix ID** (`FD010M`, `RS040M`, ...) → naming convention project mới.
3. **Giữ nguyên cấu trúc sheet, merge cells, column widths** — không reformat layout.
4. **Reset `変更履歴`** về 1 dòng `01 | <today> | 初版`.
5. **Cập nhật `案件番号`** theo project number mới.
6. **Empty vùng "image"** — chờ design layout xong mới paste.

---

> Tài liệu này extract từ `_STANDARD.md` ngày `2026-05-13`.
> Khi template gốc thay đổi, cập nhật lại checklist tương ứng.
