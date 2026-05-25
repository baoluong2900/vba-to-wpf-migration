using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;
using vba_brain.Domain.DTOs;
using vba_brain.Domain.DTOs.Auth;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

/// <summary>
/// T101_ID_PASS
/// </summary>
public class AuthRepository : IAuthRepository
{
    private readonly DapperContext _context;
    public AuthRepository(DapperContext context) => _context = context;

    /// <summary>
    /// Q000_T_LoginUser
    /// T_ID_PASSテーブルから指定されたIDのユーザー情報を抽出し、担当者名を姓と名に分割してT_LoginUserテーブルを作成する
    /// </summary>
    /// <param name="ID"></param>
    /// <returns></returns>
    public async Task<IEnumerable<GetUserInfoDto>> GetUserInfoAsync(string ID)
    {
        var sql = new StringBuilder();
        sql.AppendLine(@"SELECT SUBSTR (t1.工事担当_担当者名 , 1 , INSTR (t1.工事担当_担当者名 , ' ') - 1) AS 氏 ");
        sql.AppendLine(@", SUBSTR (t1.工事担当_担当者名 , INSTR (t1.工事担当_担当者名 , ' ') + 1) AS 名 ");
        sql.AppendLine(@", t1.工事担当_担当者名 ");
        sql.AppendLine(@", t1.支店名 ");
        sql.AppendLine(@", t1.地区CD ");
        sql.AppendLine(@", t1.地区CD_ID ");
        sql.AppendLine(@", t1.ID ");
        sql.AppendLine(@", t1.PASS ");
        sql.AppendLine(@", t1.管理者FLG ");
        sql.AppendLine(@", t1.担当者CD_A");
        sql.AppendLine(@"FROM T101_ID_PASS t1");
        sql.AppendLine(@"WHERE t1.ID =:txtID");
        sql.AppendLine(@"ORDER BY t1.地区CD ");
        sql.AppendLine(@", t1.ID");
        using var conn = _context.CreateConnection();
        return await conn.QueryAsync<GetUserInfoDto>(sql.ToString(), new { txtID = ID });
    }

    /// <summary>
    /// T_ID_pass
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<AuthEntity>> IdPassAsync()
    {
        return await Task.FromResult(Enumerable.Empty<AuthEntity>());
    }

    /// <summary>
    /// Q000_T_ID_PASS
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<AuthEntity>> QIdPassAsync()
    {
        return await Task.FromResult(Enumerable.Empty<AuthEntity>());
    }
}
