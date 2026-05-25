using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

/// <summary>
/// TBLビルアフター回収
/// </summary>
public interface IBuildingAfterCollectionRepository
{
    /// <summary>
    /// Access配信日
    /// 登録番号が'900-79-00136-000'であるレコードのコメントを取得する
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<string>> GetCommentAsync();
}
