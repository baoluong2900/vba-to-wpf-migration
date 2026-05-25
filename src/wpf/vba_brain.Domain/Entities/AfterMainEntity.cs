using System;
using vba_brain.Domain.Common;

namespace vba_brain.Domain.Entities;

public class AfterMainEntity : BaseEntity
{
    public long SeqNo { get; set; }
    public string AfterCd { get; set; } = string.Empty;
    public string CustomerNm { get; set; } = string.Empty;
    public ServiceType ServiceType { get; set; }
    public decimal PaymentAmt { get; set; }
    public PaymentFlag PaymentFlg { get; set; }
    public string DistrictCd { get; set; } = string.Empty;
    public DateTime ReceiveDt { get; set; }
}
