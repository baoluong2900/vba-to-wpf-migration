using System;

namespace vba_brain.Domain.Entities;

public class PrintDocumentEntity : BaseEntity
{
    public long PrintId { get; set; }
    public long SeqNo { get; set; }
    public string DocType { get; set; } = string.Empty; // e.g. 見積書, 請求書
    public DateTime PrintedAt { get; set; }
    public string OperatorName { get; set; } = string.Empty;
}
