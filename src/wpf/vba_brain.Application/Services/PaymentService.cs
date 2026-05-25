using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using vba_brain.Application.DTOs;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

namespace vba_brain.Application.Services;

public class PaymentService : IPaymentService
{
    private readonly IPaymentRepository _repository;

    public PaymentService(IPaymentRepository repository)
    {
        _repository = repository;
    }

    public async Task<IEnumerable<PaymentDto>> GetBySeqNoAsync(long seqNo)
    {
        var list = await _repository.GetBySeqNoAsync(seqNo);
        return list.Select(e => new PaymentDto
        {
            PaymentId = e.PaymentId,
            SeqNo = e.SeqNo,
            Amount = e.Amount,
            PaymentDt = e.PaymentDt,
            Note = e.Note
        });
    }

    public async Task<bool> ProcessPaymentAsync(PaymentDto dto)
    {
        var entity = new PaymentEntity
        {
            PaymentId = dto.PaymentId,
            SeqNo = dto.SeqNo,
            Amount = dto.Amount,
            PaymentDt = dto.PaymentDt,
            Note = dto.Note
        };
        var id = await _repository.InsertAsync(entity);
        dto.PaymentId = id;
        return id > 0;
    }
}
