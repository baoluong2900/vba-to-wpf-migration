using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using vba_brain.Application.DTOs;
using vba_brain.Domain.Common;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

namespace vba_brain.Application.Services;

public class AfterMainService : IAfterMainService
{
    private readonly IAfterMainRepository _repository;

    public AfterMainService(IAfterMainRepository repository)
    {
        _repository = repository;
    }

    public async Task<AfterMainDto?> GetBySeqNoAsync(long seqNo)
    {
        var entity = await _repository.GetBySeqNoAsync(seqNo);
        if (entity == null) return null;
        return MapToDto(entity);
    }

    public async Task<IEnumerable<AfterMainDto>> GetAllAsync()
    {
        var list = await _repository.GetAllAsync();
        return list.Select(MapToDto);
    }

    public async Task<bool> SaveAsync(AfterMainDto dto)
    {
        var entity = MapToEntity(dto);
        if (dto.SeqNo == 0)
        {
            var seq = await _repository.InsertAsync(entity);
            dto.SeqNo = seq;
            return seq > 0;
        }
        else
        {
            return await _repository.UpdateAsync(entity);
        }
    }

    public async Task<bool> DeleteAsync(long seqNo)
    {
        return await _repository.DeleteAsync(seqNo);
    }

    private static AfterMainDto MapToDto(AfterMainEntity entity)
    {
        return new AfterMainDto
        {
            SeqNo = entity.SeqNo,
            AfterCd = entity.AfterCd,
            CustomerNm = entity.CustomerNm,
            ServiceType = entity.ServiceType.ToString(),
            PaymentAmt = entity.PaymentAmt,
            PaymentFlg = entity.PaymentFlg.ToString(),
            DistrictCd = entity.DistrictCd,
            ReceiveDt = entity.ReceiveDt
        };
    }

    private static AfterMainEntity MapToEntity(AfterMainDto dto)
    {
        Enum.TryParse<ServiceType>(dto.ServiceType, out var st);
        Enum.TryParse<PaymentFlag>(dto.PaymentFlg, out var pf);

        return new AfterMainEntity
        {
            SeqNo = dto.SeqNo,
            AfterCd = dto.AfterCd,
            CustomerNm = dto.CustomerNm,
            ServiceType = st,
            PaymentAmt = dto.PaymentAmt,
            PaymentFlg = pf,
            DistrictCd = dto.DistrictCd,
            ReceiveDt = dto.ReceiveDt
        };
    }
}
