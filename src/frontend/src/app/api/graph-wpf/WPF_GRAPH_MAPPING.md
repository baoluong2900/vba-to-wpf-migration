# Mapping đồ thị VBA (Mongo) → WPF Graph (FE)

Tài liệu mô tả cách API **`GET /api/graph-wpf`** chuyển đồ thị dependency do `graphBuilder.ts` (VBA) sinh ra thành đồ thị các lớp WPF gợi ý. Logic nằm trong **`wpfGraphTransform.ts`** (`buildWpfLayerGraph`).

---

## 1. Mục đích

- **Input:** `nodes` + `edges` giống `/api/graph` (id kiểu `form:…`, `event:…::…`, `query:…`, `macro:…`, `module:…`, `report:…`).
- **Output:** Đồ thị mới với `type` Cytoscape: `view`, `viewmodel`, `handler` (gồm cả command của macro), `repository`, `service`, `navigation`, `warning`; thêm **`rootId`** để UI highlight đúng nút trung tâm (tab WPF Graph trên dashboard).

Đây là **mô hình gợi ý** từ export Layer5 + topology VBA, **không** parse C# / XAML thật.

---

## 2. Nguồn dữ liệu mapping (JSON)

Đường dẫn tính từ `GRAPHVIEW_DIR` = **`src/backend/workflow/layer5/agents/graphview`** (xem `src/lib/paths.ts`; override gốc workflow bằng `VBA_BRAIN_ROOT`):

| File (relative) | Khóa | Dùng cho |
|-----------------|------|----------|
| `outputs/forms/listFormJpToEn.json` | `access_form_name` → `wpf_view_name`, `wpf_viewmodel_name` | Nhãn View / ViewModel (form & report dùng chung map này nếu có tên trùng) và service `service:{accessName}` |
| `outputs/events/listEventJpToEn.json` | `access_form_name` + `handler_hint` → `suggested_dotnet_handler_name` | Nhãn node **handler** và service `service:{form}\|{handler}` |
| `outputs/queries/listQueryJpToEn.json` | `access_query_name` → `suggested_dotnet_type_name` | Suy ra tên **Repository** |
| `outputs/macros/listMacroJpToEn.json` | `access_macro_name` → `suggested_dotnet_type_name` | Nhãn **command** của macro (`handler:macro:…`) và service `service:macro:…` |

JSON được cache trong bộ nhớ process (biến `cache` trong `loadWpfMaps()`) chỉ khi đọc đủ cả 4 file; thiếu file nào thì log cảnh báo một lần và lần gọi sau đọc lại.

---

## 3. Quy ước ID node WPF

| `type` (Cytoscape) | ID | Ghi chú |
|--------------------|-----|---------|
| `view` | `view:{accessName}` | `accessName` = tên form/report Access |
| `viewmodel` | `viewmodel:{accessName}` | Cặp với `view:` cùng `accessName` |
| `handler` | `handler:{form}\|{handler}` | `handler` = tên procedure VBA (ví dụ `Form_Open`) |
| `handler` | `handler:macro:{macroName}` | Một macro → một command (ICommand) gợi ý |
| `repository` | `repository:{queryName}` | Một query → một node repo |
| `service` | `service:{accessName}` | Service use-case của form/report, đứng giữa ViewModel và Repository |
| `service` | `service:{form}\|{handler}` | Service use-case của một event handler, đứng giữa Handler và Repository |
| `service` | `service:macro:{macroName}` | Service use-case của macro, đứng giữa command của macro và Repository |
| `service` | `service:module:{moduleName}` | Module VBA → service gợi ý |
| `navigation` | `service:navigation` | Một node `NavigationService` dùng chung cho mọi cạnh mở/đóng form/report |
| `warning` | `trace:{vbaId}` | Đầu cạnh VBA không map được (xem §6) |

Mọi node đều có `vbaLabel` giữ mốc VBA gốc để panel chi tiết hiển thị, và `mappingStatus`: `mapped` (tên lấy từ JSON map), `fallback` (tên tự sinh, cần review) hoặc `trace` (node `trace:`).

---

## 4. Tạo “stack” View / ViewModel

