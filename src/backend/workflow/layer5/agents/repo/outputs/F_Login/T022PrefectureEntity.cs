using System.ComponentModel.DataAnnotations.Schema;
using vba_brain.Domain.Entities.Base;

namespace vba_brain.Domain.Entities;

/// <summary>
/// T022_都道府県抽出用
/// </summary>
public class T022PrefectureEntity : BaseEntity
{
    [Column("都道府県CD")]
    public decimal PrefectureCd { get; set; }  // 都道府県CD
    [Column("地区CD")]
    public string RegionCd { get; set; } = string.Empty;  // 地区CD
    [Column("店所名")]
    public string StoreName { get; set; } = string.Empty;  // 店所名
    [Column("支店CD")]
    public string BranchCd { get; set; } = string.Empty;  // 支店CD
    [Column("地方CD")]
    public decimal DistrictCd { get; set; }  // 地方CD
    [Column("選択")]
    public decimal Selected { get; set; }  // 選択
    [Column("回収店所")]
    public string CollectionBranch { get; set; } = string.Empty;  // 回収店所
    [Column("地区CD頭２文字")]
    public string RegionCdFirstTwoChars { get; set; } = string.Empty;  // 地区CD頭２文字
    [Column("支店名")]
    public string BranchName { get; set; } = string.Empty;  // 支店名
}
