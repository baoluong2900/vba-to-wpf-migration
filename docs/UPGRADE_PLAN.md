# vba_brain — Kế hoạch Nâng cấp Toàn diện

> Tài liệu task nâng cấp pipeline VBA/Access modernization.
> Mỗi mục có `[ ]` để track. Ưu tiên: 🔴 Cao · 🟡 Trung bình · 🟢 Thấp.
> Plan được lập dựa trên **khảo sát code thực tế** (không chỉ README).

---

## 0. Hiện trạng & Khoảng cách (Gap Analysis)

Đối chiếu code thật với README, phát hiện các điểm sau:

| # | Vấn đề | Bằng chứng | Mức độ |
|---|--------|-----------|--------|
| G1 | ~~README mô tả Oracle XE + Qdrant~~ — ĐÃ XÓA Oracle/Qdrant khỏi README + code; chỉ còn **MongoDB 7 + PostgreSQL 16 + Mongo-Express** đúng theo `infa/docker-compose.yml` | `docker-compose.yml` | ✅ |
| G2 | Tên layer gRPC **ngược** với README: `Layer3Service`=Excel, `Layer4Service`=SQL Migration | `grpc_server.py` | 🔴 |
| G3 | Frontend thực tế **Next.js 16.2.4 / React 19 / Tailwind 4**, README ghi Next 15 / Yarn | `frontend/package.json` | 🟡 |
| G4 | ~~Tồn tại **2 UI song song**~~ — ĐÃ CHỐT **Avalonia** làm UI chính; Layer 5 codegen + deploy đã trỏ về `vba_brain.UI.Avalonia`. `vba_brain.UI.WPF` là folder trống (không có `.csproj`, không nằm trong `vba_brain.slnx`) → nên xóa | `src/wpf/` | ✅ |
| G5 | gRPC dùng `add_insecure_port` — **không auth/TLS** | `grpc_server.py:595` | 🔴 |
| G6 | docker-compose bind `0.0.0.0` cho Mongo/Postgres/Mongo-Express → phơi network | `docker-compose.yml` | 🔴 |
| G7 | **Gần như không có test**; không CI/CD; dependency không pin (`>=`) | toàn repo | 🔴 |
| G8 | File khổng lồ khó bảo trì (`agent_ui.py` 123KB, `fill_dd_excel_report.py` 79KB, FE `layer3/page.tsx` 73KB) | layer4/5, frontend | 🟡 |
| G9 | Secrets/`.env`/`config.json` nằm trong thư mục làm việc (đã gitignore nhưng cần xác nhận chưa lọt history) | `.gitignore` | 🔴 |

---

## Phase 1 — Ổn định nền tảng & Bảo mật (🔴 ưu tiên cao nhất)

Mục tiêu: hệ thống an toàn, chạy lại được tin cậy trước khi thêm tính năng.

### 1.1 Bảo mật gRPC Gateway
- [ ] Thêm **token/API-key interceptor** cho gRPC server (chặn truy cập ẩn danh tới port 50051).
- [ ] Thêm tùy chọn **TLS** (`add_secure_port` + cert) cho môi trường không-localhost; mặc định localhost vẫn cho phép insecure.
- [ ] Chuẩn hóa **error handling**: map exception → `grpc.StatusCode` thay vì để lỗi rò rỉ stack trace.

### 1.2 Khóa bề mặt hạ tầng
- [ ] Đổi binding docker-compose từ `0.0.0.0:PORT` → `127.0.0.1:PORT` cho Mongo/Postgres/Mongo-Express (chỉ mở ra ngoài khi thực sự cần).
- [ ] Xác nhận **MongoDB bật auth** thực tế (hiện `mongod --bind_ip_all` + root user qua env) và app dùng đúng connection string có `authSource`.
- [ ] Tài liệu hóa: production KHÔNG dùng Mongo-Express.

### 1.3 Vệ sinh secrets
- [ ] Quét git history tìm key đã lọt: `git log --all -S "sk-"` và `git log --all -p -- config.json`.
- [ ] Nếu có lọt → rotate key + dùng `git-filter-repo` (đã có sẵn trong `.git/filter-repo/`).
- [ ] Bổ sung `infa/.env.example` đầy đủ biến (`MONGO_ROOT_USER/PASSWORD`, `POSTGRES_*`, `MONGO_EXPRESS_*`).

