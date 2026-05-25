# Mapping đồ thị VBA (Mongo) → WPF Graph (FE)

Tài liệu mô tả cách API **`GET /api/graph-wpf`** chuyển đồ thị dependency do `graphBuilder.ts` (VBA) sinh ra thành đồ thị các lớp WPF gợi ý. Logic nằm trong **`wpfGraphTransform.ts`** (`buildWpfLayerGraph`).

---

## 1. Mục đích

- **Input:** `nodes` + `edges` giống `/api/graph` (id kiểu `form:…`, `event:…::…`, `query:…`, `macro:…`, `module:…`, `report:…`).
- **Output:** Đồ thị mới với `type` Cytoscape: `view`, `viewmodel`, `handler`, `repository`, `service`, `workflow`; thêm **`rootId`** để UI highlight đúng nút trung tâm (tab WPF Graph trên dashboard).

Đây là **mô hình gợi ý** từ export Layer5 + topology VBA, **không** parse C# / XAML thật.

---

## 2. Nguồn dữ liệu mapping (JSON)

Đường dẫn tính từ thư mục **`workflow/frontend`** (`process.cwd()` khi chạy Next):

| File (relative) | Khóa | Dùng cho |
|-----------------|------|----------|
| `../backend/layer5/agents/graphview/outputs/forms/listFormJpToEn.json` | `access_form_name` → `wpf_view_name`, `wpf_viewmodel_name` | Nhãn View / ViewModel (form & report dùng chung map này nếu có tên trùng) |
| `../backend/layer5/agents/graphview/outputs/events/listEventJpToEn.json` | `access_form_name` + `handler_hint` → `suggested_dotnet_handler_name` | Nhãn node **handler** |
| `../backend/layer5/agents/graphview/outputs/queries/listQueryJpToEn.json` | `access_query_name` → `suggested_dotnet_type_name` | Suy ra tên **Repository** |
| `../backend/layer5/agents/graphview/outputs/macros/listMacroJpToEn.json` | `access_macro_name` → `suggested_dotnet_type_name` | Nhãn node **workflow** |

JSON được đọc một lần và cache trong bộ nhớ process (biến `cache` trong `loadWpfMaps()`).

---

## 3. Quy ước ID node WPF

| `type` (Cytoscape) | ID | Ghi chú |
|--------------------|-----|---------|
| `view` | `view:{accessName}` | `accessName` = tên form/report Access |
| `viewmodel` | `viewmodel:{accessName}` | Cặp với `view:` cùng `accessName` |
| `handler` | `handler:{form}\|{handler}` | `handler` = tên procedure VBA (ví dụ `Form_Open`) |
| `repository` | `repository:{queryName}` | Một query → một node repo |
| `workflow` | `workflow:{macroName}` | Một macro → một workflow |
| `service` | `service:{accessName}` | Service use-case của form/report, đứng giữa ViewModel/Handler và Repository |
| `service` | `service:macro:{macroName}` | Service use-case của macro, đứng giữa Workflow và Repository |
| `service` | `service:module:{moduleName}` | Module VBA → service gợi ý |

Trường `vbaLabel` trên node (khi có) giữ mốc VBA gốc để panel chi tiết hiển thị.

---

## 4. Tạo “stack” View / ViewModel

Với mỗi **form** hoặc **report** xuất hiện trong graph (từ node hoặc từ hai đầu cạnh):

- **`ensureFormStack(accessForm)`** hoặc **`ensureReportStack(accessReport)`** (cùng logic bên trong):
  - Node `view:{name}` — `label` từ JSON form map, fallback `{name}View`; `badge` gợi ý `Views/*.xaml`; `vbaLabel` = tên Access.
  - Node `viewmodel:{name}` — `label` từ `wpf_viewmodel_name`, fallback `{name}ViewModel`; `badge` `ViewModels/*.cs`.
  - Cạnh: `view:{name}` → `viewmodel:{name}` nhãn **`DataContext`**.

Phân biệt report vs form trên cùng một `accessName`:

- Nếu id VBA có dạng `report:{name}` hoặc tên nằm trong tập `reportNames` (quét từ graph) → gọi **`ensureReportStack`**, ngược lại **`ensureFormStack`**.

---

## 5. Các node đặc thù

### Handler

- `ensureHandler(form, handler)`  
- Nhãn: `events` map `form::handler` → `suggested_dotnet_handler_name`, không có map thì dùng nguyên tên VBA `handler`.
- `badge`: `ICommand / method`; `vbaLabel`: `{form}::{handler}`.

### Repository

- `ensureRepository(queryName)`  
- `queryName` lấy từ node/cạnh VBA có id dạng `query:{queryName}`.
- Tra `queryName` trong `listQueryJpToEn.json` bằng `access_query_name`; có normalize nhẹ Unicode (`NFKC`, xử lý `Ⅱ`/`II`) để giảm lỗi lệch ký tự.
- Nếu có `suggested_dotnet_type_name` và kết thúc bằng `AccessQuery` (không phân biệt hoa thường) → thay hậu tố thành **`Repository`**.  
- Nếu có spec nhưng không khớp `AccessQuery` → **`{spec}Repository`**.  
- Không có trong JSON → fallback Pascal từ phần chữ/số còn đọc được, collapse ký tự lạ; ví dụ `C000_MAINⅡ_未入金_改` fallback thành `C000Main2Repository`, không giữ dạng nhiều `_` như `C000_MAIN______Repository`.

Ví dụ khi mapping trúng:

```text
query:C000_MAINⅡ
  listQueryJpToEn: C000Main2AccessQuery
  repository label: C000Main2Repository
```

