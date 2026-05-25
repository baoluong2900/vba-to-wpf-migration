using System.Collections.Generic;
using System.Threading.Tasks;
using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

public interface IAfterMainRepository
{
    Task<AfterMainEntity?> GetBySeqNoAsync(long seqNo);
    Task<IEnumerable<AfterMainEntity>> GetAllAsync();
    Task<IEnumerable<AfterMainEntity>> GetByDistrictAsync(string districtCd);
    Task<long> InsertAsync(AfterMainEntity entity);
    Task<bool> UpdateAsync(AfterMainEntity entity);
    Task<bool> DeleteAsync(long seqNo);
}
