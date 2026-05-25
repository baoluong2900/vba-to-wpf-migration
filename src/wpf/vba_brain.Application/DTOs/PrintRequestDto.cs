namespace vba_brain.Application.DTOs;

public class PrintRequestDto
{
    public long SeqNo { get; set; }
    public string DocType { get; set; } = string.Empty; // e.g. 見積書, 請求書
    public bool IsBlankTemplate { get; set; }
    public string OperatorName { get; set; } = "System";
}
