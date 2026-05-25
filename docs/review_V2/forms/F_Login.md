# Review màn hình `F_Login` (Login)

> **Tài liệu review**:
> - BD (Basic Design / 画面仕様書): `WorkFlow_Output/forms/APP 148-03_画面仕様書_F_Login.xlsx`
> - DD (Detailed Design / プログラム・モジュール仕様書): `WorkFlow_Output/forms/APP 114_プログラム・モジュール仕様書_F_Login.xlsx`
>
> **Source đối chiếu**: `VBA_Export_All/Forms/F_Login.frm` (1420 dòng).
> **Ngày review**: 2026-05-12.

---

## Mục lục <a id="toc"></a>

- [1. Đánh giá tổng quan](#sec-overview)
- [2. Findings](#sec-findings)
- [3. Mapping spec ↔ source](#sec-mapping)
- [4. Code không cần migrate (dead code đã xác minh)](#sec-deadcode)
- [5. Khuyến nghị](#sec-reco)

---

## 1. Đánh giá tổng quan <a id="sec-overview"></a>

| Tiêu chí | Điểm (5) | Ghi chú |
|---|---|---|
| Completeness | **3/5** | Bao phủ tốt event handler chính. Thiếu mô tả: admin auto-login (whitelist 6 user) ở F000, Dev mode bypass ở F003. |
| Accuracy | **4/5** | Các module có spec đều mô tả đúng logic; chỉ thiếu chứ không sai. |
| Consistency | **4/5** | Format chuẩn, mapping E↔F đầy đủ. Naming "論理名/物理名" trong sheet 画面編集 có vấn đề (xem F-04). |
| Migration-ready | **3/5** | Nếu re-implement theo spec, .NET sẽ bị regression 2 feature đang chạy trên prod (admin auto-login, dev mode). |

**Coverage source** (sau khi loại trừ dead code đã xác minh):
- 7/7 event handler đang dùng → đều có module ID (F000–F004, F008, F009). ✅
- 2 macro reference (E006, E007) → spec thể hiện qua layout sheet (no sheet riêng cần thiết, xem mục 4 §F-03).
- 13/13 controls trong BD layout sheet — đầy đủ. ✅

---

## 2. Findings <a id="sec-findings"></a>

| # | Mức | Vị trí | Mô tả |
|---|---|---|---|
| F-01 | **High** | DD F000 (Form_Open) | Thiếu logic admin auto-login: code dùng `WshNetwork.UserName` lấy user Windows, đối chiếu whitelist 6 user ID (`00105687`, `00110772A`, `00109978A`, `00109212A`, `00106601A`, `00124937A`) → auto paste password (`SendKeys "^(v)"`) + Enter. Spec chỉ mô tả đến step 2.8 (SetWindowTop), bỏ qua toàn bộ phần auto-login. Security-relevant. |
| F-02 | **High** | DD F003 (txtPass_AfterUpdate) | Thiếu Dev mode bypass: `isDevMode = IsLoginDevModeEnabled()`. Khi bật, cho phép password rỗng (skip check 2.2) và login bất kể password (`If isDevMode Or (res = Me.txtPass)`), có log riêng (`AppendDevLoginLog`). Theo `CLAUDE.md`, dev mode là dev-only — nên trong DD ghi rõ "không port sang .NET". |
| F-03 | **High** | DD F008_SelQuery01 | Query `Q000_T_ID_PASS` được tham chiếu trong code (`DoCmd.OpenQuery`) và sheet SelQuery, nhưng **không tồn tại** trong `VBA_Export_All/Queries/`. Cùng module F000 có `Q000_T_LoginUser` — có khả năng đổi tên hoặc bị xóa. Sheet SelQuery để trống SELECT/FROM/WHERE — chứng tỏ team cũng không tìm thấy. |
| F-04 | Medium | BD `画面仕様書(画面編集)` | Cột "論理名" chứa tên tiếng Nhật (`ログインID`, `閉じる`…) — đây thực ra là `Name=` trong `.frm` (physical name của Access). Cột "物理名" chứa định danh English camelCase (`txtID`, `lblShopInfo`…) — đây là tên đề xuất cho phía .NET. Naming bị đảo so với convention chung. |
| F-05 | Low | DD F000 step 2.7 | Window size 800×400 và coordinate (0,0) hard-coded — nên đưa vào config. |
| F-06 | Low | DD F002 step 2.2 | Registration number `900-79-00136-000` là magic — nên config. |
| F-07 | Low | BD `画面仕様書(画面編集)` | Cột `桁数`, `形式`, `必須`, `入力仕様`, `出力仕様` trống cho hầu hết control. Form Login đơn giản nên chấp nhận, nhưng các form CRUD cần điền đầy đủ. |
| F-08 | Low | BD layout sheet | "＜レコードソース＞ = Access配信日" — thực ra là RecordSource cho **control** `最新版公開日` (DLookup), không phải Form. Form F_Login không có RecordSource. |
| F-09 | Low | DD F008 step 2.5 | "バージョン情報が11" không giải thích "11 = Access 2003 (Office 2003)". Cần chú thích cho người đọc/translator. |

---

## 3. Mapping spec ↔ source <a id="sec-mapping"></a>

| Module | Spec sheet | VBA procedure | Source line | Trạng thái |
|---|---|---|---|---|
| F000 | `詳細仕様書_F000` + `F000_SelQuery01` | `Form_Open` | 857–1125 | ❌ thiếu admin auto-login (F-01) |
| F001 | `詳細仕様書_F001` | `Form_KeyDown` | 1408–1420 | ✅ |
| F002 | `詳細仕様書_F002` + `F002_SelQuery01` | `Form_Load` | 819–855 | ✅ |
| F003 | `詳細仕様書_F003` | `txtPass_AfterUpdate` | 1127–1269 | ❌ thiếu Dev mode (F-02) |
| F004 | `詳細仕様書_F004` | `閉じる_Click` | 1358–1362 | ✅ |
| F005 | `詳細仕様書_F005` | (label `施工店情報` event không impl) | 642 declared only | ✅ (なし phản ánh đúng; label declare `OnDblClick="[Event Procedure]"` nhưng không có Sub, không nơi gọi) |
| F006 | `詳細仕様書_F006` | macro `A_メニューバーを表示` (external) | label `ラベル142` Click | ✅ (chỉ cần reference, chi tiết xem macro spec) |
| F007 | (layout sheet only) | macro `M300_Splash(M)を開く` (external) | label `ラベル142` DblClick | ✅ (macro reference không cần sheet DD riêng) |
| F008 | `詳細仕様書_F008` + `F008_SelQuery01` | `パスワードテーブルを開く_DblClick` | 1271–1344 | ⚠️ query `Q000_T_ID_PASS` broken (F-03) |
| F009 | `詳細仕様書_F009` | `プロセス終了_DblClick` | 1346–1356 | ✅ |

---

## 4. Code không cần migrate (dead code đã xác minh) <a id="sec-deadcode"></a>

Đã xác minh bằng grep toàn bộ `VBA_Export_All/`: 4 procedure sau **chỉ định nghĩa**, không nơi nào gọi (kể cả trong macros, queries, forms khác):

| Procedure | Source line | Kết luận |
|---|---|---|
| `Public Function Login_Log_Append()` | 1397–1406 | Body có đường dẫn cố định `D:\Log\Login.txt` và 1 dòng Print bị comment. Hàm rỗng functional. **Dead code.** |
| `Sub HideNavigationPane()` | 1364–1374 | Utility ẩn navigation. Không gọi từ đâu. **Dead code.** |
| `Sub ShowNavigationPane()` | 1376–1386 | Toàn bộ body bị comment. **Dead code.** |
| `Sub MinimuizeNavigationPane()` | 1388–1395 | Utility minimize navigation. Không gọi từ đâu. **Dead code.** |

→ **Không tính là spec miss** (theo nguyên tắc đã thống nhất). Khuyến nghị team không cần migrate sang .NET.

---

## 5. Khuyến nghị <a id="sec-reco"></a>

Trước khi migrate F_Login sang C#.NET:

1. **[Bắt buộc]** Bổ sung spec cho F000 phần admin auto-login (whitelist + WshNetwork.UserName + SendKeys). Quyết định: giữ feature trong .NET hay bỏ?
2. **[Bắt buộc]** Bổ sung spec cho F003 phần Dev mode bypass. Theo `CLAUDE.md` thì dev mode là dev-only, nên đánh dấu "do not port to prod".
3. **[Bắt buộc]** Resolve broken query `Q000_T_ID_PASS` — verify với team có phải đã đổi tên thành `Q000_T_LoginUser` hay bị xóa.
4. **[Nên]** Sửa cột naming 論理名/物理名 trong sheet `画面仕様書(画面編集)` theo đúng convention.
5. **[Nên]** Bổ sung "依存モジュール" trong sheet 概要仕様書 liệt kê module ngoài form được gọi (`Common.bas` → `Judge_Inst`, `SetAccWinStyle`, `SetWindowTop`, `SetEnabledState`, `MenuBarTrue`, `StatusBar_True`, `タイマーを開く`, `IsLoginDevModeEnabled`, `AppendDevLoginLog`) — hỗ trợ planning migration order.
6. **[Nên]** Đưa magic numbers (window size 800×400, registration `900-79-00136-000`) vào config khi migrate.
