using System.Collections.Generic;
using System.Threading.Tasks;
using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

public interface IPaymentRepository
{
    Task<IEnumerable<PaymentEntity>> GetBySeqNoAsync(long seqNo);
    Task<long> InsertAsync(PaymentEntity entity);
}
