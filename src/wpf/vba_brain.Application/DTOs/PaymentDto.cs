using System;

namespace vba_brain.Application.DTOs;

public class PaymentDto
{
    public long PaymentId { get; set; }
    public long SeqNo { get; set; }
    public decimal Amount { get; set; }
    public DateTime PaymentDt { get; set; }
    public string Note { get; set; } = string.Empty;
}
