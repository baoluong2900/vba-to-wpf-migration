# WPF Expected Graph Plan

> Mục tiêu trước mắt: mapping đúng từ VBA/BD/DD sang **Expected WPF Graph**.
> Graph này là kế hoạch migrate trước khi generate code. Về sau sẽ dùng để diff với **Actual WPF Graph** parse từ source `source/vba_brain`.

---

## 1. Vai trò của graph hiện tại

`/api/graph-wpf` không nên được hiểu là graph dependency thật của WPF code.

Vai trò đúng của nó là:

```text
VBA graph + BD/DD + mapping JSON
  -> Expected WPF Graph
  -> dùng làm chuẩn để AI Agent review code WPF sau này
```

Nói cách khác:

- **Expected graph**: hệ thống nên được migrate sang WPF như thế nào.
- **Actual graph**: code WPF thực tế đang được viết/generate như thế nào.
- **Review graph**: so sánh Expected vs Actual để phát hiện thiếu, thừa, sai flow, sai layer.

Pha hiện tại chỉ tập trung làm **Expected graph** cho đúng.

---

## 2. Phạm vi agent review

Định hướng dài hạn:

- Review toàn bộ solution.
- Source review nằm trong `workflow/source/vba_brain`.
- Agent đọc tất cả file liên quan: XAML, ViewModel, Service, Repository, DTO, Entity, DI config, test nếu có.
- Output review gồm 3 dạng:
  - Graph hiển thị.
  - JSON cho máy đọc.
  - Markdown report cho dev đọc.

Nhưng trước mắt:

- Chưa parse WPF code thật.
- Chỉ xây dựng graph chuẩn từ VBA/BD/DD.
- Output của `/api/graph-wpf` được coi là **expected flow**.

---

## 3. Input của Expected WPF Graph

### 3.1 API input

Endpoint:

```text
GET /api/graph-wpf?name={access_object_name}&type={form|report|module|macro}
```

Tham số:

| Param | Ý nghĩa |
|---|---|
| `name` | Tên object Access cần dựng graph. |
| `type` | Loại object: `form`, `report`, `module`, `macro`. |

### 3.2 Nguồn dữ liệu chính

Expected flow lấy từ:

1. **VBA graph gốc** trong MongoDB.
2. **BD/DD JSON** nếu có thể bổ sung context.
3. **Layer5 mapping JSON** để đổi tên Access sang tên WPF gợi ý.

Khi VBA và BD/DD mâu thuẫn:

```text
VBA là chuẩn.
```

BD/DD chỉ nên dùng để bổ sung mô tả, tên nghiệp vụ, layout, field, hoặc rule chi tiết; không được override dependency gốc nếu chưa có human approval.

### 3.3 VBA graph input

Graph gốc được sinh bởi `buildAccessGraph`.

Node input có dạng:

| VBA node type | Ví dụ |
|---|---|
| `form` | `form:F_Login` |
| `report` | `report:R005_作業報告書` |
| `event` | `event:F_Login::cmdLogin_Click` |
| `query` | `query:Q000_T_LoginUser` |
| `macro` | `macro:M_OpenMain` |
| `module` | `module:CommonModule` |

Edge input có dạng:

| VBA edge | Ý nghĩa |
|---|---|
| `form -> event` | Form có event/procedure. |
| `event -> query` | Event chạy query. |
| `event -> macro` | Event gọi macro. |
| `event -> form` | Event mở/đóng form. |
| `event -> report` | Event mở report. |
| `event -> module` | Event gọi module/helper. |
| `macro -> form` | Macro mở form. |
| `macro -> query` | Macro chạy query. |
| `macro -> macro` | Macro gọi macro khác. |
| `form/report -> query` | RecordSource hoặc data source. |

### 3.4 Mapping JSON input

Các file mapping hiện tại:

