using System;

namespace vba_brain.Application.DTOs;

public class AfterMainDto
{
    public long SeqNo { get; set; }
    public string AfterCd { get; set; } = string.Empty;
    public string CustomerNm { get; set; } = string.Empty;
    public string ServiceType { get; set; } = string.Empty;
    public decimal PaymentAmt { get; set; }
    public string PaymentFlg { get; set; } = string.Empty;
    public string DistrictCd { get; set; } = string.Empty;
    public DateTime ReceiveDt { get; set; }
}
