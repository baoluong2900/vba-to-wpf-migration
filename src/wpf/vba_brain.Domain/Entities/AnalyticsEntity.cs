namespace vba_brain.Domain.Entities;

public class AnalyticsEntity : BaseEntity
{
    public string Period { get; set; } = string.Empty; // e.g. 2026-05
    public string Category { get; set; } = string.Empty;
    public decimal TotalAmount { get; set; }
    public int Count { get; set; }
}
