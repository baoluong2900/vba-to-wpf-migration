using vba_brain.Domain.Entities;
using vba_brain.Domain.DTOs;
using vba_brain.Domain.DTOs.Auth;

namespace vba_brain.Domain.Interfaces;

/// <summary>
/// T101_ID_PASS
/// </summary>
public interface IAuthRepository
{
    /// <summary>
    /// Q000_T_LoginUser
    /// T_ID_PASSテーブルから指定されたIDのユーザー情報を抽出し、担当者名を姓と名に分割してT_LoginUserテーブルを作成する
    /// </summary>
    /// <param name="ID"></param>
    /// <returns></returns>
    Task<IEnumerable<GetUserInfoDto>> GetUserInfoAsync(string ID);

    /// <summary>
    /// T_ID_pass
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<AuthEntity>> IdPassAsync();

    /// <summary>
    /// Q000_T_ID_PASS
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<AuthEntity>> QIdPassAsync();
}
