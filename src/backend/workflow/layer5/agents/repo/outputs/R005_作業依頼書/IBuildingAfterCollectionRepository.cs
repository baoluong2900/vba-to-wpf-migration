using vba_brain.Domain.Entities;
using vba_brain.Domain.DTOs;
using vba_brain.Domain.DTOs.BuildingAfterCollection;

namespace vba_brain.Domain.Interfaces;

/// <summary>
/// TBLビルアフター回収
/// </summary>
public interface IBuildingAfterCollectionRepository
{
    /// <summary>
    /// Q005_アフターメンテナンス受付
    /// 指定された登録番号に一致するAM受付とアフター回収データを結合して取得するクエリ
    /// </summary>
    /// <param name="registrationNumberBf"></param>
    /// <param name="registrationNumberB"></param>
    /// <returns></returns>
    Task<IEnumerable<AfterMaintenanceReceptionDto>> AfterMaintenanceReceptionAsync(string registrationNumberBf, string registrationNumberB);
}
