using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using vba_brain.Domain.Entities.Base;

namespace vba_brain.Domain.Entities;

/// <summary>
/// Access配信日
/// </summary>
public class Access配信日Entity : BaseEntity
{
    [MaxLength(255)]
    [Column("配信日コメント")]
    public object DistributionDateComment { get; set; }  // 配信日コメント
}
