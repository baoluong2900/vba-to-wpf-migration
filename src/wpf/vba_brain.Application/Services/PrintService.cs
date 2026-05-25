using System;
using System.Threading.Tasks;
using vba_brain.Application.DTOs;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

namespace vba_brain.Application.Services;

public class PrintService : IPrintService
{
    private readonly IPrintRepository _repository;

    public PrintService(IPrintRepository repository)
    {
        _repository = repository;
    }

    public async Task<bool> PrintDocumentAsync(PrintRequestDto request)
    {
        // Log printing activity
        var entity = new PrintDocumentEntity
        {
            SeqNo = request.SeqNo,
            DocType = request.DocType,
            PrintedAt = DateTime.UtcNow,
            OperatorName = request.OperatorName
        };

        var logId = await _repository.InsertLogAsync(entity);
        return logId > 0;
    }

    public async Task<System.Collections.Generic.IEnumerable<vba_brain.Domain.Entities.PrintDocumentEntity>> GetHistoryBySeqNoAsync(long seqNo)
    {
        return await _repository.GetHistoryBySeqNoAsync(seqNo);
    }
}
