# 🗃️ Agent Repo — Gen Entity + DTO + Repository

> **Mục đích:** Đọc DD SQL specs + table schema → sinh Entity, DTO, Interface + Repository hoàn chỉnh.  
> **Đặc điểm quan trọng:** Quá trình sinh code C# được thực hiện **100% bởi Tool** (0 tokens) để đảm bảo cấu trúc chuẩn xác tuyệt đối. LLM chỉ được triệu gọi trong Phase 2 để dịch các key tiếng Nhật dạng `TODO` trong config.  
> **Ref:** [AI_Agent_Workflow.md](./AI_Agent_Workflow.md)

---

## Output Naming Rules

| Output | Đặt tên theo | Thư mục đích / Namespace | Ví dụ |
|---|---|---|---|
| **Entity** | Tên table (ENG) | `Domain/Entities/{BaseName}Entity.cs` | `T_ID_PASS` → `IdPassEntity.cs` |
| **Input DTO** | Method base name + `InputDto` | `Domain/DTOs/{BaseName}/{Method}InputDto.cs` | `SearchInputDto.cs` |
| **Output DTO** | Method base name + `Dto` | `Domain/DTOs/{BaseName}/{Method}Dto.cs` | `GetLoginUserDto.cs` |
| **IRepository** | Table/Entity + `Repository` | `Domain/Interfaces/I{BaseName}Repository.cs` | `IIdPassRepository.cs` |
| **Repository** | Table/Entity + `Repository` | `Infrastructure/.../{BaseName}Repository.cs` | `IdPassRepository.cs` |

### 💡 Quy tắc Sinh DTO & Data Types
1. **Input DTO:** Chỉ sinh khi số lượng tham số đầu vào (VBA variables/SQL Parameters) của query **> 3**. Ngược lại truyền tham số trực tiếp.
2. **Return Type (Output):**
   - Trả về **Scalar Type** (`string`, `int`, `DateTime?`, etc.) nếu query chỉ SELECT đúng 1 cột.
   - Trả về **Entity Class** nếu query trả về nhiều cột và các cột đó khớp hoàn toàn (hoặc là subset) các trường của Entity tương ứng.
   - Trả về **Output DTO** riêng biệt `{MethodBaseName}Dto` nếu SELECT có thêm các trường ngoài Entity (JOIN fields, computed fields).
3. **Deduplication:** Các DTO có cấu trúc properties giống nhau sẽ được gom lại và tái sử dụng (sử dụng Cache chữ ký signature).

---

## Layer5 Folder / Files

```
backend/layer5/agents/repo/
├── agent_repo.py                 ← Điều phối chính (Main Agent)
├── tool_repo.py                  ← Trực tiếp phân tích & sinh mã nguồn C#
├── fill_json.py                  ← Sinh Repository Reference JSON phục vụ các Layer trên
├── config/
│   └── name_config.json          ← Tự động mapping (JP -> ENG) cho Tables, Fields, Params, Functions, CTEs
├── prompts/
│       └── agent_translate.md    ← System prompt (Translate Japanese to English)
```

---

## Logic Flow — 4 Phases

### Phase 1: Tải Dữ liệu & Đăng ký Config (0 tokens)
Agent tự động tải DD JSON từ MongoDB (`dds`, `bds`, `tables`). Nếu table schema chưa đầy đủ, Agent truy vấn trực tiếp MongoDB bằng thuật toán so khớp chữ cái Fullwidth/Halfwidth (NFKC Normalization) để lấy chính xác cấu trúc cột.
- Tự động trích xuất SQL queries, parameters và table schemas.
- Đăng ký tất cả các định danh tiếng Nhật (Tables, Fields, Params, Functions, CTEs) vào `config/name_config.json`.
- Nếu định danh đã có bản dịch tiếng Anh: Sử dụng trực tiếp. Chưa có: Gán mặc định `"TODO"` hoặc `"TODO_" + jp_name`.

### Phase 2: LLM Translator (Bản dịch "TODO" hàng loạt, ~1.5k token)
Agent quét `name_config.json`. Nếu có bất kỳ khóa nào mang giá trị `"TODO"`, Agent sẽ đóng gói chúng lại và gọi LLM để dịch toàn bộ cùng một lúc thông qua prompt `agent_translate.md`.
- Sau khi dịch thành công, Agent lưu kết quả ngược lại vào file config.
- Trường hợp lỗi API/Quota LLM: Agent log warning, thực hiện Fallback tự động và vẫn tiếp tục chạy Phase 3 an toàn với các định danh `TODO_` gốc.

