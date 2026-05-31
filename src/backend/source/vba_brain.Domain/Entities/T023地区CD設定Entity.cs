using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using vba_brain.Domain.Entities.Base;

namespace vba_brain.Domain.Entities;

/// <summary>
/// T023_地区CD設定
/// </summary>
public class T023地区CD設定Entity : BaseEntity
{
    [MaxLength(4)]
    [Column("地区コードID")]
    public object AreaCodeId { get; set; }  // 地区コードID
}
