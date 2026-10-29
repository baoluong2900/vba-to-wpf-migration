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
| G2 | ~~Tên layer gRPC **ngược** với README~~ — README đã ghi rõ: `Layer3Service`=Excel, `Layer4Service`=SQL Migration (đổi tên service: xem 3.3) | `grpc_server.py` | ✅ |
| G3 | ~~Frontend thực tế **Next.js 16.2.4 / React 19 / Tailwind 4**, README ghi Next 15 / Yarn~~ — README đã ghi đúng phiên bản | `frontend/package.json` | ✅ |
| G4 | ~~Tồn tại **2 UI song song**~~ — ĐÃ CHỐT **Avalonia** làm UI chính; Layer 5 codegen + deploy đã trỏ về `vba_brain.UI.Avalonia`. Folder trống `vba_brain.UI.WPF` đã được xóa | `src/wpf/` | ✅ |
| G5 | ~~gRPC không auth, bind `[::]`~~ — ĐÃ bind `localhost` mặc định + token Bearer tùy chọn (`api_gateway/auth.py`) + TLS tùy chọn (`GRPC_TLS_CERT` / `GRPC_TLS_KEY`) | `grpc_server.py::serve` | 🟡 |
| G6 | ~~docker-compose bind `0.0.0.0`~~ — ĐÃ bind `127.0.0.1` | `docker-compose.yml` | ✅ |
| G7 | ~~Không test, không CI, dependency không pin~~ — ĐÃ có pytest (backend + Layer 5) + `node --test` (frontend) + CI 4 job; dependency có trần major (trừ `typing_extensions`) | toàn repo | 🟡 |
| G8 | File khổng lồ khó bảo trì (`agent_ui.py` 120KB, `dd_common.py` 80KB, FE `layer3/page.tsx` 73KB); `fill_dd_excel_report.py` (từng 79KB) đã tách phần chung sang `dd_common.py`, còn ~7.7KB | layer4/5, frontend | 🟡 |
| G9 | **Mật khẩu PostgreSQL thật đã lọt vào git history**: `src/wpf/vba_brain.UI.Avalonia/appsettings.json` (user `postgres`) được commit ở `85a0e7f`, xóa ở `691ae04` nhưng vẫn còn trong history của repo public → phải rotate, xem `SECURITY.md`. Ngoài ra không có `config.json`/`.env` nào từng được commit, không có key `sk-`/`gsk_`/`AKIA`/`ghp_` | git history | 🔴 |

---

## Phase 1 — Ổn định nền tảng & Bảo mật (🔴 ưu tiên cao nhất)

Mục tiêu: hệ thống an toàn, chạy lại được tin cậy trước khi thêm tính năng.

### 1.1 Bảo mật gRPC Gateway
- [x] Thêm **token/API-key interceptor** cho gRPC server (`api_gateway/auth.py`, `GRPC_AUTH_TOKEN`); gateway bind `localhost` mặc định (`GRPC_HOST`).
- [x] Thêm tùy chọn **TLS** (`GRPC_TLS_CERT` / `GRPC_TLS_KEY` → `add_secure_port`; console tin `GRPC_TLS_CA`); mặc định localhost vẫn chạy plaintext.
- [ ] Chuẩn hóa **error handling**: map exception → `grpc.StatusCode` thay vì để lỗi rò rỉ stack trace.

### 1.2 Khóa bề mặt hạ tầng
- [x] Đổi binding docker-compose từ `0.0.0.0:PORT` → `127.0.0.1:PORT` cho Mongo/Postgres/Mongo-Express (chỉ mở ra ngoài khi thực sự cần).
- [x] Xác nhận **MongoDB bật auth** (root user qua `MONGO_INITDB_ROOT_*`); `mongo-init/01_init_user.js` không còn tạo thêm tài khoản root với mật khẩu cứng.
- [x] Tài liệu hóa: production KHÔNG dùng Mongo-Express (`SECURITY.md`).

### 1.3 Vệ sinh secrets
- [x] Quét git history tìm key đã lọt: không có API key, nhưng có **một mật khẩu PostgreSQL thật** (G9, xem `SECURITY.md`).
- [ ] Nếu có lọt → rotate key + dùng `git-filter-repo` — **cần**: rotate mật khẩu PostgreSQL ở G9 (xem `SECURITY.md`).
- [x] Bổ sung `infa/.env.example` đầy đủ biến (`MONGO_ROOT_USER/PASSWORD`, `POSTGRES_*`, `MONGO_EXPRESS_*`).