### Phase 3: Code Generation & Merge (Tool-driven, 0 tokens)
`tool_repo.py` tiến hành sinh mã nguồn C# dựa trên file config hoàn chỉnh:
1. **Entity & DTO Generation**: Tạo class, kế thừa `BaseEntity`, sinh các thuộc tính với annotation `[Column("Tên_Tiếng_Nhật")]`.
2. **Signature Cache Deduplication**: Gom nhóm các DTO (cả Input DTO và Output DTO) có cùng cấu trúc bằng cơ chế Cache theo chữ ký, đảm bảo không sinh thừa các file DTO giống hệt nhau.
3. **Dependency & SQL Analysis**: Phân tích đệ quy mối quan hệ giữa các Query, bóc tách biểu thức WITH AS (CTE) thành các private helper method trả về SQL String. Sử dụng `StringBuilder` và ký pháp `@""` có escape ký tự nháy đúp chuẩn xác.
4. **Repository Generation**: Ánh xạ các phương thức truy vấn. Tự động bổ sung **XML Document Comments** chi tiết (`/// <summary>`, `<param>`, `<returns>`) chứa cả mục đích nghiệp vụ (`query_purpose`). Tự động quyết định hàm Dapper tối ưu (`QueryAsync`, `QueryFirstOrDefaultAsync`, `ExecuteScalarAsync` cho Single Column).

### Phase 4: Reference JSON & Legacy Cleanup
Sau khi sinh code, Agent kích hoạt quy trình dọn dẹp và đồng bộ tự động:
1. **Reference JSON Generation**: Kích hoạt `fill_json.generate_reference_json` để tạo file ánh xạ API Repository cho các Layer cao hơn (Service).
2. **Legacy File Cleanup**: Quét toàn bộ thư mục đích và xóa bỏ vĩnh viễn các file `TODO_*.cs` cũ (DTO/Entity) nếu chúng có cấu trúc cột trùng khớp hoàn toàn với file sạch mới sinh.

---

## Ví dụ Chi tiết mã nguồn được Sinh ra (Generated Code)

Dưới đây là ví dụ mô tả cấu trúc code được tạo ra sau khi qua Tool:

### Output 1: Domain/Entities/IdPassEntity.cs

```csharp
using System.ComponentModel.DataAnnotations.Schema;
using vba_brain.Domain.Entities.Base;

namespace vba_brain.Domain.Entities;

public class IdPassEntity : BaseEntity
{
    [Column("ID")]
    public string Id { get; set; } = string.Empty;

    [Column("PASS")]
    public string Pass { get; set; } = string.Empty;

    [Column("管理者FLG")]
    public int KanriFlg { get; set; }

    [Column("工事担当_担当者名")]
    public string KojiTantoName { get; set; } = string.Empty;  // 工事担当_担当者名
}
```

### Output 2: Domain/DTOs/IdPass/GetLoginUserDto.cs (Custom Output DTO)

```csharp
using System.ComponentModel.DataAnnotations.Schema;

namespace vba_brain.Domain.DTOs.IdPass;

public class GetLoginUserDto
{
    [Column("氏")]
    public string Sei { get; set; } = string.Empty;

    [Column("工事担当_担当者名")]
    public string KojiTantoName { get; set; } = string.Empty;

    [Column("支店名")]
    public string ShitenName { get; set; } = string.Empty;

    [Column("ID")]
    public string Id { get; set; } = string.Empty;
}
```

### Output 3: Domain/Interfaces/IIdPassRepository.cs

```csharp
using vba_brain.Domain.Entities;
using vba_brain.Domain.DTOs;
using vba_brain.Domain.DTOs.IdPass;

namespace vba_brain.Domain.Interfaces;

public interface IIdPassRepository
{
    Task<IdPassEntity?> GetByIdAsync(string id);
    Task<IEnumerable<GetLoginUserDto>> GetLoginUserAsync(string id);
}
```

### Output 4: Infrastructure/.../Repositories/IdPassRepository.cs

