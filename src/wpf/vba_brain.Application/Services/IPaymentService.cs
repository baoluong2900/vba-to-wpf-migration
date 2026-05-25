using System.Collections.Generic;
using System.Threading.Tasks;
using vba_brain.Application.DTOs;

namespace vba_brain.Application.Services;

public interface IPaymentService
{
    Task<IEnumerable<PaymentDto>> GetBySeqNoAsync(long seqNo);
    Task<bool> ProcessPaymentAsync(PaymentDto dto);
}
