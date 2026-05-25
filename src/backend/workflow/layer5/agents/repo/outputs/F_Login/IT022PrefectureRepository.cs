using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

/// <summary>
/// T022_都道府県抽出用
/// </summary>
public interface IT022PrefectureRepository
{
    /// <summary>
    /// Q023_地区CD設定
    /// 選択がYesのレコードから地区CDと地区CD頭2文字を抽出し、新しいテーブルT023_地区CD設定を作成する
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<T022PrefectureEntity>> GetRegionCdAsync();
}
