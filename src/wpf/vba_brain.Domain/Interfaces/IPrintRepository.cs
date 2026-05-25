using System.Collections.Generic;
using System.Threading.Tasks;
using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

public interface IPrintRepository
{
    Task<IEnumerable<PrintDocumentEntity>> GetHistoryBySeqNoAsync(long seqNo);
    Task<long> InsertLogAsync(PrintDocumentEntity entity);
}