Với form/report gốc (khi `type` là `form` / `report`) và mỗi **form** hoặc **report** là **nguồn** của một cạnh VBA; form/report chỉ nằm ở **đích** cạnh (ví dụ form được event/macro mở) **không** có stack, cạnh event/macro tới nó đi vào `service:navigation` (xem §6):

- **`ensureFormStack(accessForm)`** hoặc **`ensureReportStack(accessReport)`** (cùng logic bên trong):
  - Node `view:{name}` — `label` từ JSON form map, fallback `{name}View`; `badge` gợi ý `Views/*.axaml`; `vbaLabel` = tên Access.
  - Node `viewmodel:{name}` — `label` từ `wpf_viewmodel_name`, fallback `{name}ViewModel`; `badge` `ViewModels/*.cs`.
  - Cạnh: `view:{name}` → `viewmodel:{name}` nhãn **`DataContext`**.

Phân biệt report vs form trên cùng một `accessName`:

- Nếu id VBA có dạng `report:{name}` hoặc tên nằm trong tập `reportNames` (quét từ graph) → gọi **`ensureReportStack`**, ngược lại **`ensureFormStack`**.

---

## 5. Các node đặc thù

### Handler

- `ensureHandler(form, handler)`  
- Nhãn: `events` map `form::handler` → `suggested_dotnet_handler_name`, không có map thì dùng nguyên tên VBA `handler`.
- `badge`: `ICommand`; `vbaLabel`: `{form}::{handler}`.

### Repository

- `ensureRepository(queryName)`  
- `queryName` lấy từ node/cạnh VBA có id dạng `query:{queryName}`.
- Tra `queryName` trong `listQueryJpToEn.json` bằng `access_query_name`; có normalize nhẹ Unicode (`NFKC`, xử lý `Ⅱ`/`II`) để giảm lỗi lệch ký tự.
- Nếu có `suggested_dotnet_type_name` và kết thúc bằng `AccessQuery` (không phân biệt hoa thường) → thay hậu tố thành **`Repository`**.  
- Nếu có spec nhưng không khớp `AccessQuery` → **`{spec}Repository`**.  
- Không có trong JSON → fallback `pascalFallbackName`: chuẩn hóa NFKC, đổi `Ⅱ` / số khoanh tròn / số full-width thành số ASCII, tách theo mọi ký tự không phải chữ/số ASCII (chữ Nhật bị bỏ), viết hoa **chữ cái đầu** mỗi đoạn, phần còn lại giữ nguyên, rồi nối lại; ví dụ `C000_MAINⅡ_未入金_改` fallback thành `C000MAIN2Repository` (không phải `C000Main2Repository`), không giữ dạng nhiều `_` như `C000_MAIN______Repository`. Không còn chữ/số ASCII nào → `QueryRepository`.

Ví dụ khi mapping trúng:

```text
query:C000_MAINⅡ
  listQueryJpToEn: C000Main2AccessQuery
  repository label: C000Main2Repository
```

### Command (macro)

- `ensureMacroCommand(macroName)`  
- ID `handler:macro:{macroName}`, `type` = `handler`: macro thành command, không còn node `workflow`.  
- Nhãn: map macro JSON, đổi hậu tố `Workflow` hoặc `Macro` thành `Command` (không có hậu tố đó thì giữ nguyên); không có map thì fallback **`{Pascal(macroName)}Command`** (cùng `pascalFallbackName` như Repository, ví dụ `M_OpenMain` → `MOpenMainCommand`).  
- `badge`: `ICommand (macro)`; `vbaLabel`: `{macroName}`.

### Service use-case (form/report/handler/macro)

- `ensureUseCaseService(accessName)`  
- Tạo service nghiệp vụ cho form/report khi form/report có cạnh **trực tiếp** tới `query:` (RecordSource).  
- ID: `service:{accessName}`; nhãn ưu tiên theo ViewModel map rồi đổi hậu tố `ViewModel` thành `Service`, không có map thì `{Pascal(accessName)}Service`.
- Mục đích: giữ kiến trúc WPF theo tầng **View/ViewModel/Handler → Service → Repository**, không để UI/handler gọi Repository trực tiếp.

