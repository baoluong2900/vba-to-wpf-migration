# Review màn hình `C000_MAINⅡ_未入金` (Danh sách chưa thu)

> **Tài liệu review**:
> - BD: `WorkFlow_Output/forms/APP 148-03_画面仕様書_C000_MAINⅡ_未入金.xlsx`
> - DD: `WorkFlow_Output/forms/APP 114_プログラム・モジュール仕様書_C000_MAINⅡ_未入金.xlsx`
>
> **Source đối chiếu**: `VBA_Export_All/Forms/C000_MAINⅡ_未入金.frm` (2772 dòng).
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

Màn hình danh sách hiển thị các hồ sơ chưa thu (未入金) — bind với query `C000_MAINⅡ_未入金_改`. Cho phép: xem chi tiết, xuất Excel, mở dữ liệu kỳ trước, in PDF (chưa implement).

| Tiêu chí | Điểm (5) | Ghi chú |
|---|---|---|
| Completeness | **4/5** | Bao phủ tốt 9 event chính (F000–F008). Thiếu: 2 sub `アフター管理終了_Click` và `終了A_Click` tồn tại trong source nhưng không có module ID. Cần verify có phải dead code hay không. |
| Accuracy | **4/5** | Các spec có module đều mô tả đúng logic. Một số chi tiết bị bỏ sót khi mô tả (xem F-04). |
| Consistency | **3/5** | Naming logical/physical đảo ngược như F_Login. Tên query trong spec dùng full-width `Ｑ` trong khi code dùng half-width `Q` (F-05). |
| Migration-ready | **4/5** | Đủ thông tin để migrate phần UI + Excel export. Phần SQL của RecordSource_SelQuery01-03 đã chi tiết hóa thành Oracle-dialect (LEFT JOIN, CASE, TO_CHAR…) — sẵn sàng cho .NET/EF. |

**Coverage source** (sau khi loại trừ dead code):
- 6/8 event handler trong source có module ID rõ ràng (F001-Form_Open, F004-戻る, F005-PDF作成, F006-エクセル書き出し, F007-未入金_前期).
- 2 sub `アフター管理終了_Click` và `終了A_Click` không xuất hiện trong spec → cần xác minh dead code (mục 4).
- 47/47 controls có trong sheet 画面編集 (bao gồm subform F021_NavigationButtons_S).

---

## 2. Findings <a id="sec-findings"></a>

| # | Mức | Vị trí | Mô tả |
|---|---|---|---|
| F-01 | **High** | DD F006 (エクセル書き出し_Click) | Thiếu mô tả: code có 2 lần `MsgBox`-confirm cancelled với `On Error Resume Next` (L2746-2750), và step 2.4 dùng `CreateObject("shell.application").ShellExecute CurrentProject.Path & "\アフター管理_エクセル\..."` — **path KHÁC** so với path delete (`C:\新アフター管理ＤＢ\アフター管理_エクセル\...` hard-coded). Spec mô tả 2.2 và 2.4 dùng cùng 1 path — không đúng với source. Nếu `CurrentProject.Path` khác `C:\新アフター管理ＤＢ` thì file ShellExecute mở sẽ KHÔNG phải file vừa export. Đây là lỗi tiềm ẩn cần verify. |
| F-02 | Medium | DD F005 (PDF作成_Click) | Mô tả spec ổn (chỉ là MsgBox dummy "対応中"). Nhưng cần ghi rõ "feature chưa được implement, chỉ là placeholder" — quyết định: .NET có cần implement PDF export hay không? |
| F-03 | Medium | DD F007 SelQuery01 / source | Tên query bất nhất: spec ghi `Ｑ011_期設定_前期テーブル作成` (full-width `Ｑ`), source code VBA dùng `Q011_期設定_前期テーブル作成` (half-width `Q`). File trong `VBA_Export_All/Queries/` cũng dùng full-width `Ｑ011_期設定_前期テーブル作成.sql.sql`. Có thể Access auto-resolve, nhưng khi migrate sang .NET cần thống nhất naming. |
| F-04 | Medium | DD F001 (Form_Open) | Source có nhiều bước "DoCmd.RunCommand acCmdAppMaximize" + "DoCmd.Maximize" lặp lại 3 lần (L2566, L2612, L2632). Spec gộp thành step 2.1 và 2.9 ("再度...最大化") — chấp nhận được nhưng nên ghi rõ "3 lần maximize" để khớp source (có thể là defensive coding để fix bug timing của Access). |
| F-05 | Medium | DD coverage | 2 sub `アフター管理終了_Click` (L2639-2658) và `終了A_Click` (L2660-2695) tồn tại trong source nhưng **không có module ID** trong spec và **không có control tương ứng** trong sheet 画面編集. Có thể là dead code (button đã bị xóa khỏi form nhưng code-behind chưa cleanup). Cần verify (xem mục 4). |
| F-06 | Medium | BD `画面仕様書(画面編集)` | Cột "論理名/物理名" bị đảo ngược như F_Login. Cùng pattern: 論理名 = `戻る/PDF作成/エクセル書き出し/未入金_前期` (tên `Name=` trong .frm), 物理名 = `cmdBack/cmdCreate PDF/cmdExportExcel/cmdUnpaid Previous Term` (tên đề xuất English camelCase). |
| F-07 | Low | DD F007 step 2.1 | "現在日付の12ヶ月前" — magic number nên đưa vào config (kỳ trước = 12 tháng trước hiện tại). Source: `Q011_期設定_前期` — không thấy explicit. |
| F-08 | Low | BD layout | "＜レコードソース＞" = `C000_MAINⅡ_未入金_改` — khớp source L27. ✅ Tốt hơn F_Login. |
| F-09 | Low | DD 概要仕様書 | パラメータ情報 ghi 5 trường (`txt連番, txt工事名称, txt期, txt請求先, txt店所`) là cross-form parameters (`[forms]![C000_MAINⅡ]![...]`). Spec mới ghi 4 trường có signature đầy đủ, trường 5 `txt店所` thiếu signature. Cần điền đầy đủ. |
| F-10 | Low | DD F005-F008 | Format dataset Excel export path hard-coded `C:\新アフター管理ＤＢ\アフター管理_エクセル\C000_MAINⅡ_未入金_EXCEL.xlsx` — magic path. Khi migrate phải đưa vào config. |
| F-11 | Low | DD F002, F003 | F002 (lblMenuBarTrue Click) — spec không có sheet riêng (chỉ là macro reference `M002_メニューバーを非表示`) — đúng convention.<br>F003 (lblMenuBarTrue DblClick) — có sheet ghi gọi macro `M001_メニューバーを表示` — OK. Tuy nhiên BD layout sheet ghi sai: E002 (Click) trong source là `OnClick="M002_メニューバーを非表示"` nhưng spec E002 mô tả là Click event và E003 là DblClick. Mapping đúng. |

