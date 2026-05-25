using System.ComponentModel.DataAnnotations.Schema;
using vba_brain.Domain.Entities.Base;

namespace vba_brain.Domain.Entities;

/// <summary>
/// T101_ID_PASS
/// </summary>
public class AuthEntity : BaseEntity
{
    [Column("地区CD_ID")]
    public string RegionCdId { get; set; } = string.Empty;  // 地区CD_ID
    [Column("ID")]
    public string Id { get; set; } = string.Empty;  // ID
    [Column("PASS")]
    public string Pass { get; set; } = string.Empty;  // PASS
    [Column("工事担当_担当者名")]
    public string ConstructionHandlerName { get; set; } = string.Empty;  // 工事担当_担当者名
    [Column("担当者CD_A")]
    public string HandlerCdA { get; set; } = string.Empty;  // 担当者CD_A
    [Column("支店名")]
    public string BranchName { get; set; } = string.Empty;  // 支店名
    [Column("地区CD")]
    public string RegionCd { get; set; } = string.Empty;  // 地区CD
    [Column("管理者FLG")]
    public string AdminFlag { get; set; } = string.Empty;  // 管理者FLG
}
