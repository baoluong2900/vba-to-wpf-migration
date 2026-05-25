using System;

namespace vba_brain.Domain.Entities;

public abstract class BaseEntity
{
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public string CreatedBy { get; set; } = "System";
    public DateTime? UpdatedAt { get; set; }
    public string? UpdatedBy { get; set; }
}