### Workflow (macro)

- `ensureWorkflow(macroName)`  
- Nhãn: map macro JSON, fallback **`{macroName}MacroWorkflow`**.  
- `badge`: `Application/Workflows`.

### Service use-case (form/report/macro)

- `ensureUseCaseService(accessName)`  
- Tạo service nghiệp vụ cho form/report khi graph VBA có cạnh tới `query:`.  
- ID: `service:{accessName}`; nhãn ưu tiên theo ViewModel map rồi đổi hậu tố `ViewModel` thành `Service`.
- Mục đích: giữ kiến trúc WPF theo tầng **View/ViewModel/Handler → Service → Repository**, không để UI/handler gọi Repository trực tiếp.

- `ensureMacroService(macroName)`  
- Tạo service nghiệp vụ cho macro khi macro dùng query.  
- ID: `service:macro:{macroName}`.

### Service module

- `ensureModuleService(moduleName)`  
- Nhãn cố định dạng gợi ý: **`{moduleName}ModuleService`**.  
- `badge`: `Application/Services`.
- Đây là service gợi ý cho VBA module/shared procedure, khác với service use-case được tạo cho form/report/macro.

---

## 6. Chuyển cạnh VBA → cạnh WPF

Mỗi cạnh VBA `(source, target, label)` được xử lý theo bảng sau (thứ tự `if` trong code). Nhãn cạnh mới: cột **WPF label** (nếu không ghi thì dùng mặc định sau `??`).

| Nguồn VBA | Đích VBA | Nguồn WPF | Đích WPF | WPF label (mặc định nếu thiếu `lbl`) |
|-----------|----------|-----------|----------|--------------------------------------|
| `form:` / `report:` | `event:` | `viewmodel:{form}` | `handler:{form}\|{handler}` | `lbl` hoặc **`handles`** |
| `module:` | `event:` | `service:module:{module}` | `handler:…` | **`handles`** |
| `macro:` | `macro:` | `workflow:{A}` | `workflow:{B}` | **`calls`** |
| `macro:` | `form:` | `workflow:{macro}` | `view:{form}` | **`opens view`** (đảm bảo form stack trước) |
| `macro:` | `report:` | `workflow:{macro}` | `view:{report}` | **`opens view`** |
| `macro:` | `query:` | `workflow:{macro}` → `service:macro:{macro}` | `repository:{query}` | `uses service` rồi **`uses repository`** |
| `event:` | `query:` | `handler:…` → `service:{form}` | `repository:{query}` | `calls service` rồi **`uses repository`** |
| `event:` | `form:` | `handler:…` | `view:{form}` | **`Navigate`** |
| `event:` | `report:` | `handler:…` | `view:{report}` | **`Navigate`** |
| `event:` | `macro:` | `handler:…` | `workflow:{macro}` | **`invokes`** |
| `event:` | `module:` | `handler:…` | `service:module:{module}` | **`uses`** |
| `form:` / `report:` | `query:` | `viewmodel:{form}` → `service:{form}` | `repository:{query}` | `loads via service` rồi **`uses repository`** |
| `module:` | `query:` | `service:module:{module}` | `repository:{query}` | **`uses repository`** |

Với các cạnh đi tới `query:`, graph WPF luôn ưu tiên tầng **Service → Repository**. `Repository` chỉ đại diện cho data-access/query wrapper; `Service` mới là nơi chứa nghiệp vụ/use-case để ViewModel hoặc Handler gọi vào.

Cạnh trùng (cùng source, target, label) bị bỏ qua (tập `edgeKey`).

Cạnh VBA **không** khớp bất kỳ dòng nào ở trên → **bị bỏ** (không xuất hiện trên WPF graph).

---

## 7. `rootId` trả về API (highlight)

| `type` query (API) | `rootId` |
|--------------------|----------|
| `form` | `view:{name}` |
| `report` | `view:{name}` |
| `module` | `service:module:{name}` |
| `macro` | `workflow:{name}` |

`GraphView` dùng `data.rootId` nếu có; không có thì fallback `type:name` (chuẩn VBA).

---

## 8. Thống kê (`stats`)

Đếm theo `node.data.type`: `views`, `viewmodels`, `handlers`, `repositories`, `services`, `workflows`, cộng `nodes` / `edges`. Thêm các khóa tương thích VBA cũ (`events` = handlers, `forms` = views, …) để UI linh hoạt.

---

## 9. Hạn chế & hướng mở rộng

- **Không** suy DI chi tiết (constructor inject) từ C#.
- **Không** map `event → event` hay các pattern VBA lạ nếu `graphBuilder` không sinh cạnh tương ứng.
- Macro → module, form → macro trực tiếp (không qua event), v.v. nếu có trong VBA graph sau này → cần bổ sung nhánh trong `buildWpfLayerGraph`.
- Đồ thị WPF “chuẩn migration” theo tài liệu Agent GraphView (so khớp với C# parse) là bước **khác**, có thể thay hoặc merge output `dependency_{form}.json` khi có.

---

## 10. File liên quan

| File | Vai trò |
|------|---------|
| `frontend/src/app/api/graph/graphBuilder.ts` | Sinh graph VBA (Mongo) |
| `frontend/src/app/api/graph-wpf/route.ts` | `buildAccessGraph` → `buildWpfLayerGraph` → JSON response |
| `frontend/src/app/api/graph-wpf/wpfGraphTransform.ts` | Toàn bộ mapping layer |
| `frontend/src/components/GraphView.tsx` | `apiPath=/api/graph-wpf`, `graphKind=wpf`, legend & stats theo type WPF |
