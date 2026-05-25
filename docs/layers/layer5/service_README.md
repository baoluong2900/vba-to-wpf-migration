# Agent Service — Cơ chế hoạt động

Tài liệu mô tả **cách thư mục `agents/service` chạy** trong Layer 5 (sinh `IService` + `*Service.cs` cho migration Access → WPF/C#). Spec thiết kế tổng thể xem thêm [`Agent_Service.md`](../../docs/Design/AI%20Agent%20workflow/Agent_Service.md).

> **Codegen:** Mặc định **deterministic** qua `tool_service_gen` (không LLM). Tuỳ chọn **`--llm`**: sinh `{Feature}Service.cs` bằng `L5LLMClient` + `prompts/agent_service_form.md`; interface vẫn Jinja2. Prompt còn lại (`agent_service_macro.md`, …) chỉ tham khảo nếu không dùng nhánh LLM form.

---

## 1. Vai trò trong pipeline

- **Thứ tự:** sau **Agent Repo** (DTO, Entity, `I*Repository`, Repository).
- **Nhiệm vụ:** sinh lớp **Application Service** (interface + implementation) cho mỗi form. Mỗi event trong unified input được map thành **một method async** trên service. Service orchestrates các `I*Repository` đã có từ Agent Repo.
- **Hợp đồng:** Service **phải khớp** tên type / method với output Repo và với Agent Logic phía sau (ViewModel inject DI).

---

## 2. Cấu trúc thư mục

```
agents/service/
├── agent_service.py            # ServiceAgent + build_service_input (Mongo/file) + optional LLM impl
├── tool_service_gen.py         # Deterministic codegen — sinh {Feature}Service.cs
├── __init__.py                 # export ServiceAgent
├── inputs/                     # JSON / debug (optional)
│   ├── {Form}_dd.json                  # offline fallback only
│   ├── {Form}_repository_ouput.json   # offline fallback only
│   └── {Form}_service_input.json       # chỉ khi `--save-input` hoặc `persist_service_input_json`
├── outputs/                    # snapshot .cs đã sinh
│   └── {Form}/*.cs
└── prompts/
    ├── agent_service.md
    ├── agent_service_form.md   # dùng khi chạy `--llm` (implementation)
    ├── agent_service_macro.md
    └── agent_service_module.md
```

---

## 3. Định nghĩa Input (unified)

`agent_service.build_service_input` / loaders trong cùng module lắp payload **trong RAM** mỗi lần chạy Agent Service. Mặc định:

| Nguồn | Collection / chỗ đọc |
|--------|----------------------|
| DD | MongoDB **`dds`** — `find_one({ "name": form_name })` (fallback `form_name` / `screen_name`), sau đó file local nếu không có DB |
| Repository contract | MongoDB **`agent_repo`** — `find_one({ "name": form_name })` (fallback `form_name` / `screen_name`), sau đó `inputs/{Form}_repository_*.json` |
| VBA | MongoDB **`forms`** — như cũ |

Tên collection có thể ghi đè bằng biến môi trường `MONGO_COL_DDS`, `MONGO_COL_AGENT_REPO` (xem `core/config.py`).

Ghi file `inputs/{form}_service_input.json` **chỉ khi** bạn bật `--save-input` (CLI Service) hoặc `AgentInput.persist_service_input_json=True` (pipeline / test).

```jsonc
{
  "form_name": "F_Login",
  "screen_id": "F_Login",
  "screen_name": "F_Login",
  "source": {
    "dd_path": "",
    "repo_output_path": "",
    "dd_origin": "mongodb:dds",
    "repo_origin": "mongodb:agent_repo",
    "mongodb_forms": true,
    "filter_mode": "any_repo_signal"
  },
  "stats": {
    "detail_specs_total": 10,
    "events_kept": 4,
    "events_with_query_mappings": 2,
    "events_with_vba_query_op": 3,
    "vba_functions": 9
  },
  "events": [                          // events cần giao tiếp với repository
    {
      "sheet_name_pattern": "詳細仕様書_F003",
      "module_id": "F003",
      "module_name": "パスワード：",
      "event_trigger": "更新後処理",
      "event_content": "...",
      "steps": [...],
      "query_mappings": [],            // có thể rỗng — vẫn được giữ nếu VBA có query op
      "matched_vba": {                 // handler VBA gắn với event (có thể null)
        "handler": "txtPass_AfterUpdate",
        "type": "Sub",
        "input": "",
        "output": "",
        "code": "..."                  // body VBA gốc
      },
      "repo_signals": ["vba_query_op"] // dấu hiệu nào quyết định giữ event này
    }
  ],
  "vba_functions": [                   // toàn bộ functions của form từ MongoDB
    { "handler": "Form_Open", "type": "Sub", "input": "...", "output": "", "code": "..." }
  ],
  "repository_contracts": {            // passthrough từ Agent Repo
    "repositories": [...],
    "dtos": [...],
    "entities": [...]
  }
}
```

### Nguồn input

| Field | Nguồn | Ghi chú |
|---|---|---|
| `events` | `dd_json.sheet_3_detail_specs[]` (DD lấy từ **`dds`** hoặc `AgentInput.dd_json`) | Áp dụng filter; kèm `matched_vba` + `repo_signals` |
| `vba_functions` | MongoDB **`forms`** | `functions[]` / `vba_procedures[]` |
| `repository_contracts` | MongoDB **`agent_repo`** (hoặc file fallback) | Cùng shape với JSON Agent Repo (repository, dto, entity) |

### Filter modes

| Mode | Mô tả |
|---|---|
| `any_repo_signal` (mặc định) | Giữ event nếu `query_mappings` không rỗng **HOẶC** matched VBA chứa op truy vấn (`DLookup`, `DCount`, `DoCmd.RunSQL`, `DoCmd.OpenQuery`, `CurrentDb`, `OpenRecordset`, `Execute`). Bắt được các event như F003 (login auth dùng `DLookup`) mà DD bỏ trống `query_mappings`. |
| `query_mappings_only` | Strict — chỉ giữ event có `query_mappings` không rỗng. |

### Match VBA handler ↔ DD event

Match được thực hiện theo 3 pass có kiểm soát noise:

1. `module_name` (control name) + suffix theo `event_trigger` (vd `txtPass` + 更新後処理 → `txtPass_AfterUpdate`).
2. Sự kiện form-level (module_name là `-`/empty) + suffix nằm trong `FORM_LEVEL_SUFFIXES` (`_Open`, `_Load`, `_Close`, `_Timer`, ...) → ưu tiên `Form_<suffix>` hoặc unique candidate.
3. Label heuristic — `module_name` là nhãn tiếng Nhật + suffix trong `LABEL_HEURISTIC_SUFFIXES` (`_AfterUpdate`, `_BeforeUpdate`, `_KeyDown`, `_KeyUp`, `_Timer`) và chỉ có đúng 1 candidate → accept.

**Cố ý KHÔNG** auto-match `_Click` / `_DblClick` khi module_name không khớp — nhiều control trên cùng form thường share suffix này, dễ false-positive.

### Sinh input

```bash
# Chỉ ghi unified JSON (tương đương tool_service cũ)
python -X utf8 agents/service/agent_service.py F_Login --dump-service-input
```

---

## 4. Luồng `ServiceAgent.run(AgentInput)`

1. **Build unified input (in-memory)** — `build_service_input` (+ loaders trong `agent_service.py`):
   - DD: `dds` (hoặc override `AgentInput.dd_json`).
   - Contract: `agent_repo`.
   - VBA: `forms`.
2. **Sinh interface** — Jinja2 `I{Feature}Service.cs`.
3. **Sinh implementation** — `tool_service_gen.py` (deterministic) **hoặc** LLM nếu `service_codegen_mode="llm"` / CLI `--llm`.
4. **Ghi snapshot** `outputs/{form_name}/*.cs`.
5. (Tuỳ chọn) **Ghi** `inputs/{form}_service_input.json` nếu bật persist.

`pipeline/orchestrator.py` gọi Service với **`dd_json` để trống** (default) để Service đọc DD từ MongoDB `dds` thay vì file layer3.

---

## 5. Input / Output chuẩn

### `AgentInput` (từ `core.models`)

- `form_name` — ví dụ `F_Login`
- `dd_json` — **để trống** trong production → đọc DD từ MongoDB `dds`. Nếu có (dict không rỗng) → override, dùng cho test / legacy.
- `service_filter_mode` — `"any_repo_signal"` (mặc định) hoặc `"query_mappings_only"` (xem mục Filter modes).
- `persist_service_input_json` — `True` thì ghi `inputs/{form}_service_input.json` sau khi build payload.
- `mongodb_data.form` (tùy chọn) — nếu cung cấp, dùng thay vì query collection `forms` cho `vba_functions`.
- `service_codegen_mode` — `"tool"` (mặc định) hoặc `"llm"` (sinh `*Service.cs` qua LLM; interface vẫn Jinja2).
- `model_override` — dùng khi `service_codegen_mode="llm"` (cùng convention `AVAILABLE_MODELS` / `--model` như agent khác).
- `upstream_files` — khi chạy LLM, các file `.cs` từ Agent Repo được đính kèm prompt tham khảo.

### File logic (`GeneratedFile.path`)

- `Application/Interfaces/I{Feature}Service.cs` — `generator="jinja2"`
- `Application/Services/{Feature}Service.cs` — `generator="tool"` (deterministic) hoặc `generator="llm"`

> Lưu ý: Pipeline hiện không còn sinh `INavigationService` / `ICommonService` ở agent này. Các `DoCmd.RunMacro`, `Call <Module>` v.v. nằm trong DD `steps[]` được giữ nguyên dưới dạng comment để dev biết chỗ cần wire sang service navigation/common (agent khác hoặc bước migration sau đảm nhiệm).

---

## 6. Cách chạy CLI

Từ thư mục `backend/layer5`:

```bash
cd backend/layer5

python -X utf8 agents/service/agent_service.py F_Login
python -X utf8 agents/service/agent_service.py F_Login --save-input
python -X utf8 agents/service/agent_service.py F_Login --filter-mode query_mappings_only

python -X utf8 agents/service/agent_service.py F_Login --llm
python -X utf8 agents/service/agent_service.py F_Login --llm --model qwen3-coder-plus

# Chỉ dump unified JSON
python -X utf8 agents/service/agent_service.py F_Login --dump-service-input
```

Orchestrator (`pipeline/orchestrator.py`) gọi `ServiceAgent()` sau `RepoAgent`, truyền `upstream_files` từ Repo; **không** truyền `dd_json` để Service đọc DD từ MongoDB `dds`.

---

## 7. Hạn chế / lưu ý khi đọc output

- Method body chỉ **resolve `query_mappings`** thành repo call; logic phức tạp (if/else theo `管理者FLG`, validation message tiếng Nhật, branching macro/module) được giữ ở dạng comment để dev điền tay. Đây là chủ ý — tool-based gen ưu tiên đúng và traceable thay vì cố đoán.
- Nếu DD bỏ trống `query_mappings` nhưng VBA matched có data-access op → method có `// TODO: ... DLookup/DCount ... wire repository call manually` để cảnh báo.
- Nếu `logic_query_name` không khớp repository function nào trong contract → method có `// TODO: Repository function not found for query 'X'` — bug ở upstream Agent Repo (thiếu mapping hoặc đánh sai `sheet_query_name`).
- Tham số method (vd `request.TxtID`) được suy luận từ `parameters[].mapping`. Nếu DTO Request chưa có property tương ứng, code sẽ không build — cần đối chiếu với DTO do Agent Repo sinh.

---

## 8. Liên kết

- Design: `docs/Design/AI Agent workflow/Agent_Service.md`
- Models: `core/models.py` (`BaseAgent`, `AgentInput`, `AgentOutput`)
- Repo trước đó: `agents/repo/agent_repo.py`
- Builder + loaders: `agents/service/agent_service.py` (`build_service_input`, …)
- Codegen tool: `agents/service/tool_service_gen.py`
