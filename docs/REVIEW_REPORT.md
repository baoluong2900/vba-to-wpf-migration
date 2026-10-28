# Báo cáo review toàn bộ source — vba_brain

> Ngày review: **2026-10-28** · Branch: `review/full-source-cleanup` · Phạm vi: toàn bộ repo
> (`src/backend`, `src/frontend`, `src/wpf`, `infa/`, launcher, CI, tài liệu).
> Mọi lỗi ghi ở đây đều đã được **kiểm chứng trên code thật** (đọc đường gọi, tái hiện trong bộ
> nhớ hoặc bằng test) trước khi sửa. Ký hiệu mức độ: 🔴 critical · 🟠 high · 🟡 medium · 🟢 low.

---

## 1. Tóm tắt

- **Quy mô:** 545 file được track, ~65.000 dòng code (Python ~53k, TypeScript ~10k, C#/AXAML ~0,7k).
- **Phát hiện:** hơn 150 lỗi có bằng chứng, trong đó khoảng 40 lỗi mức 🔴/🟠: bảo mật (RCE,
  path traversal, lộ mật khẩu, gateway mở ra mạng) hoặc làm hỏng chức năng chính. Ví dụ: lưu SQL
  ở Layer 3 luôn lỗi, Layer 4 xuất DD không có sheet chi tiết, Layer 2 retry LLM vô hạn, Layer 5
  ghép sai handler khiến bấm Login chạy `taskkill`.
- **Đã sửa:** toàn bộ mức 🔴/🟠 và đa số 🟡/🟢. Phần còn lại là thay đổi kiến trúc lớn, được ghi
  ở mục 9 kèm lý do.
- **Phát triển thêm:** xác thực token cho gRPC, chống cross-site, bộ test (420 test backend +
  34 frontend, trước đó gần như bằng 0), CI 4 job, các cờ `--from/--only/--skip/--dry-run` cho
  pipeline, `--dry-run` cho migration PostgreSQL, collection `dependency_graph`, kiểm tra SQL
  tĩnh, đăng ký model từ `config.json`, và các mục khác ở mục 6.
- **Dọn dẹp:** gom code trùng lặp ở Layer 4 (8.031 → 3.022 dòng), xoá 43 file/route chết hoặc hỏng,
  bỏ 9 dependency không dùng, ~330 cảnh báo pyflakes → 0, gỡ 95 file sinh ra khỏi git. Tổng cộng
  code gọn hơn ~6.800 dòng dù có thêm ~450 test.

---

## 2. Cách review

1. **Công cụ tự động** trên toàn repo: `compileall`, `pyflakes`/`ruff`, `eslint`, `tsc --noEmit`,
   `next build`, `dotnet build`, `dotnet list package --vulnerable`, quét lịch sử git tìm secret.
2. **Review sâu song song 6 vùng:**
   - gateway + Layer 1 + Layer 3 + hạ tầng + .NET
   - Layer 2
   - Layer 4
   - Layer 5 (UI / Logic / pipeline)
   - Layer 5 (repo / service / report / mapping / graphview)
   - frontend

   Mỗi phát hiện bắt buộc kèm dòng code nguyên văn và kịch bản lỗi cụ thể.
3. **Review riêng Layer 3 từ đầu đến cuối** (backend → gRPC `Layer4Service` → API route
   `/api/v1/layer3/*` → trang `/layer3`), làm thêm theo yêu cầu.
4. **Kiểm chứng rồi mới sửa.** Mỗi bản sửa có test hồi quy khi phần logic test thuần được.
   Layer 4 còn có so sánh output trước/sau trên 9 trường hợp.
5. **Chạy lại toàn bộ quality gate** sau khi sửa (mục 3) và kiểm tra tĩnh mọi câu
   `from X import Y`. Lần kiểm tra này đã bắt được 3 re-export bị ruff gỡ nhầm; đã khôi phục.

---

## 3. Kết quả kiểm tra tự động — trước / sau

| Kiểm tra | Trước | Sau |
| --- | --- | --- |
| `python -m compileall` | OK | OK |
| `ruff` (E9 + pyflakes) | ~330 cảnh báo, trong đó 3 tên **chưa định nghĩa** (crash khi chạy) và 1 module bị dán trùng toàn bộ | **0** (ruff). Pyflakes chỉ còn ghi chú star-import cố ý của `bd_agent` và 13 re-export đã đánh dấu `noqa` |
| pytest | 0 test (chỉ có vài script in ra màn hình) | **420 test** (254 `tests/backend` + 166 `tests/layer5`), chạy dưới 2 giây, không cần Mongo/LLM/mạng |
| `yarn lint` / `tsc --noEmit` | OK / OK | OK / OK |
| Test frontend | không có | 34 test (`yarn test`) |
| `next build` | OK, 2 cảnh báo (Cache-Control, NFT trace) | OK, 1 cảnh báo NFT trace (có từ trước) |
| `dotnet build` | 0 lỗi, **10 cảnh báo** | 0 lỗi, **0 cảnh báo** |
| NuGet có lỗ hổng | `System.Security.Cryptography.Pkcs` 9.0.x (high + moderate) | không còn |
| Secret trong lịch sử git | chưa kiểm | sạch: không `config.json`/`.env` nào từng commit, không có key `sk-`/`gsk_`/`AKIA`/`ghp_` |

---

## 4. Lỗi nghiêm trọng đã sửa (Critical / High)

| # | Vùng | Lỗi | Hậu quả | Cách sửa |
| --- | --- | --- | --- | --- |
| 1 | Frontend | `run-agent` nhét `phase` / `test_agents` từ request vào lệnh shell | 🔴 **RCE**: bất kỳ ai gọi được API là chạy được lệnh trên máy | `execFile`/`spawn` với mảng tham số; allow-list `phase`; `isSafeName` cho mọi tên |
| 2 | Frontend | Không chặn cross-site; `GET /api/v1/layer1/extract` chạy cả pipeline | 🟠 Một thẻ `<img>` trên trang bất kỳ là kích hoạt gọi LLM cho mọi item và `DROP TABLE` PostgreSQL | `src/proxy.ts` chặn POST/PUT/PATCH/DELETE không cùng origin; extract chỉ nhận POST và không bao giờ chạy migration DB; `yarn dev` bind `127.0.0.1` |
| 3 | Gateway, L2, L4 | `screen_name` từ request nối thẳng vào đường dẫn file | 🟠 Ghi đè `*.json` tuỳ ý (ví dụ `config.json`, `package.json`); ghi `.xlsx`/`.docx` ra ngoài thư mục | `_bad_name` ở gateway, `utils/paths.safe_child_path` ở Layer 2, `_child`/`_confine` ở Layer 4 |
| 4 | Gateway | Bind `[::]:50051`, không xác thực | 🟠 Mọi máy trong LAN điều khiển được pipeline (kể cả tiêu tiền LLM) | Mặc định bind `localhost`; token Bearer tuỳ chọn (`GRPC_AUTH_TOKEN`), so sánh thời gian hằng |
| 5 | Layer 1 | `seed_db.py` in URI Mongo kèm mật khẩu, output này được stream ra trình duyệt | 🟠 Lộ mật khẩu DB trên console web | `redact_uri()` cho mọi chỗ log URI |
| 6 | Layer 3 | Handler `UpdateMigrationQuery` tạo object thiếu `target_query_json` | 🔴 **Nút Lưu ở `/layer3` luôn thất bại** | Truyền thẳng request proto; router chỉ ghi các field client thực sự gửi |
| 7 | Layer 3 | Route trả `{query}` nhưng trang đọc `d.result` | 🟠 Convert AI thành công ở server nhưng UI luôn báo "Conversion failed" và để trống editor; xem chi tiết query không bao giờ tải | Thống nhất `result` |
| 8 | Layer 3 | LLM trả rác vẫn lưu `converted`; convert lỗi thì ghi đè SQL đã review bằng SQL Access | 🟠 Mất công review của người dùng | Không có `target_sql` hợp lệ thì đánh dấu `error` và giữ nguyên SQL cũ |
| 9 | Layer 3 | `postgres_migrator` tìm `config.json` ở `src/` | 🟠 Luôn chạy bằng user `postgres` không mật khẩu, bỏ qua `POSTGRES_*` | Dùng `common.config` |
| 10 | Layer 2 | Vòng retry UI-formula: bộ đếm tăng trong hàm routing (LangGraph bỏ qua thay đổi đó) | 🔴 Một phản hồi lỗi kéo theo ~5.000 lần gọi LLM **tính phí** rồi mới crash | Bộ đếm chuyển vào node; `recursion_limit` tường minh; có fallback |
| 11 | Layer 2 | Report không bao giờ vào nhánh report; macro không bao giờ tới LLM | 🟠 BD/DD của mọi report và macro gần như rỗng | Đọc `form` hoặc `report`; `macro_raw = item.get("macro_raw") or code` |
| 12 | Layer 2 | `--stage` không có tác dụng với BD; fallback quota chỉ đi 1 bước | 🟠 Production vẫn chạy model dev; hết quota là dừng | `select_model(complexity, stage, model_id)`; đi hết chuỗi fallback, fail-fast với 403 |
| 13 | L1 → L2 | Không ai ghi `dependency_graph`; batch không seed `queries_v2` | 🟠 Mọi BD/DD thiếu ngữ cảnh phụ thuộc và query | `seed_db.py` dựng `dependency_graph`; `run_all.py` thêm bước `seed-queries`; seeder chép đủ field |
| 14 | Layer 3 | Dựng lại SQL chỉ hiểu SELECT | 🟠 Câu UPDATE thành `WHERE …`; Layer 3/5 xử lý SQL sai | Parser lưu SQL gốc; dựng lại đủ UPDATE/INSERT/DELETE/TRANSFORM |
| 15 | Layer 4 | Template bị dịch sang tiếng Anh rồi commit đè (commit `02417d0`), trong khi code tìm nhãn tiếng Nhật | 🔴 File DD **không có sheet chi tiết, không có SQL**; BD ghi event sai dòng; lộ dữ liệu mẫu của template | Khôi phục template gốc; mọi bộ định vị nhãn đều song ngữ |
| 16 | Layer 4 | `gen_dd` không truyền `detail_profile` | 🟠 DD chỉ giữ spec chi tiết đầu tiên (F_Login: 1/11) | Truyền profile theo loại |
| 17 | Layer 4 | `mock_change_history=True` mặc định | 🟠 Mọi tài liệu xuất ra kèm **10 dòng lịch sử sửa đổi bịa** | Mặc định tắt |
| 18 | Layer 4 | Không có output Layer 2 thì dựng từ dữ liệu thô Layer 1 rồi báo thành công | 🟠 Xuất ra tài liệu đầy dữ liệu mẫu của template | Trả lỗi "not generated yet" |
| 19 | .NET | `System.Security.Cryptography.Pkcs` 9.0.13 (bắc cầu qua SqlClient) | 🟠 Lỗ hổng GHSA-846f-f764-76mx (high) | Ghim 10.0.14 |
| 20 | Layer 5 | `orchestrator.py` chứa 2 bản module dán nối nhau; gọi `.exists()` trên `None` | 🟠 Form không có service contract làm hỏng cả lượt chạy | Giữ một bản (đúng hành vi đang chạy), sửa lỗi `None` |
| 21 | Layer 5 | UI đánh số F-ID theo `ui_event_map.json`, còn Service/Logic theo BD | 🟠 Handler nối sai logic: **bấm Login chạy thân `taskkill`**, KeyDown gọi kiểm tra phiên bản mỗi lần gõ phím | Resolver dùng chung `core/fid_resolver.py` |
| 22 | Layer 5 | `merge_csharp_code` khi chạy lại một form | 🔴 **Xoá mất khai báo class/interface** (4 file output đang track đã hỏng) | Chỉ merge bên trong thân type; hỗ trợ tên tiếng Nhật |
| 23 | Layer 5 | Vòng build-fix lấy file theo tên trùng đầu tiên | 🟠 Ghi đè ViewModel đã được Logic vá bằng skeleton "đã sửa" bởi LLM, mất toàn bộ logic | Khử trùng theo đường dẫn thật; gửi file trên đĩa cho LLM |
| 24 | Layer 5 | Code sinh ra không biên dịch được (xem cột hậu quả) | 🟠 Lỗi CS0234/CS0246/CS0103 khi build. Nguyên nhân: using DTO cho service không có method; tên sự kiện VBA thô; thân sự kiện hệ thống viết cho WPF; entity thiếu `using vba_brain.Domain.Common` | Sinh có điều kiện; map sang sự kiện Avalonia hoặc TODO; `sys_bodies.py` sinh code Avalonia |
| 25 | Layer 5 | Service "auth" select cả bảng `T_ID_Pass` | 🟠 **Mật khẩu plaintext của mọi user** bị trả lên ViewModel | `VerifyCredentialsAsync` có tham số; không bao giờ select cột mật khẩu |
| 26 | Layer 5 | Bỏ qua `raw_sql`; Dapper không đọc `[Column]` | 🟠 Repository trả rỗng hoặc thuộc tính luôn null mà vẫn báo thành công | SQL lấy theo thứ tự DD → `queries_v2.target_sql` → `raw_sql`; alias cột; `NotImplementedException` + danh sách stub |
| 27 | Layer 5 | Service gọi repository theo tham số của DD | 🟠 CS1501/CS7036, hoặc tham số bị tráo mà không báo lỗi | Gọi theo đúng input contract của repository |
| 28 | Layer 5 | `tool_report` chèn code WinForms/ReportViewer riêng của R005 | 🟠 Build Avalonia hỏng với mọi report | Bỏ hẳn; sinh TODO theo service contract |
| 29 | Layer 5 | CLI Logic luôn exit 0; `fill_json` gọi `sys.exit(1)` trong code thư viện | 🟠 Console báo thành công khi đã thất bại; một lỗi làm dừng cả batch | Trả trạng thái đúng; raise thay vì exit |
| 30 | Layer 5 | `agent_ui.py` dùng `form_name`/`form_config` chưa định nghĩa | 🟠 NameError bị nuốt, nên phần tra cứu event map không bao giờ chạy | Truyền tham số; xoá hàm không ai gọi |

---

## 5. Chi tiết theo từng vùng

### 5.1 Gateway gRPC (`src/backend/api_gateway/`)
- Đã sửa:
  - Bind theo `GRPC_HOST` (mặc định `localhost`).
  - Interceptor token tuỳ chọn (`auth.py`).
  - `_bad_name` cho mọi tên dùng làm đường dẫn.
  - `ListForms` luôn lỗi (đưa dict vào `repeated string`).
  - `GetBdStatus` bỏ sót DD của report.
  - `GenBd/GenDd/GenAll/SeedQueries/GetStats` báo thành công cả khi thất bại.
  - `RunBdFlowFull` coi macro là form.
- `GetModelsHealth`:
  - Trước đây hết timeout là vứt bỏ mọi kết quả đã có.
  - Dùng client có fallback, nên model hết quota vẫn báo "ok".
  - Gọi LLM tính phí cho mọi model ở mỗi lần tải trang.
  - Nay timeout từng model, dùng client không fallback, cache 5 phút.

### 5.2 Layer 1
- Parser tìm `src/VBA/…`, nên chỉ chạy được trên filesystem không phân biệt hoa thường (macOS) và hỏng trên Linux/CI.
- Export không có macro/report làm dừng cả pipeline. Nay thư mục rỗng thì exit 0, seeder bỏ qua thư mục thiếu.
- `run_all.py`: thêm step key và các cờ `--list/--from/--only/--skip/--dry-run/--keep-going`.
- Docstring `table_parser.py` mô tả ngược với code; đã sửa cho khớp.

### 5.3 Layer 2
Sửa 21 mục:
- Vòng retry.
- Report và macro.
- Định tuyến model theo stage/độ phức tạp.
- Chuỗi fallback.
- Batch BD3 đánh khoá theo `module_id` thay vì theo vị trí, cache có hash.
- Cờ `required` bị đảo (chuỗi `"False"` là truthy).
- `functions` / `procedures`.
- BD2 ghi nhầm thư mục.
- DD đọc tên file BD3 không tồn tại.
- Cache DD3 cho module không bao giờ trúng.
- Lỗi tóm tắt bị ghi vào tài liệu như là mô tả.
- Rò rỉ Mongo client; URI chưa che khi log.
- CLI thêm `--type macro` / `--all-macros` và chỉ push item vừa chạy.

Đã xoá code chết: `fill_dd_macro_module.py`, 2 runner FastAPI cũ, `_MinimalPipeline`, các alias `call_with_fallback`, khối code trùng lặp.

### 5.4 Layer 3 (review riêng theo yêu cầu)
- **Backend:**
  - `router.py` viết lại: client Mongo dùng chung, ghi từng phần, không đánh dấu `converted` khi LLM trả rác, không ghi đè SQL đã review khi lỗi.
  - `query_utils.py` mới:
    - dựng lại SQL đủ loại câu lệnh;
    - `query_type` / `target_table`;
    - biến bind bỏ qua `::cast`, giờ `12:30` và chuỗi literal.
  - `seed_queries_v2.py` đồng bộ đủ field mà Layer 2 đọc, refresh nguồn nhưng không động tới field review.
- **`table_converter.py`:** bảng ánh xạ thay cho chuỗi `if "text" in …`:
  - `Long Text` → `TEXT` (trước là `VARCHAR(255)`), `LongBinary` → `BYTEA` (trước là `BIGINT`).
  - `AutoNumber` → identity, `Decimal` → `NUMERIC`, `GUID` → `UUID`.
  - Chỉ quote tên khi bắt buộc, để giữ quy tắc gập chữ thường của PostgreSQL mà code Dapper sinh ra đang dựa vào.
  - Hỗ trợ `PRIMARY KEY`.
- **`postgres_migrator.py`:** sửa đường dẫn config; thêm `--dry-run/--table/--output`; báo rõ khi thiếu `psql`; exit 1 khi có bảng lỗi.
- **Frontend:**
  - Các route trả về đúng cấu trúc trang cần.
  - Route `stats` đọc `stats_json`.
  - Bỏ model gán cứng `deepseek-v4-pro` (không tồn tại).
  - "Test query" giả lập trước đây trả mã lỗi **Oracle** `ORA-xxxxx` và **dữ liệu mẫu bịa** ("Sample Data A"), lại báo "executed successfully". Nay là bộ kiểm tra tĩnh trung thực (`staticSqlCheck.ts`): mã SQLSTATE của PostgreSQL, ghi rõ là không thực thi.
- Có 4 file test Layer 3 (router chạy trên Mongo giả lập, LLM giả lập).

### 5.5 Layer 4
- Khôi phục template tiếng Nhật; bộ định vị song ngữ.
- `detail_profile`; `なし` / `raw_sql`.
- Toạ độ ghi giá trị header; `AW2`; dòng bắt đầu bảng report; record source.
- Không dựng từ dữ liệu Layer 1.
- `.docx` đọc đúng key của Layer 2.
- Translator chỉ dịch nhãn template, không đụng dữ liệu và công thức; tham chiếu công thức được viết lại khi đổi tên sheet.
- Tắt lịch sử giả; xoá sheet `QA` nội bộ; giới hạn đường dẫn.
- Gom code: `dd_common.py` (4 script DD: 8.031 → 3.022 dòng). So sánh trước/sau trên 9 trường hợp cho thấy chỉ có khác biệt mong muốn.
- Xoá `fix_templates.py`: script này dịch template **tại chỗ ngay khi bị import**, chính là nguồn gốc lỗi #15.

### 5.6 Layer 5
**UI / Logic / pipeline:**
- **F-ID và orchestrator:**
  - Một resolver F-ID dùng chung; registry ghi nguyên tử, id `_auto` ổn định.
  - Orchestrator còn một class, thứ tự repo → service → refresh input → UI → logic → graphview (không chặn) → ghi → build.
  - Form chỉ "success" khi các agent và build đều thành công.
- **Ghi file và build:**
  - `file_writer` chỉ ghi `.cs/.axaml/.xaml` và giới hạn trong thư mục đích.
  - `build_verify` khử trùng theo đường dẫn.
- **Code sinh ra:**
  - Thêm DI và using chỉ khi có method và namespace thật sự tồn tại.
  - Sự kiện form không có tương đương Avalonia → TODO.
  - Thân sự kiện hệ thống viết bằng Avalonia (`sys_bodies.py`).
  - PasswordBox → `TextBox PasswordChar` có `Text="{Binding TxtPass}"`; AfterUpdate/DoubleClick… được đăng ký ở code-behind (Avalonia không có `Interaction.Triggers`).
  - Method ViewModel luôn tên `{FID}Async`; nhận diện macro dạng `macro.X`.
- **CLI và vận hành:**
  - `--fix` đọc đúng đường dẫn; prompt SERVICE không còn gán cứng của F_Login.
  - Backup giữ cấu trúc thư mục; token tracker ghi nguyên tử và xuất thêm `.xlsx`.
  - Tên form không an toàn bị từ chối; Layer 5 dùng chung registry model với Layer 2/3.
- **Template sinh code** (`RelayCommand`, code-behind, `CloseRequested`) đã được sửa giống các file đã sửa tay trong `src/wpf`, để lượt deploy sau không quay lại lỗi cũ.

**Repo / service / report / mapping / graphview:**
- Sửa 20 mục ở bảng mục 4 (#22, #25–#28).
- **Repo:** contract của form được tổng hợp từ JSON theo từng bảng; tách `AS` bằng regex; chặn query tự tham chiếu; tra bảng theo khớp chính xác/NFKC; thêm hậu tố khi trùng tên; ánh xạ kiểu Access → C# đúng (Long → `int`, Currency → `decimal`, Yes/No → `bool`, …).
- **Service:** nhận diện trigger cả tiếng Nhật lẫn tiếng Anh.
- **Graphview:** chạy được ở script mode.
- **Mapping:** tên class macro không còn trùng nhau.
- **Report:** tên item RDLC hợp lệ; một hàm `access_color_to_hex` với bảng màu hệ thống đúng.

**Kiểm chứng:**
- 166 test Layer 5 pass; cả 7 CLI agent khởi động được ở script mode.
- ViewModel + code-behind sinh ra cho F_Login đã được **biên dịch thử** trong bản sao tạm của solution cùng DTO/interface do Agent Service sinh: **phần C# không còn lỗi**.
- Độ khớp AXAML ↔ ViewModel cần một lượt Layer 5 thật (có LLM) để kiểm (mục 9).

### 5.7 Frontend
- **Bảo mật:** #1, #2. Tên tiếng Nhật giờ dùng được: regex cũ chặn 127/135 form thật nhưng lại cho `..` lọt qua.
- **`python` không có trên macOS:** đổi sang `PYTHON_BIN` → `python3` → `python`.
- **Tải file tên tiếng Nhật làm hỏng header `Content-Disposition`:** dùng RFC 5987.
- **Đường dẫn Layer 5 sai** (`src/backend/layer5` không tồn tại), khiến file browser, báo cáo token và bản đồ tên Access→.NET đều rỗng.
- **Pipeline Layer 5:** không chờ Agent Logic; nút Stop không dừng tiến trình.
- **Race condition:** kết quả của màn hình cũ gắn nhầm sang màn hình mới.
- **SSE:** làm rơi sự kiện bị cắt giữa 2 chunk.
- **Kết nối Mongo:** client hỏng vĩnh viễn sau lần kết nối đầu thất bại.
- **Header Cache-Control:** ép `no-store` lên asset tĩnh có hash.
- **Xoá 9 route/file chết hoặc hỏng.**
- **Kiến trúc mới:** đường dẫn, Python, kiểm tra tên, origin, SSE, auth gRPC gom về `src/lib/*`.

### 5.8 Ứng dụng .NET (`src/wpf`)
- Hết lỗ hổng NuGet; 10 cảnh báo build → 0.
- `RelayCommand`: exception trong command `async void` trước đây làm sập app.
- `FLoginView`: thêm constructor public mà XAML loader cần.
- `F011` (Close) phát `CloseRequested`.
- `App.axaml.cs`: dựng DI thật; khi chưa nối màn hình sinh ra nào thì hiện cửa sổ hướng dẫn thay vì chạy như tiến trình vô hình không bao giờ thoát.
- Xoá 3 file `Class1.cs` thừa và thư mục `vba_brain.UI.WPF` rỗng.

### 5.9 Hạ tầng, launcher, dependency, CI
- **`infa/mongo-init/01_init_user.js`:** tạo thêm tài khoản root với mật khẩu cứng trong git, và xung đột với user root mặc định ngay lần khởi tạo đầu. Nay không chứa thông tin đăng nhập.
- **`start.py`:**
  - `kill_port` chỉ dừng tiến trình LISTEN; trước đây `lsof -i:PORT` trả cả client, nên **trình duyệt bị `kill -9`**.
  - Không ghi đè biến môi trường của bạn; không ghi lại `api_gateway/.env`.
  - Che mật khẩu khi log; truyền `GRPC_*` sang console.
  - Dừng cả cây tiến trình khi Ctrl+C.
- **`clean_generated_files.py`:** trước dùng đường dẫn tương đối theo thư mục đang đứng. Nay có `--dry-run`, khử trùng lặp, và trước đây không xoá được file trong thư mục con.
- **`requirements.txt`:** mức sàn thấp hơn mức mà stub gRPC đòi (`grpcio>=1.71.2`), thiếu `python-docx` và `protobuf`, thừa 9 gói không ai import. Nay có trần major cho mọi gói.
- **CI 4 job:**
  - backend: ruff, 2 phiên pytest, kiểm tra stub gRPC khớp `.proto`;
  - frontend: lint, tsc, test, build;
  - .NET: build và chặn NuGet có lỗ hổng;
  - hygiene: thêm các đường dẫn sinh ra.

---

## 6. Phát triển thêm (tính năng mới)

| Tính năng | Ở đâu | Cách dùng |
| --- | --- | --- |
| Xác thực token cho gRPC + bind localhost | `api_gateway/auth.py`, `grpc_server.serve` | `GRPC_AUTH_TOKEN`, `GRPC_HOST`, `GRPC_PORT` (hoặc `config.json → grpc`) |
| Chặn request cross-site | `src/frontend/src/proxy.ts` | Tự động |
| Điều khiển pipeline theo bước | `layer1/run_all.py` | `--list`, `--from seed`, `--only tables,queries`, `--skip layer3`, `--dry-run`, `--keep-going` |
| Xem trước DDL trước khi migrate | `layer3/.../postgres_migrator.py` | `--dry-run --output schema.sql`, `--table NAME` |
| Collection `dependency_graph` | `layer1/seed_db.py` | Tự động khi seed |
| Đồng bộ `queries_v2` đầy đủ, giữ công review | `layer3/.../seed_queries_v2.py` | Bước `seed-queries` |
| Kiểm tra SQL tĩnh (PostgreSQL SQLSTATE) | `api/v1/layer3/staticSqlCheck.ts` | Nút Test ở `/layer3` |
| Model từ `config.json` chọn được thật | `common/config.py` | Khai báo trong `llm_providers.<p>.models` |
| Cache health-check model | `grpc_server.GetModelsHealth` | 5 phút |
| Bộ test | `tests/backend`, `tests/layer5`, `src/frontend/tests` | `pytest && pytest tests/layer5`, `yarn test` |
| CI đầy đủ | `.github/workflows/ci.yml` | Tự động trên PR |
| API token-stats Layer 5 | `GET /api/v1/layer5/token-stats` | Trang `/layer5` |
| F-ID dùng chung cho UI / Logic / Service | `layer5/core/fid_resolver.py` | Tự động |
| Thân sự kiện hệ thống không cần LLM (quit/close/kill process/phím) | `layer5/agents/logic/sys_bodies.py` | Tự động |
| Kiểm tra đăng nhập an toàn (`VerifyCredentialsAsync`) | `agents/service/tool_service_gen.py` | Tự động cho sự kiện kiểu login |
| Chọn form khi sinh code | `layer5/run_codegen_all.py --form NAME` | Lặp được; exit 1 nếu có form lỗi |
| Báo cáo token Layer 5 dạng Excel | `layer5/llm/token_tracker.py` | `logs/token_report.xlsx` |

---

## 7. Dọn dẹp

- **Layer 4:** 4 script DD gom về `dd_common.py` (−5.000 dòng); xoá 4 script tiện ích hỏng hoặc nguy hiểm.
- **Layer 2:** xoá 3 file chết và nhiều hàm/khối trùng; ~80 import/biến thừa.
- **Frontend:** xoá 6 route legacy `api/layer3/*`, `api/v1/layer3/stats`, `api/bd-agent`, `graph-wpf/{mapping,validate}`, `validator.ts`, `seed_db.js`, `jsconfig.json`, `next.config.mjs` (bị `next.config.js` che), node Agent Test.
- **Hạ tầng / repo:**
  - xoá `infa/scripts/{translate_templates,update_prompts}.py` (trỏ vào thư mục không tồn tại);
  - xoá `src/vba/vba_source/run_tests.py` (đã thành pytest);
  - xoá `Class1.cs` ×3.
- **Gỡ khỏi git index** (file vẫn giữ trên máy, nay đã gitignore): `layer2/agents/output/`, `layer3/scratch/*` (có script chứa tên dữ liệu khách hàng), `layer5/logs/token_report.json`, `src/frontend/reports/`.
- **Dependency:** bỏ FastAPI, uvicorn, google-generativeai, langchain-core/-groq/-openai, jsonschema, psycopg2-binary, requests; `grpcio-tools` chuyển sang `requirements-dev.txt`.
- **Layer 5:**
  - Xoá 13 module/template/prompt chết: `tool_method_merger`, `sync_vm_stubs`, `gen_code_behind`, `gen_vm_methods`, `patch_vm_from_output`, `core/utils`, 3 template Jinja, 4 prompt/template không dùng, `run_codegen_test.py`. Kèm nhiều hàm không ai gọi.
  - Gỡ khỏi git các artifact sinh lại mỗi lượt: contract cũ, 4 snapshot hỏng, review/mapping theo lượt, `list*Jp.json` không ai đọc. Giữ lại bản đồ tên, config, prompt.
- **Tổng cộng:**
  - 365 file thay đổi; 43 file xoá hẳn; 95 file gỡ khỏi git (vẫn giữ trên máy).
  - Code **+22.151 / −28.914 dòng**, đã gồm ~450 test mới.

---

## 8. Thay đổi hành vi cần biết

1. **Gateway chỉ nghe `localhost`.** Muốn mở ra mạng, đặt `GRPC_HOST=0.0.0.0` **và**
   `GRPC_AUTH_TOKEN`, rồi để sau một proxy TLS.
2. **Console web không còn tự chạy migration PostgreSQL** (`run_all.py --skip layer3`). Chạy tay:
   `postgres_migrator.py --dry-run` trước, rồi bỏ `--dry-run`. Lưu ý: trước đây bước này thực tế
   luôn thất bại do sai đường dẫn config; giờ nó chạy thật và sẽ `DROP` + `CREATE` bảng.
3. **Template Layer 4 là bản tiếng Nhật gốc** (đã khôi phục). Không dùng openpyxl để lưu đè template.
4. **Layer 4 không còn dịch dữ liệu.** Văn bản tiếng Nhật do Layer 2 sinh ra giữ nguyên trong tài
   liệu tiếng Anh; trước đây bị dịch chèn thành chữ lai (ví dụ "画面の初期表示のProcess").
5. **Không còn lịch sử sửa đổi bịa** trong Excel (CLI có `--mock-change-history` nếu cần demo).
6. **Nút Test ở `/layer3` là kiểm tra tĩnh** và nói rõ là không thực thi SQL.
7. **`yarn dev` chỉ bind `127.0.0.1`.**
8. **Request POST/PUT/PATCH/DELETE cross-site vào `/api/**` bị trả 403.** Request không có header
   `Origin`/`Sec-Fetch-Site` (curl, script) vẫn được cho qua.
9. **Lần chạy BD3 kế tiếp sẽ tạo lại cache một lần** (cache giờ có hash nội dung). Cache DD3 cho
   module bắt đầu trúng thật.
10. **Định tuyến model:** stage `production` giờ áp dụng thật cho BD; model không có trong
    registry sẽ log cảnh báo khi bị thay thế.
11. **Bảng PostgreSQL:** tên bảng/cột có dấu cách hoặc trùng từ khoá giờ được quote (trước đó DDL
    lỗi cú pháp). Tên thường giữ nguyên, không quote.
12. **Lượt chạy Layer 5 kế tiếp sẽ đánh số lại F-ID theo BD** (F_Login: Form_Load F001,
    Form_KeyDown F002, cmdLogin F004, cmdClose F005, …) và ghi lại `ui_event_map.json`.
    View/ViewModel đang deploy (đã sửa tay để build sạch) sẽ bị thay.
    - Deploy lại cả output Service: ViewModel mới gọi `F009Async` mà `IFLoginService` đang
      deploy chưa có.
    - Trước khi deploy, chạy `python clean_generated_files.py --dry-run`, rồi bỏ `--dry-run`,
      để DTO cũ (`F00xRequest.cs`) không trùng với `FLoginServiceRequests.cs`.
13. **Tên sinh ra sẽ đổi:**
    - `AuthRepository` → `TIDPassRepository` (không còn khớp chuỗi con `T_ID_Pass` ~ `T101_ID_PASS`).
    - `F003Response.AuthEntity` → `Authenticated`.
    - `OnF000Async` → `GetInitialDataAsync` (giờ đã nhận diện trigger tiếng Anh).
14. **Mã thoát CLI:** repo/report/logic trả exit 1 khi lỗi, tên không an toàn trả exit 2. Console
    giờ hiển thị đúng là thất bại, thay vì "success".

---

## 9. Việc còn lại / đề xuất

| Ưu tiên | Việc | Lý do chưa làm |
| --- | --- | --- |
| 🟠 | TLS cho gateway (`add_secure_port`) | Cần quyết định cách cấp cert; hiện bind localhost + token |
| 🟠 | Tracker chi phí theo request (contextvars) | Gateway 20 thread dùng chung tracker toàn cục, nên số liệu chi phí có thể lẫn giữa các request chạy đồng thời. Sửa cần truyền context qua ThreadPoolExecutor |
| 🟡 | Health service chuẩn `grpc.health.v1` + `start.py` chờ backend sẵn sàng | Thêm dependency `grpcio-health-checking` |
| 🟡 | Ô chọn `source_path` ở `/layer1` chưa có tác dụng | Nối vào parser sẽ cho trình duyệt đọc thư mục tuỳ ý; cần quyết định chính sách (allow-list thư mục) |
| 🟡 | Migration index / FK / rollback cho Layer 3 | Dữ liệu `AllColumns.csv` hiện không có thông tin PK/FK/index |
| 🟡 | Test query thật trên PostgreSQL (`EXPLAIN` trong transaction read-only, một câu lệnh, role giới hạn) | Cần thiết kế an toàn: nhiều câu lệnh trong một chuỗi có thể thoát khỏi transaction |
| 🟡 | `query_mapper.py` tìm `layer2/schema/table_config.json` (chưa bao giờ tồn tại) | Trỏ sang file của Layer 5 sẽ thay đổi output DD, cần xác nhận |
| 🟡 | Ngữ nghĩa cột CSV `LogicalName` / `PhysicalName` | DDL dùng `logical_name` (khớp query trong fixture), nhưng Layer 2 coi `physical_name` là cột DB. Cần đối chiếu với export thật |
| 🟡 | Dịch văn bản tiếng Nhật cố định ngay từ Layer 2 (tiêu đề bước, …) thay vì ở Layer 4 | Xem mục 8.4 |
| 🟡 | Cột "attribute_digits" của BD sheet 3 chỉ có độ dài | Code từng tính sẵn chuỗi "kiểu(độ dài)" nhưng không dùng; cần xác nhận định dạng mong muốn |
| 🟢 | Đổi tên `Layer3Service`/`Layer4Service` cho khớp số layer | Thay đổi phá vỡ tương thích (proto + frontend) |
| 🟢 | Tách `agent_ui.py`, `layer3/page.tsx`, `layer5/page.tsx` | Refactor lớn, nên làm sau khi có test giao diện |
| 🟢 | Lockfile Python | Phụ thuộc phiên bản Python đích |
| 🟠 | Chạy một lượt Layer 5 thật (có LLM), rồi `dotnet build`, để kiểm độ khớp AXAML ↔ ViewModel ↔ Service | Đợt review không gọi LLM; đã kiểm C# sinh ra biên dịch được với DTO/interface sinh ra |
| 🟡 | Sinh lại `graphview/outputs/{macros,modules}/list*JpToEn.json` bằng `agent_mapping ALL` | Bản đang track dùng key cũ (code đã đọc được cả hai) |
| 🟡 | Quyết định có untrack `agents/ui/outputs` và `agents/logic/{inputs,outputs}` hay không | Sinh lại mỗi lượt, nhưng console đang đọc trực tiếp |
| 🟢 | `deploy_to_source.py` chỉ copy `*.cs`, không copy `.axaml` | Cần quyết định luồng deploy view |
| 🟢 | Prompt `agents/logic/prompts/agent_vm_methods.md` không còn được dùng | Giữ lại để tham khảo |

---

## 10. Cách tự kiểm chứng

```bash
# Backend
pip install -r src/backend/requirements.txt -r src/backend/requirements-dev.txt
ruff check src/backend tests start.py start_wpf.py clean_generated_files.py infa/scripts
pytest && pytest tests/layer5

# Frontend
cd src/frontend && yarn install --frozen-lockfile
yarn lint && npx tsc --noEmit -p tsconfig.json && yarn test && yarn build

# Ứng dụng đích (.NET 10)
dotnet build src/wpf/vba_brain.slnx
dotnet list src/wpf/vba_brain.slnx package --vulnerable --include-transitive

# Layer 3 — xem trước DDL, không đụng vào PostgreSQL
python src/backend/workflow/layer3/sql_migration/postgres_migrator.py --dry-run --output schema.sql

# Pipeline — xem kế hoạch, không chạy gì
python src/backend/workflow/layer1/run_all.py --dry-run
```