### 1.4 Pin & khóa dependency
- [x] Pin version trong `src/backend/requirements.txt`: sàn theo nhu cầu code + trần ở mốc major cho mọi gói trừ `typing_extensions` (không có trần); `protobuf<7`, `openai`/`anthropic<3` cho phép hơn một major; bỏ 9 gói không dùng, thêm `python-docx`, `protobuf`; tool dev trong `requirements-dev.txt`.
- [ ] Thêm `requirements.lock` (pip-tools/`pip freeze`) để build tái lập.
- [x] Frontend: commit `yarn.lock` (đã có) + ghi rõ Node version trong `.nvmrc` (repo root: `22`).

---

## Phase 2 — Chất lượng & Độ tin cậy (🔴/🟡)

Mục tiêu: thay đổi không sợ vỡ, có lưới an toàn.

### 2.1 Test framework (Python)
- [x] Thêm `pyproject.toml` cấu hình pytest + ruff.
- [x] Viết **unit test cho Layer 1 parser** (cả 5 parser, chạy trên fixture `src/vba/vba_source/`).
- [ ] Test cho `aggregator.py` (cross-reference: DoCmd, DLookup, CallSub).
- [x] Test cho Layer 3 `table_converter.py`, `query_utils.py`, `seed_queries_v2.py`, `router.py` (Mongo + LLM giả lập).
- [x] Mock LLM cho Layer 2/3/5 (test logic ráp prompt + parse output, không gọi API thật) — `tests/backend/test_layer2_*`, `test_layer3_router.py`, `tests/layer5/*`.
- [x] Gom các script test rời rạc: `src/vba/vba_source/run_tests.py` → `tests/backend/test_layer1_parsers.py`; `layer3/scratch/*` gỡ khỏi git; `layer4/scripts/test_*.py` xóa.

### 2.2 Test frontend
- [ ] Thêm test cho `graphBuilder.ts` và `wpfGraphTransform.ts` (logic thuần, không UI).
- [x] Smoke test build: `next build` phải pass (CI) + unit test `yarn test` cho `src/lib/*`.

### 2.3 CI/CD
- [x] `.github/workflows/ci.yml`: ruff + pytest + kiểm tra stub gRPC (backend), lint + tsc + test + build (frontend), `dotnet build` + chặn NuGet có lỗ hổng, hygiene.
- [x] Cache pip & yarn để CI nhanh.
- [x] Job `dotnet build vba_brain.slnx` (Avalonia) + kiểm tra package có lỗ hổng.

### 2.4 Logging & quan sát
- [ ] Chuẩn hóa **structured logging** (JSON) thay cho `print`/`*.log` rải rác.
- [ ] Thêm endpoint/health-check cho gRPC (`grpc_health_v1`) để FE và `start.py` kiểm tra trạng thái BE.
- [x] Tracker chi phí theo request (`cost_tracker.track_request`, contextvars) thay cho tracker toàn cục bị các request song song dùng chung.
- [ ] Hợp nhất token/cost report (Layer 2 `cost_tracker` + Layer 5 `token_tracker`) về một định dạng chung.

---

## Phase 3 — Đồng bộ tài liệu & Dọn kiến trúc (🟡)

Mục tiêu: README phản ánh đúng code; giảm nợ kỹ thuật.

### 3.1 Sửa README cho khớp thực tế
- [x] Cập nhật Infra table: đã bỏ Oracle XE/Qdrant, ghi đúng **PostgreSQL 16-alpine**.
- [x] Sửa **bảng gRPC**: làm rõ `Layer3Service`=Excel, `Layer4Service`=SQL (hoặc đổi tên service cho khớp ý nghĩa — xem 3.3).
- [x] Cập nhật Tech Stack frontend: **Next 16 / React 19 / Tailwind 4**.
- [x] Làm rõ chiến lược UI: **Avalonia** là target chính (G4 — đã chốt).

### 3.2 Quyết định 1 UI target — ✅ ĐÃ CHỐT: Avalonia
- [x] Chốt **Avalonia** (đa nền tảng, .NET 10) làm UI chính.
- [x] Layer 5 codegen sinh AXAML/Avalonia (namespace `vba_brain.UI.Avalonia`); `deploy_to_source.py`, `file_writer.py`, frontend `run-agent`/`run-logic` đã trỏ về `src/wpf/vba_brain.UI.Avalonia`.
- [x] `start_wpf.py` build/run `vba_brain.UI.Avalonia` (trực tiếp qua `vba_brain.UI.Avalonia.csproj`, không qua `vba_brain.slnx`).
- [x] Xóa folder trống `vba_brain.UI.WPF` (không còn dùng).