---

## 3. Mapping spec ↔ source <a id="sec-mapping"></a>

| Module | Spec sheet | VBA procedure | Source line | Trạng thái |
|---|---|---|---|---|
| F000 | `詳細仕様書_F000` (なし) | (`OnCurrent="[Event Procedure]"` declared, no Sub) | L28 declared only | ✅ (なし phản ánh đúng) |
| F001 | `詳細仕様書_F001` | `Form_Open` | 2562–2637 | ✅ (chi tiết hơi gộp, xem F-04) |
| F002 | `詳細仕様書_F002` (なし) | macro `M002_メニューバーを非表示` | label `lblMenuBarTrue` OnClick | ✅ (macro ref, không cần body) |
| F003 | `詳細仕様書_F003` | macro `M001_メニューバーを表示` | label `lblMenuBarTrue` OnDblClick | ✅ |
| F004 | `詳細仕様書_F004` | `戻る_Click` | 2712–2725 | ✅ |
| F005 | `詳細仕様書_F005` | `PDF作成_Click` | 2727–2734 | ✅ (placeholder feature) |
| F006 | `詳細仕様書_F006` | `エクセル書き出し_Click` | 2736–2773 | ⚠️ thiếu mismatch path (F-01) |
| F007 | `詳細仕様書_F007` + `F007_SelQuery01` | `未入金_前期_Click` | 2697–2710 | ⚠️ tên query naming (F-03) |
| F008 | `詳細仕様書_F008` (なし) | (`OnClick="[イベント プロシージャ]"` declared, no Sub) | 2293 declared only | ✅ (なし phản ánh đúng) |
| — | (RecordSource_SelQuery01) | query `C000_MAINⅡ_未入金_改` (RecordSource form) | — | ✅ tồn tại tại `Queries/C000_MAINⅡ_未入金_改.sql.sql` |
| — | (RecordSource_SelQuery02) | query `C000_MAINⅡ ALL` (sub-query) | — | ✅ tồn tại tại `Queries/C000_MAINⅡ ALL.sql.sql` |
| — | (RecordSource_SelQuery03) | query `C500_期算出` (sub-query) | — | ✅ tồn tại tại `Queries/C500_期算出.sql.sql` |

---

## 4. Code không cần migrate (dead code đã xác minh) <a id="sec-deadcode"></a>

Hai sub trong source-behind nhưng không có control nào trong layout và không có tham chiếu trong các form khác (đã grep `アフター管理終了_Click` và `終了A_Click` trên toàn bộ `VBA_Export_All/`):

| Procedure | Source line | Kết luận |
|---|---|---|
| `Private Sub アフター管理終了_Click()` | 2639–2658 | Trong layout sheet không có button nào tên `アフター管理終了`. Logic: confirm + DoCmd.Quit. **Dead code** (button đã xóa nhưng sub-behind còn). |
| `Private Sub 終了A_Click()` | 2660–2695 | Tương tự, không có control `終了A`. Logic: confirm + Me.Refresh + DoCmd.Quit acSave. **Dead code**. |

→ Không tính là spec miss. Khuyến nghị team .NET không cần migrate (logic đã có ở F004 戻る + F_Login `閉じる_Click`).

---

## 5. Khuyến nghị <a id="sec-reco"></a>

1. **[Bắt buộc]** Verify F-01: confirm path trong `ShellExecute` của F006 step 2.4 có thực sự match path delete + export hay không. Nếu khác, fix bug ngay tại tài liệu thiết kế.
2. **[Bắt buộc]** F-03: thống nhất naming query `Q011` vs `Ｑ011` trước khi migrate. Đề xuất: chuẩn hóa toàn bộ tên query về half-width.
3. **[Nên]** F-02: quyết định fate của F005 PDF作成 (placeholder feature). Nếu giữ → cần spec mới chi tiết. Nếu bỏ → đánh dấu trong roadmap.
4. **[Nên]** F-09: bổ sung signature `[forms]![C000_MAINⅡ]![txt店所]` cho parameter 5.
5. **[Nên]** F-04: ghi rõ "3 lần maximize" trong F001 spec hoặc note "defensive coding for Access window race condition".
6. **[Nên]** F-10: tách path hard-coded ra config (vd `ExcelExportFolder`, `ExcelExportFile`).
7. **[Nên]** Sửa cột naming 論理名/物理名 trong sheet 画面編集 đúng convention.
8. **[Nên]** Note rằng RecordSource_SelQuery02 (`C000_MAINⅡ ALL`) có **CASE WHEN cho 20 明細区分** — khi migrate sang LINQ/EF cần generate code này (có thể qua SQL view hoặc raw SQL thay vì LINQ).