### 1.4 Pin & khóa dependency
- [ ] Pin chính xác version trong `src/backend/requirements.txt` (thay `>=` bằng `==` hoặc `~=`).
- [ ] Thêm `requirements.lock` (pip-tools/`pip freeze`) để build tái lập.
- [ ] Frontend: commit `yarn.lock` (đã có) + ghi rõ Node version trong `.nvmrc`.

---

## Phase 2 — Chất lượng & Độ tin cậy (🔴/🟡)

Mục tiêu: thay đổi không sợ vỡ, có lưới an toàn.

### 2.1 Test framework (Python)
- [ ] Thêm `pytest.ini`/`pyproject.toml` cấu hình test root, marker, coverage.
- [ ] Viết **unit test cho Layer 1 parser** (`frm_parser`, `query_parser`, `macro_parser`, `modules_parser`, `table_parser`) dùng các JSON mẫu trong `data/`.
- [ ] Test cho `aggregator.py` (cross-reference: DoCmd, DLookup, CallSub).
- [ ] Test cho Layer 3 `table_converter.py` (Access type → PostgreSQL DDL) — pure function, dễ test.
- [ ] Mock LLM cho Layer 2/5 (test logic ráp prompt + parse output, không gọi API thật).
- [ ] Gom các script `test_*.py` rời rạc trong `layer4/scripts` và `layer3/scratch` về thư mục `tests/` thống nhất.

### 2.2 Test frontend
- [ ] Thêm test cho `graphBuilder.ts` và `wpfGraphTransform.ts` (logic thuần, không UI).
- [ ] Smoke test build: `next build` phải pass.

### 2.3 CI/CD
- [ ] Thêm `.github/workflows/ci.yml`: lint + pytest (backend) + `next build`/eslint (frontend) chạy trên PR.
- [ ] Cache pip & yarn để CI nhanh.
- [ ] (Tùy chọn) Job `dotnet build vba_brain.slnx` (Avalonia) nếu chạm Layer 5 output.

### 2.4 Logging & quan sát
- [ ] Chuẩn hóa **structured logging** (JSON) thay cho `print`/`*.log` rải rác.
- [ ] Thêm endpoint/health-check cho gRPC (`grpc_health_v1`) để FE và `start.py` kiểm tra trạng thái BE.
- [ ] Hợp nhất token/cost report (Layer 2 `cost_tracker` + Layer 5 `token_tracker`) về một định dạng chung.

---

## Phase 3 — Đồng bộ tài liệu & Dọn kiến trúc (🟡)

Mục tiêu: README phản ánh đúng code; giảm nợ kỹ thuật.

### 3.1 Sửa README cho khớp thực tế
- [x] Cập nhật Infra table: đã bỏ Oracle XE/Qdrant, ghi đúng **PostgreSQL 16-alpine**.
- [ ] Sửa **bảng gRPC**: làm rõ `Layer3Service`=Excel, `Layer4Service`=SQL (hoặc đổi tên service cho khớp ý nghĩa — xem 3.3).
- [ ] Cập nhật Tech Stack frontend: **Next 16 / React 19 / Tailwind 4**.
- [x] Làm rõ chiến lược UI: **Avalonia** là target chính (G4 — đã chốt).

### 3.2 Quyết định 1 UI target — ✅ ĐÃ CHỐT: Avalonia
- [x] Chốt **Avalonia** (đa nền tảng, .NET 10) làm UI chính.
- [x] Layer 5 codegen sinh AXAML/Avalonia (namespace `vba_brain.UI.Avalonia`); `deploy_to_source.py`, `file_writer.py`, frontend `run-agent`/`run-logic` đã trỏ về `src/wpf/vba_brain.UI.Avalonia`.
- [x] `start_wpf.py` build/run `vba_brain.UI.Avalonia` (qua `vba_brain.slnx`).
- [ ] Xóa folder trống `vba_brain.UI.WPF` (không còn dùng).

### 3.3 Đổi tên service gRPC cho nhất quán (nếu chọn)
- [ ] Cân nhắc đổi `Layer3Service`→`ExcelService`, `Layer4Service`→`SqlMigrationService` trong `.proto`, regenerate stub, cập nhật FE. (Breaking — làm có chủ đích, kèm test.)

