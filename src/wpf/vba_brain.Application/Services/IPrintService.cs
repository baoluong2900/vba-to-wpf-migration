using System.Threading.Tasks;
using vba_brain.Application.DTOs;

namespace vba_brain.Application.Services;

public interface IPrintService
{
    Task<bool> PrintDocumentAsync(PrintRequestDto request);
    System.Threading.Tasks.Task<System.Collections.Generic.IEnumerable<vba_brain.Domain.Entities.PrintDocumentEntity>> GetHistoryBySeqNoAsync(long seqNo);
}
