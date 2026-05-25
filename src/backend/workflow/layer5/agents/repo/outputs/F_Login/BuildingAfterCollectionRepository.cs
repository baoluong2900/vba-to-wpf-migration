using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

/// <summary>
/// TBLビルアフター回収
/// </summary>
public class BuildingAfterCollectionRepository : IBuildingAfterCollectionRepository
{
    private readonly DapperContext _context;
    public BuildingAfterCollectionRepository(DapperContext context) => _context = context;

    /// <summary>
    /// Access配信日
    /// 登録番号が'900-79-00136-000'であるレコードのコメントを取得する
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<string>> GetCommentAsync()
    {
        var sql = new StringBuilder();
        sql.AppendLine(@"SELECT コメント");
        sql.AppendLine(@"FROM TBLビルアフター回収");
        sql.AppendLine(@"WHERE 登録番号 = '900-79-00136-000'");
        using var conn = _context.CreateConnection();
        return await conn.QueryAsync<string>(sql.ToString());
    }
}