- `ensureHandlerService(form, handler)`  
- Tạo service nghiệp vụ riêng cho từng event handler khi event có cạnh tới `query:` (không gom chung vào `service:{form}`).  
- ID: `service:{form}|{handler}`; nhãn lấy tên handler từ events map, bỏ hậu tố `Command` và tiền tố `On`, thêm `Service` (ví dụ `LoginCommand` → `LoginService`); không có map thì `{Pascal(handler)}Service`.

- `ensureMacroService(macroName)`  
- Tạo service nghiệp vụ cho macro khi macro dùng query.  
- ID: `service:macro:{macroName}`; nhãn từ macro map (hoặc Pascal fallback) bỏ hậu tố `Workflow` / `Macro` / `Command`, thêm `Service`.

### Service module

- `ensureModuleService(moduleName)`  
- Nhãn cố định dạng gợi ý: **`{Pascal(moduleName)}ModuleService`** (cùng `pascalFallbackName`, ví dụ `basUtil` → `BasUtilModuleService`).  
- `badge`: `Application/Services`; `mappingStatus` luôn `fallback` (không có JSON map cho module).
- Đây là service gợi ý cho VBA module/shared procedure, khác với service use-case được tạo cho form/report/handler/macro.

### NavigationService

- `ensureNavigationService()`  
- Một node duy nhất `service:navigation`, `type` = `navigation`, nhãn cố định **`NavigationService`** (`mappingStatus` `mapped`), `badge` `Application/Navigation`, `vbaLabel` `DoCmd.OpenForm/OpenReport`.  
- Chỉ tạo khi có cạnh event/macro → form/report; mọi cạnh mở/đóng form/report gom vào node này (xem §6).

### Trace (dependency chưa map)

- `ensureTraceNode(vbaId)`  
- ID `trace:{vbaId}`, `type` = `warning`, nhãn = `vbaId` bỏ tiền tố loại (ví dụ `form:`), `badge` `Unmapped VBA dependency`, `vbaLabel` = `vbaId`, `mappingStatus` `trace`, `status` `warning`.  
- Dùng cho hai đầu của cạnh VBA không khớp dòng nào ở §6.

---

## 6. Chuyển cạnh VBA → cạnh WPF

Mỗi cạnh VBA `(source, target, label)` được xử lý theo bảng sau (thứ tự `if` trong code). Nhãn cạnh mới: cột **WPF label**. Dạng "`lbl` hoặc **X**" nghĩa là giữ nhãn cạnh VBA, thiếu nhãn mới dùng **X** (`lbl ?? 'X'` trong code); `graphBuilder` hiện luôn gán nhãn (`event`, `calls`, `references`, …) nên trên thực tế các dòng này hiện nhãn VBA. Các dòng còn lại luôn dùng nhãn cố định, bỏ nhãn VBA.

| Nguồn VBA | Đích VBA | Nguồn WPF | Đích WPF | WPF label |
|-----------|----------|-----------|----------|-----------|
| `form:` / `report:` | `event:` | `viewmodel:{form}` | `handler:{form}\|{handler}` | `lbl` hoặc **`handles`** |
| `module:` | `event:` | `service:module:{module}` | `handler:…` | `lbl` hoặc **`handles`** |
| `macro:` | `macro:` | `handler:macro:{A}` | `handler:macro:{B}` | `lbl` hoặc **`calls command`** |
| `macro:` | `form:` | `handler:macro:{macro}` | `service:navigation` | **`uses navigation`** |
| `macro:` | `report:` | `handler:macro:{macro}` | `service:navigation` | **`uses navigation`** |
| `macro:` | `query:` | `handler:macro:{macro}` → `service:macro:{macro}` | `repository:{query}` | `calls service` rồi **`uses repository`** |
| `event:` | `query:` | `handler:…` → `service:{form}\|{handler}` | `repository:{query}` | `calls service` rồi **`uses repository`** |
| `event:` | `form:` | `handler:…` | `service:navigation` | **`uses navigation`** |
| `event:` | `report:` | `handler:…` | `service:navigation` | **`uses navigation`** |
| `event:` | `macro:` | `handler:…` | `handler:macro:{macro}` | `lbl` hoặc **`invokes command`** |
| `event:` | `module:` | `handler:…` | `service:module:{module}` | `lbl` hoặc **`uses`** |
| `form:` / `report:` | `query:` | `viewmodel:{form}` → `service:{form}` | `repository:{query}` | `loads via service` rồi **`uses repository`** |
| `module:` | `query:` | `service:module:{module}` | `repository:{query}` | **`uses repository`** |
| (còn lại) | (còn lại) | `trace:{source}` | `trace:{target}` | `lbl` hoặc **`unmapped dependency`** |