| File | Dùng để |
|---|---|
| `backend/layer5/agents/graphview/outputs/forms/listFormJpToEn.json` | Map Access form/report sang WPF View + ViewModel. |
| `backend/layer5/agents/graphview/outputs/events/listEventJpToEn.json` | Map Access event handler sang ICommand/method. |
| `backend/layer5/agents/graphview/outputs/queries/listQueryJpToEn.json` | Map Access query sang Repository/spec name. |
| `backend/layer5/agents/graphview/outputs/macros/listMacroJpToEn.json` | Map Access macro sang command/workflow name gợi ý. |

Nếu thiếu mapping:

- Không được bỏ node.
- Phải fallback ra tên WPF an toàn.
- Node fallback nên được đánh dấu để sau này review mapping thiếu.

---

## 4. Output của Expected WPF Graph

Endpoint trả về:

```json
{
  "success": true,
  "graphKind": "wpf",
  "rootId": "view:F_Login",
  "elements": {
    "nodes": [],
    "edges": []
  },
  "stats": {
    "nodes": 0,
    "edges": 0,
    "views": 0,
    "viewmodels": 0,
    "handlers": 0,
    "services": 0,
    "repositories": 0,
    "workflows": 0
  }
}
```

### 4.1 Node output

Expected WPF Graph cần các node type chính:

| WPF node type | ID | Ý nghĩa |
|---|---|---|
| `view` | `view:{accessName}` | WPF XAML View. |
| `viewmodel` | `viewmodel:{accessName}` | ViewModel tương ứng View. |
| `handler` | `handler:{form}|{event}` | ICommand tương ứng Access event. |
| `service` | `service:{accessName}` | Application service/use-case service. |
| `repository` | `repository:{queryName}` | Repository bọc Access query/data access. |
| `module_service` hoặc `service` | `service:module:{moduleName}` | Service/helper migrate từ VBA module. |

Với mục tiêu mới:

```text
Macro Access khi migrate sang WPF nên thành command trong ViewModel.
```

Vì vậy không nên ưu tiên node `workflow` cho macro trong expected graph pha này.
Macro nên được biểu diễn như một command/handler hoặc command flow thuộc ViewModel gọi nó.

Khuyến nghị:

| Macro case | Expected WPF mapping |
|---|---|
| Event gọi macro | `handler:event` -> `handler:macroCommand` hoặc merge macro logic vào command hiện tại. |
| Macro mở form | command điều hướng qua ViewModel/NavigationService. |
| Macro chạy query | command gọi Service, Service gọi Repository. |
| Macro gọi macro khác | command gọi command/helper flow khác, nhưng vẫn nằm trong ViewModel/Service boundary. |

Nếu vẫn cần giữ node macro để trace nguồn VBA, node đó nên là metadata/reference, không phải layer runtime chính.

### 4.2 Edge output

Flow chuẩn mong muốn:

```text
View
  -> ViewModel
  -> ICommand / Handler
  -> Service
  -> Repository
```

Navigation:

```text
Handler / ViewModel
  -> NavigationService
  -> Target View
```

Module/helper:

```text
Handler / Service
  -> ModuleService
```

Report:

```text
ViewModel / Handler
  -> ReportService
  -> Repository
```

---

## 5. Mapping rule VBA -> Expected WPF

### Rule 1: Form/Report

VBA:

```text
form:{name}
report:{name}
```

Expected WPF:

```text
view:{name}
viewmodel:{name}
view:{name} -> viewmodel:{name} [DataContext]
```

Rule:

- View bắt buộc chỉ bind tới ViewModel.
- Không cho View gọi trực tiếp Service/Repository.
- XAML sau này phải kiểm tra `Command`, `DataContext`, `ItemsSource`, `SelectedItem`.

### Rule 2: Event

VBA:

```text
event:{form}::{handler}
```

Expected WPF:

```text
handler:{form}|{handler}
viewmodel:{form} -> handler:{form}|{handler}
```

Rule:

- Một Access event tương ứng với một `ICommand`.
- Tên command lấy từ `listEventJpToEn.json`.
- Nếu không có mapping thì fallback từ handler VBA.
- Event không nên mất trace về VBA gốc.