```csharp
using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;
using vba_brain.Domain.DTOs;
using vba_brain.Domain.DTOs.IdPass;
using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

public class IdPassRepository : IIdPassRepository
{
    private readonly DapperContext _context;
    public IdPassRepository(DapperContext context) => _context = context;

    /// Q000_Auth_SubQuery
    private string GetCte_AuthSubQuery()
    {
        var sql = new StringBuilder();
        sql.AppendLine(@"""Q000_Auth_SubQuery"" AS (");
        sql.AppendLine(@"    SELECT ID, ROLE_CD");
        sql.AppendLine(@"    FROM T_USER_ROLES");
        sql.AppendLine(@")");
        return sql.ToString();
    }

    /// <summary>
    /// Q000_T_LoginUser
    /// </summary>
    /// <param name="id"></param>
    /// <returns></returns>
    public async Task<IEnumerable<GetLoginUserDto>> GetLoginUserAsync(string id)
    {
        var sql = new StringBuilder();
        sql.Append("WITH ");
        sql.Append(GetCte_AuthSubQuery());
        sql.Append("\n");
        sql.AppendLine(@"SELECT SUBSTR(main.工事担当_担当者名, 1, INSTR(main.工事担当_担当者名, ' ') - 1) AS 氏,");
        sql.AppendLine(@"main.工事担当_担当者名, main.支店名, main.ID");
        sql.AppendLine(@"FROM T_ID_PASS main");
        sql.AppendLine(@"WHERE main.ID = :txtID");

        using var conn = _context.CreateConnection();
        return await conn.QueryAsync<GetLoginUserDto>(sql.ToString(), new { txtID = id });
    }

    /// <summary>
    /// DLookup_管理者FLG
    /// </summary>
    /// <param name="id"></param>
    /// <returns></returns>
    public async Task<IdPassEntity?> GetByIdAsync(string id)
    {
        var sql = new StringBuilder();
        sql.AppendLine(@"SELECT ID, PASS, 管理者FLG");
        sql.AppendLine(@"FROM T_ID_PASS");
        sql.AppendLine(@"WHERE ID = :txtID");

        using var conn = _context.CreateConnection();
        return await conn.QueryFirstOrDefaultAsync<IdPassEntity>(sql.ToString(), new { txtID = id });
    }
}
```

---

## Cơ chế Merge C# (Robust Merge Logic)

Hệ thống tích hợp thuật toán phân tích, lọc và trộn mã nguồn C# cấp độ khối code (`merge_csharp_code`):

1. **Auto-Healing:** Tự động phân tích số lượng dấu ngoặc `{` và `}`. Nếu file gốc bị thiếu ngoặc do lỗi lưu trước đó, hệ thống tự động chèn thêm `}` vào cuối để đảm bảo tính hợp lệ trước khi xử lý.
2. **Pre-Cleanup Legacy TODOs:** Trước khi chèn phương thức hoặc Interface mới, hệ thống quét và loại bỏ triệt để tất cả phương thức/Interface cũ mang tiền tố `TODO_` ứng với cùng một Query tiếng Nhật.
3. **Smart Property Replacement:** Đối với Properties trong Entity/DTO, thuật toán ưu tiên so khớp chuẩn xác thông qua Annotation `[Column("Tên_Tiếng_Nhật")]`. Nếu không có, thuật toán so khớp qua comment `TODO: translate '...'` để ghi đè, dọn sạch các Property `TODO_` cũ mà không làm biến dạng thứ tự code.
4. **Matching Anchors for Methods & CTEs:**
   - **Cấp độ 1:** Định vị tuyệt đối bằng Comment Query tiếng Nhật (ví dụ: `/// Q000_T_LoginUser`). Hệ thống tự động định vị và cắt bỏ toàn bộ khối lệnh bao gồm các dòng `///` comment cũ mà không để lại rác.
   - **Cấp độ 2:** So khớp theo chữ ký phương thức (`public async Task<...>`, `private string Cte_...`).
5. **Safe Insertion:** Đối với các thành phần hoàn toàn mới, hệ thống tìm vị trí dấu ngoặc nhọn kết thúc Class (`}`) để chèn an toàn vào cuối class, đồng thời tự động gộp và sắp xếp lại các khối `using` ở đầu file.

---

## Verification

- [ ] Check `name_config.json` xem đã dịch hết các key `TODO` chưa.
- [ ] Đảm bảo Entity Class kế thừa `BaseEntity` và có đủ data annotation `[Column("...")]`.
- [ ] Các tham số Oracle được binding đúng dạng `:param` thông qua anonymous object trong Dapper.
- [ ] Các truy vấn có CTE (WITH) đã được sinh phương thức private string builder phụ trợ chưa.
- [ ] Hàm có > 3 param đã được gói thành `InputDto` đặt tại `Domain/DTOs/{TableBaseName}/` chưa.
- [ ] File code C# tại thư mục `source/` đã được merge đầy đủ phương thức mới mà không làm mất code cũ hay thiếu ngoặc chưa.
- [ ] Entity fields khớp table schema (MongoDB `tables[]`)
- [ ] Entity đặt tên theo table gốc + `Entity` suffix
- [ ] Repository đặt tên theo table/entity + `Repository` suffix
- [ ] Interface methods cover tất cả queries cần dùng
- [ ] Repository SQL khớp queries_v2 (Oracle syntax)