Với các cạnh đi tới `query:`, graph WPF luôn ưu tiên tầng **Service → Repository**. `Repository` chỉ đại diện cho data-access/query wrapper; `Service` mới là nơi chứa nghiệp vụ/use-case để ViewModel hoặc Handler gọi vào.

Các cạnh mở/đóng form/report (`opens form`, `closes form`, `references report`) của cùng một handler/command gom thành **một** cạnh `uses navigation` tới `service:navigation`; không có cạnh nào trỏ tới `view:` của form/report đích.

Cạnh trùng (cùng source, target, label) bị bỏ qua (tập `edgeKey`); cạnh tự trỏ (source = target, ví dụ cạnh `calls` từ macro gốc tới chính nó) cũng bị bỏ.

Cạnh VBA **không** khớp bất kỳ dòng nào ở trên **không** bị bỏ: hai đầu cạnh thành node `trace:{vbaId}` (`type` `warning`), nối bằng cạnh `status: warning`, `vbaLabel` = `{source} -> {target}`, nhãn `lbl` hoặc `unmapped dependency`; UI tô vàng các node/cạnh này (cạnh nét đứt).

---

## 7. `rootId` trả về API (highlight)

| `type` query (API) | `rootId` |
|--------------------|----------|
| `form` | `view:{name}` |
| `report` | `view:{name}` |
| `module` | `service:module:{name}` |
| `macro` | `handler:macro:{name}` |

`GraphView` dùng `data.rootId` nếu có; không có thì fallback `type:name` (chuẩn VBA).

---

## 8. Thống kê (`stats`)

Đếm theo `node.data.type`: `views`, `viewmodels`, `handlers` (gồm cả command của macro), `repositories`, `services`, `navigation`, `warnings`, cộng `nodes` / `edges`. Khóa `workflows` vẫn còn nhưng luôn bằng 0 (không còn node `workflow`). Thêm các khóa tương thích VBA cũ để UI linh hoạt: `events` = handlers, `macros` = số node `handler:macro:`, `modules` = services (tính mọi service, không riêng module), `queries` = repositories, `forms` = views.

---

## 9. Hạn chế & hướng mở rộng

- **Không** suy DI chi tiết (constructor inject) từ C#.
- **Không** map `event → event` hay các pattern VBA lạ nếu `graphBuilder` không sinh cạnh tương ứng.
- Macro → module, form → macro trực tiếp (không qua event), v.v. nếu có trong VBA graph sau này → cần bổ sung nhánh trong `buildWpfLayerGraph` (trước đó chúng rơi vào nhánh `trace:` warning ở §6).
- Đồ thị WPF “chuẩn migration” theo tài liệu Agent GraphView (so khớp với C# parse) là bước **khác**, có thể thay hoặc merge output `dependency_{form}.json` khi có.

---

## 10. File liên quan

| File | Vai trò |
|------|---------|
| `frontend/src/app/api/graph/graphBuilder.ts` | Sinh graph VBA (Mongo) |
| `frontend/src/app/api/graph-wpf/route.ts` | `buildAccessGraph` → `buildWpfLayerGraph` → JSON response |
| `frontend/src/app/api/graph-wpf/wpfGraphTransform.ts` | Toàn bộ mapping layer |
| `frontend/src/app/api/graph-wpf/export/route.ts` | `POST`: cùng `buildWpfLayerGraph`, ghi expected graph ra `WPF_GRAPH_REPORTS_DIR/{name}.expected.json` (xem `src/lib/paths.ts`) |
| `frontend/src/app/api/graph-wpf/source-review/` | `GET`: parse source WPF thật dưới `WPF_DIR` (`sourceGraphParser.ts`) rồi diff với file expected ở trên |
| `frontend/src/components/GraphView.tsx` | `apiPath=/api/graph-wpf`, `graphKind=wpf`, legend & stats theo type WPF |