### Rule 3: Query

VBA:

```text
query:{queryName}
```

Expected WPF:

```text
repository:{queryName}
```

Rule:

- Query Access luôn map sang Repository.
- Repository chỉ chứa data access / SQL.
- SQL không được nằm trong View, ViewModel, Handler, hoặc Service.
- Service có thể gọi nhiều Repository.

### Rule 4: Event gọi Query

VBA:

```text
event -> query
```

Expected WPF:

```text
handler -> handler_service -> repository
```

Rule:

- ViewModel/Handler không được gọi Repository trực tiếp.
- Bắt buộc đi qua Service.
- Service cho `event -> query` được tạo theo command/use-case, không gom chung toàn bộ query của form vào một form service.
- ID service theo event: `service:{form}|{handler}`.
- Ví dụ: `LoginCommand -> LoginService -> Q000TLoginUserRepository`.

### Rule 5: Form/Report RecordSource

VBA:

```text
form/report -> query
```

Expected WPF:

```text
viewmodel -> service -> repository
```

Rule:

- Data load của màn hình đi qua ViewModel.
- ViewModel gọi Service.
- Service gọi Repository.

### Rule 6: Event mở Form/Report

VBA:

```text
event -> form/report
```

Expected WPF:

```text
handler -> navigation_service
```

Rule:

- Không mở View trực tiếp bằng code rải rác.
- Nên đi qua `NavigationService` hoặc abstraction tương đương.
- WPF Graph không show chi tiết từng `DoCmd.OpenForm`, `DoCmd.OpenReport`, hoặc `DoCmd.Close`.
- Các open/close form/report được gom thành cạnh tổng quát `uses navigation` tới `NavigationService`.
- Target form/report gốc vẫn nên được giữ trong dữ liệu review chi tiết sau này, nhưng không vẽ thành cạnh riêng trên Expected WPF Graph.

### Rule 7: Macro

VBA:

```text
event -> macro
macro -> query
macro -> form
macro -> macro
```

Expected WPF:

```text
event command / macro command
  -> service / navigation_service / repository
```

Rule:

- Macro Access nên migrate thành command trong ViewModel hoặc logic được command gọi.
- Không ưu tiên macro thành Workflow độc lập trong pha hiện tại.
- Nếu macro chỉ là chuỗi thao tác UI/navigation, map thành command + NavigationService.
- Nếu macro chạy query, command gọi Service, Service gọi Repository.
- Nếu macro chứa logic nghiệp vụ dài, command gọi Service chứa logic đó.

### Rule 8: Module

VBA:

```text
event -> module
module -> query
```

Expected WPF:

```text
handler/service -> module_service
module_service -> repository
```

Rule:

- Module VBA không nên map máy móc 1-1 thành service nếu nội dung không phải service.
- Trước mắt vẫn tạo `service:module:{moduleName}` để giữ trace.
- Sau này agent có thể phân loại module thành utility, domain service, validation service, formatter, hoặc infrastructure helper.

---

## 6. Trạng thái cạnh trong review graph sau này

Khi đã có Actual WPF Graph, cạnh/node cần có trạng thái:

| Status | Màu | Ý nghĩa |
|---|---|---|
| `ok` | Xanh | Expected và Actual khớp. |
| `missing` | Đỏ | Expected có nhưng Actual thiếu. |
| `extra` | Vàng | Actual có nhưng không trace được về VBA/BD/DD. |
| `mismatch` | Đỏ/cam | Có node/cạnh tương ứng nhưng sai target, sai layer, sai mapping. |
| `warning` | Vàng | Flow có thể đúng nhưng mapping/name chưa chắc chắn. |

Pha hiện tại `/api/graph-wpf` chưa cần trả status này, nhưng nên thiết kế node/edge để sau này dễ diff.

---

## 7. Các lỗi review cần phát hiện về sau

Khi Actual Graph đã có, agent cần bắt các lỗi:

| Lỗi | Ví dụ |
|---|---|
| Missing node | VBA có event/query/macro nhưng WPF code không có command/service/repository tương ứng. |
| Extra node | WPF có service/repository không trace được về VBA/BD/DD. |
| Wrong edge | ViewModel gọi Repository trực tiếp thay vì Service. |
| Wrong layer | SQL nằm trong ViewModel hoặc Service thay vì Repository. |
| Wrong direction | Repository gọi Service hoặc ViewModel. |
| Wrong navigation | Event VBA mở form A nhưng WPF command mở view B. |
| Binding mismatch | XAML binding `Command`, `ItemsSource`, `SelectedItem` không có property/command trong ViewModel. |
| DI mismatch | Service/Repository/ViewModel được dùng nhưng không đăng ký DI. |

---

## 8. Gap của implementation hiện tại

Các điểm cần chỉnh để expected graph đúng với mục tiêu mới:

1. Macro hiện đang map thành `workflow`. Cần đổi hoặc bổ sung mode để macro map thành `handler/command` trong ViewModel.
2. Chưa có node `NavigationService`; edge navigation đang đi trực tiếp `handler -> view`.
3. Chưa dùng BD/DD để bổ sung expected flow; hiện chủ yếu dựa vào VBA graph + mapping JSON.
4. Chưa đánh dấu fallback mapping, nên UI chưa biết node nào là chắc chắn và node nào là tên tự sinh.
5. Chưa có status `ok/missing/extra/mismatch` vì chưa có Actual Graph.
6. Query mapping hiện chưa đủ toàn bộ query, nhiều Repository sẽ fallback.
7. Report đang dùng chung logic View/ViewModel với Form; về sau có thể cần `ReportService`.

---

## 9. Definition of Done cho pha Expected WPF Graph

Pha này coi là xong khi:

- `/api/graph-wpf` trả graph ổn định cho `form`, `report`, `module`, `macro`.
- Mỗi Access Form/Report có `View -> ViewModel`.
- Mỗi Access Event có đúng một command/handler.
- Mỗi Access Query có đúng một Repository.
- Không có edge `ViewModel/Handler -> Repository` trực tiếp.
- Query luôn đi qua Service.
- Navigation có node/service trung gian rõ ràng.
- Macro được biểu diễn theo hướng command trong ViewModel, không mặc định là Workflow độc lập.
- Node/edge giữ được `vbaLabel` để trace về VBA gốc.
- Fallback mapping được đánh dấu để dev biết cần review tên.
- Output JSON đủ dữ liệu để sau này diff với Actual WPF Graph.

---

## 10. Kiến trúc đề xuất cho bước tiếp theo

Nên tách rõ 3 endpoint:

```text
/api/graph-wpf-expected
  -> Sinh Expected WPF Graph từ VBA + BD/DD + mapping.

/api/graph-wpf-actual
  -> Parse source WPF trong workflow/source/vba_brain.

/api/graph-wpf-review
  -> Diff Expected vs Actual, trả graph có status ok/missing/extra/mismatch.
```

Trong ngắn hạn có thể giữ `/api/graph-wpf` là expected graph, nhưng UI/document cần ghi rõ:

```text
WPF Graph = Expected WPF Graph, không phải actual code graph.
```

---

## 11. Checklist khi sửa mapping hiện tại

- [ ] Đổi macro mapping từ `workflow` sang command/handler theo mục tiêu mới.
- [ ] Thêm `NavigationService` node và gom open/close form/report vào node này, không show từng `DoCmd.OpenForm` / `DoCmd.Close`.
- [ ] Thêm `mappingStatus`: `mapped` hoặc `fallback`.
- [ ] Giữ `vbaLabel` cho mọi node WPF.
- [ ] Không bỏ edge VBA nếu chưa map được; đưa vào warning/fallback edge.
- [ ] Chuẩn hóa Unicode tên Access (`Ⅱ`, `II`, `2`, full-width number).
- [ ] Bổ sung docs ví dụ input/output cho một form cụ thể.
- [ ] Chuẩn bị schema JSON dùng chung cho expected/actual/review graph.