### 3.4 Refactor file khổng lồ
- [ ] Tách `agent_ui.py` (123KB) theo trách nhiệm: skeleton / control_mapper / xaml_render / vm_gen.
- [ ] Tách `fill_dd_excel_report.py` (79KB) & các `fill_*` trùng lặp → module helper chung (nhiều file ~65-79KB nghi ngờ copy-paste).
- [ ] FE: tách `layer3/page.tsx` (73KB), `layer5/page.tsx` (69KB) thành component nhỏ + hook.

---

## Phase 4 — Bổ sung tính năng & Hoàn thiện pipeline (🟡/🟢)

Mục tiêu: các tính năng nâng cao giá trị mà code hiện đã sẵn nền.

### 4.1 Hoàn thiện Layer 3 (SQL Migration)
- [ ] Bổ sung **migrate index/FK/constraint** (hiện tập trung CREATE TABLE) trong `table_converter.py`.
- [ ] Thêm **dry-run + diff report** trước khi execute DDL lên Postgres.
- [ ] Thêm **rollback script** sinh kèm mỗi lần migrate.
- [ ] Validate dữ liệu sau migrate (row count, type sanity).

### 4.2 Layer 5 Build-Verify mạnh hơn
- [ ] Tăng khả năng tự sửa: log chi tiết từng iteration của `build_verify.py` (hiện max 3 lần).
- [ ] Thêm **unit test sinh kèm** cho code C# được generate (xUnit skeleton).
- [ ] Báo cáo coverage mapping Access→.NET (control nào chưa map).

### 4.3 Trải nghiệm pipeline đầu-cuối
- [ ] `run_all.py`: thêm **resume/checkpoint** (bỏ qua item đã xử lý), flag `--only-layer`, `--from-layer`.
- [ ] Thêm **progress dashboard** trên Web Console: trạng thái từng item qua 5 layer (đã parse / có BD / có DD / có Excel / có code).
- [ ] Thêm cơ chế **incremental**: chỉ chạy lại item có input thay đổi (hash JSON nguồn).

### 4.4 Quản lý chi phí LLM
- [ ] Dashboard tổng hợp token/USD theo layer + theo item (gộp report Phase 2.4).
- [ ] Cảnh báo ngưỡng chi phí; cấu hình budget cap.
- [ ] Kiểm thử thực tế **fallback chain** khi quota cạn (README mô tả nhưng cần test tự động).

### 4.5 Đa dialect SQL (🟢)
- [x] ĐÃ CHỐT **chỉ PostgreSQL** — đã loại bỏ hẳn mọi dấu vết Oracle khỏi code (table_converter, router prompt, tool_repo type-map, proto, frontend dropdowns) và tài liệu.

---

## Phase 5 — Vận hành & Hoàn thiện (🟢)

- [ ] Viết `CONTRIBUTING.md` + chuẩn commit/PR.
- [ ] Thêm pre-commit hooks (black/ruff cho Python, eslint/prettier cho FE).
- [ ] Dockerize backend gRPC + frontend để deploy nhất quán.
- [ ] Tài liệu kiến trúc cập nhật trong `docs/ai-md/` (đã có nền sẵn).
- [ ] Backup/restore script cho MongoDB & Postgres (data volume hiện ở `data/mongo`, `data/postgres`).

---

## Thứ tự thực thi đề xuất

```
Phase 1 (bảo mật + pin deps)        ──► nền an toàn, bắt buộc trước
   └─► Phase 2 (test + CI)          ──► lưới an toàn để refactor
          └─► Phase 3 (docs + dọn kiến trúc)
                 └─► Phase 4 (tính năng mới)
                        └─► Phase 5 (vận hành)
```

**Quick wins làm ngay (≤ 1 ngày mỗi cái):**
1. Bind docker-compose về `127.0.0.1` (1.2).
2. Pin `requirements.txt` (1.4).
3. Quét secrets trong git history (1.3).
4. ~~Sửa các lệch README rõ ràng nhất: Oracle/Qdrant~~ (ĐÃ XONG), Next version, swap tên layer (3.1).
5. Thêm `pytest.ini` + 1 bộ test cho `table_converter.py` (2.1).

---

## Ghi chú phạm vi
- Plan dựa trên khảo sát ngày lập tài liệu; một số quyết định (UI target, đổi tên service) cần **bạn chốt hướng** trước khi thực thi vì có tính breaking.
- Các mục 🔴 nên hoàn thành trước khi đưa hệ thống ra môi trường chia sẻ/production.
