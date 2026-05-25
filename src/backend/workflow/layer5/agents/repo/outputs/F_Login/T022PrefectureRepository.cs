using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

/// <summary>
/// T022_都道府県抽出用
/// </summary>
public class T022PrefectureRepository : IT022PrefectureRepository
{
    private readonly DapperContext _context;
    public T022PrefectureRepository(DapperContext context) => _context = context;

    /// <summary>
    /// Q023_地区CD設定
    /// 選択がYesのレコードから地区CDと地区CD頭2文字を抽出し、新しいテーブルT023_地区CD設定を作成する
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<T022PrefectureEntity>> GetRegionCdAsync()
    {
        var sql = new StringBuilder();
        sql.AppendLine(@"SELECT t1.地区CD ");
        sql.AppendLine(@", t1.地区CD頭２文字");
        sql.AppendLine(@"FROM T022_都道府県抽出用 t1");
        sql.AppendLine(@"WHERE t1.選択 = 1");
        using var conn = _context.CreateConnection();
        return await conn.QueryAsync<T022PrefectureEntity>(sql.ToString());
    }
}
