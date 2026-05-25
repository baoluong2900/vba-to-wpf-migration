using System.Collections.Generic;
using System.Threading.Tasks;
using vba_brain.Application.DTOs;

namespace vba_brain.Application.Services;

public interface IAfterMainService
{
    Task<AfterMainDto?> GetBySeqNoAsync(long seqNo);
    Task<IEnumerable<AfterMainDto>> GetAllAsync();
    Task<bool> SaveAsync(AfterMainDto dto);
    Task<bool> DeleteAsync(long seqNo);
}