### 3.3 Đổi tên service gRPC cho nhất quán (nếu chọn)
- [ ] Cân nhắc đổi `Layer3Service`→`ExcelService`, `Layer4Service`→`SqlMigrationService` trong `.proto`, regenerate stub, cập nhật FE. (Breaking — làm có chủ đích, kèm test.)

### 3.4 Refactor file khổng lồ
- [ ] Tách `agent_ui.py` (120KB) theo trách nhiệm: skeleton / control_mapper / xaml_render / vm_gen.
- [x] Tách `fill_dd_excel_*` trùng lặp → `layer4/scripts/dd_common.py` (4 script DD: 8.031 → 3.022 dòng; so sánh output trước/sau trên 9 trường hợp).
- [ ] FE: tách `layer3/page.tsx` (73KB), `layer5/page.tsx` (56KB) thành component nhỏ + hook.

---

## Phase 4 — Bổ sung tính năng & Hoàn thiện pipeline (🟡/🟢)

Mục tiêu: các tính năng nâng cao giá trị mà code hiện đã sẵn nền.

### 4.1 Hoàn thiện Layer 3 (SQL Migration)
- [ ] Bổ sung **migrate index/FK/constraint** (hiện tập trung CREATE TABLE) trong `table_converter.py`.
- [x] Thêm **dry-run** (`postgres_migrator.py --dry-run --output schema.sql`) trước khi execute DDL lên Postgres; console không còn tự chạy bước này.
- [ ] Thêm **rollback script** sinh kèm mỗi lần migrate.
- [ ] Validate dữ liệu sau migrate (row count, type sanity).

### 4.2 Layer 5 Build-Verify mạnh hơn
- [ ] Tăng khả năng tự sửa: log chi tiết từng iteration của `build_verify.py` (hiện max 3 lần).
- [ ] Thêm **unit test sinh kèm** cho code C# được generate (xUnit skeleton).
- [ ] Báo cáo coverage mapping Access→.NET (control nào chưa map).

### 4.3 Trải nghiệm pipeline đầu-cuối
- [x] `run_all.py`: `--from`, `--only`, `--skip`, `--list`, `--dry-run`, `--keep-going` (checkpoint theo item: chưa).
- [ ] Thêm **progress dashboard** trên Web Console: trạng thái từng item qua 5 layer (đã parse / có BD / có DD / có Excel / có code).
- [ ] Thêm cơ chế **incremental**: chỉ chạy lại item có input thay đổi (hash JSON nguồn).

### 4.4 Quản lý chi phí LLM
- [ ] Dashboard tổng hợp token/USD theo layer + theo item (gộp report Phase 2.4).
- [ ] Cảnh báo ngưỡng chi phí; cấu hình budget cap.
- [x] Kiểm thử **fallback chain** khi quota cạn (`tests/backend/test_layer2_model_routing.py`): đi hết chuỗi, fail-fast với 403.

### 4.5 Đa dialect SQL (🟢)
- [x] ĐÃ CHỐT **chỉ PostgreSQL** — đã loại bỏ hẳn mọi dấu vết Oracle khỏi code (table_converter, router prompt, tool_repo type-map, proto, frontend dropdowns) và tài liệu.

---

## Phase 5 — Vận hành & Hoàn thiện (🟢)

- [x] Viết `CONTRIBUTING.md` + chuẩn commit/PR.
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
4. ~~Sửa các lệch README rõ ràng nhất: Oracle/Qdrant, Next version, swap tên layer~~ (ĐÃ XONG) (3.1).
5. ~~Thêm cấu hình pytest + 1 bộ test cho `table_converter.py`~~ (ĐÃ XONG: cấu hình nằm trong `pyproject.toml`, không có `pytest.ini`) (2.1).

---

## Ghi chú phạm vi
- Plan dựa trên khảo sát ngày lập tài liệu; một số quyết định (UI target, đổi tên service) cần **bạn chốt hướng** trước khi thực thi vì có tính breaking.
- Các mục 🔴 nên hoàn thành trước khi đưa hệ thống ra môi trường chia sẻ/production.

---

## Cập nhật sau đợt review toàn bộ source (2026-10-28)

Kết quả chi tiết, lý do từng bản sửa và danh sách việc còn lại: [`docs/REVIEW_REPORT.md`](REVIEW_REPORT.md).
Các mục mới phát sinh từ đợt review (chưa làm) đã được đưa vào §9 của báo cáo đó. TLS cho
gateway và tracker chi phí theo request đã làm xong (2026-10-29); quan trọng nhất còn lại là một
lượt Layer 5 thật có LLM (Agent Logic, vòng build-fix) và cho cấu hình thư mục nguồn của Layer 1
(hiện cố định `src/vba/vba_source`; `/layer1` không còn ô `source_path`).
